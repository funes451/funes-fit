from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import nutricion as calc_nutricion
from app.calculos import progreso as calc_progreso
from app.calculos.fechas import hoy_local, interpretar_fecha, interpretar_hora, lunes_de, texto_fecha
from app.calculos.numeros import interpretar_numero
from app.db import obtener_bd
from app.modelos import CambioMenu, ComidaPlanificada, PlanSemana, Receta, Usuario
from app.seguridad import usuario_actual
from app.servicios.nucleo import (
    MOMENTOS,
    CacheRecetas,
    lista_compra_plan,
    perfil_de,
    plan_de_fecha,
    productos_preferidos,
    propio,
    publica,
    resumen_dia,
    semana_plan,
)

enrutador = APIRouter(prefix="/api/menu", tags=["menu"])


def _registrar_cambio(bd: Session, plan: PlanSemana, descripcion: str, datos: dict) -> None:
    plan.version = plan.version + 1
    bd.add(CambioMenu(plan_id=plan.id, version=plan.version, descripcion=descripcion, datos=datos))


@enrutador.get("/dia")
def dia(fecha: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    objetivo_fecha = interpretar_fecha(fecha) if fecha else hoy
    resumen = resumen_dia(bd, usuario.id, objetivo_fecha)
    resumen["hoy"] = hoy.isoformat()
    resumen["texto_fecha"] = texto_fecha(objetivo_fecha)
    resumen["hay_plan"] = plan_de_fecha(bd, usuario.id, objetivo_fecha) is not None
    resumen["modo_registro"] = perfil.modo_registro
    return resumen


@enrutador.get("/semana")
def semana(fecha: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    hoy = hoy_local(perfil.zona_horaria)
    objetivo_fecha = interpretar_fecha(fecha) if fecha else hoy
    plan = plan_de_fecha(bd, usuario.id, objetivo_fecha)
    lunes = lunes_de(objetivo_fecha)
    if(plan is None):
        anterior = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.lunes < lunes).order_by(PlanSemana.lunes.desc()).first()
        return {"plan": None, "lunes": lunes.isoformat(), "hoy": hoy.isoformat(), "puede_repetir_desde": anterior.lunes.isoformat() if anterior else None, "plan_aceptado": perfil.plan_aceptado}
    datos = semana_plan(bd, usuario.id, plan)
    datos["hoy"] = hoy.isoformat()
    datos["lunes"] = lunes.isoformat()
    datos["plan_aceptado"] = perfil.plan_aceptado
    datos["cambios"] = [{"version": c.version, "descripcion": c.descripcion, "momento": c.momento.isoformat()} for c in bd.query(CambioMenu).filter(CambioMenu.plan_id == plan.id).order_by(CambioMenu.version.desc()).limit(20).all()]
    return datos


@enrutador.get("/historial")
def historial(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    planes = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id).order_by(PlanSemana.lunes.desc()).all()
    return {"semanas": [{"id": p.id, "lunes": p.lunes.isoformat(), "version": p.version, "origen": p.origen, "cerrada": p.cerrada} for p in planes]}


@enrutador.post("/semana/generar")
def generar(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        lunes = lunes_de(interpretar_fecha(cuerpo.get("lunes")))
        desde = lunes_de(interpretar_fecha(cuerpo.get("desde_lunes"))) if cuerpo.get("desde_lunes") else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    modo = cuerpo.get("modo") or "repetir"
    if(modo not in ("repetir", "variar")):
        raise HTTPException(status_code=422, detail="Modo no válido")
    existente = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.lunes == lunes).first()
    if(existente is not None):
        return {"plan_id": existente.id, "creado": False}
    if(desde is None):
        base = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.lunes < lunes).order_by(PlanSemana.lunes.desc()).first()
    else:
        base = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario.id, PlanSemana.lunes == desde).first()
    if(base is None):
        raise HTTPException(status_code=404, detail="No hay una semana anterior que usar como plantilla")
    comidas = bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == base.id).order_by(ComidaPlanificada.fecha, ComidaPlanificada.orden).all()
    nuevo = PlanSemana(usuario_id=usuario.id, lunes=lunes, version=1, origen="repeticion_programada" if modo == "repetir" else "variada", repite_de=base.id)
    bd.add(nuevo)
    bd.flush()
    desplazamiento = lunes - base.lunes
    principales = {}
    if(modo == "variar"):
        dias = sorted({c.fecha for c in comidas})
        for(momento) in ("comida", "cena"):
            secuencia = [next((c.receta_id for c in comidas if c.fecha == d and c.momento == momento), None) for d in dias]
            if(len(secuencia) > 0):
                rotada = secuencia[2:] + secuencia[:2]
                for(d, receta_id) in zip(dias, rotada):
                    principales[(d, momento)] = receta_id
    for(c) in comidas:
        receta_id = principales.get((c.fecha, c.momento)) or c.receta_id
        bd.add(ComidaPlanificada(plan_id=nuevo.id, usuario_id=usuario.id, fecha=c.fecha + desplazamiento, momento=c.momento, hora=c.hora, receta_id=receta_id, factor=c.factor, orden=c.orden, opcional=c.opcional))
    bd.commit()
    return {"plan_id": nuevo.id, "creado": True, "origen": nuevo.origen}


@enrutador.patch("/comidas/{comida_id}")
def editar_comida(comida_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    comida = propio(bd, ComidaPlanificada, comida_id, usuario.id, "Comida no encontrada")
    plan = bd.get(PlanSemana, comida.plan_id)
    cambios = {}
    try:
        if("hora" in cuerpo):
            comida.hora = interpretar_hora(cuerpo["hora"]) if cuerpo["hora"] else None
            cambios["hora"] = comida.hora
        if("fecha" in cuerpo):
            fecha = interpretar_fecha(cuerpo["fecha"])
            if(lunes_de(fecha) != plan.lunes):
                raise ValueError("Solo puedes mover la comida dentro de la misma semana")
            comida.fecha = fecha
            cambios["fecha"] = fecha.isoformat()
        if("momento" in cuerpo):
            if(cuerpo["momento"] not in MOMENTOS):
                raise ValueError("Momento no válido")
            comida.momento = cuerpo["momento"]
            cambios["momento"] = comida.momento
        if("factor" in cuerpo):
            comida.factor = interpretar_numero(cuerpo["factor"], "Las raciones", 0.25, 4)
            cambios["factor"] = comida.factor
        if("receta_id" in cuerpo):
            receta = propio(bd, Receta, int(cuerpo["receta_id"]), usuario.id, "Receta no encontrada")
            cambios["receta"] = {"antes": comida.receta_id, "despues": receta.id}
            comida.receta_id = receta.id
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    _registrar_cambio(bd, plan, "Comida editada", {"comida_id": comida.id, **cambios})
    bd.commit()
    return {"ok": True, "version": plan.version}


@enrutador.get("/comidas/{comida_id}/equivalentes")
def equivalentes(comida_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    comida = propio(bd, ComidaPlanificada, comida_id, usuario.id, "Comida no encontrada")
    perfil = perfil_de(bd, usuario.id)
    cache = CacheRecetas(bd, usuario.id)
    actual = cache.receta(comida.receta_id)
    kcal = actual["nutrientes_racion"]["kcal"] * comida.factor
    proteina = actual["nutrientes_racion"]["proteina"] * comida.factor
    opciones = []
    for(r) in bd.query(Receta).filter(Receta.usuario_id == usuario.id, Receta.archivada == False, Receta.id != comida.receta_id).all():
        datos = cache.receta(r.id)
        if(any(calc_nutricion.contiene_excluido(i["nombre"], perfil.alimentos_excluidos) for i in datos["ingredientes"]) or calc_nutricion.contiene_excluido(datos["nombre"], perfil.alimentos_excluidos)):
            continue
        if(datos["nutrientes_racion"]["kcal"] <= 0):
            continue
        factor = round(kcal / datos["nutrientes_racion"]["kcal"] * 4) / 4
        factor = min(2.0, max(0.5, factor))
        kcal_opcion = datos["nutrientes_racion"]["kcal"] * factor
        proteina_opcion = datos["nutrientes_racion"]["proteina"] * factor
        if(abs(kcal_opcion - kcal) / kcal > 0.12 or proteina_opcion < proteina * 0.85):
            continue
        opciones.append({"receta": publica(datos), "factor": factor, "kcal": kcal_opcion, "proteina": proteina_opcion, "mismo_momento": r.momento_tipico == comida.momento})
    opciones.sort(key=lambda o: (not o["mismo_momento"], abs(o["kcal"] - kcal)))
    return {"actual": {"kcal": kcal, "proteina": proteina, "nombre": actual["nombre"]}, "opciones": opciones}


def _ajuste(bd: Session, usuario_id: int, plan: PlanSemana, kcal_objetivo: float) -> dict:
    cache = CacheRecetas(bd, usuario_id)
    comidas = bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan.id).all()
    dias = {}
    for(c) in comidas:
        receta = cache.receta(c.receta_id)
        kcal_base = receta["nutrientes_racion"]["kcal"]
        clave = c.fecha
        if(clave not in dias):
            dias[clave] = {"fijas": 0.0, "ajustables": 0.0, "comidas": []}
        if(c.opcional):
            continue
        if(c.momento in ("comida", "cena")):
            dias[clave]["ajustables"] = dias[clave]["ajustables"] + kcal_base
            dias[clave]["comidas"].append((c, kcal_base))
        else:
            dias[clave]["fijas"] = dias[clave]["fijas"] + kcal_base * c.factor
    propuesta = []
    for(fecha) in sorted(dias.keys()):
        datos = dias[fecha]
        resultado = calc_progreso.factores_para_objetivo(datos["fijas"], datos["ajustables"], kcal_objetivo)
        total = datos["fijas"] + datos["ajustables"] * resultado["factor"]
        actual = datos["fijas"] + sum(k * c.factor for c, k in datos["comidas"])
        propuesta.append({"fecha": fecha.isoformat(), "factor": resultado["factor"], "limitado": resultado["limitado"], "kcal_actual": actual, "kcal_propuesta": total, "comidas": [c.id for c, _ in datos["comidas"]]})
    return {"kcal_objetivo": kcal_objetivo, "dias": propuesta, "nota": "Se escalan comida y cena; desayuno y merienda no cambian. La compra se recalcula al aplicar."}


@enrutador.post("/{plan_id}/ajuste/propuesta")
def propuesta_ajuste(plan_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    try:
        kcal = interpretar_numero(cuerpo.get("kcal_objetivo"), "Las kcal", 1200, 6000)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return _ajuste(bd, usuario.id, plan, kcal)


@enrutador.post("/{plan_id}/ajuste/aplicar")
def aplicar_ajuste(plan_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    try:
        kcal = interpretar_numero(cuerpo.get("kcal_objetivo"), "Las kcal", 1200, 6000)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    propuesta = _ajuste(bd, usuario.id, plan, kcal)
    hoy = hoy_local(perfil_de(bd, usuario.id).zona_horaria)
    aplicados = 0
    for(dia_propuesto) in propuesta["dias"]:
        if(interpretar_fecha(dia_propuesto["fecha"]) < hoy and not cuerpo.get("incluir_pasado")):
            continue
        for(comida_id) in dia_propuesto["comidas"]:
            comida = bd.get(ComidaPlanificada, comida_id)
            comida.factor = dia_propuesto["factor"]
            aplicados = aplicados + 1
    _registrar_cambio(bd, plan, f"Raciones ajustadas a unas {kcal:.0f} kcal/día", {"kcal_objetivo": kcal, "comidas": aplicados})
    bd.commit()
    return {"ok": True, "comidas_ajustadas": aplicados, "version": plan.version}


@enrutador.get("/{plan_id}/abaratar")
def abaratar(plan_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    perfil = perfil_de(bd, usuario.id)
    cache = CacheRecetas(bd, usuario.id)
    productos = productos_preferidos(bd, usuario.id)

    def coste_racion(receta: dict, factor: float) -> float | None:
        total = 0.0
        for(i) in receta["_ingredientes_calculo"]:
            producto = productos.get(i["alimento"]["id"])
            if(producto is None or producto.get("precio") is None):
                return None
            cantidad = calc_nutricion.a_unidad_base(i["cantidad"], i["unidad"], i["alimento"]) * (i["alimento"].get("factor_compra") or 1) * factor / receta["raciones"]
            total = total + cantidad / producto["capacidad_util"] * producto["precio"]
        return total

    recetas = [cache.receta(r.id) for r in bd.query(Receta).filter(Receta.usuario_id == usuario.id, Receta.archivada == False).all()]
    propuestas = []
    sin_datos = set()
    for(c) in bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan.id, ComidaPlanificada.momento.in_(("comida", "cena"))).order_by(ComidaPlanificada.fecha).all():
        actual = cache.receta(c.receta_id)
        coste_actual = coste_racion(actual, c.factor)
        if(coste_actual is None):
            sin_datos.add(actual["nombre"])
            continue
        kcal = actual["nutrientes_racion"]["kcal"] * c.factor
        proteina = actual["nutrientes_racion"]["proteina"] * c.factor
        mejor = None
        for(r) in recetas:
            if(r["id"] == actual["id"] or r["nutrientes_racion"]["kcal"] <= 0):
                continue
            if(any(calc_nutricion.contiene_excluido(i["nombre"], perfil.alimentos_excluidos) for i in r["ingredientes"])):
                continue
            factor = min(2.0, max(0.5, round(kcal / r["nutrientes_racion"]["kcal"] * 4) / 4))
            if(abs(r["nutrientes_racion"]["kcal"] * factor - kcal) / kcal > 0.1 or r["nutrientes_racion"]["proteina"] * factor < proteina * 0.9):
                continue
            coste = coste_racion(r, factor)
            if(coste is None):
                sin_datos.add(r["nombre"])
                continue
            if(coste < coste_actual - 0.05 and (mejor is None or coste < mejor["coste"])):
                mejor = {"receta_id": r["id"], "nombre": r["nombre"], "factor": factor, "coste": coste}
        if(mejor is not None):
            propuestas.append({"comida_id": c.id, "fecha": c.fecha.isoformat(), "momento": c.momento, "actual": actual["nombre"], "coste_actual": coste_actual, "propuesta": mejor, "ahorro": coste_actual - mejor["coste"]})
    return {
        "propuestas": propuestas,
        "recetas_sin_precios": sorted(sin_datos),
        "aviso": "Las sustituciones mantienen kcal (±10 %) y proteína similares y respetan tus exclusiones. No se aplican hasta que las aceptes. Sin precios suficientes no se puede comparar coste.",
    }


@enrutador.post("/{plan_id}/abaratar/aplicar")
def aplicar_abaratar(plan_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    aplicados = []
    for(cambio) in cuerpo.get("cambios") or []:
        comida = propio(bd, ComidaPlanificada, int(cambio["comida_id"]), usuario.id, "Comida no encontrada")
        if(comida.plan_id != plan.id):
            raise HTTPException(status_code=422, detail="La comida no pertenece a esta semana")
        receta = propio(bd, Receta, int(cambio["receta_id"]), usuario.id, "Receta no encontrada")
        comida.receta_id = receta.id
        comida.factor = interpretar_numero(cambio.get("factor", 1), "Las raciones", 0.25, 4)
        aplicados.append(comida.id)
    if(len(aplicados) > 0):
        _registrar_cambio(bd, plan, "Sustituciones para abaratar la semana", {"comidas": aplicados})
    bd.commit()
    return {"ok": True, "aplicados": len(aplicados)}


@enrutador.get("/{plan_id}/tandas")
def tandas(plan_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    cache = CacheRecetas(bd, usuario.id)
    dias_tanda = [plan.lunes, plan.lunes + timedelta(days=3)]
    resultado = [{"fecha": d.isoformat(), "nombre": f"Tanda {i + 1}", "recetas": {}} for i, d in enumerate(dias_tanda)]
    al_momento = []
    for(c) in bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan.id).order_by(ComidaPlanificada.fecha, ComidaPlanificada.orden).all():
        receta = cache.receta(c.receta_id)
        if(receta["modo_preparacion"] != "lote"):
            al_momento.append({"fecha": c.fecha.isoformat(), "momento": c.momento, "receta": receta["nombre"]})
            continue
        indice = 0 if c.fecha < dias_tanda[1] else 1
        cocina = dias_tanda[indice]
        dias_espera = (c.fecha - cocina).days
        if(dias_espera <= 0):
            conservar = "comer recién hecho"
        elif(dias_espera <= receta["max_nevera_dias"]):
            conservar = f"nevera ({dias_espera} día{'s' if dias_espera > 1 else ''})"
        else:
            conservar = "congelar por raciones y descongelar en nevera el día antes"
        grupo = resultado[indice]["recetas"].setdefault(receta["id"], {"receta": receta["nombre"], "raciones": 0.0, "usos": [], "conservacion": receta["conservacion"]})
        grupo["raciones"] = grupo["raciones"] + c.factor
        grupo["usos"].append({"fecha": c.fecha.isoformat(), "momento": c.momento, "conservar": conservar})
    for(t) in resultado:
        t["recetas"] = list(t["recetas"].values())
    return {
        "tandas": resultado,
        "al_momento": al_momento,
        "normas": [
            "Refrigera las sobras pronto y consúmelas normalmente en 2 días, o congélalas.",
            "Arroz cocido: enfríalo rápido (idealmente en menos de 1 hora) y en nevera como máximo 24 h antes de comerlo o recalentarlo.",
            "Descongela en la nevera y recalienta hasta que esté muy caliente por todo.",
            "No guardes toda la comida de la semana siete días en la nevera.",
        ],
    }


@enrutador.get("/{plan_id}/compra")
def compra(plan_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    return lista_compra_plan(bd, usuario.id, plan)


@enrutador.post("/aceptar-plan")
def aceptar_plan(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    perfil = perfil_de(bd, usuario.id)
    perfil.plan_aceptado = True
    perfil.version = perfil.version + 1
    bd.commit()
    return {"ok": True}
