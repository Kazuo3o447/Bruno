"""
Risk API Router - Kill-Switch Management.

POST /api/v1/risk/reset_killswitch - Manuelles Zurücksetzen des Kill-Switches
GET /api/v1/risk/killswitch_status - Status des Kill-Switches abfragen
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime, timezone

router = APIRouter(tags=["risk"])


class ResetKillSwitchRequest(BaseModel):
    """Request Body für Kill-Switch Reset."""
    date: str = Field(..., description="Datum im ISO-Format (YYYY-MM-DD)")
    scope: Literal["daily", "consecutive", "all"] = Field(
        ..., description="Reset-Scope: daily=Daily Loss Limit, consecutive=Consecutive Losses, all=Beides"
    )


class KillSwitchStatusResponse(BaseModel):
    """Response mit aktuellem Kill-Switch Status."""
    daily_limit_hit: bool
    daily_limit_date: Optional[str]
    consecutive_losses_global: int
    max_consecutive_losses: int
    max_consecutive_losses_learning: int
    killswitch_active: bool
    reason: Optional[str]


@router.post("/risk/reset_killswitch")
async def reset_killswitch(request: ResetKillSwitchRequest):
    """
    PROMPT 01: Manuelles Zurücksetzen des Kill-Switches.
    
    Erlaubt manuelles Zurücksetzen von:
    - daily_limit_hit (bruno:portfolio:daily_limit_hit)
    - consecutive_losses_global (bruno:portfolio:state)
    
    Sicherheits-Check: Das Datum muss dem aktuellen Tag entsprechen.
    """
    from app.core.redis_client import RedisClient
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    # Sicherheits-Check: Nur aktueller Tag erlaubt
    if request.date != today:
        raise HTTPException(
            status_code=400,
            detail=f"Sicherheits-Check: Reset nur für aktuellen Tag ({today}) erlaubt, "
                   f"nicht für {request.date}"
        )
    
    redis = RedisClient()
    reset_actions = []
    
    try:
        # 1. Daily Limit Reset
        if request.scope in ["daily", "all"]:
            await redis.set_cache(
                "bruno:portfolio:daily_limit_hit",
                {"hit": False, "date": today, "reset_at": datetime.now(timezone.utc).isoformat()},
                ttl=86400
            )
            reset_actions.append("daily_limit_hit: reset to False")
        
        # 2. Consecutive Losses Reset
        if request.scope in ["consecutive", "all"]:
            portfolio = await redis.get_cache("bruno:portfolio:state") or {}
            old_value = portfolio.get("consecutive_losses_global", 0)
            portfolio["consecutive_losses_global"] = 0
            portfolio["consecutive_losses_reset_at"] = datetime.now(timezone.utc).isoformat()
            await redis.set_cache("bruno:portfolio:state", portfolio)
            reset_actions.append(f"consecutive_losses_global: {old_value} -> 0")
        
        return {
            "success": True,
            "date": today,
            "scope": request.scope,
            "actions": reset_actions,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis Fehler: {str(e)}")


@router.get("/risk/killswitch_status")
async def get_killswitch_status():
    """
    PROMPT 01: Abfrage des aktuellen Kill-Switch Status.
    
    Gibt zurück:
    - Ob Daily Loss Limit erreicht wurde
    - Aktuelle Anzahl globaler Consecutive Losses
    - Ob Kill-Switch aktiv ist (blockiert Trades)
    """
    from app.core.redis_client import RedisClient
    from app.core.config_cache import ConfigCache
    import os
    
    # ConfigCache initialisieren falls nötig
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config.json"
    )
    ConfigCache.init(config_path)
    
    redis = RedisClient()
    today = datetime.now(timezone.utc).date().isoformat()
    
    try:
        # Daily Limit Status
        daily_limit = await redis.get_cache("bruno:portfolio:daily_limit_hit")
        daily_limit_hit = False
        daily_limit_date = None
        
        if daily_limit and daily_limit.get("hit") == True:
            daily_limit_date = daily_limit.get("date")
            if daily_limit_date == today:
                daily_limit_hit = True
        
        # Consecutive Losses Status
        portfolio = await redis.get_cache("bruno:portfolio:state") or {}
        consecutive_losses = portfolio.get("consecutive_losses_global", 0)
        
        # Max Limits aus Config
        max_consecutive = int(ConfigCache.get("MAX_CONSECUTIVE_LOSSES", 8))
        max_consecutive_learning = int(ConfigCache.get("MAX_CONSECUTIVE_LOSSES_LEARNING", 12))
        learning_enabled = ConfigCache.get("LEARNING_MODE_ENABLED", False)
        effective_max = max_consecutive_learning if learning_enabled else max_consecutive
        
        # Kill-Switch aktiv?
        killswitch_active = daily_limit_hit or consecutive_losses >= effective_max
        
        reason = None
        if daily_limit_hit:
            reason = "DAILY_LOSS_LIMIT_HIT"
        elif consecutive_losses >= effective_max:
            reason = "MAX_CONSECUTIVE_LOSSES_GLOBAL"
        
        return {
            "daily_limit_hit": daily_limit_hit,
            "daily_limit_date": daily_limit_date,
            "consecutive_losses_global": consecutive_losses,
            "max_consecutive_losses": max_consecutive,
            "max_consecutive_losses_learning": max_consecutive_learning,
            "learning_mode_active": learning_enabled,
            "effective_max_consecutive": effective_max,
            "killswitch_active": killswitch_active,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis Fehler: {str(e)}")
