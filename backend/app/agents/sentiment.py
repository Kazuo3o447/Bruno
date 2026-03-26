import asyncio
import httpx
import xml.etree.ElementTree as ET
import hashlib
from typing import List, Dict, Tuple, Any
from datetime import datetime, timezone
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import SentimentSignalV2, SignalDirection
import json

class SentimentAgentV2(PollingAgent):
    """
    Phase 3: Sentiment Pipeline
    Liest RSS-Feeds, dedupliziert über Redis und bewertet News über das lokale Ollama-Modell.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("sentiment", deps)
        self.rss_urls = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss"
        ]

    async def setup(self) -> None:
        self.logger.info("SentimentAgent setup abgeschlossen.")
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message="Sentiment Agent gestartet und bereit."
        )

    async def process(self) -> None:
        """Ein einzelner Verarbeitungs-Zyklus."""
        try:
            # RSS-Feeds abrufen
            news_items = await self.fetch_news()
            
            # News deduplizieren
            new_items = await self.deduplicate_news(news_items)
            
            # Sentiment analysieren
            for item in new_items:
                sentiment = await self.analyze_sentiment(item["title"])
                signal = SentimentSignalV2(
                    agent_id=self.agent_id,
                    symbol="BTCUSDT",
                    direction=sentiment["direction"],
                    confidence=sentiment["confidence"],
                    reasoning=sentiment["reasoning"],
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                await self.deps.redis.publish_message("signals:sentiment", signal.json())
                
        except Exception as e:
            self.logger.error(f"SentimentAgent process error: {e}")
            raise

    def get_interval(self) -> float:
        return 300.0  # Alle 5 Minuten News prüfen

    async def _fetch_rss(self, url: str) -> List[Dict[str, str]]:
        articles = []
        try:
            async with httpx.AsyncClient() as client:
                # User-Agent hinzufügen, um 403 Forbidden Fehler bei Cloudflare zu vermeiden
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    for item in root.findall(".//item")[:5]: # Max 5 pro Feed
                        title = item.find("title")
                        link = item.find("link")
                        if title is not None and link is not None:
                            articles.append({"title": title.text, "url": link.text})
        except Exception as e:
            self.logger.warning(f"Fehler beim Abrufen von RSS {url}: {e}")
        return articles

    async def _is_new_article(self, url: str) -> bool:
        """Prüft via Redis, ob wir diesen Artikel schon analysiert haben."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        key = f"sentiment:seen:{url_hash}"
        exists = await self.deps.redis.get_cache(key)
        if exists:
            return False
        # Als gesehen markieren für 24h
        await self.deps.redis.set_cache(key, {"seen": True}, ttl=86400)
        return True

    async def fetch_news(self) -> List[Dict[str, str]]:
        """Holt alle News von RSS-Feeds."""
        all_articles = []
        for url in self.rss_urls:
            articles = await self._fetch_rss(url)
            all_articles.extend(articles)
        return all_articles

    async def deduplicate_news(self, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filtert bereits gesehene Artikel heraus."""
        new_articles = []
        for article in articles:
            if await self._is_new_article(article["url"]):
                new_articles.append(article)
        return new_articles

    async def analyze_sentiment(self, title: str) -> Dict[str, Any]:
        """Analysiert Sentiment eines Artikels via Ollama."""
        try:
            # Einfache Keyword-basierte Analyse als Fallback
            positive_words = ["bullish", "up", "rise", "gain", "positive", "growth", "surge"]
            negative_words = ["bearish", "down", "fall", "drop", "negative", "decline", "crash"]
            
            title_lower = title.lower()
            pos_count = sum(1 for word in positive_words if word in title_lower)
            neg_count = sum(1 for word in negative_words if word in title_lower)
            
            if pos_count > neg_count:
                direction = SignalDirection.BUY
                confidence = min(0.7, 0.3 + (pos_count - neg_count) * 0.1)
            elif neg_count > pos_count:
                direction = SignalDirection.SELL
                confidence = min(0.7, 0.3 + (neg_count - pos_count) * 0.1)
            else:
                direction = SignalDirection.HOLD
                confidence = 0.3
                
            return {
                "direction": direction,
                "confidence": confidence,
                "reasoning": f"Keyword analysis: {pos_count} positive, {neg_count} negative keywords"
            }
        except Exception as e:
            self.logger.error(f"Sentiment analysis error: {e}")
            return {
                "direction": SignalDirection.HOLD,
                "confidence": 0.3,
                "reasoning": "Fallback to neutral due to error"
            }
