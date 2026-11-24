import csv
import io
import uuid
from datetime import date, datetime

from sqlalchemy import Date
from sqlalchemy.orm import Session

from app.calculos.fechas import interpretar_fecha
from app.calculos.numeros import interpretar_numero
from app.modelos import (
    Alimento,
    CambioMenu,
    CampoPersonalizado,
    ComidaPlanificada,
    Compra,
    Consumo,
    Ejercicio,
    EjercicioRutina,
    EntradaDiario,
    Evento,
    FechaHoraUTC,
    Foto,
    IngredienteReceta,
    ItemDespensa,
    Medicion,
    Objetivo,
    Perfil,
    PlanSemana,
    Producto,
    Receta,
    Recordatorio,
    Rutina,
    SesionEntreno,
)

VERSION_FORMATO = 1

TABLAS = [
    ("objetivos", Objetivo),
    ("alimentos", Alimento),
    ("productos", Producto),
    ("recetas", Receta),
    ("planes_semana", PlanSemana),
    ("comidas_planificadas", ComidaPlanificada),
    ("consumos", Consumo),
    ("despensa", ItemDespensa),
    ("compras", Compra),
    ("ejercicios", Ejercicio),
    ("rutinas", Rutina),
    ("sesiones_entreno", SesionEntreno),
    ("eventos", Evento),
    ("mediciones", Medicion),
    ("diario", EntradaDiario),
    ("campos_personalizados", CampoPersonalizado),
    ("recordatorios", Recordatorio),
    ("fotos", Foto),
]


def _fila(objeto) -> dict:
    resultado = {}
    for(columna) in objeto.__table__.columns:
        if(columna.key == "contenido"):
            continue
        valor = getattr(objeto, columna.key)
        if(isinstance(valor, (date, datetime))):
            valor = valor.isoformat()
        resultado[columna.key] = valor
    return resultado


def exportar(bd: Session, usuario_id: int) -> dict:
    datos = {"formato": "funes-fit", "version_formato": VERSION_FORMATO, "exportado_en": datetime.now().isoformat(), "perfil": None}
    perfil = bd.get(Perfil, usuario_id)
    datos["perfil"] = _fila(perfil) if perfil else None
    for(nombre, modelo) in TABLAS:
        datos[nombre] = [_fila(o) for o in bd.query(modelo).filter(modelo.usuario_id == usuario_id).order_by(modelo.id).all()]
    recetas = [r["id"] for r in datos["recetas"]]
    datos["ingredientes_receta"] = [_fila(o) for o in bd.query(IngredienteReceta).filter(IngredienteReceta.receta_id.in_(recetas or [0])).all()]
    rutinas = [r["id"] for r in datos["rutinas"]]
    datos["rutina_ejercicios"] = [_fila(o) for o in bd.query(EjercicioRutina).filter(EjercicioRutina.rutina_id.in_(rutinas or [0])).all()]
    planes = [p["id"] for p in datos["planes_semana"]]
    datos["cambios_menu"] = [_fila(o) for o in bd.query(CambioMenu).filter(CambioMenu.plan_id.in_(planes or [0])).all()]
    datos["nota"] = "Las fotos se listan, pero sus imágenes no van dentro de este JSON. Descárgalas desde la app si quieres conservarlas."
    return datos


def _convertir(modelo, fila: dict, excluir: tuple) -> dict:
    valores = {}
    for(columna) in modelo.__table__.columns:
        clave = columna.key
        if(clave in excluir or clave not in fila):
            continue
        valor = fila[clave]
        if(valor is not None and isinstance(columna.type, FechaHoraUTC)):
            valor = datetime.fromisoformat(valor)
        elif(valor is not None and isinstance(columna.type, Date)):
            valor = date.fromisoformat(valor[:10])
        valores[clave] = valor
    return valores


def _id_cliente_libre(bd: Session, modelo, valor: str | None, usuario_id: int) -> tuple:
    if(not valor):
        return f"imp-{uuid.uuid4()}", False
    for(candidato) in (valor, f"i{usuario_id}-{valor}"[:64]):
        existente = bd.query(modelo).filter(modelo.id_cliente == candidato).first()
        if(existente is None):
            return candidato, False
        if(existente.usuario_id == usuario_id):
            return candidato, True
    return f"imp-{uuid.uuid4()}", False


def importar(bd: Session, usuario_id: int, datos: dict) -> dict:
    if(datos.get("formato") != "funes-fit"):
        raise ValueError("El archivo no es una exportación de Funes Fit")
    informe = {}
    mapa = {nombre: {} for nombre, _ in TABLAS}

    def contar(nombre: str, clave: str) -> None:
        informe.setdefault(nombre, {"creados": 0, "existentes": 0})
        informe[nombre][clave] = informe[nombre][clave] + 1

    for(fila) in datos.get("objetivos", []):
        existe = bd.query(Objetivo).filter(Objetivo.usuario_id == usuario_id, Objetivo.vigente_desde == date.fromisoformat(fila["vigente_desde"]), Objetivo.kcal == fila.get("kcal"), Objetivo.origen == fila["origen"]).first()
        if(existe is None):
            bd.add(Objetivo(usuario_id=usuario_id, **_convertir(Objetivo, fila, ("id", "usuario_id"))))
            contar("objetivos", "creados")
        else:
            contar("objetivos", "existentes")
    for(fila) in datos.get("alimentos", []):
        consulta = bd.query(Alimento).filter(Alimento.usuario_id == usuario_id)
        existe = consulta.filter(Alimento.codigo == fila["codigo"]).first() if fila.get("codigo") else consulta.filter(Alimento.nombre == fila["nombre"], Alimento.base == fila["base"]).first()
        if(existe is None):
            existe = Alimento(usuario_id=usuario_id, **_convertir(Alimento, fila, ("id", "usuario_id")))
            bd.add(existe)
            bd.flush()
            contar("alimentos", "creados")
        else:
            contar("alimentos", "existentes")
        mapa["alimentos"][fila["id"]] = existe.id
    for(fila) in datos.get("productos", []):
        alimento_id = mapa["alimentos"].get(fila["alimento_id"])
        if(alimento_id is None):
            continue
        consulta = bd.query(Producto).filter(Producto.usuario_id == usuario_id)
        existe = consulta.filter(Producto.codigo == fila["codigo"]).first() if fila.get("codigo") else consulta.filter(Producto.alimento_id == alimento_id, Producto.nombre == fila["nombre"]).first()
        if(existe is None):
            bd.add(Producto(usuario_id=usuario_id, **{**_convertir(Producto, fila, ("id", "usuario_id")), "alimento_id": alimento_id}))
            contar("productos", "creados")
        else:
            contar("productos", "existentes")
    nuevas_recetas = set()
    for(fila) in datos.get("recetas", []):
        consulta = bd.query(Receta).filter(Receta.usuario_id == usuario_id)
        existe = consulta.filter(Receta.codigo == fila["codigo"]).first() if fila.get("codigo") else consulta.filter(Receta.nombre == fila["nombre"]).first()
        if(existe is None):
            existe = Receta(usuario_id=usuario_id, **_convertir(Receta, fila, ("id", "usuario_id")))
            bd.add(existe)
            bd.flush()
            nuevas_recetas.add(fila["id"])
            contar("recetas", "creados")
        else:
            contar("recetas", "existentes")
        mapa["recetas"][fila["id"]] = existe.id
    for(fila) in datos.get("ingredientes_receta", []):
        if(fila["receta_id"] in nuevas_recetas and fila["alimento_id"] in mapa["alimentos"]):
            bd.add(IngredienteReceta(**{**_convertir(IngredienteReceta, fila, ("id",)), "receta_id": mapa["recetas"][fila["receta_id"]], "alimento_id": mapa["alimentos"][fila["alimento_id"]]}))
    nuevos_planes = set()
    for(fila) in datos.get("planes_semana", []):
        existe = bd.query(PlanSemana).filter(PlanSemana.usuario_id == usuario_id, PlanSemana.lunes == date.fromisoformat(fila["lunes"])).first()
        if(existe is None):
            existe = PlanSemana(usuario_id=usuario_id, **{**_convertir(PlanSemana, fila, ("id", "usuario_id", "repite_de")), "repite_de": None})
            bd.add(existe)
            bd.flush()
            nuevos_planes.add(fila["id"])
            contar("planes_semana", "creados")
        else:
            contar("planes_semana", "existentes")
        mapa["planes_semana"][fila["id"]] = existe.id
    for(fila) in datos.get("comidas_planificadas", []):
        if(fila["plan_id"] in nuevos_planes and fila["receta_id"] in mapa["recetas"]):
            nueva = ComidaPlanificada(usuario_id=usuario_id, **{**_convertir(ComidaPlanificada, fila, ("id", "usuario_id")), "plan_id": mapa["planes_semana"][fila["plan_id"]], "receta_id": mapa["recetas"][fila["receta_id"]]})
            bd.add(nueva)
            bd.flush()
            mapa["comidas_planificadas"][fila["id"]] = nueva.id
        else:
            plan_nuevo = mapa["planes_semana"].get(fila["plan_id"])
            existente = bd.query(ComidaPlanificada).filter(ComidaPlanificada.plan_id == plan_nuevo, ComidaPlanificada.fecha == date.fromisoformat(fila["fecha"]), ComidaPlanificada.momento == fila["momento"]).first() if plan_nuevo else None
            if(existente is not None):
                mapa["comidas_planificadas"][fila["id"]] = existente.id
    for(fila) in datos.get("cambios_menu", []):
        if(fila["plan_id"] in nuevos_planes):
            bd.add(CambioMenu(**{**_convertir(CambioMenu, fila, ("id",)), "plan_id": mapa["planes_semana"][fila["plan_id"]]}))
    for(fila) in datos.get("consumos", []):
        id_cliente, existe = _id_cliente_libre(bd, Consumo, fila.get("id_cliente"), usuario_id)
        if(existe):
            contar("consumos", "existentes")
            continue
        bd.add(Consumo(usuario_id=usuario_id, **{**_convertir(Consumo, fila, ("id", "usuario_id", "id_cliente", "comida_planificada_id")), "id_cliente": id_cliente, "comida_planificada_id": mapa["comidas_planificadas"].get(fila.get("comida_planificada_id"))}))
        bd.flush()
        contar("consumos", "creados")
    for(fila) in datos.get("despensa", []):
        alimento_id = mapa["alimentos"].get(fila["alimento_id"])
        if(alimento_id and bd.query(ItemDespensa).filter(ItemDespensa.usuario_id == usuario_id, ItemDespensa.alimento_id == alimento_id).first() is None):
            bd.add(ItemDespensa(usuario_id=usuario_id, alimento_id=alimento_id, cantidad=fila["cantidad"]))
            contar("despensa", "creados")
    for(fila) in datos.get("compras", []):
        id_cliente, existe = _id_cliente_libre(bd, Compra, fila.get("id_cliente"), usuario_id)
        if(existe or fila["alimento_id"] not in mapa["alimentos"]):
            contar("compras", "existentes")
            continue
        bd.add(Compra(usuario_id=usuario_id, **{**_convertir(Compra, fila, ("id", "usuario_id", "id_cliente", "plan_id", "alimento_id", "producto_id")), "id_cliente": id_cliente, "plan_id": mapa["planes_semana"].get(fila.get("plan_id")), "alimento_id": mapa["alimentos"][fila["alimento_id"]], "producto_id": None}))
        bd.flush()
        contar("compras", "creados")
    for(fila) in datos.get("ejercicios", []):
        consulta = bd.query(Ejercicio).filter(Ejercicio.usuario_id == usuario_id)
        existe = consulta.filter(Ejercicio.codigo == fila["codigo"]).first() if fila.get("codigo") else consulta.filter(Ejercicio.nombre == fila["nombre"]).first()
        if(existe is None):
            existe = Ejercicio(usuario_id=usuario_id, **_convertir(Ejercicio, fila, ("id", "usuario_id")))
            bd.add(existe)
            bd.flush()
            contar("ejercicios", "creados")
        mapa["ejercicios"][fila["id"]] = existe.id
    nuevas_rutinas = set()
    for(fila) in datos.get("rutinas", []):
        existe = bd.query(Rutina).filter(Rutina.usuario_id == usuario_id, Rutina.nombre == fila["nombre"], Rutina.version == fila["version"]).first()
        if(existe is None):
            existe = Rutina(usuario_id=usuario_id, **_convertir(Rutina, fila, ("id", "usuario_id")))
            if(existe.activa):
                bd.query(Rutina).filter(Rutina.usuario_id == usuario_id).update({"activa": False})
            bd.add(existe)
            bd.flush()
            nuevas_rutinas.add(fila["id"])
            contar("rutinas", "creados")
        mapa["rutinas"][fila["id"]] = existe.id
    for(fila) in datos.get("rutina_ejercicios", []):
        if(fila["rutina_id"] in nuevas_rutinas and fila["ejercicio_id"] in mapa["ejercicios"]):
            bd.add(EjercicioRutina(**{**_convertir(EjercicioRutina, fila, ("id",)), "rutina_id": mapa["rutinas"][fila["rutina_id"]], "ejercicio_id": mapa["ejercicios"][fila["ejercicio_id"]]}))
    for(fila) in datos.get("sesiones_entreno", []):
        id_cliente, existe = _id_cliente_libre(bd, SesionEntreno, fila.get("id_cliente"), usuario_id)
        if(existe):
            contar("sesiones_entreno", "existentes")
            continue
        ejercicios = [{**e, "ejercicio_id": mapa["ejercicios"].get(e.get("ejercicio_id"), e.get("ejercicio_id"))} for e in fila.get("ejercicios") or []]
        bd.add(SesionEntreno(usuario_id=usuario_id, **{**_convertir(SesionEntreno, fila, ("id", "usuario_id", "id_cliente", "rutina_id", "ejercicios")), "id_cliente": id_cliente, "rutina_id": mapa["rutinas"].get(fila.get("rutina_id")), "ejercicios": ejercicios}))
        bd.flush()
        contar("sesiones_entreno", "creados")
    for(fila) in datos.get("eventos", []):
        if(fila.get("clave_plan") and bd.query(Evento).filter(Evento.usuario_id == usuario_id, Evento.clave_plan == fila["clave_plan"], Evento.borrado == False).first()):
            contar("eventos", "existentes")
            continue
        id_cliente, existe = _id_cliente_libre(bd, Evento, fila.get("id_cliente"), usuario_id)
        if(existe):
            contar("eventos", "existentes")
            continue
        bd.add(Evento(usuario_id=usuario_id, **{**_convertir(Evento, fila, ("id", "usuario_id", "id_cliente")), "id_cliente": id_cliente if fila.get("id_cliente") else None}))
        bd.flush()
        contar("eventos", "creados")
    for(fila) in datos.get("mediciones", []):
        id_cliente, existe = _id_cliente_libre(bd, Medicion, fila.get("id_cliente"), usuario_id)
        if(existe):
            contar("mediciones", "existentes")
            continue
        bd.add(Medicion(usuario_id=usuario_id, **{**_convertir(Medicion, fila, ("id", "usuario_id", "id_cliente")), "id_cliente": id_cliente}))
        bd.flush()
        contar("mediciones", "creados")
    conflictos_diario = []
    for(fila) in datos.get("diario", []):
        existe = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario_id, EntradaDiario.fecha == date.fromisoformat(fila["fecha"])).first()
        if(existe is None):
            bd.add(EntradaDiario(usuario_id=usuario_id, **_convertir(EntradaDiario, fila, ("id", "usuario_id"))))
            contar("diario", "creados")
        else:
            if(existe.datos != fila.get("datos")):
                conflictos_diario.append(fila["fecha"])
            contar("diario", "existentes")
    for(fila) in datos.get("campos_personalizados", []):
        if(bd.query(CampoPersonalizado).filter(CampoPersonalizado.usuario_id == usuario_id, CampoPersonalizado.clave == fila["clave"]).first() is None):
            bd.add(CampoPersonalizado(usuario_id=usuario_id, **_convertir(CampoPersonalizado, fila, ("id", "usuario_id"))))
            contar("campos_personalizados", "creados")
    for(fila) in datos.get("recordatorios", []):
        if(bd.query(Recordatorio).filter(Recordatorio.usuario_id == usuario_id, Recordatorio.tipo == fila["tipo"], Recordatorio.hora == fila["hora"]).first() is None):
            bd.add(Recordatorio(usuario_id=usuario_id, **{**_convertir(Recordatorio, fila, ("id", "usuario_id")), "activo": False}))
            contar("recordatorios", "creados")
    bd.commit()
    return {
        "informe": informe,
        "diario_no_sobrescrito": conflictos_diario,
        "fotos_listadas": len(datos.get("fotos", [])),
        "aviso": "La importación no borra ni sobrescribe datos existentes. Los días de diario que ya existían se conservan. Los recordatorios importados quedan desactivados. Las fotos se restauran desde la copia de seguridad completa.",
    }


CSV_TABLAS = {
    "mediciones": (Medicion, ["fecha", "tipo", "valor", "unidad", "condiciones", "notas"]),
    "consumos": (Consumo, ["fecha", "momento", "tipo", "descripcion", "kcal", "proteina", "hidratos", "grasas", "fibra"]),
    "diario": (EntradaDiario, ["fecha", "datos"]),
    "sesiones": (SesionEntreno, ["fecha", "sesion_codigo", "estado", "ejercicios"]),
    "eventos": (Evento, ["fecha", "tipo", "titulo", "hora", "estado", "datos"]),
}


def exportar_csv(bd: Session, usuario_id: int, tabla: str) -> str:
    if(tabla not in CSV_TABLAS):
        raise ValueError("Tabla no exportable")
    modelo, columnas = CSV_TABLAS[tabla]
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    if(tabla == "sesiones"):
        escritor.writerow(["fecha", "sesion", "estado", "ejercicio", "serie", "peso_kg", "repeticiones", "completada", "rir", "descanso_s", "notas"])
        for(s) in bd.query(modelo).filter(modelo.usuario_id == usuario_id).order_by(modelo.fecha).all():
            for(e) in s.ejercicios or []:
                for(serie) in e.get("series") or []:
                    escritor.writerow([s.fecha.isoformat(), s.sesion_codigo, s.estado, e.get("nombre"), serie.get("numero"), _decimal(serie.get("peso_kg")), serie.get("repeticiones"), "sí" if serie.get("completada") else "no", serie.get("rir"), serie.get("descanso_s"), serie.get("notas") or ""])
        return salida.getvalue()
    escritor.writerow(columnas)
    consulta = bd.query(modelo).filter(modelo.usuario_id == usuario_id)
    if(hasattr(modelo, "borrado")):
        consulta = consulta.filter(modelo.borrado == False)
    for(fila) in consulta.order_by(modelo.fecha).all():
        valores = []
        for(c) in columnas:
            valor = getattr(fila, c)
            if(isinstance(valor, date)):
                valor = valor.isoformat()
            elif(isinstance(valor, float)):
                valor = _decimal(valor)
            elif(isinstance(valor, (dict, list))):
                import json
                valor = json.dumps(valor, ensure_ascii=False)
            valores.append("" if valor is None else valor)
        escritor.writerow(valores)
    return salida.getvalue()


def _decimal(valor) -> str:
    if(valor is None):
        return ""
    return str(round(valor, 3)).replace(".", ",")


def importar_mediciones_csv(bd: Session, usuario_id: int, texto: str, confirmar: bool) -> dict:
    from app.servicios.registros import crear_medicion
    filas = []
    primera = texto.strip().splitlines()[0] if texto.strip() else ""
    separador = ";" if ";" in primera else ","
    for(numero, fila) in enumerate(csv.reader(io.StringIO(texto), delimiter=separador)):
        if(len(fila) < 2 or fila[0].strip().lower() == "fecha"):
            continue
        try:
            fecha = interpretar_fecha(fila[0])
            tipo = (fila[2].strip() if len(fila) > 2 and fila[2].strip() else "peso") if separador == ";" or len(fila) > 2 else "peso"
            valor = interpretar_numero(fila[1], "El valor", 0, 1000)
            filas.append({"linea": numero + 1, "fecha": fecha.isoformat(), "valor": valor, "tipo": tipo, "id_cliente": f"csv-{usuario_id}-{tipo}-{fecha.isoformat()}-{valor}"})
        except ValueError as error:
            filas.append({"linea": numero + 1, "error": str(error)})
    if(not confirmar):
        return {"filas": filas, "aviso": "Revisa los datos detectados. No se guardan hasta que confirmes. Formato: fecha;valor;tipo"}
    guardadas = 0
    duplicadas = 0
    errores = []
    for(f) in filas:
        if("error" in f):
            continue
        try:
            resultado = crear_medicion(bd, usuario_id, {"id_cliente": f["id_cliente"], "fecha": f["fecha"], "tipo": f["tipo"], "valor": f["valor"]})
            if(resultado["duplicado"]):
                duplicadas = duplicadas + 1
            else:
                guardadas = guardadas + 1
        except ValueError as error:
            errores.append({"linea": f["linea"], "error": str(error)})
    return {"guardadas": guardadas, "duplicadas": duplicadas, "errores": errores}
