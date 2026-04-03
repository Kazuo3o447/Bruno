import asyncio
import logging
import time
import httpx
import feedparser
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.core.log_manager import LogManager, LogCategory, LogLevel

# Glaubwürdigkeits-Gewichtung pro Quelle.
# Höher = verlässlicher / institutioneller Fokus.
SOURCE_CREDIBILITY: Dict[str, float] = {
    "cryptopanic":    1.2,   # Kuratiert, breiter Fokus
    "coindesk":       1.3,   # Institutionell, hohe Qualität
    "cointelegraph":  1.0,   # Gut, leicht sensationalistisch
    "decrypt":        0.9,   # Solide, Consumer-fokussiert
}

class SentimentAgent(PollingAgent):
    """
    Sentiment Agent für News-Analyse.
    Nutzt FinBERT, CryptoBERT und Zero-Shot Classification für Sentiment-Scoring.
    Source Credibility Weighting: unterschiedliche Quellen haben unterschiedliches Gewicht.
    CryptoPanic Votes: Artikel mit vielen positiven Votes werden stärker gewichtet.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("sentiment", deps)
        self.analyzer = SentimentAnalyzer()
        self.news_sources: List[str] = []
        self.last_analysis: Optional[Dict[str, Any]] = None

    async def setup(self) -> None:
        """Initialisiert den Sentiment Analyzer (Lazy-Load der Modelle)."""
        self.logger.info("SentimentAgent startet. Modelle werden bei Bedarf geladen.")
        await self.deps.log_manager.add_log(
            LogLevel.INFO,
            LogCategory.AGENT,
            "agent.sentiment",
            "SentimentAgent startet. Modelle werden bei Bedarf geladen."
        )
        # Test-Initialisierung um Fehler früh zu erkennen
        try:
            self.analyzer._init_zero_shot()
            self.logger.info("Zero-Shot Classifier initialisiert.")
            await self.deps.log_manager.add_log(
                LogLevel.INFO,
                LogCategory.AGENT,
                "agent.sentiment",
                "Zero-Shot Classifier initialisiert."
            )
        except Exception as e:
            self.logger.warning(f"Zero-Shot Init (lazy): {e}")
            await self.deps.log_manager.add_log(
                LogLevel.WARNING,
                LogCategory.AGENT,
                "agent.sentiment",
                f"Zero-Shot Init (lazy): {e}"
            )

    async def _report_health(self, source: str, status: str, latency: float):
        """Meldet Status und Latenz an den globalen Redis-Health-Hub."""
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.deps.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.deps.redis.set_cache("bruno:health:sources", current_map)

    def get_interval(self) -> float:
        """15 Minuten — News ändern sich nicht schneller."""
        return 900.0

    async def process(self) -> None:
        """
        Sammelt echte News via CryptoPanic API und RSS Feeds.
        Analysiert Sentiment mit FinBERT/CryptoBERT Pipeline.
        Publiziert aggregierten Score an Redis für ContextAgent.

        KEIN Dummy-Code. Kein random. Echte Daten.
        """
        try:
            headlines = []   # Liste von (source, headline) Tuples

            # ── 1. CryptoPanic API (primäre Quelle) ──────────────
            self.state.sub_state = "fetching news (cryptopanic)"
            api_key = self.deps.config.CRYPTOPANIC_API_KEY
            if api_key:
                try:
                    cp_start = time.perf_counter()
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        resp = await client.get(
                            "https://cryptopanic.com/api/developer/v2/posts/",
                            params={
                                "auth_token": api_key,
                                "public": "true"
                            }
                        )
                        if resp.status_code == 200:
                            cp_latency = (time.perf_counter() - cp_start) * 1000
                            await self._report_health("CryptoPanic", "online", cp_latency)
                            data = resp.json()
                            for post in data.get("results", [])[:20]:
                                title = post.get("title", "").strip()
                                if not title:
                                    continue
                                # Votes als Relevanz-Gewichtung (mehr Votes = wichtiger)
                                votes = post.get("votes", {}) or {}
                                votes_up = int(votes.get("positive", 0) or 0)
                                votes_down = int(votes.get("negative", 0) or 0)
                                total_votes = votes_up + votes_down
                                # Gewichtung: 1.0 bis 2.5 je nach Votes
                                vote_weight = 1.0 + min(1.5, total_votes / 20.0)
                                # Bei negativen Votes leicht heruntergewichten
                                if votes_down > votes_up:
                                    vote_weight *= 0.7
                                headlines.append(("cryptopanic", title, vote_weight))
                            self.logger.debug(
                                f"CryptoPanic: {len(headlines)} Headlines"
                            )
                        else:
                            cp_latency = (time.perf_counter() - cp_start) * 1000
                            await self._report_health("CryptoPanic", "degraded", cp_latency)
                            self.logger.warning(
                                f"CryptoPanic HTTP {resp.status_code}"
                            )
                except Exception as e:
                    cp_latency = (time.perf_counter() - cp_start) * 1000 if 'cp_start' in locals() else 0.0
                    await self._report_health("CryptoPanic", "offline", cp_latency)
                    self.logger.warning(f"CryptoPanic Fehler: {e}")
            else:
                await self._report_health("CryptoPanic", "offline", 0.0)
                self.logger.warning(
                    "CRYPTOPANIC_API_KEY nicht gesetzt — nur RSS Fallback"
                )

            # ── 2. RSS Feeds (Fallback + Ergänzung) ──────────────
            self.state.sub_state = "fetching news (rss)"
            rss_feeds = [
                ("coindesk",      "https://www.coindesk.com/arc/outboundfeeds/rss/"),
                ("cointelegraph", "https://cointelegraph.com/rss"),
                ("decrypt",       "https://decrypt.co/feed"),
            ]
            for source, url in rss_feeds:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:7]:
                        title = entry.get("title", "").strip()
                        if title:
                            # RSS hat keine Votes → Basis-Gewicht 1.0
                            headlines.append((source, title, 1.0))
                except Exception as e:
                    self.logger.debug(f"RSS {source} Fehler: {e}")

            # ── 3. Keine Headlines verfügbar ─────────────────────
            if not headlines:
                self.logger.warning(
                    "Keine Headlines — Sentiment auf 0.0 (neutral) gesetzt"
                )
                await self.deps.redis.set_cache(
                    "bruno:sentiment:aggregate",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "average_score": 0.0,
                        "average_confidence": 0.0,
                        "samples_analyzed": 0,
                        "interpretation": "neutral",
                        "source": "no_data"
                    },
                    ttl=900
                )
                return

            # ── 4. NLP-Analyse mit Source Credibility Weighting ──────────────
            sentiment_scores = []
            total_headlines = len(headlines[:25])
            source_breakdown: Dict[str, List[float]] = {}

            for i, item in enumerate(headlines[:25]):   # Max 25 analysieren
                source, headline = item[0], item[1]
                vote_weight = item[2] if len(item) > 2 else 1.0
                self.state.sub_state = f"analyzing news ({i+1}/{total_headlines})"

                # CoinDesk = institutionelle Perspektive → FinBERT (Makro-Modell)
                # Alle anderen Krypto-Quellen → CryptoBERT
                mode = "macro" if source == "coindesk" else "crypto"

                # Source Credibility aus der globalen Tabelle
                credibility = SOURCE_CREDIBILITY.get(source, 1.0)
                combined_weight = credibility * vote_weight

                try:
                    result = await self.analyzer.analyze_with_filter(headline, mode=mode)
                    if result:
                        result["weight"] = round(combined_weight, 3)
                        result["source"] = source
                        sentiment_scores.append(result)
                        # Breakdown für Diagnose
                        source_breakdown.setdefault(source, []).append(result["score"])
                except Exception as e:
                    self.logger.debug(f"NLP Fehler: {e}")

            if not sentiment_scores:
                self.state.sub_state = "error (no sentiment scores)"
                self.logger.warning("NLP-Analyse ergab keine verwertbaren Ergebnisse")
                return

            # ── 5. Gewichtete Aggregation ─────────────────────────────────────
            self.state.sub_state = "aggregating sentiment"

            # Gewichteter Durchschnitt: Score * Gewicht / Summe Gewichte
            total_weight = sum(s["weight"] for s in sentiment_scores)
            if total_weight > 0:
                avg_score = sum(
                    s["score"] * s["weight"] for s in sentiment_scores
                ) / total_weight
                avg_confidence = sum(
                    s["confidence"] * s["weight"] for s in sentiment_scores
                ) / total_weight
            else:
                avg_score = 0.0
                avg_confidence = 0.0

            interpretation = (
                "bullish" if avg_score > 0.20
                else "bearish" if avg_score < -0.20
                else "neutral"
            )

            # Source-Breakdown für Diagnose und LLM-Kontext
            source_summary = {
                src: round(sum(scores) / len(scores), 3)
                for src, scores in source_breakdown.items()
                if scores
            }

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "average_score": round(avg_score, 3),
                "average_confidence": round(avg_confidence, 3),
                "samples_analyzed": len(sentiment_scores),
                "headlines_collected": len(headlines),
                "interpretation": interpretation,
                "source": "cryptopanic+rss",
                "source_breakdown": source_summary,
                "weighted": True,
            }

            await self.deps.redis.set_cache(
                "bruno:sentiment:aggregate", result, ttl=1800
            )
            self.last_analysis = result

            self.logger.info(
                f"Sentiment: {interpretation} | "
                f"Score={avg_score:.3f} | "
                f"N={len(sentiment_scores)} | "
                f"Headlines={len(headlines)}"
            )

        except Exception as e:
            self.logger.error(f"SentimentAgent Fehler: {e}", exc_info=True)

    async def get_last_analysis(self) -> Optional[Dict[str, Any]]:
        """Gibt die letzte Analyse zurück (für API-Zugriff)."""
        return self.last_analysis
