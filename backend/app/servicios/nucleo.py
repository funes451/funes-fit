from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.calculos import compra as calc_compra
from app.calculos import nutricion as calc_nutricion
from app.calculos.fechas import dias_semana, lunes_de
from app.modelos import (
    Alimento,
    ComidaPlanificada,
    Compra,
    Consumo,
    IngredienteReceta,
    ItemDespensa,
    Objetivo,
    Perfil,
    PlanSemana,
    Producto,
    Receta,
)

MOMENTOS = ["desayuno", "comida", "merienda", "cena", "extra"]


def no_encontrado(texto: str = "No encontrado"):
    return HTTPException(status_code=404, detail=texto)


def propio(bd: Session, modelo, identificador: int, usuario_id: int, texto: str = "No encontrado"):
    objeto = bd.get(modelo, identificador)
    if(objeto is None or getattr(objeto, "usuario_id", None) != usuario_id):
        raise no_encontrado(texto)
    return objeto


def alimento_a_dict(a: Alimento) -> dict:
    return {
        "id": a.id,
        "codigo": a.codigo,
        "nombre": a.nombre,
        "base": a.base,
        "unidad_base": calc_nutricion.unidad_base_alimento({"base": a.base}),
        "gramos_unidad": a.gramos_unidad,
        "kcal": a.kcal,
        "proteina": a.proteina,
        "hidratos": a.hidratos,
        "grasas": a.grasas,
        "fibra": a.fibra,
        "origen": a.origen,
        "fuente": a.fuente,
        "estado_peso": a.estado_peso,
        "factor_compra": a.factor_compra,
        "nota_factor": a.nota_factor,
        "densidad": a.densidad,
        "alergenos": a.alergenos or [],
        "seccion": a.seccion,
        "codigo_barras": a.codigo_barras,
    }


def producto_a_dict(p: Producto) -> dict:
    return {
        "id": p.id,
        "alimento_id": p.alimento_id,
        "codigo": p.codigo,
        "nombre": p.nombre,
        "capacidad": p.capacidad,
        "unidad": p.unidad,
        "capacidad_util": p.capacidad_util,
        "nota_capacidad": p.nota_capacidad,
        "formato_verificado": p.formato_verificado,
        "precio": p.precio,
        "precio_origen": p.precio_origen,
        "precio_fecha": p.precio_fecha.isoformat() if p.precio_fecha else None,
        "precio_fuente": p.precio_fuente,
        "tienda": p.tienda,
        "preferido": p.preferido,
    }


class CacheRecetas:
    def __init__(self, bd: Session, usuario_id: int) -> None:
        self.bd = bd
        self.usuario_id = usuario_id
        self.recetas = {}
        self.alimentos = {}

    def alimento(self, alimento_id: int) -> dict:
        if(alimento_id not in self.alimentos):
            fila = self.bd.get(Alimento, alimento_id)
            self.alimentos[alimento_id] = alimento_a_dict(fila)
        return self.alimentos[alimento_id]

    def receta(self, receta_id: int) -> dict:
        if(receta_id in self.recetas):
            return self.recetas[receta_id]
        receta = self.bd.get(Receta, receta_id)
        if(receta is None or receta.usuario_id != self.usuario_id):
            raise no_encontrado("Receta no encontrada")
        filas = self.bd.query(IngredienteReceta).filter(IngredienteReceta.receta_id == receta.id).order_by(IngredienteReceta.orden, IngredienteReceta.id).all()
        ingredientes = [{"id": f.id, "alimento": self.alimento(f.alimento_id), "cantidad": f.cantidad, "unidad": f.unidad, "nota": f.nota} for f in filas]
        calculo = calc_nutricion.nutrientes_receta(ingredientes, receta.raciones)
        alergenos = sorted({al for i in ingredientes for al in i["alimento"]["alergenos"]})
        datos = {
            "id": receta.id,
            "codigo": receta.codigo,
            "nombre": receta.nombre,
            "momento_tipico": receta.momento_tipico,
            "raciones": receta.raciones,
            "tiempo_min": receta.tiempo_min,
            "pasos": receta.pasos or [],
            "conservacion": receta.conservacion,
            "sustituciones": receta.sustituciones or [],
            "notas": receta.notas,
            "favorita": receta.favorita,
            "peso_final_lote": receta.peso_final_lote,
            "modo_preparacion": receta.modo_preparacion,
            "max_nevera_dias": receta.max_nevera_dias,
            "origen": receta.origen,
            "archivada": receta.archivada,
            "ingredientes": [
                {
                    "id": i["id"],
                    "alimento_id": i["alimento"]["id"],
                    "nombre": i["alimento"]["nombre"],
                    "cantidad": i["cantidad"],
                    "unidad": i["unidad"],
                    "estado_peso": i["alimento"]["estado_peso"],
                    "origen": i["alimento"]["origen"],
                    "nota": i["nota"],
                    "valores": d["valores"],
                }
                for i, d in zip(ingredientes, calculo["detalle"])
            ],
            "nutrientes_total": calculo["total"],
            "nutrientes_racion": calculo["racion"],
            "confianza": calculo["confianza"],
            "alergenos": alergenos,
            "_ingredientes_calculo": ingredientes,
        }
        self.recetas[receta_id] = datos
        return datos


def publica(receta: dict) -> dict:
    return {k: v for k, v in receta.items() if not k.startswith("_")}


def perfil_de(bd: Session, usuario_id: int) -> Perfil:
    perfil = bd.get(Perfil, usuario_id)
    if(perfil is None):
        perfil = Perfil(usuario_id=usuario_id, nombre="", horarios={}, alimentos_excluidos=list(calc_nutricion.EXCLUIDOS_POR_DEFECTO))
        bd.add(perfil)
        bd.commit()
    return perfil


def objetivo_vigente(bd: Session, usuario_id: int, fecha: date) -> Objetivo | None:
    return bd.query(Objetivo).filter(Objetivo.usuario_id == usuario_id, Objetivo.vigente_desde <= fecha).order_by(Objetivo.vigente_desde.desc(), Objetivo.id.desc()).first()


def objetivo_a_dict(o: Objetivo | None) -> dict | None:
    if(o is None):
        return None
    return {
        "id": o.id,
        "vigente_desde": o.vigente_desde.isoformat(),
        "kcal": o.kcal,
        "proteina_g": o.proteina_g,
        "hidratos_g": o.hidratos_g,
        "grasas_g": o.grasas_g,
        "fibra_g": o.fibra_g,
        "modo": o.modo,
        "origen": o.origen,
        "provisional": o.provisional,
        "detalle": o.detalle or {},
    }


def comida_a_dict(cache: CacheRecetas, comida: ComidaPlanificada) -> dict:
    receta = cache.receta(comida.receta_id)
    return {
        "id": comida.id,
        "plan_id": comida.plan_id,
        "fecha": comida.fecha.isoformat(),
        "momento": comida.momento,
        "hora": comida.hora,
        "factor": comida.factor,
        "orden": comida.orden,
        "opcional": comida.opcional,
        "receta_id": receta["id"],
        "receta_codigo": receta["codigo"],
        "receta_nombre": receta["nombre"],
        "nutrientes": calc_nutricion.escalar(receta["nutrientes_racion"], comida.factor),
        "confianza": receta["confianza"],
        "alergenos": receta["alergenos"],
    }


def consumo_a_dict(c: Consumo) -> dict:
    return {
        "id": c.id,
        "id_cliente": c.id_cliente,
        "comida_planificada_id": c.comida_planificada_id,
        "fecha": c.fecha.isoformat(),
        "momento": c.momento,
        "tipo": c.tipo,
        "descripcion": c.descripcion,
        "nutrientes": {"kcal": c.kcal, "proteina": c.proteina, "hidratos": c.hidratos, "grasas": c.grasas, "fibra": c.fibra},
        "instantanea": c.instantanea or {},
        "version": c.version,
        "creado_en": c.creado_en.isoformat() if c.creado_en else None,
    }


def plan_de_fecha(bd: Session, usuario_id: int, fecha: date) -> PlanSemana | None:
    return bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario_id, PlanSemana.lunes == lunes_de(fecha)).first()


def resumen_dia(bd: Session, usuario_id: int, fecha: date, cache: CacheRecetas | None = None) -> dict:
    cache = cache or CacheRecetas(bd, usuario_id)
    comidas = bd.query(ComidaPlanificada).filter(ComidaPlanificada.usuario_id == usuario_id, ComidaPlanificada.fecha == fecha).order_by(ComidaPlanificada.orden, ComidaPlanificada.id).all()
    consumos = bd.query(Consumo).filter(Consumo.usuario_id == usuario_id, Consumo.fecha == fecha, Consumo.borrado == False).order_by(Consumo.id).all()
    lista_comidas = []
    registradas = 0
    for(comida) in comidas:
        datos = comida_a_dict(cache, comida)
        asociados = [consumo_a_dict(c) for c in consumos if c.comida_planificada_id == comida.id]
        datos["consumos"] = asociados
        datos["estado"] = estado_comida(asociados)
        if(datos["estado"] != "pendiente" and not comida.opcional):
            registradas = registradas + 1
        lista_comidas.append(datos)
    extras = [consumo_a_dict(c) for c in consumos if c.comida_planificada_id is None]
    obligatorias = [c for c in lista_comidas if not c["opcional"]]
    planificado = calc_nutricion.sumar_nutrientes([c["nutrientes"] for c in obligatorias])
    con_opcionales = calc_nutricion.sumar_nutrientes([c["nutrientes"] for c in lista_comidas])
    consumido = calc_nutricion.sumar_nutrientes([c["nutrientes"] for c in [consumo_a_dict(x) for x in consumos]])
    objetivo = objetivo_vigente(bd, usuario_id, fecha)
    return {
        "fecha": fecha.isoformat(),
        "comidas": lista_comidas,
        "extras": extras,
        "planificado": planificado,
        "planificado_con_opcionales": con_opcionales if len(obligatorias) != len(lista_comidas) else None,
        "consumido_registrado": consumido if len(consumos) > 0 else None,
        "comidas_registradas": registradas,
        "comidas_pendientes": len(obligatorias) - registradas,
        "registro_completo": len(obligatorias) > 0 and registradas == len(obligatorias),
        "objetivo": objetivo_a_dict(objetivo),
        "aviso_registro": None if registradas == len(obligatorias) else "Las comidas sin registrar no cuentan como cero: el total consumido solo incluye lo registrado.",
    }


def estado_comida(consumos: list[dict]) -> str:
    if(len(consumos) == 0):
        return "pendiente"
    tipos = {c["tipo"] for c in consumos}
    if("previsto" in tipos):
        return "comido_previsto"
    if("diferente" in tipos):
        return "comido_diferente"
    if("parcial" in tipos):
        return "parcial"
    if("modificado" in tipos):
        return "modificado"
    return "registrado"


def comensales(perfil: Perfil) -> int:
    return max(1, perfil.comensales or 1)


def necesidades_plan(bd: Session, usuario_id: int, plan: PlanSemana, numero_comensales: int, cache: CacheRecetas | None = None) -> dict:
    cache = cache or CacheRecetas(bd, usuario_id)
    comidas = bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan.id).all()
    lineas = []
    for(comida) in comidas:
        receta = cache.receta(comida.receta_id)
        proporcion = comida.factor / receta["raciones"] * numero_comensales
        for(ingrediente) in receta["_ingredientes_calculo"]:
            alimento = ingrediente["alimento"]
            cantidad = calc_nutricion.a_unidad_base(ingrediente["cantidad"], ingrediente["unidad"], alimento) * proporcion
            lineas.append({"alimento": alimento, "cantidad": cantidad, "uso": f"{comida.fecha.strftime('%d/%m')} {comida.momento}{' (opcional)' if comida.opcional else ''}: {receta['nombre']}"})
    return calc_compra.sumar_necesidades(lineas)


def productos_preferidos(bd: Session, usuario_id: int) -> dict:
    resultado = {}
    for(p) in bd.query(Producto).filter(Producto.usuario_id == usuario_id).order_by(Producto.preferido.desc(), Producto.id).all():
        if(p.alimento_id not in resultado):
            resultado[p.alimento_id] = producto_a_dict(p)
    return resultado


def despensa_de(bd: Session, usuario_id: int) -> dict:
    return {d.alimento_id: d.cantidad for d in bd.query(ItemDespensa).filter(ItemDespensa.usuario_id == usuario_id).all()}


def comprado_en_plan(bd: Session, usuario_id: int, plan_id: int) -> dict:
    resultado = {}
    for(c) in bd.query(Compra).filter(Compra.usuario_id == usuario_id, Compra.plan_id == plan_id, Compra.anulada == False).all():
        resultado[c.alimento_id] = resultado.get(c.alimento_id, 0.0) + c.cantidad_util
    return resultado


def lista_compra_plan(bd: Session, usuario_id: int, plan: PlanSemana) -> dict:
    perfil = perfil_de(bd, usuario_id)
    necesidades = necesidades_plan(bd, usuario_id, plan, comensales(perfil))
    lista = calc_compra.calcular_lista(necesidades, despensa_de(bd, usuario_id), productos_preferidos(bd, usuario_id), comprado_en_plan(bd, usuario_id, plan.id))
    gastado = 0.0
    sin_precio_gastado = 0
    for(c) in bd.query(Compra).filter(Compra.usuario_id == usuario_id, Compra.plan_id == plan.id, Compra.anulada == False).all():
        if(c.precio_unitario is None):
            sin_precio_gastado = sin_precio_gastado + 1
        else:
            gastado = gastado + c.precio_unitario * c.envases
    lista["totales"]["desembolso_realizado_conocido"] = gastado
    lista["totales"]["compras_sin_precio"] = sin_precio_gastado
    lista["presupuesto"] = calc_compra.comparar_presupuesto(lista["totales"], perfil.presupuesto_semanal, perfil.presupuesto_confirmado)
    lista["presupuesto"]["importe"] = perfil.presupuesto_semanal
    lista["presupuesto"]["confirmado"] = perfil.presupuesto_confirmado
    anterior = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario_id, PlanSemana.lunes == plan.lunes - timedelta(days=7)).first()
    lista["aviso_semana_anterior"] = None
    if(anterior is not None and not anterior.cerrada):
        lista["aviso_semana_anterior"] = "La semana anterior no está cerrada: la despensa puede incluir comida que ya se consumió."
    lista["plan"] = {"id": plan.id, "lunes": plan.lunes.isoformat(), "version": plan.version, "cerrada": plan.cerrada}
    lista["comensales"] = comensales(perfil)
    return lista


def semana_plan(bd: Session, usuario_id: int, plan: PlanSemana) -> dict:
    cache = CacheRecetas(bd, usuario_id)
    dias = []
    for(fecha) in dias_semana(plan.lunes):
        dias.append(resumen_dia(bd, usuario_id, fecha, cache))
    medias = calc_nutricion.sumar_nutrientes([d["planificado"] for d in dias])
    return {
        "plan": {"id": plan.id, "lunes": plan.lunes.isoformat(), "version": plan.version, "origen": plan.origen, "repite_de": plan.repite_de, "cerrada": plan.cerrada},
        "dias": dias,
        "media_diaria_planificada": calc_nutricion.escalar(medias, 1 / 7),
    }
