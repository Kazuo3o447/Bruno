"""
Agenten Status API Router

Bietet Endpunkte für:
- Agenten Status-Überwachung
- Health-Checks
- Agenten-Beschreibungen
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
import logging
from app.core.redis_client import redis_client
from app.agents.quant import QuantAgent
from app.core.log_manager import log_manager

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

class AgentStatus(BaseModel):
    id: str
    name: str
    type: str
    status: str  # "running", "stopped", "error", "idle"
    last_activity: str
    uptime_seconds: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    tasks_processed: int = 0
    errors: int = 0
    last_error: Optional[str] = None
    description: str
    purpose: str
    logic: str

class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    purpose: str
    logic: str
    configuration: Dict[str, Any]
    dependencies: List[str]

class AgentsResponse(BaseModel):
    agents: List[AgentStatus]
    overall_status: str
    last_check: str
    total_agents: int
    running_agents: int
    error_agents: int

# Redis Keys
AGENT_STATUS_KEY = "bruno:agents:status"
AGENT_INFO_KEY = "bruno:agents:info"
LAST_AGENT_CHECK_KEY = "bruno:agents:last_check"

# Agenten-Definitionen
AGENT_DEFINITIONS = {
    "ingestion": {
        "name": "Ingestion Agent",
        "type": "data",
        "description": "Live-Marktdaten Sammler via WebSocket",
        "purpose": "BTC/USDT Ticks von Binance WebSocket empfangen",
        "logic": "Verbindet sich zu Binance Futures WebSocket, empfängt Trades und pusht sie in Redis Stream. Verwendet Exponential Backoff bei Verbindungsproblemen.",
        "configuration": {
            "websocket_url": "wss://fstream.binance.com/ws/btcusdt@aggTrade",
            "reconnect_backoff": "1-60s",
            "stream_channel": "market:ticks:BTC/USDT"
        },
        "dependencies": ["redis", "binance_ws"]
    },
    "quant": {
        "name": "Quant Agent",
        "type": "analysis",
        "description": "KI-gestützter Trading-Analyse-Agent",
        "purpose": "Marktanalyse und Trading-Signale generieren",
        "logic": "Analysiert Marktdaten, technische Indikatoren und News-Ereignisse. Verwendet Machine Learning Modelle zur Vorhersage von Preisbewegungen und generiert Kauf/Verkauf-Signale basierend auf konfigurierbaren Strategien.",
        "configuration": {
            "analysis_interval": 60,
            "risk_threshold": 0.02,
            "max_positions": 5,
            "strategies": ["trend_following", "mean_reversion", "momentum"]
        },
        "dependencies": ["redis", "database", "binance_api", "news_api"]
    },
    "sentiment": {
        "name": "Sentiment Agent",
        "type": "analysis",
        "description": "News-Sentiment Analyse mit LLM",
        "purpose": "Marktstimmung aus Nachrichten analysieren",
        "logic": "Verarbeitet Krypto-Nachrichten, Social Media Posts und andere Sentiment-Quellen. Nutzt Ollama LLM zur Text-Analyse und generiert Bullish/Bearish Signale basierend auf Marktstimmung.",
        "configuration": {
            "analysis_interval": 300,
            "llm_model": "qwen2.5",
            "sentiment_threshold": 0.2,
            "news_sources": ["cryptopanic", "twitter", "reddit"]
        },
        "dependencies": ["redis", "ollama", "news_apis"]
    },
    "risk": {
        "name": "Risk Agent",
        "type": "risk",
        "description": "Risiko-Management und Konfluenz-Check",
        "purpose": "Signale validieren und Risiken managen",
        "logic": "Überwacht alle Signale von Quant und Sentiment Agenten. Führt Konfluenz-Checks durch, validiert Risikoparameter und gibt nur bei starker Übereinstimmung Freigabe für Execution.",
        "configuration": {
            "confluence_threshold": 0.7,
            "max_risk_per_trade": 0.02,
            "max_daily_loss": 0.05,
            "position_sizing": "dynamic"
        },
        "dependencies": ["redis", "database"]
    },
    "execution": {
        "name": "Execution Agent",
        "type": "execution",
        "description": "Trade-Ausführung und Logging",
        "purpose": "Paper-Trading Orders ausführen und auditieren",
        "logic": "Empfängt validierte Execution Orders, führt Paper-Trades aus und speichert alle Transaktionen in der Datenbank für Auditing und Performance-Analyse.",
        "configuration": {
            "execution_mode": "paper",
            "slippage_model": "realistic",
            "fee_rate": 0.001,
            "audit_retention": "7_years"
        },
        "dependencies": ["redis", "database"]
    }
}

async def check_ingestion_agent() -> AgentStatus:
    """Prüft den Ingestion Agent Status"""
    try:
        from app.main import active_agent_tasks
        
        is_running = any("ingestion" in str(task) for task in active_agent_tasks)
        
        # Hol letzte Aktivität aus Redis
        try:
            last_tick = await redis_client.redis.lindex("market:ticks:BTC/USDT", -1)
            if last_tick:
                import json
                tick_data = json.loads(last_tick)
                last_activity = datetime.fromtimestamp(int(tick_data.get('timestamp', 0)) / 1000, timezone.utc).isoformat()
                tasks_processed = await redis_client.redis.llen("market:ticks:BTC/USDT")
            else:
                last_activity = datetime.now(timezone.utc).isoformat()
                tasks_processed = 0
        except:
            last_activity = datetime.now(timezone.utc).isoformat()
            tasks_processed = 0
        
        status = "running" if is_running else "stopped"
        
        definition = AGENT_DEFINITIONS["ingestion"]
        
        return AgentStatus(
            id="ingestion",
            name=definition["name"],
            type=definition["type"],
            status=status,
            last_activity=last_activity,
            tasks_processed=tasks_processed,
            errors=0,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Ingestion Agents: {e}")
        definition = AGENT_DEFINITIONS["ingestion"]
        return AgentStatus(
            id="ingestion",
            name=definition["name"],
            type=definition["type"],
            status="error",
            last_activity=datetime.now(timezone.utc).isoformat(),
            last_error=str(e),
            tasks_processed=0,
            errors=1,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )

async def check_quant_agent() -> AgentStatus:
    """Prüft den Quant Agent Status"""
    try:
        from app.main import active_agent_tasks
        
        is_running = any("quant" in str(task) for task in active_agent_tasks)
        
        # Hol letzte Aktivität aus Redis
        try:
            status_data = await redis_client.redis.get("status:agent:quant")
            if status_data:
                import json
                data = json.loads(status_data)
                last_activity = data.get('timestamp', datetime.now(timezone.utc).isoformat())
                tasks_processed = 1  # Quant produziert ein Signal pro Minute
            else:
                last_activity = datetime.now(timezone.utc).isoformat()
                tasks_processed = 0
        except:
            last_activity = datetime.now(timezone.utc).isoformat()
            tasks_processed = 0
        
        status = "running" if is_running else "stopped"
        
        definition = AGENT_DEFINITIONS["quant"]
        
        return AgentStatus(
            id="quant",
            name=definition["name"],
            type=definition["type"],
            status=status,
            last_activity=last_activity,
            tasks_processed=tasks_processed,
            errors=0,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Quant Agents: {e}")
        definition = AGENT_DEFINITIONS["quant"]
        return AgentStatus(
            id="quant",
            name=definition["name"],
            type=definition["type"],
            status="error",
            last_activity=datetime.now(timezone.utc).isoformat(),
            last_error=str(e),
            tasks_processed=0,
            errors=1,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )

async def check_sentiment_agent() -> AgentStatus:
    """Prüft den Sentiment Agent Status"""
    try:
        from app.main import active_agent_tasks
        
        is_running = any("sentiment" in str(task) for task in active_agent_tasks)
        
        # Hol letzte Aktivität aus Redis
        try:
            status_data = await redis_client.redis.get("status:agent:sentiment")
            if status_data:
                import json
                data = json.loads(status_data)
                last_activity = data.get('timestamp', datetime.now(timezone.utc).isoformat())
                tasks_processed = 1  # Sentiment produziert ein Signal alle 5 Minuten
            else:
                last_activity = datetime.now(timezone.utc).isoformat()
                tasks_processed = 0
        except:
            last_activity = datetime.now(timezone.utc).isoformat()
            tasks_processed = 0
        
        status = "running" if is_running else "stopped"
        
        definition = AGENT_DEFINITIONS["sentiment"]
        
        return AgentStatus(
            id="sentiment",
            name=definition["name"],
            type=definition["type"],
            status=status,
            last_activity=last_activity,
            tasks_processed=tasks_processed,
            errors=0,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Sentiment Agents: {e}")
        definition = AGENT_DEFINITIONS["sentiment"]
        return AgentStatus(
            id="sentiment",
            name=definition["name"],
            type=definition["type"],
            status="error",
            last_activity=datetime.now(timezone.utc).isoformat(),
            last_error=str(e),
            tasks_processed=0,
            errors=1,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )

async def check_risk_agent() -> AgentStatus:
    """Prüft den Risk Agent Status"""
    try:
        from app.main import active_agent_tasks
        
        is_running = any("risk" in str(task) for task in active_agent_tasks)
        
        # Hol letzte Aktivität aus Redis
        try:
            orders = await redis_client.redis.lrange("execution:orders", 0, -1)
            last_activity = datetime.now(timezone.utc).isoformat() if not orders else datetime.now(timezone.utc).isoformat()
            tasks_processed = len(orders)
        except:
            last_activity = datetime.now(timezone.utc).isoformat()
            tasks_processed = 0
        
        status = "running" if is_running else "stopped"
        
        definition = AGENT_DEFINITIONS["risk"]
        
        return AgentStatus(
            id="risk",
            name=definition["name"],
            type=definition["type"],
            status=status,
            last_activity=last_activity,
            tasks_processed=tasks_processed,
            errors=0,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Risk Agents: {e}")
        definition = AGENT_DEFINITIONS["risk"]
        return AgentStatus(
            id="risk",
            name=definition["name"],
            type=definition["type"],
            status="error",
            last_activity=datetime.now(timezone.utc).isoformat(),
            last_error=str(e),
            tasks_processed=0,
            errors=1,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )

async def check_execution_agent() -> AgentStatus:
    """Prüft den Execution Agent Status"""
    try:
        from app.main import active_agent_tasks
        
        is_running = any("execution" in str(task) for task in active_agent_tasks)
        
        # Hol letzte Aktivität aus Datenbank
        try:
            from app.core.database import AsyncSessionLocal
            from app.schemas.models import TradeAuditLog
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    "SELECT COUNT(*) as count, MAX(filled_at) as last_activity FROM trade_audit_logs WHERE status = 'filled'"
                )
                row = result.fetchone()
                tasks_processed = row.count if row else 0
                last_activity = row.last_activity.isoformat() if row and row.last_activity else datetime.now(timezone.utc).isoformat()
        except:
            last_activity = datetime.now(timezone.utc).isoformat()
            tasks_processed = 0
        
        status = "running" if is_running else "stopped"
        
        definition = AGENT_DEFINITIONS["execution"]
        
        return AgentStatus(
            id="execution",
            name=definition["name"],
            type=definition["type"],
            status=status,
            last_activity=last_activity,
            tasks_processed=tasks_processed,
            errors=0,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Execution Agents: {e}")
        definition = AGENT_DEFINITIONS["execution"]
        return AgentStatus(
            id="execution",
            name=definition["name"],
            type=definition["type"],
            status="error",
            last_activity=datetime.now(timezone.utc).isoformat(),
            last_error=str(e),
            tasks_processed=0,
            errors=1,
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"]
        )

@router.get("/status", response_model=AgentsResponse)
async def get_agents_status():
    """
    Holt den Status aller Agenten.
    """
    try:
        # Alle Agenten-Status parallel prüfen
        agent_statuses = await asyncio.gather(
            check_ingestion_agent(),
            check_quant_agent(),
            check_sentiment_agent(),
            check_risk_agent(),
            check_execution_agent(),
            return_exceptions=True
        )
        
        # Ergebnisse verarbeiten
        agents = []
        for status in agent_statuses:
            if isinstance(status, Exception):
                logger.error(f"Agent-Check fehlgeschlagen: {status}")
                continue
            agents.append(status)
        
        # Gesamtstatus berechnen
        total = len(agents)
        running = len([a for a in agents if a.status == "running"])
        error = len([a for a in agents if a.status == "error"])
        
        if error == 0:
            overall = "success" if running > 0 else "idle"
        elif error < total / 2:
            overall = "warning"
        else:
            overall = "error"
        
        response = AgentsResponse(
            agents=agents,
            overall_status=overall,
            last_check=datetime.now(timezone.utc).isoformat(),
            total_agents=total,
            running_agents=running,
            error_agents=error
        )
        
        # In Redis speichern
        await redis_client.redis.set(AGENT_STATUS_KEY, response.json())
        await redis_client.redis.set(LAST_AGENT_CHECK_KEY, datetime.now(timezone.utc).isoformat())
        
        return response
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Agenten-Status: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/info/{agent_id}", response_model=AgentInfo)
async def get_agent_info(agent_id: str):
    """
    Holt detaillierte Informationen über einen spezifischen Agenten.
    """
    try:
        if agent_id not in AGENT_DEFINITIONS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} nicht gefunden")
        
        definition = AGENT_DEFINITIONS[agent_id]
        
        return AgentInfo(
            id=agent_id,
            name=definition["name"],
            description=definition["description"],
            purpose=definition["purpose"],
            logic=definition["logic"],
            configuration=definition["configuration"],
            dependencies=definition["dependencies"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Agenten-Info: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/info", response_model=List[AgentInfo])
async def get_all_agents_info():
    """
    Holt Informationen über alle verfügbaren Agenten.
    """
    try:
        agents = []
        for agent_id, definition in AGENT_DEFINITIONS.items():
            agents.append(AgentInfo(
                id=agent_id,
                name=definition["name"],
                description=definition["description"],
                purpose=definition["purpose"],
                logic=definition["logic"],
                configuration=definition["configuration"],
                dependencies=definition["dependencies"]
            ))
        
        return agents
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen aller Agenten-Infos: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Einfacher Health-Check für die Agenten-API.
    """
    try:
        await redis_client.connect()
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "agents-api"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@router.post("/restart/{agent_id}")
async def restart_agent(agent_id: str):
    """
    Startet einen spezifischen Agenten neu.
    """
    try:
        if agent_id not in AGENT_DEFINITIONS:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} nicht gefunden")
        
        # TODO: Implementiere Agent-Restart-Logik
        # Für jetzt nur logging
        await log_manager.info("AGENT", "AgentManager", f"Agent {agent_id} neustarten angefordert")
        
        return {
            "status": "success",
            "message": f"Agent {agent_id} wird neu gestartet",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Neustarten des Agents {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")

@router.get("/last-check")
async def get_last_check():
    """
    Gibt den Zeitstempel der letzten Agenten-Prüfung zurück.
    """
    try:
        last_check = await redis_client.redis.get(LAST_AGENT_CHECK_KEY)
        if last_check:
            return {"last_check": last_check}
        else:
            return {"last_check": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")
