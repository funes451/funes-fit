import pytest

from app.calculos.nutricion import contiene_excluido

LUNES = "2026-11-23"

NETO_ESPERADO = {
    "Avena (copos normales)": 420, "Leche semidesnatada": 2100, "Plátano sin piel": 1050, "Queso fresco batido 0 %": 3500, "Manzana": 1260,
    "Frutos secos naturales": 140, "Pollo sin piel (pechuga)": 540, "Arroz": 350, "Aceite de oliva": 175, "Lentejas cocidas escurridas": 500,
    "Patata": 1600, "Soja texturizada": 180, "Pasta integral": 200, "Tomate triturado": 400, "Merluza": 440, "Pan integral": 180,
    "Garbanzos cocidos escurridos": 800, "Atún al natural escurrido": 200, "Huevo sin cáscara": 240, "Caballa al natural escurrida": 150,
}
VERDURAS = ("Brócoli congelado", "Judías verdes congeladas", "Zanahoria", "Pimiento", "Cebolla", "Tomate", "Lechuga")


def semana(cliente):
    respuesta = cliente.get(f"/api/menu/semana?fecha={LUNES}")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_semana_empieza_lunes_23_con_torso(funes):
    datos = semana(funes)
    assert datos["plan"]["lunes"] == LUNES
    assert datos["dias"][0]["fecha"] == LUNES
    gym = funes.get(f"/api/gym/dia?fecha={LUNES}").json()
    assert [a["sesion"] for a in gym["actividades"] if a["tipo"] == "gimnasio"] == ["torso"]
    miercoles = funes.get("/api/gym/dia?fecha=2026-11-25").json()
    assert miercoles["descanso"] is True
    sabado = funes.get("/api/gym/dia?fecha=2026-11-28").json()
    assert sabado["actividades"][0]["sesion"] == "pierna_b"


def test_dia_real_y_semana_sin_plan(funes):
    hoy = funes.get("/api/hoy").json()
    assert hoy["fecha"] == hoy["menu"]["hoy"]
    futura = funes.get("/api/menu/semana?fecha=2027-03-01").json()
    assert futura["plan"] is None and futura["puede_repetir_desde"] == LUNES


def test_siete_dias_completos_sin_excluidos(funes):
    datos = semana(funes)
    assert len(datos["dias"]) == 7
    for(dia) in datos["dias"]:
        momentos = [c["momento"] for c in dia["comidas"]]
        assert momentos == ["desayuno", "comida", "merienda", "cena"]
        for(comida) in dia["comidas"]:
            receta = funes.get(f"/api/recetas/{comida['receta_id']}").json()["receta"]
            assert len(receta["ingredientes"]) >= 2
            assert all(i["cantidad"] > 0 for i in receta["ingredientes"])
            assert receta["pasos"] and receta["conservacion"]
            for(i) in receta["ingredientes"]:
                assert contiene_excluido(i["nombre"]) is None or "sin calabacín" in i["nombre"]


def test_totales_derivados_de_ingredientes(funes):
    datos = semana(funes)
    lunes = datos["dias"][0]
    suma = 0
    for(comida) in lunes["comidas"]:
        receta = funes.get(f"/api/recetas/{comida['receta_id']}").json()["receta"]
        suma = suma + sum(i["valores"]["kcal"] for i in receta["ingredientes"])
    assert lunes["planificado"]["kcal"] == pytest.approx(suma)
    assert 2300 < lunes["planificado"]["kcal"] < 2550
    assert lunes["objetivo"]["provisional"] is True


def test_lista_coincide_con_suma_de_ingredientes(funes):
    plan_id = semana(funes)["plan"]["id"]
    lista = funes.get(f"/api/menu/{plan_id}/compra").json()
    netas = {l["nombre"]: l["necesidad_neta"] for l in lista["lineas"]}
    for(nombre, cantidad) in NETO_ESPERADO.items():
        assert netas[nombre] == pytest.approx(cantidad), nombre
    assert sum(netas[v] for v in VERDURAS) == pytest.approx(3700)
    assert lista["totales"]["estado"] == "parcial"
    assert lista["presupuesto"]["estado"] == "no_comparable"
    aceite = next(l for l in lista["lineas"] if l["nombre"] == "Aceite de oliva")
    assert aceite["envases"] == 1 and aceite["sobrante"] == pytest.approx(741)


def test_despensa_y_compra_marcada(funes):
    plan_id = semana(funes)["plan"]["id"]
    lista = funes.get(f"/api/menu/{plan_id}/compra").json()
    arroz = next(l for l in lista["lineas"] if l["nombre"] == "Arroz")
    assert funes.put(f"/api/despensa/{arroz['alimento_id']}", json={"cantidad": "200"}).status_code == 200
    arroz = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"] == "Arroz")
    assert arroz["falta"] == pytest.approx(150) and arroz["envases"] == 1
    op = {"id_operacion": "op-compra-1", "tipo": "compra.marcar", "carga": {"id_cliente": "compra-1", "plan_id": plan_id, "alimento_id": arroz["alimento_id"], "producto_id": arroz["producto"]["id"], "envases": 1, "precio_unitario": "1,15"}}
    funes.post("/api/sync", json={"operaciones": [op]})
    funes.post("/api/sync", json={"operaciones": [op]})
    arroz = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"] == "Arroz")
    assert arroz["estado"] == "comprado" and arroz["despensa"] == pytest.approx(1200)
    assert arroz["precio_estado"] == "confirmado"


def test_duplicar_cantidad_actualiza_nutrientes_y_compra_sin_tocar_historial(funes):
    datos = semana(funes)
    comida = datos["dias"][0]["comidas"][1]
    registro = funes.post("/api/sync", json={"operaciones": [{"id_operacion": "op-a", "tipo": "consumo.crear", "carga": {"id_cliente": "c-a", "tipo": "previsto", "comida_planificada_id": comida["id"]}}]}).json()
    kcal_historico = registro["resultados"][0]["resultado"]["consumo"]["nutrientes"]["kcal"]
    receta = funes.get(f"/api/recetas/{comida['receta_id']}").json()["receta"]
    nuevos = [{"alimento_id": i["alimento_id"], "cantidad": i["cantidad"] * 2, "unidad": i["unidad"]} for i in receta["ingredientes"]]
    plan_id = datos["plan"]["id"]
    pollo_antes = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"].startswith("Pollo"))["necesidad_neta"]
    assert funes.put(f"/api/recetas/{receta['id']}", json={"ingredientes": nuevos}).status_code == 200
    actualizada = funes.get(f"/api/recetas/{receta['id']}").json()["receta"]
    assert actualizada["nutrientes_racion"]["kcal"] == pytest.approx(receta["nutrientes_racion"]["kcal"] * 2)
    pollo_despues = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"].startswith("Pollo"))["necesidad_neta"]
    assert pollo_despues == pytest.approx(pollo_antes * 2)
    dia = funes.get(f"/api/menu/dia?fecha={LUNES}").json()
    consumo = dia["comidas"][1]["consumos"][0]
    assert consumo["nutrientes"]["kcal"] == pytest.approx(kcal_historico)


def test_marcar_dos_veces_no_duplica_y_diferente_conserva_plan(funes):
    comidas = semana(funes)["dias"][0]["comidas"]
    for(i) in range(2):
        funes.post("/api/sync", json={"operaciones": [{"id_operacion": f"op-x{i}", "tipo": "consumo.crear", "carga": {"id_cliente": f"cx{i}", "tipo": "previsto", "comida_planificada_id": comidas[0]["id"]}}]})
    distinto = funes.post("/api/sync", json={"operaciones": [{"id_operacion": "op-dif", "tipo": "consumo.crear", "carga": {"id_cliente": "cdif", "tipo": "diferente", "comida_planificada_id": comidas[3]["id"], "descripcion": "Bocadillo fuera de casa"}}]}).json()
    assert distinto["resultados"][0]["estado"] == "aplicada"
    dia = funes.get(f"/api/menu/dia?fecha={LUNES}").json()
    assert len(dia["comidas"][0]["consumos"]) == 1
    assert dia["comidas"][3]["estado"] == "comido_diferente"
    assert dia["comidas"][3]["receta_id"] == comidas[3]["receta_id"]
    assert dia["comidas_pendientes"] == 2
    assert dia["aviso_registro"] is not None


def test_ajuste_de_raciones_cambia_menu_y_compra(funes):
    datos = semana(funes)
    plan_id = datos["plan"]["id"]
    propuesta = funes.post(f"/api/menu/{plan_id}/ajuste/propuesta", json={"kcal_objetivo": 2650}).json()
    assert all(abs(d["kcal_propuesta"] - 2650) < 120 for d in propuesta["dias"])
    sin_cambios = semana(funes)
    assert sin_cambios["dias"][6]["planificado"]["kcal"] == pytest.approx(datos["dias"][6]["planificado"]["kcal"])
    arroz_antes = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"] == "Arroz")["necesidad_neta"]
    resultado = funes.post(f"/api/menu/{plan_id}/ajuste/aplicar", json={"kcal_objetivo": 2650, "incluir_pasado": True}).json()
    assert resultado["comidas_ajustadas"] == 14
    despues = semana(funes)
    assert despues["dias"][0]["planificado"]["kcal"] > datos["dias"][0]["planificado"]["kcal"]
    arroz_despues = next(l for l in funes.get(f"/api/menu/{plan_id}/compra").json()["lineas"] if l["nombre"] == "Arroz")["necesidad_neta"]
    assert arroz_despues > arroz_antes
    assert despues["plan"]["version"] == datos["plan"]["version"] + 1


def test_equivalentes_y_sustitucion(funes):
    comida = semana(funes)["dias"][1]["comidas"][3]
    opciones = funes.get(f"/api/menu/comidas/{comida['id']}/equivalentes").json()["opciones"]
    assert len(opciones) > 0
    elegida = opciones[0]
    assert funes.patch(f"/api/menu/comidas/{comida['id']}", json={"receta_id": elegida["receta"]["id"], "factor": elegida["factor"], "hora": "21:30"}).status_code == 200
    dia = funes.get("/api/menu/dia?fecha=2026-11-24").json()
    assert dia["comidas"][3]["receta_id"] == elegida["receta"]["id"] and dia["comidas"][3]["hora"] == "21:30"


def test_generar_semana_siguiente_como_repeticion(funes):
    respuesta = funes.post("/api/menu/semana/generar", json={"lunes": "30/11/2026"}).json()
    assert respuesta["creado"] and respuesta["origen"] == "repeticion_programada"
    otra = funes.post("/api/menu/semana/generar", json={"lunes": "2026-11-30"}).json()
    assert otra["creado"] is False
    nueva = funes.get("/api/menu/semana?fecha=2026-12-02").json()
    assert nueva["plan"]["origen"] == "repeticion_programada" and len(nueva["dias"]) == 7


def test_tandas_y_conservacion(funes):
    plan_id = semana(funes)["plan"]["id"]
    tandas = funes.get(f"/api/menu/{plan_id}/tandas").json()
    assert len(tandas["tandas"]) == 2
    pollo = next(r for r in tandas["tandas"][0]["recetas"] if r["receta"].startswith("Pollo"))
    assert any("congelar" in u["conservar"] or "recién" in u["conservar"] for u in pollo["usos"])
    assert any("24 h" in n for n in tandas["normas"])


def test_abaratar_pide_precios_y_no_aplica_sin_aceptar(funes):
    plan_id = semana(funes)["plan"]["id"]
    respuesta = funes.get(f"/api/menu/{plan_id}/abaratar").json()
    assert respuesta["propuestas"] == []
    assert len(respuesta["recetas_sin_precios"]) > 0
