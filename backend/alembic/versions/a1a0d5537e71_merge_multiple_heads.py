"""merge multiple heads

Revision ID: a1a0d5537e71
Revises: 011_add_order_type_column, coinalyze_reference
Create Date: 2026-04-09 17:42:06.925285

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1a0d5537e71'
down_revision = ('011_add_order_type_column', 'coinalyze_reference')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
