import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculos import nutricion as calc_nutricion
from app.calculos.fechas import interpretar_fecha
from app.calculos.numeros import interpretar_entero, interpretar_numero
from app.modelos import (
    Alimento,
    CampoPersonalizado,
    ComidaPlanificada,
    Compra,
    Conflicto,
    Consumo,
    EntradaDiario,
    ItemDespensa,
    Medicion,
    MovimientoDespensa,
    PlanSemana,
    Producto,
    SesionEntreno,
)
from app.servicios.nucleo import MOMENTOS, CacheRecetas, alimento_a_dict, consumo_a_dict, propio

TIPOS_CONSUMO = ("previsto", "modificado", "parcial", "diferente", "extra")
TIPOS_MEDICION = {"peso": ("kg", 30, 350), "cintura": ("cm", 40, 250), "cadera": ("cm", 40, 250), "pecho": ("cm", 40, 250), "brazo": ("cm", 10, 80), "muslo": ("cm", 20, 120), "cuello": ("cm", 20, 80)}
CAMPOS_DIARIO = {
    "sueno_horas": ("numero", 0, 24),
    "calidad_sueno": ("escala", 1, 5),
    "hambre": ("escala", 1, 5),
    "energia": ("escala", 1, 5),
    "estres": ("escala", 1, 5),
    "dolor": ("escala", 0, 10),
    "digestion": ("escala", 1, 5),
    "agua_ml": ("numero", 0, 10000),
    "pasos": ("entero", 0, 100000),
    "cardio_min": ("entero", 0, 600),
    "notas": ("texto", 0, 2000),
    "molestias": ("texto", 0, 500),
}


class ErrorConflicto(Exception):
    def __init__(self, mensaje: str, servidor: dict, conflicto_id: int) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.servidor = servidor
        self.conflicto_id = conflicto_id


def _id_cliente(carga: dict) -> str:
    valor = str(carga.get("id_cliente") or "").strip()
    if(valor == ""):
        return f"srv-{uuid.uuid4()}"
    if(len(valor) > 64):
        raise ValueError("Identificador de cliente demasiado largo")
    return valor


def _ingredientes_libres(bd: Session, usuario_id: int, lista: list) -> tuple:
    alimentos = []
    cantidades = []
    partes = []
    for(item) in lista or []:
        alimento = propio(bd, Alimento, int(item["alimento_id"]), usuario_id, "Alimento no encontrado")
        datos = alimento_a_dict(alimento)
        cantidad = interpretar_numero(item.get("cantidad"), "La cantidad", 0, 5000)
        unidad = str(item.get("unidad") or datos["unidad_base"])
        partes.append(calc_nutricion.nutrientes_cantidad(datos, cantidad, unidad))
        alimentos.append(datos)
        cantidades.append({"cantidad": cantidad, "unidad": unidad})
    return alimentos, cantidades, partes


def _desde_receta(receta: dict, proporcion: float) -> tuple:
    alimentos = []
    cantidades = []
    for(ing) in receta["_ingredientes_calculo"]:
        alimentos.append(ing["alimento"])
        cantidades.append({"cantidad": ing["cantidad"] * proporcion / receta["raciones"], "unidad": ing["unidad"]})
    nutrientes = calc_nutricion.escalar(receta["nutrientes_racion"], proporcion)
    return alimentos, cantidades, nutrientes


def crear_consumo(bd: Session, usuario_id: int, carga: dict) -> dict:
    id_cliente = _id_cliente(carga)
    existente = bd.query(Consumo).filter(Consumo.id_cliente == id_cliente).first()
    if(existente is not None):
        if(existente.usuario_id != usuario_id):
            raise ValueError("Identificador ya usado")
        return {"consumo": consumo_a_dict(existente), "duplicado": True}
    tipo = carga.get("tipo")
    if(tipo not in TIPOS_CONSUMO):
        raise ValueError("Tipo de registro no válido")
    cache = CacheRecetas(bd, usuario_id)
    comida = None
    if(carga.get("comida_planificada_id")):
        comida = propio(bd, ComidaPlanificada, int(carga["comida_planificada_id"]), usuario_id, "Comida no encontrada")
    if(tipo in ("previsto", "modificado", "parcial") and comida is None):
        raise ValueError("Este registro necesita la comida planificada")
    fecha = comida.fecha if comida is not None else interpretar_fecha(carga.get("fecha"))
    momento = comida.momento if comida is not None else str(carga.get("momento") or "extra")
    if(momento not in MOMENTOS):
        raise ValueError("Momento no válido")
    if(tipo == "previsto"):
        previo = bd.query(Consumo).filter(Consumo.usuario_id == usuario_id, Consumo.comida_planificada_id == comida.id, Consumo.tipo == "previsto", Consumo.borrado == False).first()
        if(previo is not None):
            return {"consumo": consumo_a_dict(previo), "duplicado": True}
    descripcion = str(carga.get("descripcion") or "").strip()[:500]
    nutrientes = None
    alimentos = []
    cantidades = []
    if(tipo == "previsto"):
        receta = cache.receta(comida.receta_id)
        alimentos, cantidades, nutrientes = _desde_receta(receta, comida.factor)
        descripcion = descripcion or receta["nombre"]
    elif(tipo == "parcial"):
        proporcion = interpretar_numero(carga.get("proporcion"), "La proporción", 0.05, 1)
        receta = cache.receta(comida.receta_id)
        alimentos, cantidades, nutrientes = _desde_receta(receta, comida.factor * proporcion)
        descripcion = descripcion or f"{receta['nombre']} ({round(proporcion * 100)} %)"
    elif(carga.get("ingredientes")):
        alimentos, cantidades, partes = _ingredientes_libres(bd, usuario_id, carga["ingredientes"])
        nutrientes = calc_nutricion.sumar_nutrientes(partes)
    elif(carga.get("receta_id")):
        receta = cache.receta(int(carga["receta_id"]))
        factor = interpretar_numero(carga.get("factor", 1), "Las raciones", 0.05, 10)
        alimentos, cantidades, nutrientes = _desde_receta(receta, factor)
        descripcion = descripcion or receta["nombre"]
    elif(carga.get("nutrientes")):
        manual = carga["nutrientes"]
        nutrientes = {
            "kcal": interpretar_numero(manual.get("kcal"), "Las kcal", 0, 5000, opcional=True),
            "proteina": interpretar_numero(manual.get("proteina"), "La proteína", 0, 500, opcional=True),
            "hidratos": interpretar_numero(manual.get("hidratos"), "Los hidratos", 0, 1000, opcional=True),
            "grasas": interpretar_numero(manual.get("grasas"), "Las grasas", 0, 500, opcional=True),
            "fibra": interpretar_numero(manual.get("fibra"), "La fibra", 0, 200, opcional=True),
        }
    elif(descripcion == ""):
        raise ValueError("Describe lo que has comido o añade ingredientes")
    if(tipo == "modificado" and nutrientes is None):
        raise ValueError("Indica las cantidades modificadas")
    consumo = Consumo(
        usuario_id=usuario_id,
        id_cliente=id_cliente,
        comida_planificada_id=comida.id if comida is not None else None,
        fecha=fecha,
        momento=momento,
        tipo=tipo,
        descripcion=descripcion,
        kcal=nutrientes.get("kcal") if nutrientes else None,
        proteina=nutrientes.get("proteina") if nutrientes else None,
        hidratos=nutrientes.get("hidratos") if nutrientes else None,
        grasas=nutrientes.get("grasas") if nutrientes else None,
        fibra=nutrientes.get("fibra") if nutrientes else None,
        instantanea=calc_nutricion.instantanea_consumo(alimentos, cantidades, nutrientes) if nutrientes else {"sin_cantidades": True},
    )
    bd.add(consumo)
    try:
        bd.commit()
    except IntegrityError:
        bd.rollback()
        previo = bd.query(Consumo).filter(Consumo.id_cliente == id_cliente).first() or bd.query(Consumo).filter(Consumo.usuario_id == usuario_id, Consumo.comida_planificada_id == comida.id, Consumo.tipo == "previsto", Consumo.borrado == False).first()
        return {"consumo": consumo_a_dict(previo), "duplicado": True}
    return {"consumo": consumo_a_dict(consumo), "duplicado": False}


def borrar_consumo(bd: Session, usuario_id: int, carga: dict) -> dict:
    consumo = propio(bd, Consumo, int(carga["id"]), usuario_id, "Registro no encontrado")
    consumo.borrado = True
    consumo.version = consumo.version + 1
    bd.commit()
    return {"id": consumo.id, "borrado": True}


def crear_medicion(bd: Session, usuario_id: int, carga: dict) -> dict:
    id_cliente = _id_cliente(carga)
    existente = bd.query(Medicion).filter(Medicion.id_cliente == id_cliente).first()
    if(existente is not None):
        if(existente.usuario_id != usuario_id):
            raise ValueError("Identificador ya usado")
        return {"medicion": medicion_a_dict(existente), "duplicado": True}
    tipo = str(carga.get("tipo") or "peso")
    if(tipo in TIPOS_MEDICION):
        unidad, minimo, maximo = TIPOS_MEDICION[tipo]
    else:
        campo = _campo_personalizado(bd, usuario_id, tipo)
        unidad, minimo, maximo = campo.unidad or "", campo.minimo, campo.maximo
    valor = interpretar_numero(carga.get("valor"), "El valor", minimo, maximo)
    medicion = Medicion(
        usuario_id=usuario_id,
        id_cliente=id_cliente,
        fecha=interpretar_fecha(carga.get("fecha")),
        tipo=tipo,
        valor=valor,
        unidad=unidad,
        condiciones=str(carga.get("condiciones") or "")[:60] or None,
        notas=str(carga.get("notas") or "")[:500] or None,
    )
    bd.add(medicion)
    bd.commit()
    return {"medicion": medicion_a_dict(medicion), "duplicado": False}


def _campo_personalizado(bd: Session, usuario_id: int, clave: str) -> CampoPersonalizado:
    campo = bd.query(CampoPersonalizado).filter(CampoPersonalizado.usuario_id == usuario_id, CampoPersonalizado.clave == clave).first()
    if(campo is None):
        raise ValueError(f"Medida desconocida: {clave}")
    return campo


def medicion_a_dict(m: Medicion) -> dict:
    return {"id": m.id, "id_cliente": m.id_cliente, "fecha": m.fecha.isoformat(), "tipo": m.tipo, "valor": m.valor, "unidad": m.unidad, "condiciones": m.condiciones, "notas": m.notas}


def borrar_medicion(bd: Session, usuario_id: int, carga: dict) -> dict:
    medicion = propio(bd, Medicion, int(carga["id"]), usuario_id, "Medida no encontrada")
    medicion.borrado = True
    medicion.version = medicion.version + 1
    bd.commit()
    return {"id": medicion.id, "borrado": True}


def validar_diario(bd: Session, usuario_id: int, datos: dict) -> dict:
    limpio = {}
    personalizados = {c.clave: c for c in bd.query(CampoPersonalizado).filter(CampoPersonalizado.usuario_id == usuario_id).all()}
    for(clave, valor) in (datos or {}).items():
        if(valor is None or valor == ""):
            continue
        if(clave in CAMPOS_DIARIO):
            tipo, minimo, maximo = CAMPOS_DIARIO[clave]
        elif(clave in personalizados):
            campo = personalizados[clave]
            tipo, minimo, maximo = campo.tipo, campo.minimo, campo.maximo
        else:
            raise ValueError(f"Campo desconocido: {clave}")
        if(tipo == "texto"):
            limpio[clave] = str(valor)[: int(maximo or 500)]
        elif(tipo == "si_no"):
            limpio[clave] = bool(valor)
        elif(tipo == "entero"):
            limpio[clave] = interpretar_entero(valor, clave, minimo, maximo)
        else:
            limpio[clave] = interpretar_numero(valor, clave, minimo, maximo)
    return limpio


def diario_a_dict(e: EntradaDiario | None, fecha=None) -> dict:
    if(e is None):
        return {"fecha": fecha.isoformat() if fecha else None, "datos": {}, "version": 0, "existe": False}
    return {"id": e.id, "fecha": e.fecha.isoformat(), "datos": e.datos or {}, "version": e.version, "existe": True}


def guardar_diario(bd: Session, usuario_id: int, carga: dict) -> dict:
    fecha = interpretar_fecha(carga.get("fecha"))
    datos = validar_diario(bd, usuario_id, carga.get("datos") or {})
    base = int(carga.get("version_base") or 0)
    entrada = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario_id, EntradaDiario.fecha == fecha).first()
    if(entrada is None):
        if(base != 0):
            raise ValueError("La entrada del diario no existe en el servidor")
        entrada = EntradaDiario(usuario_id=usuario_id, fecha=fecha, datos=datos, version=1)
        bd.add(entrada)
        try:
            bd.commit()
        except IntegrityError:
            bd.rollback()
            entrada = bd.query(EntradaDiario).filter(EntradaDiario.usuario_id == usuario_id, EntradaDiario.fecha == fecha).first()
            registrar_conflicto(bd, usuario_id, "diario", entrada.id, carga, diario_a_dict(entrada))
        return {"diario": diario_a_dict(entrada)}
    if(base != entrada.version):
        if(entrada.datos == datos):
            return {"diario": diario_a_dict(entrada)}
        registrar_conflicto(bd, usuario_id, "diario", entrada.id, carga, diario_a_dict(entrada))
    entrada.datos = datos
    entrada.version = entrada.version + 1
    bd.commit()
    return {"diario": diario_a_dict(entrada)}


def registrar_conflicto(bd: Session, usuario_id: int, entidad: str, entidad_id: int | None, cliente: dict, servidor: dict) -> None:
    conflicto = Conflicto(usuario_id=usuario_id, entidad=entidad, entidad_id=entidad_id, carga_cliente=cliente, carga_servidor=servidor)
    bd.add(conflicto)
    bd.commit()
    raise ErrorConflicto("Este dato cambió en otro dispositivo. Se guardaron las dos versiones para que elijas.", servidor, conflicto.id)


def sesion_a_dict(s: SesionEntreno) -> dict:
    return {
        "id": s.id,
        "id_cliente": s.id_cliente,
        "fecha": s.fecha.isoformat(),
        "sesion_codigo": s.sesion_codigo,
        "rutina_id": s.rutina_id,
        "estado": s.estado,
        "inicio": s.inicio.isoformat() if s.inicio else None,
        "fin": s.fin.isoformat() if s.fin else None,
        "notas": s.notas,
        "semana_programa": s.semana_programa,
        "ejercicios": s.ejercicios or [],
        "version": s.version,
    }


def _validar_ejercicios_sesion(lista: list) -> list:
    resultado = []
    for(indice, e) in enumerate(lista or []):
        series = []
        for(numero, s) in enumerate(e.get("series") or []):
            series.append({
                "numero": numero + 1,
                "peso_kg": interpretar_numero(s.get("peso_kg"), "El peso", 0, 1000, opcional=True),
                "repeticiones": interpretar_entero(s.get("repeticiones"), "Las repeticiones", 0, 200, opcional=True),
                "completada": bool(s.get("completada")),
                "rir": interpretar_entero(s.get("rir"), "Las repeticiones en reserva", 0, 10, opcional=True),
                "descanso_s": interpretar_entero(s.get("descanso_s"), "El descanso", 0, 3600, opcional=True),
                "notas": str(s.get("notas") or "")[:300] or None,
            })
        resultado.append({
            "ejercicio_id": e.get("ejercicio_id"),
            "nombre": str(e.get("nombre") or "")[:160],
            "sustituye_a": e.get("sustituye_a"),
            "orden": indice,
            "rep_min": e.get("rep_min"),
            "rep_max": e.get("rep_max"),
            "series_objetivo": e.get("series_objetivo"),
            "tecnica_ok": e.get("tecnica_ok", True) != False,
            "notas": str(e.get("notas") or "")[:500] or None,
            "series": series,
        })
    return resultado


def guardar_sesion(bd: Session, usuario_id: int, carga: dict) -> dict:
    id_cliente = _id_cliente(carga)
    estado = str(carga.get("estado") or "en_curso")
    if(estado not in ("en_curso", "finalizada", "parcial")):
        raise ValueError("Estado de sesión no válido")
    ejercicios = _validar_ejercicios_sesion(carga.get("ejercicios"))
    sesion = bd.query(SesionEntreno).filter(SesionEntreno.id_cliente == id_cliente).first()
    base = int(carga.get("version_base") or 0)
    rutina_id = carga.get("rutina_id")
    if(rutina_id is not None):
        from app.modelos import Rutina
        rutina = bd.get(Rutina, int(rutina_id))
        rutina_id = rutina.id if rutina is not None and rutina.usuario_id == usuario_id else None
    if(sesion is None):
        sesion = SesionEntreno(
            usuario_id=usuario_id,
            id_cliente=id_cliente,
            fecha=interpretar_fecha(carga.get("fecha")),
            sesion_codigo=str(carga.get("sesion_codigo") or "")[:20],
            rutina_id=rutina_id,
            semana_programa=carga.get("semana_programa"),
            inicio=_instante(carga.get("inicio")),
            version=1,
        )
        bd.add(sesion)
    else:
        if(sesion.usuario_id != usuario_id):
            raise ValueError("Identificador ya usado")
        if(base != sesion.version):
            registrar_conflicto(bd, usuario_id, "sesion", sesion.id, carga, sesion_a_dict(sesion))
        sesion.version = sesion.version + 1
    sesion.estado = estado
    sesion.ejercicios = ejercicios
    sesion.notas = str(carga.get("notas") or "")[:2000] or None
    if(estado != "en_curso"):
        sesion.fin = _instante(carga.get("fin")) or sesion.fin
    bd.commit()
    return {"sesion": sesion_a_dict(sesion)}


def _instante(valor):
    if(not valor):
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def ajustar_despensa(bd: Session, usuario_id: int, alimento_id: int, delta: float, motivo: str, plan_id: int | None) -> float:
    item = bd.query(ItemDespensa).filter(ItemDespensa.usuario_id == usuario_id, ItemDespensa.alimento_id == alimento_id).first()
    if(item is None):
        item = ItemDespensa(usuario_id=usuario_id, alimento_id=alimento_id, cantidad=0.0)
        bd.add(item)
    nuevo = max(0.0, (item.cantidad or 0.0) + delta)
    real = nuevo - (item.cantidad or 0.0)
    item.cantidad = nuevo
    bd.add(MovimientoDespensa(usuario_id=usuario_id, alimento_id=alimento_id, cantidad=real, motivo=motivo, plan_id=plan_id))
    return real


def marcar_compra(bd: Session, usuario_id: int, carga: dict) -> dict:
    id_cliente = _id_cliente(carga)
    existente = bd.query(Compra).filter(Compra.id_cliente == id_cliente).first()
    if(existente is not None):
        if(existente.usuario_id != usuario_id):
            raise ValueError("Identificador ya usado")
        return {"compra_id": existente.id, "duplicado": True}
    plan = propio(bd, PlanSemana, int(carga["plan_id"]), usuario_id, "Semana no encontrada")
    alimento = propio(bd, Alimento, int(carga["alimento_id"]), usuario_id, "Alimento no encontrado")
    producto = None
    if(carga.get("producto_id")):
        producto = propio(bd, Producto, int(carga["producto_id"]), usuario_id, "Producto no encontrado")
    envases = interpretar_entero(carga.get("envases", 1), "Los envases", 0, 100)
    if(producto is not None):
        cantidad = envases * producto.capacidad_util
    else:
        cantidad = interpretar_numero(carga.get("cantidad"), "La cantidad", 0, 100000)
    precio = interpretar_numero(carga.get("precio_unitario"), "El precio", 0, 500, opcional=True)
    origen = "manual" if carga.get("precio_unitario") not in (None, "") else (producto.precio_origen if producto is not None and producto.precio is not None else "desconocido")
    if(precio is None and producto is not None and producto.precio is not None):
        precio = producto.precio
    compra = Compra(usuario_id=usuario_id, id_cliente=id_cliente, plan_id=plan.id, alimento_id=alimento.id, producto_id=producto.id if producto else None, envases=envases, cantidad_util=cantidad, precio_unitario=precio, precio_origen=origen)
    bd.add(compra)
    ajustar_despensa(bd, usuario_id, alimento.id, cantidad, "compra", plan.id)
    if(producto is not None and carga.get("precio_unitario") not in (None, "")):
        producto.precio = precio
        producto.precio_origen = "manual"
        from app.calculos.fechas import hoy_local
        producto.precio_fecha = hoy_local()
        producto.precio_fuente = "Precio introducido al marcar la compra"
    bd.commit()
    return {"compra_id": compra.id, "duplicado": False}


def anular_compra(bd: Session, usuario_id: int, carga: dict) -> dict:
    compra = propio(bd, Compra, int(carga["id"]), usuario_id, "Compra no encontrada")
    if(compra.anulada):
        return {"compra_id": compra.id, "anulada": True}
    compra.anulada = True
    ajustar_despensa(bd, usuario_id, compra.alimento_id, -compra.cantidad_util, "anulacion_compra", compra.plan_id)
    bd.commit()
    return {"compra_id": compra.id, "anulada": True}


def evento_a_dict(e) -> dict:
    return {"id": e.id, "id_cliente": e.id_cliente, "fecha": e.fecha.isoformat(), "tipo": e.tipo, "titulo": e.titulo, "hora": e.hora, "clave_plan": e.clave_plan, "estado": e.estado, "datos": e.datos or {}, "version": e.version}


def guardar_evento(bd: Session, usuario_id: int, carga: dict) -> dict:
    from app.calculos.entrenamiento import TIPOS_EVENTO
    from app.calculos.fechas import interpretar_hora
    from app.modelos import Evento
    tipo = str(carga.get("tipo") or "")
    if(tipo not in TIPOS_EVENTO):
        raise ValueError("Tipo de actividad no válido")
    estado = str(carga.get("estado") or "realizado")
    if(estado not in ("planificado", "realizado", "omitido")):
        raise ValueError("Estado no válido")
    datos_entrada = carga.get("datos") or {}
    datos = {}
    if(datos_entrada.get("duracion_min") not in (None, "")):
        datos["duracion_min"] = interpretar_entero(datos_entrada["duracion_min"], "La duración", 0, 400)
    if(datos_entrada.get("minutos_jugados") not in (None, "")):
        datos["minutos_jugados"] = interpretar_entero(datos_entrada["minutos_jugados"], "Los minutos jugados", 0, 200)
    if(datos_entrada.get("esfuerzo") not in (None, "")):
        datos["esfuerzo"] = interpretar_entero(datos_entrada["esfuerzo"], "El esfuerzo percibido", 1, 10)
    if(datos_entrada.get("molestias")):
        datos["molestias"] = str(datos_entrada["molestias"])[:500]
    if(datos_entrada.get("notas")):
        datos["notas"] = str(datos_entrada["notas"])[:1000]
    clave = carga.get("clave_plan") or None
    id_cliente = _id_cliente(carga)
    evento = None
    if(clave):
        evento = bd.query(Evento).filter(Evento.usuario_id == usuario_id, Evento.clave_plan == clave, Evento.borrado == False).first()
    if(evento is None):
        evento = bd.query(Evento).filter(Evento.id_cliente == id_cliente).first()
        if(evento is not None and evento.usuario_id != usuario_id):
            raise ValueError("Identificador ya usado")
    base = int(carga.get("version_base") or 0)
    if(evento is None):
        evento = Evento(usuario_id=usuario_id, id_cliente=id_cliente, clave_plan=clave, fecha=interpretar_fecha(carga.get("fecha")), tipo=tipo, titulo=str(carga.get("titulo") or tipo)[:160], version=0, datos={})
        bd.add(evento)
    elif(base != evento.version and evento.datos and evento.datos != datos):
        registrar_conflicto(bd, usuario_id, "evento", evento.id, carga, evento_a_dict(evento))
    if(carga.get("hora")):
        evento.hora = interpretar_hora(carga["hora"])
    evento.estado = estado
    evento.datos = datos
    evento.id_cliente = evento.id_cliente or id_cliente
    evento.version = (evento.version or 0) + 1
    bd.commit()
    return {"evento": evento_a_dict(evento)}


MANEJADORES = {
    "evento.guardar": guardar_evento,
    "consumo.crear": crear_consumo,
    "consumo.borrar": borrar_consumo,
    "medicion.crear": crear_medicion,
    "medicion.borrar": borrar_medicion,
    "diario.guardar": guardar_diario,
    "sesion.guardar": guardar_sesion,
    "compra.marcar": marcar_compra,
    "compra.anular": anular_compra,
}


def ejecutar(bd: Session, usuario_id: int, tipo: str, carga: dict) -> dict:
    if(tipo not in MANEJADORES):
        raise ValueError(f"Operación desconocida: {tipo}")
    try:
        return MANEJADORES[tipo](bd, usuario_id, carga or {})
    except HTTPException as error:
        bd.rollback()
        raise ValueError(str(error.detail))
