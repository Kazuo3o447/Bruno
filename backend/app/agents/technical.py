import asyncio
import json
import logging
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies

class TechnicalAnalysisAgent(PollingAgent):
    """
    Technical Analysis Engine für Bruno v2.
    
    Berechnet:
    - EMA(9/21/50/200) auf 1h-Candles
    - RSI(14) auf 1h-Candles
    - VWAP (intraday, 15m)
    - ATR(14) auf 1h-Candles
    - Multi-Timeframe EMA-Alignment (5m, 15m, 1h, 4h)
    - Support/Resistance via Swing-High/Low-Clustering
    - Breakout-Proximity
    - Wick-Detection (Reversal-Kerzen)
    - Session-Awareness (Asia/EU/US)
    - Orderbuch-Walls (Binance depth=1000)
    
    Polling-Intervall: 60 Sekunden
    Datenquelle: market_candles (1m, TimescaleDB)
    Output: bruno:ta:snapshot (Redis JSON)
    """
    
    def __init__(self, deps: AgentDependencies):
        super().__init__("technical", deps)
        self.logger = logging.getLogger("technical_agent")
        
        # Cache für Orderbuch-Walls (30s TTL)
        self._ob_walls_cache = None
        self._ob_walls_cache_time = 0
        
        # FIX: Institutioneller VWAP Tages-Reset
        self._last_vwap_reset_date = datetime.min.date()
        self._vwap_cumulative_pv = 0.0
        self._vwap_cumulative_volume = 0.0
        self.volume_profile: Dict[int, float] = {}

    def get_interval(self) -> float:
        """60-Sekunden-Intervall für Technical Analysis."""
        return 60.0

    async def setup(self) -> None:
        """Setup mit historischem Backfill wenn nötig."""
        await self._ensure_historical_data()
        self.logger.info("TechnicalAnalysisAgent setup completed")

    async def _ensure_historical_data(self) -> None:
        """Prüft ob genug Candles in DB. Wenn < 1000 → Backfill via Binance REST."""
        try:
            async with self.deps.db_session_factory() as session:
                result = await session.execute(text("""
                    SELECT COUNT(*) as count FROM market_candles 
                    WHERE symbol = 'BTCUSDT' AND time >= NOW() - INTERVAL '7 days'
                """))
                count = result.scalar() or 0
                
                if count < 1000:
                    self.logger.info(f"TA-Engine Backfill: Nur {count} Candles vorhanden, starte Backfill")
                    await self._backfill_candles()
                else:
                    self.logger.info(f"TA-Engine: {count} Candles vorhanden, kein Backfill nötig")
                    
        except Exception as e:
            self.logger.warning(f"Backfill-Check Fehler: {e}")

    async def _backfill_candles(self) -> None:
        """Lädt historische Candles von Binance REST API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1000 Candles = ~16.7 Stunden
                url = "https://fapi.binance.com/fapi/v1/klines"
                params = {
                    "symbol": "BTCUSDT",
                    "interval": "1m",
                    "limit": 1000
                }
                
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    raise Exception(f"Binance API Error: {response.status_code}")
                
                data = response.json()
                
                # Bulk Insert mit ON CONFLICT DO NOTHING
                candles_data = []
                for candle in data:
                    timestamp_ms, open_price, high_price, low_price, close_price, volume = candle[:6]
                    candles_data.append({
                        "time": datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc),
                        "symbol": "BTCUSDT",
                        "open": float(open_price),
                        "high": float(high_price),
                        "low": float(low_price),
                        "close": float(close_price),
                        "volume": float(volume)
                    })
                
                async with self.deps.db_session_factory() as session:
                    # Bulk Insert mit Conflict Resolution
                    for candle_data in candles_data:
                        await session.execute(text("""
                            INSERT INTO market_candles (time, symbol, open, high, low, close, volume)
                            VALUES (:time, :symbol, :open, :high, :low, :close, :volume)
                            ON CONFLICT (time, symbol) DO NOTHING
                        """), candle_data)
                    
                    await session.commit()
                
                self.logger.info(f"TA-Engine Backfill: {len(candles_data)} Candles geladen")
                
        except Exception as e:
            self.logger.error(f"Backfill Fehler: {e}")

    async def _fetch_candles(self, interval: str, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Lädt Candles mit Multi-Timeframe Aggregation.
        Versucht zuerst time_bucket(), dann Fallback.
        """
        try:
            lookback_map = {
                "1 minute": "24 hours",
                "5 minutes": "5 hours",
                "15 minutes": "24 hours", 
                "1 hour": "8 days",
                "4 hours": "16 days"
            }
            
            lookback = lookback_map.get(interval, "24 hours")
            
            # Versuch 1: TimescaleDB time_bucket()
            try:
                async with self.deps.db_session_factory() as session:
                    result = await session.execute(text(f"""
                        SELECT time_bucket(:interval, time) AS bucket,
                               FIRST(open, time) AS open, MAX(high) AS high,
                               MIN(low) as low, LAST(close, time) AS close, SUM(volume) AS volume
                        FROM market_candles 
                        WHERE symbol = :symbol AND time > NOW() - INTERVAL '{lookback}'
                        GROUP BY bucket ORDER BY bucket ASC
                        LIMIT :limit
                    """), {"interval": interval, "symbol": "BTCUSDT", "limit": limit})
                    
                    rows = result.fetchall()
                    return [
                        {
                            "time": row[0],
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5])
                        }
                        for row in rows
                    ]
                    
            except Exception as e:
                self.logger.debug(f"time_bucket() nicht verfügbar, nutze Fallback: {e}")
            
            # Versuch 2: Fallback mit date_trunc() / floor()
            try:
                async with self.deps.db_session_factory() as session:
                    if interval in ["1 hour", "4 hours"]:
                        # date_trunc() für 1h/4h
                        interval_map = {"1 hour": "hour", "4 hours": "hour"}
                        result = await session.execute(text(f"""
                            SELECT date_trunc('{interval_map[interval]}', time) AS bucket,
                                   FIRST(open, time) AS open, MAX(high) AS high,
                                   MIN(low) AS low, LAST(close, time) AS close, SUM(volume) AS volume
                            FROM market_candles 
                            WHERE symbol = 'BTCUSDT' AND time > NOW() - INTERVAL '{lookback}'
                            GROUP BY bucket ORDER BY bucket ASC
                            LIMIT {limit}
                        """))
                    else:
                        # floor-Berechnung für 5m/15m
                        seconds_map = {"1 minute": 60, "5 minutes": 300, "15 minutes": 900}
                        seconds = seconds_map.get(interval, 300)
                        
                        result = await session.execute(text(f"""
                            SELECT to_timestamp(floor(extract(epoch from time) / {seconds}) * {seconds}) AS bucket,
                                   FIRST(open, time) AS open, MAX(high) AS high,
                                   MIN(low) as low, LAST(close, time) AS close, SUM(volume) AS volume
                            FROM market_candles 
                            WHERE symbol = 'BTCUSDT' AND time > NOW() - INTERVAL '{lookback}'
                            GROUP BY bucket ORDER BY bucket ASC
                            LIMIT {limit}
                        """))
                    
                    rows = result.fetchall()
                    return [
                        {
                            "time": row[0],
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5])
                        }
                        for row in rows
                    ]
                    
            except Exception as e:
                self.logger.error(f"Candle Fetch Fehler: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Candle Fetch komplett fehlgeschlagen: {e}")
            return []

    def _calc_volume_profile(self, candles: List[Dict]) -> dict:
        """
        Berechnet ein 1m Volume-at-Price Profil und identifiziert VPOC.

        Volumen jeder Kerze wird auf den auf 10er-Schritte gerundeten Preis-Bucket
        geschrieben. Der Bucket mit dem höchsten akkumulierten Volumen wird als VPOC
        und primäres S/R-Level verwendet.
        """
        if not candles:
            self.volume_profile = {}
            return {"vpoc": 0.0, "vpoc_volume": 0.0, "profile": [], "high_volume_nodes": [], "volume_profile": {}}

        tick_size = 10
        self.volume_profile = {}

        for candle in candles:
            price_reference = float(candle["close"])
            bucket_price = int(round(price_reference / tick_size) * tick_size)
            self.volume_profile[bucket_price] = self.volume_profile.get(bucket_price, 0.0) + float(candle["volume"])

        if not self.volume_profile:
            return {"vpoc": 0.0, "vpoc_volume": 0.0, "profile": [], "high_volume_nodes": [], "volume_profile": {}}

        sorted_volume_levels = sorted(self.volume_profile.items(), key=lambda x: x[1], reverse=True)
        vpoc_price, vpoc_volume = sorted_volume_levels[0]
        total_volume = sum(self.volume_profile.values())

        high_volume_nodes = []
        for price_level, volume in sorted_volume_levels[:10]:
            high_volume_nodes.append({
                "price": float(price_level),
                "volume": round(volume, 2),
                "volume_pct": round(volume / total_volume * 100, 1) if total_volume > 0 else 0.0,
            })

        return {
            "vpoc": float(vpoc_price),
            "vpoc_volume": round(vpoc_volume, 2),
            "profile": high_volume_nodes,
            "high_volume_nodes": high_volume_nodes[:5],
            "total_volume": round(total_volume, 2),
            "price_levels_count": len(self.volume_profile),
            "volume_profile": dict(self.volume_profile),
        }

    def _calc_15m_delta_bars(self, candles_15m: List[Dict]) -> dict:
        """
        Aggregiert CVD in 15m-Blöcken und identifiziert Absorption-Signale.
        
        Absorption = Hohes Volumen + starkes Delta aber kleine Preisbewegung.
        Institutionelle Käufer/Verkäufer absorbieren Order-Flow.
        """
        if len(candles_15m) < 10:
            return {"delta_bars": [], "absorption_signals": [], "current_delta": 0.0}
        
        delta_bars = []
        for candle in candles_15m[-10:]:  # Letzte 10 Bars = 2.5h
            # Delta aus Taker-Buy/Sell Volume (falls verfügbar)
            # Fallback: Close-Change als Proxy
            price_change = candle["close"] - candle["open"]
            volume = candle["volume"]
            
            # Delta Proxy: Volume * Price-Direction
            delta = volume * (1 if price_change > 0 else -1 if price_change < 0 else 0)
            
            # Body Size als % von Range
            body_size = abs(candle["close"] - candle["open"])
            range_size = candle["high"] - candle["low"]
            body_ratio = body_size / range_size if range_size > 0 else 0
            
            delta_bar = {
                "time": candle["time"],
                "price": candle["close"],
                "delta": round(delta, 2),
                "volume": round(volume, 2),
                "body_ratio": round(body_ratio, 3),
                "price_change_pct": round(price_change / candle["open"] * 100, 2) if candle["open"] > 0 else 0
            }
            delta_bars.append(delta_bar)
        
        # Absorption-Detektion
        absorption_signals = []
        avg_volume = sum(bar["volume"] for bar in delta_bars) / len(delta_bars)
        
        for bar in delta_bars:
            # Kriterien für Absorption:
            # 1. Volumen > 1.5x Durchschnitt
            # 2. Starkes Delta (hohe Absolutwert)
            # 3. Kleine Preisbewegung (body_ratio < 0.3)
            if (bar["volume"] > avg_volume * 1.5 and
                abs(bar["delta"]) > avg_volume * 0.7 and
                bar["body_ratio"] < 0.3):
                
                direction = "buying" if bar["delta"] > 0 else "selling"
                absorption_signals.append({
                    "time": bar["time"],
                    "price": bar["price"],
                    "direction": direction,
                    "strength": round(abs(bar["delta"]) / avg_volume, 2),
                    "volume_ratio": round(bar["volume"] / avg_volume, 2),
                    "body_ratio": bar["body_ratio"]
                })
        
        current_delta = delta_bars[-1]["delta"] if delta_bars else 0.0
        
        return {
            "delta_bars": delta_bars,
            "absorption_signals": absorption_signals[-3:],  # Letzte 3 Signale
            "current_delta": round(current_delta, 2),
            "delta_trend": "increasing" if len(delta_bars) >= 3 and 
                           delta_bars[-1]["delta"] > delta_bars[-3]["delta"] else "decreasing"
        }

    def _calc_ema(self, candles: List[Dict], period: int) -> float:
        """Berechnet EMA für gegebenen Period."""
        if len(candles) < period:
            return 0.0
        
        closes = [c["close"] for c in candles]
        
        # Initial SMA
        sma = sum(closes[:period]) / period
        ema = sma
        multiplier = 2 / (period + 1)
        
        # EMA für restliche Candles
        for close in closes[period:]:
            ema = (close * multiplier) + (ema * (1 - multiplier))
        
        return ema

    def _calc_rsi(self, candles: List[Dict], period: int = 14) -> float:
        """Berechnet RSI(14) mit Wilder's Exponential Smoothing - TradingView kompatibel."""
        if len(candles) < period + 1:
            return 50.0
        
        closes = [c["close"] for c in candles]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(candles))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        
        # Wilder's Exponential Smoothing: Initial SMA, dann EMA mit Alpha = 1/period
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # Exponential Smoothing für restliche Werte
        alpha = 1.0 / period
        for i in range(period, len(gains)):
            avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_vwap(self, candles: List[Dict]) -> float:
        """
        Berechnet VWAP mit institutionellem Tages-Reset exakt um 00:00:00 UTC.
        
        FIX: Reset exakt um 00:00:00 UTC (Typical Price Basis).
        Tracke _last_reset_day (YYYY-MM-DD).
        Wenn datetime.now(timezone.utc).date() > _last_reset_day:
        Setze Akkumulatoren hart auf 0 zurück.
        """
        if not candles:
            return 0.0

        # Prüfe ob UTC Tages-Reset nötig (exakt 00:00:00 UTC)
        current_utc_date = datetime.now(timezone.utc).date()
        if current_utc_date > self._last_vwap_reset_date:
            self._last_vwap_reset_date = current_utc_date
            self._vwap_cumulative_pv = 0.0
            self._vwap_cumulative_volume = 0.0
            self.logger.info(f"VWAP UTC Tages-Reset für {current_utc_date} (00:00:00 UTC)")

        # Akkumuliere Typical Price * Volume (Typical Price Basis)
        for current_candle in candles:
            typical_price = (
                current_candle["high"] + current_candle["low"] + current_candle["close"]
            ) / 3.0
            self._vwap_cumulative_pv += typical_price * current_candle["volume"]
            self._vwap_cumulative_volume += current_candle["volume"]
        
        return self._vwap_cumulative_pv / self._vwap_cumulative_volume if self._vwap_cumulative_volume > 0 else 0.0

    def _calc_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Berechnet ATR(14) mit True Range."""
        if len(candles) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i-1]["close"]
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_ranges.append(max(tr1, tr2, tr3))
        
        return sum(true_ranges[-period:]) / period

    def _check_mtf_alignment(self, c5m, c15m, c1h, c4h) -> dict:
        """
        Multi-Timeframe EMA-Alignment.
        Ein Signal auf dem niedrigen Timeframe ist NUR gültig wenn der
        übergeordnete Trend in dieselbe Richtung zeigt.
        """
        def _tf_direction(candles, period=9, period2=21):
            if len(candles) < period2: 
                return "neutral"
            ema_fast = self._calc_ema(candles, period)
            ema_slow = self._calc_ema(candles, period2)
            return "bull" if ema_fast > ema_slow else "bear"
        
        dirs = {
            "5m": _tf_direction(c5m),
            "15m": _tf_direction(c15m),
            "1h": _tf_direction(c1h),
            "4h": _tf_direction(c4h),
        }
        
        # Alignment Score: gewichtete Summe
        weights = {"4h": 3, "1h": 2, "15m": 1}
        score = 0
        total_weight = sum(weights.values())
        for tf, w in weights.items():
            if dirs[tf] == "bull": 
                score += w
            elif dirs[tf] == "bear": 
                score -= w
        alignment_score = round(score / total_weight, 2)
        
        # Conflict Detection
        conflicting = None
        for tf in ["4h", "1h", "15m"]:
            if dirs[tf] != dirs.get("1h"):
                conflicting = tf
                break
        
        return {
            "aligned_long": all(d == "bull" for d in [dirs["15m"], dirs["1h"], dirs["4h"]]),
            "aligned_short": all(d == "bear" for d in [dirs["15m"], dirs["1h"], dirs["4h"]]),
            "alignment_score": alignment_score,
            "conflicting_tf": conflicting,
            "detail": dirs,
        }

    def _classify_trend(self, candles, ema_9, ema_21, ema_50, ema_200) -> dict:
        """Klassifiziert den Trend basierend auf EMA-Stack."""
        if not candles:
            return {"direction": "neutral", "strength": 0.0, "ema_stack": "mixed"}
        
        current_price = candles[-1]["close"]
        
        # EMA Stack Bestimmung
        if ema_9 > ema_21 > ema_50 > ema_200:
            stack = "perfect_bull"
        elif ema_9 > ema_21 > ema_50 > ema_200 * 0.98:
            stack = "bull"
        elif ema_9 < ema_21 < ema_50 < ema_200:
            stack = "perfect_bear"
        elif ema_9 < ema_21 < ema_50 < ema_200 * 1.02:
            stack = "bear"
        else:
            stack = "mixed"
        
        # Trend-Stärke basierend auf Abstand zu EMAs
        ema_distances = [
            abs(current_price - ema_9) / current_price,
            abs(current_price - ema_21) / current_price,
            abs(current_price - ema_50) / current_price,
            abs(current_price - ema_200) / current_price
        ]
        strength = 1.0 - sum(ema_distances) / len(ema_distances)
        
        direction = "up" if stack in ["perfect_bull", "bull"] else "down" if stack in ["perfect_bear", "bear"] else "neutral"
        
        return {
            "direction": direction,
            "strength": max(0.0, min(1.0, strength)),
            "ema_stack": stack
        }

    def _detect_sr_levels(self, candles_1h, candles_4h, current_price) -> List[Dict]:
        """Erkennt Support/Resistance Levels via Swing-High/Low-Clustering."""
        levels = []
        
        # Swing Highs/Lows auf 4h Chart
        if len(candles_4h) < 10:
            return levels
            
        for i in range(2, len(candles_4h) - 2):
            candle = candles_4h[i]
            prev_candle = candles_4h[i-1]
            next_candle = candles_4h[i+1]
            
            # Swing High
            if (candle["high"] > prev_candle["high"] and 
                candle["high"] > next_candle["high"] and
                candle["high"] > candles_4h[i-2]["high"] and
                candle["high"] > candles_4h[i+2]["high"]):
                
                strength = min(5, int((candle["high"] - current_price) / current_price * 10000 / 50))
                levels.append({
                    "price": round(candle["high"], 2),
                    "type": "resistance",
                    "strength": strength,
                    "distance_pct": round((candle["high"] - current_price) / current_price * 100, 2)
                })
            
            # Swing Low
            elif (candle["low"] < prev_candle["low"] and 
                  candle["low"] < next_candle["low"] and
                  candle["low"] < candles_4h[i-2]["low"] and
                  candle["low"] < candles_4h[i+2]["low"]):
                
                strength = min(5, int((current_price - candle["low"]) / current_price * 10000 / 50))
                levels.append({
                    "price": round(candle["low"], 2),
                    "type": "support",
                    "strength": strength,
                    "distance_pct": round((candle["low"] - current_price) / current_price * 100, 2)
                })
        
        # Sortieren nach Stärke und Entfernung
        levels.sort(key=lambda x: (x["strength"], abs(x["distance_pct"])), reverse=True)
        return levels[:10]  # Top 10 Levels

    def _check_breakout_proximity(self, price, sr_levels, atr) -> dict:
        """Prüft die Nähe zu S/R Levels und Breakout-Kandidaten."""
        if not sr_levels:
            return {"near_support": False, "near_resistance": False, "breakout_candidate": None}
        
        # Nächste Support/Resistance finden
        support_levels = [l for l in sr_levels if l["type"] == "support"]
        resistance_levels = [l for l in sr_levels if l["type"] == "resistance"]
        
        nearest_support = min(support_levels, key=lambda x: abs(x["distance_pct"])) if support_levels else None
        nearest_resistance = min(resistance_levels, key=lambda x: abs(x["distance_pct"])) if resistance_levels else None
        
        # Near-Level Definition: innerhalb von 0.5% oder 1x ATR
        near_threshold_pct = 0.5
        near_threshold_atr = (atr / price) * 100 if price > 0 and atr > 0 else near_threshold_pct
        
        near_support = nearest_support and nearest_support["distance_pct"] > -max(near_threshold_pct, near_threshold_atr)
        near_resistance = nearest_resistance and nearest_resistance["distance_pct"] < max(near_threshold_pct, near_threshold_atr)
        
        # Breakout Kandidat
        breakout_candidate = None
        if near_resistance and nearest_resistance["strength"] >= 3:
            breakout_candidate = "up"
        elif near_support and nearest_support["strength"] >= 3:
            breakout_candidate = "down"
        
        return {
            "near_support": near_support,
            "near_resistance": near_resistance,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "breakout_candidate": breakout_candidate
        }

    def _analyze_volume(self, candles_1h) -> dict:
        """Analysiert das Volumen."""
        if len(candles_1h) < 20:
            return {"current_vs_avg": 1.0, "volume_trend": "unknown"}
        
        current_volume = candles_1h[-1]["volume"]
        avg_volume = sum(c["volume"] for c in candles_1h[-20:]) / 20
        
        # Volume Trend
        recent_volumes = [c["volume"] for c in candles_1h[-5:]]
        older_volumes = [c["volume"] for c in candles_1h[-10:-5]]
        
        if sum(recent_volumes) > sum(older_volumes):
            trend = "increasing"
        elif sum(recent_volumes) < sum(older_volumes):
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "current_vs_avg": current_volume / avg_volume if avg_volume > 0 else 1.0,
            "volume_trend": trend,
            "current_volume": current_volume,
            "avg_volume": avg_volume
        }

    def _detect_wick(self, candles_5m: List[Dict]) -> dict:
        """
        Erkennt Reversal-Kerzen (Wicks/Lunten) auf dem 5m-Chart.
        Eine Lunte signalisiert Rejection an einem Preisniveau.
        """
        if len(candles_5m) < 3:
            return {"bullish_wick": False, "bearish_wick": False, 
                    "wick_strength": 0.0, "wick_price": 0.0}
        
        # Prüfe letzte 3 Kerzen
        for c in candles_5m[-3:]:
            body = abs(c["close"] - c["open"])
            if body < 0.01: 
                body = 0.01  # Division by zero
            upper_wick = c["high"] - max(c["open"], c["close"])
            lower_wick = min(c["open"], c["close"]) - c["low"]
            
            # Bullish Hammer
            if lower_wick > body * 2.0 and upper_wick < body * 0.5:
                return {
                    "bullish_wick": True, "bearish_wick": False,
                    "wick_strength": min(1.0, lower_wick / body / 4.0),
                    "wick_price": c["low"],
                }
            # Bearish Shooting Star
            if upper_wick > body * 2.0 and lower_wick < body * 0.5:
                return {
                    "bullish_wick": False, "bearish_wick": True,
                    "wick_strength": min(1.0, upper_wick / body / 4.0),
                    "wick_price": c["high"],
                }
        
        return {"bullish_wick": False, "bearish_wick": False,
                "wick_strength": 0.0, "wick_price": 0.0}

    def _get_session_context(self) -> dict:
        """
        Erkennt die aktuelle Trading-Session.
        BTC-Volatilität variiert erheblich nach Session.
        """
        hour = datetime.now(timezone.utc).hour
        if 0 <= hour < 8:
            return {"session": "asia", "volatility_bias": 0.6, "trend_expected": False}
        elif 8 <= hour < 14:
            return {"session": "europe", "volatility_bias": 0.9, "trend_expected": False}
        elif 14 <= hour < 16:
            return {"session": "eu_us_overlap", "volatility_bias": 1.4, "trend_expected": True}
        elif 16 <= hour < 21:
            return {"session": "us", "volatility_bias": 1.2, "trend_expected": True}
        else:
            return {"session": "late_us", "volatility_bias": 0.7, "trend_expected": False}

    async def _fetch_orderbook_walls(self, current_price: float) -> dict:
        """
        Fetcht das volle Binance-Orderbuch (1000 Level) und identifiziert
        massive Limit-Order-Walls als Live-Liquiditäts-Magneten.
        """
        # Cache prüfen (30s TTL)
        current_time = time.time()
        if (self._ob_walls_cache and 
            current_time - self._ob_walls_cache_time < 30):
            return self._ob_walls_cache
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = "https://fapi.binance.com/fapi/v1/depth"
                params = {"symbol": "BTCUSDT", "limit": 1000}
                
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    return self._ob_walls_fallback()
                
                data = response.json()
            
            bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
            asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
            
            # Median-Berechnung für Threshold
            all_sizes = sorted([q for _, q in bids + asks])
            median_size = all_sizes[len(all_sizes)//2] if all_sizes else 1.0
            wall_threshold = median_size * 5.0  # 5× Median = Wall
            
            bid_walls = [
                {"price": p, "size_btc": q, "size_usdt": round(p*q, 0),
                 "distance_pct": round((p - current_price) / current_price * 100, 2)}
                for p, q in bids if q > wall_threshold
            ]
            ask_walls = [
                {"price": p, "size_btc": q, "size_usdt": round(p*q, 0),
                 "distance_pct": round((p - current_price) / current_price * 100, 2)}
                for p, q in asks if q > wall_threshold
            ]
            
            # Top 5, sortiert nach Größe
            bid_walls.sort(key=lambda w: w["size_btc"], reverse=True)
            ask_walls.sort(key=lambda w: w["size_btc"], reverse=True)
            bid_walls = bid_walls[:5]
            ask_walls = ask_walls[:5]
            
            # Imbalance
            total_bid = sum(w["size_btc"] for w in bid_walls)
            total_ask = sum(w["size_btc"] for w in ask_walls)
            imbalance = total_bid / total_ask if total_ask > 0 else 2.0
            
            result = {
                "bid_walls": bid_walls,
                "ask_walls": ask_walls,
                "nearest_bid_wall": min(bid_walls, key=lambda w: abs(w["distance_pct"]), default=None),
                "nearest_ask_wall": min(ask_walls, key=lambda w: abs(w["distance_pct"]), default=None),
                "wall_imbalance": round(imbalance, 2),
            }
            
            self._ob_walls_cache = result
            self._ob_walls_cache_time = current_time
            return result
            
        except Exception as e:
            self.logger.warning(f"Orderbuch-Wall Fetch Fehler: {e}")
            return self._ob_walls_fallback()

    def _ob_walls_fallback(self) -> dict:
        return {"bid_walls": [], "ask_walls": [], "nearest_bid_wall": None,
                "nearest_ask_wall": None, "wall_imbalance": 1.0}

    def _calculate_ta_score(self, trend, rsi, sr_levels, breakout, volume,
                             price, ema_9, ema_21, vwap, mtf, wick, regime, session) -> dict:
        """
        Normalisierter TA-Score (-100 bis +100).
        Positiv = bullisch, negativ = bärisch.
        """
        score = 0.0
        signals = []
        
        # Trend (25%) — mit Ranging-Kompensation
        stack = trend.get("ema_stack", "mixed")
        if stack == "perfect_bull":
            score += 25; signals.append("Perfect bull EMA stack")
        elif stack == "bull":
            score += 18; signals.append("Bull EMA stack")
        elif stack == "perfect_bear":
            score -= 25; signals.append("Perfect bear EMA stack")
        elif stack == "bear":
            score -= 18; signals.append("Bear EMA stack")
        elif stack == "mixed":
            # NEU: Im Mixed-Stack prüfe ob sich ein Trend aufbaut
            # Wenn die kurzen EMAs (9, 21) aligned sind, tendiert der Markt
            if ema_9 > ema_21:
                score += 8
                signals.append("Short-term EMAs bullish (trend building)")
            elif ema_9 < ema_21:
                score -= 8
                signals.append("Short-term EMAs bearish (trend building)")
        
        # MTF-Alignment (20%)
        alignment = mtf.get("alignment_score", 0)
        score += alignment * 20
        if mtf.get("aligned_long"): 
            signals.append("MTF aligned long")
        elif mtf.get("aligned_short"): 
            signals.append("MTF aligned short")
        elif mtf.get("conflicting_tf"): 
            signals.append(f"MTF conflict at {mtf['conflicting_tf']}")
        
        # RSI (10%)
        if rsi < 30: 
            score += 10; signals.append("RSI oversold")
        elif rsi < 40: 
            score += 5
        elif rsi > 70: 
            score -= 10; signals.append("RSI overbought")
        elif rsi > 60: 
            score -= 5
        
        # S/R Kontext (20%)
        if breakout.get("near_support"):
            ns = breakout["nearest_support"]
            if ns and ns.get("strength", 0) >= 3:
                score += 15; signals.append(f"Near strong support {ns['price']:.0f}")
            else:
                score += 8
        elif breakout.get("near_resistance"):
            nr = breakout["nearest_resistance"]
            if nr and nr.get("strength", 0) >= 3:
                score -= 15; signals.append(f"Near strong resistance {nr['price']:.0f}")
            else:
                score -= 8
        
        # Breakout-Kandidat
        if (breakout.get("breakout_candidate") == "up" and 
            volume.get("current_vs_avg", 0) > 1.3):
            score += 5; signals.append("Breakout candidate up with volume")
        
        # Volume (10%) — session-aware
        vol_ratio = volume.get("current_vs_avg", 1.0)
        session_name = session.get("session", "us") if isinstance(session, dict) else "us"

        if vol_ratio > 1.5:
            score += 8; signals.append("High volume confirmation")
        elif vol_ratio > 1.2:
            score += 4
        elif vol_ratio < 0.5:
            # Nur in aktiven Sessions ist Low Volume ein Warnsignal
            if session_name in ("europe", "eu_us_overlap", "us"):
                score -= 5; signals.append("Low volume warning")
            else:
                # Asia/Late-US: low volume ist normal, keine Penalty
                pass
        
        # VWAP (10%)
        if price > vwap * 1.001: 
            score += 8; signals.append("Above VWAP")
        elif price < vwap * 0.999: 
            score -= 8; signals.append("Below VWAP")
        
        # Wick-Signal (5% Bonus)
        if wick.get("bullish_wick"): 
            score += 5 * wick["wick_strength"]; signals.append("Bullish wick detected")
        elif wick.get("bearish_wick"): 
            score -= 5 * wick["wick_strength"]; signals.append("Bearish wick detected")
        
        # ═══ MTF-FILTER (KRITISCH) ═══
        direction = "long" if score > 0 else "short" if score < 0 else "neutral"
        alignment = mtf.get("alignment_score", 0)  # -1.0 bis +1.0
        
        # Regime-abhängiger MTF-Filter
        if regime in ["ranging", "high_vola"]:
            # Entspannte Filter für Ranging/Hoch-Vola Märkte
            if direction == "long":
                if alignment < 0:  # Gegensignal
                    score *= 0.5
                    signals.append("⚠ MTF contra-signal — score reduced 50% (ranging regime)")
                elif alignment < 0.5:  # Teilweise aligned
                    score *= 0.8
                    signals.append("⚠ MTF partially aligned — score reduced 20% (ranging regime)")
            elif direction == "short":
                if alignment > 0:
                    score *= 0.5
                    signals.append("⚠ MTF contra-signal — score reduced 50% (ranging regime)")
                elif alignment > -0.5:
                    score *= 0.8
                    signals.append("⚠ MTF partially aligned — score reduced 20% (ranging regime)")
            signals.append("MTF relaxed (ranging regime)")
        else:
            # Aggressive Filter für Trending-Märkte (bisherige Logik)
            if direction == "long":
                if alignment < 0:  # Gegensignal
                    score *= 0.3
                    signals.append("⚠ MTF contra-signal — score reduced 70%")
                elif alignment < 0.5:  # Teilweise aligned
                    score *= 0.6
                    signals.append("⚠ MTF partially aligned — score reduced 40%")
            elif direction == "short":
                if alignment > 0:
                    score *= 0.3
                    signals.append("⚠ MTF contra-signal — score reduced 70%")
                elif alignment > -0.5:
                    score *= 0.6
                    signals.append("⚠ MTF partially aligned — score reduced 40%")
        
        score = round(max(-100, min(100, score)), 1)
        
        return {
            "score": score,
            "direction": "long" if score > 10 else "short" if score < -10 else "neutral",
            "conviction": round(min(1.0, abs(score) / 100.0), 2),
            "signals": signals,
            "mtf_aligned": mtf.get("aligned_long") or mtf.get("aligned_short"),
        }

    async def _report_health(self, source: str, status: str, latency: float):
        """Meldet Status an den globalen Redis-Health-Hub."""
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.deps.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.deps.redis.set_cache("bruno:health:sources", current_map)

    async def process(self) -> None:
        """Hauptzyklus (60s)."""
        try:
            start_time = time.perf_counter()
            
            # 0. Regime aus Redis lesen (für MTF-Filter)
            grss_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
            regime = grss_data.get("_regime_hint", "ranging")
            
            # 1. Multi-Timeframe Candles laden
            candles_1m = await self._fetch_candles("1 minute", limit=720)
            candles_5m = await self._fetch_candles("5 minutes", limit=60)
            candles_15m = await self._fetch_candles("15 minutes", limit=96)
            candles_1h = await self._fetch_candles("1 hour", limit=200)
            candles_4h = await self._fetch_candles("4 hours", limit=100)
            
            price = candles_1h[-1]["close"] if candles_1h else 0.0
            if price <= 0:
                await self._report_health("TA_Engine", "no_data", 0.0)
                return
            
            # 2. Indikatoren (alle auf 1h primär)
            ema_9   = self._calc_ema(candles_1h, 9)
            ema_21  = self._calc_ema(candles_1h, 21)
            ema_50  = self._calc_ema(candles_1h, 50)
            ema_200 = self._calc_ema(candles_1h, 200)
            rsi_14  = self._calc_rsi(candles_1h, 14)
            vwap    = self._calc_vwap(candles_15m)
            atr_14  = self._calc_atr(candles_1h, 14)
            
            # 3. Multi-Timeframe EMA-Alignment
            mtf = self._check_mtf_alignment(candles_5m, candles_15m, candles_1h, candles_4h)
            
            # 4. Trend-Klassifikation
            trend = self._classify_trend(candles_1h, ema_9, ema_21, ema_50, ema_200)
            
            # 5. Support/Resistance
            sr_levels = self._detect_sr_levels(candles_1h, candles_4h, price)

            # 5b. Volume Profile (VPOC) als primäres S/R-Level
            volume_profile = self._calc_volume_profile(candles_1m or candles_1h)
            vpoc_price = float(volume_profile.get("vpoc", 0.0) or 0.0)
            if vpoc_price > 0:
                sr_levels = [{
                    "price": round(vpoc_price, 2),
                    "type": "support" if vpoc_price <= price else "resistance",
                    "strength": 5,
                    "distance_pct": round((vpoc_price - price) / price * 100, 2),
                    "source": "vpoc",
                }] + sr_levels
            
            # 6. Breakout-Proximity
            breakout = self._check_breakout_proximity(price, sr_levels, atr_14)
            
            # 7. Volume-Analyse
            volume = self._analyze_volume(candles_1h)
            
            # 8. Wick-Detection
            wick = self._detect_wick(candles_5m)
            
            # 9. Session-Awareness
            session = self._get_session_context()
            
            # 10. Orderbuch-Walls
            ob_walls = await self._fetch_orderbook_walls(price)
            
            # 12. NEU: 15m Delta Bars mit Absorption
            delta_analysis = self._calc_15m_delta_bars(candles_15m)
            
            # 13. TA-Score
            ta_score = self._calculate_ta_score(trend, rsi_14, sr_levels, breakout,
                                                 volume, price, ema_9, ema_21, vwap, mtf, wick, regime, session)
            
            # 13. Snapshot → Redis
            snapshot = {
                "symbol": "BTCUSDT", "price": price,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ema_9": ema_9, "ema_21": ema_21, "ema_50": ema_50, "ema_200": ema_200,
                "rsi_14": rsi_14, "vwap": vwap, "atr_14": atr_14,
                "trend": trend, "sr_levels": sr_levels, "breakout": breakout,
                "volume": volume, "mtf": mtf, "wick": wick, "session": session,
                "ob_walls": ob_walls, "ta_score": ta_score,
                # NEU: Institutionelle Alpha-Indikatoren
                "volume_profile": volume_profile,
                "delta_analysis": delta_analysis,
                "regime_used": regime,  # Für Debugging
            }
            
            # Fix datetime serialization
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(repr(obj) + " is not JSON serializable")
            
            import json
            snapshot_json = json.dumps(snapshot, default=datetime_handler)
            await self.deps.redis.redis.setex("bruno:ta:snapshot", 300, snapshot_json)
            
            # NEU: Orderbuch-Walls auch separat für LiquidityEngine + ExecutionAgent
            await self.deps.redis.set_cache("bruno:ta:ob_walls", ob_walls, ttl=60)
            
            latency = (time.perf_counter() - start_time) * 1000
            await self._report_health("TA_Engine", "online", latency)
            
            self.logger.debug(f"TA Snapshot aktualisiert: Score={ta_score['score']}, Price={price:.0f}")
            
        except Exception as e:
            self.logger.error(f"TechnicalAnalysisAgent Prozess Fehler: {e}", exc_info=True)
            await self._report_health("TA_Engine", "error", 0.0)
