import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import nutricion as calc_nutricion
from app.calculos.fechas import hoy_local, interpretar_fecha
from app.calculos.numeros import interpretar_numero
from app.db import obtener_bd
from app.modelos import Alimento, ComidaPlanificada, Compra, IngredienteReceta, ItemDespensa, PlanSemana, Producto, Receta, Usuario
from app.seguridad import usuario_actual
from app.servicios import registros
from app.servicios.nucleo import (
    CacheRecetas,
    alimento_a_dict,
    despensa_de,
    necesidades_plan,
    comensales,
    perfil_de,
    producto_a_dict,
    propio,
    publica,
)

enrutador = APIRouter(prefix="/api", tags=["cocina"])

BASES = ("100g", "100ml", "unidad")
ORIGENES = ("generico", "etiqueta", "manual")


def _texto(valor, maximo: int = 200) -> str:
    return str(valor or "").strip()[:maximo]


@enrutador.get("/alimentos")
def listar_alimentos(q: str | None = None, codigo_barras: str | None = None, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    consulta = bd.query(Alimento).filter(Alimento.usuario_id == usuario.id)
    if(codigo_barras):
        consulta = consulta.filter(Alimento.codigo_barras == codigo_barras.strip())
    filas = consulta.order_by(Alimento.nombre).all()
    if(q):
        clave = calc_nutricion.normalizar_texto(q)
        filas = [a for a in filas if clave in calc_nutricion.normalizar_texto(a.nombre)]
    perfil = perfil_de(bd, usuario.id)
    return {"alimentos": [{**alimento_a_dict(a), "excluido": calc_nutricion.contiene_excluido(a.nombre, perfil.alimentos_excluidos)} for a in filas]}


def _datos_alimento(cuerpo: dict, actual: Alimento | None) -> dict:
    datos = {}
    if(actual is None or "nombre" in cuerpo):
        datos["nombre"] = _texto(cuerpo.get("nombre"), 160)
        if(datos["nombre"] == ""):
            raise ValueError("Falta el nombre")
    if(actual is None or "base" in cuerpo):
        base = cuerpo.get("base") or "100g"
        if(base not in BASES):
            raise ValueError("Base no válida: usa por 100 g, por 100 ml o por unidad")
        datos["base"] = base
    for(campo, etiqueta, maximo) in (("kcal", "Las kcal", 900), ("proteina", "La proteína", 100), ("hidratos", "Los hidratos", 100), ("grasas", "Las grasas", 100)):
        if(actual is None or campo in cuerpo):
            datos[campo] = interpretar_numero(cuerpo.get(campo), etiqueta, 0, 5000 if (cuerpo.get("base") or (actual.base if actual else "100g")) == "unidad" else maximo)
    if("fibra" in cuerpo):
        datos["fibra"] = interpretar_numero(cuerpo.get("fibra"), "La fibra", 0, 100, opcional=True)
    if("gramos_unidad" in cuerpo):
        datos["gramos_unidad"] = interpretar_numero(cuerpo.get("gramos_unidad"), "Los gramos por unidad", 0.1, 5000, opcional=True)
    if("densidad" in cuerpo):
        datos["densidad"] = interpretar_numero(cuerpo.get("densidad"), "La densidad", 0.2, 3, opcional=True)
    if("factor_compra" in cuerpo):
        datos["factor_compra"] = interpretar_numero(cuerpo.get("factor_compra"), "El factor de compra", 1, 5)
    if("origen" in cuerpo or actual is None):
        origen = cuerpo.get("origen") or "manual"
        if(origen not in ORIGENES):
            raise ValueError("Origen no válido")
        datos["origen"] = origen
    for(campo, maximo) in (("fuente", 500), ("estado_peso", 40), ("seccion", 60), ("codigo_barras", 40), ("nota_factor", 300)):
        if(campo in cuerpo):
            datos[campo] = _texto(cuerpo.get(campo), maximo) or None
    if("alergenos" in cuerpo):
        datos["alergenos"] = [_texto(a, 60) for a in (cuerpo.get("alergenos") or []) if _texto(a, 60)]
    if(actual is None):
        datos.setdefault("estado_peso", "tal_cual")
        datos.setdefault("seccion", "Otros")
    return datos


@enrutador.post("/alimentos")
def crear_alimento(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        datos = _datos_alimento(cuerpo, None)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    alimento = Alimento(usuario_id=usuario.id, **datos)
    bd.add(alimento)
    bd.commit()
    return {"alimento": alimento_a_dict(alimento)}


@enrutador.put("/alimentos/{alimento_id}")
def editar_alimento(alimento_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    alimento = propio(bd, Alimento, alimento_id, usuario.id, "Alimento no encontrado")
    try:
        datos = _datos_alimento(cuerpo, alimento)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    for(clave, valor) in datos.items():
        setattr(alimento, clave, valor)
    bd.commit()
    return {"alimento": alimento_a_dict(alimento), "aviso": "Las recetas y la compra se recalculan con estos valores. Los consumos ya registrados conservan los valores que tenían."}


@enrutador.get("/recetas")
def listar_recetas(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    cache = CacheRecetas(bd, usuario.id)
    filas = bd.query(Receta).filter(Receta.usuario_id == usuario.id, Receta.archivada == False).order_by(Receta.favorita.desc(), Receta.nombre).all()
    return {"recetas": [publica(cache.receta(r.id)) for r in filas]}


@enrutador.get("/recetas/{receta_id}")
def obtener_receta(receta_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    propio(bd, Receta, receta_id, usuario.id, "Receta no encontrada")
    perfil = perfil_de(bd, usuario.id)
    datos = publica(CacheRecetas(bd, usuario.id).receta(receta_id))
    datos["avisos_exclusion"] = sorted({x for x in (calc_nutricion.contiene_excluido(i["nombre"], perfil.alimentos_excluidos) for i in datos["ingredientes"]) if x})
    return {"receta": datos}


def _guardar_receta(bd: Session, usuario_id: int, receta: Receta, cuerpo: dict) -> list[str]:
    if("nombre" in cuerpo):
        receta.nombre = _texto(cuerpo.get("nombre"), 200)
        if(receta.nombre == ""):
            raise ValueError("Falta el nombre")
    if("momento_tipico" in cuerpo):
        receta.momento_tipico = cuerpo["momento_tipico"] if cuerpo["momento_tipico"] in ("desayuno", "comida", "merienda", "cena", "extra") else "comida"
    if("raciones" in cuerpo):
        receta.raciones = interpretar_numero(cuerpo["raciones"], "Las raciones", 0.25, 50)
    if("tiempo_min" in cuerpo):
        receta.tiempo_min = int(interpretar_numero(cuerpo["tiempo_min"], "El tiempo", 0, 600, opcional=True) or 0) or None
    if("pasos" in cuerpo):
        receta.pasos = [_texto(p, 1000) for p in (cuerpo["pasos"] or []) if _texto(p, 1000)]
    if("sustituciones" in cuerpo):
        receta.sustituciones = [_texto(p, 300) for p in (cuerpo["sustituciones"] or []) if _texto(p, 300)]
    for(campo, maximo) in (("conservacion", 2000), ("notas", 2000)):
        if(campo in cuerpo):
            setattr(receta, campo, _texto(cuerpo[campo], maximo) or None)
    if("peso_final_lote" in cuerpo):
        receta.peso_final_lote = interpretar_numero(cuerpo["peso_final_lote"], "El peso final del lote", 1, 50000, opcional=True)
    if("modo_preparacion" in cuerpo):
        receta.modo_preparacion = "lote" if cuerpo["modo_preparacion"] == "lote" else "al_momento"
    if("favorita" in cuerpo):
        receta.favorita = bool(cuerpo["favorita"])
    avisos = []
    if("ingredientes" in cuerpo):
        perfil = perfil_de(bd, usuario_id)
        bd.query(IngredienteReceta).filter(IngredienteReceta.receta_id == receta.id).delete()
        for(orden, item) in enumerate(cuerpo["ingredientes"] or []):
            alimento = propio(bd, Alimento, int(item["alimento_id"]), usuario_id, "Alimento no encontrado")
            unidad = item.get("unidad") or calc_nutricion.unidad_base_alimento({"base": alimento.base})
            calc_nutricion.a_unidad_base(1, unidad, alimento_a_dict(alimento))
            bd.add(IngredienteReceta(receta_id=receta.id, alimento_id=alimento.id, cantidad=interpretar_numero(item.get("cantidad"), "La cantidad", 0.1, 20000), unidad=unidad, orden=orden, nota=_texto(item.get("nota"), 200) or None))
            excluido = calc_nutricion.contiene_excluido(alimento.nombre, perfil.alimentos_excluidos)
            if(excluido):
                avisos.append(f"{alimento.nombre} contiene «{excluido}», que tienes en alimentos que no te gustan.")
    return avisos


@enrutador.post("/recetas")
def crear_receta(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    receta = Receta(usuario_id=usuario.id, nombre="", raciones=1, origen="propia", pasos=[], sustituciones=[])
    bd.add(receta)
    bd.flush()
    try:
        avisos = _guardar_receta(bd, usuario.id, receta, {"nombre": cuerpo.get("nombre"), **cuerpo})
    except ValueError as error:
        bd.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    bd.commit()
    return {"receta": publica(CacheRecetas(bd, usuario.id).receta(receta.id)), "avisos": avisos}


@enrutador.put("/recetas/{receta_id}")
def editar_receta(receta_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    receta = propio(bd, Receta, receta_id, usuario.id, "Receta no encontrada")
    try:
        avisos = _guardar_receta(bd, usuario.id, receta, cuerpo)
    except ValueError as error:
        bd.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    bd.commit()
    return {"receta": publica(CacheRecetas(bd, usuario.id).receta(receta.id)), "avisos": avisos, "aviso": "Nutrientes y compra recalculados. Los consumos registrados antes no cambian."}


@enrutador.post("/recetas/{receta_id}/duplicar")
def duplicar_receta(receta_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    original = propio(bd, Receta, receta_id, usuario.id, "Receta no encontrada")
    copia = Receta(
        usuario_id=usuario.id, nombre=f"{original.nombre} (copia)", momento_tipico=original.momento_tipico, raciones=original.raciones, tiempo_min=original.tiempo_min,
        pasos=list(original.pasos or []), conservacion=original.conservacion, sustituciones=list(original.sustituciones or []), notas=original.notas,
        peso_final_lote=original.peso_final_lote, modo_preparacion=original.modo_preparacion, max_nevera_dias=original.max_nevera_dias, origen="propia",
    )
    bd.add(copia)
    bd.flush()
    for(i) in bd.query(IngredienteReceta).filter(IngredienteReceta.receta_id == original.id).all():
        bd.add(IngredienteReceta(receta_id=copia.id, alimento_id=i.alimento_id, cantidad=i.cantidad, unidad=i.unidad, orden=i.orden, nota=i.nota))
    bd.commit()
    return {"receta": publica(CacheRecetas(bd, usuario.id).receta(copia.id))}


@enrutador.delete("/recetas/{receta_id}")
def archivar_receta(receta_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    receta = propio(bd, Receta, receta_id, usuario.id, "Receta no encontrada")
    en_uso = bd.query(ComidaPlanificada).filter(ComidaPlanificada.receta_id == receta.id).count()
    receta.archivada = True
    bd.commit()
    return {"ok": True, "en_uso": en_uso, "aviso": "Archivada: deja de proponerse, pero las semanas que la usan la conservan." if en_uso else None}


@enrutador.post("/recetas/{receta_id}/porcion-lote")
def porcion_lote(receta_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    propio(bd, Receta, receta_id, usuario.id, "Receta no encontrada")
    receta = CacheRecetas(bd, usuario.id).receta(receta_id)
    try:
        peso_lote = interpretar_numero(cuerpo.get("peso_final_lote") or receta["peso_final_lote"], "El peso final del lote", 1, 50000)
        porcion = interpretar_numero(cuerpo.get("porcion_servida"), "La porción servida", 1, 5000)
        nutrientes = calc_nutricion.nutrientes_porcion_lote(receta["nutrientes_total"], peso_lote, porcion)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"nutrientes": nutrientes, "proporcion_del_lote": porcion / peso_lote}


@enrutador.get("/productos")
def listar_productos(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    filas = bd.query(Producto).filter(Producto.usuario_id == usuario.id).order_by(Producto.nombre).all()
    return {"productos": [producto_a_dict(p) for p in filas]}


def _datos_producto(bd: Session, usuario_id: int, cuerpo: dict, actual: Producto | None) -> dict:
    datos = {}
    if(actual is None):
        alimento = propio(bd, Alimento, int(cuerpo.get("alimento_id") or 0), usuario_id, "Alimento no encontrado")
        datos["alimento_id"] = alimento.id
    if("nombre" in cuerpo or actual is None):
        datos["nombre"] = _texto(cuerpo.get("nombre"), 200)
        if(datos["nombre"] == ""):
            raise ValueError("Falta el nombre del producto")
    if("capacidad" in cuerpo or actual is None):
        datos["capacidad"] = interpretar_numero(cuerpo.get("capacidad"), "La capacidad del envase", 0.001, 100000)
    if("unidad" in cuerpo or actual is None):
        if(cuerpo.get("unidad") not in ("g", "kg", "ml", "l", "ud")):
            raise ValueError("Unidad de envase no válida")
        datos["unidad"] = cuerpo["unidad"]
    if("capacidad_util" in cuerpo or actual is None):
        datos["capacidad_util"] = interpretar_numero(cuerpo.get("capacidad_util"), "La cantidad útil (escurrida o comestible)", 0.001, 100000)
    if("formato_verificado" in cuerpo):
        datos["formato_verificado"] = bool(cuerpo["formato_verificado"])
    if("precio" in cuerpo):
        datos["precio"] = interpretar_numero(cuerpo.get("precio"), "El precio", 0, 500, opcional=True)
        datos["precio_origen"] = cuerpo.get("precio_origen") if cuerpo.get("precio_origen") in ("manual", "ticket", "catalogo", "referencia_externa") else ("manual" if datos["precio"] is not None else "desconocido")
        datos["precio_fecha"] = interpretar_fecha(cuerpo["precio_fecha"]) if cuerpo.get("precio_fecha") else (hoy_local() if datos["precio"] is not None else None)
        datos["precio_fuente"] = _texto(cuerpo.get("precio_fuente"), 500) or ("Introducido a mano" if datos["precio"] is not None else None)
    for(campo, maximo) in (("tienda", 120), ("nota_capacidad", 500)):
        if(campo in cuerpo):
            datos[campo] = _texto(cuerpo[campo], maximo) or None
    if("preferido" in cuerpo):
        datos["preferido"] = bool(cuerpo["preferido"])
    return datos


@enrutador.post("/productos")
def crear_producto(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    try:
        datos = _datos_producto(bd, usuario.id, cuerpo, None)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    producto = Producto(usuario_id=usuario.id, **datos)
    if(producto.preferido):
        bd.query(Producto).filter(Producto.usuario_id == usuario.id, Producto.alimento_id == producto.alimento_id).update({"preferido": False})
    bd.add(producto)
    bd.commit()
    return {"producto": producto_a_dict(producto)}


@enrutador.put("/productos/{producto_id}")
def editar_producto(producto_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    producto = propio(bd, Producto, producto_id, usuario.id, "Producto no encontrado")
    try:
        datos = _datos_producto(bd, usuario.id, cuerpo, producto)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if(datos.get("preferido")):
        bd.query(Producto).filter(Producto.usuario_id == usuario.id, Producto.alimento_id == producto.alimento_id, Producto.id != producto.id).update({"preferido": False})
    for(clave, valor) in datos.items():
        setattr(producto, clave, valor)
    bd.commit()
    return {"producto": producto_a_dict(producto)}


@enrutador.post("/productos/ticket/previsualizar")
def previsualizar_ticket(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    texto = str(cuerpo.get("csv") or "")
    productos = bd.query(Producto).filter(Producto.usuario_id == usuario.id).all()
    filas = []
    primera = texto.strip().splitlines()[0] if texto.strip() else ""
    separador = ";" if ";" in primera else ","
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    for(fila) in lector:
        if(len(fila) < 2 or fila[0].strip().lower() in ("producto", "nombre")):
            continue
        nombre = fila[0].strip()
        try:
            precio = interpretar_numero(fila[1], "El precio", 0, 500)
        except ValueError as error:
            filas.append({"texto": nombre, "error": str(error)})
            continue
        clave = calc_nutricion.normalizar_texto(nombre)
        candidatos = [p for p in productos if clave in calc_nutricion.normalizar_texto(p.nombre) or calc_nutricion.normalizar_texto(p.nombre) in clave]
        filas.append({"texto": nombre, "precio": precio, "producto_id": candidatos[0].id if len(candidatos) == 1 else None, "candidatos": [{"id": p.id, "nombre": p.nombre} for p in candidatos[:5]]})
    return {"filas": filas, "aviso": "Revisa cada fila y elige el producto antes de guardar. No se guarda nada hasta que confirmes."}


@enrutador.post("/productos/ticket/confirmar")
def confirmar_ticket(cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    tienda = _texto(cuerpo.get("tienda"), 120) or None
    fecha = interpretar_fecha(cuerpo.get("fecha")) if cuerpo.get("fecha") else hoy_local()
    guardados = 0
    for(fila) in cuerpo.get("filas") or []:
        if(not fila.get("producto_id")):
            continue
        producto = propio(bd, Producto, int(fila["producto_id"]), usuario.id, "Producto no encontrado")
        producto.precio = interpretar_numero(fila.get("precio"), "El precio", 0, 500)
        producto.precio_origen = "ticket"
        producto.precio_fecha = fecha
        producto.precio_fuente = "Ticket introducido por el usuario"
        producto.tienda = tienda or producto.tienda
        guardados = guardados + 1
    bd.commit()
    return {"guardados": guardados}


@enrutador.get("/despensa")
def despensa(usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    items = []
    for(d) in bd.query(ItemDespensa).filter(ItemDespensa.usuario_id == usuario.id, ItemDespensa.cantidad > 0).all():
        alimento = bd.get(Alimento, d.alimento_id)
        items.append({"alimento_id": d.alimento_id, "nombre": alimento.nombre, "cantidad": d.cantidad, "unidad": calc_nutricion.unidad_base_alimento({"base": alimento.base}), "seccion": alimento.seccion})
    items.sort(key=lambda x: x["nombre"])
    return {"despensa": items}


@enrutador.put("/despensa/{alimento_id}")
def ajustar_despensa(alimento_id: int, cuerpo: dict, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    propio(bd, Alimento, alimento_id, usuario.id, "Alimento no encontrado")
    try:
        nueva = interpretar_numero(cuerpo.get("cantidad"), "La cantidad", 0, 100000)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    actual = despensa_de(bd, usuario.id).get(alimento_id, 0.0)
    registros.ajustar_despensa(bd, usuario.id, alimento_id, nueva - actual, "ajuste_manual", None)
    bd.commit()
    return {"ok": True, "cantidad": nueva}


@enrutador.post("/compra/{plan_id}/cerrar")
def cerrar_semana(plan_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    plan = propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    if(plan.cerrada):
        return {"ok": True, "ya_cerrada": True}
    perfil = perfil_de(bd, usuario.id)
    necesidades = necesidades_plan(bd, usuario.id, plan, comensales(perfil))
    descontado = []
    for(alimento_id, datos) in necesidades.items():
        cantidad = datos["cantidad"] * (datos["alimento"].get("factor_compra") or 1)
        real = registros.ajustar_despensa(bd, usuario.id, alimento_id, -cantidad, "consumo_semana", plan.id)
        descontado.append({"nombre": datos["alimento"]["nombre"], "cantidad": -real})
    plan.cerrada = True
    bd.commit()
    return {"ok": True, "descontado": descontado, "aviso": "Se descontó de la despensa lo previsto para la semana, sin bajar de cero. Ajusta a mano lo que no se gastara."}


@enrutador.get("/compra/{plan_id}/compras")
def compras_semana(plan_id: int, usuario: Usuario = Depends(usuario_actual), bd: Session = Depends(obtener_bd)) -> dict:
    propio(bd, PlanSemana, plan_id, usuario.id, "Semana no encontrada")
    filas = bd.query(Compra).filter(Compra.usuario_id == usuario.id, Compra.plan_id == plan_id, Compra.anulada == False).order_by(Compra.momento).all()
    return {"compras": [{"id": c.id, "alimento_id": c.alimento_id, "producto_id": c.producto_id, "envases": c.envases, "cantidad_util": c.cantidad_util, "precio_unitario": c.precio_unitario, "precio_origen": c.precio_origen, "momento": c.momento.isoformat()} for c in filas]}
