from fastapi.testclient import TestClient

from app.config import configuracion, normalizar_url_bd


def cliente(aplicacion):
    c = TestClient(aplicacion)
    c.headers.update({"X-Funes": "1"})
    return c


def test_normalizar_url_de_neon():
    assert normalizar_url_bd("postgres://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalizar_url_bd("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalizar_url_bd("sqlite:///x.db") == "sqlite:///x.db"


def test_admin_desactivado_sin_clave(aplicacion, monkeypatch):
    monkeypatch.setattr(configuracion, "clave_admin", "")
    assert cliente(aplicacion).post("/api/admin/estado", json={"clave_admin": "x"}).status_code == 503


def test_admin_crea_cuentas_e_invitaciones(aplicacion, monkeypatch):
    monkeypatch.setattr(configuracion, "clave_admin", "clave-admin-de-prueba")
    c = cliente(aplicacion)
    assert c.post("/api/admin/estado", json={"clave_admin": "mala"}).status_code == 401
    r = c.post("/api/admin/cuentas", json={"clave_admin": "clave-admin-de-prueba", "email": "funes@x.es", "contrasena": "contrasena-larga-1", "plan": "funes"})
    assert r.status_code == 200 and r.json()["creados"]["plan"] == 1
    repetida = c.post("/api/admin/cuentas", json={"clave_admin": "clave-admin-de-prueba", "email": "otro@x.es", "contrasena": "contrasena-larga-1", "plan": "funes"})
    assert repetida.status_code == 409
    assert c.post("/api/admin/cuentas", json={"clave_admin": "clave-admin-de-prueba", "email": "a@x.es", "contrasena": "contrasena-larga-1", "plan": "amigo"}).status_code == 422
    invitacion = c.post("/api/admin/invitaciones", json={"clave_admin": "clave-admin-de-prueba", "plan": "amigo"}).json()
    token = invitacion["ruta"].split("/")[-1]
    activada = c.post(f"/api/invitaciones/{token}/activar", json={"email": "amigo@x.es", "contrasena": "contrasena-larga-2"})
    assert activada.status_code == 200
    estado = c.post("/api/admin/estado", json={"clave_admin": "clave-admin-de-prueba"}).json()
    assert [x["modo"] for x in estado["cuentas"]] == ["perder", "ganar"]
    recarga = c.post("/api/admin/recargar-plan", json={"clave_admin": "clave-admin-de-prueba", "email": "amigo@x.es", "plan": "amigo"}).json()
    assert all(v == 0 for v in recarga["creados"].values())


def test_admin_limita_intentos(aplicacion, monkeypatch):
    monkeypatch.setattr(configuracion, "clave_admin", "clave-admin-de-prueba")
    c = cliente(aplicacion)
    for(_) in range(5):
        c.post("/api/admin/estado", json={"clave_admin": "mala"})
    assert c.post("/api/admin/estado", json={"clave_admin": "clave-admin-de-prueba"}).status_code == 429


def test_fotos_en_base_de_datos(funes, amigo, monkeypatch):
    monkeypatch.setattr(configuracion, "fotos_en_bd", True)
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 32
    foto_id = funes.post("/api/fotos", data={"fecha": "2026-11-24"}, files={"archivo": ("f.png", png, "image/png")}).json()["id"]
    assert not any(p.name.startswith(f"{funes.usuario_id}_") and p.stat().st_size == len(png) for p in (configuracion.directorio_datos / "fotos").glob("*") if False)
    assert funes.get(f"/api/fotos/{foto_id}/archivo").content == png
    assert amigo.get(f"/api/fotos/{foto_id}/archivo").status_code == 404
    exportado = funes.get("/api/exportar/json").json()
    assert "contenido" not in exportado["fotos"][0]
    grande = b"0" * (4 * 1024 * 1024 + 1)
    assert funes.post("/api/fotos", data={"fecha": "2026-11-24"}, files={"archivo": ("g.jpg", grande, "image/jpeg")}).status_code == 413


def test_ip_real_tras_proxy(monkeypatch):
    from starlette.requests import Request
    from app.seguridad import ip_cliente
    peticion = Request({"type": "http", "headers": [(b"x-forwarded-for", b"203.0.113.7, 10.0.0.1")], "client": ("10.0.0.1", 1)})
    monkeypatch.setattr(configuracion, "confiar_proxy", True)
    assert ip_cliente(peticion) == "203.0.113.7"
    monkeypatch.setattr(configuracion, "confiar_proxy", False)
    assert ip_cliente(peticion) == "10.0.0.1"
