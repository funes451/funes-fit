NIVELES_ACTIVIDAD = {
    "sedentario": {"etiqueta": "Sedentario: trabajo sentado, pocos pasos", "minimo": 1.20, "maximo": 1.30},
    "ligero": {"etiqueta": "Ligero: algo de movimiento diario", "minimo": 1.30, "maximo": 1.40},
    "ligero_moderado": {"etiqueta": "Ligero-moderado: entreno + movimiento diario moderado", "minimo": 1.35, "maximo": 1.50},
    "moderado": {"etiqueta": "Moderado: trabajo activo o muchos pasos", "minimo": 1.50, "maximo": 1.65},
    "alto": {"etiqueta": "Alto: trabajo físico y entreno exigente", "minimo": 1.65, "maximo": 1.80},
}

DEFICIT_MINIMO_KCAL = 300
DEFICIT_MAXIMO_KCAL = 500
DEFICIT_MINIMO_PCT = 0.10
DEFICIT_MAXIMO_PCT = 0.20


def mifflin_st_jeor(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> float:
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    if(sexo == "masculino"):
        return base + 5
    if(sexo == "femenino"):
        return base - 161
    raise ValueError("El sexo para la fórmula debe ser 'masculino' o 'femenino'")


def reposo_por_sexo(peso_kg: float, altura_cm: float, edad: int) -> dict:
    return {
        "masculino": mifflin_st_jeor(peso_kg, altura_cm, edad, "masculino"),
        "femenino": mifflin_st_jeor(peso_kg, altura_cm, edad, "femenino"),
    }


def gasto_estimado(reposo: float, nivel: str) -> dict:
    if(nivel not in NIVELES_ACTIVIDAD):
        raise ValueError(f"Nivel de actividad desconocido: {nivel}")
    datos = NIVELES_ACTIVIDAD[nivel]
    factor_central = (datos["minimo"] + datos["maximo"]) / 2
    return {
        "nivel": nivel,
        "etiqueta": datos["etiqueta"],
        "factor_minimo": datos["minimo"],
        "factor_maximo": datos["maximo"],
        "factor_central": factor_central,
        "minimo": reposo * datos["minimo"],
        "maximo": reposo * datos["maximo"],
        "central": reposo * factor_central,
    }


def deficit_moderado(gasto: float) -> dict:
    minimo = max(DEFICIT_MINIMO_KCAL, gasto * DEFICIT_MINIMO_PCT)
    maximo = min(DEFICIT_MAXIMO_KCAL, gasto * DEFICIT_MAXIMO_PCT)
    if(minimo > maximo):
        minimo = maximo
    return {"minimo": minimo, "maximo": maximo, "central": (minimo + maximo) / 2}


def proponer_objetivo(reposo: float, gasto: dict) -> dict:
    deficit = deficit_moderado(gasto["central"])
    objetivo = gasto["central"] - deficit["central"]
    suelo = reposo
    limitado = False
    if(objetivo < suelo):
        objetivo = suelo
        limitado = True
    objetivo = round(objetivo / 10) * 10
    return {
        "kcal": objetivo,
        "deficit_central": gasto["central"] - objetivo,
        "deficit_rango": [gasto["minimo"] - objetivo, gasto["maximo"] - objetivo],
        "limitado_por_reposo": limitado,
        "explicacion": "Gasto central menos un déficit moderado (300–500 kcal y 10–20 % del gasto). El rango de déficit refleja la incertidumbre del factor de actividad.",
    }


def evaluar_plantilla(kcal_plantilla: float, gasto: dict) -> dict:
    deficit_desde = gasto["minimo"] - kcal_plantilla
    deficit_hasta = gasto["maximo"] - kcal_plantilla
    moderado = deficit_moderado(gasto["central"])
    deficit_central = gasto["central"] - kcal_plantilla
    if(deficit_central > moderado["maximo"]):
        estado = "excede_deficit_moderado"
        mensaje = "Con esta estimación la plantilla queda por debajo del déficit moderado elegido: conviene aumentar raciones antes de activarla."
    elif(deficit_central < moderado["minimo"]):
        estado = "deficit_bajo"
        mensaje = "Con esta estimación la plantilla produce poco déficit o ninguno: se puede reducir alguna ración o mantenerla y revisar con la evolución."
    else:
        estado = "dentro_de_rango"
        mensaje = "La plantilla queda dentro de un déficit moderado según esta estimación."
    return {
        "kcal_plantilla": kcal_plantilla,
        "deficit_rango": [deficit_desde, deficit_hasta],
        "deficit_central": deficit_central,
        "estado": estado,
        "mensaje": mensaje,
    }


def resumen_energia(peso_kg: float | None, altura_cm: float | None, edad: int | None, sexo: str | None, nivel: str | None, kcal_plantilla: float | None) -> dict:
    if(peso_kg is None or altura_cm is None or edad is None):
        return {"completo": False, "faltan": ["peso, altura o edad"], "aviso": "Faltan datos básicos para estimar el metabolismo en reposo."}
    reposos = reposo_por_sexo(peso_kg, altura_cm, edad)
    faltan = []
    if(sexo is None):
        faltan.append("sexo usado en la fórmula")
    if(nivel is None):
        faltan.append("actividad fuera del gimnasio y pasos habituales")
    resultado = {
        "completo": len(faltan) == 0,
        "faltan": faltan,
        "formula": "Mifflin–St Jeor: 10 × kg + 6,25 × cm − 5 × edad + 5 (masculina) o − 161 (femenina)",
        "reposo_por_sexo": reposos,
        "aviso": "El metabolismo en reposo no es el gasto total diario ni una cantidad que haya que comer. El factor de actividad es una hipótesis, no una medida.",
    }
    if(sexo is not None):
        reposo = reposos[sexo]
        resultado["reposo"] = reposo
        if(nivel is not None):
            gasto = gasto_estimado(reposo, nivel)
            resultado["gasto"] = gasto
            resultado["propuesta"] = proponer_objetivo(reposo, gasto)
            if(kcal_plantilla is not None):
                resultado["plantilla"] = evaluar_plantilla(kcal_plantilla, gasto)
    return resultado
