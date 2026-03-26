from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

class QuantSignal(BaseModel):
    symbol: str
    signal: int  # -1 (Bearish) bis 1 (Bullish)
    confidence: float  # 0.0 bis 1.0
    indicators: Dict[str, Any]  # z.B. {"rsi": 25.5, "trend": "down"}
    timestamp: datetime
