"""
On-Chain Data Client — Blockchain.com + Glassnode Free Tier.
Cache: 6 Stunden (On-Chain-Daten ändern sich langsam).
"""
import httpx
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("onchain_client")

class OnChainClient:
    def __init__(self, redis_client, glassnode_api_key: str = None):
        self.redis = redis_client
        self.glassnode_key = glassnode_api_key
        self._last_fetch: float = 0.0
        self._fetch_interval: float = 21600.0  # 6 Stunden
    
    async def update(self) -> Dict:
        now = time.time()
        if now - self._last_fetch < self._fetch_interval:
            cached = await self.redis.get_cache("bruno:onchain:data")
            if cached:
                return cached
        
        result = {}
        
        # Blockchain.com (immer verfügbar)
        result.update(await self._fetch_blockchain_com())
        
        # Glassnode Free (wenn Key vorhanden)
        if self.glassnode_key:
            result.update(await self._fetch_glassnode_free())
        
        if result:
            await self.redis.set_cache("bruno:onchain:data", result, ttl=25200)
            self._last_fetch = now
        
        return result
    
    async def _fetch_blockchain_com(self) -> Dict:
        data = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Hash Rate (7d Trend)
            try:
                r = await client.get(
                    "https://api.blockchain.info/charts/hash-rate",
                    params={"timespan": "7days", "format": "json"}
                )
                if r.status_code == 200:
                    values = r.json().get("values", [])
                    if len(values) >= 2:
                        hr_current = values[-1]["y"]
                        hr_7d_ago = values[0]["y"]
                        data["hash_rate_eh"] = round(hr_current / 1e6, 1)  # EH/s
                        data["hash_rate_7d_change_pct"] = round(
                            (hr_current - hr_7d_ago) / hr_7d_ago * 100, 2)
            except Exception as e:
                logger.warning(f"Blockchain.com Hash Rate Fehler: {e}")
            
            # Mempool Size (Netzwerk-Stress)
            try:
                r = await client.get(
                    "https://api.blockchain.info/charts/mempool-size",
                    params={"timespan": "2days", "format": "json"}
                )
                if r.status_code == 200:
                    values = r.json().get("values", [])
                    if values:
                        data["mempool_bytes"] = values[-1]["y"]
                        # > 100MB = Netzwerk unter Stress
                        data["mempool_stress"] = values[-1]["y"] > 100_000_000
            except Exception as e:
                logger.warning(f"Blockchain.com Mempool Fehler: {e}")
        
        return data
    
    async def _fetch_glassnode_free(self) -> Dict:
        """Glassnode Free Tier: sehr limitiert, aber Exchange Balance ist verfügbar."""
        data = {}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Exchange Balance (BTC auf Exchanges)
                r = await client.get(
                    "https://api.glassnode.com/v1/metrics/distribution/balance_exchanges",
                    params={"a": "BTC", "api_key": self.glassnode_key, "i": "24h"}
                )
                if r.status_code == 200:
                    values = r.json()
                    if len(values) >= 2:
                        current = values[-1]["v"]
                        prev = values[-2]["v"]
                        data["exchange_balance_btc"] = round(current, 0)
                        data["exchange_balance_change_btc"] = round(current - prev, 0)
                        # Negativer Change = BTC werden abgezogen = bullish
                        data["exchange_outflow"] = (current - prev) < 0
                elif r.status_code == 403:
                    logger.info("Glassnode: Free Tier Limit erreicht oder Endpoint nicht verfügbar")
        except Exception as e:
            logger.warning(f"Glassnode Fehler: {e}")
        
        return data
