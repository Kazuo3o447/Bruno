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
        # Background-Task für Alternative.me F&G Index (Polling)
        asyncio.create_task(self._poll_fg_index())

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
            k = data["k"]
            if k["x"]: # Nur abgeschlossene Kerzen in die DB
                symbol = data["s"]
                candle_data = {
                    "time": datetime.fromtimestamp(k["t"]/1000.0, tz=timezone.utc),
                    "symbol": symbol,
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"])
                }
                self.candle_buffer.append(candle_data)
                # Redis-Live Update
                redis_data = dict(candle_data)
                redis_data["time"] = redis_data["time"].isoformat()
                await self.deps.redis.publish_stream(f"market:kline:{symbol}", redis_data)
        
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

    async def _flush_buffers(self):
        """Schreibt alle gesammelten Daten via Bulk-Insert in PostgreSQL."""
        if not self.candle_buffer and not self.ob_buffer and not self.liq_buffer and not self.funding_buffer:
            return

        async with self.deps.db_session_factory() as session:
            try:
                if self.candle_buffer:
                    stmt = insert(MarketCandle).values(self.candle_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.candle_buffer.clear()
                
                if self.ob_buffer:
                    stmt = insert(OrderbookSnapshot).values(self.ob_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.ob_buffer.clear()
                    
                if self.liq_buffer:
                    stmt = insert(Liquidation).values(self.liq_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.liq_buffer.clear()
                    
                if self.funding_buffer:
                    stmt = insert(FundingRate).values(self.funding_buffer)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['time', 'symbol'])
                    await session.execute(stmt)
                    self.funding_buffer.clear()
                    
                await session.commit()
                self.state.health = "healthy"
            except Exception as e:
                self.state.health = "degraded"
                await self.log_manager.error(
                    category="DATABASE",
                    source=self.agent_id,
                    message=f"Fehler beim DB-Flush: {e}"
                )
                self.logger.error(f"Fehler beim DB-Flush: {e}")
                await session.rollback()
                self.candle_buffer.clear()
                self.ob_buffer.clear()
                self.liq_buffer.clear()
                self.funding_buffer.clear()
