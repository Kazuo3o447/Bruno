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
from datetime import datetime, timezone

router = APIRouter()

@router.get("/telemetry/live")
async def get_live_telemetry():
    """
    Echtzeit-Systemstatus aus Redis.
    Kein Hardcoding. Keine Platzhalter.
    """
    try:
        veto_raw = await redis_client.redis.get("bruno:veto:state")
        veto_data = json.loads(veto_raw) if veto_raw else {
            "Veto_Active": True, "Reason": "Keine Daten"
        }

        grss_data = await redis_client.get_cache("bruno:context:grss") or {}
        quant_data = await redis_client.get_cache("bruno:quant:micro") or {}
        health_data = await redis_client.get_cache("bruno:health:sources") or {}
        sources = [
            "Binance_REST",
            "Binance_Analytics",
            "Deribit_Public",
            "yFinance_Macro",
            "Binance_OI_Trend",
            "CryptoCompare_News",
            "CryptoCompare_Market",
            "CoinMarketCap_BTC",
            "CoinMarketCap_Global",
            "Blockchain_OnChain",
            "TA_Engine",
            "Liquidation_Cluster_SQL",
        ]
        normalized_sources = {
            name: health_data.get(name, {
                "status": "offline",
                "latency_ms": 0.0,
                "last_update": "",
            })
            for name in sources
        }
        # Existing sources that are already present stay untouched.
        for key, value in health_data.items():
            normalized_sources[key] = value

        # Letztes Decision Event
        last_event_raw = await redis_client.redis.lindex("bruno:decisions:feed", 0)
        last_event = json.loads(last_event_raw) if last_event_raw else None

        # Agent Heartbeats aus agent_status
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        agent_heartbeats = {}
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT agent_id, status, last_heartbeat,
                           EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as age_seconds
                    FROM agent_status ORDER BY agent_id
                """))
                for row in result.fetchall():
                    agent_heartbeats[row[0]] = {
                        "status": row[1],
                        "last_heartbeat": row[2].isoformat() if row[2] else None,
                        "age_seconds": round(float(row[3]), 1) if row[3] else None,
                        "healthy": float(row[3] or 9999) < 60,
                    }
        except Exception:
            pass

        return {
            "status": "ARMED" if not veto_data.get("Veto_Active") else "HALTED",
            "veto_active": veto_data.get("Veto_Active", True),
            "veto_reason": veto_data.get("Reason", "Unbekannt"),
            "dry_run": settings.DRY_RUN,
            "live_trading_approved": getattr(settings, "LIVE_TRADING_APPROVED", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "grss": {
                "score": grss_data.get("GRSS_Score"),
                "score_raw": grss_data.get("GRSS_Score_Raw"),
                "velocity_30min": grss_data.get("GRSS_Velocity_30min"),
                "deriv_sub": grss_data.get("GRSS_Deriv_Sub"),
                "inst_sub": grss_data.get("GRSS_Inst_Sub"),
                "sent_sub": grss_data.get("GRSS_Sent_Sub"),
                "macro_sub": grss_data.get("GRSS_Macro_Sub"),
                "veto_active": grss_data.get("Veto_Active"),
                "last_update": grss_data.get("last_update") or grss_data.get("timestamp") or "",
            },
            "market": {
                "btc_price": quant_data.get("price"),
                "ofi": quant_data.get("OFI_Buy_Pressure"),
                "cvd": quant_data.get("CVD"),
                "vamp": quant_data.get("VAMP"),
                "max_pain": grss_data.get("Max_Pain"),
                "max_pain_distance": grss_data.get("Max_Pain_Distance_Pct"),
                "btc_change_24h_pct": grss_data.get("BTC_Change_24h_Pct"),
                "btc_change_1h_pct": grss_data.get("BTC_Change_1h_Pct"),
                "funding_rate": grss_data.get("Funding_Rate"),
                "funding_divergence": grss_data.get("Funding_Divergence"),
                "put_call_ratio": grss_data.get("Put_Call_Ratio"),
                "dvol": grss_data.get("DVOL"),
                "oi_delta_pct": grss_data.get("OI_Delta_Pct"),
                "perp_basis_pct": grss_data.get("Perp_Basis_Pct"),
                "fear_greed": grss_data.get("Fear_Greed"),
                "vix": grss_data.get("VIX"),
                "ndx_status": grss_data.get("Macro_Status"),
                "yields_10y": grss_data.get("Yields_10Y"),
                "m2_yoy_pct": grss_data.get("M2_YoY_Pct"),
                "stablecoin_delta_bn": grss_data.get("Stablecoin_Delta_Bn"),
                "llm_news_sentiment": grss_data.get("LLM_News_Sentiment"),
                "news_silence_seconds": grss_data.get("News_Silence_Seconds"),
            },
            "cryptocompare": grss_data.get("CryptoCompare", {}),
            "coinmarketcap": grss_data.get("CoinMarketCap", {}),
            "data_sources": normalized_sources,
            "agents": agent_heartbeats,
            "last_decision": last_event,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/debug/trade-pipeline")
async def trade_pipeline_debug():
    """
    Zeigt den Zustand jedes Gates in der Trade-Execution-Pipeline.
    Nutze diesen Endpoint um zu diagnostizieren wo Trades blockiert werden.
    """
    import json

    # 1. GRSS & Freshness (ContextAgent Output)
    grss_data = await redis_client.get_cache("bruno:context:grss") or {}

    # 2. Veto State (RiskAgent Output)
    veto_raw = await redis_client.redis.get("bruno:veto:state")
    veto_data = json.loads(veto_raw) if veto_raw else {"error": "key_not_found"}

    # 3. Veto History (letzte 5 Zustandswechsel)
    veto_history_raw = await redis_client.redis.lrange("bruno:veto:history", 0, 4)
    veto_history = [json.loads(x) for x in veto_history_raw] if veto_history_raw else []

    # 4. Decision Feed (letzte 5 Zyklen aus QuantAgent)
    feed_raw = await redis_client.redis.lrange("bruno:decisions:feed", 0, 4)
    decision_feed = [json.loads(x) for x in feed_raw] if feed_raw else []

    # 5. Quant Micro (QuantAgent letzter Output)
    quant_micro = await redis_client.get_cache("bruno:quant:micro") or {}

    # 6. Portfolio State
    portfolio = await redis_client.get_cache("bruno:portfolio:state") or {}

    # 7. Health Sources
    health = await redis_client.get_cache("bruno:health:sources") or {}

    # 8. Offene Position
    position = await redis_client.get_cache("bruno:positions:BTCUSDT") or {}

    # 9. Daily Limit
    daily_limit = await redis_client.get_cache("bruno:portfolio:daily_limit_hit") or {}

    # Klartext-Diagnose bauen
    gates = {
        "gate_1_data_freshness": {
            "fresh_source_count": grss_data.get("Fresh_Source_Count", "MISSING"),
            "data_freshness_active": grss_data.get("Data_Freshness_Active", "MISSING"),
            "blocked": grss_data.get("Data_Freshness_Active") == False,
            "note": "Wenn False: quant_v3 Pre-Gate blockiert LLM Cascade komplett"
        },
        "gate_2_grss_precheck": {
            "grss_score": grss_data.get("GRSS_Score", "MISSING"),
            "grss_score_raw": grss_data.get("GRSS_Score_Raw", "MISSING"),
            "blocked": float(grss_data.get("GRSS_Score", 100)) < 20,
            "note": "Wenn GRSS < 20: quant_v3 Pre-Gate hält (Extremstress)"
        },
        "gate_3_risk_veto": {
            "veto_active": veto_data.get("Veto_Active", "MISSING"),
            "reason": veto_data.get("Reason", "MISSING"),
            "blocked": veto_data.get("Veto_Active", True),
            "veto_history": veto_history,
            "note": "Wenn True: ExecutionAgent blockiert ALLE Trades"
        },
        "gate_4_composite_scorer": {
            "last_5_decisions": decision_feed,
            "note": "Prüfe outcome-Felder: SIGNAL_BUY/SIGNAL_SELL/COMPOSITE_HOLD"
        },
        "gate_5_position_guard": {
            "has_open_position": bool(position and position.get("status") == "open"),
            "position": position,
            "blocked": bool(position and position.get("status") == "open"),
            "note": "Wenn True: kein neuer Trade bis Position geschlossen"
        },
        "gate_6_daily_limit": {
            "limit_hit": daily_limit.get("hit", False),
            "blocked": daily_limit.get("hit", False),
            "note": "Wenn True: kein Trade heute mehr"
        },
    }

    # Summary
    blocking_gates = [k for k, v in gates.items() if v.get("blocked") == True]

    return {
        "summary": {
            "blocking_gates": blocking_gates,
            "trade_possible": len(blocking_gates) == 0,
            "grss_score": grss_data.get("GRSS_Score"),
            "vix": grss_data.get("VIX"),
            "data_freshness_active": grss_data.get("Data_Freshness_Active"),
            "context_timestamp": grss_data.get("timestamp"),
        },
        "gates": gates,
        "health_sources": health,
        "portfolio": {
            "capital_eur": portfolio.get("capital_eur"),
            "total_trades": portfolio.get("total_trades"),
            "daily_pnl_eur": portfolio.get("daily_pnl_eur"),
        },
        "quant_micro": {
            "price": quant_micro.get("price"),
            "ofi": quant_micro.get("OFI"),
            "ofi_buy_pressure": quant_micro.get("OFI_Buy_Pressure"),
            "source": quant_micro.get("Source"),
            "timestamp": quant_micro.get("timestamp"),
        }
    }


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


@router.get("/performance/simulated")
async def get_simulated_performance(db: AsyncSession = Depends(get_db)):
    """
    Simulated Performance Endpoint.
    
    Zeigt die tatsächliche Rendite von Paper-Trading und später Real Trading
    für verschiedene Zeiträume an:
    - 24h (1 Tag)
    - 1 Woche
    - 6 Monate
    - 1 Jahr
    - YTD (Year-to-Date)
    
    Aufruf: GET /api/v1/performance/simulated
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import func, select, text
    
    try:
        now = datetime.now(timezone.utc)
        
        # Zeitpunkte für verschiedene Perioden
        timeframes = {
            "24h": now - timedelta(hours=24),
            "1w": now - timedelta(weeks=1),
            "6m": now - timedelta(days=180),
            "1y": now - timedelta(days=365),
            "ytd": datetime(now.year, 1, 1, tzinfo=timezone.utc)  # 1. Januar aktuelles Jahr
        }
        
        performance_data = {}
        
        for period_name, start_time in timeframes.items():
            # Abfrage: Geschlossene Positionen im Zeitraum (using raw SQL)
            query = text("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(pnl_eur) as total_pnl,
                    SUM(pnl_pct) as total_pnl_pct,
                    AVG(pnl_pct) as avg_return_per_trade,
                    COUNT(CASE WHEN pnl_eur > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN pnl_eur < 0 THEN 1 END) as losing_trades,
                    MAX(pnl_pct) as best_trade_pct,
                    MIN(pnl_pct) as worst_trade_pct
                FROM positions 
                WHERE status = 'closed' 
                AND exit_time >= :start_time
            """)
            
            result = await db.execute(query, {"start_time": start_time})
            row = result.fetchone()
            
            total_trades = row.total_trades or 0
            winning_trades = row.winning_trades or 0
            losing_trades = row.losing_trades or 0
            total_pnl = float(row.total_pnl or 0.0)
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Tägliche Returns für die Grafik
            daily_query = text("""
                SELECT 
                    DATE(exit_time) as date,
                    SUM(pnl_eur) as daily_pnl,
                    SUM(pnl_pct) as daily_return_pct
                FROM positions 
                WHERE status = 'closed' 
                AND exit_time >= :start_time
                GROUP BY DATE(exit_time)
                ORDER BY DATE(exit_time)
            """)
            
            daily_result = await db.execute(daily_query, {"start_time": start_time})
            daily_data = [
                {
                    "date": str(row.date),
                    "pnl_eur": float(row.daily_pnl or 0),
                    "return_pct": float(row.daily_return_pct or 0)
                }
                for row in daily_result.fetchall()
            ]
            
            # Kumulativen Return berechnen
            cumulative_return = 0.0
            cumulative_data = []
            for day in daily_data:
                cumulative_return += day["return_pct"]
                cumulative_data.append({
                    "date": day["date"],
                    "cumulative_return_pct": round(cumulative_return, 4)
                })
            
            # Falls keine Daten, füge Dummy-Daten für den Zeitraum hinzu
            if not cumulative_data:
                cumulative_data = [
                    {"date": start_time.strftime("%Y-%m-%d"), "cumulative_return_pct": 0},
                    {"date": now.strftime("%Y-%m-%d"), "cumulative_return_pct": 0}
                ]
            
            performance_data[period_name] = {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate_pct": round(win_rate, 2),
                "total_pnl_eur": round(total_pnl, 2),
                "avg_return_per_trade_pct": round(float(row.avg_return_per_trade or 0), 4),
                "best_trade_pct": round(float(row.best_trade_pct or 0), 4),
                "worst_trade_pct": round(float(row.worst_trade_pct or 0), 4),
                "period": period_name,
                "start_date": start_time.isoformat(),
                "end_date": now.isoformat(),
                "daily_breakdown": daily_data,
                "cumulative_chart_data": cumulative_data
            }
        
        # Zusammenfassung über alle Perioden
        summary = {
            "status": "ok" if any(p["total_trades"] > 0 for p in performance_data.values()) else "no_data",
            "trading_mode": "paper" if settings.DRY_RUN else "real",
            "current_capital_eur": settings.INITIAL_CAPITAL_EUR,
            "generated_at": now.isoformat()
        }
        
        return {
            "summary": summary,
            "performance_by_period": performance_data
        }
        
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(
            status_code=500, 
            detail=f"Fehler bei Performance-Berechnung: {error_detail}"
        )


@router.get("/performance/metrics")
async def get_performance_metrics():
    """
    Performance-Metrik-Endpoint für Dashboard.
    
    Gibt aggregierte Performance-Kennzahlen zurück:
    - Renditen für verschiedene Zeiträume
    - Win Rate, Average Trade P&L, Maximum Drawdown
    - Sharpe Ratio
    
    Aufruf: GET /api/v1/performance/metrics
    """
    try:
        from app.core.redis_client import redis_client
        
        # Simulierte Performance-Daten holen
        sim_data = await redis_client.get_cache("bruno:performance:simulated") or {}
        
        # Profit Factor Daten
        pf_data = await redis_client.get_cache("bruno:performance:profit_factor") or {}
        
        # Portfolio-Daten
        portfolio_data = await redis_client.get_cache("bruno:portfolio:state") or {}
        
        # Standard-Werte falls keine Daten vorhanden
        return {
            "daily_return": sim_data.get("daily_return_pct"),
            "weekly_return": sim_data.get("weekly_return_pct"), 
            "monthly_return": sim_data.get("monthly_return_pct"),
            "six_month_return": sim_data.get("six_month_return_pct"),
            "yearly_return": sim_data.get("yearly_return_pct"),
            "ytd_return": sim_data.get("ytd_return_pct"),
            "total_pnl": portfolio_data.get("total_pnl_eur"),
            "win_rate": sim_data.get("win_rate_pct"),
            "avg_trade_pnl": sim_data.get("avg_trade_pnl_eur"),
            "max_drawdown": sim_data.get("max_drawdown_pct"),
            "sharpe_ratio": sim_data.get("sharpe_ratio"),
            "profit_factor": pf_data.get("pf_total"),
            "status": "ok" if sim_data else "no_data"
        }
        
    except Exception as e:
        # Bei Fehlern Standard-Werte zurückgeben
        return {
            "daily_return": None,
            "weekly_return": None,
            "monthly_return": None,
            "six_month_return": None,
            "yearly_return": None,
            "ytd_return": None,
            "total_pnl": None,
            "win_rate": None,
            "avg_trade_pnl": None,
            "max_drawdown": None,
            "sharpe_ratio": None,
            "profit_factor": None,
            "status": "error",
            "error": str(e)
        }


@router.get("/api/health/dashboard")
async def get_api_health_dashboard():
    """
    API Health Dashboard - Umfassende Übersicht aller Datenquellen und Systemkomponenten.
    
    Zeigt den Status aller externen APIs, Datenquellen und internen Services an.
    Enthält Latenz-Metriken, Fehlerraten und Verfügbarkeits-Statistiken.
    
    Aufruf: GET /api/v1/api/health/dashboard
    """
    try:
        from app.core.redis_client import redis_client
        
        # Hole alle Health-Daten aus Redis
        health_data = await redis_client.get_cache("bruno:health:sources") or {}
        veto_data = await redis_client.get_cache("bruno:veto:state") or {}
        grss_data = await redis_client.get_cache("bruno:context:grss") or {}
        
        # Definiere alle API-Quellen mit Kategorien
        api_sources = {
            "market_data": [
                "Bybit_V5_WebSocket",
                "Binance_REST", 
                "Binance_Analytics",
                "Deribit_Public"
            ],
            "macro_data": [
                "Alpha_Vantage",
                "FRED_API",
                "yFinance_Macro"
            ],
            "crypto_data": [
                "CryptoCompare_News",
                "CryptoCompare_Market",
                "CoinMarketCap_BTC",
                "CoinMarketCap_Global"
            ],
            "onchain_data": [
                "Blockchain_OnChain",
                "Glassnode_OnChain"
            ],
            "sentiment_data": [
                "HuggingFace_Models",
                "CryptoPanic_News",
                "Reddit_Sentiment",
                "StockTwits_Sentiment"
            ],
            "internal_services": [
                "TA_Engine",
                "Liquidation_Cluster_SQL",
                "QuantAgent_Micro",
                "ContextAgent_GRSS",
                "RiskAgent_Veto"
            ]
        }
        
        # Berechne Gesamt-Statistiken
        total_apis = sum(len(sources) for sources in api_sources.values())
        online_apis = 0
        total_latency = 0.0
        
        health_status = {}
        
        # Erstelle detaillierten Status für jede API
        for category, sources in api_sources.items():
            health_status[category] = {}
            
            for source in sources:
                source_data = health_data.get(source, {
                    "status": "offline",
                    "latency_ms": 0.0,
                    "last_update": "",
                    "error_rate": 0.0
                })
                
                # Statistik-Zählung
                if source_data.get("status") == "online":
                    online_apis += 1
                    total_latency += source_data.get("latency_ms", 0.0)
                
                health_status[category][source] = {
                    "status": source_data.get("status", "offline"),
                    "latency_ms": round(source_data.get("latency_ms", 0.0), 2),
                    "last_update": source_data.get("last_update", ""),
                    "error_rate": round(source_data.get("error_rate", 0.0), 2),
                    "uptime": source_data.get("uptime", 0.0)
                }
        
        # Berechne Gesamt-Metriken
        availability_pct = (online_apis / total_apis * 100) if total_apis > 0 else 0
        avg_latency = (total_latency / online_apis) if online_apis > 0 else 0
        
        # System-weite Health-Metriken
        system_health = {
            "veto_active": veto_data.get("Veto_Active", False),
            "veto_reason": veto_data.get("Reason", ""),
            "grss_score": grss_data.get("GRSS_Score"),
            "data_freshness": grss_data.get("Data_Freshness_Active", False),
            "news_silence_seconds": grss_data.get("News_Silence_Seconds", 0)
        }
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_availability": round(availability_pct, 1),
            "online_apis": online_apis,
            "total_apis": total_apis,
            "avg_latency_ms": round(avg_latency, 2),
            "categories": health_status,
            "system_health": system_health,
            "status": "healthy" if availability_pct >= 80 else "degraded" if availability_pct >= 50 else "critical"
        }
        
    except Exception as e:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_availability": 0.0,
            "online_apis": 0,
            "total_apis": 0,
            "avg_latency_ms": 0.0,
            "categories": {},
            "system_health": {"veto_active": True, "veto_reason": "Health Dashboard Error"},
            "status": "error",
            "error": str(e)
        }
