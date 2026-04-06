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

        if getattr(settings, "PAPER_TRADING_ONLY", True):
            self.logger.info("Paper-Trading-Only-Modus aktiv: echte Orders sind gesperrt.")

        if settings.BYBIT_MODE.lower() == "live" and not settings.LIVE_TRADING_APPROVED:
            raise RuntimeError(
                "BYBIT_MODE='live' ist gesperrt. Setze LIVE_TRADING_APPROVED=True "
                "nur nach bestandenem Backtest und expliziter Freigabe."
            )
        
        # Binance mit Keys re-initialisieren
        self.binance = ccxt.binance({
            'apiKey': settings.BINANCE_API_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })

        # Bybit mit Keys re-initialisieren
        bybit_config = self._get_bybit_config()
        if bybit_config:
            self.bybit = ccxt.bybit(bybit_config)

    def _get_bybit_config(self) -> dict:
        """
        Gibt Bybit-Konfiguration basierend auf BYBIT_MODE zurück.
        demo → api-demo.bybit.com (50.000 USDT simuliert)
        live → api.bybit.com (echtes Kapital — NUR nach Backtest)
        """
        mode = getattr(settings, 'BYBIT_MODE', 'demo')
        api_key = getattr(settings, 'BYBIT_API_KEY', None)
        secret = getattr(settings, 'BYBIT_SECRET', None)

        if not api_key or not secret:
            return {}   # Kein Key — ccxt nicht initialisieren

        base_config = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "linear",
                "adjustForTimeDifference": True,
            }
        }

        if mode == "demo":
            base_config["urls"] = {
                "api": {
                    "rest": "https://api-demo.bybit.com"
                }
            }
            self.logger.info("Bybit: DEMO-Modus (api-demo.bybit.com)")
        elif mode == "live":
            # Wird durch LIVE_TRADING_APPROVED Guard in Phase A blockiert
            self.logger.warning("Bybit: LIVE-Modus — nur nach bestandenem Backtest!")

        return base_config

    async def set_leverage(self, symbol: str, leverage: int):
        """Setzt den Leverage auf der Exchange."""
        try:
            # Binance Futures
            if not getattr(settings, "PAPER_TRADING_ONLY", True) and not settings.DRY_RUN:
                await self.binance.set_leverage(leverage, symbol)
                self.logger.info(f"Leverage gesetzt: {symbol} = {leverage}x")
            else:
                self.logger.info(f"Paper Trading: Leverage {leverage}x für {symbol} simuliert")
        except Exception as e:
            self.logger.error(f"Leverage setzen fehlgeschlagen: {e}")

    async def create_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Führt eine Order an der Binance Futures Börse aus."""
        try:
            if getattr(settings, "PAPER_TRADING_ONLY", True):
                raise RuntimeError(
                    "Paper-Trading-Only ist aktiv. Echte Order-Erstellung ist gesperrt."
                )

            if settings.DRY_RUN:
                raise RuntimeError(
                    "DRY_RUN ist aktiv. Echte Order-Erstellung ist gesperrt."
                )

            if price:
                return await self.binance.create_limit_order(symbol, side, amount, price)
            else:
                return await self.binance.create_market_order(symbol, side, amount)
        except Exception as e:
            self.logger.error(f"Order-Fehler: {e}")
            raise


# Singleton-Instanz wird in den Agenten-Dependencies oder direkt initialisiert
