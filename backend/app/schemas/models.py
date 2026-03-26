from sqlalchemy import Column, String, Float, DateTime, Integer, Text, Boolean, Index
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime, timezone
import uuid


class MarketCandle(Base):
    """Marktdaten (Kerzen) für TimescaleDB Hypertable."""
    __tablename__ = "market_candles"
    
    # TimescaleDB benötigt time als Primary Key Teil
    time = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(20), primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # Indexe für schnelle Abfragen
    __table_args__ = (
        Index('idx_market_candles_symbol_time', 'symbol', 'time'),
        Index('idx_market_candles_time', 'time'),
    )

class OrderbookSnapshot(Base):
    """Tiefe des Orderbuchs für Liquiditätsanalysen (Hypertable)."""
    __tablename__ = "orderbook_snapshots"
    
    time = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(20), primary_key=True)
    bids_volume_usdt = Column(Float, nullable=False) # Total USDT volume in top 20 bids
    asks_volume_usdt = Column(Float, nullable=False) # Total USDT volume in top 20 asks
    imbalance_ratio = Column(Float, nullable=False)  # bids / asks
    
    __table_args__ = (
        Index('idx_ob_snapshots_symbol_time', 'symbol', 'time'),
    )

class Liquidation(Base):
    """Zwangsliquidierungen (Hypertable)."""
    __tablename__ = "liquidations"
    
    time = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(20), primary_key=True)
    side = Column(String(10), nullable=False)        # BUY (short liquidation) / SELL (long liquidation)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    total_usdt = Column(Float, nullable=False)
    
    __table_args__ = (
        Index('idx_liquidations_symbol_time', 'symbol', 'time'),
    )

class FundingRate(Base):
    """Funding Rates von Perpetual Futures (Hypertable)."""
    __tablename__ = "funding_rates"
    
    time = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(20), primary_key=True)
    rate = Column(Float, nullable=False)
    mark_price = Column(Float, nullable=False)
    
    __table_args__ = (
        Index('idx_funding_rates_symbol_time', 'symbol', 'time'),
    )



class TradeAuditLog(Base):
    """Audit-Log für alle Trades."""
    __tablename__ = "trade_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # 'buy', 'sell'
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    
    # Agent-Scores
    quant_score = Column(Float)
    sentiment_score = Column(Float)
    risk_score = Column(Float)
    
    # LLM Reasoning
    llm_reasoning = Column(Text)
    llm_model = Column(String(50))
    
    # Status
    status = Column(String(20), default="open")  # open, filled, cancelled, failed
    filled_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    # Indexe
    __table_args__ = (
        Index('idx_trade_audit_symbol_time', 'symbol', 'timestamp'),
        Index('idx_trade_audit_status', 'status'),
    )


class NewsEmbedding(Base):
    """News-Artikel mit Vektor-Embeddings für pgvector."""
    __tablename__ = "news_embeddings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = Column(String(50), nullable=False)  # cryptopanic, reddit, twitter, etc.
    source_url = Column(Text)
    headline = Column(Text, nullable=False)
    content = Column(Text)
    
    # pgvector Embedding (1536 ist Standard für viele Modelle)
    embedding = Column(Vector(1536))
    sentiment_score = Column(Float)  # -1.0 bis 1.0
    sentiment_confidence = Column(Float)  # 0.0 bis 1.0
    
    # Metadaten
    author = Column(String(100))
    tags = Column(Text)  # JSON Array als Text
    language = Column(String(10), default="en")
    
    # Indexe
    __table_args__ = (
        Index('idx_news_embeddings_timestamp', 'timestamp'),
        Index('idx_news_embeddings_source', 'source'),
        Index('idx_news_embeddings_sentiment', 'sentiment_score'),
    )


class AgentStatus(Base):
    """Status der einzelnen Agenten."""
    __tablename__ = "agent_status"
    
    agent_id = Column(String(50), primary_key=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="idle")  # idle, running, error, stopped
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    error_message = Column(Text)
    processed_count = Column(Integer, default=0)
    
    # Metadaten
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    uptime_seconds = Column(Integer, default=0)
    
    # Index
    __table_args__ = (
        Index('idx_agent_status_heartbeat', 'last_heartbeat'),
    )


class SystemMetrics(Base):
    """System-Metriken für Monitoring."""
    __tablename__ = "system_metrics"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    
    # Performance Metriken
    api_response_time = Column(Float)  # ms
    websocket_connections = Column(Integer, default=0)
    redis_connections = Column(Integer, default=0)
    
    # Trading Metriken
    active_trades = Column(Integer, default=0)
    total_trades_today = Column(Integer, default=0)
    win_rate_today = Column(Float)
    
    # System Metriken
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    
    # Index
    __table_args__ = (
        Index('idx_system_metrics_timestamp', 'timestamp'),
    )


class Alert(Base):
    """Alerts und Benachrichtigungen."""
    __tablename__ = "alerts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    alert_type = Column(String(50), nullable=False)  # error, warning, info, success
    source = Column(String(50), nullable=False)  # system, agent, manual
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # Status
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(50))
    
    # Metadaten
    extra_data = Column(Text)  # JSON als Text
    severity = Column(String(10), default="medium")  # low, medium, high, critical
    
    # Indexe
    __table_args__ = (
        Index('idx_alerts_timestamp', 'timestamp'),
        Index('idx_alerts_unread', 'is_read'),
        Index('idx_alerts_unresolved', 'is_resolved'),
    )
