from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.config import RAIZ_BACKEND

BLOQUEO_POSTGRES = 4711202611


def configuracion_alembic(url: str | None = None) -> Config:
    config = Config(str(RAIZ_BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ_BACKEND / "migraciones"))
    if(url):
        config.attributes["url"] = url
    return config


def revision_actual(motor) -> str | None:
    with motor.connect() as conexion:
        return MigrationContext.configure(conexion).get_current_revision()


def revision_destino() -> str:
    return ScriptDirectory.from_config(configuracion_alembic()).get_current_head()


def esta_al_dia(motor) -> bool:
    return revision_actual(motor) == revision_destino()


def aplicar(motor) -> bool:
    if(esta_al_dia(motor)):
        return False
    config = configuracion_alembic()
    if(motor.dialect.name == "postgresql"):
        with motor.connect() as conexion:
            conexion.execute(text("SELECT pg_advisory_lock(:clave)"), {"clave": BLOQUEO_POSTGRES})
            try:
                if(MigrationContext.configure(conexion).get_current_revision() != revision_destino()):
                    config.attributes["conexion"] = conexion
                    command.upgrade(config, "head")
                    conexion.commit()
            finally:
                conexion.execute(text("SELECT pg_advisory_unlock(:clave)"), {"clave": BLOQUEO_POSTGRES})
                conexion.commit()
        return True
    command.upgrade(config, "head")
    return True
