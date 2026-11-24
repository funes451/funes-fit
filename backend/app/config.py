import os
import tempfile
from pathlib import Path


def _booleano(valor: str | None, defecto: bool) -> bool:
    if(valor is None or valor == ""):
        return defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


def _cargar_env(ruta: Path) -> None:
    if(not ruta.exists()):
        return
    for(linea) in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if(linea == "" or linea.startswith("#") or "=" not in linea):
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if(clave not in os.environ):
            os.environ[clave] = valor


def normalizar_url_bd(url: str) -> str:
    if(url.startswith("postgres://")):
        url = "postgresql://" + url[len("postgres://"):]
    if(url.startswith("postgresql://")):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _directorio_escribible(preferido: Path) -> Path:
    try:
        preferido.mkdir(parents=True, exist_ok=True)
        prueba = preferido / ".escritura"
        prueba.write_text("ok")
        prueba.unlink()
        return preferido
    except OSError:
        alternativa = Path(tempfile.gettempdir()) / "funesfit"
        alternativa.mkdir(parents=True, exist_ok=True)
        return alternativa


RAIZ_BACKEND = Path(__file__).resolve().parent.parent
_cargar_env(RAIZ_BACKEND / ".env")


class Configuracion:
    def __init__(self) -> None:
        self.en_vercel = _booleano(os.environ.get("VERCEL"), False)
        self.directorio_datos = _directorio_escribible(Path(os.environ.get("FUNES_DATOS", str(RAIZ_BACKEND / "datos"))).resolve())
        url_externa = os.environ.get("FUNES_URL_BD") or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
        self.url_bd = normalizar_url_bd(url_externa) if url_externa else f"sqlite:///{(self.directorio_datos / 'funes_fit.db').as_posix()}"
        self.es_postgres = self.url_bd.startswith("postgresql")
        self.cookie_segura = _booleano(os.environ.get("FUNES_COOKIE_SEGURA"), self.en_vercel)
        self.confiar_proxy = _booleano(os.environ.get("FUNES_CONFIAR_PROXY"), self.en_vercel)
        self.permitir_registro = _booleano(os.environ.get("FUNES_PERMITIR_REGISTRO"), False)
        self.duracion_sesion_dias = int(os.environ.get("FUNES_DURACION_SESION_DIAS", "30"))
        self.vapid_publica = os.environ.get("FUNES_VAPID_PUBLICA", "")
        self.vapid_privada = os.environ.get("FUNES_VAPID_PRIVADA", "")
        self.vapid_contacto = os.environ.get("FUNES_VAPID_CONTACTO", "mailto:admin@localhost")
        self.avisos_activos = _booleano(os.environ.get("FUNES_AVISOS_ACTIVOS"), not self.en_vercel)
        self.intervalo_avisos_s = int(os.environ.get("FUNES_INTERVALO_AVISOS_S", "30"))
        self.clave_admin = os.environ.get("FUNES_CLAVE_ADMIN", "")
        self.clave_cron = os.environ.get("FUNES_CLAVE_CRON") or os.environ.get("CRON_SECRET") or ""
        self.fotos_en_bd = _booleano(os.environ.get("FUNES_FOTOS_EN_BD"), self.es_postgres or self.en_vercel)
        self.migrar_al_arrancar = _booleano(os.environ.get("FUNES_MIGRAR_AL_ARRANCAR"), self.en_vercel)
        self.directorio_frontend = Path(os.environ.get("FUNES_FRONTEND", str(RAIZ_BACKEND.parent / "public"))).resolve()
        self.servir_frontend = _booleano(os.environ.get("FUNES_SERVIR_FRONTEND"), True)
        self.falta_bd_persistente = self.en_vercel and not self.es_postgres
        self.zona_horaria = os.environ.get("FUNES_ZONA_HORARIA", "Europe/Madrid")
        for(sub) in ("fotos", "copias"):
            try:
                (self.directorio_datos / sub).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass


configuracion = Configuracion()
