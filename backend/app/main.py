import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app import avisos
from app.config import configuracion
from app.db import FabricaSesion, obtener_bd
from app.modelos import Usuario
from app.rutas import admin, auth, avisos as rutas_avisos, cocina, cuenta, gym, menu, perfil, progreso, sync
from app.seguridad import usuario_actual

METODOS_SEGUROS = ("GET", "HEAD", "OPTIONS")
RUTAS_SIN_CABECERA = ("/api/avisos/procesar",)


@asynccontextmanager
async def ciclo_vida(aplicacion: FastAPI):
    if(configuracion.migrar_al_arrancar and not configuracion.falta_bd_persistente):
        from app import migraciones
        from app.db import motor
        migraciones.aplicar(motor)
    tarea = None
    if(configuracion.avisos_activos and getattr(aplicacion.state, "planificador", True)):
        tarea = asyncio.create_task(avisos.bucle_avisos(FabricaSesion))
    yield
    if(tarea is not None):
        tarea.cancel()


def crear_aplicacion(planificador: bool = True) -> FastAPI:
    aplicacion = FastAPI(title="Funes Fit", lifespan=ciclo_vida, docs_url=None, redoc_url=None, openapi_url=None)
    aplicacion.state.planificador = planificador

    @aplicacion.middleware("http")
    async def proteccion(peticion: Request, siguiente):
        if(configuracion.falta_bd_persistente and peticion.url.path.startswith("/api/")):
            return JSONResponse({"detail": "Falta conectar la base de datos (DATABASE_URL de Neon) en Vercel. Sin ella los datos se perderían."}, status_code=503)
        if(peticion.url.path.startswith("/api/") and peticion.method not in METODOS_SEGUROS and peticion.url.path not in RUTAS_SIN_CABECERA and peticion.headers.get("x-funes") != "1"):
            return JSONResponse({"detail": "Petición no permitida"}, status_code=403)
        respuesta = await siguiente(peticion)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
        if(peticion.url.path.startswith("/api/")):
            respuesta.headers.setdefault("Cache-Control", "no-store")
        return respuesta

    for(modulo) in (auth, perfil, menu, cocina, gym, progreso, sync, rutas_avisos, cuenta, admin):
        aplicacion.include_router(modulo.enrutador)

    @aplicacion.get("/api/salud")
    def salud() -> dict:
        return {"ok": True}

    @aplicacion.get("/api/hoy")
    def hoy(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
        comidas = menu.dia(None, usuario, bd)
        entreno = gym.dia(comidas["fecha"], usuario, bd)
        diario = progreso.diario(comidas["fecha"], usuario, bd)
        datos_perfil = perfil.perfil_de(bd, usuario.id)
        return {
            "fecha": comidas["fecha"],
            "texto_fecha": comidas["texto_fecha"],
            "nombre": datos_perfil.nombre,
            "modo_objetivo": datos_perfil.modo_objetivo,
            "plan_aceptado": datos_perfil.plan_aceptado,
            "pendientes": len(perfil.preguntas_pendientes(datos_perfil)),
            "menu": comidas,
            "entreno": entreno,
            "diario": diario["entrada"],
        }

    @aplicacion.exception_handler(ValueError)
    async def error_valor(peticion: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=422)

    frontend = configuracion.directorio_frontend
    if(configuracion.servir_frontend and frontend.exists()):
        @aplicacion.get("/{ruta:path}", include_in_schema=False)
        def estaticos(ruta: str):
            if(ruta.startswith("api/")):
                return JSONResponse({"detail": "No encontrado"}, status_code=404)
            archivo = (frontend / ruta).resolve()
            if(ruta and archivo.is_file() and frontend in archivo.parents):
                cabeceras = {"Cache-Control": "no-cache"} if archivo.name in ("sw.js", "index.html", "manifest.webmanifest") else {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in archivo.as_posix() else {}
                return FileResponse(archivo, headers=cabeceras)
            return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    return aplicacion


app = crear_aplicacion()
