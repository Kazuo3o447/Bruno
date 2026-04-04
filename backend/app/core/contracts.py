from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid

class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class SignalEnvelope(BaseModel):
    """Standard-Hülle für JEDES Signal im System."""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    version: str = "2.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str

class QuantSignalV2(SignalEnvelope):
    """Quant Agent → Risk Agent"""
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    # Beinhaltet z.B. {"price": 60000.0, "rsi_5m": 30.5, "macd_1h": 0.003, "atr_1h": 200.0}
    indicators: Dict[str, float]
    # Macro context wie "bullish", "oversold" etc.
    market_state: Dict[str, str]
    reasoning: str

class SentimentSignalV2(SignalEnvelope):
    """Sentiment Agent → Risk Agent"""
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=-1.0, le=1.0)
    sources: List[str]  # e.g., ["CoinMarketCap", "RSS:coindesk"]
    reasoning: str
    article_count: int

class RiskDecision(SignalEnvelope):
    """Risk Agent → Execution Agent"""
    action: SignalDirection
    approved: bool
    position_size_usd: float
    stop_loss_price: float
    take_profit_price: float
    risk_reward_ratio: float
    market_context: Dict[str, Any]
    reasoning: str
    quant_signal: Optional[QuantSignalV2] = None
    sentiment_signal: Optional[SentimentSignalV2] = None

class TradeExecution(SignalEnvelope):
    """Execution Agent → Dashboard/Telegram"""
    action: str  # "BUY" / "SELL"
    entry_price: float
    quantity: float
    position_size_usd: float
    stop_loss: float
    take_profit: float
    risk_decision: RiskDecision
    execution_status: str  # "FILLED" / "FAILED" / "PAPER"
    order_id: Optional[str] = None
