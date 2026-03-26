"""
Risk & Consensus Agent

Hört auf Pub/Sub. Triggert Execution, wenn Quant & Sentiment korrelieren.
Implementiert Konfluenz-Check für sichere Entscheidungen.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from app.core.redis_client import redis_client
from app.schemas.agents import ExecutionOrder

logger = logging.getLogger(__name__)

class RiskAgent:
    def __init__(self):
        self._running = False
        self.last_quant = None
        self.last_sentiment = None

    async def start(self):
        self._running = True
        pubsub = await redis_client.subscribe_channel("signals:*")
        if not pubsub:
            return

        logger.info("RiskAgent: Lausche auf Signale...")
        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    channel = message['channel']
                    data = json.loads(message['data'])
                    
                    if channel == "signals:quant":
                        self.last_quant = data
                    elif channel == "signals:sentiment":
                        self.last_sentiment = data

                    # Konfluenz-Check
                    if self.last_quant and self.last_sentiment:
                        q_sig = self.last_quant['signal']
                        s_sig = self.last_sentiment['signal']
                        
                        action = None
                        if q_sig == 1 and s_sig == 1:
                            action = "buy"
                        elif q_sig == -1 and s_sig == -1:
                            action = "sell"
                            
                        if action:
                            order = ExecutionOrder(
                                symbol="BTC/USDT",
                                action=action,
                                reason=f"Konfluenz! Quant:{q_sig} Sent:{s_sig}",
                                quant_confidence=self.last_quant['confidence'],
                                sentiment_confidence=self.last_sentiment['confidence'],
                                timestamp=datetime.now(timezone.utc).isoformat()
                            )
                            await redis_client.publish_message("execution:orders", json.dumps(order.model_dump()))
                            logger.warning(f"🚨 RISK AGENT GIBT FREIGABE: {action.upper()} BTC/USDT")
                            
                            # Signale resetten nach Execution
                            self.last_quant = None
                            self.last_sentiment = None
            except Exception as e:
                logger.error(f"RiskAgent Error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self._running = False
