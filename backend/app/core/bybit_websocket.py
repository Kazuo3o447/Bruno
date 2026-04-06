"""
Bybit V5 WebSocket Client für Bruno Trading Bot

Primärquelle für Echtzeit-Marktdaten:
- Kline.1.BTCUSDT (1-Minute Candles)
- publicTrade.BTCUSDT (CVD Berechnung)
- orderbook.50.BTCUSDT (Orderbuch-Daten)
- Heartbeat-Monitoring mit Binance-Fallback
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Deque
from collections import deque
import aiohttp
import websockets
from datetime import datetime, timezone

logger = logging.getLogger("bybit_websocket")


class BybitWebSocketClient:
    """Bybit V5 WebSocket Client mit Heartbeat-Monitoring und Fallback-Logic."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        self.websocket = None
        self.connected = False
        self.last_heartbeat = None
        self.heartbeat_timeout = 5.0  # 5 Sekunden Timeout
        
        # CVD Berechnung
        self.cvd_value = 0.0
        self.last_trade_ids: Deque[str] = deque(maxlen=200)  # Deduplizierung
        
        # Binance Fallback
        self.use_fallback = False
        self.fallback_reason = ""
        
    async def connect(self):
        """Stellt Verbindung zum Bybit V5 WebSocket her."""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            self.last_heartbeat = datetime.now(timezone.utc)
            
            # Subscribe to required streams
            subscribe_message = {
                "op": "subscribe",
                "args": [
                    "kline.1.BTCUSDT",
                    "publicTrade.BTCUSDT", 
                    "orderbook.50.BTCUSDT"
                ]
            }
            
            await self.websocket.send(json.dumps(subscribe_message))
            logger.info("Bybit V5 WebSocket verbunden und subscribed")
            
            # Starte Listener und Heartbeat Monitor
            asyncio.create_task(self._listen())
            asyncio.create_task(self._heartbeat_monitor())
            
        except Exception as e:
            logger.error(f"Bybit WebSocket Verbindung fehlgeschlagen: {e}")
            await self._activate_fallback("Verbindungsfehler")
    
    async def _listen(self):
        """Hört auf eingehende WebSocket Nachrichten."""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
                self.last_heartbeat = datetime.now(timezone.utc)
                
        except websockets.exceptions.ConnectionClosed:
            logger.error("Bybit WebSocket Verbindung geschlossen")
            await self._activate_fallback("Verbindung geschlossen")
        except Exception as e:
            logger.error(f"Bybit WebSocket Listen-Fehler: {e}")
            await self._activate_fallback("Listen-Fehler")
    
    async def _handle_message(self, message: str):
        """Verarbeitet eingehende WebSocket Nachrichten."""
        try:
            data = json.loads(message)
            
            if "topic" in data:
                topic = data["topic"]
                
                if topic == "publicTrade.BTCUSDT":
                    await self._handle_public_trade(data)
                elif topic.startswith("kline"):
                    await self._handle_kline(data)
                elif topic.startswith("orderbook"):
                    await self._handle_orderbook(data)
                elif topic == "pong":
                    # Heartbeat response
                    pass
                    
        except Exception as e:
            logger.error(f"Fehler bei Nachrichtenverarbeitung: {e}")
    
    async def _handle_public_trade(self, data: Dict[str, Any]):
        """
        Verarbeitet Trade-Daten für institutionelle CVD-Berechnung.
        
        MATHEMATIK (Bybit V5):
        - side == "Buy" → Taker Buy (Aggressives Kaufvolumen)
        - side == "Sell" → Taker Sell (Aggressives Verkaufvolumen)
        - CVD = Summe(Taker_Buy_Vol) - Summe(Taker_Sell_Vol)
        
        DEDUPLIZIERUNG:
        - Bybit execId als Guard
        - deque mit letzten 200 execIds
        """
        try:
            trades = data.get("data", [])
            
            for trade in trades:
                trade_id = trade.get("execId")
                
                # Deduplizierung
                if trade_id in self.last_trade_ids:
                    continue
                
                self.last_trade_ids.append(trade_id)
                
                # INSTITUTIONELLE CVD-BERECHNUNG MIT SIDE-HANDLING
                side = trade.get("side", "")
                price = float(trade.get("price", 0))
                size = float(trade.get("size", 0))
                
                if side == "Buy":
                    # Taker Buy: Aggressives Kaufvolumen (Market Buy Order)
                    self.cvd_value += size
                    logger.debug(f"CVD +{size:.4f} (Buy) | execId={trade_id[:12]}...")
                elif side == "Sell":
                    # Taker Sell: Aggressives Verkaufvolumen (Market Sell Order)
                    self.cvd_value -= size
                    logger.debug(f"CVD -{size:.4f} (Sell) | execId={trade_id[:12]}...")
                else:
                    # Unbekannte side ignorieren
                    logger.warning(f"Unbekannte side: {side} | execId={trade_id}")
                    continue
                
                # CVD in Redis speichern (QuantAgent liest von hier)
                await self.redis.redis.set("market:cvd:cumulative", str(self.cvd_value))
                await self.redis.set_cache(
                    "bruno:cvd:BTCUSDT",
                    {
                        "value": self.cvd_value,
                        "last_processed_ts": int(datetime.now(timezone.utc).timestamp()),
                        "last_processed_exec_id": trade_id,
                        "side": side,
                        "volume": size,
                        "price": price,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    ttl=86400
                )
                await self.redis.redis.set("bybit:last_trade_time", datetime.now(timezone.utc).isoformat())
                
        except Exception as e:
            logger.error(f"Fehler bei Trade-Verarbeitung: {e}")
    
    async def _handle_kline(self, data: Dict[str, Any]):
        """Verarbeitet Kline/Candle-Daten für Technical Analysis."""
        try:
            kline_data = data.get("data", [])
            if not kline_data:
                return
            
            kline = kline_data[0] if isinstance(kline_data, list) else kline_data
            
            kline_obj = {
                "symbol": "BTCUSDT",
                "open": float(kline.get("open", 0)),
                "high": float(kline.get("high", 0)),
                "low": float(kline.get("low", 0)),
                "close": float(kline.get("close", 0)),
                "volume": float(kline.get("volume", 0)),
                "timestamp": int(kline.get("start", 0)),
                "confirm": kline.get("confirm", False)
            }
            
            # In Redis speichern für TA Engine
            await self.redis.set_cache(
                "bruno:ta:klines:BTCUSDT",
                {"klines": [kline_obj], "timestamp": datetime.now(timezone.utc).isoformat()},
                ttl=60
            )
            
        except Exception as e:
            logger.error(f"Fehler bei Kline-Verarbeitung: {e}")
    
    async def _handle_orderbook(self, data: Dict[str, Any]):
        """Verarbeitet Orderbuch-Daten für OFI-Berechnung."""
        try:
            ob_data = data.get("data", {})
            if not ob_data:
                return
            
            bids = ob_data.get("b", [])  # Bids [price, size]
            asks = ob_data.get("a", [])  # Asks [price, size]
            
            # Formatieren für Redis
            formatted_bids = [[float(p), float(s)] for p, s in bids[:50]]
            formatted_asks = [[float(p), float(s)] for p, s in asks[:50]]
            
            # Orderbook-Metriken berechnen
            bids_volume = sum(p * s for p, s in formatted_bids)
            asks_volume = sum(p * s for p, s in formatted_asks)
            imbalance_ratio = bids_volume / asks_volume if asks_volume > 0 else 1.0
            
            ob_obj = {
                "symbol": "BTCUSDT",
                "bids": formatted_bids,
                "asks": formatted_asks,
                "bids_volume": bids_volume,
                "asks_volume": asks_volume,
                "imbalance_ratio": imbalance_ratio,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.redis.set_cache(
                "market:orderbook:BTCUSDT",
                ob_obj,
                ttl=5
            )
            
            # OFI Tick für QuantAgent
            ofi_tick = {
                "t": datetime.now(timezone.utc).isoformat(),
                "r": round(imbalance_ratio, 4)
            }
            pipe = self.redis.redis.pipeline()
            pipe.lpush("market:ofi:ticks", str(ofi_tick))
            pipe.ltrim("market:ofi:ticks", 0, 299)
            await pipe.execute()
                
        except Exception as e:
            logger.error(f"Fehler bei Orderbook-Verarbeitung: {e}")
    
    async def _heartbeat_monitor(self):
        """Überwacht WebSocket Verbindung und aktiviert Fallback bei Timeout."""
        while True:
            await asyncio.sleep(1)
            
            if self.last_heartbeat and not self.use_fallback:
                timeout = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
                
                if timeout > self.heartbeat_timeout:
                    logger.warning(f"Bybit Heartbeat Timeout ({timeout:.1f}s) - Aktiviere Fallback")
                    await self._activate_fallback("Heartbeat Timeout")
    
    async def _activate_fallback(self, reason: str):
        """Aktiviert Binance Fallback Mode."""
        if not self.use_fallback:
            self.use_fallback = True
            self.fallback_reason = reason
            logger.warning(f"Bybit Fallback aktiviert: {reason}")
            
            # Setze Fallback Flag in Redis
            await self.redis.redis.set("market:data_source", "binance_fallback")
            await self.redis.redis.set("market:fallback_reason", reason)
    
    async def _deactivate_fallback(self):
        """Deaktiviert Fallback Mode."""
        if self.use_fallback:
            self.use_fallback = False
            self.fallback_reason = ""
            logger.info("Bybit Fallback deaktiviert")
            
            # Entferne Fallback Flag
            await self.redis.redis.delete("market:data_source")
            await self.redis.redis.delete("market:fallback_reason")
    
    async def close(self):
        """Schließt WebSocket Verbindung."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Bybit WebSocket verbindung geschlossen")


# Singleton Instance
_bybit_websocket = None

def get_bybit_websocket(redis_client) -> BybitWebSocketClient:
    """Gibt die Bybit WebSocket Instance zurück."""
    global _bybit_websocket
    if _bybit_websocket is None:
        _bybit_websocket = BybitWebSocketClient(redis_client)
    return _bybit_websocket