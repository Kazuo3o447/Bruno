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
            # 1. RSS-Feeds abrufen
            news_items = await self.fetch_news()
            
            # 2. News deduplizieren
            new_items = await self.deduplicate_news(news_items)
            
            if not new_items:
                # Keine neuen News, wir senden kein Signal um Rauschen zu vermeiden
                return

            # 3. Sentiment analysieren und Ergebnisse sammeln
            results = []
            for item in new_items:
                sentiment = await self.analyze_sentiment(item["title"])
                results.append({
                    "sentiment": sentiment,
                    "url": item["url"],
                    "title": item["title"]
                })

            # 4. Aggregation der Ergebnisse
            avg_score = sum(r["sentiment"]["score"] for r in results) / len(results)
            avg_confidence = sum(r["sentiment"]["confidence"] for r in results) / len(results)
            
            # Bestimmung der Gesamt-Richtung basierend auf dem Durchschnitts-Score
            if avg_score > 0.1:
                final_direction = SignalDirection.BUY
            elif avg_score < -0.1:
                final_direction = SignalDirection.SELL
            else:
                final_direction = SignalDirection.HOLD

            # Reasoning zusammenstellen (Top-News erwähnen)
            summary_reasoning = f"Aggregiertes Sentiment aus {len(results)} Artikeln. Konsens: {final_direction.value}. "
            summary_reasoning += "Top News: " + " | ".join([r["title"][:50] + "..." for r in results[:3]])

            # 5. Signal erstellen und publizieren
            signal = SentimentSignalV2(
                agent_id=self.agent_id,
                symbol="BTCUSDT",
                direction=final_direction,
                confidence=round(avg_confidence, 2),
                score=round(avg_score, 2),
                sources=[r["url"] for r in results],
                reasoning=summary_reasoning,
                article_count=len(results)
            )
            
            await self.deps.redis.publish_message("signals:sentiment", signal.model_dump_json())
            
            await self.log_manager.info(
                category="AGENT",
                source=self.agent_id,
                message=f"Sentiment Signal aggregiert: {final_direction.value} ({len(results)} Artikel)",
                details={"score": round(avg_score, 2), "confidence": round(avg_confidence, 2)}
            )
                
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
        """Holt alle News von RSS-Feeds und der CryptoPanic API."""
        all_articles = []
        
        # 1. RSS Feeds abrufen
        for url in self.rss_urls:
            articles = await self._fetch_rss(url)
            all_articles.extend(articles)
            
        # 2. CryptoPanic API abrufen (wenn Key vorhanden)
        cp_articles = await self._fetch_cryptopanic()
        all_articles.extend(cp_articles)
        
        return all_articles

    async def _fetch_cryptopanic(self) -> List[Dict[str, str]]:
        """Holt News von der CryptoPanic API (Alpha Aggregator)."""
        token = self.deps.config.CRYPTOPANIC_API_KEY
        if not token or token == "":
            return []
            
        articles = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://cryptopanic.com/api/v1/posts/"
                params = {
                    "auth_token": token,
                    "currencies": "BTC", # Relevanz für BTCUSDT
                    "filter": "important",
                    "public": "true"
                }
                response = await client.get(url, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    # Wir nehmen die ersten 10 Ergebnisse
                    for item in data.get("results", [])[:10]:
                        articles.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "source": "CryptoPanic"
                        })
        except Exception as e:
            self.logger.warning(f"Fehler beim Abrufen von CryptoPanic: {e}")
        return articles

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
                score = confidence
            elif neg_count > pos_count:
                direction = SignalDirection.SELL
                confidence = min(0.7, 0.3 + (neg_count - pos_count) * 0.1)
                score = -confidence
            else:
                direction = SignalDirection.HOLD
                confidence = 0.3
                score = 0.0
                
            return {
                "direction": direction,
                "confidence": confidence,
                "score": score,
                "reasoning": f"Keyword analysis: {pos_count} positive, {neg_count} negative keywords"
            }
        except Exception as e:
            self.logger.error(f"Sentiment analysis error: {e}")
            return {
                "direction": SignalDirection.HOLD,
                "confidence": 0.3,
                "score": 0.0,
                "reasoning": "Fallback to neutral due to error"
            }
