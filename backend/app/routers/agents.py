from fastapi import APIRouter
from app.core.redis_client import redis_client

router = APIRouter()

@router.get("/agents/status/quant")
async def quant_status():
    """Liest das letzte Signal des Quant-Agenten aus dem Cache."""
    try:
        latest_signal = await redis_client.get_cache("agent:latest:quant:BTC/USDT")
        
        if not latest_signal:
            return {"status": "waiting", "message": "Noch kein Signal berechnet"}
            
        return {
            "status": "ok",
            "agent_alive": True,
            "latest_signal": latest_signal
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/agents/kill")
async def emergency_kill():
    """
    Emergency Stop: Publiziert Kill-Command an den Worker-Orchestrator.
    Der Worker hört auf 'worker:commands' und stoppt alle Agenten.
    """
    import json
    try:
        await redis_client.publish_message(
            "worker:commands",
            json.dumps({"command": "shutdown"})
        )
        # Zusätzlich: Veto sofort setzen damit kein Trade mehr ausgeführt wird
        from datetime import datetime, timezone
        await redis_client.redis.set(
            "bruno:veto:state",
            json.dumps({
                "Veto_Active": True,
                "Reason": "EMERGENCY STOP via Kill-Switch",
                "Max_Leverage": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        )
        await redis_client.redis.publish(
            "bruno:pubsub:veto",
            json.dumps({
                "Veto_Active": True,
                "Reason": "EMERGENCY STOP via Kill-Switch",
                "Max_Leverage": 0.0,
            })
        )
        return {"status": "ok", "message": "Emergency Stop ausgeführt. Alle Agenten werden gestoppt."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
