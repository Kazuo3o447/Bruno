import asyncio
import logging
import time
import feedparser
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.core.log_manager import LogManager, LogCategory, LogLevel
from app.core.cryptocompare_client import get_cryptocompare_client
from app.core.coinmarketcap_client import get_coinmarketcap_client

class SentimentAgent(PollingAgent):
    """
    Sentiment Agent für News-Analyse.
    Nutzt FinBERT, CryptoBERT und Zero-Shot Classification für Sentiment-Scoring.
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
        Sammelt echte News via CryptoCompare, CoinMarketCap und RSS Feeds.
        Analysiert Sentiment mit FinBERT/CryptoBERT Pipeline.
        Publiziert aggregierten Score an Redis für ContextAgent.

        KEIN Dummy-Code. Kein random. Echte Daten.
        """
        try:
            headlines: List[Dict[str, Any]] = []
            cc_news_items: List[Dict[str, Any]] = []
            cc_market_bundle: Dict[str, Any] = {}
            cmc_market_bundle: Dict[str, Any] = {}
            cc_api_key = self.deps.config.CRYPTOCOMPARE_API_KEY
            cmc_api_key = self.deps.config.COINMARKETCAP_API_KEY

            # ── 1. CryptoCompare + CoinMarketCap (parallel, Bitcoin-zentriert) ──────────────
            if cc_api_key or cmc_api_key:
                fetch_tasks = []
                if cc_api_key:
                    self.state.sub_state = "fetching news (cryptocompare)"
                    cryptocompare = get_cryptocompare_client(cc_api_key)
                    fetch_tasks.append(("cryptocompare", cryptocompare.get_news(limit=50, categories=["BTC", "Bitcoin", "Regulation", "Exchange"]), cryptocompare.get_market_bundle(symbols=["BTC", "ETH"], tsym="USD")))
                if cmc_api_key:
                    self.state.sub_state = "fetching market (coinmarketcap)"
                    coinmarketcap = get_coinmarketcap_client(cmc_api_key)
                    fetch_tasks.append(("coinmarketcap", coinmarketcap.get_btc_bundle(convert="USD")))

                try:
                    if cc_api_key:
                        cc_start = time.perf_counter()
                        cc_news_items, cc_market_bundle = await asyncio.gather(
                            fetch_tasks[0][1],
                            fetch_tasks[0][2],
                        )
                        cc_latency = (time.perf_counter() - cc_start) * 1000
                        if cc_news_items:
                            await self._report_health("CryptoCompare_News", "online", cc_latency)
                            for item in cc_news_items[:30]:
                                title = item.get("title", "").strip()
                                if title:
                                    headlines.append({
                                        "source": "cryptocompare",
                                        "title": title,
                                        "categories": item.get("categories", []) or [],
                                        "language": item.get("language", "EN"),
                                    })
                            await self._report_health("CryptoCompare_Market", "online", cc_latency)
                        else:
                            await self._report_health("CryptoCompare_News", "degraded", cc_latency)
                            await self._report_health("CryptoCompare_Market", "degraded", cc_latency)
                    else:
                        await self._report_health("CryptoCompare_News", "offline", 0.0)
                        await self._report_health("CryptoCompare_Market", "offline", 0.0)

                    if cmc_api_key:
                        cmc_start = time.perf_counter()
                        cmc_market_bundle = await fetch_tasks[-1][1]
                        cmc_latency = (time.perf_counter() - cmc_start) * 1000
                        if cmc_market_bundle:
                            await self._report_health("CoinMarketCap_BTC", "online", cmc_latency)
                            await self._report_health("CoinMarketCap_Global", "online", cmc_latency)
                        else:
                            await self._report_health("CoinMarketCap_BTC", "degraded", cmc_latency)
                            await self._report_health("CoinMarketCap_Global", "degraded", cmc_latency)
                    else:
                        await self._report_health("CoinMarketCap_BTC", "offline", 0.0)
                        await self._report_health("CoinMarketCap_Global", "offline", 0.0)

                    if cc_market_bundle:
                        cc_market_bundle["timestamp"] = datetime.now(timezone.utc).isoformat()
                        await self.deps.redis.set_cache("bruno:cryptocompare:bundle", cc_market_bundle, ttl=1800)

                    if cmc_market_bundle:
                        cmc_market_bundle["timestamp"] = datetime.now(timezone.utc).isoformat()
                        await self.deps.redis.set_cache("bruno:coinmarketcap:bundle", cmc_market_bundle, ttl=1800)

                    if not cc_news_items and not cmc_market_bundle:
                        self.logger.warning("Weder CryptoCompare noch CoinMarketCap lieferten verwertbare Daten")

                except Exception as e:
                    if cc_api_key:
                        await self._report_health("CryptoCompare_News", "offline", 0.0)
                        await self._report_health("CryptoCompare_Market", "offline", 0.0)
                    if cmc_api_key:
                        await self._report_health("CoinMarketCap_BTC", "offline", 0.0)
                        await self._report_health("CoinMarketCap_Global", "offline", 0.0)
                    self.logger.warning(f"Dual-Source Fehler: {e}")
            else:
                await self._report_health("CryptoCompare_News", "offline", 0.0)
                await self._report_health("CryptoCompare_Market", "offline", 0.0)
                await self._report_health("CoinMarketCap_BTC", "offline", 0.0)
                await self._report_health("CoinMarketCap_Global", "offline", 0.0)
                self.logger.warning("CRYPTOCOMPARE_API_KEY und COINMARKETCAP_API_KEY nicht gesetzt — nur RSS Fallback")

            # ── 2. News Ingestion Integration (Tier-1 Source) ──────────────
            self.state.sub_state = "fetching news (ingestion service)"
            try:
                processed_news = await self.deps.redis.get_cache("bruno:news:processed_items") or []
                if processed_news:
                    await self._report_health("News_Ingestion", "online", 0.0)
                    self.logger.info(f"News Ingestion: {len(processed_news)} verarbeitete Items geladen")
                    
                    # Füge verarbeitete News zu Headlines hinzu (mit Sentiment vor-analysiert)
                    for item in processed_news[-20:]:  # Letzte 20 Items
                        headlines.append({
                            "source": f"ingestion_{item.get('source', 'unknown')}",
                            "title": item.get("title", ""),
                            "categories": ["NewsIngestion"],
                            "language": "EN",
                            "pre_analyzed_sentiment": item.get("sentiment_score", 0.0),
                            "pre_analyzed_label": item.get("sentiment", "neutral")
                        })
                else:
                    await self._report_health("News_Ingestion", "degraded", 0.0)
                    self.logger.debug("News Ingestion: Keine verarbeiteten Items gefunden")
            except Exception as e:
                await self._report_health("News_Ingestion", "offline", 0.0)
                self.logger.error(f"News Ingestion Integration Fehler: {e}")

            # ── 3. RSS Feeds (Fallback + Ergänzung) ──────────────
            self.state.sub_state = "fetching news (rss)"
            rss_feeds = [
                ("coindesk",      "https://www.coindesk.com/arc/outboundfeeds/rss/"),
                ("cointelegraph", "https://cointelegraph.com/rss"),
                ("decrypt",       "https://decrypt.co/feed"),
            ]
            for source, url in rss_feeds:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:5]:
                        title = entry.get("title", "").strip()
                        if title:
                            headlines.append({
                                "source": source,
                                "title": title,
                                "categories": ["RSS"],
                                "language": entry.get("language", "EN"),
                            })
                except Exception as e:
                    self.logger.debug(f"RSS {source} Fehler: {e}")

            # ── 4. Keine Headlines verfügbar ─────────────────────
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
                        "headlines_collected": 0,
                        "sources": [],
                        "categories": [],
                        "interpretation": "neutral",
                        "source": "cryptocompare+coinmarketcap+rss"
                    },
                    ttl=900
                )
                return

            # ── 5. NLP-Analyse ────────────────────────────────────
            sentiment_scores = []
            total_headlines = len(headlines[:20])
            for i, item in enumerate(headlines[:20]):   # Max 20 analysieren
                source = item["source"]
                headline = item["title"]
                categories = [c.lower() for c in (item.get("categories") or [])]
                self.state.sub_state = f"analyzing news ({i+1}/{total_headlines})"
                
                # Prüfe ob vor-analysierte Daten vorliegen (News Ingestion)
                if "pre_analyzed_sentiment" in item:
                    # Nutze vor-analysierte Sentiment-Daten
                    sentiment_scores.append({
                        "score": item["pre_analyzed_sentiment"],
                        "confidence": 0.8,  # Hohe Konfidenz bei vor-analysierten Daten
                        "classification": item.get("pre_analyzed_label", "neutral"),
                        "source": source
                    })
                    self.logger.debug(f"Vor-analysiert: {headline[:30]}... -> {item['pre_analyzed_sentiment']:.3f}")
                else:
                    # Makro-/Regulierungsquellen → FinBERT
                    # Krypto-spezifische Quellen → CryptoBERT
                    mode = "macro" if source == "coindesk" or any(cat in {"regulation", "exchange"} for cat in categories) else "crypto"
                    try:
                        result = await self.analyzer.analyze_with_filter(
                            headline, mode=mode
                        )
                        if result:
                            sentiment_scores.append(result)
                    except Exception as e:
                        self.logger.debug(f"NLP Fehler: {e}")

            if not sentiment_scores:
                self.state.sub_state = "error (no sentiment scores)"
                self.logger.warning("NLP-Analyse ergab keine verwertbaren Ergebnisse")
                return

            # ── 5. Aggregation ────────────────────────────────────
            self.state.sub_state = "aggregating sentiment"
            avg_score = sum(s["score"] for s in sentiment_scores) / len(sentiment_scores)
            avg_confidence = sum(
                s["confidence"] for s in sentiment_scores
            ) / len(sentiment_scores)

            top_sources = Counter(item["source"] for item in headlines).most_common(5)
            top_categories = Counter(cat for item in headlines for cat in (item.get("categories") or [])).most_common(10)

            interpretation = (
                "bullish" if avg_score > 0.20
                else "bearish" if avg_score < -0.20
                else "neutral"
            )

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "average_score": round(avg_score, 3),
                "average_confidence": round(avg_confidence, 3),
                "samples_analyzed": len(sentiment_scores),
                "headlines_collected": len(headlines),
                "sources": [source for source, _ in top_sources],
                "categories": [category for category, _ in top_categories],
                "news_summary": {
                    "cryptocompare_articles": len(cc_news_items),
                    "coinmarketcap_articles": 0,
                    "bitcoin_filter": True,
                    "sources": ["CryptoCompare", "CoinMarketCap", "RSS"],
                },
                "cryptocompare_bundle": cc_market_bundle,
                "coinmarketcap_bundle": cmc_market_bundle,
                "interpretation": interpretation,
                "source": "cryptocompare+coinmarketcap+rss"
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
