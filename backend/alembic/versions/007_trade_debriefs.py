"""Create trade_debriefs table (Phase F)

Revision ID: 007_trade_debriefs
Revises: 006_trade_audit_extended
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '007_trade_debriefs'
down_revision = '006_trade_audit_extended'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'trade_debriefs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('trade_id', sa.String(36), nullable=False),  # FK zu positions.id
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('decision_quality', sa.String(20), nullable=True),
        sa.Column('key_signal', sa.Text(), nullable=True),
        sa.Column('improvement', sa.Text(), nullable=True),
        sa.Column('pattern', sa.Text(), nullable=True),
        sa.Column('regime_assessment', sa.Text(), nullable=True),
        sa.Column('raw_llm_response', postgresql.JSONB(), nullable=True),
    )
    op.create_index('idx_trade_debriefs_trade_id', 'trade_debriefs', ['trade_id'])
    op.create_index('idx_trade_debriefs_timestamp', 'trade_debriefs', ['timestamp'])

def downgrade():
    op.drop_table('trade_debriefs')
