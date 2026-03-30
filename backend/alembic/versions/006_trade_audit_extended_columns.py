"""Extend trade_audit_logs with Phase C/D columns

Revision ID: 006_trade_audit_extended
Revises: 005_positions_table
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '006_trade_audit_extended'
down_revision = '005_positions_table'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('trade_audit_logs',
        sa.Column('layer1_output', postgresql.JSONB(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('layer2_output', postgresql.JSONB(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('layer3_output', postgresql.JSONB(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('regime', sa.String(20), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('exit_reason', sa.String(50), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('hold_duration_minutes', sa.Integer(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('pnl_pct', sa.Float(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('mae_pct', sa.Float(), nullable=True))
    op.add_column('trade_audit_logs',
        sa.Column('grss_at_entry', sa.Float(), nullable=True))

def downgrade():
    for col in ['layer1_output','layer2_output','layer3_output','regime',
                'exit_reason','hold_duration_minutes','pnl_pct','mae_pct','grss_at_entry']:
        op.drop_column('trade_audit_logs', col)
