"""Create market_regimes hypertable (Phase C)

Revision ID: 008_market_regimes
Revises: 007_trade_debriefs
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008_market_regimes'
down_revision = '007_trade_debriefs'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'market_regimes',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('regime', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('key_signals', postgresql.JSONB(), nullable=True),
        sa.Column('grss', sa.Float(), nullable=True),
    )
    op.create_index('idx_market_regimes_time', 'market_regimes', ['time'])
    # TimescaleDB Hypertable
    op.execute("SELECT create_hypertable('market_regimes', 'time', if_not_exists => TRUE)")

def downgrade():
    op.drop_table('market_regimes')
