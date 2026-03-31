from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, backup, ws, agents, logs, systemtest, agents_status, trades, monitoring, llm_cascade, positions, market, sentiment_test, liquidations, decisions, config_api, export
from app.core.redis_client import redis_client
from app.core.llm_client import ollama_client
from app.core.database import init_db, close_db
from app.core.log_manager import log_manager
from app.core.scheduler import scheduler
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

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(backup.router, prefix="/api/v1", tags=["backup"])
app.include_router(ws.router, tags=["WebSockets"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
app.include_router(systemtest.router, prefix="/api/v1", tags=["systemtest"])
app.include_router(sentiment_test.router, prefix="/api/v1", tags=["systemtest"])
app.include_router(agents_status.router, prefix="/api/v1", tags=["agents_status"])
app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(llm_cascade.router, prefix="/api/v1", tags=["llm-cascade"])
app.include_router(positions.router, prefix="/api/v1", tags=["positions"])
app.include_router(market.router, prefix="/api/v1/market", tags=["market"])
app.include_router(liquidations.router, prefix="/api/v1/liquidations", tags=["liquidations"])
app.include_router(decisions.router, tags=["decisions"])
app.include_router(config_api.router, prefix="/api/v1", tags=["config"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])

@app.on_event("startup")
async def startup_event():
    """Initialisiert alle Services beim Start."""
    try:
        await init_db()
        logger.info("Datenbank initialisiert")
        
        await redis_client.connect()
        logger.info("Redis verbunden")
        
        await log_manager.initialize()
        logger.info("Log Manager initialisiert")
        
        await scheduler.initialize()
        logger.info("Scheduler initialisiert")
        
        ollama_healthy = await ollama_client.health_check()
        logger.info(f"Ollama Status: {'OK' if ollama_healthy else 'FEHLER (Fallback in Agents)'}")
        
        logger.info("Bruno API Services gestartet")
        
    except Exception as e:
        logger.error(f"Startup Fehler: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Räumt alle Resources beim Herunterfahren."""
    try:
        await ollama_client.close()
        logger.info("Ollama Client geschlossen")
        
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
    
    # 1. Ollama Check
    ollama_status = "disconnected"
    ollama_models = []
    try:
        ollama_healthy = await ollama_client.health_check()
        if ollama_healthy:
            ollama_status = "connected"
            models_data = await ollama_client.list_models()
            if models_data:
                ollama_models = [m.get("name", "") for m in models_data.get("models", [])]
    except Exception as e:
        logger.warning(f"Ollama Health Check fehlgeschlagen: {e}")
    
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
        ollama_status == "connected",
        redis_status == "connected",
        db_status == "connected"
    ]) else "degraded"

    return {
        "status": overall,
        "version": "0.1.0",
        "ollama": ollama_status,
        "ollama_models": ollama_models,
        "redis": redis_status,
        "database": db_status,
    }

@app.get("/")
async def root():
    return {"message": "Bruno Trading Bot API", "docs": "/docs"}
