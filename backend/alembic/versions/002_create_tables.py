"""Create all database tables for Bruno Trading Bot

Revision ID: 002_create_tables
Revises: 001_initial
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002_create_tables'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MarketCandle Table
    op.create_table('market_candles',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('time', 'symbol')
    )
    op.create_index('idx_market_candles_symbol_time', 'market_candles', ['symbol', 'time'])
    op.create_index('idx_market_candles_time', 'market_candles', ['time'])
    
    # TimescaleDB Hypertable
    op.execute("SELECT create_hypertable('market_candles', 'time', if_not_exists => TRUE);")
    
    # TradeAuditLog Table
    op.create_table('trade_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('action', sa.String(length=10), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column('quant_score', sa.Float(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('llm_reasoning', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trade_audit_symbol_time', 'trade_audit_logs', ['symbol', 'timestamp'])
    op.create_index('idx_trade_audit_status', 'trade_audit_logs', ['status'])
    
    # NewsEmbedding Table
    op.create_table('news_embeddings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('headline', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),  # Fallback for pgvector
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_confidence', sa.Float(), nullable=True),
        sa.Column('author', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_news_embeddings_timestamp', 'news_embeddings', ['timestamp'])
    op.create_index('idx_news_embeddings_source', 'news_embeddings', ['source'])
    op.create_index('idx_news_embeddings_sentiment', 'news_embeddings', ['sentiment_score'])
    
    # AgentStatus Table
    op.create_table('agent_status',
        sa.Column('agent_id', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_count', sa.Integer(), nullable=True),
        sa.Column('cpu_usage', sa.Float(), nullable=True),
        sa.Column('memory_usage', sa.Float(), nullable=True),
        sa.Column('uptime_seconds', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('agent_id')
    )
    op.create_index('idx_agent_status_heartbeat', 'agent_status', ['last_heartbeat'])
    
    # SystemMetrics Table
    op.create_table('system_metrics',
        sa.Column('timestamp', sa.DateTime(timezone=True), primary_key=True),
        sa.Column('api_response_time', sa.Float(), nullable=True),
        sa.Column('websocket_connections', sa.Integer(), nullable=True),
        sa.Column('redis_connections', sa.Integer(), nullable=True),
        sa.Column('active_trades', sa.Integer(), nullable=True),
        sa.Column('total_trades_today', sa.Integer(), nullable=True),
        sa.Column('win_rate_today', sa.Float(), nullable=True),
        sa.Column('cpu_usage', sa.Float(), nullable=True),
        sa.Column('memory_usage', sa.Float(), nullable=True),
        sa.Column('disk_usage', sa.Float(), nullable=True)
    )
    op.create_index('idx_system_metrics_timestamp', 'system_metrics', ['timestamp'])
    
    # Alert Table
    op.create_table('alerts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=50), nullable=True),
        sa.Column('extra_data', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alerts_timestamp', 'alerts', ['timestamp'])
    op.create_index('idx_alerts_unread', 'alerts', ['is_read'])
    op.create_index('idx_alerts_unresolved', 'alerts', ['is_resolved'])


def downgrade() -> None:
    op.drop_index('idx_alerts_unresolved', table_name='alerts')
    op.drop_index('idx_alerts_unread', table_name='alerts')
    op.drop_index('idx_alerts_timestamp', table_name='alerts')
    op.drop_table('alerts')
    
    op.drop_index('idx_system_metrics_timestamp', table_name='system_metrics')
    op.drop_table('system_metrics')
    
    op.drop_index('idx_agent_status_heartbeat', table_name='agent_status')
    op.drop_table('agent_status')
    
    op.drop_index('idx_news_embeddings_sentiment', table_name='news_embeddings')
    op.drop_index('idx_news_embeddings_source', table_name='news_embeddings')
    op.drop_index('idx_news_embeddings_timestamp', table_name='news_embeddings')
    op.drop_table('news_embeddings')
    
    op.drop_index('idx_trade_audit_status', table_name='trade_audit_logs')
    op.drop_index('idx_trade_audit_symbol_time', table_name='trade_audit_logs')
    op.drop_table('trade_audit_logs')
    
    op.execute("SELECT drop_hypertable('market_candles', if_exists => TRUE, force => TRUE);")
    op.drop_index('idx_market_candles_time', table_name='market_candles')
    op.drop_index('idx_market_candles_symbol_time', table_name='market_candles')
    op.drop_table('market_candles')
