from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.modelos


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('intentos_acceso',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clave', sa.String(length=255), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('momento', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('exito', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('intentos_acceso', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_intentos_acceso_clave'), ['clave'], unique=False)
        batch_op.create_index(batch_op.f('ix_intentos_acceso_ip'), ['ip'], unique=False)

    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hash_contrasena', sa.String(length=255), nullable=False),
    sa.Column('totp_secreto', sa.String(length=64), nullable=True),
    sa.Column('totp_activo', sa.Boolean(), nullable=False),
    sa.Column('codigos_recuperacion', sa.JSON(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('alimentos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=True),
    sa.Column('nombre', sa.String(length=160), nullable=False),
    sa.Column('base', sa.String(length=10), nullable=False),
    sa.Column('gramos_unidad', sa.Float(), nullable=True),
    sa.Column('kcal', sa.Float(), nullable=False),
    sa.Column('proteina', sa.Float(), nullable=False),
    sa.Column('hidratos', sa.Float(), nullable=False),
    sa.Column('grasas', sa.Float(), nullable=False),
    sa.Column('fibra', sa.Float(), nullable=True),
    sa.Column('origen', sa.String(length=20), nullable=False),
    sa.Column('fuente', sa.Text(), nullable=True),
    sa.Column('estado_peso', sa.String(length=40), nullable=False),
    sa.Column('factor_compra', sa.Float(), nullable=False),
    sa.Column('nota_factor', sa.Text(), nullable=True),
    sa.Column('densidad', sa.Float(), nullable=True),
    sa.Column('alergenos', sa.JSON(), nullable=False),
    sa.Column('seccion', sa.String(length=60), nullable=False),
    sa.Column('codigo_barras', sa.String(length=40), nullable=True),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'codigo', name='uq_alimento_codigo')
    )
    with op.batch_alter_table('alimentos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alimentos_codigo_barras'), ['codigo_barras'], unique=False)
        batch_op.create_index(batch_op.f('ix_alimentos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('campos_personalizados',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('clave', sa.String(length=60), nullable=False),
    sa.Column('etiqueta', sa.String(length=120), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('unidad', sa.String(length=20), nullable=True),
    sa.Column('minimo', sa.Float(), nullable=True),
    sa.Column('maximo', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'clave', name='uq_campo_clave')
    )
    with op.batch_alter_table('campos_personalizados', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campos_personalizados_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('conflictos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('entidad', sa.String(length=40), nullable=False),
    sa.Column('entidad_id', sa.Integer(), nullable=True),
    sa.Column('carga_cliente', sa.JSON(), nullable=False),
    sa.Column('carga_servidor', sa.JSON(), nullable=False),
    sa.Column('resuelto', sa.Boolean(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conflictos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conflictos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('diario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('datos', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'fecha', name='uq_diario_fecha')
    )
    with op.batch_alter_table('diario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_diario_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('ejercicios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=True),
    sa.Column('nombre', sa.String(length=160), nullable=False),
    sa.Column('grupo', sa.String(length=60), nullable=True),
    sa.Column('instrucciones', sa.Text(), nullable=True),
    sa.Column('alternativas', sa.JSON(), nullable=False),
    sa.Column('incremento_kg', sa.Float(), nullable=False),
    sa.Column('principal', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'codigo', name='uq_ejercicio_codigo')
    )
    with op.batch_alter_table('ejercicios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ejercicios_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('eventos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('titulo', sa.String(length=160), nullable=False),
    sa.Column('hora', sa.String(length=5), nullable=True),
    sa.Column('clave_plan', sa.String(length=60), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('datos', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('borrado', sa.Boolean(), nullable=False),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    with op.batch_alter_table('eventos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eventos_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_eventos_usuario_id'), ['usuario_id'], unique=False)
        batch_op.create_index('uq_evento_plan_dia', ['usuario_id', 'clave_plan'], unique=True, sqlite_where=sa.text('clave_plan IS NOT NULL AND borrado = 0'), postgresql_where=sa.text('clave_plan IS NOT NULL AND borrado = false'))

    op.create_table('fotos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('archivo', sa.String(length=120), nullable=False),
    sa.Column('tipo_mime', sa.String(length=60), nullable=False),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('archivo')
    )
    with op.batch_alter_table('fotos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fotos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('invitaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('plan', sa.String(length=20), nullable=False),
    sa.Column('nombre_provisional', sa.String(length=120), nullable=False),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('expira_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('usada_en', app.modelos.FechaHoraUTC(), nullable=True),
    sa.Column('usuario_creado_id', sa.Integer(), nullable=True),
    sa.Column('revocada', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_creado_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_table('mediciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('tipo', sa.String(length=40), nullable=False),
    sa.Column('valor', sa.Float(), nullable=False),
    sa.Column('unidad', sa.String(length=10), nullable=False),
    sa.Column('condiciones', sa.String(length=60), nullable=True),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('borrado', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    with op.batch_alter_table('mediciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mediciones_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_mediciones_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('objetivos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('vigente_desde', sa.Date(), nullable=False),
    sa.Column('kcal', sa.Float(), nullable=True),
    sa.Column('proteina_g', sa.Float(), nullable=True),
    sa.Column('hidratos_g', sa.Float(), nullable=True),
    sa.Column('grasas_g', sa.Float(), nullable=True),
    sa.Column('fibra_g', sa.Float(), nullable=True),
    sa.Column('modo', sa.String(length=20), nullable=False),
    sa.Column('origen', sa.String(length=40), nullable=False),
    sa.Column('provisional', sa.Boolean(), nullable=False),
    sa.Column('detalle', sa.JSON(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('objetivos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_objetivos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('operaciones_sync',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_operacion', sa.String(length=64), nullable=False),
    sa.Column('tipo', sa.String(length=60), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('resultado', sa.JSON(), nullable=False),
    sa.Column('recibida_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_operacion')
    )
    with op.batch_alter_table('operaciones_sync', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_operaciones_sync_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('perfiles',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('edad_referencia', sa.Integer(), nullable=True),
    sa.Column('fecha_referencia_edad', sa.Date(), nullable=True),
    sa.Column('fecha_nacimiento', sa.Date(), nullable=True),
    sa.Column('altura_cm', sa.Float(), nullable=True),
    sa.Column('peso_inicial_kg', sa.Float(), nullable=True),
    sa.Column('sexo_formula', sa.String(length=20), nullable=True),
    sa.Column('nivel_actividad', sa.String(length=40), nullable=True),
    sa.Column('pasos_habituales', sa.Integer(), nullable=True),
    sa.Column('presupuesto_semanal', sa.Float(), nullable=True),
    sa.Column('presupuesto_confirmado', sa.Boolean(), nullable=False),
    sa.Column('horarios', sa.JSON(), nullable=False),
    sa.Column('equipo_gimnasio', sa.Text(), nullable=True),
    sa.Column('continuidad_entrenamiento', sa.String(length=40), nullable=True),
    sa.Column('cargas_conocidas', sa.Text(), nullable=True),
    sa.Column('modo_registro', sa.String(length=20), nullable=False),
    sa.Column('tema', sa.String(length=20), nullable=False),
    sa.Column('comensales', sa.Integer(), nullable=False),
    sa.Column('inicio_plan', sa.Date(), nullable=True),
    sa.Column('zona_horaria', sa.String(length=64), nullable=False),
    sa.Column('alimentos_excluidos', sa.JSON(), nullable=False),
    sa.Column('modo_dias_entreno', sa.String(length=20), nullable=False),
    sa.Column('meta_revision_kg', sa.Float(), nullable=True),
    sa.Column('silencio_inicio', sa.String(length=5), nullable=False),
    sa.Column('silencio_fin', sa.String(length=5), nullable=False),
    sa.Column('sintomas_alerta', sa.JSON(), nullable=False),
    sa.Column('modo_objetivo', sa.String(length=20), nullable=False),
    sa.Column('objetivo_descripcion', sa.Text(), nullable=True),
    sa.Column('experiencia', sa.String(length=30), nullable=True),
    sa.Column('hitos_kg', sa.JSON(), nullable=False),
    sa.Column('peso_referencia_kg', sa.Float(), nullable=True),
    sa.Column('peso_referencia_origen', sa.Text(), nullable=True),
    sa.Column('alergias', sa.Text(), nullable=True),
    sa.Column('molestias_actuales', sa.Text(), nullable=True),
    sa.Column('actividad_cotidiana', sa.Text(), nullable=True),
    sa.Column('pendientes_confirmar', sa.JSON(), nullable=False),
    sa.Column('plan_aceptado', sa.Boolean(), nullable=False),
    sa.Column('agua_referencia', sa.String(length=60), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id')
    )
    op.create_table('planes_semana',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('lunes', sa.Date(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('origen', sa.String(length=30), nullable=False),
    sa.Column('repite_de', sa.Integer(), nullable=True),
    sa.Column('cerrada', sa.Boolean(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['repite_de'], ['planes_semana.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'lunes', name='uq_plan_lunes')
    )
    with op.batch_alter_table('planes_semana', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_planes_semana_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('recetas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=True),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('momento_tipico', sa.String(length=20), nullable=False),
    sa.Column('raciones', sa.Float(), nullable=False),
    sa.Column('tiempo_min', sa.Integer(), nullable=True),
    sa.Column('pasos', sa.JSON(), nullable=False),
    sa.Column('conservacion', sa.Text(), nullable=True),
    sa.Column('sustituciones', sa.JSON(), nullable=False),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('favorita', sa.Boolean(), nullable=False),
    sa.Column('peso_final_lote', sa.Float(), nullable=True),
    sa.Column('modo_preparacion', sa.String(length=20), nullable=False),
    sa.Column('max_nevera_dias', sa.Integer(), nullable=False),
    sa.Column('origen', sa.String(length=20), nullable=False),
    sa.Column('archivada', sa.Boolean(), nullable=False),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('actualizada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'codigo', name='uq_receta_codigo')
    )
    with op.batch_alter_table('recetas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recetas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('recordatorios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('hora', sa.String(length=5), nullable=False),
    sa.Column('dias', sa.JSON(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('texto_generico', sa.Boolean(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recordatorios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recordatorios_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('rutinas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=160), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('vigente_desde', sa.Date(), nullable=False),
    sa.Column('activa', sa.Boolean(), nullable=False),
    sa.Column('distribucion', sa.JSON(), nullable=False),
    sa.Column('configuracion', sa.JSON(), nullable=False),
    sa.Column('plantilla', sa.String(length=40), nullable=True),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('rutinas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rutinas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('sesiones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('expira_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('segundo_factor_pendiente', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('sesiones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sesiones_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('suscripciones_push',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('endpoint', sa.Text(), nullable=False),
    sa.Column('dispositivo', sa.String(length=64), nullable=True),
    sa.Column('p256dh', sa.Text(), nullable=False),
    sa.Column('auth', sa.Text(), nullable=False),
    sa.Column('agente', sa.Text(), nullable=True),
    sa.Column('creada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('ultimo_envio_ok', app.modelos.FechaHoraUTC(), nullable=True),
    sa.Column('fallos', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    with op.batch_alter_table('suscripciones_push', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_suscripciones_push_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('cambios_menu',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('momento', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('datos', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['plan_id'], ['planes_semana.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cambios_menu', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cambios_menu_plan_id'), ['plan_id'], unique=False)

    op.create_table('comidas_planificadas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('momento', sa.String(length=20), nullable=False),
    sa.Column('hora', sa.String(length=5), nullable=True),
    sa.Column('receta_id', sa.Integer(), nullable=False),
    sa.Column('factor', sa.Float(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('opcional', sa.Boolean(), nullable=False),
    sa.Column('actualizada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['plan_id'], ['planes_semana.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['receta_id'], ['recetas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comidas_planificadas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comidas_planificadas_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_comidas_planificadas_plan_id'), ['plan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comidas_planificadas_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('despensa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('alimento_id', sa.Integer(), nullable=False),
    sa.Column('cantidad', sa.Float(), nullable=False),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['alimento_id'], ['alimentos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'alimento_id', name='uq_despensa_alimento')
    )
    with op.batch_alter_table('despensa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_despensa_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('envios_recordatorio',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recordatorio_id', sa.Integer(), nullable=False),
    sa.Column('fecha_local', sa.Date(), nullable=False),
    sa.Column('enviado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('resultado', sa.String(length=40), nullable=False),
    sa.Column('detalle', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['recordatorio_id'], ['recordatorios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('recordatorio_id', 'fecha_local', name='uq_envio_dia')
    )
    op.create_table('ingredientes_receta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('receta_id', sa.Integer(), nullable=False),
    sa.Column('alimento_id', sa.Integer(), nullable=False),
    sa.Column('cantidad', sa.Float(), nullable=False),
    sa.Column('unidad', sa.String(length=5), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('nota', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['alimento_id'], ['alimentos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['receta_id'], ['recetas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ingredientes_receta', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ingredientes_receta_receta_id'), ['receta_id'], unique=False)

    op.create_table('movimientos_despensa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('alimento_id', sa.Integer(), nullable=False),
    sa.Column('cantidad', sa.Float(), nullable=False),
    sa.Column('motivo', sa.String(length=40), nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=True),
    sa.Column('momento', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['alimento_id'], ['alimentos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plan_id'], ['planes_semana.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('movimientos_despensa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_movimientos_despensa_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('productos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('alimento_id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=True),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('capacidad', sa.Float(), nullable=False),
    sa.Column('unidad', sa.String(length=5), nullable=False),
    sa.Column('capacidad_util', sa.Float(), nullable=False),
    sa.Column('nota_capacidad', sa.Text(), nullable=True),
    sa.Column('formato_verificado', sa.Boolean(), nullable=False),
    sa.Column('precio', sa.Float(), nullable=True),
    sa.Column('precio_origen', sa.String(length=30), nullable=False),
    sa.Column('precio_fecha', sa.Date(), nullable=True),
    sa.Column('precio_fuente', sa.Text(), nullable=True),
    sa.Column('tienda', sa.String(length=120), nullable=True),
    sa.Column('preferido', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['alimento_id'], ['alimentos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'codigo', name='uq_producto_codigo')
    )
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_productos_alimento_id'), ['alimento_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_productos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('rutina_ejercicios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tiempo', sa.String(length=60), nullable=True),
    sa.Column('rutina_id', sa.Integer(), nullable=False),
    sa.Column('sesion', sa.String(length=20), nullable=False),
    sa.Column('ejercicio_id', sa.Integer(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('series', sa.Integer(), nullable=False),
    sa.Column('rep_min', sa.Integer(), nullable=True),
    sa.Column('rep_max', sa.Integer(), nullable=True),
    sa.Column('por_lado', sa.Boolean(), nullable=False),
    sa.Column('nota', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['ejercicio_id'], ['ejercicios.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['rutina_id'], ['rutinas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('rutina_ejercicios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rutina_ejercicios_rutina_id'), ['rutina_id'], unique=False)

    op.create_table('sesiones_entreno',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('sesion_codigo', sa.String(length=20), nullable=False),
    sa.Column('rutina_id', sa.Integer(), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('inicio', app.modelos.FechaHoraUTC(), nullable=True),
    sa.Column('fin', app.modelos.FechaHoraUTC(), nullable=True),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('semana_programa', sa.Integer(), nullable=True),
    sa.Column('ejercicios', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actualizada_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['rutina_id'], ['rutinas.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    with op.batch_alter_table('sesiones_entreno', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sesiones_entreno_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_sesiones_entreno_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('compras',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('plan_id', sa.Integer(), nullable=True),
    sa.Column('alimento_id', sa.Integer(), nullable=False),
    sa.Column('producto_id', sa.Integer(), nullable=True),
    sa.Column('envases', sa.Integer(), nullable=False),
    sa.Column('cantidad_util', sa.Float(), nullable=False),
    sa.Column('precio_unitario', sa.Float(), nullable=True),
    sa.Column('precio_origen', sa.String(length=30), nullable=False),
    sa.Column('anulada', sa.Boolean(), nullable=False),
    sa.Column('momento', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['alimento_id'], ['alimentos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plan_id'], ['planes_semana.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['producto_id'], ['productos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    with op.batch_alter_table('compras', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_compras_plan_id'), ['plan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_compras_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('consumos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('comida_planificada_id', sa.Integer(), nullable=True),
    sa.Column('fecha', sa.Date(), nullable=False),
    sa.Column('momento', sa.String(length=20), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('kcal', sa.Float(), nullable=True),
    sa.Column('proteina', sa.Float(), nullable=True),
    sa.Column('hidratos', sa.Float(), nullable=True),
    sa.Column('grasas', sa.Float(), nullable=True),
    sa.Column('fibra', sa.Float(), nullable=True),
    sa.Column('instantanea', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('borrado', sa.Boolean(), nullable=False),
    sa.Column('creado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.Column('actualizado_en', app.modelos.FechaHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['comida_planificada_id'], ['comidas_planificadas.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    with op.batch_alter_table('consumos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_consumos_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_consumos_usuario_id'), ['usuario_id'], unique=False)
        batch_op.create_index('uq_consumo_previsto_unico', ['usuario_id', 'comida_planificada_id'], unique=True, sqlite_where=sa.text("tipo = 'previsto' AND borrado = 0"), postgresql_where=sa.text("tipo = 'previsto' AND borrado = false"))



def downgrade() -> None:
    with op.batch_alter_table('consumos', schema=None) as batch_op:
        batch_op.drop_index('uq_consumo_previsto_unico', sqlite_where=sa.text("tipo = 'previsto' AND borrado = 0"), postgresql_where=sa.text("tipo = 'previsto' AND borrado = false"))
        batch_op.drop_index(batch_op.f('ix_consumos_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_consumos_fecha'))

    op.drop_table('consumos')
    with op.batch_alter_table('compras', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_compras_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_compras_plan_id'))

    op.drop_table('compras')
    with op.batch_alter_table('sesiones_entreno', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sesiones_entreno_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_sesiones_entreno_fecha'))

    op.drop_table('sesiones_entreno')
    with op.batch_alter_table('rutina_ejercicios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rutina_ejercicios_rutina_id'))

    op.drop_table('rutina_ejercicios')
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_productos_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_productos_alimento_id'))

    op.drop_table('productos')
    with op.batch_alter_table('movimientos_despensa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_movimientos_despensa_usuario_id'))

    op.drop_table('movimientos_despensa')
    with op.batch_alter_table('ingredientes_receta', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ingredientes_receta_receta_id'))

    op.drop_table('ingredientes_receta')
    op.drop_table('envios_recordatorio')
    with op.batch_alter_table('despensa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_despensa_usuario_id'))

    op.drop_table('despensa')
    with op.batch_alter_table('comidas_planificadas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comidas_planificadas_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_comidas_planificadas_plan_id'))
        batch_op.drop_index(batch_op.f('ix_comidas_planificadas_fecha'))

    op.drop_table('comidas_planificadas')
    with op.batch_alter_table('cambios_menu', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cambios_menu_plan_id'))

    op.drop_table('cambios_menu')
    with op.batch_alter_table('suscripciones_push', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_suscripciones_push_usuario_id'))

    op.drop_table('suscripciones_push')
    with op.batch_alter_table('sesiones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sesiones_usuario_id'))

    op.drop_table('sesiones')
    with op.batch_alter_table('rutinas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rutinas_usuario_id'))

    op.drop_table('rutinas')
    with op.batch_alter_table('recordatorios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recordatorios_usuario_id'))

    op.drop_table('recordatorios')
    with op.batch_alter_table('recetas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recetas_usuario_id'))

    op.drop_table('recetas')
    with op.batch_alter_table('planes_semana', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_planes_semana_usuario_id'))

    op.drop_table('planes_semana')
    op.drop_table('perfiles')
    with op.batch_alter_table('operaciones_sync', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_operaciones_sync_usuario_id'))

    op.drop_table('operaciones_sync')
    with op.batch_alter_table('objetivos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_objetivos_usuario_id'))

    op.drop_table('objetivos')
    with op.batch_alter_table('mediciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mediciones_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_mediciones_fecha'))

    op.drop_table('mediciones')
    op.drop_table('invitaciones')
    with op.batch_alter_table('fotos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fotos_usuario_id'))

    op.drop_table('fotos')
    with op.batch_alter_table('eventos', schema=None) as batch_op:
        batch_op.drop_index('uq_evento_plan_dia', sqlite_where=sa.text('clave_plan IS NOT NULL AND borrado = 0'), postgresql_where=sa.text('clave_plan IS NOT NULL AND borrado = false'))
        batch_op.drop_index(batch_op.f('ix_eventos_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_eventos_fecha'))

    op.drop_table('eventos')
    with op.batch_alter_table('ejercicios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ejercicios_usuario_id'))

    op.drop_table('ejercicios')
    with op.batch_alter_table('diario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_diario_usuario_id'))

    op.drop_table('diario')
    with op.batch_alter_table('conflictos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_conflictos_usuario_id'))

    op.drop_table('conflictos')
    with op.batch_alter_table('campos_personalizados', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campos_personalizados_usuario_id'))

    op.drop_table('campos_personalizados')
    with op.batch_alter_table('alimentos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alimentos_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_alimentos_codigo_barras'))

    op.drop_table('alimentos')
    op.drop_table('usuarios')
    with op.batch_alter_table('intentos_acceso', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_intentos_acceso_ip'))
        batch_op.drop_index(batch_op.f('ix_intentos_acceso_clave'))

    op.drop_table('intentos_acceso')
