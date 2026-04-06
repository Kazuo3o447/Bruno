"""
CryptoPanic News Client — Bruno Trading Bot

Aggregiert Krypto-News aus CryptoPanic API (diskret, kein Browser-Scraping).
API: https://cryptopanic.com/developers/api/
"""

import asyncio
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger("cryptopanic")


class CryptoPanicClient:
    """CryptoPanic API Client für Krypto-News-Aggregation."""

    def __init__(self, api_key: Optional[str] = None, redis_client=None):
        self.api_key = api_key
        self.redis = redis_client
        self.base_url = "https://cryptopanic.com/api/v1"
        self._last_update: float = 0.0
        self._update_interval: float = 1800.0  # 30 Minuten

    async def fetch_latest_news(self, filter_type: str = "hot") -> List[Dict[str, Any]]:
        """
        Holt die neuesten News von CryptoPanic.
        
        Args:
            filter_type: "hot" (trending), "latest" (neueste), or "bullish"/"bearish"
        
        Returns:
            Liste von News-Artikeln
        """
        if not self.api_key:
            logger.debug("CryptoPanic: kein API Key — übersprungen")
            return []

        try:
            params = {
                "auth_token": self.api_key,
                "filter": filter_type,
                "currencies": "BTC",  # Nur Bitcoin News
                "limit": 20
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{self.base_url}/posts/", params=params)
                
                if response.status_code == 401:
                    logger.warning("CryptoPanic 401 — API Key ungültig")
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"CryptoPanic HTTP {response.status_code}")
                    return []

                data = response.json()
                results = data.get("results", [])
                
                # Artikel formatieren
                formatted_articles = []
                for article in results:
                    formatted_articles.append({
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("published_at"),
                        "source": article.get("source", {}).get("title", "CryptoPanic"),
                        "votes": article.get("votes", {}).get("positive", 0),
                        "domains": article.get("domains", []),
                        "currencies": article.get("currencies", []),
                    })

                logger.info(f"CryptoPanic: {len(formatted_articles)} Artikel geladen (Filter: {filter_type})")
                return formatted_articles

        except Exception as e:
            logger.warning(f"CryptoPanic API Fehler: {e}")
            return []

    async def update(self) -> Dict[str, Any]:
        """
        Hauptmethode: Aktualisiert CryptoPanic News.
        Wird von ContextAgent alle 30min aufgerufen.
        """
        now = datetime.now(timezone.utc)
        
        # Hot News (trending)
        hot_news = await self.fetch_latest_news(filter_type="hot")
        
        # Latest News
        latest_news = await self.fetch_latest_news(filter_type="latest")
        
        result = {
            "hot_news": hot_news,
            "latest_news": latest_news,
            "total_articles": len(hot_news) + len(latest_news),
            "last_update": now.isoformat(),
            "data_source": "cryptopanic"
        }
        
        # In Redis cachen
        await self.redis.set_cache(
            "bruno:cryptopanic:news",
            result,
            ttl=3600  # 1 Stunde
        )
        
        self._last_update = now.timestamp()
        return result

    def is_active(self) -> bool:
        """Prüft ob der Client aktiv ist (API Key vorhanden)."""
        return self.api_key is not None
