import httpx
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MarketDataCollector:
    """Marktdaten-Sammler für Bruno Trading Bot.
    
    Holt automatisch alle wichtigen Marktdaten von Binance
    und speichert sie in Redis für die Agenten.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.base_url = "https://api.binance.com"
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def collect_all_data(self, symbol: str = "BTCUSDT"):
        """Sammelt alle Marktdaten und speichert sie in Redis."""
        try:
            # Parallel fetch aller Daten
            tasks = [
                self._fetch_ticker(symbol),
                self._fetch_klines(symbol),
                self._fetch_orderbook(symbol),
                self._fetch_funding_rate(symbol),
                self._fetch_open_interest(symbol),
                self._fetch_liquidations(symbol)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Daten in Redis speichern
            await self._save_to_redis(symbol, results)
            
            logger.info(f"Marktdaten für {symbol} aktualisiert")
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei Datensammlung: {e}")
            return False

    async def _fetch_ticker(self, symbol: str) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/ticker/price?symbol={symbol}")
            response.raise_for_status()
            return {"ticker": response.json()}
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return {"ticker": {}}

    async def _fetch_klines(self, symbol: str, limit: int = 500) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}")
            response.raise_for_status()
            return {"klines": response.json()}
        except Exception as e:
            logger.error(f"Klines fetch error: {e}")
            return {"klines": []}

    async def _fetch_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/depth?symbol={symbol}&limit={limit}")
            response.raise_for_status()
            data = response.json()
            
            # Orderbook Metriken berechnen
            bids_volume = sum(float(bid[0]) * float(bid[1]) for bid in data.get("bids", []))
            asks_volume = sum(float(ask[0]) * float(ask[1]) for ask in data.get("asks", []))
            imbalance_ratio = bids_volume / asks_volume if asks_volume > 0 else 1.0
            
            return {
                "orderbook": data,
                "bids_volume": bids_volume,
                "asks_volume": asks_volume,
                "imbalance_ratio": imbalance_ratio
            }
        except Exception as e:
            logger.error(f"Orderbook fetch error: {e}")
            return {"orderbook": {}, "bids_volume": 0, "asks_volume": 0, "imbalance_ratio": 1.0}

    async def _fetch_funding_rate(self, symbol: str) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/premiumIndex?symbol={symbol}")
            response.raise_for_status()
            return {"funding_rate": response.json()}
        except Exception as e:
            logger.error(f"Funding rate fetch error: {e}")
            return {"funding_rate": {}}

    async def _fetch_open_interest(self, symbol: str) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/openInterest?symbol={symbol}")
            response.raise_for_status()
            return {"open_interest": response.json()}
        except Exception as e:
            logger.error(f"Open interest fetch error: {e}")
            return {"open_interest": {}}

    async def _fetch_liquidations(self, symbol: str, limit: int = 100) -> Dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/allForceOrders?symbol={symbol}&limit={limit}")
            response.raise_for_status()
            return {"liquidations": response.json()}
        except Exception as e:
            logger.error(f"Liquidations fetch error: {e}")
            return {"liquidations": []}

    async def _save_to_redis(self, symbol: str, results: List[Dict]):
        """Speichert alle Daten in Redis."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Einzelne Daten speichern
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Result error: {result}")
                continue
                
            for key, data in result.items():
                redis_key = f"market:{key}:{symbol}"
                
                if key == "ticker":
                    # Ticker mit kurzer TTL
                    await self.redis.set_cache(redis_key, data, ttl=10)
                elif key == "klines":
                    # Klines für Technical Analysis
                    klines_data = {
                        "symbol": symbol,
                        "klines": data,
                        "timestamp": timestamp,
                        "count": len(data)
                    }
                    await self.redis.set_cache(f"bruno:ta:klines:{symbol}", klines_data, ttl=60)
                elif key == "orderbook":
                    # Orderbook Daten
                    ob_data = {
                        "symbol": symbol,
                        "bids": data.get("orderbook", {}).get("bids", []),
                        "asks": data.get("orderbook", {}).get("asks", []),
                        "bids_volume": data.get("bids_volume", 0),
                        "asks_volume": data.get("asks_volume", 0),
                        "imbalance_ratio": data.get("imbalance_ratio", 1.0),
                        "timestamp": timestamp
                    }
                    await self.redis.set_cache(redis_key, ob_data, ttl=5)
                    
                    # OFI Tick für QuantAgent
                    ofi_tick = {
                        "t": timestamp,
                        "r": round(data.get("imbalance_ratio", 1.0), 4)
                    }
                    pipe = self.redis.redis.pipeline()
                    pipe.lpush(f"market:ofi:ticks", str(ofi_tick))
                    pipe.ltrim(f"market:ofi:ticks", 0, 299)
                    await pipe.execute()
                elif key == "funding_rate":
                    # Funding Rate
                    await self.redis.set_cache(redis_key, data, ttl=300)
                elif key == "open_interest":
                    # Open Interest
                    await self.redis.set_cache(redis_key, data, ttl=300)
                elif key == "liquidations":
                    # Liquidations
                    liq_data = {
                        "symbol": symbol,
                        "liquidations": data,
                        "timestamp": timestamp,
                        "count": len(data)
                    }
                    await self.redis.set_cache(f"market:liquidations:{symbol}", liq_data, ttl=60)

        # Zusammengefasste Market Data
        market_snapshot = {
            "symbol": symbol,
            "timestamp": timestamp,
            "ticker": results[0].get("ticker", {}) if not isinstance(results[0], Exception) else {},
            "orderbook_imbalance": results[2].get("imbalance_ratio", 1.0) if not isinstance(results[2], Exception) else 1.0,
            "funding_rate": results[3].get("funding_rate", {}).get("fundingRate", 0) if not isinstance(results[3], Exception) else 0,
            "open_interest": results[4].get("open_interest", {}).get("openInterest", "0") if not isinstance(results[4], Exception) else "0",
            "liquidation_count": len(results[5].get("liquidations", [])) if not isinstance(results[5], Exception) else 0
        }
        
        await self.redis.set_cache(f"market:snapshot:{symbol}", market_snapshot, ttl=30)

    async def health_check(self) -> bool:
        """Prüft ob Binance API erreichbar ist."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/time")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Binance health check failed: {e}")
            return False
