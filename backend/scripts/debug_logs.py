import asyncio
import json
import os
import sys

# Füge das Projektverzeichnis zum Pfad hinzu
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.redis_client import redis_client
from app.core.log_manager import LogManager

async def fetch_logs():
    lm = LogManager()
    # Wir müssen manuell connecten, da wir nicht im FastAPI-Context sind
    await redis_client.connect()
    
    print("Frage Redis-Logs ab...")
    logs = await lm.get_logs(limit=50)
    
    if not logs:
        print("Keine Logs in Redis gefunden.")
        return

    print(f"Gefundene Logs: {len(logs)}")
    print("-" * 80)
    for log in reversed(logs):
        ts = log.timestamp.split("T")[1][:8] # Nur Zeit
        print(f"[{ts}] [{log.level}] [{log.category}] {log.source}: {log.message}")
        if log.stack_trace:
            print(f"STACK TRACE:\n{log.stack_trace}")
    print("-" * 80)
    
    await redis_client.disconnect()

if __name__ == "__main__":
    asyncio.run(fetch_logs())
