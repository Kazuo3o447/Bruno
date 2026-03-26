"""
Ingestion Agent

Zieht Live-Ticks via nativen WebSockets von Binance und pusht sie in Redis.
Verwendet Exponential Backoff für robuste Verbindung.
"""

import asyncio
import websockets
import json
import logging
from app.core.redis_client import redis_client
from app.schemas.agents import TickData

logger = logging.getLogger(__name__)

class IngestionAgent:
    def __init__(self):
        self.ws_url = "wss://fstream.binance.com/ws/btcusdt@aggTrade"
        self._running = False

    async def start(self):
        self._running = True
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    logger.info("IngestionAgent: Verbunden mit Binance Futures WS")
                    backoff = 1
                    async for message in ws:
                        if not self._running:
                            break
                        data = json.loads(message)
                        if 'p' in data and 'q' in data:
                            tick = {"symbol": "BTC/USDT", "price": float(data['p']), "volume": float(data['q']), "timestamp": int(data['T'])}
                            await redis_client.publish_stream("market:ticks:BTC/USDT", tick)
            except Exception as e:
                logger.error(f"IngestionAgent WS Error: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def stop(self):
        self._running = False
