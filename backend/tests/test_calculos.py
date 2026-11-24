from datetime import date, datetime, timezone

import pytest

from app.calculos import compra, energia, entrenamiento, nutricion, progreso
from app.calculos.fechas import en_franja_silencio, hoy_local, interpretar_fecha, interpretar_hora, lunes_de
from app.calculos.numeros import formatear, interpretar_numero


def test_mifflin_con_datos_de_funes():
    assert energia.mifflin_st_jeor(111.8, 182, 19, "masculino") == pytest.approx(2165.5)
    assert energia.mifflin_st_jeor(111.8, 182, 19, "femenino") == pytest.approx(1999.5)


def test_gasto_es_hipotesis_con_rango():
    gasto = energia.gasto_estimado(2165.5, "ligero_moderado")
    assert gasto["minimo"] == pytest.approx(2923.4, abs=0.1)
    assert gasto["maximo"] == pytest.approx(3248.3, abs=0.1)


def test_plantilla_que_excede_deficit_moderado_no_se_activa_a_ciegas():
    gasto = energia.gasto_estimado(2165.5, "ligero_moderado")
    evaluacion = energia.evaluar_plantilla(2412, gasto)
    assert evaluacion["estado"] == "excede_deficit_moderado"
    assert evaluacion["deficit_rango"][0] == pytest.approx(511, abs=1)
    propuesta = energia.proponer_objetivo(2165.5, gasto)
    assert 300 <= propuesta["deficit_central"] <= 500
    assert propuesta["kcal"] > 2412


def test_resumen_sin_sexo_no_inventa_gasto():
    resumen = energia.resumen_energia(111.8, 182, 19, None, None, 2412)
    assert resumen["completo"] is False
    assert "gasto" not in resumen
    assert resumen["reposo_por_sexo"]["masculino"] == pytest.approx(2165.5)


def test_numeros_con_coma_decimal():
    assert interpretar_numero("111,8", "peso") == pytest.approx(111.8)
    assert interpretar_numero("1.234,5", "x") == pytest.approx(1234.5)
    assert interpretar_numero("111.8", "x") == pytest.approx(111.8)
    assert interpretar_numero("", "x", opcional=True) is None
    with pytest.raises(ValueError):
        interpretar_numero("abc", "x")
    with pytest.raises(ValueError):
        interpretar_numero("400", "peso", 30, 350)
    assert formatear(111.8) == "111,8"


def test_fechas_y_horas_locales():
    assert interpretar_fecha("23/11/2026") == date(2026, 11, 23)
    assert interpretar_fecha("2026-11-23") == date(2026, 11, 23)
    assert interpretar_hora("8.30") == "08:30"
    assert lunes_de(date(2026, 11, 29)) == date(2026, 11, 23)
    assert hoy_local("Europe/Madrid", datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc)) == date(2026, 11, 23)
    assert en_franja_silencio(23 * 60, "22:30", "08:00")
    assert en_franja_silencio(7 * 60, "22:30", "08:00")
    assert not en_franja_silencio(12 * 60, "22:30", "08:00")


def test_exclusiones():
    assert nutricion.contiene_excluido("Crema de calabacín") == "calabacín"
    assert nutricion.contiene_excluido("Puré de patata") == "puré"
    assert nutricion.contiene_excluido("Morcillas de Burgos") == "morcilla"
    assert nutricion.contiene_excluido("Purés variados") == "puré"
    assert nutricion.contiene_excluido("Verduras sin calabacín") == "calabacín"
    assert nutricion.contiene_excluido("Pollo con arroz") is None
    assert nutricion.contiene_excluido("Crema de calabacín", []) is None


def test_nutrientes_y_fibra_ausente():
    avena = {"id": 1, "nombre": "Avena", "base": "100g", "kcal": 370, "proteina": 13, "hidratos": 60, "grasas": 7, "fibra": None}
    leche = {"id": 2, "nombre": "Leche", "base": "100ml", "kcal": 46, "proteina": 3.2, "hidratos": 4.8, "grasas": 1.6, "fibra": None}
    resultado = nutricion.nutrientes_receta([{"alimento": avena, "cantidad": 60, "unidad": "g"}, {"alimento": leche, "cantidad": 300, "unidad": "ml"}], 1)
    assert resultado["racion"]["kcal"] == pytest.approx(222 + 138)
    assert resultado["racion"]["fibra"] is None
    assert resultado["total"]["fibra_faltan"] == 2


def test_conversion_ml_a_gramos_con_densidad():
    aceite = {"nombre": "Aceite", "base": "100g", "densidad": 0.916}
    assert nutricion.a_unidad_base(1, "l", aceite) == pytest.approx(916)
    with pytest.raises(ValueError):
        nutricion.a_unidad_base(1, "l", {"nombre": "Arroz", "base": "100g"})


def test_porcion_de_lote_cocinado():
    total = {"kcal": 1000.0, "proteina": 50.0, "hidratos": 100.0, "grasas": 20.0, "fibra": None}
    porcion = nutricion.nutrientes_porcion_lote(total, 2000, 500)
    assert porcion["kcal"] == pytest.approx(250)
    assert porcion["fibra"] is None


def _alimento(identificador, nombre, factor=1.0):
    return {"id": identificador, "nombre": nombre, "factor_compra": factor, "seccion": "Otros", "unidad_base": "g"}


def test_compra_envases_despensa_y_sobrante():
    arroz = _alimento(1, "Arroz")
    producto = {"id": 10, "nombre": "Arroz 1 kg", "capacidad": 1, "unidad": "kg", "capacidad_util": 1000, "precio": 1.2, "precio_origen": "ticket"}
    linea = compra.calcular_linea(arroz, 350, 0, producto, 0)
    assert linea["envases"] == 1 and linea["sobrante"] == pytest.approx(650)
    assert linea["coste_consumido"] == pytest.approx(0.42)
    assert linea["desembolso"] == pytest.approx(1.2)
    con_despensa = compra.calcular_linea(arroz, 350, 650, producto, 0)
    assert con_despensa["envases"] == 0 and con_despensa["estado"] == "en_despensa"
    assert con_despensa["sobrante"] == pytest.approx(300)
    parcial = compra.calcular_linea(arroz, 350, 100, producto, 0)
    assert parcial["falta"] == pytest.approx(250) and parcial["envases"] == 1


def test_compra_peso_escurrido_y_merma():
    atun = _alimento(2, "Atún escurrido")
    pack = {"id": 11, "nombre": "Pack 3", "capacidad": 3, "unidad": "ud", "capacidad_util": 156, "precio": None, "precio_origen": "desconocido"}
    linea = compra.calcular_linea(atun, 200, 0, pack, 0)
    assert linea["envases"] == 2
    assert linea["sobrante"] == pytest.approx(112)
    platano = _alimento(3, "Plátano", 1.55)
    granel = {"id": 12, "nombre": "Granel", "capacidad": 100, "unidad": "g", "capacidad_util": 100, "precio": None}
    linea = compra.calcular_linea(platano, 1050, 0, granel, 0)
    assert linea["necesidad_compra"] == pytest.approx(1627.5)
    assert linea["envases"] == 17


def test_precios_desconocidos_no_cuentan_como_cero():
    necesidades = {1: {"alimento": _alimento(1, "Arroz"), "cantidad": 350}, 2: {"alimento": _alimento(2, "Avena"), "cantidad": 420}}
    productos = {
        1: {"id": 10, "nombre": "Arroz", "capacidad": 1000, "unidad": "g", "capacidad_util": 1000, "precio": None},
        2: {"id": 11, "nombre": "Avena", "capacidad": 800, "unidad": "g", "capacidad_util": 800, "precio": 1.3, "precio_origen": "referencia_externa"},
    }
    lista = compra.calcular_lista(necesidades, {}, productos, {})
    assert lista["totales"]["estado"] == "parcial"
    assert lista["totales"]["sin_precio_compra"] == ["Arroz"]
    assert lista["totales"]["desembolso_pendiente_conocido"] == pytest.approx(1.3)
    assert next(l for l in lista["lineas"] if l["nombre"] == "Avena")["precio_estado"] == "estimado"
    assert compra.comparar_presupuesto(lista["totales"], 60, False)["estado"] == "no_comparable"


def test_progresion_requiere_dos_sesiones_en_maximo():
    serie = lambda reps, rir=2: {"peso_kg": 40, "repeticiones": reps, "completada": True, "rir": rir}
    dos_maximo = [{"series": [serie(12), serie(12), serie(12)], "series_objetivo": 3}, {"series": [serie(12), serie(12), serie(12)], "series_objetivo": 3}]
    sugerencia = entrenamiento.sugerencia_progresion(dos_maximo, 8, 12, 2.5)
    assert sugerencia["accion"] == "subir" and sugerencia["peso_sugerido"] == 42.5 and sugerencia["requiere_aceptacion"]
    una = entrenamiento.sugerencia_progresion(dos_maximo[:1], 8, 12, 2.5)
    assert una["accion"] == "mantener"
    sin_margen = [{"series": [serie(12, 0)] * 3, "series_objetivo": 3}] * 2
    assert entrenamiento.sugerencia_progresion(sin_margen, 8, 12, 2.5)["accion"] == "mantener"
    bajo_minimo = [{"series": [serie(7), serie(9)], "series_objetivo": 2}]
    assert entrenamiento.sugerencia_progresion(bajo_minimo, 8, 12, 2.5)["accion"] == "mantener_o_reducir"
    mala_tecnica = [{"series": [serie(12)] * 3, "series_objetivo": 3, "tecnica_ok": False}] * 2
    assert entrenamiento.sugerencia_progresion(mala_tecnica, 8, 12, 2.5)["accion"] == "mantener_o_reducir"


def test_calibracion_y_parada_larga():
    assert entrenamiento.series_objetivo(3, 1, "continuo", False, False, True)["series"] == 2
    assert entrenamiento.series_objetivo(3, 1, "continuo", False, False, True)["rir_objetivo"] == 3
    assert entrenamiento.series_objetivo(3, 2, "continuo", False, False, True)["series"] == 3
    assert entrenamiento.series_objetivo(3, 2, "mas_de_3_meses", False, False, True)["fase"] == "adaptacion"
    assert entrenamiento.series_objetivo(3, 3, "continuo", True, False, False)["series"] == 2


def test_distribucion_lunes_viernes_no_duplica():
    dias = entrenamiento.distribucion("lunes_viernes")
    avisos = entrenamiento.validar_distribucion(dias)
    assert any("Cinco días seguidos" in a for a in avisos)
    assert not any("repetida" in a for a in avisos)
    mala = entrenamiento.normalizar_distribucion({0: ["torso"], 1: ["torso"]})
    assert any("repetida" in a for a in entrenamiento.validar_distribucion(mala))


def test_media_semanal_requiere_tres_medidas():
    medidas = [{"fecha": date(2026, 11, 23), "valor": 111.8}, {"fecha": date(2026, 11, 25), "valor": 111.4}]
    semanas = progreso.medias_semanales(medidas)
    assert semanas[0]["valida"] is False and semanas[0]["media"] is None and semanas[0]["medidas"] == 2


def _semanas(valores_por_semana):
    medidas = []
    for(i, valores) in enumerate(valores_por_semana):
        for(j, v) in enumerate(valores):
            medidas.append({"fecha": date(2026, 11, 23 + j) if i == 0 else date.fromordinal(date(2026, 11, 23).toordinal() + 7 * i + j), "valor": v})
    return progreso.medias_semanales(medidas)


def test_no_recorta_por_una_semana_sin_bajada():
    semanas = _semanas([[111.8, 111.6, 111.7], [111.7, 111.8, 111.6]])
    assert progreso.propuesta_ajuste(semanas, 2600, 2166, {}, 0.9, None, date(2026, 12, 7))["accion"] == "esperar"


def test_propone_bajada_explicita_tras_tres_semanas_planas():
    semanas = _semanas([[111.8] * 3, [111.8] * 3, [111.8] * 3])
    propuesta = progreso.propuesta_ajuste(semanas, 2600, 2166, {}, 0.9, date(2026, 11, 23), date(2026, 12, 14))
    assert propuesta["accion"] == "proponer_bajada"
    assert -150 <= propuesta["delta_kcal"] <= -100 and propuesta["requiere_aceptacion"]


def test_no_baja_del_suelo_ni_con_alertas():
    semanas = _semanas([[111.8] * 3, [111.8] * 3, [111.8] * 3])
    assert progreso.propuesta_ajuste(semanas, 2200, 2166, {}, 0.9, None, date(2026, 12, 14))["accion"] == "no_bajar"
    assert progreso.propuesta_ajuste(semanas, 2600, 2166, {"mareos": True}, 0.9, None, date(2026, 12, 14))["accion"] == "detener"


def test_modo_ganar_reglas_del_documento():
    plano = _semanas([[55.0] * 3, [55.05] * 3, [55.1] * 3])
    assert progreso.propuesta_ajuste(plano, 2900, None, {}, 0.9, None, date(2026, 12, 14), "ganar")["delta_kcal"] == 150
    moderado = _semanas([[55.0] * 3, [55.25] * 3, [55.5] * 3])
    assert progreso.propuesta_ajuste(moderado, 2900, None, {}, 0.9, None, date(2026, 12, 14), "ganar")["accion"] == "mantener"
    rapido = _semanas([[55.0] * 3, [55.6] * 3, [56.2] * 3])
    resultado = progreso.propuesta_ajuste(rapido, 2900, None, {}, 0.9, None, date(2026, 12, 14), "ganar")
    assert resultado["accion"] == "proponer_bajada" and resultado["delta_kcal"] == -150
    una = _semanas([[55.0] * 3, [55.0] * 3])
    assert progreso.propuesta_ajuste(una, 2900, None, {}, 0.9, None, date(2026, 12, 14), "ganar")["accion"] == "esperar"


def test_semanas_de_programa_por_semana_natural():
    assert entrenamiento.semana_programa(date(2026, 11, 24), date(2026, 11, 23)) == 0
    assert entrenamiento.semana_programa(date(2026, 11, 24), date(2026, 11, 29)) == 1
    assert entrenamiento.semana_programa(date(2026, 11, 24), date(2026, 11, 30)) == 2
    assert entrenamiento.semana_programa(date(2026, 11, 23), date(2026, 12, 6)) == 2
