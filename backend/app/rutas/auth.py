import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import configuracion
from app.db import obtener_bd
from app.modelos import SesionUsuario, Usuario
from app.semilla import sembrar_usuario
from app import seguridad

enrutador = APIRouter(prefix="/api/auth", tags=["auth"])


def _email(valor) -> str:
    texto = str(valor or "").strip().lower()
    if("@" not in texto or len(texto) < 5 or len(texto) > 255):
        raise HTTPException(status_code=422, detail="Introduce un correo válido")
    return texto


def _usuario_publico(usuario: Usuario) -> dict:
    return {"id": usuario.id, "email": usuario.email, "totp_activo": usuario.totp_activo, "codigos_recuperacion_restantes": len(usuario.codigos_recuperacion or [])}


@enrutador.get("/estado")
def estado(bd: Session = Depends(obtener_bd)) -> dict:
    return {"registro_abierto": configuracion.permitir_registro, "hay_usuarios": bd.query(Usuario).count() > 0}


@enrutador.post("/registro")
def registro(cuerpo: dict, peticion: Request, respuesta: Response, bd: Session = Depends(obtener_bd)) -> dict:
    if(not configuracion.permitir_registro):
        raise HTTPException(status_code=403, detail="El registro libre está cerrado. Las cuentas se crean con el comando de alta o con una invitación de un solo uso.")
    email = _email(cuerpo.get("email"))
    contrasena = str(cuerpo.get("contrasena") or "")
    seguridad.validar_contrasena_nueva(contrasena)
    if(bd.query(Usuario).filter(Usuario.email == email).first() is not None):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")
    usuario = Usuario(email=email, hash_contrasena=seguridad.hash_contrasena(contrasena), codigos_recuperacion=[])
    bd.add(usuario)
    bd.commit()
    sembrar_usuario(bd, usuario.id, "vacio")
    token = seguridad.crear_sesion(bd, usuario, False)
    seguridad.fijar_cookie(respuesta, token, False)
    return {"usuario": _usuario_publico(usuario)}


@enrutador.post("/acceso")
def acceso(cuerpo: dict, peticion: Request, respuesta: Response, bd: Session = Depends(obtener_bd)) -> dict:
    email = str(cuerpo.get("email") or "").strip().lower()
    contrasena = str(cuerpo.get("contrasena") or "")
    ip = seguridad.ip_cliente(peticion)
    seguridad.comprobar_limite(bd, email, ip)
    usuario = bd.query(Usuario).filter(Usuario.email == email).first()
    if(usuario is None or not seguridad.verificar_contrasena(usuario.hash_contrasena, contrasena)):
        seguridad.registrar_intento(bd, email, ip, False)
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    seguridad.registrar_intento(bd, email, ip, True)
    pendiente = bool(usuario.totp_activo)
    token = seguridad.crear_sesion(bd, usuario, pendiente)
    seguridad.fijar_cookie(respuesta, token, pendiente)
    if(pendiente):
        return {"requiere_totp": True}
    return {"requiere_totp": False, "usuario": _usuario_publico(usuario)}


@enrutador.post("/segundo-factor")
def segundo_factor(cuerpo: dict, peticion: Request, respuesta: Response, bd: Session = Depends(obtener_bd)) -> dict:
    sesion = seguridad.sesion_desde_peticion(bd, peticion)
    if(sesion is None or not sesion.segundo_factor_pendiente):
        raise HTTPException(status_code=401, detail="Vuelve a introducir correo y contraseña")
    usuario = bd.get(Usuario, sesion.usuario_id)
    clave = f"totp:{usuario.email}"
    ip = seguridad.ip_cliente(peticion)
    seguridad.comprobar_limite(bd, clave, ip)
    valido = False
    if(cuerpo.get("codigo")):
        valido = seguridad.verificar_totp(usuario.totp_secreto, cuerpo.get("codigo"))
    elif(cuerpo.get("recuperacion")):
        valido = seguridad.usar_codigo_recuperacion(usuario, cuerpo.get("recuperacion"))
    if(not valido):
        seguridad.registrar_intento(bd, clave, ip, False)
        raise HTTPException(status_code=401, detail="Código incorrecto")
    seguridad.registrar_intento(bd, clave, ip, True)
    bd.delete(sesion)
    bd.commit()
    token = seguridad.crear_sesion(bd, usuario, False)
    seguridad.fijar_cookie(respuesta, token, False)
    return {"usuario": _usuario_publico(usuario)}


@enrutador.post("/salir")
def salir(peticion: Request, respuesta: Response, bd: Session = Depends(obtener_bd)) -> dict:
    sesion = seguridad.sesion_desde_peticion(bd, peticion)
    if(sesion is not None):
        bd.delete(sesion)
        bd.commit()
    respuesta.delete_cookie(seguridad.NOMBRE_COOKIE, path="/")
    return {"ok": True}


@enrutador.get("/yo")
def yo(usuario: Usuario = Depends(seguridad.usuario_actual)) -> dict:
    return {"usuario": _usuario_publico(usuario)}


@enrutador.post("/contrasena")
def cambiar_contrasena(cuerpo: dict, peticion: Request, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(not seguridad.verificar_contrasena(usuario.hash_contrasena, str(cuerpo.get("actual") or ""))):
        raise HTTPException(status_code=401, detail="La contraseña actual no es correcta")
    nueva = str(cuerpo.get("nueva") or "")
    seguridad.validar_contrasena_nueva(nueva)
    usuario.hash_contrasena = seguridad.hash_contrasena(nueva)
    token_actual = seguridad.hash_token(peticion.cookies.get(seguridad.NOMBRE_COOKIE, ""))
    bd.query(SesionUsuario).filter(SesionUsuario.usuario_id == usuario.id, SesionUsuario.token_hash != token_actual).delete()
    bd.commit()
    return {"ok": True}


@enrutador.post("/totp/configurar")
def configurar_totp(usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(usuario.totp_activo):
        raise HTTPException(status_code=409, detail="El segundo factor ya está activo")
    secreto = seguridad.nuevo_secreto_totp()
    usuario.totp_secreto = secreto
    bd.commit()
    return {"secreto": secreto, "uri": pyotp.TOTP(secreto).provisioning_uri(name=usuario.email, issuer_name="Funes Fit")}


@enrutador.post("/totp/activar")
def activar_totp(cuerpo: dict, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(not usuario.totp_secreto):
        raise HTTPException(status_code=409, detail="Primero genera el código QR")
    if(not seguridad.verificar_totp(usuario.totp_secreto, cuerpo.get("codigo"))):
        raise HTTPException(status_code=401, detail="Código incorrecto")
    codigos = seguridad.generar_codigos_recuperacion()
    usuario.codigos_recuperacion = [seguridad.hash_contrasena(c) for c in codigos]
    usuario.totp_activo = True
    bd.commit()
    return {"codigos_recuperacion": codigos, "aviso": "Guarda estos códigos en un lugar seguro. Solo se muestran ahora y cada uno sirve una vez."}


@enrutador.post("/totp/desactivar")
def desactivar_totp(cuerpo: dict, usuario: Usuario = Depends(seguridad.usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    if(not seguridad.verificar_contrasena(usuario.hash_contrasena, str(cuerpo.get("contrasena") or ""))):
        raise HTTPException(status_code=401, detail="La contraseña no es correcta")
    if(usuario.totp_activo and not seguridad.verificar_totp(usuario.totp_secreto, cuerpo.get("codigo"))):
        raise HTTPException(status_code=401, detail="Código incorrecto")
    usuario.totp_activo = False
    usuario.totp_secreto = None
    usuario.codigos_recuperacion = []
    bd.commit()
    return {"ok": True}
