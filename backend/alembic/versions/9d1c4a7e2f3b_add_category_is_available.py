"""add is_available to menu categories

Revision ID: 9d1c4a7e2f3b
Revises: 7a3f9e5b1c2d
Create Date: 2026-08-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9d1c4a7e2f3b'
down_revision: Union[str, None] = '7a3f9e5b1c2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'menu_categories',
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('menu_categories', 'is_available')
