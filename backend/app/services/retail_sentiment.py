"""
Retail Sentiment Service — Bruno Trading Bot

Sammelt Retail-Signale aus drei Quellen:
1. Google Trends (BTC + "buy bitcoin")
2. Reddit r/Bitcoin (Top Posts Sentiment)
3. StockTwits (Bull/Bear Ratio)

Datenfluss:
- Alle 6 Stunden aktualisiert
- In Redis gecacht (bruno:retail:sentiment)
- An ContextAgent für GRSS-Berechnung weitergegeben

FOMO-Warning: Wenn alle drei Quellen gleichzeitig extrem bullish
→ Telegram-Alert + Failure Watch Trigger
"""

import asyncio
import httpx
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger("retail_sentiment")


class RetailSentimentService:

    def __init__(self, redis_client, sentiment_analyzer=None):
        self.redis = redis_client
        self.nlp = sentiment_analyzer
        self._last_update: float = 0.0
        self._update_interval: float = 21600.0  # 6 Stunden

    async def update(self) -> Dict[str, Any]:
        """
        Hauptmethode: Aktualisiert alle Retail-Quellen.
        Wird von ContextAgent alle 6h aufgerufen.
        """
        now = datetime.now(timezone.utc)
        
        # Google Trends
        google_score = await self._fetch_google_trends()
        
        # Reddit r/Bitcoin
        reddit_score = await self._fetch_reddit_sentiment()
        
        # StockTwits Bull/Bear Ratio
        stocktwits_score = await self._fetch_stocktwits_ratio()
        
        # Aggregierter Score (-1.0 bis +1.0)
        scores = [s for s in [google_score, reddit_score, stocktwits_score] if s is not None]
        retail_score = sum(scores) / len(scores) if scores else 0.0
        
        # FOMO-Warning: alle > 0.7
        fomo_warning = all(
            s is not None and s > 0.7 
            for s in [google_score, reddit_score, stocktwits_score]
        )
        
        result = {
            "retail_score": retail_score,
            "google_trends": google_score,
            "reddit_sentiment": reddit_score,
            "stocktwits_ratio": stocktwits_score,
            "fomo_warning": fomo_warning,
            "last_update": now.isoformat(),
            "sources_active": len(scores)
        }
        
        # In Redis cachen
        await self.redis.set_cache(
            "bruno:retail:sentiment",
            result,
            ttl=25200  # 7 Stunden
        )
        
        self._last_update = now.timestamp()
        return result

    async def _fetch_google_trends(self) -> Optional[float]:
        """
        Google Trends für "bitcoin" und "buy bitcoin".
        Normalisiert auf 0-100, dann auf -1 bis +1.
        """
        try:
            # pytrends wäre ideal, aber hat Probleme mit headless
            # Wir nutzen einen simpleren HTTP-Ansatz mit public data
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Multi-Interest-Query (bis zu 5 Topics)
                payload = {
                    "req": {
                        "comparisonItem": [
                            {"geo": "", "timeRange": "now 7-d", "complexKeywordsRestriction": {"keyword": [{"type": "BROAD", "value": "bitcoin"}]}},
                            {"geo": "", "timeRange": "now 7-d", "complexKeywordsRestriction": {"keyword": [{"type": "BROAD", "value": "buy bitcoin"}]}}
                        ],
                        "category": 0,
                        "property": ""
                    }
                }
                
                resp = await client.post(
                    "https://trends.google.com/trends/api/explore",
                    json=payload
                )
                
                if resp.status_code == 200:
                    # Parsen der JSON-Antwort
                    data = resp.json()
                    widgets = data.get("widgets", [])
                    
                    bitcoin_trend = None
                    buy_bitcoin_trend = None
                    
                    for widget in widgets:
                        title = widget.get("title", "").lower()
                        if "bitcoin" in title and "buy" not in title:
                            bitcoin_trend = widget
                        elif "buy bitcoin" in title:
                            buy_bitcoin_trend = widget
                    
                    if bitcoin_trend and buy_bitcoin_trend:
                        # Durchschnittliche Werte der letzten 7 Tage
                        btc_avg = self._extract_avg_trend(bitcoin_trend)
                        buy_avg = self._extract_avg_trend(buy_bitcoin_trend)
                        
                        if btc_avg is not None and buy_avg is not None:
                            # Kombinierter Score: "buy bitcoin" hat mehr Gewicht
                            combined = (btc_avg * 0.3 + buy_avg * 0.7) / 50.0  # → 0-2
                            normalized = (combined - 1.0)  # → -1 bis +1
                            return max(-1.0, min(1.0, normalized))
                
        except Exception as e:
            logger.warning(f"Google Trends Fehler: {e}")
        
        return None

    def _extract_avg_trend(self, widget: Dict) -> Optional[float]:
        """Extrahiert den Durchschnittswert aus einem Google Trends Widget."""
        try:
            timeline_data = widget.get("lineData", [])
            if not timeline_data:
                return None
            
            values = [item.get("formattedValue", "0") for item in timeline_data]
            # "1.2K" → 1200, "890" → 890
            numeric_values = []
            for v in values:
                if "K" in v:
                    numeric_values.append(float(v.replace("K", "")) * 1000)
                elif "M" in v:
                    numeric_values.append(float(v.replace("M", "")) * 1000000)
                else:
                    numeric_values.append(float(v))
            
            return sum(numeric_values) / len(numeric_values) if numeric_values else None
        except:
            return None

    async def _fetch_reddit_sentiment(self) -> Optional[float]:
        """
        r/Bitcoin Top Posts der letzten 24h.
        Sentiment-Analyse mit NLP (wenn verfügbar), sonst simplere Heuristik.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Reddit API (no auth needed für public posts)
                resp = await client.get(
                    "https://www.reddit.com/r/Bitcoin/hot.json",
                    headers={"User-Agent": "BrunoBot/1.0"}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    # Top 10 Posts der letzten 24h
                    recent_posts = []
                    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                    
                    for post in posts[:20]:  # Mehr holen, falls ältere dabei
                        post_data = post.get("data", {})
                        created = datetime.fromtimestamp(
                            post_data.get("created_utc", 0),
                            timezone.utc
                        )
                        
                        if created > cutoff:
                            recent_posts.append(post_data)
                    
                    if not recent_posts:
                        return None
                    
                    # Sentiment-Analyse
                    if self.nlp:
                        # Mit echtem NLP
                        texts = [
                            post.get("title", "") + " " + post.get("selftext", "")
                            for post in recent_posts[:10]
                        ]
                        sentiment = await self.nlp.analyze_batch(texts)
                        avg_sentiment = sum(sentiment) / len(sentiment) if sentiment else 0.0
                    else:
                        # Heuristik: bullish/bearish keywords
                        bullish_words = [
                            "moon", "pump", "bull", "buy", "hold", "hodl",
                            "accumulate", "dip", "cheap", "undervalued"
                        ]
                        bearish_words = [
                            "dump", "bear", "sell", "crash", "bubble",
                            "overvalued", "expensive", "scam", "collapse"
                        ]
                        
                        total_score = 0.0
                        for post in recent_posts[:10]:
                            text = (post.get("title", "") + " " + 
                                   post.get("selftext", "")).lower()
                            
                            bullish_count = sum(1 for w in bullish_words if w in text)
                            bearish_count = sum(1 for w in bearish_words if w in text)
                            
                            if bullish_count + bearish_count > 0:
                                post_score = (bullish_count - bearish_count) / (
                                    bullish_count + bearish_count
                                )
                                total_score += post_score
                        
                        avg_sentiment = total_score / min(10, len(recent_posts))
                    
                    return max(-1.0, min(1.0, avg_sentiment))
                
        except Exception as e:
            logger.warning(f"Reddit Sentiment Fehler: {e}")
        
        return None

    async def _fetch_stocktwits_ratio(self) -> Optional[float]:
        """
        StockTwits Bull/Bear Ratio für $BTC.
        Kein API-Key nötig für public streams.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # StockTwits API für BTC sentiment
                resp = await client.get(
                    "https://api.stocktwits.com/api/2/streams/symbol/BTC.json",
                    headers={"User-Agent": "BrunoBot/1.0"}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    messages = data.get("messages", [])
                    
                    if not messages:
                        return None
                    
                    # Letzte 50 Messages analysieren
                    bull_count = 0
                    bear_count = 0
                    
                    for msg in messages[:50]:
                        body = msg.get("body", "").lower()
                        sentiment = msg.get("entities", {}).get("sentiment", {})
                        
                        # Explizites Sentiment
                        if sentiment:
                            if sentiment.get("basic") == "Bullish":
                                bull_count += 1
                            elif sentiment.get("basic") == "Bearish":
                                bear_count += 1
                        else:
                            # Heuristik aus Text
                            bullish_keywords = [
                                "bull", "buy", "long", "moon", "pump",
                                "accumulate", "dip", "cheap"
                            ]
                            bearish_keywords = [
                                "bear", "sell", "short", "dump", "crash",
                                "bubble", "overvalued"
                            ]
                            
                            bull_words = sum(1 for w in bullish_keywords if w in body)
                            bear_words = sum(1 for w in bearish_keywords if w in body)
                            
                            if bull_words > bear_words:
                                bull_count += 1
                            elif bear_words > bull_words:
                                bear_count += 1
                    
                    total = bull_count + bear_count
                    if total > 0:
                        ratio = (bull_count - bear_count) / total
                        return max(-1.0, min(1.0, ratio))
                
        except Exception as e:
            logger.warning(f"StockTwits Fehler: {e}")
        
        return None
