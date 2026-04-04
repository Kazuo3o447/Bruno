import httpx
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)


class BinanceDataClient:
    """Binance API Client für alle Marktdaten.
    
    Holt Klines, Orderbook, Ticker und andere Marktdaten von Binance.
    Keine API Keys erforderlich für öffentliche Endpunkte.
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.ws_url = "wss://fstream.binance.com"
        self.timeout = 30.0
        
        # HTTP Client mit Connection Pooling
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Erstellt oder gibt den HTTP Client zurück."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        """Schließt den HTTP Client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt aktuellen Ticker."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/ticker/price?symbol={symbol}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return {}

    async def get_24hr_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt 24h Ticker Statistiken."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/ticker/24hr?symbol={symbol}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"24hr ticker fetch error: {e}")
            return {}

    async def get_klines(self, symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500) -> List[List]:
        """Holt Kline Daten."""
        try:
            client = await self._get_client()
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            response = await client.get(f"{self.base_url}/api/v3/klines", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Klines fetch error: {e}")
            return []

    async def get_orderbook(self, symbol: str = "BTCUSDT", limit: int = 100) -> Dict[str, Any]:
        """Holt Orderbuch."""
        try:
            client = await self._get_client()
            params = {"symbol": symbol, "limit": limit}
            response = await client.get(f"{self.base_url}/api/v3/depth", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Orderbook fetch error: {e}")
            return {}

    async def get_recent_trades(self, symbol: str = "BTCUSDT", limit: int = 500) -> List[Dict]:
        """Holt letzte Trades."""
        try:
            client = await self._get_client()
            params = {"symbol": symbol, "limit": limit}
            response = await client.get(f"{self.base_url}/api/v3/trades", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Recent trades fetch error: {e}")
            return []

    async def get_server_time(self) -> Dict[str, Any]:
        """Holt Binance Server Zeit."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/time")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Server time fetch error: {e}")
            return {}

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Holt Exchange Informationen."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/exchangeInfo")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Exchange info fetch error: {e}")
            return {}

    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt Funding Rate (Futures)."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/premiumIndex?symbol={symbol}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Funding rate fetch error: {e}")
            return {}

    async def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt Open Interest (Futures)."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/openInterest?symbol={symbol}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Open interest fetch error: {e}")
            return {}

    async def get_mark_price(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt Mark Price (Futures)."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/markPrice?symbol={symbol}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Mark price fetch error: {e}")
            return {}

    async def get_liquidation_orders(self, symbol: str = "BTCUSDT", limit: int = 100) -> List[Dict]:
        """Holt Liquidation Orders (Futures)."""
        try:
            client = await self._get_client()
            params = {"symbol": symbol, "limit": limit}
            response = await client.get(f"{self.base_url}/fapi/v1/allForceOrders", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Liquidation orders fetch error: {e}")
            return []

    async def get_comprehensive_market_data(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Holt alle wichtigen Marktdaten auf einmal."""
        try:
            # Parallel fetch aller wichtigen Daten
            tasks = [
                self.get_ticker(symbol),
                self.get_24hr_ticker(symbol),
                self.get_klines(symbol, "1m", 500),
                self.get_orderbook(symbol, 100),
                self.get_funding_rate(symbol),
                self.get_open_interest(symbol),
                self.get_mark_price(symbol),
                self.get_liquidation_orders(symbol, 50)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "ticker": results[0] if not isinstance(results[0], Exception) else {},
                "ticker_24h": results[1] if not isinstance(results[1], Exception) else {},
                "klines": results[2] if not isinstance(results[2], Exception) else [],
                "orderbook": results[3] if not isinstance(results[3], Exception) else {},
                "funding_rate": results[4] if not isinstance(results[4], Exception) else {},
                "open_interest": results[5] if not isinstance(results[5], Exception) else {},
                "mark_price": results[6] if not isinstance(results[6], Exception) else {},
                "liquidations": results[7] if not isinstance(results[7], Exception) else [],
                "errors": [str(r) for r in results if isinstance(r, Exception)]
            }
        except Exception as e:
            logger.error(f"Comprehensive market data fetch error: {e}")
            return {"timestamp": datetime.now(timezone.utc).isoformat(), "error": str(e)}

    async def health_check(self) -> bool:
        """Prüft ob Binance API erreichbar ist."""
        try:
            server_time = await self.get_server_time()
            return bool(server_time.get("serverTime"))
        except Exception as e:
            logger.error(f"Binance health check failed: {e}")
            return False


# Singleton-Instanz
binance_client = BinanceDataClient()
