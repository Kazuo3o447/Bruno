"""
CoinGlass API Client — Bruno Trading Bot

Liefert institutionelle Derivate-Daten:
- ETF Net Flows (IBIT, FBTC) — 3-Tages-Aggregat
- Cross-Exchange Funding Divergenz (Binance vs Bybit vs OKX)
- Aggregiertes Open Interest (alle Börsen)

Graceful Degradation:
Wenn COINGLASS_API_KEY fehlt → alle Werte = 0.0 (neutral).
Kein Crash. Kein Exception. Bot läuft weiter.

Aktivierung: COINGLASS_API_KEY in .env eintragen.
Plan: Hobbyist ($29/Monat) — ausreichend für unsere Zwecke.
"""

import httpx
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("coinglass_client")

BASE_URL = "https://open-api.coinglass.com/public/v2"


class CoinGlassClient:

    def __init__(self, api_key: Optional[str], redis_client=None):
        self.api_key = api_key
        self.redis = redis_client
        self._active = bool(api_key)

        if not self._active:
            logger.info(
                "CoinGlass: Kein API-Key — neutraler Platzhalter aktiv. "
                "COINGLASS_API_KEY in .env eintragen um zu aktivieren."
            )

    @property
    def is_active(self) -> bool:
        return self._active

    async def get_etf_flows(self) -> float:
        """
        Bitcoin ETF Net Flows der letzten 3 Tage in Mio. USD.
        Positiv = Inflows (institutionelles Kaufinteresse)
        Negativ = Outflows (institutioneller Rückzug)

        Rückgabe 0.0 wenn kein API-Key.
        """
        if not self._active:
            return 0.0

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BASE_URL}/etf/bitcoin/list",
                    headers={"coinglassSecret": self.api_key}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    etfs = data.get("data", [])

                    # 3-Tages-Aggregat über alle BTC ETFs
                    flows_3d = sum(
                        float(etf.get("flow3Day", 0) or 0)
                        for etf in etfs
                        if etf.get("symbol") in ["IBIT", "FBTC", "ARKB", "BITB"]
                    )

                    latency = (time.perf_counter() - start) * 1000
                    if self.redis:
                        await self.redis.set_cache(
                            "bruno:health:sources",
                            {"CoinGlass_ETF": {
                                "status": "online",
                                "latency_ms": round(latency, 1),
                                "last_update": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                    logger.info(f"ETF Flows 3d: {flows_3d:.1f}M USD")
                    return flows_3d

                else:
                    logger.warning(f"CoinGlass ETF HTTP {resp.status_code}")
                    return 0.0

        except Exception as e:
            logger.warning(f"CoinGlass ETF Fehler: {e}")
            return 0.0

    async def get_funding_divergence(self) -> float:
        """
        Cross-Exchange Funding Rate Divergenz.
        Misst Abweichung zwischen Binance, Bybit und OKX.
        Hohe Divergenz = instabiles Marktumfeld.

        Rückgabe 0.0 wenn kein API-Key.
        """
        if not self._active:
            return 0.0

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BASE_URL}/futures/funding-rates",
                    headers={"coinglassSecret": self.api_key},
                    params={"symbol": "BTC"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("data", [])

                    # Funding Rates der drei größten Börsen
                    exchange_rates = {}
                    for rate_data in rates:
                        exchange = rate_data.get("exchangeName", "")
                        rate = float(rate_data.get("rate", 0) or 0)
                        if exchange in ["Binance", "Bybit", "OKX"]:
                            exchange_rates[exchange] = rate

                    if len(exchange_rates) < 2:
                        return 0.0

                    rates_list = list(exchange_rates.values())
                    divergence = max(rates_list) - min(rates_list)

                    logger.debug(
                        f"Funding Divergence: {divergence:.4%} | "
                        f"Exchanges: {exchange_rates}"
                    )
                    return abs(divergence)

                else:
                    logger.warning(
                        f"CoinGlass Funding HTTP {resp.status_code}"
                    )
                    return 0.0

        except Exception as e:
            logger.warning(f"CoinGlass Funding Fehler: {e}")
            return 0.0

    async def get_aggregated_oi(self) -> float:
        """
        Aggregiertes Open Interest über alle Börsen in Mio. USD.
        Rückgabe 0.0 wenn kein API-Key.
        """
        if not self._active:
            return 0.0

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BASE_URL}/futures/openInterest/chart",
                    headers={"coinglassSecret": self.api_key},
                    params={"symbol": "BTC", "interval": "h1"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    oi_data = data.get("data", {})
                    # Letzter Gesamtwert in USD
                    total_oi = float(
                        oi_data.get("totalOpenInterest", 0) or 0
                    ) / 1_000_000  # → Mio USD
                    return total_oi
                return 0.0

        except Exception as e:
            logger.warning(f"CoinGlass OI Fehler: {e}")
            return 0.0
