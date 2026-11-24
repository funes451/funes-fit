import argparse
import getpass
import json
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import RAIZ_BACKEND, configuracion


def ruta_bd() -> Path:
    if(not configuracion.url_bd.startswith("sqlite:///")):
        raise SystemExit("Las copias automáticas de este comando solo admiten SQLite. Con PostgreSQL usa pg_dump.")
    return Path(configuracion.url_bd.replace("sqlite:///", "", 1))


def copia_seguridad(motivo: str = "manual") -> Path | None:
    origen = ruta_bd()
    if(not origen.exists()):
        print("No hay base de datos todavía: no se hace copia.")
        return None
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = configuracion.directorio_datos / "copias" / f"funes-fit-{marca}-{motivo}.zip"
    temporal = configuracion.directorio_datos / "copias" / f"bd-{marca}.db"
    conexion = sqlite3.connect(origen)
    copia = sqlite3.connect(temporal)
    with copia:
        conexion.backup(copia)
    copia.close()
    conexion.close()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as archivo:
        archivo.write(temporal, "funes_fit.db")
        for(foto) in (configuracion.directorio_datos / "fotos").glob("*"):
            archivo.write(foto, f"fotos/{foto.name}")
        archivo.writestr("LEEME.txt", "Copia de Funes Fit: base de datos SQLite completa (todas las cuentas) y carpeta de fotos privadas.\nRestaurar: python -m app.cli restaurar <este archivo>\n")
    temporal.unlink()
    print(f"Copia creada: {destino}")
    return destino


def restaurar(archivo: str) -> None:
    origen = Path(archivo)
    if(not origen.exists()):
        raise SystemExit("No existe el archivo de copia")
    copia_seguridad("antes-de-restaurar")
    with zipfile.ZipFile(origen) as zipf:
        nombres = zipf.namelist()
        if("funes_fit.db" not in nombres):
            raise SystemExit("La copia no contiene funes_fit.db")
        destino = ruta_bd()
        for(extension) in ("-wal", "-shm"):
            Path(str(destino) + extension).unlink(missing_ok=True)
        with zipf.open("funes_fit.db") as entrada, open(destino, "wb") as salida:
            shutil.copyfileobj(entrada, salida)
        for(nombre) in nombres:
            if(nombre.startswith("fotos/") and not nombre.endswith("/")):
                with zipf.open(nombre) as entrada, open(configuracion.directorio_datos / "fotos" / Path(nombre).name, "wb") as salida:
                    shutil.copyfileobj(entrada, salida)
    print("Copia restaurada. Reinicia el servidor.")


def migrar() -> None:
    from app import migraciones
    from app.db import motor
    if(migraciones.esta_al_dia(motor)):
        print("La base de datos ya está al día.")
        return
    if(configuracion.url_bd.startswith("sqlite") and ruta_bd().exists()):
        copia_seguridad("antes-de-migrar")
    migraciones.aplicar(motor)
    print("Base de datos actualizada.")
    verificar()


def verificar() -> None:
    from app.db import FabricaSesion
    from app.modelos import Consumo, Medicion, PlanSemana, Receta, Rutina, SesionEntreno, Usuario, Perfil
    bd = FabricaSesion()
    try:
        for(u) in bd.query(Usuario).order_by(Usuario.id).all():
            perfil = bd.get(Perfil, u.id)
            print(f"Cuenta {u.id} ({u.email}) · perfil «{perfil.nombre if perfil else '—'}» · modo {perfil.modo_objetivo if perfil else '—'} · recetas {bd.query(Receta).filter(Receta.usuario_id == u.id).count()} · semanas {bd.query(PlanSemana).filter(PlanSemana.usuario_id == u.id).count()} · rutinas {bd.query(Rutina).filter(Rutina.usuario_id == u.id).count()} · consumos {bd.query(Consumo).filter(Consumo.usuario_id == u.id).count()} · medidas {bd.query(Medicion).filter(Medicion.usuario_id == u.id).count()} · sesiones {bd.query(SesionEntreno).filter(SesionEntreno.usuario_id == u.id).count()}")
    finally:
        bd.close()


def crear_cuenta(email: str, plan: str, contrasena: str | None) -> None:
    from app import seguridad
    from app.db import FabricaSesion
    from app.modelos import Usuario
    from app.semilla import sembrar_usuario
    bd = FabricaSesion()
    try:
        email = email.strip().lower()
        if(bd.query(Usuario).filter(Usuario.email == email).first() is not None):
            raise SystemExit("Ya existe una cuenta con ese correo")
        if(contrasena is None):
            contrasena = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
            if(contrasena != getpass.getpass("Repite la contraseña: ")):
                raise SystemExit("Las contraseñas no coinciden")
        if(len(contrasena) < seguridad.LONGITUD_MINIMA_CONTRASENA):
            raise SystemExit("La contraseña es demasiado corta")
        copia_seguridad("antes-de-alta")
        usuario = Usuario(email=email, hash_contrasena=seguridad.hash_contrasena(contrasena), codigos_recuperacion=[])
        bd.add(usuario)
        bd.commit()
        print(json.dumps(sembrar_usuario(bd, usuario.id, plan), ensure_ascii=False))
        print(f"Cuenta {usuario.id} creada para {email} con el plan «{plan}».")
    finally:
        bd.close()


def sembrar_de_nuevo(email: str, plan: str) -> None:
    from app.db import FabricaSesion
    from app.modelos import Usuario
    from app.semilla import sembrar_usuario
    bd = FabricaSesion()
    try:
        usuario = bd.query(Usuario).filter(Usuario.email == email.strip().lower()).first()
        if(usuario is None):
            raise SystemExit("No existe esa cuenta")
        copia_seguridad("antes-de-recargar-plan")
        print(json.dumps(sembrar_usuario(bd, usuario.id, plan), ensure_ascii=False))
        print("Carga completada. Lo que ya existía no se ha duplicado ni modificado.")
    finally:
        bd.close()


def invitar(plan: str, horas: int, base_url: str) -> None:
    from app.db import FabricaSesion
    from app.rutas.cuenta import crear_invitacion
    bd = FabricaSesion()
    try:
        token = crear_invitacion(bd, plan, horas)
    finally:
        bd.close()
    print("Enlace de un solo uso (no lo publiques; no contiene datos personales):")
    print(f"{base_url.rstrip('/')}/#/invitacion/{token}")
    print(f"Caduca en {horas} horas. No se ha enviado a nadie.")


def generar_vapid() -> None:
    import base64
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    vapid = Vapid()
    vapid.generate_keys()
    privada = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    publica = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    codificar = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    print("Añade estas líneas a backend/.env y reinicia el servidor:")
    print(f"FUNES_VAPID_PUBLICA={codificar(publica)}")
    print(f"FUNES_VAPID_PRIVADA={codificar(privada)}")


def avisos_una_vez() -> None:
    from app.avisos import procesar_avisos
    from app.db import FabricaSesion
    bd = FabricaSesion()
    try:
        print(json.dumps(procesar_avisos(bd), ensure_ascii=False))
    finally:
        bd.close()


def principal(argumentos: list[str] | None = None) -> None:
    analizador = argparse.ArgumentParser(prog="python -m app.cli", description="Herramientas de Funes Fit")
    sub = analizador.add_subparsers(dest="orden", required=True)
    alta = sub.add_parser("crear-cuenta", help="Crea una cuenta y carga su plan")
    alta.add_argument("--email", required=True)
    alta.add_argument("--plan", choices=["funes", "amigo", "vacio"], required=True)
    alta.add_argument("--contrasena")
    recarga = sub.add_parser("cargar-plan", help="Vuelve a cargar el plan inicial sin duplicar ni borrar")
    recarga.add_argument("--email", required=True)
    recarga.add_argument("--plan", choices=["funes", "amigo"], required=True)
    inv = sub.add_parser("invitar", help="Genera un enlace de invitación de un solo uso")
    inv.add_argument("--plan", choices=["amigo", "funes", "vacio"], required=True)
    inv.add_argument("--horas", type=int, default=72)
    inv.add_argument("--url", default="http://localhost:8000")
    sub.add_parser("migrar", help="Copia de seguridad + migraciones + verificación")
    sub.add_parser("verificar", help="Resumen de datos por cuenta")
    sub.add_parser("copia", help="Copia de seguridad de base de datos y fotos")
    rest = sub.add_parser("restaurar", help="Restaura una copia")
    rest.add_argument("archivo")
    sub.add_parser("generar-vapid", help="Genera claves para Web Push")
    sub.add_parser("avisos", help="Procesa los avisos pendientes una vez")
    args = analizador.parse_args(argumentos)
    if(args.orden == "crear-cuenta"):
        crear_cuenta(args.email, args.plan, args.contrasena)
    elif(args.orden == "cargar-plan"):
        sembrar_de_nuevo(args.email, args.plan)
    elif(args.orden == "invitar"):
        invitar(args.plan, args.horas, args.url)
    elif(args.orden == "migrar"):
        migrar()
    elif(args.orden == "verificar"):
        verificar()
    elif(args.orden == "copia"):
        copia_seguridad()
    elif(args.orden == "restaurar"):
        restaurar(args.archivo)
    elif(args.orden == "generar-vapid"):
        generar_vapid()
    elif(args.orden == "avisos"):
        avisos_una_vez()


if(__name__ == "__main__"):
    principal(sys.argv[1:])
