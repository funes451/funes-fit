from datetime import date, timedelta

MEDIDAS_MINIMAS_SEMANA = 3
SEMANAS_MINIMAS_REVISION = 2
PASO_MINIMO_KCAL = 100
PASO_MAXIMO_KCAL = 150
PERDIDA_REFERENCIA_MIN = 0.25
PERDIDA_REFERENCIA_MAX = 0.75
PERDIDA_RAPIDA = 1.0


def lunes(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def medias_semanales(mediciones: list[dict]) -> list[dict]:
    grupos = {}
    for(m) in mediciones:
        clave = lunes(m["fecha"])
        if(clave not in grupos):
            grupos[clave] = []
        grupos[clave].append(m["valor"])
    resultado = []
    for(clave) in sorted(grupos.keys()):
        valores = grupos[clave]
        valida = len(valores) >= MEDIDAS_MINIMAS_SEMANA
        resultado.append({
            "lunes": clave,
            "medidas": len(valores),
            "media": sum(valores) / len(valores) if valida else None,
            "valida": valida,
            "aviso": None if valida else f"Solo {len(valores)} medida(s): hacen falta al menos {MEDIDAS_MINIMAS_SEMANA} para una media semanal.",
        })
    return resultado


def cambios_semanales(semanas: list[dict]) -> list[dict]:
    validas = [s for s in semanas if s["valida"]]
    cambios = []
    for(i) in range(1, len(validas)):
        anterior = validas[i - 1]
        actual = validas[i]
        semanas_entre = (actual["lunes"] - anterior["lunes"]).days / 7
        if(semanas_entre <= 0):
            continue
        diferencia = actual["media"] - anterior["media"]
        porcentaje = diferencia / anterior["media"] * 100 / semanas_entre
        cambios.append({
            "desde": anterior["lunes"],
            "hasta": actual["lunes"],
            "kg": diferencia,
            "pct_semanal": porcentaje,
            "semanas_entre": semanas_entre,
        })
    return cambios


def propuesta_ajuste(semanas: list[dict], kcal_actual: float | None, suelo_kcal: float | None, alertas: dict, adherencia: float | None, ultimo_cambio: date | None, hoy: date, modo: str = "perder") -> dict:
    if(modo == "ganar"):
        return propuesta_ganar(semanas, kcal_actual, alertas, adherencia, ultimo_cambio, hoy)
    if(modo == "mantener"):
        return propuesta_mantener(semanas, kcal_actual, alertas, ultimo_cambio, hoy)
    return propuesta_perder(semanas, kcal_actual, suelo_kcal, alertas, adherencia, ultimo_cambio, hoy)


def _comprobaciones_comunes(semanas: list[dict], kcal_actual: float | None, alertas: dict, ultimo_cambio: date | None, hoy: date, texto_alerta: str) -> dict | None:
    activas = [clave for clave, valor in (alertas or {}).items() if valor]
    if(len(activas) > 0):
        return {"accion": "detener", "motivo": activas, "mensaje": texto_alerta}
    if(kcal_actual is None):
        return {"accion": "esperar", "mensaje": "Todavía no hay un objetivo calórico confirmado."}
    if(ultimo_cambio is not None and (hoy - ultimo_cambio).days < 14):
        return {"accion": "esperar", "mensaje": "El último cambio es reciente: espera al menos dos semanas antes de revisar."}
    if(len(cambios_semanales(semanas)) < SEMANAS_MINIMAS_REVISION):
        return {"accion": "esperar", "mensaje": f"Hacen falta al menos {SEMANAS_MINIMAS_REVISION + 1} semanas con {MEDIDAS_MINIMAS_SEMANA} pesajes o más para revisar. Una medición aislada no cambia nada."}
    return None


def propuesta_ganar(semanas: list[dict], kcal_actual: float | None, alertas: dict, adherencia: float | None, ultimo_cambio: date | None, hoy: date) -> dict:
    bloqueo = _comprobaciones_comunes(semanas, kcal_actual, alertas, ultimo_cambio, hoy, "Has registrado señales como mareos, fatiga marcada o caída de rendimiento. No se proponen cambios automáticos: si persisten, consulta con un profesional sanitario.")
    if(bloqueo is not None):
        return bloqueo
    recientes = cambios_semanales(semanas)[-3:]
    kg_semana = [c["kg"] / c["semanas_entre"] for c in recientes]
    media = sum(kg_semana) / len(kg_semana)
    base = {"kg_semana_media": media, "semanas_analizadas": len(recientes), "referencia": "Subida orientativa de 0,15–0,30 kg por semana; no toda la subida es masa muscular."}
    if(len(kg_semana) >= 2 and all(k > 0.5 for k in kg_semana[-2:])):
        return {**base, "accion": "proponer_bajada", "delta_kcal": -150, "kcal_propuesta": kcal_actual - 150, "requiere_aceptacion": True, "mensaje": f"Subida sostenida de unos {media:.2f} kg por semana, por encima de 0,5 kg: se puede considerar bajar 150 kcal/día. Tú decides."}
    if(media < 0.1):
        if(adherencia is not None and adherencia < 0.8):
            return {**base, "accion": "mantener", "mensaje": "El peso apenas sube, pero el registro indica que el plan no se siguió de forma estable. Antes de subir calorías revisa cumplimiento, apetito y horarios."}
        return {**base, "accion": "proponer_subida", "delta_kcal": 150, "kcal_propuesta": kcal_actual + 150, "requiere_aceptacion": True, "mensaje": f"El peso no sube o apenas sube ({media:.2f} kg/semana): se propone subir 150 kcal/día. Revisa también apetito, rendimiento y recuperación antes de aceptar."}
    return {**base, "accion": "mantener", "mensaje": f"Subida de unos {media:.2f} kg por semana: se mantiene el objetivo."}


def propuesta_mantener(semanas: list[dict], kcal_actual: float | None, alertas: dict, ultimo_cambio: date | None, hoy: date) -> dict:
    bloqueo = _comprobaciones_comunes(semanas, kcal_actual, alertas, ultimo_cambio, hoy, "Has registrado señales de alerta: no se proponen cambios. Consulta con un profesional si persisten.")
    if(bloqueo is not None):
        return bloqueo
    recientes = cambios_semanales(semanas)[-3:]
    media_pct = sum(c["pct_semanal"] for c in recientes) / len(recientes)
    base = {"pct_semanal_medio": media_pct, "semanas_analizadas": len(recientes)}
    if(media_pct > 0.25):
        return {**base, "accion": "proponer_bajada", "delta_kcal": -100, "kcal_propuesta": kcal_actual - 100, "requiere_aceptacion": True, "mensaje": "El peso sube de forma sostenida: se propone bajar 100 kcal/día para mantener."}
    if(media_pct < -0.25):
        return {**base, "accion": "proponer_subida", "delta_kcal": 100, "kcal_propuesta": kcal_actual + 100, "requiere_aceptacion": True, "mensaje": "El peso baja de forma sostenida: se propone subir 100 kcal/día para mantener."}
    return {**base, "accion": "mantener", "mensaje": "El peso se mantiene estable."}


def propuesta_perder(semanas: list[dict], kcal_actual: float | None, suelo_kcal: float | None, alertas: dict, adherencia: float | None, ultimo_cambio: date | None, hoy: date) -> dict:
    activas = [clave for clave, valor in (alertas or {}).items() if valor]
    if(len(activas) > 0):
        return {
            "accion": "detener",
            "motivo": activas,
            "mensaje": "Has registrado señales como mareos, fatiga marcada, caída de rendimiento o pérdida muy rápida. No se proponen bajadas de calorías. Consulta con un médico o dietista-nutricionista.",
        }
    if(kcal_actual is None):
        return {"accion": "esperar", "mensaje": "Todavía no hay un objetivo calórico confirmado."}
    if(ultimo_cambio is not None and (hoy - ultimo_cambio).days < 14):
        return {"accion": "esperar", "mensaje": "El último cambio es reciente: espera al menos dos semanas antes de revisar."}
    cambios = cambios_semanales(semanas)
    if(len(cambios) < SEMANAS_MINIMAS_REVISION):
        return {
            "accion": "esperar",
            "mensaje": f"Hacen falta al menos {SEMANAS_MINIMAS_REVISION + 1} semanas con {MEDIDAS_MINIMAS_SEMANA} pesajes o más para revisar. Una semana sin bajada no justifica recortar.",
        }
    recientes = cambios[-3:]
    media_pct = sum(c["pct_semanal"] for c in recientes) / len(recientes)
    perdida = -media_pct
    base = {"perdida_media_pct": perdida, "semanas_analizadas": len(recientes)}
    if(perdida > PERDIDA_RAPIDA):
        return {
            **base,
            "accion": "proponer_subida",
            "delta_kcal": PASO_MAXIMO_KCAL,
            "kcal_propuesta": kcal_actual + PASO_MAXIMO_KCAL,
            "requiere_aceptacion": True,
            "mensaje": f"Pérdida media del {perdida:.2f} % semanal, más rápida de lo razonable: se propone subir {PASO_MAXIMO_KCAL} kcal. Si hay mareos o fatiga, consulta con un profesional.",
        }
    if(perdida >= PERDIDA_REFERENCIA_MIN):
        return {**base, "accion": "mantener", "mensaje": f"Pérdida media del {perdida:.2f} % semanal, dentro de la referencia orientativa. Sin cambios."}
    if(adherencia is not None and adherencia < 0.8):
        return {**base, "accion": "mantener", "mensaje": "La tendencia es plana, pero el registro de comidas indica que el plan no se siguió de forma estable. Antes de recortar, revisa adherencia, hambre y sueño."}
    if(suelo_kcal is not None and kcal_actual - PASO_MINIMO_KCAL < suelo_kcal):
        return {**base, "accion": "no_bajar", "mensaje": "El objetivo ya está cerca del límite inferior que usa la app. No se propone bajar más: revisa actividad, pasos y adherencia, o consulta con un profesional."}
    paso = PASO_MINIMO_KCAL if perdida > 0 else PASO_MAXIMO_KCAL
    if(suelo_kcal is not None):
        paso = min(paso, kcal_actual - suelo_kcal)
    return {
        **base,
        "accion": "proponer_bajada",
        "delta_kcal": -paso,
        "kcal_propuesta": kcal_actual - paso,
        "requiere_aceptacion": True,
        "mensaje": f"Tendencia media del {perdida:.2f} % semanal durante {len(recientes)} semanas con registros suficientes. Se propone bajar {paso:.0f} kcal; revisa también cintura, pasos, hambre, sueño y rendimiento antes de aceptar.",
    }


def factores_para_objetivo(kcal_fijas: float, kcal_ajustables: float, objetivo: float, minimo: float = 0.75, maximo: float = 1.4) -> dict:
    if(kcal_ajustables <= 0):
        return {"factor": 1.0, "limitado": True}
    factor = (objetivo - kcal_fijas) / kcal_ajustables
    limitado = False
    if(factor < minimo):
        factor = minimo
        limitado = True
    if(factor > maximo):
        factor = maximo
        limitado = True
    factor = round(factor * 20) / 20
    return {"factor": factor, "limitado": limitado}
