from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, backup, ws
from app.core.redis_client import redis_client
from app.core.llm_client import ollama_client
from app.core.database import init_db, close_db
import logging

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


@app.on_event("startup")
async def startup_event():
    """Initialisiert alle Services beim Start."""
    try:
        # Datenbank initialisieren
        await init_db()
        logger.info("Datenbank initialisiert")
        
        # Redis Verbindung herstellen
        await redis_client.connect()
        logger.info("Redis verbunden")
        
        # Ollama Verbindung prüfen
        ollama_healthy = await ollama_client.health_check()
        logger.info(f"Ollama Status: {'OK' if ollama_healthy else 'FEHLER'}")
        
        logger.info("Alle Services gestartet")
        
    except Exception as e:
        logger.error(f"Startup Fehler: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Räumt alle Resources beim Shutdown."""
    try:
        # Ollama Client schließen
        await ollama_client.close()
        logger.info("Ollama Client geschlossen")
        
        # Redis Verbindung schließen
        await redis_client.disconnect()
        logger.info("Redis Verbindung geschlossen")
        
        # Datenbank Verbindungen schließen
        await close_db()
        logger.info("Datenbank Verbindungen geschlossen")
        
        logger.info("Alle Services heruntergefahren")
        
    except Exception as e:
        logger.error(f"Shutdown Fehler: {e}")


@app.get("/health")
async def health_check():
    """Health Check mit Service-Status."""
    redis_healthy = await redis_client.health_check()
    ollama_healthy = await ollama_client.health_check()
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "redis": "ok" if redis_healthy else "error",
            "ollama": "ok" if ollama_healthy else "error"
        }
    }


@app.get("/")
async def root():
    return {"message": "Bruno Trading Bot API", "docs": "/docs"}
