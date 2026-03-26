import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import QuantSignalV2, SignalDirection

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist

class QuantAgentV2(PollingAgent):
    """
    Phase 3: Multi-Timeframe Quant Logic
    Berechnet RSI, MACD, ATR auf 5m und 1h Basis und zieht das Orderbuch ein.
    """
    def __init__(self, deps: AgentDependencies, symbol: str = "BTCUSDT"):
        super().__init__("quant", deps)
        self.symbol = symbol

    async def setup(self) -> None:
        self.logger.info("QuantAgent setup abgeschlossen.")
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message="Quant Agent initialisiert. Überwache BTCUSDT."
        )

    def get_interval(self) -> float:
        return 60.0  # Alle 60 Sekunden evaluieren wir den Markt neu

    async def _fetch_candles(self, view_name: str, limit: int = 50) -> pd.DataFrame:
        """Holt Kerzen aus einer spezifischen View (z.B. candles_5m, candles_1h)."""
        query = text(f"""
            SELECT time, open, high, low, close, volume 
            FROM {view_name} 
            WHERE symbol = :symbol 
            ORDER BY time DESC 
            LIMIT :limit
        """)
        async with self.deps.db_session_factory() as session:
            result = await session.execute(query, {"symbol": self.symbol, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()
            # Umkehren für chronologische Berechnung
            df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df = df.iloc[::-1].reset_index(drop=True)
            return df

    def _analyze_timeframe(self, df: pd.DataFrame) -> Dict[str, float]:
        """Berechnet Indikatoren via NumPy/Pandas in Threads."""
        if len(df) < 14:
            return {}
            
        close = df['close']
        high = df['high']
        low = df['low']
        
        rsi = calculate_rsi(close, 14).iloc[-1]
        atr = calculate_atr(high, low, close, 14).iloc[-1]
        macd_line, signal_line, macd_hist = calculate_macd(close)
        
        # Sicherstellen, dass keine NaN Werte zurückgegeben werden (z.B. am Anfang)
        if np.isnan(rsi) or np.isnan(atr) or np.isnan(macd_hist.iloc[-1]):
            self.logger.warning(f"Indikatoren unvollständig (NaN). Warte auf mehr Daten.")
            return {}
            
        return {
            "close": float(close.iloc[-1]),
            "rsi": float(rsi),
            "atr": float(atr),
            "macd_hist": float(macd_hist.iloc[-1])
        }

    async def _get_orderbook_imbalance(self) -> float:
        ob_data = await self.deps.redis.get_cache(f"market:orderbook:{self.symbol}")
        if ob_data and "imbalance_ratio" in ob_data:
            return ob_data["imbalance_ratio"]
        return 1.0

    def _evaluate_signals(self, metrics_5m: dict, metrics_1h: dict, imbalance: float) -> Tuple[SignalDirection, float, str, str]:
        # Sehr primitive Beispiel-Logik:
        # Wenn 1h RSI < 45 und 5m RSI < 30 und Buy-Überhang im Orderbuch -> Long (Reversal Scalp)
        # Wenn 1h RSI > 55 und 5m RSI > 70 und Sell-Überhang -> Short
        
        rsi_1h = metrics_1h.get("rsi", 50)
        rsi_5m = metrics_5m.get("rsi", 50)
        
        market_state = "neutral"
        direction = SignalDirection.HOLD
        confidence = 0.5
        reasoning = f"Märkte sind neutral. RSI_1h={rsi_1h:.1f}, RSI_5m={rsi_5m:.1f}"

        if rsi_1h < 45 and rsi_5m < 35 and imbalance >= 1.5:
            market_state = "oversold + bid_wall"
            direction = SignalDirection.BUY
            confidence = 0.75
            reasoning = f"Makro leicht bearish, aber 5m stark oversold ({rsi_5m:.1f}) + OB zeigt massive Buy-Absicht ({imbalance:.1f}x bids)."
        
        elif rsi_1h > 55 and rsi_5m > 65 and imbalance <= 0.8:
            market_state = "overbought + ask_wall"
            direction = SignalDirection.SELL
            confidence = 0.75
            reasoning = f"Makro leicht bullish, aber 5m overbought ({rsi_5m:.1f}) + OB zeigt Verkaufsdruck ({imbalance:.1f}x imbalance)."
            
        return direction, confidence, reasoning, market_state

    async def process(self) -> None:
        try:
            # Daten sammeln
            df_5m = await self._fetch_candles("candles_5m", 100)
            df_1h = await self._fetch_candles("candles_1h", 100)
            
            if df_5m.empty or df_1h.empty:
                self.state.health = "degraded"
                await self.log_manager.warning(
                    category="AGENT",
                    source=self.agent_id,
                    message="Warte auf Marktdaten (Datenbank-Views sind noch leer)."
                )
                return
            else:
                self.state.health = "healthy"
            
            # Indikatoren im Thread berechnen
            metrics_5m = await asyncio.to_thread(self._analyze_timeframe, df_5m)
            metrics_1h = await asyncio.to_thread(self._analyze_timeframe, df_1h)
            
            if not metrics_5m or not metrics_1h:
                self.logger.warning("Nicht genug Kerzen-Daten für Quant-Analyse.")
                return
                
            imbalance = await self._get_orderbook_imbalance()
            
            # Logik ausführen
            direction, confidence, reasoning, state = self._evaluate_signals(metrics_5m, metrics_1h, imbalance)
            
            # Indicators Map bauen
            indicators = {
                "price": metrics_1h["close"],
                "rsi_5m": metrics_5m["rsi"],
                "rsi_1h": metrics_1h["rsi"],
                "macd_hist_5m": metrics_5m["macd_hist"],
                "atr_1h": metrics_1h["atr"],
                "ob_imbalance": imbalance
            }
            
            signal = QuantSignalV2(
                agent_id=self.agent_id,
                symbol=self.symbol,
                direction=direction,
                confidence=confidence,
                indicators=indicators,
                market_state={"trend": state},
                reasoning=reasoning
            )
            
            
            await self.deps.redis.publish_message("signals:quant", signal.model_dump_json())
            
            await self.log_manager.debug(
                category="AGENT",
                source=self.agent_id,
                message=f"Quant Analyse abgeschlossen: {direction.value}",
                details={"rsi_5m": indicators["rsi_5m"], "rsi_1h": indicators["rsi_1h"]}
            )
            self.logger.info(f"Quant Signal publiziert: {direction} ({confidence:.2f})")
            
        except Exception as e:
            self.logger.error(f"Fehler in Quant-Analyse: {e}")
