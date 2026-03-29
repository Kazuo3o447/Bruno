import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.core.redis_client import get_redis_client
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt aktuelle Ticker-Daten für ein Symbol zurück."""
    try:
        ticker_data = await redis.get_cache(f"market:ticker:{symbol}")
        if not ticker_data:
            raise HTTPException(status_code=404, detail=f"No ticker data found for {symbol}")
        
        return {
            "symbol": symbol,
            "data": ticker_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ticker for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt aktuelle Orderbook-Daten für ein Symbol zurück."""
    try:
        orderbook_data = await redis.get_cache(f"market:orderbook:{symbol}")
        if not orderbook_data:
            raise HTTPException(status_code=404, detail=f"No orderbook data found for {symbol}")
        
        return {
            "symbol": symbol,
            "data": orderbook_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching orderbook for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/price/{symbol}")
async def get_price(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt nur den aktuellen Preis für ein Symbol zurück."""
    try:
        ticker_data = await redis.get_cache(f"market:ticker:{symbol}")
        if not ticker_data:
            raise HTTPException(status_code=404, detail=f"No price data found for {symbol}")
        
        price = ticker_data.get("last_price") or ticker_data.get("price")
        if price is None:
            raise HTTPException(status_code=404, detail=f"No price found in ticker data")
        
        return {
            "symbol": symbol,
            "price": float(price),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
