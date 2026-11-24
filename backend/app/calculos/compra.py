import math

ORDEN_SECCIONES = [
    "Fruta y verdura",
    "Carne y pescado",
    "Congelados",
    "Lácteos y huevos",
    "Panadería",
    "Despensa seca",
    "Legumbres y conservas",
    "Aceites y frutos secos",
    "Otros",
]

ORIGENES_PRECIO_CONFIRMADOS = ("ticket", "manual", "catalogo")
EPSILON = 1e-9


def sumar_necesidades(lineas: list[dict]) -> dict:
    resultado = {}
    for(linea) in lineas:
        alimento = linea["alimento"]
        clave = alimento["id"]
        if(clave not in resultado):
            resultado[clave] = {"alimento": alimento, "cantidad": 0.0, "usos": []}
        resultado[clave]["cantidad"] = resultado[clave]["cantidad"] + linea["cantidad"]
        if(linea.get("uso")):
            resultado[clave]["usos"].append(linea["uso"])
    return resultado


def calcular_linea(alimento: dict, necesidad_neta: float, despensa: float, producto: dict | None, comprado_semana: float) -> dict:
    factor = alimento.get("factor_compra") or 1.0
    necesidad_compra = necesidad_neta * factor
    disponible = max(0.0, despensa)
    uso_despensa = min(disponible, necesidad_compra)
    falta = max(0.0, necesidad_compra - disponible)
    linea = {
        "alimento_id": alimento["id"],
        "nombre": alimento["nombre"],
        "seccion": alimento.get("seccion") or "Otros",
        "unidad": alimento.get("unidad_base", "g"),
        "estado_peso": alimento.get("estado_peso"),
        "factor_compra": factor,
        "nota_factor": alimento.get("nota_factor"),
        "necesidad_neta": necesidad_neta,
        "necesidad_compra": necesidad_compra,
        "despensa": disponible,
        "uso_despensa": uso_despensa,
        "falta": falta,
        "comprado_semana": comprado_semana,
        "producto": None,
        "envases": None,
        "cantidad_a_comprar": None,
        "sobrante": None,
        "coste_consumido": None,
        "desembolso": None,
        "precio_estado": "sin_producto",
    }
    if(falta <= EPSILON):
        linea["estado"] = "comprado" if comprado_semana > EPSILON else "en_despensa"
        linea["envases"] = 0
        linea["cantidad_a_comprar"] = 0.0
        linea["sobrante"] = disponible - necesidad_compra
        linea["desembolso"] = 0.0
    else:
        linea["estado"] = "pendiente"
    if(producto is None):
        if(linea["estado"] == "pendiente"):
            linea["cantidad_a_comprar"] = falta
            linea["sobrante"] = 0.0
        return linea
    capacidad = producto["capacidad_util"]
    linea["producto"] = {
        "id": producto["id"],
        "nombre": producto["nombre"],
        "capacidad": producto["capacidad"],
        "unidad": producto["unidad"],
        "capacidad_util": capacidad,
        "formato_verificado": producto.get("formato_verificado", False),
        "precio": producto.get("precio"),
        "precio_origen": producto.get("precio_origen", "desconocido"),
        "precio_fecha": producto.get("precio_fecha"),
        "precio_fuente": producto.get("precio_fuente"),
        "tienda": producto.get("tienda"),
    }
    if(linea["estado"] == "pendiente"):
        envases = math.ceil(falta / capacidad - EPSILON)
        linea["envases"] = envases
        linea["cantidad_a_comprar"] = envases * capacidad
        linea["sobrante"] = disponible + envases * capacidad - necesidad_compra
    precio = producto.get("precio")
    if(precio is None):
        linea["precio_estado"] = "desconocido"
        if(linea["estado"] != "pendiente"):
            linea["desembolso"] = 0.0
        else:
            linea["desembolso"] = None
        return linea
    linea["precio_estado"] = "confirmado" if producto.get("precio_origen") in ORIGENES_PRECIO_CONFIRMADOS else "estimado"
    linea["coste_consumido"] = necesidad_compra / capacidad * precio
    linea["desembolso"] = (linea["envases"] or 0) * precio
    return linea


def calcular_lista(necesidades: dict, despensa: dict, productos: dict, comprado: dict) -> dict:
    lineas = []
    for(alimento_id, datos) in necesidades.items():
        linea = calcular_linea(
            datos["alimento"],
            datos["cantidad"],
            despensa.get(alimento_id, 0.0),
            productos.get(alimento_id),
            comprado.get(alimento_id, 0.0),
        )
        linea["usos"] = datos.get("usos", [])
        lineas.append(linea)
    lineas.sort(key=lambda l: (ORDEN_SECCIONES.index(l["seccion"]) if l["seccion"] in ORDEN_SECCIONES else len(ORDEN_SECCIONES), l["nombre"]))
    secciones = []
    for(linea) in lineas:
        if(len(secciones) == 0 or secciones[-1]["nombre"] != linea["seccion"]):
            secciones.append({"nombre": linea["seccion"], "lineas": []})
        secciones[-1]["lineas"].append(linea)
    return {"secciones": secciones, "lineas": lineas, "totales": totales(lineas)}


def totales(lineas: list[dict]) -> dict:
    coste_consumido = 0.0
    desembolso_pendiente = 0.0
    sin_precio_consumo = []
    sin_precio_compra = []
    estimados = 0
    for(linea) in lineas:
        if(linea["coste_consumido"] is None):
            sin_precio_consumo.append(linea["nombre"])
        else:
            coste_consumido = coste_consumido + linea["coste_consumido"]
            if(linea["precio_estado"] == "estimado"):
                estimados = estimados + 1
        if(linea["estado"] == "pendiente"):
            if(linea["desembolso"] is None):
                sin_precio_compra.append(linea["nombre"])
            else:
                desembolso_pendiente = desembolso_pendiente + linea["desembolso"]
    if(len(sin_precio_consumo) > 0 or len(sin_precio_compra) > 0):
        estado = "parcial"
    elif(estimados > 0):
        estado = "con_estimaciones"
    else:
        estado = "completo"
    return {
        "coste_consumido_conocido": coste_consumido,
        "desembolso_pendiente_conocido": desembolso_pendiente,
        "sin_precio_consumo": sin_precio_consumo,
        "sin_precio_compra": sin_precio_compra,
        "lineas_con_precio_estimado": estimados,
        "estado": estado,
        "aviso": aviso_totales(estado, len(set(sin_precio_consumo) | set(sin_precio_compra))),
    }


def aviso_totales(estado: str, faltan: int) -> str:
    if(estado == "parcial"):
        return f"Total parcial: {faltan} productos sin precio no se cuentan. No es el coste real de la compra."
    if(estado == "con_estimaciones"):
        return "Incluye precios orientativos no confirmados en tu tienda."
    return "Todos los precios vienen de ticket, catálogo o introducción manual."


def comparar_presupuesto(total: dict, presupuesto: float | None, confirmado: bool) -> dict:
    if(presupuesto is None):
        return {"estado": "sin_presupuesto"}
    if(total["estado"] == "parcial"):
        return {"estado": "no_comparable", "mensaje": "Faltan precios: no se puede saber si la compra cabe en el presupuesto."}
    gasto = total["desembolso_pendiente_conocido"]
    etiqueta = "presupuesto confirmado" if confirmado else "presupuesto provisional de planificación"
    if(gasto <= presupuesto):
        return {"estado": "dentro", "mensaje": f"Dentro del {etiqueta} según los precios disponibles."}
    return {"estado": "fuera", "mensaje": f"Supera el {etiqueta} según los precios disponibles."}
