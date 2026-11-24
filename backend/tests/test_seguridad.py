from datetime import timedelta

import pyotp
from fastapi.testclient import TestClient

from app.modelos import Invitacion, ahora_utc
from app.rutas.cuenta import crear_invitacion
from tests.conftest import CONTRASENA


def test_sin_sesion_no_hay_datos(aplicacion):
    cliente = TestClient(aplicacion)
    for(ruta) in ("/api/hoy", "/api/perfil", "/api/recetas", "/api/mediciones", "/api/fotos", "/api/exportar/json", "/api/gym/rutina"):
        assert cliente.get(ruta).status_code == 401, ruta


def test_peticiones_sin_cabecera_se_rechazan(funes):
    respuesta = funes.post("/api/sync", json={"operaciones": []}, headers={"X-Funes": "0"})
    assert respuesta.status_code == 403


def test_registro_libre_cerrado(aplicacion):
    cliente = TestClient(aplicacion)
    respuesta = cliente.post("/api/auth/registro", json={"email": "x@y.es", "contrasena": "una-contrasena-larga"}, headers={"X-Funes": "1"})
    assert respuesta.status_code == 403


def test_un_usuario_no_ve_ni_edita_datos_del_otro(funes, amigo):
    receta = funes.get("/api/recetas").json()["recetas"][0]
    assert amigo.get(f"/api/recetas/{receta['id']}").status_code == 404
    assert amigo.put(f"/api/recetas/{receta['id']}", json={"nombre": "Robada"}).status_code == 404
    assert funes.get(f"/api/recetas/{receta['id']}").json()["receta"]["nombre"] == receta["nombre"]
    comida = funes.get("/api/menu/dia?fecha=2026-11-23").json()["comidas"][0]
    assert amigo.patch(f"/api/menu/comidas/{comida['id']}", json={"hora": "03:00"}).status_code == 404
    r = amigo.post("/api/sync", json={"operaciones": [{"id_operacion": "robo", "tipo": "consumo.crear", "carga": {"tipo": "previsto", "comida_planificada_id": comida["id"]}}]}).json()
    assert r["resultados"][0]["estado"] == "error"
    plan = funes.get("/api/menu/semana?fecha=2026-11-23").json()["plan"]["id"]
    assert amigo.get(f"/api/menu/{plan}/compra").status_code == 404
    alimento = funes.get("/api/alimentos").json()["alimentos"][0]
    assert amigo.put(f"/api/despensa/{alimento['id']}", json={"cantidad": 5}).status_code == 404
    funes.post("/api/sync", json={"operaciones": [{"id_operacion": "mf", "tipo": "medicion.crear", "carga": {"id_cliente": "mf1", "fecha": "2026-11-24", "tipo": "peso", "valor": 111.0}}]})
    medida = funes.get("/api/mediciones").json()["mediciones"][0]
    r = amigo.post("/api/sync", json={"operaciones": [{"id_operacion": "borra", "tipo": "medicion.borrar", "carga": {"id": medida["id"]}}]}).json()
    assert r["resultados"][0]["estado"] == "error"
    assert len(funes.get("/api/mediciones").json()["mediciones"]) == len([m for m in funes.get("/api/mediciones").json()["mediciones"]])
    assert all(m["id"] != medida["id"] for m in amigo.get("/api/mediciones").json()["mediciones"])
    repetido = amigo.post("/api/sync", json={"operaciones": [{"id_operacion": "mf", "tipo": "medicion.crear", "carga": {"fecha": "2026-11-24", "tipo": "peso", "valor": 56}}]}).json()
    assert repetido["resultados"][0]["estado"] == "error"


def test_fotos_privadas(funes, amigo):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = funes.post("/api/fotos", data={"fecha": "2026-11-24"}, files={"archivo": ("f.png", png, "image/png")})
    foto_id = r.json()["id"]
    assert funes.get(f"/api/fotos/{foto_id}/archivo").status_code == 200
    assert "no-store" in funes.get(f"/api/fotos/{foto_id}/archivo").headers["cache-control"]
    assert amigo.get(f"/api/fotos/{foto_id}/archivo").status_code == 404
    assert amigo.delete(f"/api/fotos/{foto_id}").status_code == 404
    assert TestClient(funes.app).get(f"/api/fotos/{foto_id}/archivo").status_code == 401


def test_exportacion_solo_propia(funes, amigo):
    datos_amigo = amigo.get("/api/exportar/json").json()
    nombres = {r["nombre"] for r in datos_amigo["recetas"]}
    assert "Pollo con arroz y verduras" not in nombres
    assert datos_amigo["perfil"]["nombre"] == "Amigo de Funes"
    assert all(m["usuario_id"] == amigo.usuario_id for m in datos_amigo["mediciones"])


def test_limite_de_intentos(aplicacion, funes):
    cliente = TestClient(aplicacion)
    cliente.headers.update({"X-Funes": "1"})
    for(_) in range(5):
        assert cliente.post("/api/auth/acceso", json={"email": "funes@example.com", "contrasena": "mala"}).status_code == 401
    assert cliente.post("/api/auth/acceso", json={"email": "funes@example.com", "contrasena": CONTRASENA}).status_code == 429


def test_totp_y_codigos_de_recuperacion(aplicacion, funes):
    secreto = funes.post("/api/auth/totp/configurar").json()["secreto"]
    codigos = funes.post("/api/auth/totp/activar", json={"codigo": pyotp.TOTP(secreto).now()}).json()["codigos_recuperacion"]
    cliente = TestClient(aplicacion)
    cliente.headers.update({"X-Funes": "1"})
    assert cliente.post("/api/auth/acceso", json={"email": "funes@example.com", "contrasena": CONTRASENA}).json()["requiere_totp"] is True
    assert cliente.get("/api/perfil").status_code == 401
    assert cliente.post("/api/auth/segundo-factor", json={"codigo": "000000"}).status_code == 401
    assert cliente.post("/api/auth/segundo-factor", json={"recuperacion": codigos[0]}).status_code == 200
    assert cliente.get("/api/perfil").status_code == 200
    otro = TestClient(aplicacion)
    otro.headers.update({"X-Funes": "1"})
    otro.post("/api/auth/acceso", json={"email": "funes@example.com", "contrasena": CONTRASENA})
    assert otro.post("/api/auth/segundo-factor", json={"recuperacion": codigos[0]}).status_code == 401
    assert otro.post("/api/auth/segundo-factor", json={"codigo": pyotp.TOTP(secreto).now()}).status_code == 200


def test_invitacion_un_solo_uso_y_caducidad(aplicacion, fabrica, funes):
    bd = fabrica()
    token = crear_invitacion(bd, "amigo", 72)
    caducado = crear_invitacion(bd, "amigo", 1)
    invitacion = bd.query(Invitacion).order_by(Invitacion.id.desc()).first()
    invitacion.expira_en = ahora_utc() - timedelta(minutes=1)
    bd.commit()
    bd.close()
    cliente = TestClient(aplicacion)
    cliente.headers.update({"X-Funes": "1"})
    vista = cliente.get(f"/api/invitaciones/{token}").json()
    assert vista == {"nombre_provisional": "Amigo de Funes", "expira_en": vista["expira_en"]}
    assert cliente.post(f"/api/invitaciones/{caducado}/activar", json={"email": "z@z.es", "contrasena": "contrasena-amigo-1"}).status_code == 410
    r = cliente.post(f"/api/invitaciones/{token}/activar", json={"email": "amigo2@example.com", "contrasena": "contrasena-amigo-1"})
    assert r.status_code == 200
    assert cliente.get("/api/perfil").json()["perfil"]["modo_objetivo"] == "ganar"
    otro = TestClient(aplicacion)
    otro.headers.update({"X-Funes": "1"})
    assert otro.post(f"/api/invitaciones/{token}/activar", json={"email": "amigo3@example.com", "contrasena": "contrasena-amigo-1"}).status_code == 410
    assert "Pollo con arroz y verduras" in {r["nombre"] for r in funes.get("/api/recetas").json()["recetas"]}


def test_borrar_cuenta_del_amigo_no_toca_a_funes(funes, amigo):
    antes = funes.get("/api/exportar/json").json()
    assert amigo.post("/api/cuenta/borrar", json={"contrasena": CONTRASENA, "confirmacion": "BORRAR"}).status_code == 200
    despues = funes.get("/api/exportar/json").json()
    for(tabla) in ("recetas", "comidas_planificadas", "mediciones", "rutinas", "objetivos"):
        assert len(antes[tabla]) == len(despues[tabla]), tabla
