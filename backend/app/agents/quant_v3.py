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
from app.core.llm_provider import OllamaProvider

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
        self._last_price: float = 0.0   # Für Decision Logging
        
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

    async def _fetch_ofi_rolling(self) -> dict:
        """
        Liest den akkumulierten OFI-Buffer aus dem IngestionAgent.
        Gibt semantisch auswertbare Metriken zurück — keinen rohen Absolutwert.
        """
        try:
            raw = await self.deps.redis.redis.lrange("market:ofi:ticks", 0, -1)
            if not raw or len(raw) < 10:
                return {"buy_pressure_ratio": 0.5, "mean_imbalance": 1.0, "tick_count": 0}

            import json as _json
            ratios = [_json.loads(t)["r"] for t in raw]
            mean_imb = sum(ratios) / len(ratios)
            buy_ticks = sum(1 for r in ratios if r > 1.0)

            return {
                "buy_pressure_ratio": round(buy_ticks / len(ratios), 3),  # 0.0=nur Verkauf, 1.0=nur Kauf
                "mean_imbalance": round(mean_imb, 4),                     # 1.0=neutral
                "tick_count": len(ratios)
            }
        except Exception as e:
            self.logger.warning(f"OFI Rolling Fetch Fehler: {e}")
            return {"buy_pressure_ratio": 0.5, "mean_imbalance": 1.0, "tick_count": 0}

    async def _log_decision(
        self,
        outcome: str,
        reason: str,
        grss: float = 0.0,
        price: float = 0.0,
        ofi_data: dict = None,
        cascade_result=None
    ) -> None:
        """
        Loggt jede Evaluierungs-Entscheidung in den Decision Feed.
        Schreibt nach bruno:decisions:feed (kompatibel mit /api/v1/decisions/feed).
        """
        ofi = (ofi_data or {}).get("buy_pressure_ratio", 0.5)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ofi": ofi,
            "ofi_met": True,                 # immer True — kein OFI-Gate mehr
            "grss": grss,
            "outcome": outcome,              # z.B. "PRE_GATE_HOLD", "CASCADE_L1_HOLD", "SIGNAL_BUY"
            "reason": reason,
            "regime": None,
            "layer1_confidence": None,
            "layer2_decision": None,
            "layer3_blocked": None,
            "price": price,
            # Zusätzliche Felder (additive, brechen kein bestehendes Frontend)
            "ofi_buy_pressure": ofi,
            "cascade_duration_ms": None,
        }

        if cascade_result is not None:
            aborted = cascade_result.aborted_at
            l1 = cascade_result.layer1 or {}
            l2 = cascade_result.layer2 or {}
            l3 = cascade_result.layer3 or {}
            entry.update({
                "regime": l1.get("regime"),
                "layer1_confidence": l1.get("confidence"),
                "layer2_decision": l2.get("decision"),
                "layer3_blocked": l3.get("blocker"),
                "cascade_duration_ms": round(cascade_result.duration_ms, 1),
            })

        try:
            import json as _json
            pipe = self.deps.redis.redis.pipeline()
            pipe.lpush("bruno:decisions:feed", _json.dumps(entry))
            pipe.ltrim("bruno:decisions:feed", 0, 143)  # 12h bei 300s Zyklen
            await pipe.execute()
        except Exception as e:
            self.logger.warning(f"Decision Log Fehler: {e}")

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
        """
        Zeitbasierte Marktbewertung (alle 300s).

        Paradigma: Evaluiere IMMER. Kein OFI-Gate. Kein GRSS-40-Gate.
        OFI ist Input für den LLM, nicht Trigger.
        Jeder Zyklus produziert einen Decision-Feed-Eintrag (HOLD oder Signal).
        """
        try:
            # ── 1. Orderbook (für VAMP und Preis) ──────────────────────────────
            ob = await self.exm.fetch_order_book_redundant(self.symbol, limit=20)
            if not ob or not ob.get("bids") or not ob.get("asks"):
                return

            best_bid_p = ob["bids"][0][0]
            best_bid_v = ob["bids"][0][1]
            best_ask_p = ob["asks"][0][0]
            best_ask_v = ob["asks"][0][1]
            self._last_price = best_bid_p

            # ── 2. VAMP (Volume-Adjusted Mid Price) ─────────────────────────────
            vamp = (best_bid_p * best_ask_v + best_ask_p * best_bid_v) / (best_bid_v + best_ask_v)

            # ── 3. CVD akkumulieren ─────────────────────────────────────────────
            start_trades = time.perf_counter()
            try:
                trades = await self.exm.binance.fetch_trades(self.symbol, limit=20)
                latency_trades = (time.perf_counter() - start_trades) * 1000
                delta_cvd = sum(t["amount"] if t["side"] == "buy" else -t["amount"] for t in trades)
                self.cvd_cumulative += delta_cvd
                await self.deps.redis.set_cache(
                    "bruno:cvd:BTCUSDT",
                    {"value": self.cvd_cumulative, "timestamp": datetime.now(timezone.utc).isoformat()},
                    ttl=86400
                )
                await self._report_health("Binance_Trades", "online", latency_trades)
            except Exception:
                await self._report_health("Binance_Trades", "offline", 0.0)

            # ── 4. Rolling OFI aus IngestionAgent-Buffer ────────────────────────
            ofi_data = await self._fetch_ofi_rolling()

            # ── 5. Liquidation Walls ────────────────────────────────────────────
            liq_walls = await self._get_liquidation_walls()

            # ── 6. Micro-Payload in Redis schreiben ─────────────────────────────
            payload = {
                "symbol": self.symbol,
                "price": best_bid_p,
                "VAMP": round(vamp, 2),
                "CVD": round(self.cvd_cumulative, 2),
                "OFI_Buy_Pressure": ofi_data["buy_pressure_ratio"],
                "OFI_Mean_Imbalance": ofi_data["mean_imbalance"],
                "OFI_Tick_Count": ofi_data["tick_count"],
                "Liquidation_Walls": liq_walls,
                "Source": ob.get("source", "unknown"),
                "latency_ms": ob.get("latency_ms", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.deps.redis.set_cache("bruno:quant:micro", payload)

            # ── 7. GRSS lesen (FIX: korrekte Key-Namen) ─────────────────────────
            grss_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
            grss_score = grss_data.get("GRSS_Score", 0.0)   # FIX: war "score" → FALSCH
            # grss_data ist selbst die Komponenten-Map (kein "components"-Sub-Key)

            # ── 8. Pre-Gate: nur absolute Extremfälle blockieren ─────────────────
            # GRSS < 20 = extremer Marktstress (VIX > 45 oder Systemausfall)
            # Normales "HOLD"-Verhalten entscheidet die LLM-Cascade selbst
            if grss_score < 20:
                reason = f"Pre-Gate: GRSS={grss_score:.1f} < 20 (Extremstress)"
                self.logger.info(reason)
                await self._log_decision("PRE_GATE_HOLD", reason, grss=grss_score,
                                         price=best_bid_p, ofi_data=ofi_data)
                return

            if not grss_data.get("Data_Freshness_Active", True):
                reason = "Pre-Gate: Keine validen Datenquellen verfügbar"
                self.logger.info(reason)
                await self._log_decision("PRE_GATE_HOLD", reason, grss=grss_score,
                                         price=best_bid_p, ofi_data=ofi_data)
                return

            # ── 9. LLM Cascade — immer ausführen ────────────────────────────────
            if not hasattr(self, "_llm_cascade"):
                from app.llm import LLMCascade
                llm_provider = OllamaProvider()
                self._llm_cascade = LLMCascade(self.deps.redis, llm_provider)
                await self._llm_cascade.initialize()

            # market_context enthält alle Daten für Layer 2 und 3
            market_context = {
                **grss_data,  # Alle GRSS-Komponenten (FIX: war immer leeres Dict)
                "btc_price": best_bid_p,
                "ofi_buy_pressure": ofi_data["buy_pressure_ratio"],
                "ofi_mean_imbalance": ofi_data["mean_imbalance"],
                "ofi_tick_count": ofi_data["tick_count"],
                "vamp": vamp,
                "cvd": self.cvd_cumulative,
                "liq_walls": liq_walls,
            }

            cascade_result = await self._llm_cascade.run(
                grss_components=grss_data,      # FIX: war immer leeres Dict
                market_context=market_context,
                grss_score=grss_score,
            )

            # ── 10. Outcome-Code ableiten ────────────────────────────────────────
            aborted = cascade_result.aborted_at
            if cascade_result.is_actionable:
                outcome = f"SIGNAL_{cascade_result.decision.upper()}"
            elif aborted == "grss_gate":
                outcome = "CASCADE_GRSS_HOLD"
            elif aborted == "gate1":
                outcome = "CASCADE_L1_HOLD"
            elif aborted == "gate2":
                outcome = "CASCADE_L2_HOLD"
            elif aborted == "gate3":
                outcome = "CASCADE_L3_BLOCK"
            else:
                outcome = "CASCADE_HOLD"

            reason = aborted or "cascade_completed"
            self.logger.info(
                f"Zyklus: {outcome} | GRSS={grss_score:.1f} "
                f"| OFI-Buy={ofi_data['buy_pressure_ratio']:.2f} "
                f"| Price={best_bid_p:,.0f}"
            )

            # ── 11. Immer loggen (auch HOLDs) ────────────────────────────────────
            await self._log_decision(
                outcome=outcome,
                reason=reason,
                grss=grss_score,
                price=best_bid_p,
                ofi_data=ofi_data,
                cascade_result=cascade_result,
            )

            # ── 12. Bei BUY/SELL → Signal publizieren ────────────────────────────
            if cascade_result.is_actionable:
                signal = {
                    "symbol": self.symbol,
                    "side": cascade_result.decision.lower(),
                    "amount": 0.001,
                    "price": best_bid_p,
                    "grss": grss_score,
                    "ofi_buy_pressure": ofi_data["buy_pressure_ratio"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **cascade_result.to_signal_extras(),
                }
                await self.deps.redis.publish_message(
                    "bruno:pubsub:signals", json.dumps(signal)
                )
                self.logger.info(
                    f"Signal publiziert: {cascade_result.decision} {self.symbol} "
                    f"| Regime={cascade_result.regime} "
                    f"| Conf={cascade_result.final_confidence:.2f} "
                    f"| {cascade_result.duration_ms:.0f}ms"
                )

        except Exception as e:
            self.logger.error(f"QuantAgent process() Fehler: {e}", exc_info=True)
