"""
Agenten Schemas

Strikte Pydantic-Typisierung für die Agenten-Kommunikation.
Definiert die Datenstrukturen für Signale, Ticks und Orders.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class TickData(BaseModel):
    symbol: str
    price: float
    volume: float
    timestamp: int

class QuantSignal(BaseModel):
    symbol: str
    signal: int  # -1 (Bearish), 0 (Neutral), 1 (Bullish)
    confidence: float
    indicators: Dict[str, Any]
    timestamp: str

class SentimentSignal(BaseModel):
    symbol: str
    signal: int
    confidence: float
    reasoning: str
    timestamp: str

class ExecutionOrder(BaseModel):
    symbol: str
    action: str  # "buy" oder "sell"
    reason: str
    quant_confidence: float
    sentiment_confidence: float
    timestamp: str
