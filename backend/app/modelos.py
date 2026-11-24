from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.types import TypeDecorator

from app.db import Base


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class FechaHoraUTC(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, valor, dialecto):
        if(valor is None):
            return None
        if(valor.tzinfo is None):
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, valor, dialecto):
        if(valor is None):
            return None
        return valor.replace(tzinfo=timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    hash_contrasena = Column(String(255), nullable=False)
    totp_secreto = Column(String(64))
    totp_activo = Column(Boolean, nullable=False, default=False)
    codigos_recuperacion = Column(JSON, nullable=False, default=list)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class SesionUsuario(Base):
    __tablename__ = "sesiones"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    expira_en = Column(FechaHoraUTC, nullable=False)
    segundo_factor_pendiente = Column(Boolean, nullable=False, default=False)


class IntentoAcceso(Base):
    __tablename__ = "intentos_acceso"
    id = Column(Integer, primary_key=True)
    clave = Column(String(255), nullable=False, index=True)
    ip = Column(String(64), nullable=False, index=True)
    momento = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    exito = Column(Boolean, nullable=False, default=False)


class Perfil(Base):
    __tablename__ = "perfiles"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    nombre = Column(String(120), nullable=False, default="")
    edad_referencia = Column(Integer)
    fecha_referencia_edad = Column(Date)
    fecha_nacimiento = Column(Date)
    altura_cm = Column(Float)
    peso_inicial_kg = Column(Float)
    sexo_formula = Column(String(20))
    nivel_actividad = Column(String(40))
    pasos_habituales = Column(Integer)
    presupuesto_semanal = Column(Float)
    presupuesto_confirmado = Column(Boolean, nullable=False, default=False)
    horarios = Column(JSON, nullable=False, default=dict)
    equipo_gimnasio = Column(Text)
    continuidad_entrenamiento = Column(String(40))
    cargas_conocidas = Column(Text)
    modo_registro = Column(String(20), nullable=False, default="calorias")
    tema = Column(String(20), nullable=False, default="sistema")
    comensales = Column(Integer, nullable=False, default=1)
    inicio_plan = Column(Date)
    zona_horaria = Column(String(64), nullable=False, default="Europe/Madrid")
    alimentos_excluidos = Column(JSON, nullable=False, default=list)
    modo_dias_entreno = Column(String(20), nullable=False, default="estandar")
    meta_revision_kg = Column(Float)
    silencio_inicio = Column(String(5), nullable=False, default="22:30")
    silencio_fin = Column(String(5), nullable=False, default="08:00")
    sintomas_alerta = Column(JSON, nullable=False, default=dict)
    modo_objetivo = Column(String(20), nullable=False, default="perder")
    objetivo_descripcion = Column(Text)
    experiencia = Column(String(30))
    hitos_kg = Column(JSON, nullable=False, default=list)
    peso_referencia_kg = Column(Float)
    peso_referencia_origen = Column(Text)
    alergias = Column(Text)
    molestias_actuales = Column(Text)
    actividad_cotidiana = Column(Text)
    pendientes_confirmar = Column(JSON, nullable=False, default=list)
    plan_aceptado = Column(Boolean, nullable=False, default=True)
    agua_referencia = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)


class Objetivo(Base):
    __tablename__ = "objetivos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    vigente_desde = Column(Date, nullable=False)
    kcal = Column(Float)
    proteina_g = Column(Float)
    hidratos_g = Column(Float)
    grasas_g = Column(Float)
    fibra_g = Column(Float)
    modo = Column(String(20), nullable=False, default="perder")
    origen = Column(String(40), nullable=False)
    provisional = Column(Boolean, nullable=False, default=True)
    detalle = Column(JSON, nullable=False, default=dict)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class Alimento(Base):
    __tablename__ = "alimentos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(60))
    nombre = Column(String(160), nullable=False)
    base = Column(String(10), nullable=False, default="100g")
    gramos_unidad = Column(Float)
    kcal = Column(Float, nullable=False)
    proteina = Column(Float, nullable=False)
    hidratos = Column(Float, nullable=False)
    grasas = Column(Float, nullable=False)
    fibra = Column(Float)
    origen = Column(String(20), nullable=False, default="generico")
    fuente = Column(Text)
    estado_peso = Column(String(40), nullable=False, default="tal_cual")
    factor_compra = Column(Float, nullable=False, default=1.0)
    nota_factor = Column(Text)
    densidad = Column(Float)
    alergenos = Column(JSON, nullable=False, default=list)
    seccion = Column(String(60), nullable=False, default="Otros")
    codigo_barras = Column(String(40), index=True)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (UniqueConstraint("usuario_id", "codigo", name="uq_alimento_codigo"),)


class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(60))
    nombre = Column(String(200), nullable=False)
    capacidad = Column(Float, nullable=False)
    unidad = Column(String(5), nullable=False)
    capacidad_util = Column(Float, nullable=False)
    nota_capacidad = Column(Text)
    formato_verificado = Column(Boolean, nullable=False, default=False)
    precio = Column(Float)
    precio_origen = Column(String(30), nullable=False, default="desconocido")
    precio_fecha = Column(Date)
    precio_fuente = Column(Text)
    tienda = Column(String(120))
    preferido = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("usuario_id", "codigo", name="uq_producto_codigo"),)


class Receta(Base):
    __tablename__ = "recetas"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(60))
    nombre = Column(String(200), nullable=False)
    momento_tipico = Column(String(20), nullable=False, default="comida")
    raciones = Column(Float, nullable=False, default=1)
    tiempo_min = Column(Integer)
    pasos = Column(JSON, nullable=False, default=list)
    conservacion = Column(Text)
    sustituciones = Column(JSON, nullable=False, default=list)
    notas = Column(Text)
    favorita = Column(Boolean, nullable=False, default=False)
    peso_final_lote = Column(Float)
    modo_preparacion = Column(String(20), nullable=False, default="al_momento")
    max_nevera_dias = Column(Integer, nullable=False, default=2)
    origen = Column(String(20), nullable=False, default="propia")
    archivada = Column(Boolean, nullable=False, default=False)
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    actualizada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (UniqueConstraint("usuario_id", "codigo", name="uq_receta_codigo"),)


class IngredienteReceta(Base):
    __tablename__ = "ingredientes_receta"
    id = Column(Integer, primary_key=True)
    receta_id = Column(Integer, ForeignKey("recetas.id", ondelete="CASCADE"), nullable=False, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id", ondelete="CASCADE"), nullable=False)
    cantidad = Column(Float, nullable=False)
    unidad = Column(String(5), nullable=False, default="g")
    orden = Column(Integer, nullable=False, default=0)
    nota = Column(Text)


class Invitacion(Base):
    __tablename__ = "invitaciones"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    plan = Column(String(20), nullable=False)
    nombre_provisional = Column(String(120), nullable=False)
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    expira_en = Column(FechaHoraUTC, nullable=False)
    usada_en = Column(FechaHoraUTC)
    usuario_creado_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"))
    revocada = Column(Boolean, nullable=False, default=False)


class PlanSemana(Base):
    __tablename__ = "planes_semana"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    lunes = Column(Date, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    origen = Column(String(30), nullable=False, default="manual")
    repite_de = Column(Integer, ForeignKey("planes_semana.id", ondelete="SET NULL"))
    cerrada = Column(Boolean, nullable=False, default=False)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    __table_args__ = (UniqueConstraint("usuario_id", "lunes", name="uq_plan_lunes"),)


class ComidaPlanificada(Base):
    __tablename__ = "comidas_planificadas"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("planes_semana.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    momento = Column(String(20), nullable=False)
    hora = Column(String(5))
    receta_id = Column(Integer, ForeignKey("recetas.id", ondelete="CASCADE"), nullable=False)
    factor = Column(Float, nullable=False, default=1.0)
    orden = Column(Integer, nullable=False, default=0)
    opcional = Column(Boolean, nullable=False, default=False)
    actualizada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)


class CambioMenu(Base):
    __tablename__ = "cambios_menu"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("planes_semana.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    momento = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    descripcion = Column(Text, nullable=False)
    datos = Column(JSON, nullable=False, default=dict)


class Consumo(Base):
    __tablename__ = "consumos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_cliente = Column(String(64), unique=True)
    comida_planificada_id = Column(Integer, ForeignKey("comidas_planificadas.id", ondelete="SET NULL"))
    fecha = Column(Date, nullable=False, index=True)
    momento = Column(String(20), nullable=False)
    tipo = Column(String(20), nullable=False)
    descripcion = Column(Text, nullable=False, default="")
    kcal = Column(Float)
    proteina = Column(Float)
    hidratos = Column(Float)
    grasas = Column(Float)
    fibra = Column(Float)
    instantanea = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    borrado = Column(Boolean, nullable=False, default=False)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (
        Index(
            "uq_consumo_previsto_unico",
            "usuario_id",
            "comida_planificada_id",
            unique=True,
            sqlite_where=text("tipo = 'previsto' AND borrado = 0"),
            postgresql_where=text("tipo = 'previsto' AND borrado = false"),
        ),
    )


class ItemDespensa(Base):
    __tablename__ = "despensa"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id", ondelete="CASCADE"), nullable=False)
    cantidad = Column(Float, nullable=False, default=0)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (UniqueConstraint("usuario_id", "alimento_id", name="uq_despensa_alimento"),)


class MovimientoDespensa(Base):
    __tablename__ = "movimientos_despensa"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id", ondelete="CASCADE"), nullable=False)
    cantidad = Column(Float, nullable=False)
    motivo = Column(String(40), nullable=False)
    plan_id = Column(Integer, ForeignKey("planes_semana.id", ondelete="SET NULL"))
    momento = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class Compra(Base):
    __tablename__ = "compras"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_cliente = Column(String(64), unique=True)
    plan_id = Column(Integer, ForeignKey("planes_semana.id", ondelete="SET NULL"), index=True)
    alimento_id = Column(Integer, ForeignKey("alimentos.id", ondelete="CASCADE"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id", ondelete="SET NULL"))
    envases = Column(Integer, nullable=False, default=1)
    cantidad_util = Column(Float, nullable=False)
    precio_unitario = Column(Float)
    precio_origen = Column(String(30), nullable=False, default="desconocido")
    anulada = Column(Boolean, nullable=False, default=False)
    momento = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class Ejercicio(Base):
    __tablename__ = "ejercicios"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(60))
    nombre = Column(String(160), nullable=False)
    grupo = Column(String(60))
    instrucciones = Column(Text)
    alternativas = Column(JSON, nullable=False, default=list)
    incremento_kg = Column(Float, nullable=False, default=2.5)
    principal = Column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint("usuario_id", "codigo", name="uq_ejercicio_codigo"),)


class Rutina(Base):
    __tablename__ = "rutinas"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(160), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    vigente_desde = Column(Date, nullable=False)
    activa = Column(Boolean, nullable=False, default=True)
    distribucion = Column(JSON, nullable=False, default=dict)
    configuracion = Column(JSON, nullable=False, default=dict)
    plantilla = Column(String(40))
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class EjercicioRutina(Base):
    __tablename__ = "rutina_ejercicios"
    id = Column(Integer, primary_key=True)
    tiempo = Column(String(60))
    rutina_id = Column(Integer, ForeignKey("rutinas.id", ondelete="CASCADE"), nullable=False, index=True)
    sesion = Column(String(20), nullable=False)
    ejercicio_id = Column(Integer, ForeignKey("ejercicios.id", ondelete="CASCADE"), nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    series = Column(Integer, nullable=False)
    rep_min = Column(Integer)
    rep_max = Column(Integer)
    por_lado = Column(Boolean, nullable=False, default=False)
    nota = Column(Text)


class SesionEntreno(Base):
    __tablename__ = "sesiones_entreno"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_cliente = Column(String(64), unique=True)
    fecha = Column(Date, nullable=False, index=True)
    sesion_codigo = Column(String(20), nullable=False)
    rutina_id = Column(Integer, ForeignKey("rutinas.id", ondelete="SET NULL"))
    estado = Column(String(20), nullable=False, default="en_curso")
    inicio = Column(FechaHoraUTC)
    fin = Column(FechaHoraUTC)
    notas = Column(Text)
    semana_programa = Column(Integer)
    ejercicios = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    actualizada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)


class Evento(Base):
    __tablename__ = "eventos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_cliente = Column(String(64), unique=True)
    fecha = Column(Date, nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    titulo = Column(String(160), nullable=False)
    hora = Column(String(5))
    clave_plan = Column(String(60))
    estado = Column(String(20), nullable=False, default="planificado")
    datos = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    borrado = Column(Boolean, nullable=False, default=False)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (
        Index("uq_evento_plan_dia", "usuario_id", "clave_plan", unique=True, sqlite_where=text("clave_plan IS NOT NULL AND borrado = 0"), postgresql_where=text("clave_plan IS NOT NULL AND borrado = false")),
    )


class Medicion(Base):
    __tablename__ = "mediciones"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_cliente = Column(String(64), unique=True)
    fecha = Column(Date, nullable=False, index=True)
    tipo = Column(String(40), nullable=False)
    valor = Column(Float, nullable=False)
    unidad = Column(String(10), nullable=False)
    condiciones = Column(String(60))
    notas = Column(Text)
    borrado = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class EntradaDiario(Base):
    __tablename__ = "diario"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False)
    datos = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
    __table_args__ = (UniqueConstraint("usuario_id", "fecha", name="uq_diario_fecha"),)


class CampoPersonalizado(Base):
    __tablename__ = "campos_personalizados"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    clave = Column(String(60), nullable=False)
    etiqueta = Column(String(120), nullable=False)
    tipo = Column(String(20), nullable=False)
    unidad = Column(String(20))
    minimo = Column(Float)
    maximo = Column(Float)
    __table_args__ = (UniqueConstraint("usuario_id", "clave", name="uq_campo_clave"),)


class Foto(Base):
    __tablename__ = "fotos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False)
    archivo = Column(String(120), nullable=False, unique=True)
    tipo_mime = Column(String(60), nullable=False)
    contenido = Column(LargeBinary)
    notas = Column(Text)
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class Recordatorio(Base):
    __tablename__ = "recordatorios"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    hora = Column(String(5), nullable=False)
    dias = Column(JSON, nullable=False, default=list)
    activo = Column(Boolean, nullable=False, default=False)
    texto_generico = Column(Boolean, nullable=False, default=True)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class SuscripcionPush(Base):
    __tablename__ = "suscripciones_push"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    dispositivo = Column(String(64))
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    agente = Column(Text)
    creada_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    ultimo_envio_ok = Column(FechaHoraUTC)
    fallos = Column(Integer, nullable=False, default=0)


class EnvioRecordatorio(Base):
    __tablename__ = "envios_recordatorio"
    id = Column(Integer, primary_key=True)
    recordatorio_id = Column(Integer, ForeignKey("recordatorios.id", ondelete="CASCADE"), nullable=False)
    fecha_local = Column(Date, nullable=False)
    enviado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)
    resultado = Column(String(40), nullable=False)
    detalle = Column(Text)
    __table_args__ = (UniqueConstraint("recordatorio_id", "fecha_local", name="uq_envio_dia"),)


class OperacionSync(Base):
    __tablename__ = "operaciones_sync"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    id_operacion = Column(String(64), nullable=False, unique=True)
    tipo = Column(String(60), nullable=False)
    estado = Column(String(20), nullable=False)
    resultado = Column(JSON, nullable=False, default=dict)
    recibida_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class Conflicto(Base):
    __tablename__ = "conflictos"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    entidad = Column(String(40), nullable=False)
    entidad_id = Column(Integer)
    carga_cliente = Column(JSON, nullable=False, default=dict)
    carga_servidor = Column(JSON, nullable=False, default=dict)
    resuelto = Column(Boolean, nullable=False, default=False)
    creado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc)


class AjusteServidor(Base):
    __tablename__ = "ajustes_servidor"
    clave = Column(String(60), primary_key=True)
    valor = Column(Text, nullable=False)
    actualizado_en = Column(FechaHoraUTC, nullable=False, default=ahora_utc, onupdate=ahora_utc)
