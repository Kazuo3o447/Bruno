"""
Positions Table Migration — Phase D

Erstellt die positions Tabelle für Position-Tracking.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '005_positions_table'
down_revision = '004_liquidation_aggregates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Positions Tabelle erstellen
    op.create_table(
        'positions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entry_trade_id', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('stop_loss_price', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('take_profit_price', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('grss_at_entry', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('layer1_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('layer2_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('layer3_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('regime', sa.String(length=20), nullable=True),
        sa.Column('mae_pct', sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column('mfe_pct', sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column('current_pnl_pct', sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('exit_price', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('exit_reason', sa.String(length=20), nullable=True),
        sa.Column('exit_trade_id', sa.String(length=100), nullable=True),
        sa.Column('pnl_eur', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('pnl_pct', sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column('hold_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_positions_symbol', 'symbol'),
        sa.Index('idx_positions_status', 'status'),
        sa.Index('idx_positions_entry_time', 'entry_time'),
        sa.Index('idx_positions_symbol_status', 'symbol', 'status'),
    )
    
    # Updated_at Trigger erstellen
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_positions_updated_at 
            BEFORE UPDATE ON positions 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Trigger löschen
    op.execute("DROP TRIGGER IF EXISTS update_positions_updated_at ON positions")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Tabelle löschen
    op.drop_table('positions')
