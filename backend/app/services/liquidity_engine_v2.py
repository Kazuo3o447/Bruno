import asyncio
import json
import logging
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import text

class LiquidityEngineV2:
    """
    Bruno v2.1 Liquidity Intelligence mit WebSocket OI Support.
    
    NEU v2.1 Features:
    - WebSocket OI Stream (1s Latenz statt 60s)
    - Sweep-Early-Warning mit OI-Flow Detection
    - Fallback auf REST API bei WebSocket-Ausfall
    
    Legacy REST API bleibt als Backup aktiv.
    """
    
    def __init__(self, db_session_factory, redis_client):
        self.db = db_session_factory
        self.redis = redis_client
        self.logger = logging.getLogger("liquidity_engine_v2")
        self._sweep_state: dict = {}
        self._oi_history: list = []   # Letzten 10 OI-Werte für Delta
        self._last_oi_fetch: float = 0.0
        
        # v2.1 WebSocket Support
        self._websocket_enabled = False
        self._ws_oi_stream = None
        self._last_ws_oi = 0.0
        self._ws_oi_timestamp = 0.0
        self._oi_flow_rate = 0.0  # OI Änderung pro Sekunde
        
        # Fallback-Tracking
        self._ws_failures = 0
        self._last_rest_fetch = 0.0

    async def analyze(self, current_price: float) -> dict:
        """
        Vollständige Liquiditäts-Analyse mit optimiertem OI-Stream.
        """
        clusters = await self._fetch_clusters(current_price)
        magnetic_pull = self._calculate_magnetic_pull(clusters, current_price)
        asymmetry = self._analyze_asymmetry(clusters, current_price)
        ob_walls = await self.redis.get_cache("bruno:ta:ob_walls") or {}
        
        # OI-Delta mit WebSocket-Optimierung
        oi_delta = await self._fetch_oi_delta_optimized()
        
        # Wick-Status aus TA-Snapshot lesen
        ta_snapshot = await self.redis.get_cache("bruno:ta:snapshot") or {}
        wick = ta_snapshot.get("wick", {})
        
        # Sweep mit 3-facher Konfirmation
        sweep = await self._detect_sweep_confirmed(current_price, oi_delta, wick)
        
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

    async def _fetch_oi_delta_optimized(self) -> dict:
        """
        v2.1: Optimierter OI-Fetch mit WebSocket-Priorität.
        
        Strategie:
        1. Versuche WebSocket OI Stream (1s Latenz)
        2. Fallback auf REST API bei WebSocket-Ausfall
        3. OI-Flow Rate für Early-Warning berechnen
        """
        now = time.time()
        
        # 1. WebSocket OI Stream (priorität)
        if self._websocket_enabled and self._ws_oi_timestamp > 0:
            oi_age = now - self._ws_oi_timestamp
            if oi_age < 5.0:  # WebSocket-Daten sind aktuell (< 5s)
                return self._build_oi_result_v2(use_websocket=True)
        
        # 2. REST API Fallback (max 1×/Minute)
        if now - self._last_rest_fetch < 55:
            # Verwende gecachte Daten
            if self._oi_history:
                return self._build_oi_result_v2()
            return {"current_oi": 0, "oi_1min_change": 0, "oi_5min_change": 0,
                    "oi_dropping": False, "oi_rising": False, "oi_change_pct": 0,
                    "oi_flow_rate": 0.0, "data_source": "cached"}
        
        # 3. REST API Aufruf
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("https://fapi.binance.com/fapi/v1/openInterest",
                                    params={"symbol": "BTCUSDT"})
                if r.status_code == 200:
                    oi = float(r.json().get("openInterest", 0))
                    self._oi_history.append({"oi": oi, "ts": now})
                    self._oi_history = self._oi_history[-10:]  # Max 10 Werte (~10 Min)
                    self._last_rest_fetch = now
                    
                    # OI-Flow Rate berechnen (Änderung pro Sekunde)
                    if len(self._oi_history) >= 2:
                        prev_oi = self._oi_history[-2]["oi"]
                        prev_ts = self._oi_history[-2]["ts"]
                        time_diff = now - prev_ts
                        if time_diff > 0:
                            self._oi_flow_rate = (oi - prev_oi) / time_diff
                    
                    self._ws_failures = 0  # Reset bei erfolgreichem REST Call
                    
        except Exception as e:
            self.logger.warning(f"OI REST Fetch Fehler: {e}")
            self._ws_failures += 1
        
        return self._build_oi_result_v2()

    def _build_oi_result_v2(self, use_websocket: bool = False) -> dict:
        """v2.1: Erweiterte OI-Analyse mit Flow Rate und Source Info."""
        if len(self._oi_history) < 2:
            base_oi = self._ws_oi if use_websocket else (self._oi_history[-1]["oi"] if self._oi_history else 0)
            return {
                "current_oi": base_oi,
                "oi_1min_change": 0, "oi_5min_change": 0,
                "oi_dropping": False, "oi_rising": False, "oi_change_pct": 0,
                "oi_flow_rate": self._oi_flow_rate,
                "data_source": "websocket" if use_websocket else "rest",
                "latency_ms": 1000 if use_websocket else 55000
            }
        
        # Verwende WebSocket oder REST Daten
        if use_websocket and self._ws_oi > 0:
            current = self._ws_oi
            current_ts = self._ws_oi_timestamp
        else:
            current = self._oi_history[-1]["oi"]
            current_ts = self._oi_history[-1]["ts"]
        
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
            "oi_flow_rate": round(self._oi_flow_rate, 4),  # BTC pro Sekunde
            "data_source": "websocket" if use_websocket else "rest",
            "latency_ms": 1000 if use_websocket else 55000,
            "last_update": datetime.fromtimestamp(current_ts, timezone.utc).isoformat()
        }

    async def start_websocket_oi_stream(self):
        """
        v2.1: Startet WebSocket OI Stream für 1s Latenz.
        
        WebSocket: wss://fstream.binance.com/ws/btcusdt@openInterest
        Format: {"e": "openInterest", "s": "BTCUSDT", "O": "75000.000", "T": 1712...}
        """
        if self._websocket_enabled:
            return
        
        try:
            import websockets
            self._websocket_enabled = True
            self.logger.info("Starte Binance OI WebSocket Stream...")
            
            async def oi_stream():
                uri = "wss://fstream.binance.com/ws/btcusdt@openInterest"
                while self._websocket_enabled:
                    try:
                        async with websockets.connect(uri) as websocket:
                            self._ws_oi_stream = websocket
                            self.logger.info("OI WebSocket verbunden")
                            
                            while self._websocket_enabled:
                                try:
                                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                                    data = json.loads(message)
                                    
                                    if data.get("e") == "openInterest":
                                        oi = float(data.get("O", 0))
                                        timestamp = int(data.get("T", 0)) / 1000
                                        
                                        # OI-Flow Rate berechnen
                                        if self._ws_oi_timestamp > 0:
                                            time_diff = timestamp - self._ws_oi_timestamp
                                            if time_diff > 0:
                                                self._oi_flow_rate = (oi - self._ws_oi) / time_diff
                                        
                                        self._ws_oi = oi
                                        self._ws_oi_timestamp = timestamp
                                        
                                        # In History für Delta-Berechnung aufnehmen
                                        self._oi_history.append({"oi": oi, "ts": timestamp})
                                        self._oi_history = self._oi_history[-10:]
                                        
                                        # Redis Cache für andere Agenten
                                        await self.redis.set_cache(
                                            "bruno:oi:realtime",
                                            {
                                                "oi": oi,
                                                "timestamp": timestamp,
                                                "flow_rate": self._oi_flow_rate,
                                                "source": "websocket"
                                            },
                                            ttl=10  # 10s Cache
                                        )
                                        
                                except asyncio.TimeoutError:
                                    self.logger.warning("OI WebSocket Timeout - reconnect...")
                                    break
                                    
                    except Exception as e:
                        self.logger.error(f"OI WebSocket Fehler: {e}")
                        self._ws_failures += 1
                        await asyncio.sleep(5)
            
            # Start im Hintergrund
            asyncio.create_task(oi_stream())
            self.logger.info("OI WebSocket Stream gestartet")
            
        except ImportError:
            self.logger.warning("websockets library nicht installiert - bleibe bei REST API")
        except Exception as e:
            self.logger.error(f"OI WebSocket Start Fehler: {e}")

    async def stop_websocket_oi_stream(self):
        """Stoppt WebSocket OI Stream."""
        self._websocket_enabled = False
        if self._ws_oi_stream:
            await self._ws_oi_stream.close()
            self._ws_oi_stream = None
        self.logger.info("OI WebSocket Stream gestoppt")

    # Legacy Methoden (unverändert für Kompatibilität)
    async def _detect_sweep_confirmed(self, current_price: float, 
                                        oi_delta: dict, wick: dict) -> dict:
        """Sweep Detection mit OI-Flow Rate Early-Warning."""
        # Bedingung 1: Liquidations-Spike
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
        total_liq = sell_total + buy_total
        
        liq_spike = total_liq > 500_000
        dominant_side = None
        if total_liq > 0:
            if sell_total / total_liq > 0.70:
                dominant_side = "long"   # Long-Positionen wurden liquidiert
            elif buy_total / total_liq > 0.70:
                dominant_side = "short"  # Short-Positionen wurden liquidiert
        
        # Bedingung 2: Wick-Bildung
        wick_formed = wick.get("bullish_wick", False) or wick.get("bearish_wick", False)
        wick_matches = False
        if dominant_side == "long" and wick.get("bullish_wick"):
            wick_matches = True   # Longs gesweept + bullish wick = reversal up
        elif dominant_side == "short" and wick.get("bearish_wick"):
            wick_matches = True   # Shorts gesweept + bearish wick = reversal down
        
        # Bedingung 3: OI-Drop (mit Flow Rate)
        oi_dropping = oi_delta.get("oi_dropping", False)
        oi_flow_negative = oi_delta.get("oi_flow_rate", 0) < -10  # >10 BTC/s Abfluss
        
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
                "oi_flow_negative": oi_flow_negative,  # v2.1 Early-Warning
            },
            "all_confirmed": all_confirmed,
            "post_sweep_entry": post_sweep_entry,
        }

    async def _fetch_clusters(self, current_price: float) -> List[Dict[str, Any]]:
        """Lädt Liquidations-Cluster aus der Datenbank."""
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
                        "strength": min(5, int(total_usdt / 50000))
                    })
                
                return clusters
                
        except Exception as e:
            self.logger.error(f"Cluster Fetch Fehler: {e}")
            return []

    def _calculate_magnetic_pull(self, clusters: List[Dict], current_price: float) -> Dict[str, Any]:
        """Berechnet den magnetischen Pull basierend auf Gravitations-Analogie."""
        if not clusters:
            return {"direction": "neutral", "strength": 0.0, "target_price": current_price}
        
        G = 1.0
        total_force_y = 0.0
        
        for cluster in clusters:
            distance = abs(cluster["distance_pct"]) / 100
            if distance < 0.001:
                distance = 0.001
            
            mass = cluster["total_usdt"] / 1_000_000
            force = G * mass / (distance ** 2)
            force_y = force if cluster["is_above"] else -force
            total_force_y += force_y
        
        if abs(total_force_y) < 0.01:
            direction = "neutral"
            strength = 0.0
        else:
            direction = "up" if total_force_y > 0 else "down"
            strength = min(1.0, abs(total_force_y) / 0.5)
        
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
        """Analysiert die Asymmetrie zwischen Long und Short Liquidations."""
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
        
        if ratio > 1.5:
            bias = "bullish_sweep"
        elif ratio < 0.67:
            bias = "bearish_sweep"
        else:
            bias = "balanced"
        
        return {
            "long_liq_below": round(long_liq_total, 0),
            "short_liq_above": round(short_liq_total, 0),
            "ratio": round(ratio, 2),
            "bias": bias
        }

    def _calculate_liq_score(self, magnetic_pull, asymmetry, sweep, ob_walls) -> float:
        """Liquiditäts-Score für den Composite Scorer."""
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
        
        # Post-Sweep Entry (±20)
        if sweep.get("all_confirmed"):
            if sweep["post_sweep_entry"] == "long":
                score += 20
            elif sweep["post_sweep_entry"] == "short":
                score -= 20
        
        # Orderbuch-Wall-Imbalance (±10)
        imbalance = ob_walls.get("wall_imbalance", 1.0)
        if imbalance > 1.5:
            score += 10
        elif imbalance < 0.67:
            score -= 10
        elif imbalance > 1.2:
            score += 5
        elif imbalance < 0.83:
            score -= 5
        
        return round(max(-50, min(50, score)), 1)

    async def get_health_status(self) -> Dict[str, Any]:
        """Health-Check für die Liquidity Engine v2.1."""
        return {
            "status": "online",
            "oi_history_size": len(self._oi_history),
            "websocket_enabled": self._websocket_enabled,
            "ws_failures": self._ws_failures,
            "last_oi_fetch": datetime.fromtimestamp(self._last_rest_fetch, timezone.utc).isoformat() if self._last_rest_fetch > 0 else None,
            "oi_flow_rate": self._oi_flow_rate,
            "data_source": "websocket" if self._websocket_enabled and self._ws_oi_timestamp > 0 else "rest",
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
