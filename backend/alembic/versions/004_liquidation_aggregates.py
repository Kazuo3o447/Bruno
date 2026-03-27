"""Add liquidation aggregates

Revision ID: 004_liquidation_aggregates
Revises: 003_market_context
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004_liquidation_aggregates'
down_revision = '003_market_context'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Continuous Aggregate for Liquidations (1h)
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS liquidations_1h
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS time,
            symbol,
            side,
            sum(total_usdt) AS total_liquidation_usdt,
            count(*) AS liquidation_count
        FROM liquidations
        GROUP BY time_bucket('1 hour', time), symbol, side
        WITH NO DATA;
    """)
    
    op.execute("""
        SELECT add_continuous_aggregate_policy('liquidations_1h',
            start_offset => NULL,
            end_offset => NULL,
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS liquidations_1h CASCADE;")
