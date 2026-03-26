"""
Sentiment Agent

Simuliert News-Check (Polling) und bewertet via Ollama Qwen2.5.
Verwendet Exponential Backoff für robuste LLM-Anfragen.
"""

import asyncio
import logging
import json
import httpx
from datetime import datetime, timezone
from app.core.redis_client import redis_client
from app.core.llm_client import ollama_client
from app.schemas.agents import SentimentSignal

logger = logging.getLogger(__name__)

class SentimentAgent:
    def __init__(self):
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                # DUMMY-NEWS (Da Krypto-APIs oft Keys brauchen, simulieren wir hier einen starken News-Feed für Tests)
                # In Prod: Hier CryptoPanic API abfragen
                dummy_news = "Bitcoin Adoption soars as major banks announce massive BTC purchases for their treasuries."
                
                analysis = await ollama_client.analyze_sentiment(dummy_news)
                
                # Convert -1.0 to 1.0 into discrete -1, 0, 1
                sentiment_val = analysis.get("sentiment", 0)
                signal = 1 if sentiment_val > 0.2 else (-1 if sentiment_val < -0.2 else 0)
                
                sig = SentimentSignal(
                    symbol="BTC/USDT",
                    signal=signal,
                    confidence=float(analysis.get("confidence", 0.5)),
                    reasoning=analysis.get("reasoning", "No data")[:100],
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                await redis_client.publish_message("signals:sentiment", json.dumps(sig.model_dump()))
                await redis_client.set_cache("status:agent:sentiment", sig.model_dump())
                logger.debug(f"Sentiment Signal: {signal} (Conf: {sig.confidence})")
            except Exception as e:
                logger.error(f"SentimentAgent Error: {e}")
            
            await asyncio.sleep(300) # Alle 5 Minuten

    async def stop(self):
        self._running = False
