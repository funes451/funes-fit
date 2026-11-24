import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import seguridad
from app.config import configuracion
from app.db import obtener_bd
from app.modelos import Consumo, Medicion, Perfil, PlanSemana, Receta, SesionEntreno, Usuario
from app.rutas.cuenta import crear_invitacion
from app.semilla import sembrar_usuario

enrutador = APIRouter(prefix="/api/admin", tags=["admin"])


def comprobar_clave(bd: Session, peticion: Request, cuerpo: dict) -> None:
    ip = seguridad.ip_cliente(peticion)
    seguridad.comprobar_limite(bd, "admin", ip)
    if(not configuracion.clave_admin):
        raise HTTPException(status_code=503, detail="La administración está desactivada: define FUNES_CLAVE_ADMIN en el servidor.")
    recibida = str(cuerpo.get("clave_admin") or "")
    if(not hmac.compare_digest(recibida.encode(), configuracion.clave_admin.encode())):
        seguridad.registrar_intento(bd, "admin", ip, False)
        raise HTTPException(status_code=401, detail="Clave de administración incorrecta")


@enrutador.post("/estado")
def estado(cuerpo: dict, peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    comprobar_clave(bd, peticion, cuerpo)
    cuentas = []
    for(u) in bd.query(Usuario).order_by(Usuario.id).all():
        perfil = bd.get(Perfil, u.id)
        cuentas.append({
            "id": u.id,
            "email": u.email,
            "perfil": perfil.nombre if perfil else None,
            "modo": perfil.modo_objetivo if perfil else None,
            "recetas": bd.query(Receta).filter(Receta.usuario_id == u.id).count(),
            "semanas": bd.query(PlanSemana).filter(PlanSemana.usuario_id == u.id).count(),
            "consumos": bd.query(Consumo).filter(Consumo.usuario_id == u.id).count(),
            "medidas": bd.query(Medicion).filter(Medicion.usuario_id == u.id).count(),
            "sesiones": bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == u.id).count(),
        })
    return {"cuentas": cuentas, "base_de_datos": "PostgreSQL" if configuracion.es_postgres else "SQLite", "avisos": "cron externo" if configuracion.clave_cron else ("servidor" if configuracion.avisos_activos else "sin configurar")}


@enrutador.post("/cuentas")
def crear_cuenta(cuerpo: dict, peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    comprobar_clave(bd, peticion, cuerpo)
    plan = cuerpo.get("plan")
    if(plan not in ("funes", "vacio")):
        raise HTTPException(status_code=422, detail="Plan no válido. La cuenta del amigo se crea con una invitación.")
    email = str(cuerpo.get("email") or "").strip().lower()
    if("@" not in email or len(email) < 5):
        raise HTTPException(status_code=422, detail="Introduce un correo válido")
    contrasena = str(cuerpo.get("contrasena") or "")
    seguridad.validar_contrasena_nueva(contrasena)
    if(bd.query(Usuario).filter(Usuario.email == email).first() is not None):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")
    if(plan == "funes" and bd.query(Perfil).filter(Perfil.nombre == "Funes").first() is not None and not cuerpo.get("forzar")):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con el plan de Funes. No se duplica.")
    usuario = Usuario(email=email, hash_contrasena=seguridad.hash_contrasena(contrasena), codigos_recuperacion=[])
    bd.add(usuario)
    bd.commit()
    creados = sembrar_usuario(bd, usuario.id, plan)
    return {"usuario_id": usuario.id, "email": email, "plan": plan, "creados": creados}


@enrutador.post("/invitaciones")
def invitar(cuerpo: dict, peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    comprobar_clave(bd, peticion, cuerpo)
    plan = cuerpo.get("plan") or "amigo"
    if(plan not in ("amigo", "vacio")):
        raise HTTPException(status_code=422, detail="Plan no válido")
    horas = int(cuerpo.get("horas") or 72)
    if(horas < 1 or horas > 336):
        raise HTTPException(status_code=422, detail="La caducidad debe estar entre 1 y 336 horas")
    token = crear_invitacion(bd, plan, horas)
    return {"ruta": f"/#/invitacion/{token}", "horas": horas, "aviso": "Enlace de un solo uso. No contiene datos personales y no se ha enviado a nadie."}


@enrutador.post("/recargar-plan")
def recargar_plan(cuerpo: dict, peticion: Request, bd: Session = Depends(obtener_bd)) -> dict:
    comprobar_clave(bd, peticion, cuerpo)
    usuario = bd.query(Usuario).filter(Usuario.email == str(cuerpo.get("email") or "").strip().lower()).first()
    if(usuario is None):
        raise HTTPException(status_code=404, detail="No existe esa cuenta")
    plan = cuerpo.get("plan")
    if(plan not in ("funes", "amigo")):
        raise HTTPException(status_code=422, detail="Plan no válido")
    return {"creados": sembrar_usuario(bd, usuario.id, plan), "aviso": "Lo que ya existía no se ha duplicado ni modificado."}
