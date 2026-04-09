import asyncio
import json
import logging
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import text

class LiquidityEngine:
    """
    Liquidity Intelligence für Bruno v3.
    
    Analysiert:
    - Liquidations-Cluster aus DB (24h, historisch)
    - Orderbuch-Walls aus TA-Agent (live, depth=1000)
    - Magnetismus-Scoring (Gravitations-Analogie)
    - Sweep-Detection mit 3-facher Konfirmation:
        1. Liquidations-Spike (>$500k in 5 Min)
        2. Wick-Bildung (bullish/bearish Hammer — aus TA-Snapshot)
        3. OI-Delta negativ (Positionen werden geschlossen, nicht neu eröffnet)
    - Asymmetrie (Long vs Short Liq-Verteilung)
    - v3 sweep_signal: SSL/BSL Sweep + Reclaim (+30/-30)
    
    Wird vom QuantAgentV4 aufgerufen (kein eigenständiger Agent).
    Schreibt nach: bruno:liq:intelligence (Redis)
    """
    
    def __init__(self, db_session_factory, redis_client):
        self.db = db_session_factory
        self.redis = redis_client
        self.logger = logging.getLogger("liquidity_engine")
        self._sweep_state: dict = {}
        self._oi_history: list = []   # Letzten 10 OI-Werte für Delta
        self._last_oi_fetch: float = 0.0
        self._active_sweep_signals: list = []  # Stores active {side, score, expiry} signals

    async def analyze(self, current_price: float, liquidation_event: dict | None = None) -> dict:
        """
        Vollständige Liquiditäts-Analyse mit 3-facher Sweep-Konfirmation.
        """
        clusters = await self._fetch_clusters(current_price)
        magnetic_pull = self._calculate_magnetic_pull(clusters, current_price)
        asymmetry = self._analyze_asymmetry(clusters, current_price)
        ob_walls = await self.redis.get_cache("bruno:ta:ob_walls") or {}
        
        # OI-Delta
        oi_delta = await self._fetch_oi_delta()
        
        # Wick-Status aus TA-Snapshot lesen
        ta_snapshot = await self.redis.get_cache("bruno:ta:snapshot") or {}
        wick = ta_snapshot.get("wick", {})
        
        # Sweep mit 3-facher Konfirmation
        sweep = await self._detect_sweep_confirmed(
            current_price,
            oi_delta,
            wick,
            liquidation_event=liquidation_event,
            clusters=clusters
        )
        
        # Combined Liq-Score
        liq_score = self._calculate_liq_score(magnetic_pull, asymmetry, sweep, ob_walls)
        
        # Nearest clusters
        above = [c for c in clusters if c["is_above"]]
        below = [c for c in clusters if not c["is_above"]]
        nearest_above = min(above, key=lambda c: abs(c["distance_pct"]), default=None)
        nearest_below = min(below, key=lambda c: abs(c["distance_pct"]), default=None)
        
        return {
            "clusters": clusters,
            "nearest_above": nearest_above,
            "nearest_below": nearest_below,
            "magnetic_pull": magnetic_pull,
            "asymmetry": asymmetry,
            "ob_walls_merged": ob_walls,
            "oi_delta": oi_delta,
            "sweep": sweep,
            "liq_score": liq_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_oi_delta(self) -> dict:
        """Fetcht Open Interest von Binance und berechnet das minütliche Delta."""
        now = time.time()
        if now - self._last_oi_fetch < 55:
            if self._oi_history:
                return self._build_oi_result()
            return {"current_oi": 0, "oi_1min_change": 0, "oi_5min_change": 0,
                    "oi_dropping": False, "oi_rising": False, "oi_change_pct": 0}
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("https://fapi.binance.com/fapi/v1/openInterest",
                                    params={"symbol": "BTCUSDT"})
                if r.status_code == 200:
                    oi = float(r.json().get("openInterest", 0))
                    self._oi_history.append({"oi": oi, "ts": now})
                    self._oi_history = self._oi_history[-10:]
                    self._last_oi_fetch = now
        except Exception as e:
            self.logger.warning(f"OI Fetch Fehler: {e}")
        
        return self._build_oi_result()

    def _build_oi_result(self) -> dict:
        if len(self._oi_history) < 2:
            return {"current_oi": self._oi_history[-1]["oi"] if self._oi_history else 0,
                    "oi_1min_change": 0, "oi_5min_change": 0,
                    "oi_dropping": False, "oi_rising": False, "oi_change_pct": 0}
        
        current = self._oi_history[-1]["oi"]
        prev = self._oi_history[-2]["oi"]
        first = self._oi_history[0]["oi"]
        
        delta_1 = current - prev
        delta_5 = current - first
        pct_5 = (delta_5 / first * 100) if first > 0 else 0
        
        dropping = len(self._oi_history) >= 3 and all(
            self._oi_history[i]["oi"] < self._oi_history[i-1]["oi"]
            for i in range(-1, -3, -1) if abs(i) <= len(self._oi_history)
        )
        rising = len(self._oi_history) >= 3 and all(
            self._oi_history[i]["oi"] > self._oi_history[i-1]["oi"]
            for i in range(-1, -3, -1) if abs(i) <= len(self._oi_history)
        )
        
        return {
            "current_oi": round(current, 2),
            "oi_1min_change": round(delta_1, 2),
            "oi_5min_change": round(delta_5, 2),
            "oi_dropping": dropping,
            "oi_rising": rising,
            "oi_change_pct": round(pct_5, 3),
        }

    async def _detect_sweep_confirmed(
        self,
        current_price: float,
        oi_delta: dict,
        wick: dict,
        liquidation_event: dict | None = None,
        clusters: List[Dict] = None
    ) -> dict:
        """
        Sweep-Detection mit 3 Bedingungen + v3 sweep_signal.
        """
        event_total = float((liquidation_event or {}).get("total_usdt", 0.0) or 0.0)
        event_side = str((liquidation_event or {}).get("side", "")).upper()
        
        query = text("""
            SELECT side, SUM(total_usdt) AS total
            FROM liquidations
            WHERE symbol = :symbol AND time > NOW() - INTERVAL '5 minutes'
            GROUP BY side
        """)
        try:
            async with self.db() as session:
                result = await session.execute(query, {"symbol": "BTCUSDT"})
                rows = {row[0]: float(row[1]) for row in result.fetchall()}
        except Exception:
            rows = {}
        
        sell_total = rows.get("SELL", 0) # Long-Liqs
        buy_total = rows.get("BUY", 0)   # Short-Liqs

        if event_total >= 500_000:
            if event_side == "SELL": sell_total = max(sell_total, event_total)
            elif event_side == "BUY": buy_total = max(buy_total, event_total)

        total_liq = sell_total + buy_total
        liq_spike = total_liq > 500_000
        
        dominant_side = None
        if total_liq > 0:
            if sell_total / total_liq > 0.70: dominant_side = "long"
            elif buy_total / total_liq > 0.70: dominant_side = "short"
        
        wick_matches = False
        if dominant_side == "long" and wick.get("bullish_wick"): wick_matches = True
        elif dominant_side == "short" and wick.get("bearish_wick"): wick_matches = True
        
        oi_dropping = oi_delta.get("oi_dropping", False)
        all_confirmed = liq_spike and wick_matches and oi_dropping
        
        now = time.time()
        self._active_sweep_signals = [s for s in self._active_sweep_signals if s["expiry"] > now]
        
        sweep_signal_score = 0.0
        if all_confirmed:
            if dominant_side == "long":
                sweep_signal_score = 30.0
                self._active_sweep_signals.append({"side": "long", "score": 30.0, "expiry": now + 300})
            elif dominant_side == "short":
                sweep_signal_score = -30.0
                self._active_sweep_signals.append({"side": "short", "score": -30.0, "expiry": now + 300})
        
        if sweep_signal_score == 0 and self._active_sweep_signals:
            sweep_signal_score = self._active_sweep_signals[-1]["score"]

        post_sweep_entry = None
        if all_confirmed:
            post_sweep_entry = "long" if dominant_side == "long" else "short"
        
        return {
            "active": liq_spike,
            "side": dominant_side,
            "intensity": round(total_liq, 0),
            "confirmations": {
                "liq_spike": liq_spike,
                "wick_formed": wick_matches,
                "oi_dropping": oi_dropping,
            },
            "all_confirmed": all_confirmed,
            "post_sweep_entry": post_sweep_entry,
            "sweep_signal": sweep_signal_score,
        }

    async def _fetch_clusters(self, current_price: float) -> List[Dict[str, Any]]:
        """Lädt Liquidations-Cluster aus der Datenbank."""
        try:
            async with self.db() as session:
                query = text("""
                    SELECT 
                        ROUND(price / 200) * 200 AS zone,
                        SUM(total_usdt) AS total_usdt,
                        COUNT(*) AS count
                    FROM liquidations 
                    WHERE symbol = :symbol 
                    AND time > NOW() - INTERVAL '24 hours'
                    GROUP BY zone
                    HAVING SUM(total_usdt) > 100000
                    ORDER BY total_usdt DESC
                """)
                result = await session.execute(query, {"symbol": "BTCUSDT"})
                rows = result.fetchall()
                
                clusters = []
                for row in rows:
                    zone_price = float(row[0])
                    total_usdt = float(row[1])
                    distance_pct = (zone_price - current_price) / current_price * 100
                    clusters.append({
                        "zone_price": zone_price,
                        "total_usdt": total_usdt,
                        "distance_pct": distance_pct,
                        "is_above": zone_price > current_price,
                        "strength": min(5, int(total_usdt / 50000))
                    })
                return clusters
        except Exception as e:
            self.logger.error(f"Cluster Fetch Fehler: {e}")
            return []

    def _calculate_magnetic_pull(self, clusters: List[Dict], current_price: float) -> Dict[str, Any]:
        """Berechnet den magnetischen Pull."""
        if not clusters:
            return {"direction": "neutral", "strength": 0.0, "target_price": current_price}
        
        G = 1.0
        total_force_y = 0.0
        for cluster in clusters:
            distance = max(0.001, abs(cluster["distance_pct"]) / 100)
            mass = cluster["total_usdt"] / 1_000_000
            force = G * mass / (distance ** 2)
            total_force_y += force if cluster["is_above"] else -force
        
        if abs(total_force_y) < 0.01:
            direction, strength = "neutral", 0.0
        else:
            direction = "up" if total_force_y > 0 else "down"
            strength = min(1.0, abs(total_force_y) / 0.5)
        
        target_price = current_price
        if direction != "neutral":
            relevant = [c for c in clusters if (direction == "up" and c["is_above"]) or (direction == "down" and not c["is_above"])]
            if relevant: target_price = min(relevant, key=lambda c: abs(c["distance_pct"]))["zone_price"]
        
        return {"direction": direction, "strength": round(strength, 3), "target_price": round(target_price, 2)}

    def _analyze_asymmetry(self, clusters: List[Dict], current_price: float) -> Dict[str, Any]:
        """Analysiert die Asymmetrie."""
        long_liq = sum(c["total_usdt"] for c in clusters if not c["is_above"])
        short_liq = sum(c["total_usdt"] for c in clusters if c["is_above"])
        total_liq = long_liq + short_liq
        if total_liq == 0:
            return {"long_liq_below": 0.0, "short_liq_above": 0.0, "ratio": 1.0, "bias": "neutral"}
        ratio = long_liq / short_liq if short_liq > 0 else 999
        bias = "bullish_sweep" if ratio > 1.5 else "bearish_sweep" if ratio < 0.67 else "balanced"
        return {"long_liq_below": round(long_liq, 0), "short_liq_above": round(short_liq, 0), "ratio": round(ratio, 2), "bias": bias}

    def _calculate_liq_score(self, magnetic_pull, asymmetry, sweep, ob_walls) -> float:
        """Liquiditäts-Score für den Composite Scorer."""
        score = 0.0
        if magnetic_pull["direction"] == "up": score += 10 * magnetic_pull["strength"]
        elif magnetic_pull["direction"] == "down": score -= 10 * magnetic_pull["strength"]
        
        if asymmetry["bias"] == "bullish_sweep": score += 10
        elif asymmetry["bias"] == "bearish_sweep": score -= 10
        
        if sweep.get("all_confirmed"):
            score += 20 if sweep["post_sweep_entry"] == "long" else -20
            
        # Wall Imbalance
        imb = ob_walls.get("wall_imbalance", 1.0)
        if imb > 1.5: score += 10
        elif imb < 0.67: score -= 10
        
        # NEU: Nearest-Wall-Proximity (±5)
        # Wenn ein Wall in der Nähe ist, wird Preis davon angezogen/abgestoßen
        nearest_bid = ob_walls.get("nearest_bid_wall")
        nearest_ask = ob_walls.get("nearest_ask_wall")
        if nearest_bid and abs(nearest_bid.get("distance_pct", 99)) < 1.0:
            score += 5  # Starker Bid-Wall unter uns = Support = bullish
        if nearest_ask and abs(nearest_ask.get("distance_pct", 99)) < 1.0:
            score -= 5  # Starker Ask-Wall über uns = Resistance = bearish
        
        return round(max(-50, min(50, score)), 1)

    async def get_health_status(self) -> Dict[str, Any]:
        """Health-Check für die Liquidity Engine."""
        return {
            "status": "online",
            "oi_history_size": len(self._oi_history),
            "last_oi_fetch": datetime.fromtimestamp(self._last_oi_fetch, timezone.utc).isoformat() if self._last_oi_fetch > 0 else None,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
