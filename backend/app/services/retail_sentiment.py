"""
Retail Sentiment Service — Bruno Trading Bot

Aggregiert Social-Sentiment aus Reddit und StockTwits für den Retail-Kontext.
Datenfluss:
- Alle 6 Stunden aktualisiert
- In Redis gecacht (bruno:retail:sentiment)
- An ContextAgent für GRSS-Berechnung weitergegeben

FOMO-Warning: Wenn beide Quellen gleichzeitig extrem bullish
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

    def __init__(self, redis_client, sentiment_analyzer=None, config=None):
        self.redis = redis_client
        self.nlp = sentiment_analyzer
        self.config = config  # Settings-Objekt durchreichen
        self._last_update: float = 0.0
        self._update_interval: float = 21600.0
        self._reddit_token: Optional[str] = None
        self._reddit_token_expiry: float = 0.0

    async def update(self) -> Dict[str, Any]:
        """
        Hauptmethode: Aktualisiert alle Retail-Quellen.
        Wird von ContextAgent alle 6h aufgerufen.
        """
        now = datetime.now(timezone.utc)
        
        # Reddit r/Bitcoin
        reddit_score = await self._fetch_reddit_sentiment()
        
        # StockTwits Bull/Bear Ratio
        stocktwits_score = await self._fetch_stocktwits_ratio()
        
        # Aggregierter Score (-1.0 bis +1.0)
        scores = [s for s in [reddit_score, stocktwits_score] if s is not None]
        retail_score = sum(scores) / len(scores) if scores else 0.0
        
        # FOMO-Warning: alle > 0.7
        fomo_warning = all(
            s is not None and s > 0.7 
            for s in [reddit_score, stocktwits_score]
        )
        
        result = {
            "retail_score": retail_score,
            "reddit_sentiment": reddit_score,
            "stocktwits_ratio": stocktwits_score,
            "fomo_warning": fomo_warning,
            "last_update": now.isoformat(),
            "data_sources": ["reddit", "stocktwits"]
        }
        
        # In Redis cachen
        await self.redis.set_cache(
            "bruno:retail:sentiment",
            result,
            ttl=25200  # 7 Stunden
        )
        
        self._last_update = now.timestamp()
        return result

    # Legacy helper removed. Social sentiment aggregation is intentionally limited
    # to the active sources above.

    async def _get_reddit_token(self) -> Optional[str]:
        """App-Only OAuth, kein User-Login. Token gilt 24h."""
        import time as _time
        now = _time.time()
        if self._reddit_token and now < self._reddit_token_expiry - 60:
            return self._reddit_token

        client_id = getattr(self.config, "REDDIT_CLIENT_ID", None) if self.config else None
        client_secret = getattr(self.config, "REDDIT_CLIENT_SECRET", None) if self.config else None

        if not client_id or not client_secret:
            return None  # Kein Key → anonymer Zugriff

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    data={"grant_type": "client_credentials"},
                    auth=(client_id, client_secret),
                    headers={"User-Agent": "BrunoBot/1.0"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._reddit_token = data["access_token"]
                    self._reddit_token_expiry = now + data.get("expires_in", 86400)
                    logger.info("Reddit OAuth Token erhalten")
                    return self._reddit_token
        except Exception as e:
            logger.warning(f"Reddit OAuth Token Fehler: {e}")

        return None

    async def _fetch_reddit_sentiment(self) -> Optional[float]:
        """r/Bitcoin mit OAuth (60 req/min) oder anonym als Fallback."""
        try:
            token = await self._get_reddit_token()

            if token:
                url = "https://oauth.reddit.com/r/Bitcoin/hot.json"
                headers = {"Authorization": f"Bearer {token}", "User-Agent": "BrunoBot/1.0"}
            else:
                url = "https://www.reddit.com/r/Bitcoin/hot.json"
                headers = {"User-Agent": "BrunoBot/1.0"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 429:
                    logger.warning("Reddit 429 — kein OAuth Key konfiguriert oder Limit erreicht")
                    return None

                if resp.status_code != 200:
                    return None

                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_posts = [
                    p["data"] for p in posts[:20]
                    if datetime.fromtimestamp(p["data"].get("created_utc", 0), timezone.utc) > cutoff
                ]

                if not recent_posts:
                    return None

                bullish = ["moon", "pump", "bull", "buy", "hold", "hodl", "accumulate", "dip", "cheap", "undervalued"]
                bearish = ["dump", "bear", "sell", "crash", "bubble", "overvalued", "expensive", "scam", "collapse"]

                total = 0.0
                for post in recent_posts[:10]:
                    text = (post.get("title", "") + " " + post.get("selftext", "")).lower()
                    b = sum(1 for w in bullish if w in text)
                    d = sum(1 for w in bearish if w in text)
                    if b + d > 0:
                        total += (b - d) / (b + d)

                return max(-1.0, min(1.0, total / min(10, len(recent_posts))))

        except Exception as e:
            logger.warning(f"Reddit Sentiment Fehler: {e}")
        return None

    async def _fetch_stocktwits_ratio(self) -> Optional[float]:
        """
        StockTwits Bull/Bear Ratio.
        Wird sofort übersprungen wenn kein STOCKTWITS_API_KEY gesetzt.
        Verhindert den 403-Request beim jedem Zyklus.
        """
        api_key = getattr(self.config, "STOCKTWITS_API_KEY", None) if self.config else None

        if not api_key:
            logger.debug("StockTwits: kein API Key — übersprungen")
            return None  # Graceful skip, kein Request

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.stocktwits.com/api/2/streams/symbol/BTC.json",
                    headers={"Authorization": f"OAuth {api_key}", "User-Agent": "BrunoBot/1.0"}
                )
                if resp.status_code in (401, 403):
                    logger.warning(f"StockTwits {resp.status_code} — API Key ungültig")
                    return None

                if resp.status_code == 200:
                    messages = resp.json().get("messages", [])
                    bull = sum(1 for m in messages[:50] if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
                    bear = sum(1 for m in messages[:50] if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
                    total = bull + bear
                    return max(-1.0, min(1.0, (bull - bear) / total)) if total > 0 else None

        except Exception as e:
            logger.warning(f"StockTwits Fehler: {e}")
        return None
