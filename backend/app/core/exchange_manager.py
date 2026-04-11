import asyncio
import logging
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import ccxt.async_support as ccxt
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
    
    PROMPT 04: Bybit Hedge Mode Support mit positionIdx, reduceOnly, orderLinkId
    """
    def __init__(self, redis=None):
        super().__init__(redis)
        self.logger = logging.getLogger("execution_exchange")
        self._position_mode: Optional[str] = None  # "one_way" oder "hedge"

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
    
    async def detect_bybit_position_mode(self) -> str:
        """
        PROMPT 04: Erkennt Bybit Position Mode (One-Way vs Hedge).
        
        Returns:
            str: "one_way" oder "hedge"
        """
        try:
            # ccxt's fetch_accounts oder direkter API call
            # Bybit v5: GET /v5/account/info
            response = await self.bybit.v5_get_account_info()
            
            # Parse response
            result = response.get('result', {})
            margin_mode = result.get('marginMode', 'REGULAR_MARGIN')  # ISOLATED_MARGIN, REGULAR_MARGIN
            unified_status = result.get('unifiedMarginStatus', 1)  # 1=classic, 2=unified, 3=uta2.0
            
            # Hedge Mode Erkennung
            # In Hedge Mode kann man gleichzeitig Long und Short halten
            # unifiedMarginStatus >= 2 unterstützt Hedge Mode
            if unified_status >= 2:
                self._position_mode = "hedge"
                self.logger.info(f"Bybit Position Mode: HEDGE (unifiedMarginStatus={unified_status})")
            else:
                self._position_mode = "one_way"
                self.logger.info(f"Bybit Position Mode: ONE-WAY (unifiedMarginStatus={unified_status})")
            
            # Persistiere in Redis
            if self.redis:
                await self.redis.set_cache(
                    "bruno:bybit:position_mode",
                    {
                        "mode": self._position_mode,
                        "unified_margin_status": unified_status,
                        "margin_mode": margin_mode,
                        "detected_at": datetime.now(timezone.utc).isoformat()
                    }
                )
            
            return self._position_mode
            
        except Exception as e:
            self.logger.warning(f"Konnte Bybit Position Mode nicht erkennen: {e}")
            # Fallback zu One-Way (konservativ)
            self._position_mode = "one_way"
            return self._position_mode
    
    def _get_position_idx(self, side: str, order_type: str = "entry") -> int:
        """
        PROMPT 04: Ermittelt positionIdx für Bybit Hedge Mode.
        
        Args:
            side: "buy" oder "sell"
            order_type: "entry", "close", "sl", "tp"
            
        Returns:
            int: 0=one-way, 1=hedge-long, 2=hedge-short
        """
        if self._position_mode != "hedge":
            return 0  # One-Way Mode
        
        # Hedge Mode: positionIdx basiert auf der Position, nicht auf Order-Seite
        # Long-Position (1) wird mit Buy eröffnet, mit Sell geschlossen
        # Short-Position (2) wird mit Sell eröffnet, mit Buy geschlossen
        
        if order_type in ["close", "sl", "tp"]:
            # Close-Orders: positionIdx der GEGENPOSITION
            # Long schließen = positionIdx 1
            # Short schließen = positionIdx 2
            if side == "sell":
                return 1  # Long-Position schließen
            else:
                return 2  # Short-Position schließen
        else:
            # Entry-Orders: positionIdx der zu eröffnenden Position
            if side == "buy":
                return 1  # Long eröffnen
            else:
                return 2  # Short eröffnen
    
    def _generate_order_link_id(self, slot: str) -> str:
        """
        PROMPT 04: Generiert eindeutige orderLinkId für Idempotenz.
        
        Format: bruno-{slot}-{epoch_ms}-{uuid4[:6]}
        
        Args:
            slot: Strategy slot name (z.B. "trend", "sweep")
            
        Returns:
            str: Eindeutige Order-Link-ID
        """
        epoch_ms = int(time.time() * 1000)
        short_uuid = str(uuid.uuid4())[:6]
        return f"bruno-{slot}-{epoch_ms}-{short_uuid}"
    
    async def _persist_pending_order(self, order_link_id: str, order_data: Dict, ttl: int = 600):
        """
        PROMPT 04: Persistiert pending Order in Redis für Retry-Deduplikation.
        
        Args:
            order_link_id: Eindeutige Order-ID
            order_data: Order-Parameter
            ttl: Time-to-live in Sekunden (default 10 Minuten)
        """
        if not self.redis:
            return
        
        await self.redis.set_cache(
            f"bruno:orders:pending:{order_link_id}",
            {
                "order_link_id": order_link_id,
                "order_data": order_data,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"
            },
            ttl=ttl
        )
    
    async def _get_pending_order(self, order_link_id: str) -> Optional[Dict]:
        """
        PROMPT 04: Holt pending Order aus Redis.
        
        Returns:
            Order-Daten oder None wenn nicht gefunden
        """
        if not self.redis:
            return None
        
        return await self.redis.get_cache(f"bruno:orders:pending:{order_link_id}")

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

    async def create_bybit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        slot: str = "default",
        order_type: str = "entry",
        reduce_only: bool = False
    ) -> Dict:
        """
        PROMPT 04: Erstellt eine Bybit Order mit Hedge Mode Support.
        
        Args:
            symbol: Trading-Pair (z.B. "BTCUSDT")
            side: "buy" oder "sell"
            amount: Order-Größe
            price: Limit-Preis (None für Market Order)
            slot: Strategy slot für orderLinkId
            order_type: "entry", "close", "sl", "tp"
            reduce_only: True für SL/TP/Close Orders
            
        Returns:
            Order-Response von Bybit
        """
        try:
            if getattr(settings, "PAPER_TRADING_ONLY", True):
                raise RuntimeError(
                    "Paper-Trading-Only ist aktiv. Echte Order-Erstellung ist gesperrt."
                )

            if settings.DRY_RUN:
                raise RuntimeError(
                    "DRY_RUN ist aktiv. Echte Order-Erstellung ist gesperrt."
                )
            
            # Stelle sicher dass Position Mode bekannt ist
            if self._position_mode is None:
                await self.detect_bybit_position_mode()
            
            # Generiere orderLinkId für Idempotenz
            order_link_id = self._generate_order_link_id(slot)
            
            # Ermittle positionIdx
            position_idx = self._get_position_idx(side, order_type)
            
            # Order-Parameter
            order_params = {
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'type': 'limit' if price else 'market',
            }
            
            # Bybit-spezifische Parameter
            params = {
                'orderLinkId': order_link_id,
                'positionIdx': position_idx,
            }
            
            # reduceOnly für SL/TP/Close
            if reduce_only:
                params['reduceOnly'] = True
            
            if price:
                order_params['price'] = price
            
            # Persistiere pending Order für Retry-Deduplikation
            await self._persist_pending_order(
                order_link_id,
                {
                    'symbol': symbol,
                    'side': side,
                    'amount': amount,
                    'price': price,
                    'slot': slot,
                    'order_type': order_type,
                    'reduce_only': reduce_only,
                    'position_idx': position_idx,
                }
            )
            
            # Erstelle Order
            result = await self.bybit.create_order(**order_params, params=params)
            
            self.logger.info(
                f"Bybit Order erstellt: {symbol} {side} {amount} | "
                f"positionIdx={position_idx}, reduceOnly={reduce_only}, "
                f"orderLinkId={order_link_id}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bybit Order-Fehler: {e}")
            raise
    
    async def create_bybit_sl_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        trigger_price: float,
        slot: str = "default"
    ) -> Dict:
        """
        PROMPT 04: Erstellt eine Bybit Stop-Loss Order (Conditional Order).
        
        Args:
            symbol: Trading-Pair
            side: "buy" oder "sell" (Gegenseite der Position)
            amount: Order-Größe
            trigger_price: SL-Trigger-Preis
            slot: Strategy slot
            
        Returns:
            Conditional Order Response
        """
        try:
            if getattr(settings, "PAPER_TRADING_ONLY", True):
                raise RuntimeError("Paper-Trading-Only ist aktiv.")
            if settings.DRY_RUN:
                raise RuntimeError("DRY_RUN ist aktiv.")
            
            if self._position_mode is None:
                await self.detect_bybit_position_mode()
            
            order_link_id = self._generate_order_link_id(f"{slot}-sl")
            position_idx = self._get_position_idx(side, "sl")
            
            params = {
                'orderLinkId': order_link_id,
                'positionIdx': position_idx,
                'reduceOnly': True,
                'triggerPrice': trigger_price,
            }
            
            await self._persist_pending_order(order_link_id, {
                'symbol': symbol, 'side': side, 'amount': amount,
                'trigger_price': trigger_price, 'slot': slot,
                'order_type': 'sl', 'reduce_only': True,
            })
            
            # Conditional Order für SL
            result = await self.bybit.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params={
                    **params,
                    'stopLossPrice': trigger_price,
                }
            )
            
            self.logger.info(
                f"Bybit SL Order: {symbol} {side} @ {trigger_price} | "
                f"positionIdx={position_idx}, orderLinkId={order_link_id}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bybit SL Order-Fehler: {e}")
            raise
    
    async def create_bybit_tp_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        trigger_price: float,
        slot: str = "default"
    ) -> Dict:
        """
        PROMPT 04: Erstellt eine Bybit Take-Profit Order (Conditional Order).
        
        Args:
            symbol: Trading-Pair
            side: "buy" oder "sell" (Gegenseite der Position)
            amount: Order-Größe
            trigger_price: TP-Trigger-Preis
            slot: Strategy slot
            
        Returns:
            Conditional Order Response
        """
        try:
            if getattr(settings, "PAPER_TRADING_ONLY", True):
                raise RuntimeError("Paper-Trading-Only ist aktiv.")
            if settings.DRY_RUN:
                raise RuntimeError("DRY_RUN ist aktiv.")
            
            if self._position_mode is None:
                await self.detect_bybit_position_mode()
            
            order_link_id = self._generate_order_link_id(f"{slot}-tp")
            position_idx = self._get_position_idx(side, "tp")
            
            params = {
                'orderLinkId': order_link_id,
                'positionIdx': position_idx,
                'reduceOnly': True,
            }
            
            await self._persist_pending_order(order_link_id, {
                'symbol': symbol, 'side': side, 'amount': amount,
                'trigger_price': trigger_price, 'slot': slot,
                'order_type': 'tp', 'reduce_only': True,
            })
            
            # Conditional Order für TP
            result = await self.bybit.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params={
                    **params,
                    'takeProfitPrice': trigger_price,
                }
            )
            
            self.logger.info(
                f"Bybit TP Order: {symbol} {side} @ {trigger_price} | "
                f"positionIdx={position_idx}, orderLinkId={order_link_id}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Bybit TP Order-Fehler: {e}")
            raise
    
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
