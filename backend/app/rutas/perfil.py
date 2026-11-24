from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import energia as calc_energia
from app.calculos import progreso as calc_progreso
from app.calculos.fechas import hoy_local, interpretar_fecha, interpretar_hora
from app.calculos.numeros import interpretar_entero, interpretar_numero
from app.db import obtener_bd
from app.modelos import Medicion, Objetivo, Perfil, Usuario
from app.seguridad import usuario_actual
from app.servicios.nucleo import objetivo_a_dict, objetivo_vigente, perfil_de, plan_de_fecha, semana_plan

enrutador = APIRouter(prefix="/api", tags=["perfil"])

SEXOS = ("masculino", "femenino")
CONTINUIDADES = ("continuo", "menos_de_1_mes", "1_a_3_meses", "mas_de_3_meses", "mas_de_6_meses")


def edad_actual(perfil: Perfil, hoy: date) -> int | None:
    if(perfil.fecha_nacimiento is not None):
        anios = hoy.year - perfil.fecha_nacimiento.year
        if((hoy.month, hoy.day) < (perfil.fecha_nacimiento.month, perfil.fecha_nacimiento.day)):
            anios = anios - 1
        return anios
    if(perfil.edad_referencia is None):
        return None
    if(perfil.fecha_referencia_edad is None):
        return perfil.edad_referencia
    return perfil.edad_referencia + max(0, int((hoy - perfil.fecha_referencia_edad).days // 365.25))


def peso_actual(bd: Session, usuario_id: int, perfil: Perfil) -> dict:
    ultimo = bd.query(Medicion).filter(Medicion.usuario_id == usuario_id, Medicion.tipo == "peso", Medicion.borrado == False).order_by(Medicion.fecha.desc(), Medicion.id.desc()).first()
    if(ultimo is not None):
        return {"kg": ultimo.valor, "fecha": ultimo.fecha.isoformat(), "origen": "ultimo_registro"}
    if(perfil.peso_inicial_kg is not None):
        return {"kg": perfil.peso_inicial_kg, "fecha": None, "origen": "perfil"}
    return {"kg": None, "fecha": None, "origen": "sin_datos"}


def perfil_a_dict(perfil: Perfil) -> dict:
    return {
        "nombre": perfil.nombre,
        "edad_referencia": perfil.edad_referencia,
        "fecha_referencia_edad": perfil.fecha_referencia_edad.isoformat() if perfil.fecha_referencia_edad else None,
        "fecha_nacimiento": perfil.fecha_nacimiento.isoformat() if perfil.fecha_nacimiento else None,
        "altura_cm": perfil.altura_cm,
        "peso_inicial_kg": perfil.peso_inicial_kg,
        "sexo_formula": perfil.sexo_formula,
        "nivel_actividad": perfil.nivel_actividad,
        "pasos_habituales": perfil.pasos_habituales,
        "presupuesto_semanal": perfil.presupuesto_semanal,
        "presupuesto_confirmado": perfil.presupuesto_confirmado,
        "horarios": perfil.horarios or {},
        "equipo_gimnasio": perfil.equipo_gimnasio,
        "continuidad_entrenamiento": perfil.continuidad_entrenamiento,
        "cargas_conocidas": perfil.cargas_conocidas,
        "modo_registro": perfil.modo_registro,
        "tema": perfil.tema,
        "comensales": perfil.comensales,
        "inicio_plan": perfil.inicio_plan.isoformat() if perfil.inicio_plan else None,
        "zona_horaria": perfil.zona_horaria,
        "alimentos_excluidos": perfil.alimentos_excluidos or [],
        "modo_dias_entreno": perfil.modo_dias_entreno,
        "meta_revision_kg": perfil.meta_revision_kg,
        "silencio_inicio": perfil.silencio_inicio,
        "silencio_fin": perfil.silencio_fin,
        "sintomas_alerta": perfil.sintomas_alerta or {},
        "modo_objetivo": perfil.modo_objetivo,
        "objetivo_descripcion": perfil.objetivo_descripcion,
        "experiencia": perfil.experiencia,
        "hitos_kg": perfil.hitos_kg or [],
        "peso_referencia_kg": perfil.peso_referencia_kg,
        "peso_referencia_origen": perfil.peso_referencia_origen,
        "alergias": perfil.alergias,
        "molestias_actuales": perfil.molestias_actuales,
        "actividad_cotidiana": perfil.actividad_cotidiana,
        "plan_aceptado": perfil.plan_aceptado,
        "agua_referencia": perfil.agua_referencia,
        "version": perfil.version,
    }


def preguntas_pendientes(perfil: Perfil) -> list[dict]:
    if(perfil.pendientes_confirmar):
        return list(perfil.pendientes_confirmar)
    pendientes = []
    if(perfil.sexo_formula is None):
        pendientes.append({"campo": "sexo_formula", "pregunta": "Sexo que se usa en la fórmula energética"})
    if(perfil.nivel_actividad is None or perfil.pasos_habituales is None):
        pendientes.append({"campo": "nivel_actividad", "pregunta": "Actividad fuera del gimnasio y pasos habituales"})
    if(not perfil.presupuesto_confirmado):
        pendientes.append({"campo": "presupuesto_semanal", "pregunta": "Presupuesto semanal (ahora 60 € provisional)"})
    if(not perfil.horarios or len(perfil.horarios) < 4):
        pendientes.append({"campo": "horarios", "pregunta": "Horarios disponibles"})
    if(not perfil.equipo_gimnasio):
        pendientes.append({"campo": "equipo_gimnasio", "pregunta": "Equipo de tu gimnasio"})
    if(perfil.continuidad_entrenamiento is None):
        pendientes.append({"campo": "continuidad_entrenamiento", "pregunta": "Continuidad reciente del entrenamiento y cargas actuales"})
    return pendientes


def energia_usuario(bd: Session, usuario: Usuario, perfil: Perfil, hoy: date) -> dict:
    peso = peso_actual(bd, usuario.id, perfil)
    plan = plan_de_fecha(bd, usuario.id, hoy) or plan_de_fecha(bd, usuario.id, perfil.inicio_plan or hoy)
    kcal_plantilla = None
    if(plan is not None):
        kcal_plantilla = semana_plan(bd, usuario.id, plan)["media_diaria_planificada"]["kcal"]
    resumen = calc_energia.resumen_energia(peso["kg"], perfil.altura_cm, edad_actual(perfil, hoy), perfil.sexo_formula, perfil.nivel_actividad, kcal_plantilla)
    resumen["peso_usado"] = peso
    resumen["edad_usada"] = edad_actual(perfil, hoy)
    resumen["kcal_plantilla_media"] = kcal_plantilla
    resumen["niveles"] = calc_energia.NIVELES_ACTIVIDAD
    return resumen


@enrutador.get("/perfil")
def obtener_perfil(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    return {
        "perfil": perfil_a_dict(perfil),
        "pendientes": preguntas_pendientes(perfil),
        "energia": energia_usuario(bd, usuario, perfil, hoy),
        "objetivo_vigente": objetivo_a_dict(objetivo_vigente(bd, usuario.id, hoy)),
        "hoy": hoy.isoformat(),
    }


@enrutador.put("/perfil")
def actualizar_perfil(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    version = cuerpo.get("version")
    if(version is not None and int(version) != perfil.version):
        raise HTTPException(status_code=409, detail="El perfil cambió en otro dispositivo. Recarga para ver los datos actuales.")
    try:
        aplicar_cambios_perfil(perfil, cuerpo)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    perfil.version = perfil.version + 1
    bd.commit()
    return obtener_perfil(usuario, bd)


def aplicar_cambios_perfil(perfil: Perfil, cuerpo: dict) -> None:
    if("nombre" in cuerpo):
        perfil.nombre = str(cuerpo["nombre"] or "").strip()[:120]
    if("edad_referencia" in cuerpo):
        perfil.edad_referencia = interpretar_entero(cuerpo["edad_referencia"], "La edad", 14, 100, opcional=True)
        perfil.fecha_referencia_edad = hoy_local(perfil.zona_horaria) if perfil.edad_referencia is not None else None
    if("fecha_nacimiento" in cuerpo):
        perfil.fecha_nacimiento = interpretar_fecha(cuerpo["fecha_nacimiento"]) if cuerpo["fecha_nacimiento"] else None
    if("altura_cm" in cuerpo):
        perfil.altura_cm = interpretar_numero(cuerpo["altura_cm"], "La altura", 120, 230, opcional=True)
    if("peso_inicial_kg" in cuerpo):
        perfil.peso_inicial_kg = interpretar_numero(cuerpo["peso_inicial_kg"], "El peso", 30, 350, opcional=True)
    if("sexo_formula" in cuerpo):
        valor = cuerpo["sexo_formula"] or None
        if(valor is not None and valor not in SEXOS):
            raise ValueError("Sexo para la fórmula no válido")
        perfil.sexo_formula = valor
    if("nivel_actividad" in cuerpo):
        valor = cuerpo["nivel_actividad"] or None
        if(valor is not None and valor not in calc_energia.NIVELES_ACTIVIDAD):
            raise ValueError("Nivel de actividad no válido")
        perfil.nivel_actividad = valor
    if("pasos_habituales" in cuerpo):
        perfil.pasos_habituales = interpretar_entero(cuerpo["pasos_habituales"], "Los pasos", 0, 60000, opcional=True)
    if("presupuesto_semanal" in cuerpo):
        perfil.presupuesto_semanal = interpretar_numero(cuerpo["presupuesto_semanal"], "El presupuesto", 0, 1000, opcional=True)
    if("presupuesto_confirmado" in cuerpo):
        perfil.presupuesto_confirmado = bool(cuerpo["presupuesto_confirmado"])
    if("horarios" in cuerpo):
        horarios = {}
        for(clave, valor) in (cuerpo["horarios"] or {}).items():
            if(clave in ("desayuno", "comida", "merienda", "cena", "gimnasio") and valor):
                horarios[clave] = interpretar_hora(valor)
        perfil.horarios = horarios
    for(campo) in ("equipo_gimnasio", "cargas_conocidas"):
        if(campo in cuerpo):
            setattr(perfil, campo, str(cuerpo[campo] or "").strip()[:2000] or None)
    if("continuidad_entrenamiento" in cuerpo):
        valor = cuerpo["continuidad_entrenamiento"] or None
        if(valor is not None and valor not in CONTINUIDADES):
            raise ValueError("Continuidad no válida")
        perfil.continuidad_entrenamiento = valor
    if("modo_registro" in cuerpo):
        if(cuerpo["modo_registro"] not in ("calorias", "sin_calorias")):
            raise ValueError("Modo de registro no válido")
        perfil.modo_registro = cuerpo["modo_registro"]
    if("tema" in cuerpo):
        if(cuerpo["tema"] not in ("sistema", "claro", "oscuro")):
            raise ValueError("Tema no válido")
        perfil.tema = cuerpo["tema"]
    if("comensales" in cuerpo):
        perfil.comensales = interpretar_entero(cuerpo["comensales"], "Los comensales", 1, 12)
    if("alimentos_excluidos" in cuerpo):
        perfil.alimentos_excluidos = [str(x).strip() for x in (cuerpo["alimentos_excluidos"] or []) if str(x).strip()]
    if("modo_dias_entreno" in cuerpo):
        if(cuerpo["modo_dias_entreno"] not in ("estandar", "lunes_viernes")):
            raise ValueError("Distribución no válida")
        perfil.modo_dias_entreno = cuerpo["modo_dias_entreno"]
    if("meta_revision_kg" in cuerpo):
        perfil.meta_revision_kg = interpretar_numero(cuerpo["meta_revision_kg"], "La meta de revisión", 30, 350, opcional=True)
    if("silencio_inicio" in cuerpo):
        perfil.silencio_inicio = interpretar_hora(cuerpo["silencio_inicio"])
    if("silencio_fin" in cuerpo):
        perfil.silencio_fin = interpretar_hora(cuerpo["silencio_fin"])
    if("modo_objetivo" in cuerpo):
        if(cuerpo["modo_objetivo"] not in ("perder", "mantener", "ganar")):
            raise ValueError("Modo de objetivo no válido")
        perfil.modo_objetivo = cuerpo["modo_objetivo"]
    if("hitos_kg" in cuerpo):
        perfil.hitos_kg = [interpretar_numero(h, "El hito", 30, 350) for h in (cuerpo["hitos_kg"] or [])][:5]
    if("peso_referencia_kg" in cuerpo):
        perfil.peso_referencia_kg = interpretar_numero(cuerpo["peso_referencia_kg"], "El peso de referencia", 30, 350, opcional=True)
    for(campo) in ("alergias", "molestias_actuales", "actividad_cotidiana", "objetivo_descripcion"):
        if(campo in cuerpo):
            setattr(perfil, campo, str(cuerpo[campo] or "").strip()[:1000] or None)
    if("experiencia" in cuerpo):
        if(cuerpo["experiencia"] not in (None, "", "principiante", "con_experiencia")):
            raise ValueError("Experiencia no válida")
        perfil.experiencia = cuerpo["experiencia"] or None
    if("inicio_plan" in cuerpo):
        perfil.inicio_plan = interpretar_fecha(cuerpo["inicio_plan"]) if cuerpo["inicio_plan"] else None
    if("pendientes_resueltos" in cuerpo):
        resueltos = set(cuerpo["pendientes_resueltos"] or [])
        perfil.pendientes_confirmar = [p for p in (perfil.pendientes_confirmar or []) if p["campo"] not in resueltos]
    if("sintomas_alerta" in cuerpo):
        permitidos = ("mareos", "fatiga_marcada", "caida_rendimiento", "perdida_rapida")
        perfil.sintomas_alerta = {k: bool(v) for k, v in (cuerpo["sintomas_alerta"] or {}).items() if k in permitidos}


@enrutador.get("/objetivos")
def historial_objetivos(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(Objetivo).filter(Objetivo.usuario_id == usuario.id).order_by(Objetivo.vigente_desde.desc(), Objetivo.id.desc()).all()
    return {"objetivos": [objetivo_a_dict(o) for o in filas]}


@enrutador.post("/objetivos")
def nuevo_objetivo(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    try:
        vigente = interpretar_fecha(cuerpo.get("vigente_desde") or hoy.isoformat())
        kcal = interpretar_numero(cuerpo.get("kcal"), "Las kcal", 1200, 6000, opcional=True)
        proteina = interpretar_numero(cuerpo.get("proteina_g"), "La proteína", 40, 300, opcional=True)
        hidratos = interpretar_numero(cuerpo.get("hidratos_g"), "Los hidratos", 0, 900, opcional=True)
        grasas = interpretar_numero(cuerpo.get("grasas_g"), "Las grasas", 0, 300, opcional=True)
        fibra = interpretar_numero(cuerpo.get("fibra_g"), "La fibra", 0, 100, opcional=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if(vigente < hoy):
        raise HTTPException(status_code=422, detail="Un objetivo nuevo empieza hoy o más adelante: no se aplica al historial")
    energia = energia_usuario(bd, usuario, perfil, hoy)
    objetivo = Objetivo(
        usuario_id=usuario.id,
        vigente_desde=vigente,
        kcal=kcal,
        proteina_g=proteina,
        hidratos_g=hidratos,
        grasas_g=grasas,
        fibra_g=fibra,
        modo=perfil.modo_objetivo,
        origen=str(cuerpo.get("origen") or "manual")[:40],
        provisional=bool(cuerpo.get("provisional", False)),
        detalle={
            "nota": str(cuerpo.get("nota") or "")[:500],
            "formula": energia.get("formula"),
            "reposo": energia.get("reposo"),
            "gasto": energia.get("gasto"),
            "sexo": perfil.sexo_formula,
        "modo": perfil.modo_objetivo,
            "nivel_actividad": perfil.nivel_actividad,
        },
    )
    bd.add(objetivo)
    bd.commit()
    return {"objetivo": objetivo_a_dict(objetivo)}


@enrutador.get("/objetivos/revision")
def revision_objetivo(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    pesos = [{"fecha": m.fecha, "valor": m.valor} for m in bd.query(Medicion).filter(Medicion.usuario_id == usuario.id, Medicion.tipo == "peso", Medicion.borrado == False).all()]
    semanas = calc_progreso.medias_semanales(pesos)
    objetivo = objetivo_vigente(bd, usuario.id, hoy)
    energia = energia_usuario(bd, usuario, perfil, hoy)
    from app.rutas.progreso import adherencia_reciente
    propuesta = calc_progreso.propuesta_ajuste(
        semanas,
        objetivo.kcal if objetivo is not None and not objetivo.provisional else None,
        energia.get("reposo"),
        perfil.sintomas_alerta or {},
        adherencia_reciente(bd, usuario.id, hoy),
        objetivo.vigente_desde if objetivo is not None else None,
        hoy,
        perfil.modo_objetivo,
    )
    if(objetivo is not None and objetivo.provisional and propuesta["accion"] != "detener"):
        propuesta = {"accion": "esperar", "mensaje": "El objetivo actual es provisional. Confirma tus datos en el perfil para fijarlo; después se revisa con tus registros."}
    return {"propuesta": propuesta, "semanas": [{**s, "lunes": s["lunes"].isoformat()} for s in semanas]}


@enrutador.post("/perfil/confirmar-plan")
def confirmar_plan(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    from datetime import timedelta
    from app.calculos.fechas import lunes_de
    from app.modelos import ComidaPlanificada, Consumo, PlanSemana, Rutina
    perfil = perfil_de(bd, usuario.id)
    try:
        inicio = interpretar_fecha(cuerpo.get("inicio_plan"))
        aplicar_cambios_perfil(perfil, {k: v for k, v in cuerpo.items() if k != "inicio_plan"})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    perfil.inicio_plan = inicio
    nuevo_lunes = lunes_de(inicio)
    propuesta = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.origen == "propuesta").first()
    if(propuesta is not None and propuesta.lunes != nuevo_lunes):
        if(bd.query(Consumo).join(ComidaPlanificada, Consumo.comida_planificada_id == ComidaPlanificada.id).filter(ComidaPlanificada.plan_id == propuesta.id).count() > 0):
            raise HTTPException(status_code=409, detail="La semana propuesta ya tiene registros: no se mueve para no alterar el historial")
        if(bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.lunes == nuevo_lunes, PlanSemana.id != propuesta.id).first() is None):
            desplazamiento = nuevo_lunes - propuesta.lunes
            for(c) in bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == propuesta.id).all():
                c.fecha = c.fecha + desplazamiento
            propuesta.lunes = nuevo_lunes
    if(propuesta is not None):
        propuesta.origen = "plantilla_inicial"
    for(r) in bd.query(Rutina).filter(Rutina.usuario_id == usuario.id, Rutina.version == 1).all():
        r.vigente_desde = inicio
    for(o) in bd.query(Objetivo).filter(Objetivo.usuario_id == usuario.id, Objetivo.provisional == True).all():
        o.vigente_desde = inicio
        o.provisional = False
    perfil.pendientes_confirmar = []
    perfil.plan_aceptado = True
    perfil.version = perfil.version + 1
    bd.commit()
    return obtener_perfil(usuario, bd)
