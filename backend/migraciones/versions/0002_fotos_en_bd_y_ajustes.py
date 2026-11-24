from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.modelos


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("fotos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contenido", sa.LargeBinary(), nullable=True))
    op.create_table(
        "ajustes_servidor",
        sa.Column("clave", sa.String(length=60), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("actualizado_en", app.modelos.FechaHoraUTC(), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )


def downgrade() -> None:
    op.drop_table("ajustes_servidor")
    with op.batch_alter_table("fotos", schema=None) as batch_op:
        batch_op.drop_column("contenido")
