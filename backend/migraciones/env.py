import sys
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import modelos
from app.config import configuracion
from app.db import Base, crear_motor

target_metadata = Base.metadata


def ejecutar_sin_conexion() -> None:
    context.configure(url=configuracion.url_bd, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar(conexion) -> None:
    context.configure(connection=conexion, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_con_conexion() -> None:
    existente = context.config.attributes.get("conexion")
    if(existente is not None):
        ejecutar(existente)
        return
    motor = crear_motor(context.config.attributes.get("url") or configuracion.url_bd)
    with motor.connect() as conexion:
        ejecutar(conexion)
        conexion.commit()


if(context.is_offline_mode()):
    ejecutar_sin_conexion()
else:
    ejecutar_con_conexion()
