import re
import unicodedata

NUTRIENTES = ["kcal", "proteina", "hidratos", "grasas", "fibra"]
EXCLUIDOS_POR_DEFECTO = ["puré", "calabacín", "morcilla"]

FACTORES_UNIDAD = {"g": ("g", 1.0), "kg": ("g", 1000.0), "ml": ("ml", 1.0), "l": ("ml", 1000.0), "ud": ("ud", 1.0)}


def normalizar_texto(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def contiene_excluido(texto: str, excluidos: list[str] | None = None) -> str | None:
    lista = excluidos if excluidos is not None else EXCLUIDOS_POR_DEFECTO
    normal = normalizar_texto(texto)
    for(palabra) in lista:
        clave = re.escape(normalizar_texto(palabra).strip())
        if(clave == ""):
            continue
        if(re.search(r"\b" + clave + r"(s|es)?\b", normal)):
            return palabra
    return None


def unidad_base_alimento(alimento: dict) -> str:
    if(alimento["base"] == "100ml"):
        return "ml"
    if(alimento["base"] == "unidad"):
        return "ud"
    return "g"


def a_unidad_base(cantidad: float, unidad: str, alimento: dict) -> float:
    if(unidad not in FACTORES_UNIDAD):
        raise ValueError(f"Unidad desconocida: {unidad}")
    destino = unidad_base_alimento(alimento)
    tipo, factor = FACTORES_UNIDAD[unidad]
    valor = cantidad * factor
    if(tipo == destino):
        return valor
    densidad = alimento.get("densidad")
    if(tipo == "ml" and destino == "g" and densidad):
        return valor * densidad
    if(tipo == "g" and destino == "ml" and densidad):
        return valor / densidad
    gramos_unidad = alimento.get("gramos_unidad")
    if(tipo == "ud" and destino == "g" and gramos_unidad):
        return valor * gramos_unidad
    if(tipo == "g" and destino == "ud" and gramos_unidad):
        return valor / gramos_unidad
    raise ValueError(f"No se puede convertir {unidad} a {destino} para {alimento.get('nombre', 'el alimento')} sin densidad o peso por unidad")


def nutrientes_cantidad(alimento: dict, cantidad: float, unidad: str) -> dict:
    cantidad_base = a_unidad_base(cantidad, unidad, alimento)
    divisor = 1.0 if alimento["base"] == "unidad" else 100.0
    proporcion = cantidad_base / divisor
    resultado = {}
    for(nutriente) in NUTRIENTES:
        valor = alimento.get(nutriente)
        resultado[nutriente] = None if valor is None else valor * proporcion
    return resultado


def sumar_nutrientes(lista: list[dict]) -> dict:
    total = {nutriente: 0.0 for nutriente in NUTRIENTES}
    faltan_fibra = 0
    for(elemento) in lista:
        for(nutriente) in NUTRIENTES:
            valor = elemento.get(nutriente)
            if(valor is None):
                if(nutriente == "fibra"):
                    faltan_fibra = faltan_fibra + 1
                continue
            total[nutriente] = total[nutriente] + valor
    if(faltan_fibra > 0 or len(lista) == 0):
        total["fibra"] = None
    total["fibra_faltan"] = faltan_fibra
    return total


def escalar(nutrientes: dict, factor: float) -> dict:
    resultado = {}
    for(clave, valor) in nutrientes.items():
        if(clave in NUTRIENTES):
            resultado[clave] = None if valor is None else valor * factor
        else:
            resultado[clave] = valor
    return resultado


def nutrientes_receta(ingredientes: list[dict], raciones: float) -> dict:
    partes = []
    detalle = []
    for(ingrediente) in ingredientes:
        valores = nutrientes_cantidad(ingrediente["alimento"], ingrediente["cantidad"], ingrediente["unidad"])
        partes.append(valores)
        detalle.append({
            "alimento_id": ingrediente["alimento"].get("id"),
            "nombre": ingrediente["alimento"]["nombre"],
            "cantidad": ingrediente["cantidad"],
            "unidad": ingrediente["unidad"],
            "estado_peso": ingrediente["alimento"].get("estado_peso"),
            "origen": ingrediente["alimento"].get("origen"),
            "valores": valores,
        })
    total = sumar_nutrientes(partes)
    racion = escalar(total, 1.0 / raciones) if raciones > 0 else total
    origenes = sorted({i["alimento"].get("origen", "generico") for i in ingredientes})
    return {"total": total, "racion": racion, "detalle": detalle, "origenes": origenes, "confianza": confianza(origenes)}


def nutrientes_porcion_lote(total_receta: dict, peso_final_lote: float, porcion_servida: float) -> dict:
    if(peso_final_lote <= 0):
        raise ValueError("El peso final del lote debe ser mayor que cero")
    if(porcion_servida <= 0):
        raise ValueError("La porción servida debe ser mayor que cero")
    return escalar(total_receta, porcion_servida / peso_final_lote)


def confianza(origenes: list[str]) -> str:
    if(len(origenes) == 0):
        return "sin_datos"
    if(all(o == "etiqueta" for o in origenes)):
        return "etiqueta_verificada"
    if("manual" in origenes):
        return "incluye_estimacion_manual"
    return "base_generica"


def instantanea_consumo(alimentos_usados: list[dict], cantidades: list[dict], nutrientes: dict) -> dict:
    return {
        "ingredientes": [
            {
                "alimento_id": a.get("id"),
                "nombre": a["nombre"],
                "base": a["base"],
                "por_base": {n: a.get(n) for n in NUTRIENTES},
                "origen": a.get("origen"),
                "cantidad": c["cantidad"],
                "unidad": c["unidad"],
            }
            for a, c in zip(alimentos_usados, cantidades)
        ],
        "nutrientes": nutrientes,
    }
