"""
Position Monitor — Phase D Service

Überwacht offene Positionen und aktualisiert MAE/MFE.
Prüft SL/TP und löst automatische Exits aus.
Läuft als Background Task (alle 30s).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.services.position_tracker import PositionTracker
from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)


class PositionMonitor:
    """
    Background Service für Position-Überwachung.
    
    Tasks:
    1. MAE/MFE Updates für alle offenen Positionen
    2. SL/TP Prüfung und automatische Exits
    3. Redis Health Checks
    """
    
    def __init__(self, position_tracker: PositionTracker, redis: RedisClient):
        self.position_tracker = position_tracker
        self.redis = redis
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Monitoring Parameter
        self.check_interval = 30.0  # 30 Sekunden
        self.symbols = ["BTCUSDT"]  # TODO: Konfigurierbar machen
        
    async def start(self) -> None:
        """Startet den Monitor Background Task."""
        if self._running:
            logger.warning("PositionMonitor läuft bereits")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("PositionMonitor gestartet")
        
    async def stop(self) -> None:
        """Stoppt den Monitor Background Task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PositionMonitor gestoppt")
        
    async def _monitor_loop(self) -> None:
        """Haupt-Loop für Position-Überwachung."""
        while self._running:
            try:
                await self._check_all_positions()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PositionMonitor Loop Fehler: {e}")
                await asyncio.sleep(5)  # Kurz warten bei Fehlern
                
    async def _check_all_positions(self) -> None:
        """Prüft alle konfigurierten Symbole."""
        for symbol in self.symbols:
            try:
                await self._check_symbol(symbol)
            except Exception as e:
                logger.error(f"Fehler bei {symbol}: {e}")
                
    async def _check_symbol(self, symbol: str) -> None:
        """Prüft ein einzelnes Symbol."""
        # 1. Prüfen ob offene Position existiert
        if not await self.position_tracker.has_open_position(symbol):
            return
            
        # 2. Aktuellen Preis holen
        current_price = await self._get_current_price(symbol)
        if current_price is None:
            logger.warning(f"Kein aktueller Preis für {symbol}")
            return
            
        # 3. MAE/MFE aktualisieren
        await self.position_tracker.update_excursions(symbol, current_price)
        
        # 4. SL/TP prüfen
        await self._check_stop_loss_take_profit(symbol, current_price)
        
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Holt den aktuellen Preis aus Redis."""
        try:
            ticker_data = await self.redis.get_cache(f"market:ticker:{symbol}")
            if ticker_data:
                if "last_price" in ticker_data:
                    return float(ticker_data["last_price"])
                if "price" in ticker_data:
                    return float(ticker_data["price"])
                
            # Fallback: Orderbuch Mid-Price
            orderbook = await self.redis.get_cache(f"market:orderbook:{symbol}")
            if orderbook:
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])
                if bids and asks:
                    mid_price = (float(bids[0][0]) + float(asks[0][0])) / 2
                    return mid_price
                    
        except Exception as e:
            logger.error(f"Fehler beim Preis-Holen für {symbol}: {e}")
            
        return None
        
    async def _check_stop_loss_take_profit(self, symbol: str, current_price: float) -> None:
        """Prüft SL/TP und löst Exit aus."""
        position = await self.position_tracker.get_open_position(symbol)
        if not position:
            return
            
        side = position["side"]
        stop_loss = position["stop_loss_price"]
        take_profit_1 = float(position.get("take_profit_1_price", position.get("take_profit_price", 0.0)))
        take_profit_2 = float(position.get("take_profit_2_price", position.get("take_profit_price", 0.0)))
        breakeven_trigger = float(position.get("breakeven_trigger_pct", 0.0))
        
        exit_reason = None

        # TP1 / Scale-out vor dem finalen Exit prüfen
        if not position.get("tp1_hit"):
            entry_price = float(position.get("entry_price", 0.0))
            if entry_price > 0:
                if side == "long":
                    pnl_pct = (current_price - entry_price) / entry_price
                    tp1_hit = current_price >= take_profit_1
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                    tp1_hit = current_price <= take_profit_1

                if tp1_hit and pnl_pct >= breakeven_trigger:
                    scaled = await self.position_tracker.scale_out_position(
                        symbol=symbol,
                        exit_price=current_price,
                        reason="take_profit_1",
                        fraction=float(position.get("tp1_size_pct", 0.5)),
                        move_stop_to_breakeven=True,
                        exit_trade_id=f"tp1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                    )
                    if not scaled:
                        return
                    position = scaled
                    side = position["side"]
                    stop_loss = position["stop_loss_price"]
                    take_profit_2 = float(position.get("take_profit_2_price", take_profit_2))
                    take_profit_1 = float(position.get("take_profit_1_price", take_profit_1))

        if side == "long":
            # Long Position
            if current_price <= stop_loss:
                exit_reason = "stop_loss"
            elif current_price >= take_profit_2:
                exit_reason = "take_profit"
        else:
            # Short Position
            if current_price >= stop_loss:
                exit_reason = "stop_loss"
            elif current_price <= take_profit_2:
                exit_reason = "take_profit"
                
        if exit_reason:
            logger.info(f"Automatischer Exit für {symbol}: {exit_reason} @ {current_price}")
            
            # Position schließen
            await self.position_tracker.close_position(
                symbol=symbol,
                exit_price=current_price,
                reason=exit_reason,
                exit_trade_id=f"auto_{exit_reason}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            
    async def get_monitor_status(self) -> Dict[str, Any]:
        """Gibt Monitor-Status zurück."""
        return {
            "running": self._running,
            "check_interval": self.check_interval,
            "symbols": self.symbols,
            "last_check": datetime.now(timezone.utc).isoformat(),
        }
