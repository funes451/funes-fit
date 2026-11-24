from datetime import timedelta

from sqlalchemy.orm import Session

from app import datos_iniciales as datos
from app.calculos import entrenamiento as calc_entreno
from app.calculos import nutricion as calc_nutricion
from app.modelos import (
    Alimento,
    ComidaPlanificada,
    Ejercicio,
    EjercicioRutina,
    IngredienteReceta,
    Medicion,
    Objetivo,
    Perfil,
    PlanSemana,
    Producto,
    Receta,
    Recordatorio,
    Rutina,
)
from app.servicios.nucleo import CacheRecetas

ORDEN_MOMENTOS = {"desayuno": 0, "comida": 1, "merienda": 2, "cena": 3}


PLANES = ("funes", "amigo", "vacio")


def sembrar_usuario(bd: Session, usuario_id: int, plan: str) -> dict:
    if(plan not in PLANES):
        raise ValueError(f"Plan desconocido: {plan}")
    if(plan == "amigo"):
        from app.semilla_amigo import sembrar_amigo
        return sembrar_amigo(bd, usuario_id)
    creados = {"perfil": 0, "alimentos": 0, "productos": 0, "recetas": 0, "plan": 0, "ejercicios": 0, "rutina": 0, "recordatorios": 0, "objetivo": 0, "medicion": 0}
    perfil = bd.get(Perfil, usuario_id)
    if(perfil is None):
        if(plan == "funes"):
            valores = dict(datos.PERFIL_FUNES)
            valores.update({"modo_objetivo": "perder", "experiencia": "con_experiencia", "objetivo_descripcion": "Perder grasa conservando músculo y mejorar la condición física, sin dietas extremas.", "hitos_kg": [106.2]})
        else:
            valores = {"nombre": "", "alimentos_excluidos": [], "modo_objetivo": "mantener", "plan_aceptado": True}
        perfil = Perfil(usuario_id=usuario_id, **valores)
        bd.add(perfil)
        creados["perfil"] = 1
    bd.flush()
    sembrar_catalogo(bd, usuario_id, creados)
    if(plan == "vacio"):
        bd.commit()
        return creados
    alimentos = {a.codigo: a for a in bd.query(Alimento).filter(Alimento.usuario_id == usuario_id, Alimento.codigo.isnot(None)).all()}
    recetas = {r.codigo: r for r in bd.query(Receta).filter(Receta.usuario_id == usuario_id, Receta.codigo.isnot(None)).all()}
    for(entrada) in datos.RECETAS:
        if(entrada["codigo"] in recetas):
            continue
        valores = dict(entrada)
        ingredientes = valores.pop("ingredientes")
        receta = Receta(usuario_id=usuario_id, origen="plantilla", raciones=1, **valores)
        bd.add(receta)
        bd.flush()
        for(orden, (codigo, cantidad, unidad)) in enumerate(ingredientes):
            bd.add(IngredienteReceta(receta_id=receta.id, alimento_id=alimentos[codigo].id, cantidad=cantidad, unidad=unidad, orden=orden))
        recetas[entrada["codigo"]] = receta
        creados["recetas"] = creados["recetas"] + 1
    bd.flush()
    plan_semana = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario_id, PlanSemana.lunes == datos.INICIO_PLAN).first()
    if(plan_semana is None):
        plan_semana = PlanSemana(usuario_id=usuario_id, lunes=datos.INICIO_PLAN, version=1, origen="plantilla_inicial")
        bd.add(plan_semana)
        bd.flush()
        horarios = perfil.horarios or datos.PERFIL_FUNES["horarios"]
        for(indice, (comida, cena)) in enumerate(datos.MENU_SEMANA):
            fecha = datos.INICIO_PLAN + timedelta(days=indice)
            for(momento, codigo) in (("desayuno", "desayuno"), ("comida", comida), ("merienda", "merienda"), ("cena", cena)):
                bd.add(ComidaPlanificada(plan_id=plan_semana.id, usuario_id=usuario_id, fecha=fecha, momento=momento, hora=horarios.get(momento), receta_id=recetas[codigo].id, factor=1.0, orden=ORDEN_MOMENTOS[momento]))
        creados["plan"] = 1
    bd.flush()
    ejercicios = {e.codigo: e for e in bd.query(Ejercicio).filter(Ejercicio.usuario_id == usuario_id, Ejercicio.codigo.isnot(None)).all()}
    if(bd.query(Rutina).filter(Rutina.usuario_id == usuario_id).count() == 0):
        rutina = Rutina(
            usuario_id=usuario_id,
            nombre="Rutina de cinco días",
            version=1,
            vigente_desde=datos.INICIO_PLAN,
            activa=True,
            distribucion={str(k): v for k, v in calc_entreno.distribucion("estandar").items()},
            configuracion={"adaptacion": dict(calc_entreno.ADAPTACION_POR_DEFECTO)},
            plantilla="funes_5_dias",
        )
        bd.add(rutina)
        bd.flush()
        for(sesion, filas) in datos.RUTINA.items():
            for(orden, (codigo, series, rep_min, rep_max, por_lado)) in enumerate(filas):
                bd.add(EjercicioRutina(rutina_id=rutina.id, sesion=sesion, ejercicio_id=ejercicios[codigo].id, orden=orden, series=series, rep_min=rep_min, rep_max=rep_max, por_lado=por_lado))
        creados["rutina"] = 1
    if(bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario_id).count() == 0):
        for(entrada) in datos.RECORDATORIOS:
            bd.add(Recordatorio(usuario_id=usuario_id, activo=False, texto_generico=True, **entrada))
            creados["recordatorios"] = creados["recordatorios"] + 1
    bd.flush()
    if(bd.query(Objetivo).filter(Objetivo.usuario_id == usuario_id).count() == 0):
        cache = CacheRecetas(bd, usuario_id)
        totales = []
        proteinas = []
        for(comida) in bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan_semana.id).all():
            receta = cache.receta(comida.receta_id)
            totales.append(receta["nutrientes_racion"]["kcal"] * comida.factor)
            proteinas.append(receta["nutrientes_racion"]["proteina"] * comida.factor)
        bd.add(Objetivo(
            usuario_id=usuario_id,
            vigente_desde=datos.INICIO_PLAN,
            kcal=round(sum(totales) / 7),
            proteina_g=round(sum(proteinas) / 7),
            origen="plantilla_provisional",
            modo="perder",
            provisional=True,
            detalle={"nota": "Media de la plantilla inicial. Provisional: pendiente de sexo para la fórmula y actividad. No es una prescripción."},
        ))
        creados["objetivo"] = 1
    if(bd.query(Medicion).filter(Medicion.id_cliente == f"semilla-peso-{usuario_id}").first() is None):
        bd.add(Medicion(usuario_id=usuario_id, id_cliente=f"semilla-peso-{usuario_id}", fecha=datos.INICIO_PLAN, tipo="peso", valor=111.8, unidad="kg", notas="Dato inicial indicado en el plan"))
        creados["medicion"] = 1
    bd.commit()
    return creados


def sembrar_catalogo(bd: Session, usuario_id: int, creados: dict, alimentos_extra: list | None = None, productos_extra: list | None = None, ejercicios_extra: list | None = None) -> None:
    alimentos = {a.codigo: a for a in bd.query(Alimento).filter(Alimento.usuario_id == usuario_id, Alimento.codigo.isnot(None)).all()}
    for(entrada) in datos.ALIMENTOS + (alimentos_extra or []):
        if(entrada["codigo"] in alimentos):
            continue
        valores = dict(entrada)
        valores.setdefault("fuente", datos.FUENTE_TABLA)
        valores.setdefault("alergenos", [])
        alimento = Alimento(usuario_id=usuario_id, origen="generico", **valores)
        bd.add(alimento)
        alimentos[entrada["codigo"]] = alimento
        creados["alimentos"] = creados.get("alimentos", 0) + 1
    bd.flush()
    productos = {p.codigo for p in bd.query(Producto).filter(Producto.usuario_id == usuario_id, Producto.codigo.isnot(None)).all()}
    for(entrada) in datos.PRODUCTOS + (productos_extra or []):
        if(entrada["codigo"] in productos):
            continue
        valores = dict(entrada)
        codigo_alimento = valores.pop("alimento")
        nota = valores.pop("nota", None)
        valores.setdefault("precio_origen", "desconocido")
        bd.add(Producto(usuario_id=usuario_id, alimento_id=alimentos[codigo_alimento].id, nota_capacidad=(nota + " " if nota else "") + datos.NOTA_FORMATO, formato_verificado=False, **valores))
        productos.add(entrada["codigo"])
        creados["productos"] = creados.get("productos", 0) + 1
    ejercicios = {e.codigo for e in bd.query(Ejercicio).filter(Ejercicio.usuario_id == usuario_id, Ejercicio.codigo.isnot(None)).all()}
    for(entrada) in datos.EJERCICIOS + (ejercicios_extra or []):
        if(entrada["codigo"] in ejercicios):
            continue
        bd.add(Ejercicio(usuario_id=usuario_id, **entrada))
        ejercicios.add(entrada["codigo"])
        creados["ejercicios"] = creados.get("ejercicios", 0) + 1
    bd.flush()
