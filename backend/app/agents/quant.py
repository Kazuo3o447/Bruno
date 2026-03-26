import asyncio
import logging
import ccxt.async_support as ccxt
from datetime import datetime, timezone
import json
import numpy as np

from app.core.redis_client import redis_client
from app.schemas.agents import QuantSignal

logger = logging.getLogger(__name__)


class QuantAgent:
    def __init__(self):
        self.redis = redis_client
        self._running = False
        self.symbol = "BTC/USDT"
        self.timeframe = "1m"
        self.prices = []  # Einfache Liste statt pandas DataFrame
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})

    async def _warmup_history(self):
        """Holt die letzten 100 Kerzen via REST, um Indikatoren sofort berechnen zu können."""
        try:
            logger.info(f"Quant Agent: Lade Historie für {self.symbol}...")
            ohlcv = await self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
            # Nur Close-Preise speichern
            self.prices = [candle[4] for candle in ohlcv]  # Index 4 = close
            logger.info(f"Quant Agent: Warmup beendet. {len(self.prices)} Kerzen geladen.")
        except Exception as e:
            logger.error(f"Warmup Fehler: {e}")

    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """Berechnet den RSI (Relative Strength Index) mit NumPy."""
        if len(prices) < period + 1:
            return 50.0  # Neutraler Wert bei unzureichenden Daten
        
        # In NumPy Array konvertieren
        prices_array = np.array(prices)
        
        # Deltas berechnen
        deltas = np.diff(prices_array)
        
        # Gewinne und Verluste trennen
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Durchschnittliche Gewinne und Verluste (Simple Moving Average)
        avg_gains = np.mean(gains[-period:])
        avg_losses = np.mean(losses[-period:])
        
        if avg_losses == 0:
            return 100.0  # Keine Verluste = maximaler RSI
        
        rs = avg_gains / avg_losses
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return float(rsi)

    def _calculate_indicators_sync(self, prices: list) -> dict:
        """SYNCHRONE Funktion für NumPy-Mathematik (Wird im Thread ausgeführt)."""
        if len(prices) < 14:
            return {"signal": 0, "confidence": 0.0, "rsi": 50.0}

        # RSI berechnen
        rsi_val = self._calculate_rsi(prices, period=14)

        # Simple Quant-Logik
        signal = 0
        confidence = 0.0
        
        if rsi_val < 30:  # Oversold -> Bullish
            signal = 1
            confidence = (30 - rsi_val) / 30.0  # Je tiefer, desto höher die Konfidenz
        elif rsi_val > 70:  # Overbought -> Bearish
            signal = -1
            confidence = (rsi_val - 70) / 30.0
            
        return {
            "signal": signal,
            "confidence": min(confidence, 1.0),
            "rsi": round(rsi_val, 2)
        }

    async def run_analysis_loop(self):
        """Die Endlosschleife des Agenten."""
        self._running = True
        await self._warmup_history()

        while self._running:
            try:
                # 1. Neueste Kerze von Binance holen
                ohlcv = await self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=2)
                latest_close = ohlcv[-1][4]  # Letzter Close-Preis
                
                # Preise updaten (nur die letzten 200 behalten)
                self.prices.append(latest_close)
                if len(self.prices) > 200:
                    self.prices.pop(0)

                # 2. Auslagerung in Thread, um FastAPI Event-Loop nicht zu blockieren!
                calc_result = await asyncio.to_thread(self._calculate_indicators_sync, self.prices)

                # 3. Signal erstellen und Pydantic Validierung
                signal_obj = QuantSignal(
                    symbol=self.symbol,
                    signal=calc_result["signal"],
                    confidence=calc_result["confidence"],
                    indicators={"rsi": calc_result["rsi"]},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )

                # 4. In Redis Pub/Sub und Cache schreiben
                payload = json.dumps(signal_obj.model_dump(mode='json'))
                await self.redis.publish_message("signals:quant", payload)
                await self.redis.set_cache(f"agent:latest:quant:{self.symbol}", signal_obj.model_dump(mode='json'))
                
                logger.info(f"Quant Signal publiziert: {calc_result['signal']} (RSI: {calc_result['rsi']})")
                
            except Exception as e:
                logger.error(f"Quant Loop Error: {e}")

            # Sleep bis zur nächsten Analyse (alle 30 Sekunden)
            await asyncio.sleep(30)

    async def close(self):
        self._running = False
        await self.exchange.close()
