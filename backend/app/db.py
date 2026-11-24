from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import configuracion

Base = declarative_base()


def crear_motor(url: str):
    if(url.startswith("sqlite")):
        motor = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(motor, "connect")
        def _pragmas(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return motor
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=240, connect_args={"connect_timeout": 10})


motor = crear_motor(configuracion.url_bd)
FabricaSesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obtener_bd():
    bd = FabricaSesion()
    try:
        yield bd
    finally:
        bd.close()
