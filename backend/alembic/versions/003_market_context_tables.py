"""Add rich market context tables

Revision ID: 003_market_context
Revises: 002_create_tables
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '003_market_context'
down_revision = '002_create_tables'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. OrderbookSnapshot Table
    op.create_table('orderbook_snapshots',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('bids_volume_usdt', sa.Float(), nullable=False),
        sa.Column('asks_volume_usdt', sa.Float(), nullable=False),
        sa.Column('imbalance_ratio', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('time', 'symbol')
    )
    op.create_index('idx_ob_snapshots_symbol_time', 'orderbook_snapshots', ['symbol', 'time'])
    op.execute("SELECT create_hypertable('orderbook_snapshots', 'time', if_not_exists => TRUE);")

    # 2. Liquidation Table
    op.create_table('liquidations',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('total_usdt', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('time', 'symbol')
    )
    op.create_index('idx_liquidations_symbol_time', 'liquidations', ['symbol', 'time'])
    op.execute("SELECT create_hypertable('liquidations', 'time', if_not_exists => TRUE);")

    # 3. FundingRate Table
    op.create_table('funding_rates',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('mark_price', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('time', 'symbol')
    )
    op.create_index('idx_funding_rates_symbol_time', 'funding_rates', ['symbol', 'time'])
    op.execute("SELECT create_hypertable('funding_rates', 'time', if_not_exists => TRUE);")

    # 4. Continuous Aggregates for MarketCandles
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS candles_5m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('5 minutes', time) AS time,
            symbol,
            first(open, time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, time) AS close,
            sum(volume) AS volume
        FROM market_candles
        GROUP BY time_bucket('5 minutes', time), symbol
        WITH NO DATA;
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('candles_5m',
            start_offset => NULL,
            end_offset => NULL,
            schedule_interval => INTERVAL '5 minutes',
            if_not_exists => TRUE);
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS candles_15m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('15 minutes', time) AS time,
            symbol,
            first(open, time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, time) AS close,
            sum(volume) AS volume
        FROM market_candles
        GROUP BY time_bucket('15 minutes', time), symbol
        WITH NO DATA;
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('candles_15m',
            start_offset => NULL,
            end_offset => NULL,
            schedule_interval => INTERVAL '15 minutes',
            if_not_exists => TRUE);
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1h
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS time,
            symbol,
            first(open, time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, time) AS close,
            sum(volume) AS volume
        FROM market_candles
        GROUP BY time_bucket('1 hour', time), symbol
        WITH NO DATA;
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('candles_1h',
            start_offset => NULL,
            end_offset => NULL,
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_1h CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_15m CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS candles_5m CASCADE;")
    
    op.drop_table('funding_rates')
    op.drop_table('liquidations')
    op.drop_table('orderbook_snapshots')
