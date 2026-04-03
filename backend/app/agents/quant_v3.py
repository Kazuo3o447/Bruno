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

        # Config-Cache (TTL = 30s) — vermeidet Disk-I/O pro Zyklus
        self._config_cache: dict = {}
        self._config_cache_ts: float = 0.0
        self._config_cache_ttl: float = 30.0

    def _load_config_value(self, key: str, default: float) -> float:
        """
        Lädt einen Wert aus config.json mit In-Memory-Caching (TTL 30s).
        Verhindert unnötigen Disk-I/O bei häufigen Aufrufen pro Zyklus.
        """
        import os, time as _time
        now = _time.monotonic()
        if not self._config_cache or (now - self._config_cache_ts) > self._config_cache_ttl:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))), "config.json"
            )
            try:
                with open(config_path, "r") as f:
                    self._config_cache = json.load(f)
                    self._config_cache_ts = now
            except Exception:
                pass  # Cache bleibt leer → Fallback auf defaults

        value = self._config_cache.get(key, default)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
        
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

    async def _record_phantom_trade(
        self,
        cascade_result,
        grss_score: float,
        price: float,
        ofi_data: dict,
    ) -> None:
        """
        Speichert einen hypothetischen Trade für HOLD-Entscheidungen.
        Wird nach PHANTOM_HOLD_DURATION_MINUTES ausgewertet (Preis-Outcome).

        Diese Daten gehen AUSSCHLIESSLICH in trade_debriefs mit trade_mode='phantom'.
        Kein Einfluss auf Portfolio, Capital, P&L oder Veto-Logik.
        """
        try:
            import uuid
            from datetime import timedelta

            hold_duration = int(self._load_config_value("PHANTOM_HOLD_DURATION_MINUTES", 240.0))
            phantom_id = str(uuid.uuid4())
            evaluate_at = (
                datetime.now(timezone.utc) + timedelta(minutes=hold_duration)
            ).isoformat()

            phantom = {
                "phantom_id": phantom_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "evaluate_at": evaluate_at,
                "entry_price": price,
                "grss_at_decision": grss_score,
                "regime": cascade_result.regime,
                "aborted_at": cascade_result.aborted_at,
                "layer1": cascade_result.layer1,
                "layer2": cascade_result.layer2,
                "ofi_buy_pressure": ofi_data.get("buy_pressure_ratio", 0),
                "ofi_mean_imbalance": ofi_data.get("mean_imbalance", 1.0),
                "trade_mode": "phantom",
                "status": "pending_evaluation",
            }

            await self.deps.redis.redis.lpush(
                "bruno:phantom_trades:pending", json.dumps(phantom)
            )
            await self.deps.redis.redis.ltrim("bruno:phantom_trades:pending", 0, 499)

            self.logger.debug(f"Phantom Trade gespeichert: {phantom_id} | evaluate_at={evaluate_at}")

        except Exception as e:
            self.logger.warning(f"Phantom Trade Fehler (nicht kritisch): {e}")

    async def _evaluate_phantom_trades(self, current_price: float) -> None:
        """
        Wertet fällige Phantom Trades aus (BUG #6 Fix: Evaluator war fehlend).

        Läuft jeden Zyklus. Prüft ob PHANTOM_HOLD_DURATION_MINUTES abgelaufen sind.
        Verschiebt fällige Trades von pending → evaluated mit Outcome-Berechnung.
        Kein Einfluss auf Portfolio, Capital oder Veto-Logik.
        """
        try:
            raw_pending = await self.deps.redis.redis.lrange(
                "bruno:phantom_trades:pending", 0, -1
            )
            if not raw_pending:
                return

            now = datetime.now(timezone.utc)
            still_pending = []
            evaluated_count = 0

            for raw in raw_pending:
                try:
                    phantom = json.loads(raw)
                    evaluate_at_str = phantom.get("evaluate_at")
                    if not evaluate_at_str:
                        continue

                    evaluate_at = datetime.fromisoformat(evaluate_at_str)
                    if now < evaluate_at:
                        # Noch nicht fällig
                        still_pending.append(raw)
                        continue

                    # Fällig → Outcome berechnen
                    entry_price = phantom.get("entry_price", 0.0)
                    if entry_price <= 0:
                        continue

                    price_change_pct = (current_price - entry_price) / entry_price
                    # Phantom waren HOLD-Entscheidungen — hätte die Cascade BUY gesagt?
                    # Wir prüfen: War der HOLD richtig (kein Verlust vermieden)?
                    phantom_outcome = {
                        **phantom,
                        "status": "evaluated",
                        "exit_price": current_price,
                        "price_change_pct": round(price_change_pct, 6),
                        "hold_was_correct": abs(price_change_pct) < 0.01,  # < 1% Bewegung = HOLD richtig
                        "evaluated_at": now.isoformat(),
                        "trade_mode": "phantom",
                    }

                    # In evaluated-Liste schreiben
                    pipe = self.deps.redis.redis.pipeline()
                    pipe.lpush("bruno:phantom_trades:evaluated", json.dumps(phantom_outcome))
                    pipe.ltrim("bruno:phantom_trades:evaluated", 0, 999)
                    await pipe.execute()
                    evaluated_count += 1

                except Exception as e:
                    self.logger.debug(f"Phantom Eval Einzelfehler: {e}")
                    still_pending.append(raw)

            # Pending-Liste neu schreiben (nur noch nicht fällige)
            if evaluated_count > 0:
                pipe = self.deps.redis.redis.pipeline()
                pipe.delete("bruno:phantom_trades:pending")
                for item in still_pending:
                    pipe.rpush("bruno:phantom_trades:pending", item)
                await pipe.execute()
                self.logger.info(f"Phantom Trades ausgewertet: {evaluated_count} | verbleibend: {len(still_pending)}")

        except Exception as e:
            self.logger.warning(f"Phantom Trade Evaluator Fehler: {e}")

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

            # ── 7. GRSS lesen ────────────────────────────────────────────────────
            grss_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
            grss_score = grss_data.get("GRSS_Score", 0.0)

            # ── 8. Pre-Gate: Warmup-Guard (Context Agent noch nicht bereit) ──────
            if not grss_data:
                reason = "Pre-Gate: GRSS-Daten nicht verfügbar — Context Agent noch nicht bereit"
                self.logger.info(reason)
                await self._log_decision("PRE_GATE_HOLD", reason, grss=0.0,
                                         price=best_bid_p, ofi_data=ofi_data)
                return

            # Pre-Gate: Extremstress-Filter (konfigurierbarer Threshold)
            # Default 20 = nur echter Marktkollaps; kein normaler HOLD-Filter
            pre_gate_threshold = self._load_config_value("PRE_GATE_GRSS_Threshold", 20.0)
            if grss_score < pre_gate_threshold:
                reason = f"Pre-Gate: GRSS={grss_score:.1f} < {pre_gate_threshold:.0f} (Extremstress)"
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

            # ── 9. LLM Cascade — Health-Check vor jedem Aufruf ──────────────────
            # Wenn Ollama nicht erreichbar: HOLD (kein Signal = kein Trade = sicher)
            if not hasattr(self, "_llm_cascade"):
                from app.llm import LLMCascade
                llm_provider = OllamaProvider()
                self._llm_cascade = LLMCascade(self.deps.redis, llm_provider)
                await self._llm_cascade.initialize()
                self.logger.info(
                    f"LLM Cascade initialisiert | Provider: {type(llm_provider).__name__} | "
                    f"Base URL: {getattr(llm_provider, 'base_url', 'UNBEKANNT')} | "
                    f"Models: layer1={getattr(llm_provider, 'fast_model', 'UNBEKANNT')} "
                    f"layer2={getattr(llm_provider, 'reasoning_model', 'UNBEKANNT')}"
                )

            # LLM-Status aus Redis prüfen (wird von worker.py beim Start gesetzt)
            llm_status = await self.deps.redis.get_cache("bruno:llm:status") or {}
            if llm_status.get("status") == "offline":
                reason = "Pre-Gate: LLM (Ollama) nicht erreichbar — HOLD bis Reconnect"
                self.logger.warning(reason)
                await self._log_decision("PRE_GATE_HOLD", reason, grss=grss_score,
                                         price=best_bid_p, ofi_data=ofi_data)
                return

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

            # ── PHANTOM TRADE für HOLD-Zyklen ──────────────────────────────────────
            # Nur in DRY_RUN + Learning Mode. Niemals in Live.
            if self.deps.config.DRY_RUN and self._load_config_value("LEARNING_MODE_ENABLED", 0.0) > 0:
                # Fällige Phantom Trades auswerten (Evaluator läuft jeden Zyklus)
                await self._evaluate_phantom_trades(best_bid_p)

                # Neue Phantom Trade für HOLD-Entscheidungen aufzeichnen
                if not cascade_result.is_actionable:
                    await self._record_phantom_trade(
                        cascade_result=cascade_result,
                        grss_score=grss_score,
                        price=best_bid_p,
                        ofi_data=ofi_data,
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
