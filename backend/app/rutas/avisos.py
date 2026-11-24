import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import avisos as servicio_avisos
from app.calculos.fechas import hoy_local, interpretar_hora
from app.config import configuracion
from app.db import obtener_bd
from app.modelos import EnvioRecordatorio, Recordatorio, SuscripcionPush, Usuario
from app.seguridad import usuario_actual
from app.servicios.nucleo import perfil_de, propio

enrutador = APIRouter(prefix="/api/avisos", tags=["avisos"])

DIAS_ICS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def recordatorio_a_dict(r: Recordatorio) -> dict:
    return {"id": r.id, "tipo": r.tipo, "hora": r.hora, "dias": r.dias or [], "activo": r.activo, "texto_generico": r.texto_generico}


@enrutador.get("")
def estado(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    recordatorios = bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario.id).order_by(Recordatorio.id).all()
    ultimos = bd.query(EnvioRecordatorio).filter(EnvioRecordatorio.recordatorio_id.in_([r.id for r in recordatorios] or [0])).order_by(EnvioRecordatorio.enviado_en.desc()).limit(10).all()
    return {
        "push_configurado": True,
        "clave_publica": servicio_avisos.claves_vapid(bd)["publica"],
        "planificador_activo": configuracion.avisos_activos or bool(configuracion.clave_cron),
        "planificador": "servidor" if configuracion.avisos_activos else ("cron externo" if configuracion.clave_cron else "sin configurar"),
        "recordatorios": [recordatorio_a_dict(r) for r in recordatorios],
        "silencio": {"inicio": perfil.silencio_inicio, "fin": perfil.silencio_fin},
        "suscripciones": bd.query(SuscripcionPush).filter(SuscripcionPush.usuario_id == usuario.id).count(),
        "ultimos_envios": [{"recordatorio_id": e.recordatorio_id, "fecha": e.fecha_local.isoformat(), "resultado": e.resultado} for e in ultimos],
        "aviso": "Los avisos dependen de que el servidor esté encendido y de que el navegador los entregue. No se garantiza la hora exacta ni que se lean.",
    }


@enrutador.put("/recordatorios/{recordatorio_id}")
def editar(recordatorio_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    r = propio(bd, Recordatorio, recordatorio_id, usuario.id, "Recordatorio no encontrado")
    try:
        if("hora" in cuerpo):
            r.hora = interpretar_hora(cuerpo["hora"])
        if("dias" in cuerpo):
            dias = sorted({int(d) for d in cuerpo["dias"] or []})
            if(any(d < 0 or d > 6 for d in dias)):
                raise ValueError("Días no válidos")
            r.dias = dias
        if("activo" in cuerpo):
            r.activo = bool(cuerpo["activo"])
        if("texto_generico" in cuerpo):
            r.texto_generico = bool(cuerpo["texto_generico"])
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error))
    bd.commit()
    return {"recordatorio": recordatorio_a_dict(r)}


@enrutador.post("/suscripciones")
def suscribir(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    endpoint = str(cuerpo.get("endpoint") or "")
    claves = cuerpo.get("keys") or {}
    if(not endpoint.startswith("https://") or not claves.get("p256dh") or not claves.get("auth")):
        raise HTTPException(status_code=422, detail="Suscripción no válida")
    existente = bd.query(SuscripcionPush).filter(SuscripcionPush.endpoint == endpoint).first()
    if(existente is not None and existente.usuario_id != usuario.id):
        bd.delete(existente)
        bd.flush()
        existente = None
    if(existente is None):
        existente = SuscripcionPush(usuario_id=usuario.id, endpoint=endpoint, p256dh=claves["p256dh"], auth=claves["auth"])
        bd.add(existente)
    existente.p256dh = claves["p256dh"]
    existente.auth = claves["auth"]
    existente.dispositivo = str(cuerpo.get("dispositivo") or "")[:64] or None
    existente.agente = str(cuerpo.get("agente") or "")[:300] or None
    bd.commit()
    return {"ok": True}


@enrutador.post("/suscripciones/borrar")
def desuscribir(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    endpoint = str(cuerpo.get("endpoint") or "")
    borradas = bd.query(SuscripcionPush).filter(SuscripcionPush.usuario_id == usuario.id, SuscripcionPush.endpoint == endpoint).delete()
    bd.commit()
    return {"ok": True, "borradas": borradas}


@enrutador.post("/prueba")
def prueba(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    resultado = servicio_avisos.enviar_a_usuario(bd, usuario.id, {"titulo": "Funes Fit", "cuerpo": "Aviso de prueba", "tipo": "prueba", "usuario": usuario.id, "url": "/"})
    if(resultado["suscripciones"] == 0):
        raise HTTPException(status_code=409, detail="Este usuario no tiene ningún dispositivo suscrito")
    return resultado


@enrutador.get("/calendario.ics")
def calendario(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> Response:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Funes Fit//ES", "CALSCALE:GREGORIAN"]
    for(r) in bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario.id, Recordatorio.activo == True).all():
        if(not r.dias):
            continue
        hora = r.hora.replace(":", "")
        texto = servicio_avisos.TEXTO_GENERICO if r.texto_generico else servicio_avisos.TEXTOS.get(r.tipo, servicio_avisos.TEXTO_GENERICO)
        lineas = lineas + [
            "BEGIN:VEVENT",
            f"UID:funesfit-{usuario.id}-{r.id}@funesfit",
            f"DTSTAMP:{hoy.strftime('%Y%m%d')}T000000Z",
            f"DTSTART;TZID={perfil.zona_horaria}:{hoy.strftime('%Y%m%d')}T{hora}00",
            "DURATION:PT10M",
            f"RRULE:FREQ=WEEKLY;BYDAY={','.join(DIAS_ICS[d] for d in r.dias)}",
            f"SUMMARY:{texto}",
            "BEGIN:VALARM",
            "TRIGGER:PT0M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{texto}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lineas.append("END:VCALENDAR")
    return Response("\r\n".join(lineas) + "\r\n", media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": "attachment; filename=funes-fit-recordatorios.ics", "Cache-Control": "private, no-store"})


@enrutador.api_route("/procesar", methods=["GET", "POST"])
def procesar(peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    if(not configuracion.clave_cron):
        raise HTTPException(status_code=503, detail="Falta FUNES_CLAVE_CRON en el servidor")
    cabecera = peticion.headers.get("authorization", "")
    recibida = cabecera[7:] if cabecera.lower().startswith("bearer ") else peticion.query_params.get("clave", "")
    if(not hmac.compare_digest(recibida.encode(), configuracion.clave_cron.encode())):
        raise HTTPException(status_code=401, detail="Clave no válida")
    procesados = servicio_avisos.procesar_avisos(bd)
    return {"ok": True, "procesados": len(procesados)}
