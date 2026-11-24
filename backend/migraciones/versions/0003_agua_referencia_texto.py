from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("perfiles", schema=None) as batch_op:
        batch_op.alter_column("agua_referencia", existing_type=sa.String(length=60), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("perfiles", schema=None) as batch_op:
        batch_op.alter_column("agua_referencia", existing_type=sa.Text(), type_=sa.String(length=60), existing_nullable=True)
