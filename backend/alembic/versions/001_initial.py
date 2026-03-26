"""Initial migration: Create TimescaleDB and pgvector extensions

KRITISCH: Diese Extensions MÜSSEN vor Tabellen-Erstellung existieren.
"""
from alembic import op
import sqlalchemy as sa
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # KRITISCH: Extensions vor Tabellen erstellen
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Beispiel-Tabelle für Kursdaten (wird zu hypertable)
    op.create_table(
        'market_data',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('high', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('low', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('close', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('volume', sa.Numeric(precision=24, scale=8), nullable=True),
        sa.PrimaryKeyConstraint('id', 'timestamp')
    )
    
    # Hypertable für Zeitseriendaten erstellen
    op.execute("SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);")
    
    # Indexe
    op.create_index('idx_market_data_symbol_time', 'market_data', ['symbol', 'timestamp'])
    
    # Beispiel-Tabelle für Sentiment-Embeddings
    op.create_table(
        'sentiment_embeddings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('embedding', sa.Text(), nullable=True),  # pgvector speichert als Array
        sa.Column('sentiment_score', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_sentiment_time', 'sentiment_embeddings', ['timestamp'])


def downgrade() -> None:
    op.drop_index('idx_sentiment_time', table_name='sentiment_embeddings')
    op.drop_table('sentiment_embeddings')
    op.drop_index('idx_market_data_symbol_time', table_name='market_data')
    op.execute("SELECT drop_hypertable('market_data', if_exists => TRUE, force => TRUE);")
    op.drop_table('market_data')
    
    # Extensions entfernen (optional - meist nicht empfohlen)
    # op.execute("DROP EXTENSION IF EXISTS vector;")
    # op.execute("DROP EXTENSION IF EXISTS timescaledb;")
