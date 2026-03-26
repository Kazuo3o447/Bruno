"""
Quant Agent

Lädt OHLCV-Historie, berechnet RSI im Hintergrund-Thread und feuert Signale.
Verwendet asyncio.to_thread um den Event-Loop nicht zu blockieren.
"""

import asyncio
import logging
import pandas as pd
import numpy as np
import ccxt.async_support as ccxt
from datetime import datetime, timezone
import json
from app.core.redis_client import redis_client
from app.schemas.agents import QuantSignal

logger = logging.getLogger(__name__)

class QuantAgent:
    def __init__(self):
        self.symbol = "BTC/USDT"
        self._running = False
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
        self.df = pd.DataFrame()

    def _calc_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Manuelle RSI Berechnung ohne pandas-ta"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calc_indicators(self, df: pd.DataFrame) -> dict:
        """Läuft synchron in asyncio.to_thread"""
        if len(df) < 14:
            return {"signal": 0, "confidence": 0.0, "rsi": 50.0}
        
        # Manuelle RSI Berechnung
        df['rsi'] = self._calc_rsi(df['close'])
        rsi = float(df.iloc[-1].get('rsi', 50.0))
        
        signal, conf = 0, 0.0
        if rsi < 30:
            signal, conf = 1, (30 - rsi) / 30.0
        elif rsi > 70:
            signal, conf = -1, (rsi - 70) / 30.0
            
        return {"signal": signal, "confidence": min(conf, 1.0), "rsi": round(rsi, 2)}

    async def start(self):
        self._running = True
        while self._running:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(self.symbol, "1m", limit=100)
                self.df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                result = await asyncio.to_thread(self._calc_indicators, self.df)
                
                sig = QuantSignal(
                    symbol=self.symbol, signal=result["signal"], 
                    confidence=result["confidence"], indicators={"rsi": result["rsi"]},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                await redis_client.publish_message("signals:quant", json.dumps(sig.model_dump()))
                await redis_client.set_cache("status:agent:quant", sig.model_dump())
                logger.debug(f"Quant Signal: {result['signal']} (RSI: {result['rsi']})")
            except Exception as e:
                logger.error(f"QuantAgent Error: {e}")
            await asyncio.sleep(60)

    async def stop(self):
        self._running = False
        await self.exchange.close()
