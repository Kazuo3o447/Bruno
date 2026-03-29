import websockets
import json
import asyncio
import httpx
from typing import Dict, Any, List
from datetime import datetime, timezone
from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.schemas.models import MarketCandle, OrderbookSnapshot, Liquidation, FundingRate
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

class IngestionAgentV2(StreamingAgent):
    """
    Phase 2: Free-Tier Maximum Ingestion.
    Abonniert mehrere Streams via Binance WS Multiplexing.
    Puffert Daten und schreibt sie via Batch-Insert in TimescaleDB.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("ingestion", deps)
        # Streams für BTC/USDT: 1m K-Lines, Orderbook (20 level), Liquidations, Funding Rate
        self.streams = [
            "btcusdt@kline_1m",
            "btcusdt@depth20@100ms",
            "btcusdt@forceOrder",
            "btcusdt@markPrice@1s",
            "btcdomusdt@kline_1m"
        ]
        stream_param = "/".join(self.streams)
        self.ws_url = f"wss://fstream.binance.com/stream?streams={stream_param}"
        
        # Batching Buffer
        self.candle_buffer: List[Dict] = []
        self.ob_buffer: List[Dict] = []
        self.liq_buffer: List[Dict] = []
        self.funding_buffer: List[Dict] = []
        self.last_flush = datetime.now(timezone.utc)
        self.flush_interval = 2.0  # Sekunden

    async def setup(self) -> None:
        self.logger.info("IngestionAgent setup abgeschlossen.")
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message="Ingestion Agent gestartet. Verbinde zu Binance..."
        )
        # Background-Tasks
        asyncio.create_task(self._poll_fg_index())
        asyncio.create_task(self._cleanup_old_data())

    async def _poll_fg_index(self):
        """Pollen des Fear & Greed Index 1x am Tag"""
        while self.state.running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("https://api.alternative.me/fng/")
                    if response.status_code == 200:
                        data = response.json()
                        if data and "data" in data:
                            fng_value = int(data["data"][0]["value"])
                            fng_class = data["data"][0]["value_classification"]
                            await self.deps.redis.set_cache("macro:fear_and_greed", {
                                "value": fng_value,
                                "classification": fng_class,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }, ttl=86400)
                            self.logger.info(f"F&G Index aktualisiert: {fng_value} ({fng_class})")
            except Exception as e:
                self.logger.warning(f"Fehler beim F&G Polling: {e}")
            
            await asyncio.sleep(86400) # 24 Stunden
    async def _cleanup_old_data(self):
        """Löscht alle 24h Daten, die älter als 24h sind, um die DB effizient zu halten."""
        while self.state.running:
            try:
                self.logger.info("Starte Liquidation-Cleanup (24h TTL)...")
                query = text("DELETE FROM liquidations WHERE time < NOW() - INTERVAL '24 hours'")
                async with self.deps.db_session_factory() as session:
                    await session.execute(query)
                    await session.commit()
                self.logger.info("Liquidation-Cleanup erfolgreich abgeschlossen.")
            except Exception as e:
                self.logger.error(f"Fehler beim Liquidation-Cleanup: {e}")
            
            await asyncio.sleep(86400) # Alle 24 Stunden

    async def run_stream(self) -> None:
        async with websockets.connect(self.ws_url) as ws:
            self.state.health = "healthy"
            await self.log_manager.info(
                category="BINANCE",
                source=self.agent_id,
                message=f"Verbunden mit Binance Multiplex: {len(self.streams)} Streams"
            )
            self.logger.info(f"Verbunden mit Binance Multiplex: {len(self.streams)} Streams")
            
            async for message in ws:
                if not self.state.running:
                    break
                
                try:
                    payload = json.loads(message)
                    if "stream" in payload and "data" in payload:
                        stream_name = payload["stream"]
                        data = payload["data"]
                        await self._route_event(stream_name, data)
                        self.state.processed_count += 1
                        
                        # Check Flush Timer
                        now = datetime.now(timezone.utc)
                        if (now - self.last_flush).total_seconds() >= self.flush_interval:
                            await self._flush_buffers()
                            self.last_flush = now
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error in stream routing: {e}")

    async def _route_event(self, stream: str, data: Dict[str, Any]):
        if "@kline" in stream:
            await self._handle_kline(data)
        elif "@depth20" in stream:
            bids = data["b"]
            asks = data["a"]
            bids_vol = sum(float(b[0]) * float(b[1]) for b in bids)
            asks_vol = sum(float(a[0]) * float(a[1]) for a in asks)
            
            ob_data = {
                "time": datetime.now(timezone.utc),
                "symbol": "BTCUSDT",
                "bids_volume_usdt": bids_vol,
                "asks_volume_usdt": asks_vol,
                "imbalance_ratio": bids_vol / asks_vol if asks_vol > 0 else 1.0
            }
            self.ob_buffer.append(ob_data)
            
            redis_ob = dict(ob_data)
            redis_ob["time"] = redis_ob["time"].isoformat()
            await self.deps.redis.set_cache("market:orderbook:BTCUSDT", redis_ob, ttl=5)
            
        elif "@forceOrder" in stream:
            o = data["o"]
            liq_data = {
                "time": datetime.fromtimestamp(o["T"]/1000.0, tz=timezone.utc),
                "symbol": o["s"],
                "side": o["S"],
                "price": float(o["p"]),
                "quantity": float(o["q"]),
                "total_usdt": float(o["p"]) * float(o["q"])
            }
            self.liq_buffer.append(liq_data)
            
            redis_liq = dict(liq_data)
            redis_liq["time"] = redis_liq["time"].isoformat()
            await self.deps.redis.publish_stream(f"market:liquidations:{o['s']}", redis_liq)
            self.logger.info(f"LIQUIDATION: {o['S']} {liq_data['total_usdt']:.2f} USDT")
            
        elif "@markPrice" in stream:
            fund_data = {
                "time": datetime.now(timezone.utc),
                "symbol": data["s"],
                "rate": float(data["r"]),
                "mark_price": float(data["p"])
            }
            self.funding_buffer.append(fund_data)
            
            redis_fund = dict(fund_data)
            redis_fund["time"] = redis_fund["time"].isoformat()
            await self.deps.redis.set_cache(f"market:funding:{data['s']}", redis_fund, ttl=60)

    async def _handle_kline(self, data: Dict[str, Any]) -> None:
        """Verarbeitet 1m K-Line."""
        try:
            kline = data["k"]
            # Wir speichern direkt das Dictionary für den TimescaleDB Bulk-Insert
            candle_data = {
                "time": datetime.fromtimestamp(kline["t"] / 1000, tz=timezone.utc),
                "symbol": kline["s"],
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "close": float(kline["c"]),
                "volume": float(kline["v"])
            }
            self.candle_buffer.append(candle_data)
            
            # Ticker Daten für Dashboard (Redis Cache)
            if candle_data["symbol"] == "BTCUSDT":
                ticker_data = {
                    "symbol": candle_data["symbol"],
                    "last_price": candle_data["close"],
                    "price_change_percent": 0.0, # Wird später berechnet
                    "timestamp": candle_data["time"].isoformat()
                }
                await self.deps.redis.set_cache(f"market:ticker:{candle_data['symbol'].replace('/', '')}", ticker_data)
            
            if len(self.candle_buffer) >= 10:
                await self._flush_buffers()
        except Exception as e:
            self.logger.error(f"Fehler bei K-Line Verarbeitung: {e}")

    async def _flush_buffers(self):
        """Schreibt alle gesammelten Daten via Bulk-Insert in PostgreSQL."""
        if not self.candle_buffer and not self.ob_buffer and not self.liq_buffer and not self.funding_buffer:
            return

        async with self.deps.db_session_factory() as session:
            try:
                # 1. Market Candles (TimescaleDB Hypertable)
                if self.candle_buffer:
                    # Da wir nun direkt Dictionaries puffern, können wir self.candle_buffer direkt nutzen
                    stmt = insert(MarketCandle).values(self.candle_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    
                    # Bevor wir leeren, merken wir uns den letzten Preis für Redis
                    self._last_flush_count = len(self.candle_buffer)
                    latest_candle = self.candle_buffer[-1]
                    self.candle_buffer.clear()
                    
                    # Update Redis with latest ticker data (nach erfolgreichem DB-Flush)
                    ticker_data = {
                        "symbol": latest_candle["symbol"],
                        "last_price": latest_candle["close"],
                        "price_change_percent": 0.0, 
                        "timestamp": latest_candle["time"].isoformat()
                    }
                    await self.deps.redis.set_cache(f"market:ticker:{latest_candle['symbol'].replace('/', '')}", ticker_data)
                
                # 2. Orderbook Snapshots
                if self.ob_buffer:
                    stmt = insert(OrderbookSnapshot).values(self.ob_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.ob_buffer.clear()
                    
                # 3. Liquidations
                if self.liq_buffer:
                    stmt = insert(Liquidation).values(self.liq_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.liq_buffer.clear()
                    
                # 4. Funding Rates
                if self.funding_buffer:
                    stmt = insert(FundingRate).values(self.funding_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.funding_buffer.clear()
                    
                await session.commit()
                
                # Timestamp des letzten erfolgreichen Ingestion-Cycles
                # ContextAgent prüft diesen Wert für den News-Watchdog
                await self.deps.redis.set_cache(
                    "bruno:ingestion:last_message",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "candles": getattr(self, '_last_flush_count', 0)
                    },
                    ttl=7200   # 2 Stunden
                )
                
                self.state.health = "healthy"
                
            except Exception as e:
                self.state.health = "degraded"
                error_msg = f"Fehler beim DB-Flush: {str(e)}"
                await self.log_manager.error(
                    category="DATABASE",
                    source=self.agent_id,
                    message=error_msg
                )
                self.logger.error(error_msg)
                await session.rollback()
                # Buffer leeren, um Endlosschleife bei fehlerhaften Daten zu vermeiden
                self.candle_buffer.clear()
                self.ob_buffer.clear()
                self.liq_buffer.clear()
                self.funding_buffer.clear()
