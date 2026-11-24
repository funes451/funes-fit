from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import entrenamiento as calc_entreno
from app.calculos.fechas import hoy_local, interpretar_fecha, interpretar_hora, lunes_de
from app.calculos.numeros import interpretar_entero
from app.db import obtener_bd
from app.modelos import EntradaDiario, Ejercicio, EjercicioRutina, Evento, Rutina, SesionEntreno, Usuario
from app.seguridad import usuario_actual
from app.servicios.nucleo import perfil_de, propio
from app.servicios.registros import sesion_a_dict

enrutador = APIRouter(prefix="/api/gym", tags=["gym"])

TITULOS_TIPO = {"gimnasio": "Gimnasio", "futbol": "Fútbol sala", "partido": "Partido", "recuperacion": "Recuperación suave", "cardio": "Cardio", "descanso": "Descanso", "otro": "Actividad"}


def rutina_activa(bd: Session, usuario_id: int) -> Rutina | None:
    return bd.query(Rutina).filter(Rutina.usuario_id == usuario_id, Rutina.activa == True).order_by(Rutina.version.desc()).first()


def ejercicios_rutina(bd: Session, rutina: Rutina) -> dict:
    sesiones = {}
    filas = bd.query(EjercicioRutina).filter(EjercicioRutina.rutina_id == rutina.id).order_by(EjercicioRutina.sesion, EjercicioRutina.orden).all()
    for(f) in filas:
        ejercicio = bd.get(Ejercicio, f.ejercicio_id)
        sesiones.setdefault(f.sesion, []).append({
            "id": f.id,
            "ejercicio_id": ejercicio.id,
            "nombre": ejercicio.nombre,
            "grupo": ejercicio.grupo,
            "instrucciones": ejercicio.instrucciones,
            "alternativas": ejercicio.alternativas or [],
            "incremento_kg": ejercicio.incremento_kg,
            "principal": ejercicio.principal,
            "series": f.series,
            "rep_min": f.rep_min,
            "rep_max": f.rep_max,
            "tiempo": f.tiempo,
            "por_lado": f.por_lado,
            "nota": f.nota,
        })
    return sesiones


def nombres_sesion(rutina: Rutina) -> dict:
    nombres = dict(calc_entreno.NOMBRES_SESION)
    nombres.update((rutina.configuracion or {}).get("nombres_sesion") or {})
    return nombres


def historial_ejercicio(bd: Session, usuario_id: int, ejercicio_id: int, antes_de: date | None = None, limite: int = 5) -> list[dict]:
    consulta = bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == usuario_id, SesionEntreno.estado.in_(("finalizada", "parcial")))
    if(antes_de is not None):
        consulta = consulta.filter(SesionEntreno.fecha <= antes_de)
    resultado = []
    for(s) in consulta.order_by(SesionEntreno.fecha.desc(), SesionEntreno.id.desc()).limit(60).all():
        for(e) in s.ejercicios or []:
            if(e.get("ejercicio_id") == ejercicio_id and not e.get("sustituye_a")):
                resultado.append({"fecha": s.fecha.isoformat(), "series": e.get("series") or [], "tecnica_ok": e.get("tecnica_ok", True), "series_objetivo": e.get("series_objetivo")})
                break
        if(len(resultado) >= limite):
            break
    return resultado


def fatiga_registrada(bd: Session, usuario_id: int, fecha: date) -> bool:
    entradas = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario_id, EntradaDiario.fecha.in_((fecha, fecha - timedelta(days=1)))).all()
    for(e) in entradas:
        datos = e.datos or {}
        if((datos.get("energia") is not None and datos["energia"] <= 2) or datos.get("fatiga_elevada")):
            return True
    return False


def actividades_planificadas(bd: Session, usuario_id: int, rutina: Rutina, fecha: date) -> list[dict]:
    distribucion = calc_entreno.normalizar_distribucion(rutina.distribucion or {})
    nombres = nombres_sesion(rutina)
    lunes = lunes_de(fecha)
    eventos = bd.query(Evento).filter(Evento.usuario_id == usuario_id, Evento.borrado == False, Evento.fecha >= lunes - timedelta(days=7), Evento.fecha <= lunes + timedelta(days=14)).all()
    por_clave = {e.clave_plan: e for e in eventos if e.clave_plan}
    resultado = []
    for(origen) in (fecha - timedelta(days=d) for d in range(-7, 8)):
        for(indice, item) in enumerate(distribucion.get(origen.weekday(), [])):
            clave = f"{origen.isoformat()}:{item['tipo']}:{item.get('sesion') or indice}"
            evento = por_clave.get(clave)
            fecha_real = evento.fecha if evento is not None else origen
            if(fecha_real != fecha):
                continue
            resultado.append({
                "clave_plan": clave,
                "tipo": item["tipo"],
                "sesion": item.get("sesion"),
                "titulo": item.get("titulo") or (nombres.get(item.get("sesion"), item.get("sesion")) if item["tipo"] == "gimnasio" else TITULOS_TIPO[item["tipo"]]),
                "hora": (evento.hora if evento is not None and evento.hora else item.get("hora")),
                "opcional": bool(item.get("opcional")),
                "reprogramada": evento is not None and evento.fecha != origen,
                "estado": evento.estado if evento is not None else "planificado",
                "datos": (evento.datos if evento is not None else {}) or {},
                "evento_id": evento.id if evento is not None else None,
                "version": evento.version if evento is not None else 0,
            })
    for(e) in eventos:
        if(e.fecha == fecha and (e.clave_plan is None or e.clave_plan.startswith("semana:"))):
            resultado.append({"clave_plan": e.clave_plan, "tipo": e.tipo, "sesion": None, "titulo": e.titulo, "hora": e.hora, "opcional": False, "reprogramada": False, "estado": e.estado, "datos": e.datos or {}, "evento_id": e.id, "version": e.version})
    resultado.sort(key=lambda a: (a["hora"] or "99:99", a["tipo"]))
    return resultado


def detalle_sesion(bd: Session, usuario_id: int, rutina: Rutina, sesion: str, fecha: date) -> dict:
    perfil = perfil_de(bd, usuario_id)
    inicio = rutina.vigente_desde if (rutina.configuracion or {}).get("inicio_desde_rutina") else (perfil.inicio_plan or rutina.vigente_desde)
    semana = calc_entreno.semana_programa(inicio, fecha)
    distribucion = calc_entreno.normalizar_distribucion(rutina.distribucion or {})
    cinco = calc_entreno.cinco_seguidos(distribucion)
    fatiga = fatiga_registrada(bd, usuario_id, fecha)
    adaptacion = (rutina.configuracion or {}).get("adaptacion")
    ejercicios = []
    for(e) in ejercicios_rutina(bd, rutina).get(sesion, []):
        objetivo = calc_entreno.series_objetivo(e["series"], semana, perfil.continuidad_entrenamiento, fatiga, cinco, e["principal"], adaptacion)
        historial = historial_ejercicio(bd, usuario_id, e["ejercicio_id"], fecha)
        sugerencia = calc_entreno.sugerencia_progresion(historial, e["rep_min"], e["rep_max"], e["incremento_kg"]) if e["rep_min"] and e["rep_max"] else {"accion": "sin_datos", "mensaje": "Ejercicio por tiempo: progresa según tolerancia."}
        ejercicios.append({**e, "objetivo": objetivo, "ultima": historial[0] if historial else None, "sugerencia": sugerencia})
    configuracion = rutina.configuracion or {}
    opciones_fatiga = None
    if(fatiga and sesion in (configuracion.get("sesiones_reducibles") or [])):
        opciones_fatiga = {"mensaje": "Has registrado fatiga elevada. Puedes reducir esta sesión ligera u omitirla, como prevé tu plan. No hace falta recuperarla otro día.", "opciones": ["reducir", "omitir", "hacer_normal"]}
    return {
        "sesion": sesion,
        "titulo": nombres_sesion(rutina).get(sesion, sesion),
        "semana_programa": semana,
        "semanas_total": configuracion.get("semanas_programa", calc_entreno.SEMANAS_PROGRAMA),
        "fatiga": fatiga,
        "opciones_fatiga": opciones_fatiga,
        "ejercicios": ejercicios,
        "tiempo": calc_entreno.tiempo_estimado_min([{"series": x["objetivo"]["series"], "principal": x["principal"]} for x in ejercicios]),
        "calentamiento": configuracion.get("calentamiento") or "Calienta 5–8 minutos y haz series progresivas del primer ejercicio. Descansa 2–3 min en los principales y 60–90 s en accesorios.",
        "advertencia": configuracion.get("advertencia") or "Si aparece dolor agudo, para ese ejercicio. Un dolor que persiste necesita valoración profesional. El dolor no indica que el entrenamiento sea más eficaz.",
    }


@enrutador.get("/rutina")
def rutina(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        return {"rutina": None}
    distribucion = calc_entreno.normalizar_distribucion(activa.distribucion or {})
    return {
        "rutina": {
            "id": activa.id,
            "nombre": activa.nombre,
            "version": activa.version,
            "vigente_desde": activa.vigente_desde.isoformat(),
            "distribucion": {str(k): v for k, v in distribucion.items()},
            "sesiones": ejercicios_rutina(bd, activa),
            "nombres_sesion": nombres_sesion(activa),
            "configuracion": activa.configuracion or {},
            "avisos": calc_entreno.validar_distribucion(distribucion),
        }
    }


@enrutador.get("/dia")
def dia(fecha: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    objetivo_fecha = interpretar_fecha(fecha) if fecha else hoy
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        return {"fecha": objetivo_fecha.isoformat(), "hoy": hoy.isoformat(), "actividades": [], "sin_rutina": True}
    actividades = actividades_planificadas(bd, usuario.id, activa, objetivo_fecha)
    sesiones = bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == usuario.id, SesionEntreno.fecha == objetivo_fecha).all()
    for(a) in actividades:
        if(a["tipo"] == "gimnasio" and a["sesion"]):
            a["detalle"] = detalle_sesion(bd, usuario.id, activa, a["sesion"], objetivo_fecha)
            registrada = next((s for s in sesiones if s.sesion_codigo == a["sesion"]), None)
            a["sesion_registrada"] = sesion_a_dict(registrada) if registrada else None
    return {
        "fecha": objetivo_fecha.isoformat(),
        "hoy": hoy.isoformat(),
        "actividades": actividades,
        "descanso": len([a for a in actividades if a["tipo"] in ("gimnasio", "futbol", "partido")]) == 0,
        "texto_descanso": (activa.configuracion or {}).get("texto_descanso") or "Día de descanso. Paseo opcional si te apetece.",
        "sesiones_sueltas": [sesion_a_dict(s) for s in sesiones if s.sesion_codigo not in {a["sesion"] for a in actividades}],
    }


@enrutador.get("/semana")
def semana(fecha: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    lunes = lunes_de(interpretar_fecha(fecha) if fecha else hoy)
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        return {"dias": [], "lunes": lunes.isoformat()}
    dias = []
    sesiones = bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == usuario.id, SesionEntreno.fecha >= lunes, SesionEntreno.fecha < lunes + timedelta(days=7)).all()
    for(i) in range(7):
        f = lunes + timedelta(days=i)
        actividades = actividades_planificadas(bd, usuario.id, activa, f)
        for(a) in actividades:
            if(a["tipo"] == "gimnasio"):
                registrada = next((s for s in sesiones if s.fecha == f and s.sesion_codigo == a["sesion"]), None)
                a["estado"] = registrada.estado if registrada else "planificado"
        dias.append({"fecha": f.isoformat(), "actividades": actividades})
    return {"lunes": lunes.isoformat(), "hoy": hoy.isoformat(), "dias": dias}


@enrutador.get("/plan-semanas")
def plan_semanas(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        return {"semanas": []}
    configuracion = activa.configuracion or {}
    total = configuracion.get("semanas_programa", calc_entreno.SEMANAS_PROGRAMA)
    cinco = calc_entreno.cinco_seguidos(calc_entreno.normalizar_distribucion(activa.distribucion or {}))
    sesiones = ejercicios_rutina(bd, activa)
    semanas = []
    for(n) in range(1, total + 1):
        ejemplo = None
        for(lista) in sesiones.values():
            if(lista):
                ejemplo = calc_entreno.series_objetivo(lista[0]["series"], n, perfil.continuidad_entrenamiento, False, cinco, lista[0]["principal"], configuracion.get("adaptacion"))
                break
        semanas.append({"semana": n, "fase": ejemplo["fase"] if ejemplo else None, "nota": ejemplo["nota"] if ejemplo else None, "rir_objetivo": ejemplo["rir_objetivo"] if ejemplo else None})
    return {"semanas": semanas, "nota": "La carga sube solo cuando tus registros lo indican y aceptas la sugerencia; no hay subidas automáticas cada semana."}


@enrutador.put("/distribucion")
def cambiar_distribucion(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        raise HTTPException(status_code=404, detail="No hay rutina activa")
    try:
        if(cuerpo.get("modo")):
            distribucion = calc_entreno.distribucion(cuerpo["modo"])
        else:
            distribucion = calc_entreno.normalizar_distribucion(cuerpo.get("dias") or {})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    avisos = calc_entreno.validar_distribucion(distribucion)
    nueva = _nueva_version(bd, activa)
    nueva.distribucion = {str(k): v for k, v in distribucion.items()}
    bd.commit()
    return {"ok": True, "avisos": avisos, "version": nueva.version}


def _nueva_version(bd: Session, activa: Rutina) -> Rutina:
    perfil = perfil_de(bd, activa.usuario_id)
    nueva = Rutina(
        usuario_id=activa.usuario_id, nombre=activa.nombre, version=activa.version + 1, vigente_desde=hoy_local(perfil.zona_horaria),
        activa=True, distribucion=dict(activa.distribucion or {}), configuracion=dict(activa.configuracion or {}), plantilla=activa.plantilla,
    )
    bd.add(nueva)
    bd.flush()
    for(f) in bd.query(EjercicioRutina).filter(EjercicioRutina.rutina_id == activa.id).all():
        bd.add(EjercicioRutina(rutina_id=nueva.id, sesion=f.sesion, ejercicio_id=f.ejercicio_id, orden=f.orden, series=f.series, rep_min=f.rep_min, rep_max=f.rep_max, tiempo=f.tiempo, por_lado=f.por_lado, nota=f.nota))
    activa.activa = False
    bd.flush()
    return nueva


@enrutador.put("/rutina/sesiones/{sesion}")
def editar_sesion_rutina(sesion: str, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    activa = rutina_activa(bd, usuario.id)
    if(activa is None):
        raise HTTPException(status_code=404, detail="No hay rutina activa")
    nueva = _nueva_version(bd, activa)
    bd.query(EjercicioRutina).filter(EjercicioRutina.rutina_id == nueva.id, EjercicioRutina.sesion == sesion).delete()
    try:
        for(orden, item) in enumerate(cuerpo.get("ejercicios") or []):
            ejercicio = propio(bd, Ejercicio, int(item["ejercicio_id"]), usuario.id, "Ejercicio no encontrado")
            bd.add(EjercicioRutina(
                rutina_id=nueva.id, sesion=sesion, ejercicio_id=ejercicio.id, orden=orden,
                series=interpretar_entero(item.get("series"), "Las series", 1, 10),
                rep_min=interpretar_entero(item.get("rep_min"), "Las repeticiones mínimas", 1, 100, opcional=True),
                rep_max=interpretar_entero(item.get("rep_max"), "Las repeticiones máximas", 1, 100, opcional=True),
                tiempo=str(item.get("tiempo") or "")[:60] or None, por_lado=bool(item.get("por_lado")), nota=str(item.get("nota") or "")[:300] or None,
            ))
    except ValueError as error:
        bd.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    bd.commit()
    return {"ok": True, "version": nueva.version}


@enrutador.get("/ejercicios")
def ejercicios(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(Ejercicio).filter(Ejercicio.usuario_id == usuario.id).order_by(Ejercicio.nombre).all()
    return {"ejercicios": [{"id": e.id, "nombre": e.nombre, "grupo": e.grupo, "instrucciones": e.instrucciones, "alternativas": e.alternativas or [], "incremento_kg": e.incremento_kg, "principal": e.principal} for e in filas]}


@enrutador.post("/ejercicios")
def crear_ejercicio(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    nombre = str(cuerpo.get("nombre") or "").strip()[:160]
    if(nombre == ""):
        raise HTTPException(status_code=422, detail="Falta el nombre")
    ejercicio = Ejercicio(usuario_id=usuario.id, nombre=nombre, grupo=str(cuerpo.get("grupo") or "")[:60] or None, instrucciones=str(cuerpo.get("instrucciones") or "")[:1000] or None, alternativas=[], incremento_kg=2.5)
    bd.add(ejercicio)
    bd.commit()
    return {"id": ejercicio.id}


@enrutador.get("/sesiones")
def sesiones(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == usuario.id).order_by(SesionEntreno.fecha.desc(), SesionEntreno.id.desc()).limit(100).all()
    return {"sesiones": [sesion_a_dict(s) for s in filas]}


@enrutador.get("/sesiones/{sesion_id}")
def sesion(sesion_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    return {"sesion": sesion_a_dict(propio(bd, SesionEntreno, sesion_id, usuario.id, "Sesión no encontrada"))}


@enrutador.get("/progreso/{ejercicio_id}")
def progreso_ejercicio(ejercicio_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    ejercicio = propio(bd, Ejercicio, ejercicio_id, usuario.id, "Ejercicio no encontrado")
    puntos = []
    for(h) in reversed(historial_ejercicio(bd, usuario.id, ejercicio.id, None, 60)):
        hechas = [s for s in h["series"] if s.get("completada") and s.get("peso_kg") is not None]
        if(len(hechas) == 0):
            continue
        mejor = max(hechas, key=lambda s: (s["peso_kg"], s.get("repeticiones") or 0))
        puntos.append({"fecha": h["fecha"], "peso_kg": mejor["peso_kg"], "repeticiones": mejor.get("repeticiones"), "series": len(hechas)})
    return {"ejercicio": ejercicio.nombre, "puntos": puntos}


@enrutador.put("/plan/{clave_plan:path}")
def reprogramar(clave_plan: str, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    activa = rutina_activa(bd, usuario.id)
    partes = clave_plan.split(":")
    if(activa is None or len(partes) != 3):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    try:
        origen = interpretar_fecha(partes[0])
        nueva_fecha = interpretar_fecha(cuerpo.get("fecha")) if cuerpo.get("fecha") else origen
        hora = interpretar_hora(cuerpo["hora"]) if cuerpo.get("hora") else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if(abs((nueva_fecha - origen).days) > 6):
        raise HTTPException(status_code=422, detail="Solo puedes mover la actividad dentro de unos días")
    existente = [a for a in actividades_planificadas(bd, usuario.id, activa, origen) if a["clave_plan"] == clave_plan]
    if(len(existente) == 0):
        existente = [a for a in actividades_planificadas(bd, usuario.id, activa, nueva_fecha) if a["clave_plan"] == clave_plan]
    if(len(existente) == 0):
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    evento = bd.query(Evento).filter(Evento.usuario_id == usuario.id, Evento.clave_plan == clave_plan, Evento.borrado == False).first()
    if(evento is None):
        evento = Evento(usuario_id=usuario.id, clave_plan=clave_plan, tipo=existente[0]["tipo"], titulo=existente[0]["titulo"], fecha=nueva_fecha, datos={})
        bd.add(evento)
    evento.fecha = nueva_fecha
    evento.hora = hora or evento.hora
    if(cuerpo.get("omitir")):
        evento.estado = "omitido"
    evento.version = (evento.version or 0) + 1
    bd.commit()
    return {"ok": True, "evento_id": evento.id}
