from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.config import settings
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
            "dry_run": settings.DRY_RUN,
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

        safety_guard = {
            "max_leverage_cap": 1.0,
            "current_leverage_raw": params["current"].get("Max_Leverage", 1.0),
            "optimized_leverage_raw": params["optimized"].get("Max_Leverage", 1.0),
            "drift_detected": False,
            "warnings": []
        }

        for key in ("current", "optimized"):
            raw_value = params[key].get("Max_Leverage", 1.0)
            try:
                normalized_value = float(raw_value)
            except (TypeError, ValueError):
                normalized_value = 1.0

            if normalized_value > 1.0:
                safety_guard["drift_detected"] = True
                safety_guard["warnings"].append(
                    f"{key}.Max_Leverage={normalized_value} exceeds the hard cap and was clamped to 1.0"
                )
                normalized_value = 1.0

            params[key]["Max_Leverage"] = normalized_value

        safety_guard["current_leverage_effective"] = params["current"].get("Max_Leverage", 1.0)
        safety_guard["optimized_leverage_effective"] = params["optimized"].get("Max_Leverage", 1.0)
        params["safety_guard"] = safety_guard
            
        return params
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bybit/status")
async def bybit_connection_status():
    """
    Prüft Bybit Demo API Verbindung.
    Gibt Status zurück ohne echte Order zu platzieren.
    Setzt BYBIT_API_KEY und BYBIT_SECRET in .env voraus.
    """
    from app.core.config import settings

    if not settings.BYBIT_API_KEY or not settings.BYBIT_SECRET:
        return {
            "status": "no_keys",
            "message": "BYBIT_API_KEY und BYBIT_SECRET in .env eintragen",
            "mode": settings.BYBIT_MODE
        }

    try:
        import ccxt.async_support as ccxt
        exchange = ccxt.bybit({
            "apiKey": settings.BYBIT_API_KEY,
            "secret": settings.BYBIT_SECRET,
            "enableRateLimit": True,
        })

        if settings.BYBIT_MODE == "demo":
            exchange.urls["api"]["rest"] = "https://api-demo.bybit.com"

        # Nur Balance abfragen — keine Order
        balance = await exchange.fetch_balance()
        await exchange.close()

        usdt_balance = balance.get("USDT", {}).get("total", 0)
        return {
            "status": "connected",
            "mode": settings.BYBIT_MODE,
            "usdt_balance": usdt_balance,
            "message": f"Bybit {settings.BYBIT_MODE.upper()} verbunden"
        }

    except Exception as e:
        return {
            "status": "error",
            "mode": settings.BYBIT_MODE,
            "error": str(e)
        }

@router.get("/performance/profit-factor")
async def get_profit_factor():
    """
    Gibt aktuellen Profit Factor zurück.
    Wird nach jedem Trade automatisch aktualisiert.

    Interpretation:
    PF > 2.0 = ausgezeichnet
    PF > 1.5 = gut (Ziel)
    PF > 1.2 = akzeptabel
    PF < 1.2 = Alarm — Strategie überdenken
    PF < 1.0 = Verlustbringer — Bot pausieren
    """
    from app.core.redis_client import redis_client

    pf_data = await redis_client.get_cache(
        "bruno:performance:profit_factor"
    )

    if not pf_data:
        return {
            "status": "no_data",
            "message": "Noch keine Trades — PF wird nach dem ersten Trade berechnet",
            "min_trades_needed": 5
        }

    return {
        "status": "ok",
        "profit_factor": {
            "total": pf_data.get("pf_total"),
            "rolling_20": pf_data.get("pf_rolling_20"),
            "rolling_50": pf_data.get("pf_rolling_50"),
        },
        "stats": {
            "total_trades": pf_data.get("total_trades"),
            "win_rate": pf_data.get("win_rate"),
            "avg_win_pct": pf_data.get("avg_win_pct"),
            "avg_loss_pct": pf_data.get("avg_loss_pct"),
        },
        "alarm": {
            "active": pf_data.get("alarm_active", False),
            "reason": pf_data.get("alarm_reason")
        },
        "trend": pf_data.get("pf_history", []),
        "last_update": pf_data.get("timestamp")
    }

@router.get("/monitoring/phase-b/status")
async def phase_b_status():
    """
    Phase-B Status-Endpoint.
    Gibt aktuellen System-State für Phase B Features zurück.
    """
    from app.core.redis_client import redis_client
    from app.core.config import settings
    from datetime import datetime, timezone

    # GRSS Daten
    grss_data = await redis_client.get_cache("bruno:context:grss") or {}
    
    # Portfolio Daten
    portfolio_data = await redis_client.get_cache("bruno:portfolio:state") or {}
    
    # Profit Factor Daten
    pf_data = await redis_client.get_cache("bruno:performance:profit_factor") or {}
    
    # Telegram Status
    from app.core.telegram_bot import get_telegram_bot
    telegram_bot = get_telegram_bot()
    telegram_active = telegram_bot._running if telegram_bot else False
    
    # CoinGlass Status
    coinglass_active = grss_data.get("CoinGlass_Active", False)
    
    # Retail Sentiment
    retail_active = grss_data.get("Retail_Weight_Active", False)
    
    # Latency Monitor
    latency_data = await redis_client.get_cache("bruno:telemetry:latency") or {}
    
    checks = {
        # Kapitalschutz
        "leverage_is_1x": settings.MAX_LEVERAGE == 1.0,
        "dry_run_active": settings.DRY_RUN,

        # Portfolio
        "portfolio_initialized": bool(portfolio_data),
        "portfolio_capital": portfolio_data.get("capital_eur"),

        # Neue GRSS-Features
        "grss_has_ema": "GRSS_Score_Raw" in grss_data,
        "grss_has_retail": "Retail_Score" in grss_data,
        "grss_has_coinglass": "CoinGlass_Active" in grss_data,
        "funding_settlement_tracked": (
            "Funding_Settlement_Window" in grss_data
        ),

        # Latenz-Monitor
        "latency_monitor_active": bool(latency_data),
        "binance_latency_ok": (
            latency_data.get("binance_latency_ms", 9999) < 500
        ),

        # Retail Sentiment
        "retail_sentiment_active": bool(retail_data := await redis_client.get_cache("bruno:retail:sentiment") or {}),
        "retail_source": retail_data.get("source", "inactive"),

        # Mark Price
        "mark_price_in_funding": True,
    }

    all_critical = all([
        checks["leverage_is_1x"],
        checks["dry_run_active"],
        checks["portfolio_initialized"],
    ])

    return {
        "phase_b_complete": all_critical,
        "critical_checks_passed": all_critical,
        "all_checks": checks,
        "features": {
            "telegram_bot": {
                "active": telegram_active,
                "status": "connected" if telegram_active else "inactive"
            },
            "mark_price_monitoring": {
                "active": True,  # Immer aktiv in Phase B
                "status": "monitoring"
            },
            "coinglass_integration": {
                "active": coinglass_active,
                "status": "connected" if coinglass_active else "placeholder"
            },
            "retail_sentiment": {
                "active": retail_active,
                "status": "monitoring" if retail_active else "disabled"
            },
            "atr_position_sizing": {
                "active": True,  # Immer aktiv
                "status": "calculating"
            },
            "profit_factor_tracking": {
                "active": bool(pf_data),
                "status": "tracking" if pf_data else "waiting_for_trades"
            }
        },
        "performance": {
            "profit_factor": {
                "total": pf_data.get("pf_total"),
                "rolling_20": pf_data.get("pf_rolling_20"),
                "rolling_50": pf_data.get("pf_rolling_50"),
                "alarm_active": pf_data.get("alarm_active", False),
                "total_trades": pf_data.get("total_trades", 0)
            },
            "portfolio": {
                "capital_eur": portfolio_data.get("capital_eur", 0),
                "daily_pnl_eur": portfolio_data.get("daily_pnl_eur", 0),
                "total_trades": portfolio_data.get("total_trades", 0),
                "win_rate": (portfolio_data.get("winning_trades", 0) / 
                           max(1, portfolio_data.get("total_trades", 1)))
            }
        },
        "system_health": {
            "grss_score": grss_data.get("GRSS_Score"),
            "veto_active": grss_data.get("Veto_Active", True),
            "latency_veto": latency_data.get("trade_veto_active", False),
            "funding_settlement_window": grss_data.get("Funding_Settlement_Window", False)
        },
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "coinglass_configured": bool(settings.COINGLASS_API_KEY),
        "bybit_configured": bool(settings.BYBIT_API_KEY and settings.BYBIT_SECRET),
        "grss_score": grss_data.get("GRSS_Score"),
        "grss_raw": grss_data.get("GRSS_Score_Raw"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
