import asyncio
import logging
import json
import time
import ccxt.async_support as ccxt
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.core.config import settings

class PublicExchangeClient:
    """
    Stellt öffentliche Marktdaten bereit (Orderbuch, Trades).
    Keine API-Keys erforderlich. Sicher für Quant & Context Agenten.
    """
    def __init__(self, redis=None):
        self.logger = logging.getLogger("public_exchange")
        self.redis = redis
        
        # Nur öffentliche Endpunkte
        self.binance = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        self.bybit = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'}
        })

    async def close(self):
        await self.binance.close()
        await self.bybit.close()

    async def _report_health(self, source: str, status: str, latency: float):
        if not self.redis: return
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.redis.set_cache("bruno:health:sources", current_map)

    async def fetch_order_book_redundant(self, symbol: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        start_time = time.perf_counter()
        try:
            async with asyncio.timeout(2.0):
                ob = await self.binance.fetch_order_book(symbol, limit=limit)
                latency = (time.perf_counter() - start_time) * 1000
                await self._report_health("Binance_OB", "online", latency)
                ob['source'] = 'binance'
                ob['latency_ms'] = latency
                return ob
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            self.logger.warning(f"Binance OB-Fehler ({latency:.0f}ms): {e}")
            await self._report_health("Binance_OB", "offline", latency)
            
            start_fallback = time.perf_counter()
            try:
                ob = await self.bybit.fetch_order_book(symbol, limit=limit)
                latency_fb = (time.perf_counter() - start_fallback) * 1000
                await self._report_health("Bybit_OB", "online", latency_fb)
                ob['source'] = 'bybit'
                ob['latency_ms'] = latency_fb
                return ob
            except Exception:
                await self._report_health("Bybit_OB", "offline", 0)
                return None

class AuthenticatedExchangeClient(PublicExchangeClient):
    """
    Erweiterte Engine für den ExecutionAgent.
    Bedarf API-Keys für Order-Management.
    """
    def __init__(self, redis=None):
        super().__init__(redis)
        self.logger = logging.getLogger("execution_exchange")
        
        # Binance mit Keys re-initialisieren
        self.binance = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })

    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Führt eine Order an der Binance Futures Börse aus."""
        try:
            if price:
                return await self.binance.create_limit_order(symbol, side, amount, price)
            else:
                return await self.binance.create_market_order(symbol, side, amount)
        except Exception as e:
            self.logger.error(f"Order-Fehler: {e}")
            raise


# Singleton-Instanz wird in den Agenten-Dependencies oder direkt initialisiert
