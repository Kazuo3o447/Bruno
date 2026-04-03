"""Add trade_mode columns to trade audit and debreifs

Revision ID: 010_trade_mode_column
Revises: 008_market_regimes
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa


revision = '010_trade_mode_column'
down_revision = '008_market_regimes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'trade_audit_logs',
        sa.Column('trade_mode', sa.String(20), nullable=True, server_default='production')
    )
    op.create_index('ix_trade_audit_logs_trade_mode', 'trade_audit_logs', ['trade_mode'])

    op.add_column(
        'trade_debriefs',
        sa.Column('trade_mode', sa.String(20), nullable=True, server_default='production')
    )
    op.create_index('ix_trade_debriefs_trade_mode', 'trade_debriefs', ['trade_mode'])


def downgrade():
    op.drop_index('ix_trade_debriefs_trade_mode', table_name='trade_debriefs')
    op.drop_column('trade_debriefs', 'trade_mode')

    op.drop_index('ix_trade_audit_logs_trade_mode', table_name='trade_audit_logs')
    op.drop_column('trade_audit_logs', 'trade_mode')
