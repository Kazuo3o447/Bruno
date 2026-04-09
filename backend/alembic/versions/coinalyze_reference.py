"""
Migration: Create Coinalyze reference tables.
Unabhängige externe Datenquelle für Backtests.
"""

from alembic import op
import sqlalchemy as sa

revision = "coinalyze_reference"
down_revision = None  # Ändere dies je nach deiner aktuellsten Migration
branch_labels = None
depends_on = None


def upgrade():
    """Create reference schema and Coinalyze tables."""
    
    # Create reference schema
    op.execute("CREATE SCHEMA IF NOT EXISTS reference")
    
    # OHLCV Candles
    op.create_table(
        "coinalyze_candles",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("interval", sa.Text, nullable=False),
        sa.Column("open", sa.Numeric, nullable=False),
        sa.Column("high", sa.Numeric, nullable=False),
        sa.Column("low", sa.Numeric, nullable=False),
        sa.Column("close", sa.Numeric, nullable=False),
        sa.Column("volume", sa.Numeric),
        sa.Column("buy_volume", sa.Numeric),
        sa.PrimaryKeyConstraint("time", "symbol", "interval"),
        schema="reference",
    )
    op.execute(
        "SELECT create_hypertable('reference.coinalyze_candles', 'time', if_not_exists => TRUE)"
    )
    
    # Liquidations
    op.create_table(
        "coinalyze_liquidations",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("interval", sa.Text, nullable=False),
        sa.Column("long_liquidations_usd", sa.Numeric),
        sa.Column("short_liquidations_usd", sa.Numeric),
        sa.PrimaryKeyConstraint("time", "symbol", "interval"),
        schema="reference",
    )
    op.execute(
        "SELECT create_hypertable('reference.coinalyze_liquidations', 'time', if_not_exists => TRUE)"
    )
    
    # Open Interest
    op.create_table(
        "coinalyze_open_interest",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("interval", sa.Text, nullable=False),
        sa.Column("open_interest_open", sa.Numeric),
        sa.Column("open_interest_high", sa.Numeric),
        sa.Column("open_interest_low", sa.Numeric),
        sa.Column("open_interest_close", sa.Numeric),
        sa.PrimaryKeyConstraint("time", "symbol", "interval"),
        schema="reference",
    )
    op.execute(
        "SELECT create_hypertable('reference.coinalyze_open_interest', 'time', if_not_exists => TRUE)"
    )
    
    # Funding Rate
    op.create_table(
        "coinalyze_funding",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("interval", sa.Text, nullable=False),
        sa.Column("funding_open", sa.Numeric),
        sa.Column("funding_high", sa.Numeric),
        sa.Column("funding_low", sa.Numeric),
        sa.Column("funding_close", sa.Numeric),
        sa.PrimaryKeyConstraint("time", "symbol", "interval"),
        schema="reference",
    )
    op.execute(
        "SELECT create_hypertable('reference.coinalyze_funding', 'time', if_not_exists => TRUE)"
    )
    
    # Long/Short Ratio
    op.create_table(
        "coinalyze_long_short_ratio",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("interval", sa.Text, nullable=False),
        sa.Column("long_short_ratio", sa.Numeric),
        sa.Column("longs", sa.Numeric),
        sa.Column("shorts", sa.Numeric),
        sa.PrimaryKeyConstraint("time", "symbol", "interval"),
        schema="reference",
    )
    op.execute(
        "SELECT create_hypertable('reference.coinalyze_long_short_ratio', 'time', if_not_exists => TRUE)"
    )
    
    # Indexes for faster queries
    op.create_index(
        "idx_coinalyze_candles_symbol_interval",
        "coinalyze_candles",
        ["symbol", "interval"],
        schema="reference",
    )
    op.create_index(
        "idx_coinalyze_liquidations_symbol_interval",
        "coinalyze_liquidations",
        ["symbol", "interval"],
        schema="reference",
    )
    op.create_index(
        "idx_coinalyze_oi_symbol_interval",
        "coinalyze_open_interest",
        ["symbol", "interval"],
        schema="reference",
    )
    op.create_index(
        "idx_coinalyze_funding_symbol_interval",
        "coinalyze_funding",
        ["symbol", "interval"],
        schema="reference",
    )
    op.create_index(
        "idx_coinalyze_ls_ratio_symbol_interval",
        "coinalyze_long_short_ratio",
        ["symbol", "interval"],
        schema="reference",
    )


def downgrade():
    """Drop reference schema and tables."""
    op.execute("DROP SCHEMA IF EXISTS reference CASCADE")
