"""
LLM Cascade Router — Phase C

API-Endpoints für LLM-Kaskade Monitoring und Debugging.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.core.redis_client import get_redis_client
from app.core.database import get_db_session_factory
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm", tags=["llm-cascade"])


@router.get("/cascade/status")
async def get_cascade_status(redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt Status der LLM-Kaskade und letzten Run zurück."""
    try:
        # Letzter Cascade-Run
        last_cascade = await redis.get_cache("bruno:llm:last_cascade") or {}
        
        # Regime-Zustand
        regime_state = await redis.get_cache("bruno:regime:state") or {}
        
        # Decision History
        decision_history = await redis.get_cache("bruno:llm:decision_history") or []
        
        # Failure Watchlist
        failure_watchlist = await redis.get_cache("bruno:failure_watchlist") or []
        
        return {
            "status": "active",
            "last_run": {
                "decision": last_cascade.get("decision", "N/A"),
                "aborted_at": last_cascade.get("aborted_at"),
                "regime": last_cascade.get("regime", "N/A"),
                "confidence": last_cascade.get("confidence", 0.0),
                "duration_ms": last_cascade.get("duration_ms", 0.0),
                "layer1_regime": last_cascade.get("layer1_regime"),
                "layer1_confidence": last_cascade.get("layer1_confidence", 0.0),
                "layer2_decision": last_cascade.get("layer2_decision"),
                "layer3_blocker": last_cascade.get("layer3_blocker"),
            },
            "regime": {
                "current": regime_state.get("regime", "unknown"),
                "confirmed": regime_state.get("confirmed", False),
                "confirmation_count": regime_state.get("confirmation_count", 0),
                "config": regime_state.get("config", {}),
                "updated_at": regime_state.get("updated_at"),
            },
            "decision_history": decision_history[-5:],  # Letzte 5 Entscheidungen
            "failure_watchlist": failure_watchlist[-10:],  # Letzte 10 Failure-Patterns
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Cascade Status Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade/metrics")
async def get_cascade_metrics(redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt Performance-Metriken der LLM-Kaskade zurück."""
    try:
        # Letzte 50 Runs aus Redis holen (wenn implementiert)
        # Für jetzt: Basis-Metriken
        last_cascade = await redis.get_cache("bruno:llm:last_cascade") or {}
        
        return {
            "performance": {
                "avg_duration_ms": last_cascade.get("duration_ms", 0.0),
                "last_decision": last_cascade.get("decision", "N/A"),
                "last_confidence": last_cascade.get("confidence", 0.0),
                "success_rate": 0.0,  # TODO: Aus History berechnen
                "gate_pass_rate": {
                    "gate1": 0.0,  # TODO: Aus History berechnen
                    "gate2": 0.0,
                    "gate3": 0.0,
                }
            },
            "regime_distribution": {
                # TODO: Aus History berechnen
                "trending_bull": 0,
                "ranging": 0,
                "high_vola": 0,
                "bear": 0,
                "unknown": 0,
            },
            "decision_distribution": {
                "BUY": 0,
                "SELL": 0,
                "HOLD": 0,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Cascade Metrics Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cascade/force-regime")
async def force_regime(
    regime: str,
    redis=Depends(get_redis_client)
) -> Dict[str, Any]:
    """Setzt Regime manuell (für Testing/Debug)."""
    try:
        from app.services.regime_config import RegimeManager
        
        regime_manager = RegimeManager(redis)
        await regime_manager.force_regime(regime)
        
        return {
            "status": "success",
            "regime": regime,
            "message": f"Regime manuell gesetzt auf: {regime}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Force Regime Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade/decision-history")
async def get_decision_history(
    limit: int = 20,
    redis=Depends(get_redis_client)
) -> Dict[str, Any]:
    """Gibt Decision History zurück."""
    try:
        history = await redis.get_cache("bruno:llm:decision_history") or []
        
        return {
            "history": history[-limit:],
            "total_count": len(history),
            "limit": limit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Decision History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade/failure-patterns")
async def get_failure_patterns(
    redis=Depends(get_redis_client)
) -> Dict[str, Any]:
    """Gibt aktive Failure-Patterns zurück."""
    try:
        patterns = await redis.get_cache("bruno:failure_watchlist") or []
        
        return {
            "patterns": patterns,
            "count": len(patterns),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failure Patterns Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cascade/clear-history")
async def clear_cascade_history(redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Löscht Cascade-History (für Testing)."""
    try:
        await redis.delete_cache("bruno:llm:decision_history")
        await redis.delete_cache("bruno:llm:last_cascade")
        
        return {
            "status": "success",
            "message": "Cascade History gelöscht",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Clear History Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
