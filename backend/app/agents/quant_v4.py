from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import PublicExchangeClient
from app.services.liquidity_engine import LiquidityEngine
from app.services.composite_scorer import CompositeScorer
import asyncio
import contextlib
import httpx
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import text

class QuantAgentV4(PollingAgent):
    """
    Bruno v2 Quant Agent — Deterministic Composite Scoring.
    Ersetzt quant_v3 + LLM-Cascade. 60s Intervall.
    """
    def __init__(self, deps: AgentDependencies, symbol: str = "BTCUSDT"):
        super().__init__("quant", deps)
        self.symbol = symbol
        self.cvd_cumulative = 0.0
        self.exm = PublicExchangeClient(redis=deps.redis)
        self._last_price: float = 0.0
        self._last_signal_time: float = 0.0  # NEU: Cooldown-Tracking
        
        # FIX: Strikter Timestamp-Guard für CVD Deduplizierung
        self._last_processed_kline_ts = 0
        self._last_trade_id: int = 0  # CVD Trade ID Tracking
        self._score_lock = asyncio.Lock()
        self._liquidation_listener_task: Optional[asyncio.Task] = None
        self._liquidation_spike_threshold_usdt: float = 500_000.0
        
        self.liq_engine = LiquidityEngine(deps.db_session_factory, deps.redis)
        self.scorer = CompositeScorer(redis_client=deps.redis)
    
    def get_interval(self) -> float:
        return 60.0

    async def setup(self) -> None:
        self.logger.info(f"QuantAgentV4 für {self.symbol} gestartet.")

        # CVD-State aus Redis laden (überlebt Restarts)
        cvd_cached = await self.deps.redis.get_cache("bruno:cvd:BTCUSDT")
        if cvd_cached:
            self.cvd_cumulative = float(cvd_cached.get("value", 0.0))
            self._last_trade_id = int(cvd_cached.get("last_trade_id", 0))
            # FIX: Lade letzten verarbeiteten Kline-Timestamp
            self._last_processed_kline_ts = int(cvd_cached.get("last_processed_kline_ts", 0))
            self.logger.info(f"CVD State aus Redis geladen: {self.cvd_cumulative:.2f} | Last Trade ID: {self._last_trade_id} | Last Kline TS: {self._last_processed_kline_ts}")
        else:
            self.cvd_cumulative = 0.0
            self._last_trade_id = 0
            self._last_processed_kline_ts = 0
            self.logger.info("CVD State: Kein Cache — starte bei 0.0")

        await self.deps.redis.set_cache(
            "bruno:cvd:BTCUSDT",
            {
                "value": self.cvd_cumulative,
                "last_trade_id": self._last_trade_id,
                "last_processed_kline_ts": self._last_processed_kline_ts,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            ttl=86400
        )

        self.logger.info(
            f"Liquidation-Event-Listener bereit für market:liquidations:{self.symbol}:events"
        )

    async def process(self) -> None:
        await self._ensure_liquidation_listener()
        await self._run_scoring_cycle(trigger_reason="poll")

    async def teardown(self) -> None:
        if self._liquidation_listener_task:
            self._liquidation_listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._liquidation_listener_task
        await self.exm.close()
        await super().teardown()

    async def _listen_for_liquidation_spikes(self) -> None:
        """Pub/Sub Listener für sofortige Reaktionen auf Force-Order-Spikes."""
        channel = f"market:liquidations:{self.symbol}:events"
        pubsub = await self.deps.redis.subscribe_channel(channel)
        if not pubsub:
            self.logger.warning(f"Liquidation-Listener nicht gestartet: {channel}")
            return

        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg or msg.get("type") != "message":
                    await asyncio.sleep(0.1)
                    continue

                payload = json.loads(msg["data"])
                total_usdt = float(payload.get("total_usdt", 0.0) or 0.0)
                if total_usdt < self._liquidation_spike_threshold_usdt:
                    continue

                self.logger.info(
                    f"Sofort-Trigger: Force-Order Spike {total_usdt:,.0f} USDT | "
                    f"side={payload.get('side')}"
                )
                asyncio.create_task(
                    self._run_scoring_cycle(
                        trigger_reason="sweep_event",
                        liquidation_event=payload,
                    )
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Liquidation-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def _ensure_liquidation_listener(self) -> None:
        """Startet den Liquidation-Listener genau einmal, sobald der Agent läuft."""
        if self._liquidation_listener_task and not self._liquidation_listener_task.done():
            return
        if not self.state.running:
            return

        self._liquidation_listener_task = asyncio.create_task(self._listen_for_liquidation_spikes())
        self.logger.info(
            f"Liquidation-Event-Listener aktiviert für market:liquidations:{self.symbol}:events"
        )

    async def _run_scoring_cycle(
        self,
        trigger_reason: str = "poll",
        liquidation_event: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            async with self._score_lock:
                if trigger_reason != "poll":
                    self.logger.info(f"Scoring-Run via {trigger_reason}")

                # 0. Health Check für Liquidation_Cluster_SQL
                await self._check_liquidation_cluster_sql()

                # 1. Orderbook + VAMP + CVD (aus quant_v3 kopiert)
                ob = await self.exm.fetch_order_book_redundant(self.symbol, limit=20)
                if not ob or not ob.get("bids") or not ob.get("asks"):
                    return

                best_bid_p = ob["bids"][0][0]
                best_ask_p = ob["asks"][0][0]
                best_bid_v = ob["bids"][0][1]
                best_ask_v = ob["asks"][0][1]
                self._last_price = best_bid_p
                vamp = (best_bid_p * best_ask_v + best_ask_p * best_bid_v) / (best_bid_v + best_ask_v)

                # CVD - FIXED: Nutze aggTrades mit striktem Trade-ID-Guard für Deduplizierung
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        params = {"symbol": self.symbol, "limit": 1000}
                        if self._last_trade_id > 0:
                            params["fromId"] = self._last_trade_id + 1
                        r = await client.get(
                            "https://fapi.binance.com/fapi/v1/aggTrades", params=params)
                        if r.status_code == 200:
                            trades = r.json() or []
                            if trades:
                                processed = 0.0
                                latest_trade_id = self._last_trade_id
                                for trade in trades:
                                    trade_id = int(trade.get("a", 0))
                                    if trade_id <= self._last_trade_id:
                                        continue
                                    qty = float(trade.get("q", 0.0) or 0.0)
                                    is_buyer_maker = bool(trade.get("m", False))
                                    minute_delta = -qty if is_buyer_maker else qty
                                    processed += minute_delta
                                    latest_trade_id = max(latest_trade_id, trade_id)

                                if latest_trade_id > self._last_trade_id:
                                    self.cvd_cumulative += processed
                                    self._last_trade_id = latest_trade_id

                                    await self.deps.redis.set_cache(
                                        "bruno:cvd:BTCUSDT",
                                        {
                                            "value": self.cvd_cumulative,
                                            "last_trade_id": self._last_trade_id,
                                            "timestamp": datetime.now(timezone.utc).isoformat(),
                                        },
                                        ttl=86400,
                                    )

                                    self.logger.debug(
                                        f"CVD Update (aggTrades): {processed:+.4f} -> {self.cvd_cumulative:.4f} | Last Trade ID: {self._last_trade_id}"
                                    )
                            else:
                                self.logger.debug("CVD aggTrades leer — keine neuen Trades")
                except Exception as e:
                    self.logger.warning(f"CVD aggTrades Fehler: {e}")

                # OFI Rolling (kopiere _fetch_ofi_rolling() 1:1 aus quant_v3.py)
                ofi_data = await self._fetch_ofi_rolling()

                # Micro-Payload
                await self.deps.redis.set_cache("bruno:quant:micro", {
                    "symbol": self.symbol,
                    "price": best_bid_p,
                    "VAMP": round(vamp, 2),
                    "CVD": round(self.cvd_cumulative, 2),
                    "OFI_Buy_Pressure": ofi_data["buy_pressure_ratio"],
                    "OFI_Mean_Imbalance": ofi_data["mean_imbalance"],
                    "OFI_Tick_Count": ofi_data["tick_count"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                # 2. Liquiditäts-Analyse
                liq_result = await self.liq_engine.analyze(best_bid_p, liquidation_event=liquidation_event)
                await self.deps.redis.set_cache("bruno:liq:intelligence", liq_result)

                # 3. Composite Score
                signal = await self.scorer.score()

                # 4. Decision Feed
                await self._log_decision(signal)

                # 5. Logging
                self.logger.info(
                    f"Score={signal.composite_score:+.1f} ({signal.weight_preset}) "
                    f"dir={signal.direction} trade={signal.should_trade} "
                    f"MTF={'✓' if signal.mtf_aligned else '✗'} "
                    f"Sweep={'✓' if signal.sweep_confirmed else '✗'} "
                    f"| TA={signal.ta_score:+.1f} Liq={signal.liq_score:+.1f} "
                    f"Flow={signal.flow_score:+.1f} Macro={signal.macro_score:+.1f}"
                )

                # 5b. Diagnostik-Logging (immer, auch bei HOLD)
                if hasattr(signal, 'diagnostics'):
                    self.logger.info(
                        f"DIAG: {signal.diagnostics.get('block_reason', 'NONE')} | "
                        f"GRSS={signal.diagnostics.get('grss_ema', 0):.1f} "
                        f"Veto={signal.diagnostics.get('veto_active')} | "
                        f"Score={signal.composite_score:+.1f} "
                        f"Threshold={signal.diagnostics.get('effective_threshold', 0)} "
                        f"Gap={signal.diagnostics.get('gap_to_threshold', 0):.1f}"
                    )

                # 6. Trade-Cooldown (event-driven sweeps dürfen sofort durchlaufen)
                if signal.should_trade:
                    now = time.time()
                    cooldown = 0.0 if trigger_reason == "sweep_event" else float(self._load_config_value("TRADE_COOLDOWN_SECONDS", 300))
                    if cooldown > 0 and now - self._last_signal_time < cooldown:
                        self.logger.info(
                            f"Signal unterdrückt — Cooldown "
                            f"({cooldown - (now - self._last_signal_time):.0f}s verbleibend)"
                        )
                    else:
                        signal_dict = signal.to_signal_dict(self.symbol)
                        await self.deps.redis.publish_message("bruno:pubsub:signals", json.dumps(signal_dict))
                        self._last_signal_time = now
                        self.logger.info(f"SIGNAL: {signal.direction.upper()} | Score={signal.composite_score:+.1f}")

                # Phantom Trade (Learning Mode)
                if (not signal.should_trade and self.deps.config.DRY_RUN
                    and self._load_config_value("LEARNING_MODE_ENABLED", 0) > 0
                    and abs(signal.composite_score) > 30):
                    await self._record_phantom_trade(signal, best_bid_p)

        except Exception as e:
            self.logger.error(f"QuantAgentV4 Fehler: {e}", exc_info=True)

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

    async def _check_liquidation_cluster_sql(self):
        """Health Check für Liquidation_Cluster_SQL (Legacy von quant_v3)."""
        import time
        from sqlalchemy import text
        
        start = time.perf_counter()
        query = text("""
            SELECT ROUND(price::numeric, -2) as zone, SUM(total_usdt) as amount 
            FROM liquidations 
            WHERE symbol = 'BTCUSDT' AND time > NOW() - INTERVAL '24 hours' 
            GROUP BY zone 
            HAVING SUM(total_usdt) > 100000
            ORDER BY amount DESC
        """)
        try:
            async with self.deps.db_session_factory() as session:
                result = await session.execute(query)
                clusters = [{"zone": float(row[0]), "amount": float(row[1])} for row in result.fetchall()]
                latency = (time.perf_counter() - start) * 1000
                await self._report_health("Liquidation_Cluster_SQL", "online", latency)
                return clusters
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("Liquidation_Cluster_SQL", "offline", latency)
            return []

    async def _fetch_ofi_rolling(self) -> dict:
        """
        Liest den akkumulierten OFI-Buffer aus dem IngestionAgent.
        Gibt semantisch auswertbare Metriken zurück — keinen rohen Absolutwert.
        """
        try:
            raw = await self.deps.redis.redis.lrange("market:ofi:ticks", 0, -1)
            if not raw or len(raw) < 10:
                return {"buy_pressure_ratio": None, "mean_imbalance": None, "tick_count": 0}

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
            return {"buy_pressure_ratio": None, "mean_imbalance": None, "tick_count": 0}

    async def _log_decision(self, signal) -> None:
        """
        Loggt jede Evaluierungs-Entscheidung in den Decision Feed.
        Schreibt nach bruno:decisions:feed (kompatibel mit /api/v1/decisions/feed).
        """
        try:
            import json as _json
            entry = signal.to_decision_feed_entry()
            pipe = self.deps.redis.redis.pipeline()
            pipe.lpush("bruno:decisions:feed", _json.dumps(entry))
            pipe.ltrim("bruno:decisions:feed", 0, 143)  # 12h bei 60s Zyklen
            await pipe.execute()
        except Exception as e:
            self.logger.warning(f"Decision Log Fehler: {e}")

    async def _record_phantom_trade(self, signal, price: float) -> None:
        """
        Speichert einen hypothetischen Trade für HOLD-Entscheidungen.
        Wird nach PHANTOM_HOLD_DURATION_MINUTES ausgewertet (Preis-Outcome).

        Diese Daten gehen AUSSCHLIESSLICH in trade_debriefs mit trade_mode='phantom'.
        Kein Einfluss auf Portfolio, Capital, P&L oder Veto-Logik.
        """
        try:
            import uuid

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
                "composite_score": signal.composite_score,
                "direction": signal.direction,
                "regime": signal.regime,
                "weight_preset": signal.weight_preset,
                "ta_score": signal.ta_score,
                "liq_score": signal.liq_score,
                "flow_score": signal.flow_score,
                "macro_score": signal.macro_score,
                "mtf_aligned": signal.mtf_aligned,
                "sweep_confirmed": signal.sweep_confirmed,
                "signals_active": signal.signals_active,
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

    def _load_config_value(self, key: str, default: float) -> float:
        """Lädt einen Wert aus config.json. Fallback auf default wenn nicht gefunden."""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        try:
            with open(config_path, "r") as f:
                value = json.load(f).get(key, default)
                if isinstance(value, bool):
                    return 1.0 if value else 0.0
                return float(value)
        except Exception:
            return default
