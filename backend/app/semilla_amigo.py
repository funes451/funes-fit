from datetime import timedelta

from sqlalchemy.orm import Session

from app import datos_amigo as datos
from app.calculos.fechas import hoy_local, lunes_de
from app.modelos import (
    Alimento,
    ComidaPlanificada,
    Ejercicio,
    EjercicioRutina,
    IngredienteReceta,
    Objetivo,
    Perfil,
    PlanSemana,
    Receta,
    Recordatorio,
    Rutina,
)
from app.semilla import sembrar_catalogo

ORDEN = {"desayuno": 0, "comida": 1, "merienda": 2, "cena": 3, "extra": 4}


def sembrar_amigo(bd: Session, usuario_id: int) -> dict:
    creados = {"perfil": 0, "alimentos": 0, "productos": 0, "recetas": 0, "plan": 0, "ejercicios": 0, "rutina": 0, "rutina_ejercicios": 0, "recordatorios": 0, "objetivo": 0}
    perfil = bd.get(Perfil, usuario_id)
    hoy = hoy_local("Europe/Madrid")
    if(perfil is None):
        perfil = Perfil(usuario_id=usuario_id, **datos.PERFIL_AMIGO)
        bd.add(perfil)
        creados["perfil"] = 1
    bd.flush()
    sembrar_catalogo(bd, usuario_id, creados, datos.ALIMENTOS_AMIGO, datos.PRODUCTOS_AMIGO, (datos.RUTINA_AMIGO or {}).get("ejercicios"))
    alimentos = {a.codigo: a for a in bd.query(Alimento).filter(Alimento.usuario_id == usuario_id, Alimento.codigo.isnot(None)).all()}
    recetas = {r.codigo: r for r in bd.query(Receta).filter(Receta.usuario_id == usuario_id, Receta.codigo.isnot(None)).all()}
    for(entrada) in datos.RECETAS_AMIGO:
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
    if(bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario_id).count() == 0):
        lunes = lunes_de(perfil.inicio_plan or hoy)
        plan = PlanSemana(usuario_id=usuario_id, lunes=lunes, version=1, origen="propuesta")
        bd.add(plan)
        bd.flush()
        for(indice, (desayuno, comida, cena)) in enumerate(datos.MENU_AMIGO):
            fecha = lunes + timedelta(days=indice)
            for(momento, codigo, opcional) in (("desayuno", desayuno, False), ("comida", comida, False), ("merienda", "am_merienda_tostadas", False), ("cena", cena, False), ("extra", "am_snack", True)):
                bd.add(ComidaPlanificada(plan_id=plan.id, usuario_id=usuario_id, fecha=fecha, momento=momento, receta_id=recetas[codigo].id, factor=1.0, orden=ORDEN[momento], opcional=opcional))
        creados["plan"] = 1
    rutina = bd.query(Rutina).filter(Rutina.usuario_id == usuario_id, Rutina.plantilla == "amigo_4_dias").order_by(Rutina.version).first()
    if(rutina is None):
        rutina = Rutina(
            usuario_id=usuario_id,
            nombre="Fuerza 4 días + fútbol sala",
            version=1,
            vigente_desde=perfil.inicio_plan or hoy,
            activa=True,
            plantilla="amigo_4_dias",
            distribucion=dict(datos.DISTRIBUCION_AMIGO),
            configuracion={
                "adaptacion": dict(datos.ADAPTACION_AMIGO),
                "nombres_sesion": dict(datos.NOMBRES_SESION_AMIGO),
                "sesiones_reducibles": ["torso_b"],
                "inicio_desde_rutina": True,
                "pendiente_documento": datos.RUTINA_AMIGO is None,
                "advertencia": datos.ADVERTENCIA_AMIGO,
                "texto_descanso": "Descanso o recuperación. El partido del fin de semana se configura cada semana.",
            },
        )
        bd.add(rutina)
        bd.flush()
        creados["rutina"] = 1
    if(datos.RUTINA_AMIGO is not None and bd.query(EjercicioRutina).filter(EjercicioRutina.rutina_id == rutina.id).count() == 0):
        ejercicios = {e.codigo: e for e in bd.query(Ejercicio).filter(Ejercicio.usuario_id == usuario_id, Ejercicio.codigo.isnot(None)).all()}
        for(sesion, filas) in datos.RUTINA_AMIGO["sesiones"].items():
            for(orden, fila) in enumerate(filas):
                bd.add(EjercicioRutina(rutina_id=rutina.id, sesion=sesion, ejercicio_id=ejercicios[fila["ejercicio"]].id, orden=orden, series=fila["series"], rep_min=fila.get("rep_min"), rep_max=fila.get("rep_max"), tiempo=fila.get("tiempo"), por_lado=fila.get("por_lado", False), nota=fila.get("nota")))
                creados["rutina_ejercicios"] = creados["rutina_ejercicios"] + 1
        configuracion = dict(rutina.configuracion or {})
        configuracion["pendiente_documento"] = False
        configuracion["advertencia"] = datos.ADVERTENCIA_AMIGO
        rutina.configuracion = configuracion
    if(bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario_id).count() == 0):
        for(tipo, hora, dias) in (("comida", "14:00", [0, 1, 2, 3, 4, 5, 6]), ("gimnasio", "18:00", [0, 1, 2, 3]), ("compra", "10:00", [6]), ("registro", "21:30", [0, 1, 2, 3, 4, 5, 6])):
            bd.add(Recordatorio(usuario_id=usuario_id, tipo=tipo, hora=hora, dias=dias, activo=False, texto_generico=True))
            creados["recordatorios"] = creados["recordatorios"] + 1
    if(bd.query(Objetivo).filter(Objetivo.usuario_id == usuario_id).count() == 0):
        o = datos.OBJETIVO_AMIGO
        bd.add(Objetivo(usuario_id=usuario_id, vigente_desde=perfil.inicio_plan or hoy, kcal=o["kcal"], proteina_g=o["proteina_g"], hidratos_g=o["hidratos_g"], grasas_g=o["grasas_g"], fibra_g=o["fibra_g"], modo="ganar", origen="documento_plan", provisional=True, detalle={"nota": o["nota"], "fuente": datos.FUENTE_DOCUMENTO}))
        creados["objetivo"] = 1
    bd.commit()
    return creados
