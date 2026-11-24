from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import obtener_bd
from app.modelos import Conflicto, OperacionSync, Usuario
from app.seguridad import usuario_actual
from app.servicios import registros
from app.servicios.nucleo import propio

enrutador = APIRouter(prefix="/api/sync", tags=["sync"])

MAX_OPERACIONES = 200


@enrutador.post("")
def sincronizar(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    propietario = cuerpo.get("usuario_id")
    if(propietario is not None and int(propietario) != usuario.id):
        raise HTTPException(status_code=409, detail="Estas operaciones pertenecen a otra cuenta. No se han enviado.")
    operaciones = cuerpo.get("operaciones") or []
    if(len(operaciones) > MAX_OPERACIONES):
        raise HTTPException(status_code=413, detail=f"Envía como máximo {MAX_OPERACIONES} operaciones por lote")
    resultados = []
    for(op) in operaciones:
        id_operacion = str(op.get("id_operacion") or "").strip()[:64]
        tipo = str(op.get("tipo") or "")
        if(id_operacion == ""):
            resultados.append({"id_operacion": None, "estado": "error", "error": "Falta el identificador de operación"})
            continue
        previa = bd.query(OperacionSync).filter(OperacionSync.id_operacion == id_operacion).first()
        if(previa is not None):
            if(previa.usuario_id != usuario.id):
                resultados.append({"id_operacion": id_operacion, "estado": "error", "error": "Identificador de operación no válido"})
                continue
            if(previa.estado in ("aplicada", "conflicto")):
                resultados.append({"id_operacion": id_operacion, "estado": "duplicada", "estado_original": previa.estado, "resultado": previa.resultado})
                continue
        try:
            resultado = registros.ejecutar(bd, usuario.id, tipo, op.get("carga") or {})
            estado = "aplicada"
        except registros.ErrorConflicto as conflicto:
            bd.rollback()
            resultado = {"mensaje": conflicto.mensaje, "servidor": conflicto.servidor, "conflicto_id": conflicto.conflicto_id}
            estado = "conflicto"
        except IntegrityError:
            bd.rollback()
            resultados.append({"id_operacion": id_operacion, "estado": "duplicada", "resultado": {"aviso": "Ya se estaba guardando desde otra petición"}})
            continue
        except (ValueError, KeyError, TypeError) as error:
            bd.rollback()
            resultado = {"error": str(error) or "Datos no válidos"}
            estado = "error"
        if(previa is None):
            previa = OperacionSync(usuario_id=usuario.id, id_operacion=id_operacion, tipo=tipo[:60], estado=estado, resultado=resultado)
            bd.add(previa)
        else:
            previa.estado = estado
            previa.resultado = resultado
        try:
            bd.commit()
        except IntegrityError:
            bd.rollback()
        resultados.append({"id_operacion": id_operacion, "estado": estado, "resultado": resultado})
    return {"resultados": resultados}


@enrutador.get("/conflictos")
def conflictos(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(Conflicto).filter(Conflicto.usuario_id == usuario.id, Conflicto.resuelto == False).order_by(Conflicto.creado_en.desc()).all()
    return {"conflictos": [{"id": c.id, "entidad": c.entidad, "entidad_id": c.entidad_id, "cliente": c.carga_cliente, "servidor": c.carga_servidor, "creado_en": c.creado_en.isoformat()} for c in filas]}


@enrutador.post("/conflictos/{conflicto_id}/resolver")
def resolver(conflicto_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    conflicto = propio(bd, Conflicto, conflicto_id, usuario.id, "Conflicto no encontrado")
    eleccion = cuerpo.get("eleccion")
    if(eleccion not in ("cliente", "servidor")):
        raise HTTPException(status_code=422, detail="Elige qué versión conservar")
    resultado = None
    if(eleccion == "cliente"):
        tipos = {"diario": "diario.guardar", "sesion": "sesion.guardar", "evento": "evento.guardar"}
        carga = dict(conflicto.carga_cliente)
        carga["version_base"] = (conflicto.carga_servidor or {}).get("version")
        from app.modelos import EntradaDiario, Evento, SesionEntreno
        modelo = {"diario": EntradaDiario, "sesion": SesionEntreno, "evento": Evento}[conflicto.entidad]
        actual = bd.get(modelo, conflicto.entidad_id)
        if(actual is not None):
            carga["version_base"] = actual.version
        try:
            resultado = registros.ejecutar(bd, usuario.id, tipos[conflicto.entidad], carga)
        except registros.ErrorConflicto:
            raise HTTPException(status_code=409, detail="El dato volvió a cambiar. Recarga y elige de nuevo.")
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
    conflicto.resuelto = True
    bd.commit()
    return {"ok": True, "resultado": resultado}
