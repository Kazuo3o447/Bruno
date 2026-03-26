"""
Agenten Status API Router

Liest den Agent-Status direkt aus den Redis-Heartbeats.
Kommuniziert mit dem Worker-Container via Redis Pub/Sub.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json
import logging
from app.core.redis_client import redis_client

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

class AgentStatus(BaseModel):
    id: str
    name: str
    type: str
    status: str
    last_activity: str
    uptime_seconds: Optional[float] = 0.0
    processed_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    health: str = "healthy"
    description: str

class AgentsResponse(BaseModel):
    agents: List[AgentStatus]
    overall_status: str
    last_check: str
    total_agents: int
    running_agents: int
    error_agents: int

# Agenten-Definitionen statisch
AGENT_DEFINITIONS = {
    "ingestion": {"name": "Ingestion Agent", "type": "data", "desc": "Live-Marktdaten Sammler"},
    "quant": {"name": "Quant Agent", "type": "analysis", "desc": "Trading-Analyse-Agent"},
    "sentiment": {"name": "Sentiment Agent", "type": "analysis", "desc": "News-Sentiment Analyse"},
    "risk": {"name": "Risk Agent", "type": "risk", "desc": "Risiko-Management & Consent"},
    "execution": {"name": "Execution Agent", "type": "execution", "desc": "Trade-Ausführung"}
}

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

@router.post("/restart/{agent_id}")
async def restart_agent(agent_id: str):
    if agent_id not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} nicht gefunden")
    
    await redis_client.publish_message("worker:commands", json.dumps({
        "command": "restart",
        "agent_id": agent_id
    }))
    return {
        "status": "success",
        "message": f"Restart-Kommando für {agent_id} gesendet"
    }

@router.post("/stop/{agent_id}")
async def stop_agent(agent_id: str):
    if agent_id not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} nicht gefunden")
    
    await redis_client.publish_message("worker:commands", json.dumps({
        "command": "stop",
        "agent_id": agent_id
    }))
    return {
        "status": "success",
        "message": f"Stop-Kommando für {agent_id} gesendet"
    }

@router.post("/start/{agent_id}")
async def start_agent(agent_id: str):
    if agent_id not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} nicht gefunden")
    
    await redis_client.publish_message("worker:commands", json.dumps({
        "command": "start",
        "agent_id": agent_id
    }))
    return {
        "status": "success",
        "message": f"Start-Kommando für {agent_id} gesendet"
    }

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
