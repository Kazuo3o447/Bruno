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
    Liquidity Intelligence für Bruno v2.
    
    Analysiert:
    - Liquidations-Cluster aus DB (24h, historisch)
    - Orderbuch-Walls aus TA-Agent (live, depth=1000)
    - Magnetismus-Scoring (Gravitations-Analogie)
    - Sweep-Detection mit 3-facher Konfirmation:
        1. Liquidations-Spike (>$500k in 5 Min)
        2. Wick-Bildung (bullish/bearish Hammer — aus TA-Snapshot)
        3. OI-Delta negativ (Positionen werden geschlossen, nicht neu eröffnet)
    - Asymmetrie (Long vs Short Liq-Verteilung)
    
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

    async def analyze(self, current_price: float, liquidation_event: dict | None = None) -> dict:
        """
        Vollständige Liquiditäts-Analyse mit 3-facher Sweep-Konfirmation.
        
        Returns: {
            "clusters": [...],
            "nearest_above": {...},
            "nearest_below": {...},
            "magnetic_pull": {"direction": str, "strength": float, "target_price": float},
            "asymmetry": {"long_liq_below": float, "short_liq_above": float, 
                          "ratio": float, "bias": str},
            "ob_walls_merged": {...},     # Orderbuch-Walls vom TA-Agent
            "sweep": {
                "active": bool,
                "side": "long" | "short" | None,
                "intensity": float,
                "confirmations": {         # NEU: 3-fache Konfirmation
                    "liq_spike": bool,     # ≥ $500k Liquidationen in 5 Min
                    "wick_formed": bool,   # Reversal-Kerze erkannt (aus TA-Snapshot)
                    "oi_dropping": bool,   # OI fällt (Positionen geschlossen)
                },
                "all_confirmed": bool,     # Alle 3 Bedingungen erfüllt
                "post_sweep_entry": "long" | "short" | None,
            },
            "liq_score": float,           # -50 bis +50
            "timestamp": str,
        }
        """
        clusters = await self._fetch_clusters(current_price)
        magnetic_pull = self._calculate_magnetic_pull(clusters, current_price)
        asymmetry = self._analyze_asymmetry(clusters, current_price)
        ob_walls = await self.redis.get_cache("bruno:ta:ob_walls") or {}
        
        # OI-Delta (NEU)
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
        """
        Fetcht Open Interest von Binance und berechnet das minütliche Delta.
        
        Logik (Profitrader): 
        - OI fällt bei Preisrückgang → Positionen werden gesweept → Reversal wahrscheinlich
        - OI steigt bei Preisrückgang → Neue Shorts werden eröffnet → Preis fällt weiter
        
        REST: GET https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT
        Response: {"openInterest": "75000.000", "symbol": "BTCUSDT", "time": 1712...}
        
        Rate-Limit: max. 1× pro Minute (self._last_oi_fetch Check)
        
        Rückgabe: {
            "current_oi": float,          # Aktuelles OI in BTC
            "oi_1min_change": float,      # Delta in BTC (letzte Minute)
            "oi_5min_change": float,      # Delta in BTC (letzte 5 Minuten)
            "oi_dropping": bool,          # True wenn OI in den letzten 2 Readings gefallen
            "oi_rising": bool,            # True wenn OI in den letzten 2 Readings gestiegen
            "oi_change_pct": float,       # %-Veränderung letzte 5 Min
        }
        """
        now = time.time()
        if now - self._last_oi_fetch < 55:  # Max 1×/Minute
            # Return cached
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
                    self._oi_history = self._oi_history[-10:]  # Max 10 Werte (~10 Min)
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
        
        # "Dropping" = mindestens 2 aufeinanderfolgende Rückgänge
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
    ) -> dict:
        """
        Erweiterte Sweep-Detection mit 3 Bedingungen (Profitrader-Regel):
        
        1. Liquidations-Spike: > $500k in 5 Minuten, > 70% eine Seite
        2. Wick-Bildung: Bullish/Bearish Hammer auf 5m-Chart (aus TA-Snapshot)
        3. OI-Drop: Open Interest fällt = Positionen werden GESCHLOSSEN, nicht neu eröffnet
        
        Entry NUR wenn alle 3 Bedingungen erfüllt sind.
        Begründung: "Falling Knife"-Schutz. Wenn OI bei einem Dump STEIGT,
        eröffnen aggressive Verkäufer neue Positionen → Preis fällt weiter.
        Nur wenn OI FÄLLT wurden Positionen tatsächlich gesweept → Reversal möglich.
        
        Post-Sweep Entry:
        - Long-Liqs gesweept (SELL-Liqs) + Bullish Wick + OI Drop → Entry LONG
        - Short-Liqs gesweept (BUY-Liqs) + Bearish Wick + OI Drop → Entry SHORT
        """
        # Bedingung 1: Liquidations-Spike
        event_total = float((liquidation_event or {}).get("total_usdt", 0.0) or 0.0)
        event_side = str((liquidation_event or {}).get("side", "")).upper()
        query = text("""
            SELECT side, SUM(total_usdt) AS total, COUNT(*) AS count
            FROM liquidations
            WHERE symbol = :symbol AND time > NOW() - INTERVAL '5 minutes'
            GROUP BY side
        """)
        try:
            async with self.db() as session:
                result = await session.execute(query, {"symbol": "BTCUSDT"})
                rows = {row[0]: {"total": float(row[1]), "count": int(row[2])} 
                        for row in result.fetchall()}
        except Exception:
            rows = {}
        
        sell_total = rows.get("SELL", {}).get("total", 0)  # Long-Liqs
        buy_total = rows.get("BUY", {}).get("total", 0)    # Short-Liqs

        if event_total >= 500_000:
            if event_side == "SELL":
                sell_total = max(sell_total, event_total)
            elif event_side == "BUY":
                buy_total = max(buy_total, event_total)

        total_liq = sell_total + buy_total
        
        liq_spike = total_liq > 500_000 or event_total >= 500_000
        dominant_side = None
        if total_liq > 0:
            if sell_total / total_liq > 0.70:
                dominant_side = "long"   # Long-Positionen wurden liquidiert
            elif buy_total / total_liq > 0.70:
                dominant_side = "short"  # Short-Positionen wurden liquidiert
        elif event_total >= 500_000:
            dominant_side = "long" if event_side == "SELL" else "short" if event_side == "BUY" else None
        
        # Bedingung 2: Wick-Bildung
        wick_formed = wick.get("bullish_wick", False) or wick.get("bearish_wick", False)
        wick_matches = False
        if dominant_side == "long" and wick.get("bullish_wick"):
            wick_matches = True   # Longs gesweept + bullish wick = reversal up
        elif dominant_side == "short" and wick.get("bearish_wick"):
            wick_matches = True   # Shorts gesweept + bearish wick = reversal down
        
        # Bedingung 3: OI-Drop
        oi_dropping = oi_delta.get("oi_dropping", False)
        
        # Alle 3 Bedingungen prüfen
        all_confirmed = liq_spike and wick_matches and oi_dropping
        
        # Post-Sweep Entry Richtung
        post_sweep_entry = None
        if all_confirmed:
            if dominant_side == "long":
                post_sweep_entry = "long"    # Longs gesweept → jetzt Long entry
            elif dominant_side == "short":
                post_sweep_entry = "short"   # Shorts gesweept → jetzt Short entry
        
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
        }

    async def _fetch_clusters(self, current_price: float) -> List[Dict[str, Any]]:
        """
        Lädt Liquidations-Cluster aus der Datenbank.
        Filter: >$100k, $200-Radius, 24h Lookback.
        """
        try:
            async with self.db() as session:
                query = text("""
                    SELECT 
                        ROUND(price / 200) * 200 AS zone,
                        SUM(total_usdt) AS total_usdt,
                        COUNT(*) AS count,
                        AVG(price) as avg_price,
                        MIN(price) as min_price,
                        MAX(price) as max_price
                    FROM liquidations 
                    WHERE symbol = :symbol 
                    AND time > NOW() - INTERVAL '24 hours'
                    AND total_usdt > 100000
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
                    count = int(row[2])
                    avg_price = float(row[3])
                    min_price = float(row[4])
                    max_price = float(row[5])
                    
                    # Berechne Distance und Position
                    distance_pct = (zone_price - current_price) / current_price * 100
                    is_above = zone_price > current_price
                    
                    clusters.append({
                        "zone_price": zone_price,
                        "total_usdt": total_usdt,
                        "count": count,
                        "avg_price": avg_price,
                        "min_price": min_price,
                        "max_price": max_price,
                        "distance_pct": distance_pct,
                        "is_above": is_above,
                        "strength": min(5, int(total_usdt / 50000))  # 1-5 basierend auf Volumen
                    })
                
                return clusters
                
        except Exception as e:
            self.logger.error(f"Cluster Fetch Fehler: {e}")
            return []

    def _calculate_magnetic_pull(self, clusters: List[Dict], current_price: float) -> Dict[str, Any]:
        """
        Berechnet den magnetischen Pull basierend auf Gravitations-Analogie.
        """
        if not clusters:
            return {"direction": "neutral", "strength": 0.0, "target_price": current_price}
        
        # Gravitationskonstante (angepasst für Liquidität)
        G = 1.0  # Einfache Konstante
        
        total_force_x = 0.0
        total_force_y = 0.0
        
        for cluster in clusters:
            distance = abs(cluster["distance_pct"]) / 100  # In Preis-Einheiten
            if distance < 0.001:  # Division by zero Schutz
                distance = 0.001
            
            # Masse = USDT Volumen / 1M für Skalierung
            mass = cluster["total_usdt"] / 1_000_000
            
            # Gravitationskraft: F = G * m1 * m2 / r²
            # Vereinfacht: F = G * mass / distance²
            force = G * mass / (distance ** 2)
            
            # Richtung (positiv = oben, negativ = unten)
            force_y = force if cluster["is_above"] else -force
            
            total_force_y += force_y
        
        # Bestimme dominante Richtung
        if abs(total_force_y) < 0.01:
            direction = "neutral"
            strength = 0.0
        else:
            direction = "up" if total_force_y > 0 else "down"
            strength = min(1.0, abs(total_force_y) / 0.5)  # Normalisiert auf 0-1
        
        # Target Price (nächste Zone in Richtung der Kraft)
        target_price = current_price
        if direction != "neutral":
            relevant_clusters = [c for c in clusters if 
                               (direction == "up" and c["is_above"]) or 
                               (direction == "down" and not c["is_above"])]
            if relevant_clusters:
                target_price = min(relevant_clusters, key=lambda c: abs(c["distance_pct"]))["zone_price"]
        
        return {
            "direction": direction,
            "strength": round(strength, 3),
            "target_price": round(target_price, 2),
            "total_force": round(total_force_y, 3)
        }

    def _analyze_asymmetry(self, clusters: List[Dict], current_price: float) -> Dict[str, Any]:
        """
        Analysiert die Asymmetrie zwischen Long und Short Liquidations.
        """
        long_liq_total = sum(c["total_usdt"] for c in clusters if not c["is_above"])
        short_liq_total = sum(c["total_usdt"] for c in clusters if c["is_above"])
        
        total_liq = long_liq_total + short_liq_total
        
        if total_liq == 0:
            return {
                "long_liq_below": 0.0,
                "short_liq_above": 0.0,
                "ratio": 1.0,
                "bias": "neutral"
            }
        
        ratio = long_liq_total / short_liq_total if short_liq_total > 0 else 999
        
        # Bias Bestimmung
        if ratio > 1.5:
            bias = "bullish_sweep"  # Mehr Longs liquidiert
        elif ratio < 0.67:
            bias = "bearish_sweep"  # Mehr Shorts liquidiert
        else:
            bias = "balanced"
        
        return {
            "long_liq_below": round(long_liq_total, 0),
            "short_liq_above": round(short_liq_total, 0),
            "ratio": round(ratio, 2),
            "bias": bias
        }

    def _calculate_liq_score(self, magnetic_pull, asymmetry, sweep, ob_walls) -> float:
        """
        Liquiditäts-Score für den Composite Scorer.
        Range: -50 bis +50
        
        Komponenten:
        - Magnetic Pull: ±10
        - Asymmetrie-Bias: ±10
        - Post-Sweep Entry (3× bestätigt): ±20 (stärkstes Signal!)
        - Orderbuch-Wall-Imbalance: ±10
        """
        score = 0.0
        
        # Magnetic Pull (±10)
        if magnetic_pull["direction"] == "up":
            score += 10 * magnetic_pull["strength"]
        elif magnetic_pull["direction"] == "down":
            score -= 10 * magnetic_pull["strength"]
        
        # Asymmetrie (±10)
        if asymmetry["bias"] == "bullish_sweep":
            score += 10
        elif asymmetry["bias"] == "bearish_sweep":
            score -= 10
        
        # Post-Sweep Entry — NUR wenn alle 3 bestätigt (±20)
        if sweep.get("all_confirmed"):
            if sweep["post_sweep_entry"] == "long":
                score += 20
            elif sweep["post_sweep_entry"] == "short":
                score -= 20
        elif sweep.get("active") and not sweep.get("all_confirmed"):
            # Sweep aktiv aber nicht bestätigt → leichtes Warning
            pass  # Kein Score-Beitrag — abwarten
        
        # Orderbuch-Wall-Imbalance (±10)
        imbalance = ob_walls.get("wall_imbalance", 1.0)
        if imbalance > 1.5:
            score += 10   # Mehr Bid-Walls = bullisch
        elif imbalance < 0.67:
            score -= 10   # Mehr Ask-Walls = bärisch
        elif imbalance > 1.2:
            score += 5
        elif imbalance < 0.83:
            score -= 5
        
        return round(max(-50, min(50, score)), 1)

    async def get_health_status(self) -> Dict[str, Any]:
        """Health-Check für die Liquidity Engine."""
        return {
            "status": "online",
            "oi_history_size": len(self._oi_history),
            "last_oi_fetch": datetime.fromtimestamp(self._last_oi_fetch, timezone.utc).isoformat() if self._last_oi_fetch > 0 else None,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
