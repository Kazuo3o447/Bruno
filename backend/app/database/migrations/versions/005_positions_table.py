"""Add positions table (Phase D)

Revision ID: 005_positions_table
Revises: 9033e2a4a2f9
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005_positions_table'
down_revision = '9033e2a4a2f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'positions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),          # long | short
        sa.Column('entry_price', sa.Float, nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entry_trade_id', sa.String(64)),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('stop_loss_price', sa.Float, nullable=False),
        sa.Column('take_profit_price', sa.Float, nullable=False),

        # LLM Context (Phase C forward-compatible)
        sa.Column('grss_at_entry', sa.Float, default=0.0),
        sa.Column('layer1_output', postgresql.JSONB),
        sa.Column('layer2_output', postgresql.JSONB),
        sa.Column('layer3_output', postgresql.JSONB),
        sa.Column('regime', sa.String(20), default='unknown'),

        # Exit fields
        sa.Column('exit_price', sa.Float),
        sa.Column('exit_time', sa.DateTime(timezone=True)),
        sa.Column('exit_reason', sa.String(50)),
        sa.Column('exit_trade_id', sa.String(64)),

        # Analytics
        sa.Column('pnl_eur', sa.Float),
        sa.Column('pnl_pct', sa.Float),
        sa.Column('hold_duration_minutes', sa.Integer),
        sa.Column('mae_pct', sa.Float, default=0.0),
        sa.Column('mfe_pct', sa.Float, default=0.0),

        sa.Column('status', sa.String(20), default='open'),   # open | closed
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    op.create_index('idx_positions_symbol_status', 'positions', ['symbol', 'status'])
    op.create_index('idx_positions_created_at', 'positions', ['created_at'])
    op.create_index('idx_positions_status', 'positions', ['status'])


def downgrade() -> None:
    op.drop_table('positions')
