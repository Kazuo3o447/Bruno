"""
Export-Endpoint für Ruben → Claude Analyse.

GET /api/v1/export/snapshot gibt einen vollständigen, kompakten JSON-Snapshot
des aktuellen Bot-Zustands zurück — designed um direkt in ein Claude-Gespräch
eingefügt zu werden für Analyse.

Enthält: Agenten-Status, letzte 20 Decisions, GRSS-Breakdown, Veto-History,
         Datensource-Health, Latenz, Config, letzte offene/geschlossene Position.
"""
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.core.redis_client import redis_client
from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["export"])


@router.get("/export/snapshot")
async def get_export_snapshot():
    """
    Vollständiger Bot-Snapshot für externe Analyse.
    Format: kompaktes JSON, direkt in Claude-Chat einfügbar.
    """
    try:
        grss_data = await redis_client.get_cache("bruno:context:grss") or {}
        quant_data = await redis_client.get_cache("bruno:quant:micro") or {}
        veto_raw = await redis_client.redis.get("bruno:veto:state")
        veto_data = json.loads(veto_raw) if veto_raw else {}
        health_data = await redis_client.get_cache("bruno:health:sources") or {}

        # Decision Feed (letzte 20)
        decision_raw = await redis_client.redis.lrange("bruno:decisions:feed", 0, 19)
        decisions = [json.loads(d) for d in decision_raw]

        # Veto History (letzte 10)
        veto_hist_raw = await redis_client.redis.lrange("bruno:veto:history", 0, 9)
        veto_history = [json.loads(v) for v in veto_hist_raw]

        # LLM Cascade History
        cascade_history = await redis_client.get_cache("bruno:llm:decision_history") or []

        # Offene Position
        position = await redis_client.get_cache("bruno:position:BTCUSDT")

        # Config
        config = {}
        config_path = "/app/config.json"
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            pass

        # Decision-Statistik der letzten 20
        outcomes = [d.get("outcome", "") for d in decisions]
        stats = {
            "ofi_below_threshold": sum(1 for o in outcomes if o == "OFI_BELOW_THRESHOLD"),
            "cascade_hold": sum(1 for o in outcomes if "CASCADE" in o),
            "signals_generated": sum(1 for o in outcomes if "SIGNAL_" in o),
            "avg_ofi": round(
                sum(d.get("ofi", 0) for d in decisions) / len(decisions), 1
            ) if decisions else 0,
            "ofi_threshold": decisions[0].get("ofi_threshold") if decisions else None,
        }

        return {
            "snapshot_meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dry_run": settings.DRY_RUN,
                "bot_version": "Bruno v2.0",
                "analysis_hint": (
                    "Dieser Snapshot ist für die Analyse durch Claude bestimmt. "
                    "Zeigt den aktuellen Zustand des Bruno Trading Bots. "
                    "Bitte analysiere: Warum wurden keine Trades gesetzt? "
                    "Sind die Signale konsistent? Gibt es Datenlücken?"
                ),
            },
            "current_state": {
                "status": "ARMED" if not veto_data.get("Veto_Active") else "HALTED",
                "grss_score": grss_data.get("GRSS_Score"),
                "grss_velocity": grss_data.get("GRSS_Velocity_30min"),
                "veto_active": veto_data.get("Veto_Active"),
                "veto_reason": veto_data.get("Reason"),
                "open_position": position,
            },
            "market_signals": {
                "btc_price": quant_data.get("price"),
                "btc_change_24h_pct": grss_data.get("BTC_Change_24h_Pct"),
                "btc_change_1h_pct": grss_data.get("BTC_Change_1h_Pct"),
                "ofi_current": quant_data.get("OFI"),
                "ofi_threshold": config.get("OFI_Threshold", 500),
                "cvd": quant_data.get("CVD"),
                "funding_rate": grss_data.get("Funding_Rate"),
                "funding_divergence": grss_data.get("Funding_Divergence"),
                "put_call_ratio": grss_data.get("Put_Call_Ratio"),
                "dvol": grss_data.get("DVOL"),
                "oi_delta_pct": grss_data.get("OI_Delta_Pct"),
                "fear_greed": grss_data.get("Fear_Greed"),
                "vix": grss_data.get("VIX"),
                "ndx_status": grss_data.get("Macro_Status"),
                "yields_10y": grss_data.get("Yields_10Y"),
                "m2_yoy_pct": grss_data.get("M2_YoY_Pct"),
                "stablecoin_delta_bn": grss_data.get("Stablecoin_Delta_Bn"),
                "news_silence_seconds": grss_data.get("News_Silence_Seconds"),
                "llm_sentiment": grss_data.get("LLM_News_Sentiment"),
            },
            "decision_stats_last_20": stats,
            "last_20_decisions": decisions,
            "veto_history_last_10": veto_history,
            "cascade_history": cascade_history[-5:] if cascade_history else [],
            "data_source_health": health_data,
            "active_config": config,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
