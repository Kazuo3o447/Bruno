import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# Füge das Projektverzeichnis zum Pfad hinzu
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.redis_client import redis_client

async def check_heartbeats():
    await redis_client.connect()
    
    agents = ["ingestion", "quant", "context", "sentiment", "risk", "execution"]
    print(f"{'Agent':<12} | {'Status':<10} | {'Health':<10} | {'Last Update':<20} | {'Uptime':<10}")
    print("-" * 75)
    
    for agent_id in agents:
        key = f"heartbeat:{agent_id}"
        data = await redis_client.get_cache(key)
        if data:
            status = data.get("status", "N/A")
            health = data.get("health", "N/A")
            last_ts = data.get("timestamp", "N/A")
            uptime = f"{data.get('uptime_seconds', 0):.1f}s"
            
            # Check if stale (more than 2m)
            if last_ts != "N/A":
                try:
                    ts = datetime.fromisoformat(last_ts)
                    diff = (datetime.now(timezone.utc) - ts).total_seconds()
                    if diff > 120:
                        status = f"STALE ({diff:.0f}s)"
                except:
                    pass
            
            print(f"{agent_id:<12} | {status:<10} | {health:<10} | {last_ts[:19]:<20} | {uptime:<10}")
        else:
            print(f"{agent_id:<12} | {'MISSING':<10} | {'N/A':<10} | {'N/A':<20} | {'N/A':<10}")
    
    print("-" * 75)
    await redis_client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_heartbeats())
