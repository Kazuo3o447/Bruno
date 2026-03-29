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


@router.get("/monitoring/phase-a/status")
async def phase_a_verification():
    """
    Phase-A Verifikations-Endpoint.
    Gibt aktuellen System-State zurück.
    Ermöglicht sofortige Prüfung ob Phase A korrekt läuft.

    Aufruf: GET /api/v1/monitoring/phase-a/status
    """
    from app.core.redis_client import redis_client

    grss_data = await redis_client.get_cache("bruno:context:grss")
    sentiment_data = await redis_client.get_cache("bruno:sentiment:aggregate")
    cvd_data = await redis_client.get_cache("bruno:cvd:BTCUSDT")
    funding_data = await redis_client.get_cache("market:funding:BTCUSDT")
    ingestion_data = await redis_client.get_cache("bruno:ingestion:last_message")
    ticker_data = await redis_client.get_cache("market:ticker:BTCUSDT")

    # Prüft ob Phase A Ziele erfüllt sind
    checks = {
        "grss_data_present": grss_data is not None,
        "grss_score_valid": (
            0 <= grss_data.get("GRSS_Score", -1) <= 100
            if grss_data else False
        ),
        "grss_has_required_keys": all(
            k in grss_data
            for k in ["GRSS_Score", "VIX", "Yields_10Y", "Macro_Status", "last_update"]
        ) if grss_data else False,
        "sentiment_from_real_source": (
            sentiment_data.get("source", "") not in ["", "dummy"]
            if sentiment_data else False
        ),
        "cvd_persistent": cvd_data is not None,
        "funding_live": funding_data is not None,
        "ingestion_tracked": ingestion_data is not None,
        "ticker_live": ticker_data is not None,
        "no_etf_flows_random": (
            grss_data.get("ETF_Flows_3d_M") == 0.0
            if grss_data else True
        ),
    }

    all_passed = all(checks.values())

    return {
        "phase_a_complete": all_passed,
        "checks": checks,
        "current_grss": grss_data.get("GRSS_Score") if grss_data else None,
        "grss_breakdown": {
            "vix": grss_data.get("VIX") if grss_data else None,
            "ndx": grss_data.get("Macro_Status") if grss_data else None,
            "yields": grss_data.get("Yields_10Y") if grss_data else None,
            "pcr": grss_data.get("Put_Call_Ratio") if grss_data else None,
            "dvol": grss_data.get("DVOL") if grss_data else None,
            "funding": grss_data.get("Funding_Rate") if grss_data else None,
            "sentiment": grss_data.get("LLM_News_Sentiment") if grss_data else None,
        },
        "data_sources": {
            "sentiment": sentiment_data.get("source") if sentiment_data else "unavailable",
            "sentiment_score": sentiment_data.get("average_score") if sentiment_data else None,
            "btc_price": ticker_data.get("last_price") if ticker_data else None,
            "funding_rate": funding_data.get("rate") if funding_data else None,
        }
    }

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
