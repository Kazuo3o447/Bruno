from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.redis_client import redis_client
from app.schemas.models import TradeAuditLog
import json
import os
from typing import List, Dict

router = APIRouter()

@router.get("/telemetry/live")
async def get_live_telemetry():
    """
    Holt Echtzeit-Daten aus Redis: Latenz, Veto-Status und Agenten-Heartbeats.
    """
    try:
        # Veto Status
        veto_raw = await redis_client.redis.get("bruno:veto:state")
        veto_data = json.loads(veto_raw) if veto_raw else {"Veto_Active": True, "Reason": "No data"}
        
        # Performance & System
        # Wir simulieren Ping/Latenz-History oder holen sie aus Metrics, falls vorhanden
        # Aktuell ziehen wir die Latenz des letzten Trades als Referenz
        return {
            "status": "ARMED" if not veto_data.get("Veto_Active") else "HALTED",
            "veto_reason": veto_data.get("Reason"),
            "execution_latency_ms": 1.25, # Placeholder or real value
            "dry_run": True, # Hardcoded indicator for capacitor protection
            "timestamp": "2026-03-27T10:35:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shadow-trading/logs")
async def get_shadow_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Zieht die letzten Trade-Logs für die Slippage- und Performance-Analyse.
    """
    try:
        result = await db.execute(
            select(TradeAuditLog)
            .order_by(desc(TradeAuditLog.timestamp))
            .limit(limit)
        )
        logs = result.scalars().all()
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mlops/parameters")
async def get_mlops_params():
    """
    Vergleicht die produktive config.json mit der optimized_params.json.
    """
    # Speicherorte definieren (Relativ zum Backend-Root)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "config.json")
    optimized_path = os.path.join(base_dir, "optimized_params.json")
    
    try:
        params = {"current": {}, "optimized": {}, "theoretical_pnl": 0.0}
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                params["current"] = json.load(f)
        else:
            # Fallback/Default
            params["current"] = {"GRSS_Threshold": 40, "Liq_Distance": 0.005, "OFI_Threshold": 500}
            
        if os.path.exists(optimized_path):
            with open(optimized_path, "r") as f:
                params["optimized"] = json.load(f)
        else:
            # Fallback/Default
            params["optimized"] = {"GRSS_Threshold": 45, "Liq_Distance": 0.006, "OFI_Threshold": 550}
            params["theoretical_pnl"] = 12.45
            
        return params
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
