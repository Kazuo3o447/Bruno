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
    agents = []
    running = 0
    errors = 0

    for agent_id, info in AGENT_DEFINITIONS.items():
        try:
            hb_data = await redis_client.get_cache(f"heartbeat:{agent_id}")
            if hb_data:
                status_str = hb_data.get("status", "unknown")
                if status_str == "running":
                    running += 1
                elif status_str == "error":
                    errors += 1

                agents.append(AgentStatus(
                    id=agent_id,
                    name=info["name"],
                    type=info["type"],
                    description=info["desc"],
                    status=status_str,
                    last_activity=hb_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    uptime_seconds=hb_data.get("uptime_seconds", 0.0),
                    processed_count=hb_data.get("processed_count", 0),
                    error_count=hb_data.get("error_count", 0),
                    consecutive_errors=hb_data.get("consecutive_errors", 0),
                    last_error=hb_data.get("last_error"),
                    health=hb_data.get("health", "healthy")
                ))
            else:
                # Kein Heartbeat -> Tot oder Offline
                agents.append(AgentStatus(
                    id=agent_id,
                    name=info["name"],
                    type=info["type"],
                    description=info["desc"],
                    status="dead",
                    last_activity=datetime.now(timezone.utc).isoformat(),
                ))
        except Exception as e:
            logger.error(f"Fehler bei Status für {agent_id}: {e}")

    total = len(AGENT_DEFINITIONS)
    overall = "success" if running == total else ("warning" if running > 0 else "error")

    return AgentsResponse(
        agents=agents,
        overall_status=overall,
        last_check=datetime.now(timezone.utc).isoformat(),
        total_agents=total,
        running_agents=running,
        error_agents=errors
    )

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
