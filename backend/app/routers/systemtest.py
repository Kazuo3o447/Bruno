"""
Systemtest API Router

Bietet Endpunkte für:
- Systemweite API-Tests
- News-Feed Verbindungstests
- Flow-Status Tracking
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
import asyncio
from app.core.redis_client import redis_client
from app.agents.deps import AgentDependencies
from app.core.log_manager import log_manager
from app.core.config import settings
from app.core.scheduler import scheduler
from app.core.coinmarketcap_client import get_coinmarketcap_client
import json

router = APIRouter(prefix="/systemtest", tags=["systemtest"])

class TestResult(BaseModel):
    name: str
    category: str
    status: str  # "success", "error", "warning"
    response_time_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str

class SystemTestResponse(BaseModel):
    overall_status: str
    total_tests: int
    passed: int
    failed: int
    tests: List[TestResult]
    execution_time_ms: float
    timestamp: str

class FlowRun(BaseModel):
    id: str
    name: str
    status: str  # "success", "error", "running"
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class FlowsResponse(BaseModel):
    flows: List[FlowRun]
    last_updated: str

# Redis Keys
SYSTEMTEST_RESULTS_KEY = "bruno:systemtest:results"
FLOW_RUNS_KEY = "bruno:flows:runs"
LAST_SYSTEMTEST_KEY = "bruno:systemtest:last"

async def test_binance_api() -> TestResult:
    """Testet Binance API Verbindung"""
    start_time = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.binance.com/api/v3/ping")
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                return TestResult(
                    name="Binance API",
                    category="Exchange API",
                    status="success",
                    response_time_ms=response_time,
                    message="Verbindung erfolgreich",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            else:
                return TestResult(
                    name="Binance API",
                    category="Exchange API",
                    status="error",
                    response_time_ms=response_time,
                    message=f"Fehler: Status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="Binance API",
            category="Exchange API",
            status="error",
            response_time_ms=response_time,
            message=f"Verbindungsfehler: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

async def test_backend_api() -> TestResult:
    """Testet eigene Backend API"""
    start_time = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/health")
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                return TestResult(
                    name="Backend API",
                    category="Internal API",
                    status="success",
                    response_time_ms=response_time,
                    message="Backend läuft normal",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            else:
                return TestResult(
                    name="Backend API",
                    category="Internal API",
                    status="error",
                    response_time_ms=response_time,
                    message=f"Backend Fehler: Status {response.status_code}",
                    details={"status_code": response.status_code},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="Backend API",
            category="Internal API",
            status="error",
            response_time_ms=response_time,
            message=f"Backend nicht erreichbar: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

async def test_redis_connection() -> TestResult:
    """Testet Redis Verbindung"""
    start_time = datetime.now(timezone.utc)
    try:
        await redis_client.connect()
        await redis_client.redis.ping()
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return TestResult(
            name="Redis Cache",
            category="Database",
            status="success",
            response_time_ms=response_time,
            message="Redis Verbindung OK",
            details={},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="Redis Cache",
            category="Database",
            status="error",
            response_time_ms=response_time,
            message=f"Redis Fehler: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

async def test_news_feeds() -> TestResult:
    """Testet die CoinMarketCap-News- und Bitcoin-Bundle-APIs."""
    start_time = datetime.now(timezone.utc)
    try:
        api_key = settings.COINMARKETCAP_API_KEY
        if not api_key:
            return TestResult(
                name="CoinMarketCap News",
                category="News Feed",
                status="warning",
                response_time_ms=0,
                message="Kein API Key konfiguriert",
                details={"error": "COINMARKETCAP_API_KEY is missing"},
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        coinmarketcap = get_coinmarketcap_client(api_key)
        btc_bundle, global_metrics = await asyncio.gather(
            coinmarketcap.get_btc_bundle(convert="USD"),
            coinmarketcap.get_global_metrics(),
        )

        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        quote = btc_bundle.get("quote") if btc_bundle else None
        content_items = btc_bundle.get("content_items", []) if btc_bundle else []
        market_pairs = btc_bundle.get("market_pairs", []) if btc_bundle else []

        if quote and btc_bundle.get("bitcoin_filter"):
            return TestResult(
                name="CoinMarketCap News",
                category="News Feed",
                status="success",
                response_time_ms=response_time,
                message="CoinMarketCap Bitcoin-Bundle, Content und Global Metrics erreichbar",
                details={
                    "symbol": btc_bundle.get("symbol"),
                    "bitcoin_filter": btc_bundle.get("bitcoin_filter"),
                    "quote_keys": sorted(list(quote.keys()))[:10] if isinstance(quote, dict) else [],
                    "content_items": len(content_items),
                    "market_pairs": len(market_pairs),
                    "global_metric_keys": sorted(list(global_metrics.keys()))[:10] if isinstance(global_metrics, dict) else [],
                    "source": "CoinMarketCap",
                },
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        return TestResult(
            name="CoinMarketCap News",
            category="News Feed",
            status="warning",
            response_time_ms=response_time,
            message="CoinMarketCap lieferte nur Teilmengen der Free-Plan-Daten",
            details={
                "symbol": btc_bundle.get("symbol") if btc_bundle else None,
                "bitcoin_filter": btc_bundle.get("bitcoin_filter") if btc_bundle else None,
                "content_items": len(content_items),
                "market_pairs": len(market_pairs),
                "global_metrics": bool(global_metrics),
                "source": "CoinMarketCap",
            },
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="CoinMarketCap News",
            category="News Feed",
            status="error",
            response_time_ms=response_time,
            message=f"Verbindungsfehler: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

async def test_sentiment_feeds() -> TestResult:
    """Testet die Erreichbarkeit der Makro- und Krypto-News-Feeds."""
    from app.agents.context import ContextAgent
    from app.core.database import SessionLocal
    
    start_time = datetime.now(timezone.utc)
    try:
        deps = AgentDependencies(
            redis=redis_client,
            config=settings,
            db_session_factory=SessionLocal,
            log_manager=log_manager
        )
        agent = ContextAgent(deps)
        
        # Teste Erreichbarkeit von jeweils einem Feed pro Kategorie
        macro_test = await agent._fetch_rss(agent.macro_feeds[0])
        crypto_test = await agent._fetch_rss(agent.crypto_feeds[0])
        
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        status = "success" if macro_test and crypto_test else "warning"
        message = "Feeds erreichbar" if status == "success" else "Einige Feeds konnten nicht geladen werden"
        
        return TestResult(
            name="Sentiment Feeds (BERT)",
            category="News Feed",
            status=status,
            response_time_ms=response_time,
            message=message,
            details={
                "macro_sample": macro_test,
                "crypto_sample": crypto_test,
                "macro_url": agent.macro_feeds[0],
                "crypto_url": agent.crypto_feeds[0]
            },
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="Sentiment Feeds (BERT)",
            category="News Feed",
            status="error",
            response_time_ms=response_time,
            message=f"Fehler bei Feed-Abfrage: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

async def test_postgres_connection() -> TestResult:
    """Testet PostgreSQL Verbindung"""
    start_time = datetime.now(timezone.utc)
    try:
        # Einfacher Verbindungstest via SQLAlchemy
        from app.core.database import engine
        from sqlalchemy import text
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return TestResult(
            name="PostgreSQL Database",
            category="Database",
            status="success",
            response_time_ms=response_time,
            message="Datenbankverbindung OK",
            details={"connection": "established"},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return TestResult(
            name="PostgreSQL Database",
            category="Database",
            status="error",
            response_time_ms=response_time,
            message=f"Datenbankfehler: {str(e)}",
            details={"error": str(e)},
            timestamp=datetime.now(timezone.utc).isoformat()
        )

@router.get("/run", response_model=SystemTestResponse)
async def run_systemtest():
    """
    Führt einen kompletten Systemtest durch.
    Testet alle APIs, Datenbanken und externen Services.
    """
    start_time = datetime.now(timezone.utc)
    
    # Alle Tests parallel ausführen
    tests = await asyncio.gather(
        test_backend_api(),
        test_redis_connection(),
        test_postgres_connection(),
        test_binance_api(),
        test_news_feeds(),
        test_sentiment_feeds(),
        return_exceptions=True
    )
    
    # Ergebnisse verarbeiten
    test_results = []
    for test in tests:
        if isinstance(test, Exception):
            test_results.append(TestResult(
                name="Unbekannter Test",
                category="System",
                status="error",
                response_time_ms=0,
                message=f"Test fehlgeschlagen: {str(test)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))
        else:
            test_results.append(test)
    
    # Statistik berechnen
    total = len(test_results)
    passed = len([t for t in test_results if t.status == "success"])
    failed = len([t for t in test_results if t.status == "error"])
    
    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    # Gesamtstatus bestimmen
    if failed == 0:
        overall = "success"
    elif failed < total / 2:
        overall = "warning"
    else:
        overall = "error"
    
    response = SystemTestResponse(
        overall_status=overall,
        total_tests=total,
        passed=passed,
        failed=failed,
        tests=test_results,
        execution_time_ms=execution_time,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    # In Redis speichern
    await redis_client.redis.lpush(SYSTEMTEST_RESULTS_KEY, json.dumps(response.dict()))
    await redis_client.redis.ltrim(SYSTEMTEST_RESULTS_KEY, 0, 99)  # Letzte 100 behalten
    await redis_client.redis.set(LAST_SYSTEMTEST_KEY, json.dumps(response.dict()))
    
    return response

@router.get("/results", response_model=List[SystemTestResponse])
async def get_test_results(limit: int = 10):
    """Holt die letzten Systemtest-Ergebnisse"""
    try:
        results = await redis_client.redis.lrange(SYSTEMTEST_RESULTS_KEY, 0, limit - 1)
        return [json.loads(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Ergebnisse: {str(e)}")

@router.get("/last", response_model=Optional[SystemTestResponse])
async def get_last_test():
    """Holt das letzte Systemtest-Ergebnis"""
    try:
        result = await redis_client.redis.get(LAST_SYSTEMTEST_KEY)
        if result:
            return json.loads(result)
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.post("/flows/register")
async def register_flow_run(flow: FlowRun):
    """Registriert einen Flow-Run (für n8n Integration)"""
    try:
        await redis_client.redis.lpush(FLOW_RUNS_KEY, json.dumps(flow.dict()))
        await redis_client.redis.ltrim(FLOW_RUNS_KEY, 0, 199)  # Letzte 200 behalten
        return {"status": "success", "message": "Flow registriert"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/flows", response_model=FlowsResponse)
async def get_flow_runs(limit: int = 50):
    """Holt die letzten Flow-Runs"""
    try:
        flows = await redis_client.redis.lrange(FLOW_RUNS_KEY, 0, limit - 1)
        flow_list = [json.loads(f) for f in flows]
        
        return FlowsResponse(
            flows=flow_list,
            last_updated=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Flows: {str(e)}")

@router.get("/flows/stats")
async def get_flow_stats():
    """Holt Statistiken über Flow-Runs"""
    try:
        flows = await redis_client.redis.lrange(FLOW_RUNS_KEY, 0, -1)
        flow_list = [json.loads(f) for f in flows]
        
        total = len(flow_list)
        success = len([f for f in flow_list if f.get("status") == "success"])
        error = len([f for f in flow_list if f.get("status") == "error"])
        running = len([f for f in flow_list if f.get("status") == "running"])
        
        return {
            "total": total,
            "success": success,
            "error": error,
            "running": running,
            "success_rate": (success / total * 100) if total > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

# Scheduler Endpoints
@router.post("/scheduler/start")
async def start_scheduler():
    """Startet den automatischen Scheduler"""
    try:
        result = await scheduler.start()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stoppt den automatischen Scheduler"""
    try:
        result = await scheduler.stop()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.post("/scheduler/pause")
async def pause_scheduler():
    """Pausiert den automatischen Scheduler"""
    try:
        result = await scheduler.pause()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Holt aktuellen Scheduler-Status"""
    try:
        result = await scheduler.get_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.post("/scheduler/interval")
async def update_scheduler_interval(interval_minutes: int):
    """Aktualisiert das Scheduler-Intervall"""
    try:
        result = await scheduler.update_interval(interval_minutes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")
@router.get("/health/sources")
async def get_source_health():
    """Holt den detaillierten Health-Status aller externen Datenquellen inkl. Latenz."""
    try:
        data = await redis_client.get_cache("bruno:health:sources")
        if data:
            return data
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
