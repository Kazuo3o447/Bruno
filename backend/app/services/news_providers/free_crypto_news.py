"""
Tier-3 News Integration: FreeCryptoNewsClient
Fail-safe supplementary layer for news ingestion with Zero Trust architecture.
"""

import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("free_crypto_news_client")


class FreeCryptoNewsClient:
    """
    Isolated defensive client for nirholas/free-crypto-news API.
    Zero Trust: Never blocks main thread, graceful degradation on failures.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("free_crypto_news_client")
        self.base_url = "https://cryptocurrency.cv/api"
        
        # HTTP Client with aggressive timeout for defensive operations
        self._http_client = httpx.AsyncClient(
            timeout=5.0,  # Hard 5-second timeout as required
            headers={"User-Agent": "Bruno-Institutional-News-Aggregator/1.0"}
        )
    
    async def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Defensives HTTP-Polling mit absoluter Härte gegen Ausfälle.
        
        Returns:
            List[Dict]: Normalisierte News-Items oder leere Liste bei Fehlern.
        """
        try:
            # Haupt-Endpoint für allgemeine News
            url = f"{self.base_url}/news"
            response = await self._http_client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Artikel aus der Response extrahieren
            articles = data.get("articles", [])
            
            for item in articles:
                # Pflichtfelder extrahieren
                title = item.get("title", "")
                description = item.get("description", "")
                
                # Rauschunterdrückung (Pre-Filter) - BTC/Bitcoin Check
                combined_text = (title + " " + description).lower()
                if "btc" not in combined_text and "bitcoin" not in combined_text:
                    continue
                
                # Standardisiertes Output-Format erstellen
                normalized_item = {
                    "title": title,
                    "text": description,  # description als text field
                    "source": "free-crypto-news",
                    "timestamp": item.get("pubDate", datetime.now(timezone.utc).isoformat()),
                    "url": item.get("link", ""),
                    "metadata": {
                        "source_feed": item.get("source", "unknown"),
                        "time_ago": item.get("timeAgo", ""),
                        "api_fetched_at": data.get("fetchedAt", "")
                    }
                }
                
                results.append(normalized_item)
            
            self.logger.info(f"FreeCryptoNews: {len(results)} BTC-related items fetched")
            return results
            
        except httpx.TimeoutException:
            # Timeout handling - logge exakt eine Zeile wie gefordert
            self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            return []
            
        except httpx.HTTPStatusError as e:
            # 5xx und andere HTTP Errors
            if e.response.status_code >= 500:
                self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            else:
                self.logger.warning(f"FreeCryptoNews API returned {e.response.status_code}. Skipping.")
            return []
            
        except Exception as e:
            # JSON Decode Errors und andere unerwartete Fehler
            self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            return []
    
    async def fetch_bitcoin_news(self) -> List[Dict[str, Any]]:
        """
        Spezieller Bitcoin-Endpoint für höhere BTC-Dichte.
        Fallback Methode mit identischer Defensive-Logik.
        """
        try:
            url = f"{self.base_url}/bitcoin"
            response = await self._http_client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            articles = data.get("articles", [])
            
            for item in articles:
                title = item.get("title", "")
                description = item.get("description", "")
                
                # Double-Check BTC Filter (obwohl Bitcoin-Endpoint)
                combined_text = (title + " " + description).lower()
                if "btc" not in combined_text and "bitcoin" not in combined_text:
                    continue
                
                normalized_item = {
                    "title": title,
                    "text": description,
                    "source": "free-crypto-news",
                    "timestamp": item.get("pubDate", datetime.now(timezone.utc).isoformat()),
                    "url": item.get("link", ""),
                    "metadata": {
                        "source_feed": item.get("source", "unknown"),
                        "time_ago": item.get("timeAgo", ""),
                        "api_fetched_at": data.get("fetchedAt", ""),
                        "endpoint": "bitcoin"
                    }
                }
                
                results.append(normalized_item)
            
            self.logger.info(f"FreeCryptoNews (Bitcoin): {len(results)} items fetched")
            return results
            
        except httpx.TimeoutException:
            self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            return []
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            else:
                self.logger.warning(f"FreeCryptoNews API returned {e.response.status_code}. Skipping.")
            return []
            
        except Exception:
            self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
            return []
    
    async def shutdown(self):
        """Cleanup resources."""
        await self._http_client.aclose()
        self.logger.info("FreeCryptoNewsClient shutdown complete")


# Global instance für den Ingestion Service
free_crypto_news_client = FreeCryptoNewsClient()
