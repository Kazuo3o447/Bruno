"""
Execution Agent

Hört auf execution:orders und schreibt Paper-Trades via SQLAlchemy in die DB.
Verwendet isolierte AsyncSessionLocal für Background Tasks.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
import uuid
from app.core.redis_client import redis_client
from app.core.database import AsyncSessionLocal
from app.schemas.models import TradeAuditLog

logger = logging.getLogger(__name__)

class ExecutionAgent:
    def __init__(self):
        self._running = False

    async def start(self):
        self._running = True
        pubsub = await redis_client.subscribe_channel("execution:orders")
        if not pubsub:
            return

        logger.info("ExecutionAgent: Bereit für Paper-Trading...")
        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    order = json.loads(message['data'])
                    logger.info(f"💰 EXECUTION: Führe Paper-Trade aus -> {order['action']} {order['symbol']}")
                    
                    # Schreibe in DB (Isolierte Session für Background Task!)
                    async with AsyncSessionLocal() as db:
                        trade_log = TradeAuditLog(
                            id=str(uuid.uuid4()),
                            timestamp=datetime.fromisoformat(order['timestamp']),
                            symbol=order['symbol'],
                            action=order['action'],
                            price=0.0, # Dummy Preis
                            quantity=0.1,
                            total=0.0,
                            quant_score=order['quant_confidence'],
                            sentiment_score=order['sentiment_confidence'],
                            llm_reasoning=order['reason'],
                            status="filled",
                            filled_at=datetime.now(timezone.utc)
                        )
                        db.add(trade_log)
                        await db.commit()
                        logger.info("✅ Paper-Trade in DB gespeichert.")
            except Exception as e:
                logger.error(f"ExecutionAgent Error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self._running = False
