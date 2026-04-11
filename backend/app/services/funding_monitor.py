"""
PROMPT 05: Funding Rate Monitor Service.

Pollt Bybit /v5/market/funding/history alle 60s.
Persistiert Funding-Daten in Redis für Composite Scorer.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from statistics import mean


class FundingMonitor:
    """
    Monitoring-Service für BTC Perpetual Funding Rates.
    
    Best Practice: Funding-aware Trading für BTC Perp.
    - Typisch: 0.01% pro 8h
    - Trends: bis zu 0.05%+
    - 24h-Hold gegen Funding kostet ~0.15%
    """
    
    def __init__(self, redis_client, exchange_client):
        self.redis = redis_client
        self.exchange = exchange_client
        self.logger = logging.getLogger("funding_monitor")
        self.symbol = "BTCUSDT"
        self.poll_interval = 60  # Sekunden
        self._running = False
        self._task = None
    
    async def start(self):
        """Startet den Funding Monitor Loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.logger.info("PROMPT 05: FundingMonitor gestartet (60s Intervall)")
    
    async def stop(self):
        """Stoppt den Funding Monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("FundingMonitor gestoppt")
    
    async def _monitor_loop(self):
        """Haupt-Loop: Pollt Funding-Daten alle 60s."""
        while self._running:
            try:
                await self._fetch_and_persist_funding()
            except Exception as e:
                self.logger.error(f"Funding fetch error: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    async def _fetch_and_persist_funding(self):
        """
        Holt Funding-Daten von Bybit und persistiert in Redis.
        
        Redis Keys:
        - market:funding:current → Aktueller Funding Rate
        - market:funding:predicted_next → Vorhergesagter nächster Funding
        - market:funding:8h_avg → 8h Durchschnitt
        - market:funding:24h_avg → 24h Durchschnitt
        """
        try:
            # Bybit v5: GET /v5/market/funding/history
            # Letzte 3 Perioden (24h) für Durchschnittsberechnung
            since = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000)
            
            response = await self.exchange.bybit.v5_get_market_funding_history(
                category="linear",
                symbol=self.symbol,
                limit=3,  # Letzte 3 Perioden (24h)
            )
            
            if not response or 'result' not in response:
                self.logger.warning("Keine Funding-Daten von Bybit")
                return
            
            funding_list = response['result'].get('list', [])
            if not funding_list:
                return
            
            # Aktuellster Funding Rate
            current_funding = funding_list[0]
            funding_rate = float(current_funding.get('fundingRate', 0))
            
            # Vorhergesagter nächster Funding (wenn verfügbar)
            predicted_next = None
            if len(funding_list) > 0:
                # Bybit gibt manchmal predictedFundingRate zurück
                predicted_next = current_funding.get('predictedFundingRate')
                if predicted_next:
                    predicted_next = float(predicted_next)
            
            # 8h und 24h Durchschnitte
            funding_rates = [float(f.get('fundingRate', 0)) for f in funding_list]
            avg_8h = funding_rates[0] if funding_rates else 0
            avg_24h = mean(funding_rates) if funding_rates else 0
            
            # Konvertiere zu Basis-Punkten (bps) für einfacheres Debugging
            # 0.0001 = 10 bps = 0.01%
            funding_bps = funding_rate * 10000  # Basis-Punkten
            
            # Persistiere in Redis
            now = datetime.now(timezone.utc).isoformat()
            
            await self.redis.set_cache("market:funding:current", {
                "funding_rate": funding_rate,
                "funding_bps": round(funding_bps, 2),
                "timestamp": current_funding.get('fundingRateTimestamp'),
                "updated_at": now,
            })
            
            await self.redis.set_cache("market:funding:8h_avg", {
                "avg_rate": avg_8h,
                "avg_bps": round(avg_8h * 10000, 2),
                "periods": len(funding_rates),
                "updated_at": now,
            })
            
            await self.redis.set_cache("market:funding:24h_avg", {
                "avg_rate": avg_24h,
                "avg_bps": round(avg_24h * 10000, 2),
                "periods": len(funding_rates),
                "updated_at": now,
            })
            
            if predicted_next is not None:
                await self.redis.set_cache("market:funding:predicted_next", {
                    "predicted_rate": predicted_next,
                    "predicted_bps": round(predicted_next * 10000, 2),
                    "updated_at": now,
                })
            
            self.logger.debug(
                f"Funding updated: {funding_rate:.4%} ({funding_bps:.1f} bps) | "
                f"24h avg: {avg_24h:.4%} | Predicted: {predicted_next:.4% if predicted_next else 'N/A'}"
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching funding: {e}")
            raise
    
    async def get_current_funding(self) -> Optional[Dict[str, Any]]:
        """Holt aktuellen Funding Rate aus Redis."""
        return await self.redis.get_cache("market:funding:current")
    
    async def get_funding_score_params(self) -> Dict[str, float]:
        """
        Gibt Parameter für Funding Score Berechnung.
        
        Returns:
            Dict mit funding_rate, avg_8h, avg_24h, predicted_next
        """
        current = await self.redis.get_cache("market:funding:current") or {}
        avg_8h = await self.redis.get_cache("market:funding:8h_avg") or {}
        avg_24h = await self.redis.get_cache("market:funding:24h_avg") or {}
        predicted = await self.redis.get_cache("market:funding:predicted_next") or {}
        
        return {
            "funding_rate": current.get("funding_rate", 0),
            "funding_bps": current.get("funding_bps", 0),
            "avg_8h": avg_8h.get("avg_rate", 0),
            "avg_24h": avg_24h.get("avg_rate", 0),
            "predicted_next": predicted.get("predicted_rate"),
        }


# Singleton-Instanz für den Worker
_funding_monitor: Optional[FundingMonitor] = None


def get_funding_monitor(redis_client, exchange_client) -> FundingMonitor:
    """Gibt Singleton-Instanz des FundingMonitor zurück."""
    global _funding_monitor
    if _funding_monitor is None:
        _funding_monitor = FundingMonitor(redis_client, exchange_client)
    return _funding_monitor
