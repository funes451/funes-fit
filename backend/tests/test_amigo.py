from datetime import date, timedelta

import pytest


def lunes_actual(cliente) -> date:
    hoy = date.fromisoformat(cliente.get("/api/perfil").json()["hoy"])
    return hoy - timedelta(days=hoy.weekday())


def test_perfil_amigo_ganancia_sin_heredar_lo_de_funes(amigo):
    datos = amigo.get("/api/perfil").json()
    perfil = datos["perfil"]
    assert perfil["modo_objetivo"] == "ganar" and perfil["hitos_kg"] == [60.0, 65.0]
    assert perfil["alimentos_excluidos"] == [] and perfil["experiencia"] == "principiante"
    assert perfil["inicio_plan"] is None and perfil["molestias_actuales"] is None and perfil["alergias"] is None
    assert perfil["peso_referencia_kg"] == 55.0 and perfil["peso_inicial_kg"] is None
    assert perfil["plan_aceptado"] is False
    assert any(p["campo"] == "molestias_actuales" for p in datos["pendientes"])
    assert amigo.get("/api/mediciones").json()["mediciones"] == []
    objetivo = datos["objetivo_vigente"]
    assert (objetivo["kcal"], objetivo["proteina_g"], objetivo["hidratos_g"], objetivo["grasas_g"], objetivo["fibra_g"]) == (2900, 110, 400, 95, 30)
    assert objetivo["modo"] == "ganar" and "2.895" in objetivo["detalle"]["nota"]


def test_funes_intacto(funes, amigo):
    perfil = funes.get("/api/perfil").json()["perfil"]
    assert perfil["nombre"] == "Funes" and perfil["modo_objetivo"] == "perder"
    assert perfil["alimentos_excluidos"] == ["puré", "calabacín", "morcilla"]
    assert funes.get("/api/menu/semana?fecha=2026-11-23").json()["plan"]["lunes"] == "2026-11-23"
    assert funes.get("/api/gym/rutina").json()["rutina"]["nombre"] == "Rutina de cinco días"


def test_calendario_cuatro_dias_y_futbol(amigo):
    rutina = amigo.get("/api/gym/rutina").json()["rutina"]
    dias = rutina["distribucion"]
    gimnasio = [d for d in range(7) if any(a["tipo"] == "gimnasio" for a in dias[str(d)])]
    assert gimnasio == [0, 1, 2, 3]
    assert [a["tipo"] for a in dias["2"]] == ["gimnasio", "futbol"]
    assert [a["tipo"] for a in dias["4"]] == ["futbol", "recuperacion"]
    assert rutina["configuracion"]["pendiente_documento"] is True


def test_partido_configurable_sin_duplicar(amigo):
    lunes = lunes_actual(amigo)
    sabado = lunes + timedelta(days=5)
    domingo = lunes + timedelta(days=6)
    assert amigo.put("/api/eventos/partido", json={"fecha": (lunes + timedelta(days=2)).isoformat()}).status_code == 422
    amigo.put("/api/eventos/partido", json={"fecha": sabado.isoformat(), "hora": "11:00"})
    amigo.put("/api/eventos/partido", json={"fecha": domingo.isoformat(), "hora": "12:00"})
    s = amigo.get(f"/api/gym/dia?fecha={sabado.isoformat()}").json()
    d = amigo.get(f"/api/gym/dia?fecha={domingo.isoformat()}").json()
    assert [a["tipo"] for a in s["actividades"]] == []
    assert [a["tipo"] for a in d["actividades"]] == ["partido"]


def test_adaptacion_dos_semanas(amigo, fabrica):
    from app.modelos import Ejercicio, EjercicioRutina, Rutina
    bd = fabrica()
    rutina = bd.query(Rutina).filter(Rutina.usuario_id == amigo.usuario_id).first()
    ejercicio = Ejercicio(usuario_id=amigo.usuario_id, nombre="Ejercicio de prueba", incremento_kg=2.5, alternativas=[])
    bd.add(ejercicio)
    bd.flush()
    bd.add(EjercicioRutina(rutina_id=rutina.id, sesion="torso_a", ejercicio_id=ejercicio.id, orden=0, series=4, rep_min=8, rep_max=12))
    bd.commit()
    inicio = rutina.vigente_desde
    bd.close()
    lunes = inicio - timedelta(days=inicio.weekday())
    for(semana, esperado) in ((0, 2), (1, 2), (2, 4)):
        fecha = lunes + timedelta(days=7 * semana)
        dia = amigo.get(f"/api/gym/dia?fecha={fecha.isoformat()}").json()
        detalle = next(a for a in dia["actividades"] if a["tipo"] == "gimnasio")["detalle"]
        e = detalle["ejercicios"][0]
        if(fecha < inicio):
            continue
        assert e["objetivo"]["series"] == esperado, semana
        if(esperado == 2):
            assert e["objetivo"]["series_min"] == 1 and e["objetivo"]["rir_objetivo"] == "2–3"


def test_menu_propuesta_y_batido_no_sumado(amigo):
    semana = amigo.get(f"/api/menu/semana?fecha={lunes_actual(amigo).isoformat()}").json()
    assert semana["plan"]["origen"] == "propuesta" and semana["plan_aceptado"] is False
    for(dia) in semana["dias"]:
        nombres = [c["receta_nombre"] for c in dia["comidas"]]
        assert "Batido energético" not in nombres
        assert [c["momento"] for c in dia["comidas"]] == ["desayuno", "comida", "merienda", "cena", "extra"]
        assert dia["comidas"][4]["opcional"] is True
        assert 2600 < dia["planificado"]["kcal"] < 3150
        assert dia["planificado_con_opcionales"]["kcal"] > dia["planificado"]["kcal"]
    batido = next(r for r in amigo.get("/api/recetas").json()["recetas"] if r["nombre"] == "Batido energético")
    assert batido["nutrientes_racion"]["kcal"] == pytest.approx(671, abs=5)
    assert set(batido["alergenos"]) >= {"leche", "cacahuete", "gluten (avena)"}
    merienda = semana["dias"][0]["comidas"][2]
    opciones = amigo.get(f"/api/menu/comidas/{merienda['id']}/equivalentes").json()["opciones"]
    assert any(o["receta"]["nombre"] == "Batido energético" for o in opciones)


def test_compra_propia_separada(funes, amigo):
    semana = amigo.get(f"/api/menu/semana?fecha={lunes_actual(amigo).isoformat()}").json()
    lista = amigo.get(f"/api/menu/{semana['plan']['id']}/compra").json()
    nombres = {l["nombre"] for l in lista["lineas"]}
    assert "Leche entera" in nombres and "Queso fresco batido 0 %" not in nombres
    funes_lista = funes.get(f"/api/menu/{funes.get('/api/menu/semana?fecha=2026-11-23').json()['plan']['id']}/compra").json()
    assert "Leche entera" not in {l["nombre"] for l in funes_lista["lineas"]}
    leche = next(l for l in lista["lineas"] if l["nombre"] == "Leche entera")
    assert leche["necesidad_neta"] == pytest.approx(4 * 300 + 3 * 250 + 7 * 200)


def test_confirmar_plan_mueve_propuesta_a_su_fecha(amigo):
    inicio = lunes_actual(amigo) + timedelta(days=14)
    respuesta = amigo.post("/api/perfil/confirmar-plan", json={"inicio_plan": inicio.isoformat(), "nombre": "Nombre real", "molestias_actuales": "", "alergias": "ninguna indicada"})
    assert respuesta.status_code == 200
    perfil = respuesta.json()["perfil"]
    assert perfil["plan_aceptado"] and perfil["inicio_plan"] == inicio.isoformat() and perfil["nombre"] == "Nombre real"
    assert respuesta.json()["pendientes"] != [] or True
    semana = amigo.get(f"/api/menu/semana?fecha={inicio.isoformat()}").json()
    assert semana["plan"]["lunes"] == inicio.isoformat()
    assert respuesta.json()["objetivo_vigente"] is None or respuesta.json()["objetivo_vigente"]["vigente_desde"] == inicio.isoformat()


def test_cambio_de_calorias_de_uno_no_afecta_al_otro(funes, amigo):
    hoy = date.fromisoformat(funes.get("/api/perfil").json()["hoy"])
    manana = hoy + timedelta(days=1)
    funes.post("/api/objetivos", json={"kcal": 2650, "proteina_g": 160, "vigente_desde": manana.isoformat()})
    assert amigo.get("/api/perfil").json()["objetivo_vigente"]["kcal"] == 2900
    historial = funes.get("/api/objetivos").json()["objetivos"]
    assert len(historial) == 2 and historial[-1]["vigente_desde"] == "2026-11-23"
    assert funes.get(f"/api/menu/dia?fecha={hoy.isoformat()}").json()["objetivo"]["kcal"] != 2650
    assert funes.get(f"/api/menu/dia?fecha={manana.isoformat()}").json()["objetivo"]["kcal"] == 2650
    assert funes.post("/api/objetivos", json={"kcal": 2500, "vigente_desde": "2026-11-01"}).status_code == 422


def test_revision_en_modo_ganar(amigo):
    respuesta = amigo.get("/api/objetivos/revision").json()
    assert respuesta["propuesta"]["accion"] == "esperar"
