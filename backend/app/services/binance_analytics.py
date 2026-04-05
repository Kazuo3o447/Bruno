"""
Binance Analytics Service — Free-Tier Datenquellen die kein API-Key brauchen.
Sammelt: Top Trader Ratio, Taker Buy/Sell Volume, Global L/S Ratio.
"""
import httpx
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("binance_analytics")

class BinanceAnalyticsService:
    BASE = "https://fapi.binance.com/futures/data"
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self._last_fetch: float = 0.0
        self._fetch_interval: float = 300.0  # 5 Minuten
    
    async def update(self) -> Dict:
        """Holt alle Analytics-Daten in einem Batch."""
        now = time.time()
        if now - self._last_fetch < self._fetch_interval:
            cached = await self.redis.get_cache("bruno:binance:analytics")
            if cached:
                return cached
        
        result = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Top Trader Position Ratio
            try:
                r = await client.get(f"{self.BASE}/topLongShortPositionRatio",
                    params={"symbol": "BTCUSDT", "period": "1h", "limit": 1})
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        result["top_trader_long_ratio"] = float(data[-1]["longAccount"])
                        result["top_trader_short_ratio"] = float(data[-1]["shortAccount"])
                        result["top_trader_ls_ratio"] = float(data[-1]["longShortRatio"])
            except Exception as e:
                logger.warning(f"Top Trader Ratio Fehler: {e}")
            
            # 2. Taker Buy/Sell Volume Ratio
            try:
                r = await client.get(f"{self.BASE}/takerlongshortRatio",
                    params={"symbol": "BTCUSDT", "period": "1h", "limit": 1})
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        result["taker_buy_vol"] = float(data[-1]["buyVol"])
                        result["taker_sell_vol"] = float(data[-1]["sellVol"])
                        result["taker_buy_sell_ratio"] = float(data[-1]["buySellRatio"])
            except Exception as e:
                logger.warning(f"Taker Volume Fehler: {e}")
            
            # 3. Global Long/Short Account Ratio (für context.py long_short_ratio)
            try:
                r = await client.get(f"{self.BASE}/globalLongShortAccountRatio",
                    params={"symbol": "BTCUSDT", "period": "1h", "limit": 1})
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        result["global_ls_ratio"] = float(data[-1]["longShortRatio"])
            except Exception as e:
                logger.warning(f"Global L/S Ratio Fehler: {e}")
        
        if result:
            await self.redis.set_cache("bruno:binance:analytics", result, ttl=600)
            self._last_fetch = now
        
        return result
