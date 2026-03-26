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
