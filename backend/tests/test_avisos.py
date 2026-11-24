from datetime import datetime, timezone

from app.avisos import procesar_avisos
from app.modelos import Perfil, Recordatorio, SuscripcionPush


class Enviador:
    def __init__(self, respuesta: str = "ok") -> None:
        self.envios = []
        self.respuesta = respuesta

    def __call__(self, suscripcion, carga):
        self.envios.append((suscripcion.usuario_id, carga))
        return self.respuesta


def preparar(bd, usuario_id, hora, dias=None, endpoint="https://push.example/funes"):
    bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario_id).update({"activo": False})
    r = Recordatorio(usuario_id=usuario_id, tipo="comida", hora=hora, dias=dias if dias is not None else list(range(7)), activo=True, texto_generico=True)
    bd.add(r)
    bd.add(SuscripcionPush(usuario_id=usuario_id, endpoint=endpoint, p256dh="clave", auth="auth"))
    bd.commit()
    return r


def test_hora_local_madrid_y_sin_duplicados(bd, funes):
    preparar(bd, funes.usuario_id, "13:45")
    enviador = Enviador()
    assert procesar_avisos(bd, datetime(2026, 11, 24, 12, 40, tzinfo=timezone.utc), enviador) == []
    enviados = procesar_avisos(bd, datetime(2026, 11, 24, 12, 46, tzinfo=timezone.utc), enviador)
    assert len(enviados) == 1 and enviados[0]["estado"] == "enviado"
    procesar_avisos(bd, datetime(2026, 11, 24, 12, 50, tzinfo=timezone.utc), enviador)
    assert len(enviador.envios) == 1
    assert enviador.envios[0][1]["cuerpo"] == "Tienes un recordatorio en Funes Fit"


def test_cambio_de_hora_primavera_y_otono(bd, funes):
    perfil = bd.get(Perfil, funes.usuario_id)
    perfil.silencio_inicio = "00:00"
    perfil.silencio_fin = "00:00"
    bd.commit()
    preparar(bd, funes.usuario_id, "02:30")
    enviador = Enviador()
    procesar_avisos(bd, datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc), enviador)
    assert len(enviador.envios) == 1
    procesar_avisos(bd, datetime(2026, 10, 25, 0, 31, tzinfo=timezone.utc), enviador)
    procesar_avisos(bd, datetime(2026, 10, 25, 1, 31, tzinfo=timezone.utc), enviador)
    assert len(enviador.envios) == 2


def test_franja_de_silencio(bd, funes):
    perfil = bd.get(Perfil, funes.usuario_id)
    perfil.silencio_inicio = "13:00"
    perfil.silencio_fin = "15:00"
    bd.commit()
    preparar(bd, funes.usuario_id, "13:45")
    enviador = Enviador()
    resultado = procesar_avisos(bd, datetime(2026, 11, 24, 12, 46, tzinfo=timezone.utc), enviador)
    assert resultado[0]["estado"] == "silencio" and enviador.envios == []


def test_sin_suscripcion_y_caducada(bd, funes):
    r = Recordatorio(usuario_id=funes.usuario_id, tipo="registro", hora="21:30", dias=list(range(7)), activo=True)
    bd.add(r)
    bd.commit()
    resultado = procesar_avisos(bd, datetime(2026, 11, 24, 20, 31, tzinfo=timezone.utc), Enviador())
    assert resultado[0]["estado"] == "sin_suscripcion"
    preparar(bd, funes.usuario_id, "10:00")
    procesar_avisos(bd, datetime(2026, 11, 25, 9, 1, tzinfo=timezone.utc), Enviador("caducada"))
    assert bd.query(SuscripcionPush).filter(SuscripcionPush.usuario_id == funes.usuario_id).count() == 0


def test_aviso_llega_al_usuario_correcto(bd, funes, amigo):
    preparar(bd, funes.usuario_id, "13:45", endpoint="https://push.example/movil-funes")
    bd.add(SuscripcionPush(usuario_id=amigo.usuario_id, endpoint="https://push.example/movil-amigo", p256dh="k", auth="a"))
    bd.commit()
    enviador = Enviador()
    procesar_avisos(bd, datetime(2026, 11, 24, 12, 46, tzinfo=timezone.utc), enviador)
    assert [u for u, _ in enviador.envios] == [funes.usuario_id]
    assert enviador.envios[0][1]["usuario"] == funes.usuario_id


def test_mismo_dispositivo_cambia_de_cuenta(funes, amigo):
    suscripcion = {"endpoint": "https://push.example/compartido", "keys": {"p256dh": "k", "auth": "a"}}
    assert funes.post("/api/avisos/suscripciones", json=suscripcion).status_code == 200
    assert amigo.post("/api/avisos/suscripciones", json=suscripcion).status_code == 200
    assert funes.get("/api/avisos").json()["suscripciones"] == 0
    assert amigo.get("/api/avisos").json()["suscripciones"] == 1
    assert amigo.post("/api/avisos/suscripciones/borrar", json={"endpoint": suscripcion["endpoint"]}).json()["borradas"] == 1


def test_prueba_sin_dispositivos_es_honesta(funes):
    respuesta = funes.post("/api/avisos/prueba")
    assert respuesta.status_code == 409 and "dispositivo" in respuesta.json()["detail"]


def test_claves_vapid_se_generan_una_vez(funes, amigo):
    primera = funes.get("/api/avisos").json()["clave_publica"]
    segunda = amigo.get("/api/avisos").json()["clave_publica"]
    assert primera == segunda and len(primera) > 80


def test_endpoint_de_cron(aplicacion, bd, funes, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import configuracion
    cliente = TestClient(aplicacion)
    monkeypatch.setattr(configuracion, "clave_cron", "")
    assert cliente.post("/api/avisos/procesar").status_code == 503
    monkeypatch.setattr(configuracion, "clave_cron", "secreto-cron-largo")
    assert cliente.post("/api/avisos/procesar", headers={"Authorization": "Bearer otra"}).status_code == 401
    assert cliente.get("/api/avisos/procesar?clave=secreto-cron-largo").json()["ok"] is True
    assert cliente.post("/api/avisos/procesar", headers={"Authorization": "Bearer secreto-cron-largo"}).status_code == 200


def test_calendario_alternativo(funes):
    rid = funes.get("/api/avisos").json()["recordatorios"][0]["id"]
    funes.put(f"/api/avisos/recordatorios/{rid}", json={"activo": True, "hora": "13:45"})
    ics = funes.get("/api/avisos/calendario.ics").text
    assert "RRULE:FREQ=WEEKLY" in ics and "TZID=Europe/Madrid" in ics
