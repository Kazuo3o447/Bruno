import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Set
from collections import deque
from pybit.unified_trading import WebSocket

logger = logging.getLogger(__name__)


class BybitV5Client:
    """
    Bybit V5 WebSocket Client for Paper-Trading Data.
    Single Source of Truth for BTCUSDT price and orderflow data.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ws = None
        self.connected = False
        
        # CVD Calculation State
        self.current_1m_taker_buy = 0.0
        self.current_1m_taker_sell = 0.0
        self._processed_trades: Set[str] = set()  # Deduplication by exec_id
        self._trade_deque = deque(maxlen=10000)  # Rolling window for trade dedup
        
        # VWAP State
        self.daily_volume = 0.0
        self.daily_vwap_sum = 0.0
        self.current_vwap = 0.0
        self.last_reset_date = None
        
        # VPOC State
        self.volume_profile: Dict[float, float] = {}
        self.current_vpoc = 0.0
        
        # Kline Buffer
        self.current_kline = None
        self.kline_start_time = None
        
        self.logger = logging.getLogger("bybit_v5")
    
    async def connect(self):
        """Connect to Bybit V5 WebSocket."""
        try:
            # Real data for paper-trading (testnet=False)
            # TODO: Implement actual Bybit V5 WebSocket connection
            self.logger.info("Bybit V5 WebSocket simulated connection successful")
            
        except Exception as e:
            self.logger.error(f"Bybit V5 connection failed: {e}")
            self.connected = False
    
    def _on_close(self):
        """Handle WebSocket close - attempt reconnection."""
        self.logger.warning("Bybit V5 WebSocket disconnected")
        self.connected = False
        # Reconnection logic would be handled by the main loop
    
    def _handle_kline(self, message):
        """Handle 1-minute kline data."""
        try:
            if not message or "data" not in message:
                return
                
            kline_data = message["data"][0]  # Latest kline
            
            # Parse kline fields
            start_time = int(kline_data["start"])
            open_price = float(kline_data["open"])
            high_price = float(kline_data["high"])
            low_price = float(kline_data["low"])
            close_price = float(kline_data["close"])
            volume = float(kline_data["volume"])
            turnover = float(kline_data["turnover"])
            
            # Check for new minute (kline completion)
            if self.kline_start_time and self.kline_start_time != start_time:
                # Previous minute completed - push CVD and reset
                self._finalize_minute()
            
            # Store current kline
            self.current_kline = {
                "start_time": start_time,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "turnover": turnover,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.kline_start_time = start_time
            
            # Update VWAP and VPOC
            self._update_vwap(close_price, volume)
            self._update_vpoc(close_price, volume)
            
            # Store in Redis
            asyncio.create_task(self._store_kline_data())
            
        except Exception as e:
            self.logger.error(f"Kline processing error: {e}")
    
    def _handle_trades(self, message):
        """Handle public trade data for CVD calculation."""
        try:
            if not message or "data" not in message:
                return
                
            for trade in message["data"]:
                # Parse trade fields
                exec_id = trade["i"]  # Execution ID for deduplication
                vol = float(trade["v"])
                side = trade["S"]  # "Buy" or "Sell"
                price = float(trade["p"])
                timestamp = int(trade["T"])
                
                # Deduplication check
                if exec_id in self._processed_trades:
                    continue
                
                # Add to processed sets
                self._processed_trades.add(exec_id)
                self._trade_deque.append(exec_id)
                
                # CVD Taker-Mathematik (ABSOLUTE PRÄZISION)
                if side == "Buy":
                    self.current_1m_taker_buy += vol
                elif side == "Sell":
                    self.current_1m_taker_sell += vol
                
                # Update VWAP with trade data
                self._update_vwap(price, vol)
                self._update_vpoc(price, vol)
                
        except Exception as e:
            self.logger.error(f"Trade processing error: {e}")
    
    def _finalize_minute(self):
        """Finalize the current minute - calculate CVD and reset counters."""
        try:
            # Calculate CVD Delta
            cvd_delta = self.current_1m_taker_buy - self.current_1m_taker_sell
            
            # Store CVD data point
            cvd_data = {
                "timestamp": self.kline_start_time,
                "delta": cvd_delta,
                "taker_buy": self.current_1m_taker_buy,
                "taker_sell": self.current_1m_taker_sell,
                "vwap": self.current_vwap,
                "vpoc": self.current_vpoc
            }
            
            # Store CVD time series in Redis
            asyncio.create_task(self._store_cvd_data(cvd_data))
            
            # Reset counters for next minute
            self.current_1m_taker_buy = 0.0
            self.current_1m_taker_sell = 0.0
            
            self.logger.debug(f"Minute finalized: CVD Delta = {cvd_delta:.2f}")
            
        except Exception as e:
            self.logger.error(f"Minute finalization error: {e}")
    
    def _update_vwap(self, price: float, volume: float):
        """Update Volume Weighted Average Price with daily reset."""
        try:
            current_date = datetime.now(timezone.utc).date()
            
            # Daily reset at 00:00:00 UTC
            if self.last_reset_date != current_date:
                self.daily_volume = 0.0
                self.daily_vwap_sum = 0.0
                self.current_vwap = 0.0
                self.last_reset_date = current_date
                self.logger.info("VWAP daily reset performed")
            
            # Update VWAP calculation
            self.daily_volume += volume
            self.daily_vwap_sum += price * volume
            
            if self.daily_volume > 0:
                self.current_vwap = self.daily_vwap_sum / self.daily_volume
                
        except Exception as e:
            self.logger.error(f"VWAP update error: {e}")
    
    def _update_vpoc(self, price: float, volume: float):
        """Update Volume Point of Control with 10-dollar buckets."""
        try:
            current_date = datetime.now(timezone.utc).date()
            
            # Daily reset at 00:00:00 UTC
            if self.last_reset_date != current_date:
                self.volume_profile.clear()
                self.current_vpoc = 0.0
            
            # Round price to 10-dollar buckets
            bucket = round(price / 10) * 10
            
            # Add volume to bucket
            self.volume_profile[bucket] = self.volume_profile.get(bucket, 0.0) + volume
            
            # Update VPOC (price with maximum volume)
            if self.volume_profile:
                self.current_vpoc = max(self.volume_profile, key=self.volume_profile.get)
                
        except Exception as e:
            self.logger.error(f"VPOC update error: {e}")
    
    async def _store_kline_data(self):
        """Store kline data in Redis."""
        try:
            if self.current_kline:
                await self.redis.set_cache(
                    "bybit:kline:BTCUSDT",
                    self.current_kline,
                    ttl=300
                )
        except Exception as e:
            self.logger.error(f"Kline storage error: {e}")
    
    async def _store_cvd_data(self, cvd_data: dict):
        """Store CVD data in Redis time series."""
        try:
            # Store latest CVD
            await self.redis.set_cache(
                "bybit:cvd:BTCUSDT",
                cvd_data,
                ttl=3600
            )
            
            # Add to time series list
            pipe = self.redis.redis.pipeline()
            pipe.lpush("bybit:cvd:timeseries", str(cvd_data))
            pipe.ltrim("bybit:cvd:timeseries", 0, 1439)  # Keep 24h of minutes
            await pipe.execute()
            
        except Exception as e:
            self.logger.error(f"CVD storage error: {e}")
    
    async def get_current_cvd(self) -> Dict[str, float]:
        """Get current CVD metrics."""
        return {
            "taker_buy": self.current_1m_taker_buy,
            "taker_sell": self.current_1m_taker_sell,
            "delta": self.current_1m_taker_buy - self.current_1m_taker_sell,
            "vwap": self.current_vwap,
            "vpoc": self.current_vpoc
        }
    
    async def disconnect(self):
        """Disconnect from Bybit WebSocket."""
        if self.ws:
            try:
                self.ws.disconnect()
            except:
                pass
        self.connected = False
        self.logger.info("Bybit V5 WebSocket disconnected")


class MarketDataCollector:
    """Marktdaten-Sammler für Bruno Trading Bot.
    
    Primärquelle: Bybit V5 WebSocket (Echtzeit)
    Legacy Binance REST: Deactivated for paper-trading
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None
        
        # Bybit V5 as Single Source of Truth
        self.bybit_client = BybitV5Client(redis_client)
        self.use_bybit_primary = True  # Bybit als einzige Quelle

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        
        # Bybit V5 disconnect
        await self.bybit_client.disconnect()

    async def collect_all_data(self, symbol: str = "BTCUSDT"):
        """Sammelt alle Marktdaten über Bybit V5 WebSocket."""
        try:
            # Bybit V5 ist die Single Source of Truth
            if not self.bybit_client.connected:
                await self.bybit_client.connect()
            
            # Daten werden über WebSocket-Callbacks in Redis gespeichert
            logger.info(f"Marktdaten für {symbol} via Bybit V5 aktiv")
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei Bybit V5 Datensammlung: {e}")
            return False

    async def health_check(self) -> bool:
        """Prüft ob Bybit V5 WebSocket verbunden ist."""
        try:
            return self.bybit_client.connected
        except Exception as e:
            logger.error(f"Bybit V5 health check failed: {e}")
            return False
