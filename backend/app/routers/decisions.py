"""
Decision Feed Router - Dokumentiert alle Evaluierungs-Zyklen.

GET /api/v1/decisions/feed - Alle Entscheidungen der letzten Zeit
GET /api/v1/decisions/veto-history - Veto-Zustandswechsel
"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.redis_client import get_redis_client, redis_client
import json
from typing import Optional

router = APIRouter(tags=["decisions"])


@router.get("/decisions/feed")
async def get_decision_feed(limit: int = 50):
    """
    Alle Evaluierungs-Zyklen der letzten Zeit.
    Zeigt warum Trades gesetzt oder NICHT gesetzt wurden.
    """
    try:
        raw = await redis_client.redis.lrange("bruno:decisions:feed", 0, limit - 1)
        events = [json.loads(e) for e in raw]

        # Statistik
        outcomes = [e.get("outcome", "") for e in events]
        return {
            "events": events,
            "count": len(events),
            "stats": {
                "ofi_below_threshold": sum(1 for o in outcomes if o == "OFI_BELOW_THRESHOLD"),
                "cascade_hold": sum(1 for o in outcomes if "CASCADE" in o and "SIGNAL" not in o),
                "signals_generated": sum(1 for o in outcomes if "SIGNAL_" in o),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/veto-history")
async def get_veto_history():
    """Veto-Zustandswechsel der letzten Zeit."""
    try:
        raw = await redis_client.redis.lrange("bruno:veto:history", 0, 49)
        return {"events": [json.loads(e) for e in raw]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
