"""
ATR Calculator — Bruno Trading Bot

Average True Range für dynamisches Position Sizing und Stop-Loss.

Ohne ATR: Stop-Loss ist immer 1.0% — egal ob Markt ruhig oder extrem volatil.
Mit ATR: Stop-Loss und Positionsgröße passen sich dem aktuellen Risikoumfeld an.

Daten: Aus TimescaleDB (market_candles — bereits von IngestionAgent befüllt).
Intervall: 1h Candles, Periode 14.
"""

import logging
from typing import Optional
from sqlalchemy import text

logger = logging.getLogger("atr_calculator")


class ATRCalculator:

    def __init__(self, db_session_factory):
        self.db = db_session_factory
        self._atr_14: float = 0.0
        self._atr_baseline: float = 0.0  # 90-Tage-Durchschnitt

    async def calculate_atr(self, symbol: str = "BTCUSDT",
                             period: int = 14) -> float:
        """
        Berechnet ATR(14) aus 1h-Candles in TimescaleDB.
        Gibt ATR als absoluten USD-Wert zurück.
        """
        try:
            query = text("""
                WITH candles AS (
                    SELECT
                        time,
                        high,
                        low,
                        close,
                        LAG(close) OVER (ORDER BY time) AS prev_close
                    FROM market_candles
                    WHERE symbol = :symbol
                      AND time > NOW() - INTERVAL '48 hours'
                    ORDER BY time DESC
                    LIMIT :period
                ),
                true_ranges AS (
                    SELECT
                        GREATEST(
                            high - low,
                            ABS(high - COALESCE(prev_close, close)),
                            ABS(low - COALESCE(prev_close, close))
                        ) AS tr
                    FROM candles
                    WHERE prev_close IS NOT NULL
                )
                SELECT AVG(tr) AS atr
                FROM true_ranges
            """)

            async with self.db() as session:
                result = await session.execute(
                    query,
                    {"symbol": symbol, "period": period}
                )
                row = result.fetchone()
                if row and row[0]:
                    self._atr_14 = float(row[0])
                    return self._atr_14

        except Exception as e:
            logger.warning(f"ATR Berechnung Fehler: {e}")

        return self._atr_14  # Cache-Wert wenn DB-Fehler

    async def calculate_atr_baseline(self,
                                      symbol: str = "BTCUSDT") -> float:
        """
        90-Tage-Durchschnitt des ATR(14) als Baseline.
        Wird täglich berechnet (Cache reicht).
        """
        try:
            query = text("""
                WITH daily_atr AS (
                    SELECT
                        DATE_TRUNC('day', time) AS day,
                        AVG(
                            GREATEST(
                                high - low,
                                ABS(high - LAG(close) OVER (ORDER BY time)),
                                ABS(low - LAG(close) OVER (ORDER BY time))
                            )
                        ) AS daily_avg_tr
                    FROM market_candles
                    WHERE symbol = :symbol
                      AND time > NOW() - INTERVAL '90 days'
                    GROUP BY day
                )
                SELECT AVG(daily_avg_tr) AS baseline
                FROM daily_atr
            """)

            async with self.db() as session:
                result = await session.execute(query, {"symbol": symbol})
                row = result.fetchone()
                if row and row[0]:
                    self._atr_baseline = float(row[0])
                    return self._atr_baseline

        except Exception as e:
            logger.warning(f"ATR Baseline Fehler: {e}")

        return self._atr_baseline

    def get_volatility_multiplier(self) -> float:
        """
        Gibt Positions-Größen-Multiplikator basierend auf ATR-Ratio zurück.
        ATR-Ratio = aktuelle ATR / historische Baseline ATR

        Ruhiger Markt (ratio < 0.8): volle Größe
        Normaler Markt (ratio 0.8–1.2): leicht reduziert
        Hohe Vola (ratio 1.8–2.5): stark reduziert
        Extreme Vola (ratio > 2.5): minimal (Feb 2026 Szenario)
        """
        if self._atr_baseline <= 0:
            return 1.0  # Kein Baseline — neutral

        ratio = self._atr_14 / self._atr_baseline

        if ratio < 0.8:     return 1.0
        elif ratio < 1.2:   return 0.8
        elif ratio < 1.8:   return 0.6
        elif ratio < 2.5:   return 0.4
        else:               return 0.25   # Feb 2026: DVOL 95%, ATR 3×

    def get_dynamic_stop_loss(self, base_sl_pct: float,
                               current_price: float) -> float:
        """
        Dynamischer Stop-Loss basierend auf ATR.
        Minimum: base_sl_pct
        Maximum: base_sl_pct * 2.0 (nie zu weit)
        """
        if self._atr_14 <= 0 or current_price <= 0:
            return base_sl_pct

        atr_pct = self._atr_14 / current_price
        dynamic_sl = max(base_sl_pct, atr_pct * 1.5)
        return min(dynamic_sl, base_sl_pct * 2.0)
