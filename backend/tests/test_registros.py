import pytest

from tests.conftest import CONTRASENA, cliente_para


def op(identificador, tipo, carga):
    return {"id_operacion": identificador, "tipo": tipo, "carga": carga}


def test_peso_persiste_tras_salir_y_volver(funes, aplicacion):
    r = funes.post("/api/sync", json={"usuario_id": funes.usuario_id, "operaciones": [op("p1", "medicion.crear", {"id_cliente": "m1", "fecha": "24/11/2026", "tipo": "peso", "valor": "111,8"})]}).json()
    assert r["resultados"][0]["estado"] == "aplicada"
    funes.post("/api/auth/salir")
    assert funes.get("/api/mediciones").status_code == 401
    otra = cliente_para(aplicacion, "funes@example.com")
    pesos = [m["valor"] for m in otra.get("/api/mediciones?tipo=peso").json()["mediciones"]]
    assert 111.8 in pesos


def test_sin_registro_es_ausencia_no_cero(funes):
    dia = funes.get("/api/menu/dia?fecha=2026-11-26").json()
    assert dia["consumido_registrado"] is None
    resumen = funes.get("/api/progreso/resumen-semanal?fecha=2026-11-30").json()
    assert resumen["peso"]["media"] is None and resumen["pasos"]["media"] is None


def test_validacion_de_peso(funes):
    r = funes.post("/api/sync", json={"operaciones": [op("p2", "medicion.crear", {"fecha": "2026-11-24", "tipo": "peso", "valor": "1118"})]}).json()
    assert r["resultados"][0]["estado"] == "error"


def test_sesion_gym_guardar_y_reanudar(funes):
    sesion = {"id_cliente": "s1", "fecha": "2026-11-23", "sesion_codigo": "torso", "estado": "en_curso", "ejercicios": [{"ejercicio_id": 1, "nombre": "Press", "rep_min": 8, "rep_max": 12, "series_objetivo": 2, "series": [{"peso_kg": "40", "repeticiones": 10, "completada": True, "rir": 3}, {"peso_kg": "", "repeticiones": None, "completada": False}]}]}
    r = funes.post("/api/sync", json={"operaciones": [op("g1", "sesion.guardar", sesion)]}).json()
    version = r["resultados"][0]["resultado"]["sesion"]["version"]
    dia = funes.get("/api/gym/dia?fecha=2026-11-23").json()
    guardada = dia["actividades"][0]["sesion_registrada"]
    assert guardada["estado"] == "en_curso" and guardada["ejercicios"][0]["series"][0]["peso_kg"] == 40
    sesion["version_base"] = version
    sesion["ejercicios"][0]["series"][1] = {"peso_kg": 40, "repeticiones": 9, "completada": True, "rir": 3}
    sesion["estado"] = "parcial"
    r = funes.post("/api/sync", json={"operaciones": [op("g2", "sesion.guardar", sesion)]}).json()
    assert r["resultados"][0]["estado"] == "aplicada"
    final = funes.get("/api/gym/sesiones").json()["sesiones"]
    assert len(final) == 1 and final[0]["estado"] == "parcial" and len(final[0]["ejercicios"][0]["series"]) == 2


def test_sincronizacion_offline_una_sola_vez(funes, aplicacion):
    cola = [op("off-1", "medicion.crear", {"id_cliente": "moff1", "fecha": "2026-11-25", "tipo": "peso", "valor": 111.5}), op("off-2", "diario.guardar", {"fecha": "2026-11-25", "datos": {"pasos": "6.500", "energia": 4}, "version_base": 0})]
    primera = funes.post("/api/sync", json={"operaciones": cola}).json()
    assert [r["estado"] for r in primera["resultados"]] == ["aplicada", "aplicada"]
    repetida = funes.post("/api/sync", json={"operaciones": cola}).json()
    assert [r["estado"] for r in repetida["resultados"]] == ["duplicada", "duplicada"]
    otro_dispositivo = cliente_para(aplicacion, "funes@example.com")
    pesos = [m for m in otro_dispositivo.get("/api/mediciones?tipo=peso").json()["mediciones"] if m["fecha"] == "2026-11-25"]
    assert len(pesos) == 1
    assert otro_dispositivo.get("/api/diario/2026-11-25").json()["entrada"]["datos"]["pasos"] == 6500


def test_conflicto_no_destruye_datos(funes, aplicacion):
    funes.post("/api/sync", json={"operaciones": [op("d1", "diario.guardar", {"fecha": "2026-11-26", "datos": {"notas": "móvil"}, "version_base": 0})]})
    otro = cliente_para(aplicacion, "funes@example.com")
    otro.post("/api/sync", json={"operaciones": [op("d2", "diario.guardar", {"fecha": "2026-11-26", "datos": {"notas": "ordenador"}, "version_base": 1})]})
    choque = funes.post("/api/sync", json={"operaciones": [op("d3", "diario.guardar", {"fecha": "2026-11-26", "datos": {"notas": "móvil editado sin conexión"}, "version_base": 1})]}).json()
    assert choque["resultados"][0]["estado"] == "conflicto"
    assert funes.get("/api/diario/2026-11-26").json()["entrada"]["datos"]["notas"] == "ordenador"
    conflictos = funes.get("/api/sync/conflictos").json()["conflictos"]
    assert conflictos[0]["cliente"]["datos"]["notas"] == "móvil editado sin conexión"
    funes.post(f"/api/sync/conflictos/{conflictos[0]['id']}/resolver", json={"eleccion": "cliente"})
    assert funes.get("/api/diario/2026-11-26").json()["entrada"]["datos"]["notas"] == "móvil editado sin conexión"
    assert funes.get("/api/sync/conflictos").json()["conflictos"] == []


def test_cola_de_otra_cuenta_se_rechaza(funes, amigo):
    r = amigo.post("/api/sync", json={"usuario_id": funes.usuario_id, "operaciones": [op("ajena", "medicion.crear", {"fecha": "2026-11-25", "tipo": "peso", "valor": 70})]})
    assert r.status_code == 409
    assert all(m["valor"] != 70 for m in amigo.get("/api/mediciones").json()["mediciones"])


def test_registro_parcial_y_extra(funes):
    comida = funes.get("/api/menu/dia?fecha=2026-11-24").json()["comidas"][1]
    r = funes.post("/api/sync", json={"operaciones": [
        op("pa", "consumo.crear", {"id_cliente": "cpa", "tipo": "parcial", "comida_planificada_id": comida["id"], "proporcion": "0,5"}),
        op("ex", "consumo.crear", {"id_cliente": "cex", "tipo": "extra", "fecha": "2026-11-24", "momento": "extra", "descripcion": "Café con leche"}),
    ]}).json()
    assert [x["estado"] for x in r["resultados"]] == ["aplicada", "aplicada"]
    dia = funes.get("/api/menu/dia?fecha=2026-11-24").json()
    assert dia["comidas"][1]["consumos"][0]["nutrientes"]["kcal"] == pytest.approx(comida["nutrientes"]["kcal"] * 0.5)
    assert dia["extras"][0]["nutrientes"]["kcal"] is None


def test_eventos_futbol_independientes_y_sin_duplicar(amigo):
    perfil = amigo.get("/api/perfil").json()
    lunes = perfil["hoy"]
    from datetime import date, timedelta
    hoy = date.fromisoformat(lunes)
    miercoles = hoy - timedelta(days=hoy.weekday()) + timedelta(days=2)
    dia = amigo.get(f"/api/gym/dia?fecha={miercoles.isoformat()}").json()
    tipos = sorted(a["tipo"] for a in dia["actividades"])
    assert tipos == ["futbol", "gimnasio"]
    futbol = next(a for a in dia["actividades"] if a["tipo"] == "futbol")
    carga = {"id_cliente": "ev1", "clave_plan": futbol["clave_plan"], "fecha": miercoles.isoformat(), "tipo": "futbol", "titulo": "Fútbol sala", "estado": "realizado", "datos": {"duracion_min": 60, "esfuerzo": 7, "molestias": ""}}
    amigo.post("/api/sync", json={"operaciones": [op("ev-a", "evento.guardar", carga)]})
    amigo.post("/api/sync", json={"operaciones": [op("ev-b", "evento.guardar", {**carga, "id_cliente": "ev2", "version_base": 1})]})
    dia = amigo.get(f"/api/gym/dia?fecha={miercoles.isoformat()}").json()
    assert len([a for a in dia["actividades"] if a["tipo"] == "futbol"]) == 1
    assert next(a for a in dia["actividades"] if a["tipo"] == "futbol")["estado"] == "realizado"
    gym = next(a for a in dia["actividades"] if a["tipo"] == "gimnasio")
    assert gym["estado"] == "planificado" and gym["sesion_registrada"] is None


def test_peticiones_simultaneas_con_la_misma_operacion(funes, fabrica):
    import threading
    from app.servicios import registros
    original = registros.crear_medicion
    barrera = threading.Barrier(2)

    def lenta(bd, usuario_id, carga):
        barrera.wait(timeout=5)
        return original(bd, usuario_id, carga)

    registros.MANEJADORES["medicion.crear"] = lenta
    respuestas = []
    cuerpo = {"operaciones": [op("simultanea", "medicion.crear", {"id_cliente": "msim", "fecha": "2026-11-27", "tipo": "peso", "valor": 111.2})]}
    hilos = [threading.Thread(target=lambda: respuestas.append(funes.post("/api/sync", json=cuerpo))) for _ in range(2)]
    try:
        for(h) in hilos:
            h.start()
        for(h) in hilos:
            h.join()
    finally:
        registros.MANEJADORES["medicion.crear"] = original
    assert sorted(r.status_code for r in respuestas) == [200, 200]
    estados = sorted(r.json()["resultados"][0]["estado"] for r in respuestas)
    assert estados == ["aplicada", "duplicada"]
    assert len([m for m in funes.get("/api/mediciones").json()["mediciones"] if m["fecha"] == "2026-11-27"]) == 1
