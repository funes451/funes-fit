import hashlib
import secrets
from datetime import timedelta

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import configuracion
from app.db import obtener_bd
from app.modelos import IntentoAcceso, SesionUsuario, Usuario, ahora_utc

NOMBRE_COOKIE = "ff_sesion"
MAX_FALLOS_EMAIL = 5
MAX_FALLOS_IP = 20
VENTANA_FALLOS_MIN = 15
LONGITUD_MINIMA_CONTRASENA = 10

_hasher = PasswordHasher()


def hash_contrasena(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar_contrasena(hash_guardado: str, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validar_contrasena_nueva(contrasena: str) -> None:
    if(len(contrasena or "") < LONGITUD_MINIMA_CONTRASENA):
        raise HTTPException(status_code=422, detail=f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres")


def ip_cliente(peticion: Request) -> str:
    if(configuracion.confiar_proxy):
        real = peticion.headers.get("x-real-ip") or (peticion.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if(real):
            return real[:64]
    if(peticion.client is None):
        return "desconocida"
    return peticion.client.host


def comprobar_limite(bd: Session, clave: str, ip: str) -> None:
    desde = ahora_utc() - timedelta(minutes=VENTANA_FALLOS_MIN)
    fallos_clave = bd.query(IntentoAcceso).filter(IntentoAcceso.clave == clave, IntentoAcceso.exito == False, IntentoAcceso.momento >= desde).count()
    fallos_ip = bd.query(IntentoAcceso).filter(IntentoAcceso.ip == ip, IntentoAcceso.exito == False, IntentoAcceso.momento >= desde).count()
    if(fallos_clave >= MAX_FALLOS_EMAIL or fallos_ip >= MAX_FALLOS_IP):
        raise HTTPException(status_code=429, detail=f"Demasiados intentos fallidos. Espera {VENTANA_FALLOS_MIN} minutos.")


def registrar_intento(bd: Session, clave: str, ip: str, exito: bool) -> None:
    bd.add(IntentoAcceso(clave=clave, ip=ip, exito=exito))
    bd.commit()


def crear_sesion(bd: Session, usuario: Usuario, pendiente_2fa: bool) -> str:
    token = secrets.token_urlsafe(32)
    sesion = SesionUsuario(
        usuario_id=usuario.id,
        token_hash=hash_token(token),
        expira_en=ahora_utc() + (timedelta(minutes=10) if pendiente_2fa else timedelta(days=configuracion.duracion_sesion_dias)),
        segundo_factor_pendiente=pendiente_2fa,
    )
    bd.add(sesion)
    bd.commit()
    return token


def sesion_desde_peticion(bd: Session, peticion: Request) -> SesionUsuario | None:
    token = peticion.cookies.get(NOMBRE_COOKIE)
    if(not token):
        return None
    sesion = bd.query(SesionUsuario).filter(SesionUsuario.token_hash == hash_token(token)).first()
    if(sesion is None):
        return None
    if(sesion.expira_en <= ahora_utc()):
        bd.delete(sesion)
        bd.commit()
        return None
    return sesion


def usuario_actual(peticion: Request, bd: Session = Depends(obtener_bd)) -> Usuario:
    sesion = sesion_desde_peticion(bd, peticion)
    if(sesion is None or sesion.segundo_factor_pendiente):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    usuario = bd.get(Usuario, sesion.usuario_id)
    if(usuario is None):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    return usuario


def fijar_cookie(respuesta, token: str, pendiente_2fa: bool) -> None:
    respuesta.set_cookie(
        NOMBRE_COOKIE,
        token,
        httponly=True,
        secure=configuracion.cookie_segura,
        samesite="lax",
        max_age=600 if pendiente_2fa else configuracion.duracion_sesion_dias * 86400,
        path="/",
    )


def nuevo_secreto_totp() -> str:
    return pyotp.random_base32()


def verificar_totp(secreto: str, codigo: str) -> bool:
    limpio = "".join(c for c in str(codigo or "") if c.isdigit())
    if(len(limpio) != 6):
        return False
    return pyotp.TOTP(secreto).verify(limpio, valid_window=1)


def generar_codigos_recuperacion(cantidad: int = 8) -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(cantidad)]


def usar_codigo_recuperacion(usuario: Usuario, codigo: str) -> bool:
    limpio = str(codigo or "").strip().lower()
    hashes = list(usuario.codigos_recuperacion or [])
    for(indice, guardado) in enumerate(hashes):
        if(verificar_contrasena(guardado, limpio)):
            hashes.pop(indice)
            usuario.codigos_recuperacion = hashes
            return True
    return False
