from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import backup, ws, agents, logs, systemtest, agents_status, trades, monitoring, positions, market, sentiment_test, liquidations, decisions, config_api, export, backtest_api, debrief_api
from app.core.redis_client import redis_client
from app.core.database import init_db, close_db
from app.core.log_manager import log_manager
from app.core.scheduler import scheduler
from app.core.coinalyze_scheduler import coinalyze_scheduler
from app.core.config_cache import ConfigCache
import logging
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bruno Trading Bot API",
    description="Asynchronous Multi-Agent Bitcoin Trading Bot",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backup.router, prefix="/api/v1", tags=["backup"])
app.include_router(ws.router, tags=["WebSockets"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
app.include_router(systemtest.router, prefix="/api/v1", tags=["systemtest"])
app.include_router(sentiment_test.router, prefix="/api/v1", tags=["systemtest"])
app.include_router(agents_status.router, prefix="/api/v1", tags=["agents_status"])
app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(positions.router, prefix="/api/v1", tags=["positions"])
app.include_router(market.router, prefix="/api/v1/market", tags=["market"])
app.include_router(liquidations.router, prefix="/api/v1/liquidations", tags=["liquidations"])
app.include_router(decisions.router, prefix="/api/v1", tags=["decisions"])
app.include_router(config_api.router, prefix="/api/v1", tags=["config"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(backtest_api.router, prefix="/api/v1", tags=["backtest"])
app.include_router(debrief_api.router, prefix="/api/v1", tags=["debriefs"])

@app.on_event("startup")
async def startup_event():
    """Initialisiert alle Services beim Start."""
    try:
        # ConfigCache initialisieren
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        ConfigCache.init(config_path)
        logger.info("ConfigCache initialisiert")
        
        await init_db()
        logger.info("Datenbank initialisiert")
        
        await redis_client.connect()
        logger.info("Redis verbunden")
        
        await log_manager.initialize()
        logger.info("Log Manager initialisiert")
        
        await scheduler.initialize()
        logger.info("Scheduler initialisiert")
        
        await coinalyze_scheduler.initialize()
        logger.info("Coinalyze Scheduler initialisiert")
        
        logger.info("Bruno API Services gestartet")
        
    except Exception as e:
        logger.error(f"Startup Fehler: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Räumt alle Resources beim Herunterfahren."""
    try:
        await coinalyze_scheduler.stop()
        logger.info("Coinalyze Scheduler gestoppt")
        
        await redis_client.disconnect()
        logger.info("Redis Verbindung geschlossen")
        
        await close_db()
        logger.info("Datenbank Verbindungen geschlossen")
        
        logger.info("Bruno API Services heruntergefahren")
        
    except Exception as e:
        logger.error(f"Shutdown Fehler: {e}")

@app.get("/health")
async def health_check():
    """Health Check mit echtem Service-Status für alle Komponenten."""
    
    # 1. Binance Check
    binance_status = "disconnected"
    try:
        from app.core.binance_client import binance_client
        if await binance_client.health_check():
            binance_status = "connected"
    except Exception as e:
        logger.warning(f"Binance Health Check fehlgeschlagen: {e}")
    
    # 2. Redis Check
    redis_status = "disconnected"
    try:
        if await redis_client.health_check():
            redis_status = "connected"
    except Exception as e:
        logger.warning(f"Redis Health Check fehlgeschlagen: {e}")
    
    # 3. DB Check
    db_status = "disconnected"
    try:
        from app.core.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning(f"DB Health Check fehlgeschlagen: {e}")

    overall = "healthy" if all([
        redis_status == "connected",
        db_status == "connected",
        binance_status == "connected",
    ]) else "degraded"

    return {
        "status": overall,
        "version": "0.1.0",
        "binance": binance_status,
        "redis": redis_status,
        "database": db_status,
    }

@app.get("/")
async def root():
    return {"message": "Bruno Trading Bot API", "docs": "/docs"}
