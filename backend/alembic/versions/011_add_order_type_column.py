"""Add order_type column to trade_audit_logs table

Revision ID: 011_add_order_type_column
Revises: 010_trade_mode_column
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa


revision = '011_add_order_type_column'
down_revision = '010_trade_mode_column'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'trade_audit_logs',
        sa.Column('order_type', sa.String(20), nullable=True)
    )


def downgrade():
    op.drop_column('trade_audit_logs', 'order_type')