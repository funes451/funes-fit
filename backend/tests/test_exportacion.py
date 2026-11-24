from app.semilla import sembrar_usuario
from tests.conftest import crear_usuario, cliente_para


def test_exportar_e_importar_en_cuenta_nueva_preserva_registros(aplicacion, fabrica, funes):
    comida = funes.get("/api/menu/dia?fecha=2026-11-23").json()["comidas"][0]
    funes.post("/api/sync", json={"operaciones": [
        {"id_operacion": "e1", "tipo": "consumo.crear", "carga": {"id_cliente": "ce1", "tipo": "previsto", "comida_planificada_id": comida["id"]}},
        {"id_operacion": "e2", "tipo": "medicion.crear", "carga": {"id_cliente": "me2", "fecha": "2026-11-24", "tipo": "cintura", "valor": "118,5"}},
        {"id_operacion": "e3", "tipo": "diario.guardar", "carga": {"fecha": "2026-11-24", "datos": {"sueno_horas": "7,5", "hambre": 3}}},
        {"id_operacion": "e4", "tipo": "sesion.guardar", "carga": {"id_cliente": "se4", "fecha": "2026-11-23", "sesion_codigo": "torso", "estado": "finalizada", "ejercicios": [{"ejercicio_id": 1, "nombre": "Press", "series": [{"peso_kg": 40, "repeticiones": 10, "completada": True}]}]}},
    ]})
    exportado = funes.get("/api/exportar/json").json()
    crear_usuario(fabrica, "restaurada@example.com", "vacio")
    nueva = cliente_para(aplicacion, "restaurada@example.com")
    informe = nueva.post("/api/importar/json", json=exportado).json()
    assert informe["informe"]["consumos"]["creados"] == 1
    reimportado = nueva.get("/api/exportar/json").json()
    for(tabla) in ("consumos", "mediciones", "diario", "sesiones_entreno", "comidas_planificadas", "planes_semana"):
        assert len(reimportado[tabla]) == len(exportado[tabla]), tabla
    dia = nueva.get("/api/menu/dia?fecha=2026-11-23").json()
    assert dia["comidas"][0]["estado"] == "comido_previsto"
    otra_vez = nueva.post("/api/importar/json", json=exportado).json()
    assert otra_vez["informe"].get("consumos", {}).get("creados", 0) == 0
    assert len(nueva.get("/api/exportar/json").json()["consumos"]) == len(exportado["consumos"])
    assert len(funes.get("/api/exportar/json").json()["consumos"]) == 1


def test_csv_de_mediciones(funes):
    previa = funes.post("/api/importar/csv/mediciones", json={"csv": "fecha;valor;tipo\n24/11/2026;111,4;peso\n25/11/2026;abc;peso"}).json()
    assert len(previa["filas"]) == 2 and "error" in previa["filas"][1]
    assert funes.get("/api/mediciones?tipo=peso").json()["mediciones"][0]["valor"] == 111.8
    guardado = funes.post("/api/importar/csv/mediciones", json={"csv": "fecha;valor;tipo\n24/11/2026;111,4;peso", "confirmar": True}).json()
    assert guardado["guardadas"] == 1
    repetido = funes.post("/api/importar/csv/mediciones", json={"csv": "fecha;valor;tipo\n24/11/2026;111,4;peso", "confirmar": True}).json()
    assert repetido["duplicadas"] == 1
    texto = funes.get("/api/exportar/csv/mediciones").text
    assert "111,4" in texto


def test_carga_inicial_idempotente(fabrica, funes, amigo):
    bd = fabrica()
    for(plan, usuario) in (("funes", funes.usuario_id), ("amigo", amigo.usuario_id)):
        segunda = sembrar_usuario(bd, usuario, plan)
        assert all(v == 0 for v in segunda.values()), (plan, segunda)
    bd.close()


def test_copia_y_restauracion(tmp_path, monkeypatch):
    import sqlite3
    from app import cli
    from app.config import configuracion
    base = tmp_path / "datos"
    (base / "fotos").mkdir(parents=True)
    (base / "copias").mkdir()
    ruta = base / "funes_fit.db"
    conexion = sqlite3.connect(ruta)
    conexion.execute("create table t (x integer)")
    conexion.execute("insert into t values (1)")
    conexion.commit()
    conexion.close()
    (base / "fotos" / "1_abc.jpg").write_bytes(b"foto")
    monkeypatch.setattr(configuracion, "directorio_datos", base)
    monkeypatch.setattr(configuracion, "url_bd", f"sqlite:///{ruta.as_posix()}")
    copia = cli.copia_seguridad("prueba")
    conexion = sqlite3.connect(ruta)
    conexion.execute("delete from t")
    conexion.commit()
    conexion.close()
    (base / "fotos" / "1_abc.jpg").unlink()
    cli.restaurar(str(copia))
    conexion = sqlite3.connect(ruta)
    assert conexion.execute("select count(*) from t").fetchone()[0] == 1
    conexion.close()
    assert (base / "fotos" / "1_abc.jpg").read_bytes() == b"foto"
