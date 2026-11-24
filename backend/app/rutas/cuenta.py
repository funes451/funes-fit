import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import seguridad
from app.config import configuracion
from app.db import obtener_bd
from app.modelos import Evento, Foto, Invitacion, Usuario, ahora_utc
from app.calculos.fechas import interpretar_fecha, interpretar_hora, lunes_de
from app.semilla import sembrar_usuario
from app.servicios import exportacion
from app.servicios.nucleo import perfil_de

enrutador = APIRouter(prefix="/api", tags=["cuenta"])

NOMBRES_PLAN = {"amigo": "Amigo de Funes", "funes": "Funes", "vacio": "Cuenta nueva"}


def crear_invitacion(bd: Session, plan: str, horas: int = 72) -> str:
    if(plan not in NOMBRES_PLAN):
        raise ValueError("Plan de invitación desconocido")
    token = secrets.token_urlsafe(32)
    bd.add(Invitacion(token_hash=seguridad.hash_token(token), plan=plan, nombre_provisional=NOMBRES_PLAN[plan], expira_en=ahora_utc() + timedelta(hours=horas)))
    bd.commit()
    return token


def _invitacion_valida(bd: Session, token: str) -> Invitacion:
    invitacion = bd.query(Invitacion).filter(Invitacion.token_hash == seguridad.hash_token(token or "")).first()
    if(invitacion is None or invitacion.revocada or invitacion.usada_en is not None or invitacion.expira_en <= ahora_utc()):
        raise HTTPException(status_code=410, detail="La invitación no es válida, ya se usó o ha caducado. Pide una nueva.")
    return invitacion


@enrutador.get("/invitaciones/{token}")
def ver_invitacion(token: str, peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    ip = seguridad.ip_cliente(peticion)
    seguridad.comprobar_limite(bd, "invitacion", ip)
    try:
        invitacion = _invitacion_valida(bd, token)
    except HTTPException:
        seguridad.registrar_intento(bd, "invitacion", ip, False)
        raise
    return {"nombre_provisional": invitacion.nombre_provisional, "expira_en": invitacion.expira_en.isoformat()}


@enrutador.post("/invitaciones/{token}/activar")
def activar_invitacion(token: str, cuerpo: dict, peticion: Request, respuesta: Response, bd: Session = Depends(obtener_bd)) -> dict:
    ip = seguridad.ip_cliente(peticion)
    seguridad.comprobar_limite(bd, "invitacion", ip)
    try:
        invitacion = _invitacion_valida(bd, token)
    except HTTPException:
        seguridad.registrar_intento(bd, "invitacion", ip, False)
        raise
    email = str(cuerpo.get("email") or "").strip().lower()
    if("@" not in email or len(email) < 5):
        raise HTTPException(status_code=422, detail="Introduce un correo válido")
    contrasena = str(cuerpo.get("contrasena") or "")
    seguridad.validar_contrasena_nueva(contrasena)
    if(bd.query(Usuario).filter(Usuario.email == email).first() is not None):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")
    usuario = Usuario(email=email, hash_contrasena=seguridad.hash_contrasena(contrasena), codigos_recuperacion=[])
    bd.add(usuario)
    bd.flush()
    invitacion.usada_en = ahora_utc()
    invitacion.usuario_creado_id = usuario.id
    bd.commit()
    sembrar_usuario(bd, usuario.id, invitacion.plan)
    sesion = seguridad.crear_sesion(bd, usuario, False)
    seguridad.fijar_cookie(respuesta, sesion, False)
    return {"usuario": {"id": usuario.id, "email": usuario.email, "totp_activo": False, "codigos_recuperacion_restantes": 0}}


@enrutador.get("/exportar/json")
def exportar_json(usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> Response:
    import json
    datos = exportacion.exportar(bd, usuario.id)
    return Response(json.dumps(datos, ensure_ascii=False, indent=1, default=str), media_type="application/json", headers={"Content-Disposition": "attachment; filename=funes-fit-exportacion.json", "Cache-Control": "private, no-store"})


@enrutador.get("/exportar/csv/{tabla}")
def exportar_csv(tabla: str, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> Response:
    try:
        texto = exportacion.exportar_csv(bd, usuario.id, tabla)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return Response("﻿" + texto, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=funes-fit-{tabla}.csv", "Cache-Control": "private, no-store"})


@enrutador.post("/importar/json")
def importar_json(cuerpo: dict, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        return exportacion.importar(bd, usuario.id, cuerpo)
    except ValueError as error:
        bd.rollback()
        raise HTTPException(status_code=422, detail=str(error))


@enrutador.post("/importar/csv/mediciones")
def importar_csv_mediciones(cuerpo: dict, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    return exportacion.importar_mediciones_csv(bd, usuario.id, str(cuerpo.get("csv") or ""), bool(cuerpo.get("confirmar")))


@enrutador.post("/cuenta/borrar")
def borrar_cuenta(cuerpo: dict, peticion: Request, respuesta: Response, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(not seguridad.verificar_contrasena(usuario.hash_contrasena, str(cuerpo.get("contrasena") or ""))):
        raise HTTPException(status_code=401, detail="La contraseña no es correcta")
    if(cuerpo.get("confirmacion") != "BORRAR"):
        raise HTTPException(status_code=422, detail="Escribe BORRAR para confirmar")
    for(foto) in bd.query(Foto).filter(Foto.usuario_id == usuario.id).all():
        ruta = configuracion.directorio_datos / "fotos" / foto.archivo
        if(foto.contenido is None and ruta.exists()):
            ruta.unlink()
    bd.delete(usuario)
    bd.commit()
    respuesta.delete_cookie(seguridad.NOMBRE_COOKIE, path="/")
    return {"ok": True}


@enrutador.put("/eventos/partido")
def fijar_partido(cuerpo: dict, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        fecha = interpretar_fecha(cuerpo.get("fecha"))
        hora = interpretar_hora(cuerpo["hora"]) if cuerpo.get("hora") else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if(fecha.weekday() < 5):
        raise HTTPException(status_code=422, detail="El partido se configura en sábado o domingo")
    clave = f"semana:{lunes_de(fecha).isoformat()}:partido"
    evento = bd.query(Evento).filter(Evento.usuario_id == usuario.id, Evento.clave_plan == clave, Evento.borrado == False).first()
    if(cuerpo.get("sin_partido")):
        if(evento is not None):
            evento.borrado = True
            bd.commit()
        return {"ok": True, "partido": None}
    if(evento is None):
        evento = Evento(usuario_id=usuario.id, clave_plan=clave, tipo="partido", titulo="Partido de fútbol sala", fecha=fecha, datos={}, version=1)
        bd.add(evento)
    evento.fecha = fecha
    evento.hora = hora
    bd.commit()
    return {"ok": True, "partido": {"id": evento.id, "fecha": evento.fecha.isoformat(), "hora": evento.hora}}
