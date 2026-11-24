import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculos.fechas import ahora_local, en_franja_silencio, hora_a_minutos
from app.config import configuracion
from app.modelos import AjusteServidor, EnvioRecordatorio, Perfil, Recordatorio, SuscripcionPush, ahora_utc

VENTANA_MINUTOS = 120
TEXTOS = {
    "comida": "Hora de la comida prevista",
    "gimnasio": "Hoy tienes entrenamiento previsto",
    "compra": "Recuerda revisar la lista de la compra",
    "registro": "¿Quieres registrar cómo ha ido el día?",
}
TEXTO_GENERICO = "Tienes un recordatorio en Funes Fit"


def _codificar(datos: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def generar_claves_vapid() -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    privada = ec.generate_private_key(ec.SECP256R1())
    numero = privada.private_numbers().private_value.to_bytes(32, "big")
    publica = privada.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"publica": _codificar(publica), "privada": _codificar(numero)}


def claves_vapid(bd: Session) -> dict:
    if(configuracion.vapid_publica and configuracion.vapid_privada):
        return {"publica": configuracion.vapid_publica, "privada": configuracion.vapid_privada, "origen": "entorno"}
    publica = bd.get(AjusteServidor, "vapid_publica")
    privada = bd.get(AjusteServidor, "vapid_privada")
    if(publica is None or privada is None):
        nuevas = generar_claves_vapid()
        try:
            bd.add(AjusteServidor(clave="vapid_publica", valor=nuevas["publica"]))
            bd.add(AjusteServidor(clave="vapid_privada", valor=nuevas["privada"]))
            bd.commit()
        except IntegrityError:
            bd.rollback()
        publica = bd.get(AjusteServidor, "vapid_publica")
        privada = bd.get(AjusteServidor, "vapid_privada")
    return {"publica": publica.valor, "privada": privada.valor, "origen": "base_de_datos"}


def push_configurado() -> bool:
    return True


def enviar_webpush(suscripcion: SuscripcionPush, carga: dict, privada: str | None = None) -> str:
    from pywebpush import WebPushException, webpush
    try:
        webpush(
            subscription_info={"endpoint": suscripcion.endpoint, "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth}},
            data=json.dumps(carga),
            vapid_private_key=privada or configuracion.vapid_privada,
            vapid_claims={"sub": configuracion.vapid_contacto},
            ttl=3600,
        )
        return "ok"
    except WebPushException as error:
        codigo = getattr(getattr(error, "response", None), "status_code", None)
        if(codigo in (404, 410)):
            return "caducada"
        return f"error:{codigo}"
    except Exception as error:
        return f"error:{type(error).__name__}"


def enviar_a_usuario(bd: Session, usuario_id: int, carga: dict, enviar=None) -> dict:
    suscripciones = bd.query(SuscripcionPush).filter(SuscripcionPush.usuario_id == usuario_id).all()
    resultado = {"enviados": 0, "fallos": 0, "caducadas": 0, "suscripciones": len(suscripciones)}
    if(enviar is None and len(suscripciones) > 0):
        privada = claves_vapid(bd)["privada"]
        enviar = lambda suscripcion, datos: enviar_webpush(suscripcion, datos, privada)
    for(s) in suscripciones:
        estado = enviar(s, carga)
        if(estado == "ok"):
            s.ultimo_envio_ok = ahora_utc()
            s.fallos = 0
            resultado["enviados"] = resultado["enviados"] + 1
        elif(estado == "caducada"):
            bd.delete(s)
            resultado["caducadas"] = resultado["caducadas"] + 1
        else:
            s.fallos = (s.fallos or 0) + 1
            resultado["fallos"] = resultado["fallos"] + 1
    bd.commit()
    return resultado


def procesar_avisos(bd: Session, ahora: datetime | None = None, enviar=None) -> list[dict]:
    instante = ahora or datetime.now(timezone.utc)
    procesados = []
    for(recordatorio) in bd.query(Recordatorio).filter(Recordatorio.activo == True).all():
        perfil = bd.get(Perfil, recordatorio.usuario_id)
        zona = perfil.zona_horaria if perfil else "Europe/Madrid"
        local = ahora_local(zona, instante)
        if(local.weekday() not in (recordatorio.dias or [])):
            continue
        minutos = local.hour * 60 + local.minute
        diferencia = minutos - hora_a_minutos(recordatorio.hora)
        if(diferencia < 0 or diferencia > VENTANA_MINUTOS):
            continue
        fecha_local = local.date()
        if(bd.query(EnvioRecordatorio).filter(EnvioRecordatorio.recordatorio_id == recordatorio.id, EnvioRecordatorio.fecha_local == fecha_local).first() is not None):
            continue
        if(perfil is not None and en_franja_silencio(minutos, perfil.silencio_inicio, perfil.silencio_fin)):
            estado = "silencio"
            detalle = "Dentro de la franja de silencio"
        else:
            texto = TEXTO_GENERICO if recordatorio.texto_generico else TEXTOS.get(recordatorio.tipo, TEXTO_GENERICO)
            resultado = enviar_a_usuario(bd, recordatorio.usuario_id, {"titulo": "Funes Fit", "cuerpo": texto, "tipo": recordatorio.tipo, "usuario": recordatorio.usuario_id, "url": "/"}, enviar)
            estado = "enviado" if resultado["enviados"] > 0 else ("sin_suscripcion" if resultado["suscripciones"] == 0 else "error")
            detalle = json.dumps(resultado)
        bd.add(EnvioRecordatorio(recordatorio_id=recordatorio.id, fecha_local=fecha_local, resultado=estado, detalle=detalle))
        try:
            bd.commit()
        except IntegrityError:
            bd.rollback()
            continue
        procesados.append({"recordatorio_id": recordatorio.id, "usuario_id": recordatorio.usuario_id, "estado": estado})
    return procesados


async def bucle_avisos(fabrica) -> None:
    while(True):
        try:
            bd = fabrica()
            try:
                procesar_avisos(bd)
            finally:
                bd.close()
        except Exception as error:
            print(f"Error en el planificador de avisos: {error}")
        await asyncio.sleep(configuracion.intervalo_avisos_s)
