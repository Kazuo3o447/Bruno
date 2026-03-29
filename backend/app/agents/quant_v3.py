import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import text
from typing import Dict, Any, Optional, List
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import PublicExchangeClient

class QuantAgent(PollingAgent):
    """
    Phase 6: HFT-Quant Agent (Mikro-Struktur).
    Berechnet OFI, VAMP und CVD auf Basis echter Exchange-Daten.
    Refined: PublicExchangeClient Isolation & Signal Generation.
    """
    def __init__(self, deps: AgentDependencies, symbol: str = "BTCUSDT"):
        super().__init__("quant", deps)
        self.symbol = symbol
        self.cvd_cumulative = 0.0
        self.exm = PublicExchangeClient(redis=deps.redis)
        self.prev_ob = None
        self.ofi_threshold = 500.0 # Schwellenwert für Signale
        
    async def setup(self) -> None:
        self.logger.info(f"QuantAgent für {self.symbol} gestartet.")

        # CVD-State aus Redis laden (überlebt Restarts)
        cvd_cached = await self.deps.redis.get_cache("bruno:cvd:BTCUSDT")
        if cvd_cached:
            self.cvd_cumulative = float(cvd_cached.get("value", 0.0))
            self.logger.info(f"CVD State aus Redis geladen: {self.cvd_cumulative:.2f}")
        else:
            self.cvd_cumulative = 0.0
            self.logger.info("CVD State: Kein Cache — starte bei 0.0")

        await self.deps.redis.set_cache(
            "bruno:cvd:BTCUSDT",
            {
                "value": self.cvd_cumulative,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            ttl=86400
        )

        self.prev_ob = None

    def get_interval(self) -> float:
        """5-Minuten-Intervall für Medium-Frequency (kein HFT)."""
        return 300.0

    async def teardown(self) -> None:
        await self.exm.close()
        await super().teardown()

    async def _report_health(self, source: str, status: str, latency: float):
        """Meldet Status und Latenz an den globalen Redis-Hub."""
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.deps.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.deps.redis.set_cache("bruno:health:sources", current_map)

    def _calculate_ofi(self, current_ob: Dict) -> float:
        """Berechnet den Order Flow Imbalance (OFI) basierend auf dem Vorzustand."""
        if not self.prev_ob:
            self.prev_ob = current_ob
            return 0.0
        
        # Best Bid
        p_b, v_b = current_ob['bids'][0][0], current_ob['bids'][0][1]
        p_b_prev, v_b_prev = self.prev_ob['bids'][0][0], self.prev_ob['bids'][0][1]
        
        wif_b = v_b if p_b > p_b_prev else (v_b - v_b_prev if p_b == p_b_prev else -v_b_prev)
        
        # Best Ask
        p_a, v_a = current_ob['asks'][0][0], current_ob['asks'][0][1]
        p_a_prev, v_a_prev = self.prev_ob['asks'][0][0], self.prev_ob['asks'][0][1]
        
        wif_a = -v_a if p_a < p_a_prev else (v_a_prev - v_a if p_a == p_a_prev else v_a_prev)
        
        ofi = wif_b - wif_a
        self.prev_ob = current_ob
        return ofi

    async def _get_liquidation_walls(self) -> List[Dict]:
        """Aggregiert Liquidations-Cluster via SQL (Rounding -2)."""
        start = time.perf_counter()
        query = text("""
            SELECT ROUND(price, -2) as zone, SUM(total_usdt) as amount 
            FROM liquidations 
            WHERE symbol = :symbol AND time > NOW() - INTERVAL '24 hours' 
            GROUP BY zone 
            HAVING SUM(total_usdt) > 100000
            ORDER BY amount DESC
        """)
        try:
            async with self.deps.db_session_factory() as session:
                result = await session.execute(query, {"symbol": self.symbol})
                latency = (time.perf_counter() - start) * 1000
                await self._report_health("Liquidation_Cluster_SQL", "online", latency)
                return [{"zone": float(row[0]), "amount": float(row[1])} for row in result.fetchall()]
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("Liquidation_Cluster_SQL", "offline", latency)
            return []

    async def process(self) -> None:
        try:
            # 1. Redundantes L2-Orderbuch (Public)
            ob = await self.exm.fetch_order_book_redundant(self.symbol, limit=20)
            if not ob or not ob.get('bids') or not ob.get('asks'):
                return

            best_bid_p, best_bid_v = ob['bids'][0][0], ob['bids'][0][1]
            best_ask_p, best_ask_v = ob['asks'][0][0], ob['asks'][0][1]

            # 2. HFT Metriken
            vamp = (best_bid_p * best_ask_v + best_ask_p * best_bid_v) / (best_bid_v + best_ask_v)
            ofi = self._calculate_ofi(ob)
            
            # 3. CVD & Liq Walls
            start_trades = time.perf_counter()
            try:
                # Nutze binance öffentlich
                trades = await self.exm.binance.fetch_trades(self.symbol, limit=20)
                latency_trades = (time.perf_counter() - start_trades) * 1000
                delta_cvd = sum(t['amount'] if t['side'] == 'buy' else -t['amount'] for t in trades)
                self.cvd_cumulative += delta_cvd
                
                # CVD persistieren (überlebt Neustarts)
                await self.deps.redis.set_cache(
                    "bruno:cvd:BTCUSDT",
                    {
                        "value": self.cvd_cumulative,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    ttl=86400   # 24 Stunden
                )
                
                await self._report_health("Binance_Trades", "online", latency_trades)
            except Exception:
                await self._report_health("Binance_Trades", "offline", 0.0)

            liq_walls = await self._get_liquidation_walls()

            # 4. Payload & Signal Generation
            payload = {
                "symbol": self.symbol,
                "price": best_bid_p,
                "VAMP": round(vamp, 2),
                "CVD": round(self.cvd_cumulative, 2),
                "OFI": round(ofi, 2),
                "Liquidation_Walls": liq_walls,
                "Source": ob.get('source', 'unknown'),
                "latency_ms": ob.get('latency_ms', 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            await self.deps.redis.set_cache("bruno:quant:micro", payload)
            
            # SIGNAL GENERATION + LLM CASCADE (Phase C)
            if abs(ofi) >= self.ofi_threshold:
                side = "buy" if ofi > 0 else "sell"
                signal = {
                    "symbol": self.symbol,
                    "side": side,
                    "amount": 0.001,
                    "ofi": ofi,
                    "price": best_bid_p,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                # ── LLM Cascade (Phase C) ────────────────────────────────
                # Cascade läuft nach dem OFI-Gate.
                # Bei HOLD: Signal wird nicht gesendet.
                # Bei BUY/SELL: Signal wird mit LLM-Kontext angereichert.
                grss_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
                grss_score = grss_data.get("score", 0.0)
                grss_components = grss_data.get("components", {})

                # GRSS-Gate — bevor überhaupt der LLM läuft
                from app.services.regime_config_v2 import REGIME_CONFIGS
                # Minimaler Threshold vor Regime-Detection: 40
                if grss_score < 40:
                    self.logger.info(
                        f"Signal blockiert: GRSS={grss_score:.1f} < 40 (Pre-Cascade Gate)"
                    )
                else:
                    # Cascade initialisieren (lazy — nur beim ersten Mal)
                    if not hasattr(self, "_llm_cascade"):
                        from app.llm import LLMCascade
                        self._llm_cascade = LLMCascade(self.deps.redis)
                        await self._llm_cascade.initialize()

                    market_context = {
                        **grss_components,
                        "btc_price": best_bid_p,
                        "ofi": ofi,
                        "vamp": vamp,
                        "cvd": self.cvd_cumulative,
                    }

                    cascade_result = await self._llm_cascade.run(
                        grss_components=grss_components,
                        market_context=market_context,
                        grss_score=grss_score,
                    )

                    if cascade_result.is_actionable:
                        # Signal mit LLM-Kontext anreichern
                        signal["side"] = cascade_result.decision.lower()
                        signal.update(cascade_result.to_signal_extras())
                        signal["grss"] = grss_score

                        await self.deps.redis.publish_message(
                            "bruno:pubsub:signals", json.dumps(signal)
                        )
                        self.logger.info(
                            f"Signal (Cascade): {cascade_result.decision} {self.symbol} "
                            f"| Regime={cascade_result.regime} "
                            f"| Conf={cascade_result.final_confidence:.2f} "
                            f"| {cascade_result.duration_ms:.0f}ms"
                        )
                    else:
                        self.logger.info(
                            f"Cascade HOLD (aborted_at={cascade_result.aborted_at}) "
                            f"| OFI-Signal unterdrückt"
                        )

        except Exception as e:
            self.logger.error(f"QuantAgent Fehler: {e}")
