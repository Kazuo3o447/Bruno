from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.schemas.models import TradeAuditLog
from typing import List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class TradeHistorySchema(BaseModel):
    id: str
    timestamp: datetime
    symbol: str
    action: str
    price: float
    quantity: float
    total: float
    status: str

    class Config:
        from_attributes = True

@router.get("/history", response_model=List[TradeHistorySchema])
async def get_trade_history(
    symbol: str = "BTCUSDT",
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Gibt die letzten Trades für ein Symbol zurück."""
    try:
        query = select(TradeAuditLog).where(
            TradeAuditLog.symbol == symbol
        ).order_by(desc(TradeAuditLog.timestamp)).limit(limit)
        
        result = await db.execute(query)
        trades = result.scalars().all()
        return trades
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
