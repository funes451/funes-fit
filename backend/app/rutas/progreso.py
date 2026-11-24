import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.calculos import progreso as calc_progreso
from app.calculos.fechas import hoy_local, interpretar_fecha, lunes_de
from app.config import configuracion
from app.db import obtener_bd
from app.modelos import CampoPersonalizado, ComidaPlanificada, Consumo, EntradaDiario, Foto, Medicion, SesionEntreno, Usuario
from app.seguridad import usuario_actual
from app.servicios.nucleo import objetivo_vigente, perfil_de, propio
from app.servicios.registros import CAMPOS_DIARIO, diario_a_dict, medicion_a_dict

enrutador = APIRouter(prefix="/api", tags=["progreso"])

TIPOS_FOTO = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}
MAX_FOTO_BYTES = 12 * 1024 * 1024
MAX_FOTO_BD_BYTES = 4 * 1024 * 1024


def adherencia_reciente(bd: Session, usuario_id: int, hoy: date) -> float | None:
    desde = hoy - timedelta(days=14)
    consumos = bd.query(Consumo).filter(Consumo.usuario_id == usuario_id, Consumo.fecha >= desde, Consumo.fecha < hoy, Consumo.borrado == False, Consumo.comida_planificada_id.isnot(None)).all()
    if(len(consumos) < 10):
        return None
    segun_plan = len([c for c in consumos if c.tipo in ("previsto", "modificado")])
    return segun_plan / len(consumos)


@enrutador.get("/mediciones")
def mediciones(tipo: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    consulta = bd.query(Medicion).filter(Medicion.usuario_id == usuario.id, Medicion.borrado == False)
    if(tipo):
        consulta = consulta.filter(Medicion.tipo == tipo)
    return {"mediciones": [medicion_a_dict(m) for m in consulta.order_by(Medicion.fecha.desc(), Medicion.id.desc()).all()]}


@enrutador.get("/progreso/peso")
def progreso_peso(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    filas = bd.query(Medicion).filter(Medicion.usuario_id == usuario.id, Medicion.tipo == "peso", Medicion.borrado == False).order_by(Medicion.fecha, Medicion.id).all()
    puntos = [{"fecha": m.fecha, "valor": m.valor} for m in filas]
    semanas = calc_progreso.medias_semanales(puntos)
    cambios = calc_progreso.cambios_semanales(semanas)
    hitos = perfil.hitos_kg or []
    ultima_media = next((s["media"] for s in reversed(semanas) if s["valida"]), None)
    referencia_inicio = filas[0].valor if filas else perfil.peso_referencia_kg
    progreso_hitos = []
    for(h) in hitos:
        estado = None
        if(ultima_media is not None and referencia_inicio is not None and h != referencia_inicio):
            avance = (ultima_media - referencia_inicio) / (h - referencia_inicio)
            estado = max(0.0, min(1.0, avance))
        progreso_hitos.append({"kg": h, "avance": estado})
    return {
        "modo": perfil.modo_objetivo,
        "puntos": [{"id": m.id, "fecha": m.fecha.isoformat(), "valor": m.valor, "condiciones": m.condiciones} for m in filas],
        "semanas": [{**s, "lunes": s["lunes"].isoformat()} for s in semanas],
        "cambios": [{**c, "desde": c["desde"].isoformat(), "hasta": c["hasta"].isoformat()} for c in cambios],
        "hitos": progreso_hitos,
        "referencia_plan_kg": perfil.peso_referencia_kg,
        "referencia_plan_origen": perfil.peso_referencia_origen,
        "nota": "Media semanal solo con al menos 3 pesajes comparables. No se rellenan días sin dato y un día aislado no se interpreta.",
    }


@enrutador.get("/progreso/resumen-semanal")
def resumen_semanal(fecha: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    lunes = lunes_de(interpretar_fecha(fecha) if fecha else hoy_local(perfil.zona_horaria))
    domingo = lunes + timedelta(days=6)
    pesos = [m.valor for m in bd.query(Medicion).filter(Medicion.usuario_id == usuario.id, Medicion.tipo == "peso", Medicion.borrado == False, Medicion.fecha >= lunes, Medicion.fecha <= domingo).all()]
    comidas = bd.query(ComidaPlanificada).filter(ComidaPlanificada.usuario_id == usuario.id, ComidaPlanificada.fecha >= lunes, ComidaPlanificada.fecha <= domingo).all()
    consumos = bd.query(Consumo).filter(Consumo.usuario_id == usuario.id, Consumo.fecha >= lunes, Consumo.fecha <= domingo, Consumo.borrado == False).all()
    registradas = {c.comida_planificada_id for c in consumos if c.comida_planificada_id}
    segun_plan = {c.comida_planificada_id for c in consumos if c.comida_planificada_id and c.tipo == "previsto"}
    sesiones = bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == usuario.id, SesionEntreno.fecha >= lunes, SesionEntreno.fecha <= domingo).all()
    diario = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario.id, EntradaDiario.fecha >= lunes, EntradaDiario.fecha <= domingo).all()

    def media(clave: str) -> dict:
        valores = [e.datos.get(clave) for e in diario if (e.datos or {}).get(clave) is not None]
        return {"media": sum(valores) / len(valores) if valores else None, "dias": len(valores)}

    return {
        "lunes": lunes.isoformat(),
        "peso": {"medidas": len(pesos), "media": sum(pesos) / len(pesos) if len(pesos) >= 3 else None},
        "comidas": {"planificadas": len(comidas), "registradas": len(registradas), "segun_plan": len(segun_plan), "sin_registro": len(comidas) - len(registradas)},
        "entrenos": {"realizados": len([s for s in sesiones if s.estado == "finalizada"]), "parciales": len([s for s in sesiones if s.estado == "parcial"])},
        "pasos": media("pasos"),
        "sueno_horas": media("sueno_horas"),
        "energia": media("energia"),
        "hambre": media("hambre"),
        "nota": "Resumen de lo registrado. Lo no registrado aparece como sin dato, no como cero.",
    }


@enrutador.get("/diario/{fecha}")
def diario(fecha: str, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        dia = interpretar_fecha(fecha)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    entrada = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario.id, EntradaDiario.fecha == dia).first()
    perfil = perfil_de(bd, usuario.id)
    return {
        "entrada": diario_a_dict(entrada, dia),
        "campos": [{"clave": k, "tipo": v[0], "minimo": v[1], "maximo": v[2]} for k, v in CAMPOS_DIARIO.items()],
        "personalizados": [{"clave": c.clave, "etiqueta": c.etiqueta, "tipo": c.tipo, "unidad": c.unidad, "minimo": c.minimo, "maximo": c.maximo} for c in bd.query(CampoPersonalizado).filter(CampoPersonalizado.usuario_id == usuario.id).all()],
        "agua_referencia": perfil.agua_referencia,
        "nota_agua": "Bebe según sed, calor y ejercicio. La app no impone una cantidad por tu peso.",
    }


@enrutador.post("/campos-personalizados")
def crear_campo(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    from app.calculos.nutricion import normalizar_texto
    etiqueta = str(cuerpo.get("etiqueta") or "").strip()[:120]
    tipo = cuerpo.get("tipo")
    if(etiqueta == "" or tipo not in ("numero", "entero", "escala", "texto", "si_no")):
        raise HTTPException(status_code=422, detail="Indica nombre y tipo del campo")
    clave = "p_" + "".join(c if c.isalnum() else "_" for c in normalizar_texto(etiqueta))[:50]
    if(clave in CAMPOS_DIARIO or bd.query(CampoPersonalizado).filter(CampoPersonalizado.usuario_id == usuario.id, CampoPersonalizado.clave == clave).first()):
        raise HTTPException(status_code=409, detail="Ya existe un campo con ese nombre")
    from app.calculos.numeros import interpretar_numero
    try:
        minimo = interpretar_numero(cuerpo.get("minimo"), "El mínimo", -100000, 100000, opcional=True)
        maximo = interpretar_numero(cuerpo.get("maximo"), "El máximo", -100000, 100000, opcional=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if(tipo == "escala"):
        minimo = 1 if minimo is None else minimo
        maximo = 5 if maximo is None else maximo
    if(tipo in ("numero", "entero") and (minimo is None or maximo is None)):
        raise HTTPException(status_code=422, detail="Indica límites razonables (mínimo y máximo)")
    if(minimo is not None and maximo is not None and minimo >= maximo):
        raise HTTPException(status_code=422, detail="El mínimo debe ser menor que el máximo")
    campo = CampoPersonalizado(usuario_id=usuario.id, clave=clave, etiqueta=etiqueta, tipo=tipo, unidad=str(cuerpo.get("unidad") or "")[:20] or None, minimo=minimo, maximo=maximo if tipo != "texto" else 500)
    bd.add(campo)
    bd.commit()
    return {"clave": clave}


@enrutador.post("/fotos")
async def subir_foto(fecha: str = Form(...), archivo: UploadFile = File(...), notas: str = Form(""), usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(archivo.content_type not in TIPOS_FOTO):
        raise HTTPException(status_code=415, detail="Formato de imagen no admitido")
    contenido = await archivo.read()
    limite = MAX_FOTO_BD_BYTES if configuracion.fotos_en_bd else MAX_FOTO_BYTES
    if(len(contenido) > limite):
        raise HTTPException(status_code=413, detail=f"La foto supera {limite // (1024 * 1024)} MB")
    nombre = f"{usuario.id}_{secrets.token_hex(16)}{TIPOS_FOTO[archivo.content_type]}"
    if(not configuracion.fotos_en_bd):
        (configuracion.directorio_datos / "fotos" / nombre).write_bytes(contenido)
    foto = Foto(usuario_id=usuario.id, fecha=interpretar_fecha(fecha), archivo=nombre, tipo_mime=archivo.content_type, contenido=contenido if configuracion.fotos_en_bd else None, notas=notas[:500] or None)
    bd.add(foto)
    bd.commit()
    return {"id": foto.id}


@enrutador.get("/fotos")
def fotos(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(Foto).filter(Foto.usuario_id == usuario.id).order_by(Foto.fecha.desc()).all()
    return {"fotos": [{"id": f.id, "fecha": f.fecha.isoformat(), "notas": f.notas} for f in filas], "nota": "Fotos privadas: solo se sirven con tu sesión. La app no estima grasa corporal a partir de fotos."}


@enrutador.get("/fotos/{foto_id}/archivo")
def archivo_foto(foto_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)):
    foto = propio(bd, Foto, foto_id, usuario.id, "Foto no encontrada")
    if(foto.contenido is not None):
        return Response(foto.contenido, media_type=foto.tipo_mime, headers={"Cache-Control": "private, no-store"})
    ruta = configuracion.directorio_datos / "fotos" / foto.archivo
    if(not ruta.exists()):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(ruta, media_type=foto.tipo_mime, headers={"Cache-Control": "private, no-store"})


@enrutador.delete("/fotos/{foto_id}")
def borrar_foto(foto_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    foto = propio(bd, Foto, foto_id, usuario.id, "Foto no encontrada")
    ruta = configuracion.directorio_datos / "fotos" / foto.archivo
    if(ruta.exists()):
        ruta.unlink()
    bd.delete(foto)
    bd.commit()
    return {"ok": True}
