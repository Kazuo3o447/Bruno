import asyncio
import httpx
import xml.etree.ElementTree as ET
import hashlib
from typing import List, Dict, Tuple
from datetime import datetime, timezone
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import SentimentSignalV2, SignalDirection

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

        try:
            # Health Check vorab
            ollama_ok = await self.deps.ollama.health_check()
            if not ollama_ok:
                self.state.health = "degraded"
                await self.log_manager.warning(
                    category="AGENT",
                    source=self.agent_id,
                    message="Ollama Service nicht erreichbar. Nutze Keyword-Fallback."
                )
            else:
                self.state.health = "healthy"

            all_articles = []
            for url in self.rss_urls:
                all_articles.extend(await self._fetch_rss(url))
                
            new_articles = []
            for art in all_articles:
                if await self._is_new_article(art["url"]):
                    new_articles.append(art)
                    
            if not new_articles:
                self.logger.info("Keine neuen News gefunden.")
                # Wir publishen trotzdem ein neutrales Signal, damit RiskAgent Kontext bekommt
                signal = SentimentSignalV2(
                    agent_id=self.agent_id,
                    symbol="BTCUSDT",
                    direction=SignalDirection.HOLD,
                    confidence=0.5,
                    score=0.0,
                    sources=["Cache"],
                    reasoning="Keine neuen Artikel seit letztem Check.",
                    article_count=0
                )
                await self.deps.redis.publish_message("signals:sentiment", signal.model_dump_json())
                return
                
            scores = []
            reasonings = []
            
            for art in new_articles:
                # LLM Analyse
                self.logger.info(f"Analysiere News: {art['title']}")
                await self.log_manager.debug(
                    category="AGENT",
                    source=self.agent_id,
                    message=f"Analysiere News: {art['title'][:50]}..."
                )
                analysis = await self.deps.ollama.analyze_sentiment(art["title"])
                
                # normalize score if LLM ignores format
                score = analysis.get("sentiment", 0.0)
                try:
                    score = float(score)
                except:
                    score = 0.0
                    
                scores.append(score)
                reasonings.append(analysis.get("reasoning", "Kein Reasoning"))
            
            avg_score = sum(scores) / len(scores)
            
            if avg_score > 0.3:
                direction = SignalDirection.BUY
                confidence = min(0.5 + abs(avg_score), 1.0)
            elif avg_score < -0.3:
                direction = SignalDirection.SELL
                confidence = min(0.5 + abs(avg_score), 1.0)
            else:
                direction = SignalDirection.HOLD
                confidence = 0.5
                
            short_reason = reasonings[0] if reasonings else "Kein Reasoning"
            
            signal = SentimentSignalV2(
                agent_id=self.agent_id,
                symbol="BTCUSDT",
                direction=direction,
                confidence=confidence,
                score=avg_score,
                sources=["CoinTelegraph", "CoinDesk"],
                reasoning=f"Analyzed {len(new_articles)} new articles. Avg Sentiment: {avg_score:.2f}. Example: {short_reason}",
                article_count=len(new_articles)
            )
            
            await self.deps.redis.publish_message("signals:sentiment", signal.model_dump_json())
            
            await self.log_manager.info(
                category="AGENT",
                source=self.agent_id,
                message=f"Sentiment Signal publiziert: {direction.value} (Score: {avg_score:.2f})",
                details={"confidence": confidence, "articles": len(new_articles)}
            )
            self.logger.info(f"Sentiment Signal publiziert: Score {avg_score:.2f}")

        except Exception as e:
            self.logger.error(f"Fehler in Sentiment-Analyse: {e}")
