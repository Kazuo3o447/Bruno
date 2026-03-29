"""
Positions API — Phase D

Endpoints für Position-Tracking und Monitoring.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from app.core.redis_client import get_redis_client
from app.core.database import get_db_session_factory
from app.services.position_tracker import PositionTracker
from app.services.position_monitor import PositionMonitor
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/positions", tags=["positions"])


# Dependency Injection
def get_position_tracker(redis=Depends(get_redis_client), db=Depends(get_db_session_factory)):
    return PositionTracker(redis, db)


def get_position_monitor(redis=Depends(get_redis_client), db=Depends(get_db_session_factory)):
    tracker = PositionTracker(redis, db)
    return PositionMonitor(tracker, redis)


@router.get("/open")
async def get_open_positions(
    symbol: Optional[str] = Query(None, description="Symbol filter (z.B. BTCUSDT)"),
    tracker: PositionTracker = Depends(get_position_tracker)
) -> Dict[str, Any]:
    """Gibt offene Positionen zurück."""
    try:
        if symbol:
            # Einzelne Position
            position = await tracker.get_open_position(symbol)
            if position:
                return {"position": position, "count": 1}
            else:
                return {"position": None, "count": 0}
        else:
            # Alle offenen Positionen (TODO: Multi-Symbol Support)
            position = await tracker.get_open_position("BTCUSDT")
            return {
                "positions": [position] if position else [],
                "count": 1 if position else 0
            }
    except Exception as e:
        logger.error(f"Get Open Positions Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/status")
async def get_position_status(
    symbol: str,
    tracker: PositionTracker = Depends(get_position_tracker)
) -> Dict[str, Any]:
    """Gibt detaillierten Status einer Position zurück."""
    try:
        position = await tracker.get_open_position(symbol)
        if not position:
            return {
                "symbol": symbol,
                "has_position": False,
                "status": "no_position"
            }
            
        # Aktuellen Preis holen
        current_price = None
        try:
            from app.core.redis_client import RedisClient
            redis = RedisClient()
            await redis.connect()
            
            ticker_data = await redis.get_cache(f"market:ticker:{symbol}")
            if ticker_data and "price" in ticker_data:
                current_price = float(ticker_data["price"])
                
            # P&L berechnen
            if current_price:
                side = position["side"]
                entry_price = position["entry_price"]
                if side == "long":
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                    
                position["current_price"] = current_price
                position["current_pnl_pct"] = round(pnl_pct, 6)
                position["current_pnl_eur"] = round(pnl_pct * entry_price * position["quantity"], 4)
                
        except Exception as e:
            logger.warning(f"Preis-Berechnung für {symbol}: {e}")
            
        return {
            "symbol": symbol,
            "has_position": True,
            "position": position,
            "status": "open"
        }
    except Exception as e:
        logger.error(f"Position Status Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/open")
async def test_open_position(
    symbol: str = "BTCUSDT",
    side: str = "long",
    entry_price: float = 60000.0,
    quantity: float = 0.001,
    stop_loss_price: float = 59000.0,
    take_profit_price: float = 62000.0,
    tracker: PositionTracker = Depends(get_position_tracker)
) -> Dict[str, Any]:
    """Test-Endpoint zum Öffnen einer Position (nur für DRY_RUN)."""
    try:
        # Phase C Felder simulieren
        layer1_output = {"regime": "trending_bull", "confidence": 0.8}
        layer2_output = {"decision": "BUY", "confidence": 0.7}
        layer3_output = {"blocker": False}
        
        position_id = await tracker.open_position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_trade_id=f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            grss_at_entry=55.0,
            layer1_output=layer1_output,
            layer2_output=layer2_output,
            layer3_output=layer3_output,
            regime="trending_bull"
        )
        
        return {
            "status": "success",
            "position_id": position_id,
            "message": f"Test Position für {symbol} geöffnet",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except ValueError as e:
        logger.error(f"Position Open Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Test Open Position Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/close")
async def test_close_position(
    symbol: str = "BTCUSDT",
    exit_price: float = 61000.0,
    reason: str = "take_profit",
    tracker: PositionTracker = Depends(get_position_tracker)
) -> Dict[str, Any]:
    """Test-Endpoint zum Schließen einer Position."""
    try:
        position = await tracker.close_position(
            symbol=symbol,
            exit_price=exit_price,
            reason=reason,
            exit_trade_id=f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )
        
        if not position:
            raise HTTPException(status_code=404, detail=f"Keine offene Position für {symbol}")
            
        return {
            "status": "success",
            "position": position,
            "message": f"Test Position für {symbol} geschlossen: {reason}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Test Close Position Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitor/status")
async def get_monitor_status(
    monitor: PositionMonitor = Depends(get_position_monitor)
) -> Dict[str, Any]:
    """Gibt Status des Position Monitors zurück."""
    try:
        return await monitor.get_monitor_status()
    except Exception as e:
        logger.error(f"Monitor Status Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/start")
async def start_monitor(
    monitor: PositionMonitor = Depends(get_position_monitor)
) -> Dict[str, Any]:
    """Startet den Position Monitor."""
    try:
        await monitor.start()
        return {
            "status": "success",
            "message": "Position Monitor gestartet",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Start Monitor Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/stop")
async def stop_monitor(
    monitor: PositionMonitor = Depends(get_position_monitor)
) -> Dict[str, Any]:
    """Stoppt den Position Monitor."""
    try:
        await monitor.stop()
        return {
            "status": "success",
            "message": "Position Monitor gestoppt",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Stop Monitor Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_position_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db_session_factory)
) -> Dict[str, Any]:
    """Gibt Position History aus der Datenbank zurück."""
    try:
        from sqlalchemy import text
        
        async with db() as session:
            if symbol:
                query = text("""
                    SELECT * FROM positions 
                    WHERE symbol = :symbol 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """)
                result = await session.execute(query, {"symbol": symbol, "limit": limit})
            else:
                query = text("""
                    SELECT * FROM positions 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """)
                result = await session.execute(query, {"limit": limit})
                
            rows = result.fetchall()
            positions = [dict(row) for row in rows]
            
        return {
            "positions": positions,
            "count": len(positions),
            "symbol_filter": symbol,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Position History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
