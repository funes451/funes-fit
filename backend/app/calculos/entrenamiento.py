def _gym(sesion: str) -> dict:
    return {"tipo": "gimnasio", "sesion": sesion}


DISTRIBUCION_ESTANDAR = {0: [_gym("torso")], 1: [_gym("pierna_a")], 2: [], 3: [_gym("empuje")], 4: [_gym("tiron")], 5: [_gym("pierna_b")], 6: []}
DISTRIBUCION_LUNES_VIERNES = {0: [_gym("torso")], 1: [_gym("pierna_a")], 2: [_gym("empuje")], 3: [_gym("tiron")], 4: [_gym("pierna_b")], 5: [], 6: []}
NOMBRES_SESION = {
    "torso": "Torso",
    "pierna_a": "Pierna A",
    "empuje": "Empuje",
    "tiron": "Tirón",
    "pierna_b": "Pierna B",
}
SEMANAS_PROGRAMA = 8
TIPOS_EVENTO = ("gimnasio", "futbol", "partido", "recuperacion", "cardio", "descanso", "otro")


def distribucion(modo: str) -> dict:
    origen = DISTRIBUCION_LUNES_VIERNES if modo == "lunes_viernes" else DISTRIBUCION_ESTANDAR
    return {dia: [dict(e) for e in elementos] for dia, elementos in origen.items()}


def normalizar_distribucion(datos: dict) -> dict:
    resultado = {}
    for(dia) in range(7):
        elementos = datos.get(dia, datos.get(str(dia))) or []
        if(isinstance(elementos, str)):
            elementos = [_gym(elementos)]
        limpios = []
        for(e) in elementos:
            if(isinstance(e, str)):
                e = _gym(e)
            tipo = e.get("tipo", "gimnasio")
            if(tipo not in TIPOS_EVENTO):
                raise ValueError(f"Tipo de actividad no válido: {tipo}")
            limpio = {"tipo": tipo}
            for(clave) in ("sesion", "titulo", "hora", "opcional"):
                if(e.get(clave) not in (None, "")):
                    limpio[clave] = e[clave]
            limpios.append(limpio)
        resultado[dia] = limpios
    return resultado


def sesiones_gimnasio(dias: dict) -> list:
    return [[e.get("sesion") for e in dias.get(i, []) if e.get("tipo") == "gimnasio" and e.get("sesion")] for i in range(7)]


def validar_distribucion(dias: dict) -> list[str]:
    avisos = []
    por_dia = sesiones_gimnasio(dias)
    activas = [s for lista in por_dia for s in lista]
    if(len(activas) != len(set(activas))):
        avisos.append("Hay una sesión repetida en la semana: no dupliques sesiones para recuperar faltas.")
    if(any(len(lista) > 1 for lista in por_dia)):
        avisos.append("Dos sesiones de fuerza el mismo día: revisa la recuperación.")
    for(i) in range(7):
        actual = por_dia[i]
        siguiente = por_dia[(i + 1) % 7]
        if(any(s.startswith("pierna") for s in actual) and any(s.startswith("pierna") for s in siguiente)):
            avisos.append("Dos sesiones de pierna en días seguidos: deja al menos un día entre ellas.")
    if(cinco_seguidos(dias)):
        avisos.append("Cinco días seguidos: el volumen se ajusta a la baja para facilitar la recuperación.")
    return avisos


def cinco_seguidos(dias: dict) -> bool:
    por_dia = sesiones_gimnasio(dias)
    consecutivos = 0
    maximo = 0
    for(lista) in por_dia + por_dia:
        if(len(lista) > 0):
            consecutivos = consecutivos + 1
            maximo = max(maximo, consecutivos)
        else:
            consecutivos = 0
    return maximo >= 5


def semana_programa(inicio, fecha) -> int:
    if(fecha < inicio):
        return 0
    from datetime import timedelta
    lunes_inicio = inicio - timedelta(days=inicio.weekday())
    lunes_fecha = fecha - timedelta(days=fecha.weekday())
    return (lunes_fecha - lunes_inicio).days // 7 + 1


ADAPTACION_POR_DEFECTO = {"semanas": 1, "semanas_si_parada_larga": 2, "series_max": 2, "rir_adaptacion": 3, "rir_trabajo": 2, "texto": "Semana de calibración: dos series dejando unas tres repeticiones posibles."}


def series_objetivo(series_tabla: int, semana: int, continuidad: str | None, fatiga: bool, cinco: bool, principal: bool, adaptacion: dict | None = None) -> dict:
    config = dict(ADAPTACION_POR_DEFECTO)
    config.update(adaptacion or {})
    semanas_adaptacion = config["semanas"]
    if(continuidad in ("mas_de_3_meses", "mas_de_6_meses")):
        semanas_adaptacion = max(semanas_adaptacion, config.get("semanas_si_parada_larga", semanas_adaptacion))
    if(semana >= 1 and semana <= semanas_adaptacion):
        return {
            "series": min(config["series_max"], series_tabla),
            "series_min": min(config.get("series_min", config["series_max"]), series_tabla),
            "rir_objetivo": config["rir_adaptacion"],
            "fase": "adaptacion",
            "nota": config["texto"],
        }
    series = series_tabla
    nota = config.get("texto_trabajo") or "Series de trabajo dejando normalmente dos repeticiones en reserva."
    if(cinco and not principal and series > 2):
        series = series - 1
        nota = "Volumen ajustado por entrenar cinco días seguidos."
    if(fatiga):
        series = max(1, series - 1)
        nota = "Volumen reducido por fatiga acumulada registrada."
    return {"series": series, "series_min": series, "rir_objetivo": config["rir_trabajo"], "fase": "trabajo", "nota": nota}


def sugerencia_progresion(historial: list[dict], rep_min: int, rep_max: int, incremento: float) -> dict:
    validas = [s for s in historial if len([serie for serie in s["series"] if serie.get("completada")]) > 0]
    if(len(validas) == 0):
        return {"accion": "sin_datos", "mensaje": "Elige una carga con técnica controlada y recorrido cómodo. Sin pruebas máximas."}
    ultima = validas[0]
    series_ultima = [s for s in ultima["series"] if s.get("completada")]
    peso_ultimo = max((s.get("peso_kg") or 0) for s in series_ultima)
    if(any((s.get("repeticiones") or 0) < rep_min for s in series_ultima) or ultima.get("tecnica_ok") == False):
        return {
            "accion": "mantener_o_reducir",
            "peso_sugerido": peso_ultimo,
            "mensaje": "No se llegó al mínimo del rango o la técnica empeoró: mantén o reduce la carga.",
        }
    if(len(validas) < 2):
        return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "Mantén la carga y busca completar el rango."}
    dos = validas[:2]
    pesos = []
    margen_desconocido = False
    for(sesion) in dos:
        hechas = [s for s in sesion["series"] if s.get("completada")]
        if(len(hechas) < sesion.get("series_objetivo", len(hechas))):
            return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "Completa todas las series antes de subir."}
        if(any((s.get("repeticiones") or 0) < rep_max for s in hechas)):
            return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "Sigue en esta carga hasta completar el máximo del rango en todas las series."}
        if(sesion.get("tecnica_ok") == False):
            return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "La técnica no fue buena: mantén la carga."}
        for(s) in hechas:
            if(s.get("rir") is None):
                margen_desconocido = True
            elif(s["rir"] < 1):
                return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "Llegaste muy cerca del fallo: mantén la carga."}
        pesos.append(max((s.get("peso_kg") or 0) for s in hechas))
    if(abs(pesos[0] - pesos[1]) > 1e-6):
        return {"accion": "mantener", "peso_sugerido": peso_ultimo, "mensaje": "La carga cambió entre sesiones: repite esta antes de subir."}
    mensaje = f"Completaste el máximo del rango dos sesiones seguidas: puedes probar {peso_ultimo + incremento:g} kg (siguiente incremento pequeño)."
    if(margen_desconocido):
        mensaje = mensaje + " Confirma que te quedaba margen y buena técnica."
    return {
        "accion": "subir",
        "peso_sugerido": peso_ultimo + incremento,
        "requiere_aceptacion": True,
        "confirmar_margen": margen_desconocido,
        "mensaje": mensaje,
    }


def tiempo_estimado_min(ejercicios: list[dict], cardio_min: int = 0) -> dict:
    total_s = 8 * 60
    for(e) in ejercicios:
        descanso = 150 if e.get("principal") else 75
        total_s = total_s + e["series"] * (45 + descanso)
    total = round(total_s / 60) + cardio_min
    return {"minutos": total, "texto": f"unos {total} min orientativos, sin temporizador obligatorio"}
