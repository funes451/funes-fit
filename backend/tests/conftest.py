import os
import sys
import tempfile
from pathlib import Path

DIRECTORIO = tempfile.mkdtemp(prefix="funesfit-pruebas-")
os.environ["FUNES_DATOS"] = DIRECTORIO
os.environ["FUNES_AVISOS_ACTIVOS"] = "0"
os.environ["FUNES_FRONTEND"] = str(Path(DIRECTORIO) / "sin-frontend")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import db as modulo_db
from app.db import Base, crear_motor, obtener_bd
from app.main import crear_aplicacion
from app.modelos import Usuario
from app.seguridad import hash_contrasena
from app.semilla import sembrar_usuario

CONTRASENA = "contrasena-segura-1"


URL_PRUEBAS = os.environ.get("FUNES_PRUEBAS_BD")


@pytest.fixture()
def fabrica(tmp_path):
    if(URL_PRUEBAS):
        from app.config import normalizar_url_bd
        motor = crear_motor(normalizar_url_bd(URL_PRUEBAS))
        Base.metadata.drop_all(motor)
    else:
        motor = crear_motor(f"sqlite:///{(tmp_path / 'prueba.db').as_posix()}")
    Base.metadata.create_all(motor)
    fabrica_sesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    yield fabrica_sesion
    motor.dispose()


@pytest.fixture()
def bd(fabrica):
    sesion = fabrica()
    yield sesion
    sesion.close()


@pytest.fixture()
def aplicacion(fabrica):
    app = crear_aplicacion(planificador=False)

    def bd_prueba():
        sesion = fabrica()
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[obtener_bd] = bd_prueba
    return app


def crear_usuario(fabrica, email: str, plan: str) -> int:
    sesion = fabrica()
    usuario = Usuario(email=email, hash_contrasena=hash_contrasena(CONTRASENA), codigos_recuperacion=[])
    sesion.add(usuario)
    sesion.commit()
    sembrar_usuario(sesion, usuario.id, plan)
    identificador = usuario.id
    sesion.close()
    return identificador


def cliente_para(aplicacion, email: str) -> TestClient:
    cliente = TestClient(aplicacion)
    cliente.headers.update({"X-Funes": "1"})
    respuesta = cliente.post("/api/auth/acceso", json={"email": email, "contrasena": CONTRASENA})
    assert respuesta.status_code == 200, respuesta.text
    return cliente


@pytest.fixture()
def funes(aplicacion, fabrica):
    identificador = crear_usuario(fabrica, "funes@example.com", "funes")
    cliente = cliente_para(aplicacion, "funes@example.com")
    cliente.usuario_id = identificador
    return cliente


@pytest.fixture()
def amigo(aplicacion, fabrica):
    identificador = crear_usuario(fabrica, "amigo@example.com", "amigo")
    cliente = cliente_para(aplicacion, "amigo@example.com")
    cliente.usuario_id = identificador
    return cliente
