from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import PublicExchangeClient
from app.services.liquidity_engine import LiquidityEngine
from app.services.composite_scorer import CompositeScorer
from app.services.phantom_evaluator import PhantomEvaluator
from app.core.config_cache import ConfigCache
import asyncio
import contextlib
import httpx
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from sqlalchemy import text

class QuantAgentV4(PollingAgent):
    """
    Bruno v2 Quant Agent — Deterministic Composite Scoring.
    Ersetzt quant_v3 + LLM-Cascade. 60s Intervall.
    
    PROMPT 9: Strict Pipeline Integration
    ================================
    Statt direkt Pub/Sub zu verwenden, reicht der QuantAgent Signale
    an den Orchestrator weiter via signal_submit_callback.
    Der Orchestrator führt dann synchron Risk-Validierung und Execution durch.
    """
    def __init__(
        self, 
        deps: AgentDependencies, 
        symbol: str = "BTCUSDT",
        signal_submit_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ):
        super().__init__("quant", deps)
        self.symbol = symbol
        self.cvd_cumulative = 0.0
        self.exm = PublicExchangeClient(redis=deps.redis)
        self._last_price: float = 0.0
        self._last_signal_time: float = 0.0  # NEU: Cooldown-Tracking
        
        # Cooldown-Tracker für Sweep & Funding (BUG 6)
        self._last_sweep_signal_time: float = 0.0
        self._last_funding_signal_time: float = 0.0
        
        # FIX: Strikter Timestamp-Guard für CVD Deduplizierung / Restart-Sicherheit
        self._last_processed_ts: int = 0
        self._score_lock = asyncio.Lock()
        self._liquidation_listener_task: Optional[asyncio.Task] = None
        self._liquidation_spike_threshold_usdt: float = 500_000.0
        
        # PROMPT 9: Callback für Strict Pipeline
        # Wenn gesetzt, werden Signale über diesen Callback an den Orchestrator gereicht
        # statt direkt via Pub/Sub
        self._signal_submit_callback: Optional[Callable[[Dict[str, Any]], Any]] = signal_submit_callback
        self._strict_pipeline_mode: bool = signal_submit_callback is not None
        
        self.liq_engine = LiquidityEngine(deps.db_session_factory, deps.redis)
        self.scorer = CompositeScorer(redis_client=deps.redis)
        
        # BRUNO-FIX-09: Phantom Evaluator
        self.phantom_evaluator = PhantomEvaluator(
            deps.redis, deps.db_session_factory, self.exm
        )
        self._last_phantom_eval_time: float = 0.0
    
    def get_interval(self) -> float:
        return 60.0

    async def setup(self) -> None:
        # Initialize ConfigCache
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        ConfigCache.init(config_path)
        
        self.logger.info(f"QuantAgentV4 für {self.symbol} gestartet.")

        # CVD-State aus Redis laden (überlebt Restarts)
        cvd_cached = await self.deps.redis.get_cache("bruno:cvd:BTCUSDT")
        if cvd_cached:
            self.cvd_cumulative = float(cvd_cached.get("value", 0.0))
            self._last_processed_ts = int(
                cvd_cached.get("last_processed_ts", cvd_cached.get("last_processed_kline_ts", 0))
            )
            self.logger.info(
                f"CVD State aus Redis geladen: {self.cvd_cumulative:.2f} | Last TS: {self._last_processed_ts}"
            )
        else:
            # Versuche kumulatives CVD direkt aus Redis zu laden
            cvd_cumulative_str = await self.deps.redis.redis.get("market:cvd:cumulative")
            if cvd_cumulative_str:
                self.cvd_cumulative = float(cvd_cumulative_str)
                self.logger.info(f"CVD kumulativ aus Redis geladen: {self.cvd_cumulative:.2f}")
            else:
                self.cvd_cumulative = 0.0
                self.logger.info("CVD State: Kein Cache — starte bei 0.0")
            
            self._last_processed_ts = 0

        await self.deps.redis.set_cache(
            "bruno:cvd:BTCUSDT",
            {
                "value": self.cvd_cumulative,
                "last_processed_ts": self._last_processed_ts,
                "last_processed_kline_ts": self._last_processed_ts,
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
        
        # BRUNO-FIX-09: Phantom Evaluator alle 5 Minuten laufen lassen
        now = time.time()
        if now - self._last_phantom_eval_time >= 300:
            evaluated = await self.phantom_evaluator.evaluate_pending()
            self._last_phantom_eval_time = now
            if evaluated > 0:
                self.logger.info(f"Phantom Evaluator: {evaluated} trades evaluated")

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
                
                # 0b. Portfolio für Sizing laden
                portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
                capital_eur = portfolio.get("capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR)
                capital_usd = capital_eur * 1.08

                # 1. Orderbook + VAMP + CVD (1m-Kline, restart-sicher)
                ob = await self.exm.fetch_order_book_redundant(self.symbol, limit=20)
                if not ob or not ob.get("bids") or not ob.get("asks"):
                    return

                best_bid_p = ob["bids"][0][0]
                best_ask_p = ob["asks"][0][0]
                best_bid_v = ob["bids"][0][1]
                best_ask_v = ob["asks"][0][1]
                self._last_price = best_bid_p
                vamp = (best_bid_p * best_ask_v + best_ask_p * best_bid_v) / (best_bid_v + best_ask_v)

                # BRUNO-FIX-08: CVD Single Source of Truth mit Drift-Detection
                try:
                    cvd_cumulative_str = await self.deps.redis.redis.get("market:cvd:cumulative")
                    if cvd_cumulative_str:
                        new_cvd = float(cvd_cumulative_str)
                        # Drift-Detection
                        if abs(new_cvd - self.cvd_cumulative) > 1_000_000 and self.cvd_cumulative != 0:
                            self.logger.warning(
                                f"CVD drift detected: cached={self.cvd_cumulative:.0f}, "
                                f"redis={new_cvd:.0f} — using fresh redis value"
                            )
                        self.cvd_cumulative = new_cvd
                        # Snapshot für Restart-Recovery aktualisieren
                        await self.deps.redis.set_cache(
                            "bruno:cvd:BTCUSDT",
                            {
                                "value": self.cvd_cumulative,
                                "last_processed_ts": int(time.time() * 1000),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            ttl=86400
                        )
                    else:
                        self.logger.debug("CVD: market:cvd:cumulative empty — using last known value")
                except Exception as e:
                    self.logger.warning(f"CVD Redis Fehler: {e}")

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
                    "OFI_Available": ofi_data["ofi_available"],
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

                # BRUNO-FIX-05: Exploration Metrics Logging
                if ConfigCache.get("LOG_EXPLORATION_METRICS", False):
                    exploration_entry = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "symbol": self.symbol,
                        "regime": signal.regime,
                        "composite_score": signal.composite_score,
                        "ta_score": signal.ta_score,
                        "liq_score": signal.liq_score,
                        "flow_score": signal.flow_score,
                        "macro_score": signal.macro_score,
                        "mr_score": signal.mean_reversion_score,
                        "direction": signal.direction,
                        "should_trade": signal.should_trade,
                        "conviction": signal.conviction,
                        "mtf_aligned": signal.mtf_aligned,
                        "sweep_confirmed": signal.sweep_confirmed,
                        "effective_threshold": signal.diagnostics.get("effective_threshold", 0),
                        "gap_to_threshold": signal.diagnostics.get("gap_to_threshold", 0),
                        "block_reason": signal.diagnostics.get("block_reason", "NONE"),
                        "signals": signal.signals_active[:5],
                    }
                    try:
                        import json as _json
                        pipe = self.deps.redis.redis.pipeline()
                        pipe.lpush("bruno:exploration:metrics", _json.dumps(exploration_entry))
                        pipe.ltrim("bruno:exploration:metrics", 0, 999)  # letzte 1000 Samples
                        await pipe.execute()
                    except Exception as e:
                        self.logger.debug(f"Exploration metrics log error: {e}")

                # 6. Multi-Strategy Signal Dispatch
                from app.services.strategy_manager import StrategyManager

                strategy_mgr = StrategyManager(self.deps.redis, self.deps.db_session_factory)

                # 6a. TREND-Slot: BRUNO-FIX-05 reduzierter Cooldown im Learning Mode
                if signal.should_trade:
                    now = time.time()
                    learning_mode = bool(ConfigCache.get("LEARNING_MODE_ENABLED", False))
                    if learning_mode:
                        cooldown = float(ConfigCache.get("TRADE_COOLDOWN_SECONDS_LEARNING", 60))
                    else:
                        cooldown = float(ConfigCache.get("TRADE_COOLDOWN_SECONDS", 300))

                    # BRUNO-FIX-08: Cooldown-Check vor Submit
                    cooldown_remaining = cooldown - (now - self._last_signal_time)
                    if cooldown_remaining > 0:
                        # Liquidation-Event darf Trend-Cooldown NICHT bypassen
                        if trigger_reason == "sweep_event":
                            self.logger.info(
                                f"TREND skipped (sweep_event trigger, cooldown {cooldown_remaining:.0f}s remaining)"
                            )
                    elif now - self._last_signal_time >= cooldown:
                        signal_dict = signal.to_signal_dict(self.symbol)
                        signal_dict["strategy_slot"] = "trend"

                        # BRUNO-FIX-08: Sanity-Check vor Submit
                        if signal_dict.get("amount", 0) <= 0:
                            self.logger.error(
                                f"SIGNAL DROP: amount={signal_dict.get('amount')} for {signal_dict.get('side')} "
                                f"signal — sizing={signal_dict.get('sizing', {})}"
                            )
                        else:
                            # PROMPT 9: Verwende _submit_signal für Strict Pipeline
                            submitted = await self._submit_signal(signal_dict, "trend")
                            if submitted:
                                self._last_signal_time = now
                                self.logger.info(f"TREND SIGNAL: {signal.direction.upper()} | Score={signal.composite_score:+.1f}")
                
                # 6b. SWEEP-Slot: Eigenständig, basierend auf Sweep-Detection
                # PROMPT 5: Sweep-Slot Filter (Falling Knife Protection)
                sweep_signal = strategy_mgr.evaluate_sweep_signal(
                    liq_result.get("sweep", {}),
                    liq_result.get("liq_score", 0),
                )
                if sweep_signal:
                    # Sweep Cooldown (60s — Sweeps sind zeitkritisch)
                    now = time.time()
                    if now - self._last_sweep_signal_time >= 60:
                        # PROMPT 5: OFI-Validierung für Sweep-Slot
                        # Ein Sweep-Signal wird erst freigegeben, WENN der OFI Score
                        # ofi_buy_pressure >= 0.60 (Longs) bzw. <= 0.40 (Shorts) aufweist
                        ofi_buy_pressure = ofi_data.get("buy_pressure_ratio", 0.5)
                        sweep_direction = sweep_signal["direction"]
                        
                        ofi_valid = False
                        if sweep_direction == "long" and ofi_buy_pressure >= 0.60:
                            ofi_valid = True
                        elif sweep_direction == "short" and ofi_buy_pressure <= 0.40:
                            ofi_valid = True
                        
                        if not ofi_valid:
                            self.logger.warning(
                                f"SWEEP SIGNAL BLOCKED: OFI validation failed. "
                                f"Direction={sweep_direction.upper()}, "
                                f"OFI={ofi_buy_pressure:.2f} (need {'>=0.60' if sweep_direction=='long' else '<=0.40'})"
                            )
                            # Log für Analyse
                            await self._log_blocked_sweep(sweep_signal, ofi_buy_pressure, "ofi_validation_failed")
                            return  # Signal nicht senden
                        
                        self.logger.info(
                            f"SWEEP SIGNAL VALIDATED: OFI={ofi_buy_pressure:.2f} "
                            f"passes threshold for {sweep_direction.upper()}"
                        )
                        
                        # Eigenes Sizing für Sweep-Slot
                        from app.services.strategy_manager import STRATEGY_SLOTS
                        sweep_slot = STRATEGY_SLOTS["sweep"]
                        sweep_capital = capital_usd * sweep_slot.capital_allocation_pct
                        # Vereinfachtes Sizing für Sweep (kein CompositeScorer nötig)
                        sweep_sizing = {
                            "position_size_btc": max(0.001, round(
                                (sweep_capital * 1.08 * sweep_slot.risk_per_trade_pct) / 
                                (best_bid_p * 0.01) / best_bid_p, 4
                            )),
                            "leverage_used": sweep_slot.max_leverage,
                            "sizing_valid": True,
                            "reject_reason": None,
                            "position_size_usdt": 0,  # Wird nachberechnet
                            "margin_required_usdt": 0,
                            "risk_amount_eur": round(sweep_capital * sweep_slot.risk_per_trade_pct, 2),
                            "fee_estimate_usdt": 0,
                            "rr_after_fees": 2.0,  # Sweeps haben inherent gutes R:R
                        }
                        sweep_sizing["position_size_usdt"] = round(sweep_sizing["position_size_btc"] * best_bid_p, 2)
                        sweep_sizing["margin_required_usdt"] = round(sweep_sizing["position_size_usdt"] / sweep_slot.max_leverage, 2)
                        
                        sweep_dict = {
                            **signal.to_signal_dict(self.symbol),
                            "strategy_slot": "sweep",
                            "side": "buy" if sweep_signal["direction"] == "long" else "sell",
                            "reason": f"{sweep_signal['reason']} | OFI validated: {ofi_buy_pressure:.2f}",
                            "sizing": sweep_sizing,  # ← EIGENES SIZING
                            "ofi_validation": {
                                "ofi_buy_pressure": ofi_buy_pressure,
                                "threshold": 0.60 if sweep_direction == "long" else 0.40,
                                "passed": True
                            }
                        }
                        # PROMPT 9: Verwende _submit_signal für Strict Pipeline
                        submitted = await self._submit_signal(sweep_dict, "sweep")
                        if submitted:
                            self.logger.info(f"SWEEP SIGNAL: {sweep_signal['direction'].upper()} | {sweep_signal['reason']} | OFI={ofi_buy_pressure:.2f}")
                            self._last_sweep_signal_time = now
                
                # 6c. FUNDING-Slot: Eigenständig, basierend auf Funding Rate
                # PROMPT 5: Funding-Slot Filter (Contrarian Trap Protection)
                macro_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
                funding_rate = float(macro_data.get("Funding_Rate", 0))
                funding_div = float(macro_data.get("Funding_Divergence", 0))
                
                funding_signal = strategy_mgr.evaluate_funding_signal(funding_rate, funding_div)
                if funding_signal:
                    # Funding Cooldown (1800s = 30min — Funding ändert sich langsam)
                    now = time.time()
                    if now - self._last_funding_signal_time >= 1800:
                        # PROMPT 5: EMA9-Cross Filter für Funding-Slot
                        # Der Preis muss den EMA(9) auf dem Ausführungs-Timeframe
                        # in die Trade-Richtung gekreuzt haben
                        ta_snapshot = await self.deps.redis.get_cache("bruno:ta:snapshot") or {}
                        ema9 = ta_snapshot.get("ema_9", 0)
                        current_price = best_bid_p
                        funding_direction = funding_signal["direction"]
                        
                        ema_cross_valid = False
                        if ema9 > 0:
                            if funding_direction == "short" and current_price < ema9:
                                # Short-Signal: Preis muss unter EMA9 sein
                                ema_cross_valid = True
                            elif funding_direction == "long" and current_price > ema9:
                                # Long-Signal: Preis muss über EMA9 sein
                                ema_cross_valid = True
                        
                        if not ema_cross_valid:
                            self.logger.warning(
                                f"FUNDING SIGNAL BLOCKED: EMA9 cross validation failed. "
                                f"Direction={funding_direction.upper()}, "
                                f"Price={current_price:,.0f}, EMA9={ema9:,.0f} "
                                f"(need Price {'<' if funding_direction=='short' else '>'} EMA9)"
                            )
                            await self._log_blocked_funding(funding_signal, current_price, ema9, "ema_cross_failed")
                            return  # Signal nicht senden
                        
                        self.logger.info(
                            f"FUNDING SIGNAL VALIDATED: Price={current_price:,.0f} "
                            f"{'<' if funding_direction=='short' else '>'} EMA9={ema9:,.0f} "
                            f"for {funding_direction.upper()}"
                        )
                        
                        # Eigenes Sizing für Funding-Slot
                        from app.services.strategy_manager import STRATEGY_SLOTS
                        funding_slot = STRATEGY_SLOTS["funding"]
                        funding_capital = capital_usd * funding_slot.capital_allocation_pct
                        # Vereinfachtes Sizing für Funding (kein CompositeScorer nötig)
                        funding_sizing = {
                            "position_size_btc": max(0.001, round(
                                (funding_capital * 1.08 * funding_slot.risk_per_trade_pct) / 
                                (best_bid_p * 0.01) / best_bid_p, 4
                            )),
                            "leverage_used": funding_slot.max_leverage,
                            "sizing_valid": True,
                            "reject_reason": None,
                            "position_size_usdt": 0,  # Wird nachberechnet
                            "margin_required_usdt": 0,
                            "risk_amount_eur": round(funding_capital * funding_slot.risk_per_trade_pct, 2),
                            "fee_estimate_usdt": 0,
                            "rr_after_fees": 1.5,  # Funding Trades haben moderates R:R
                        }
                        funding_sizing["position_size_usdt"] = round(funding_sizing["position_size_btc"] * best_bid_p, 2)
                        funding_sizing["margin_required_usdt"] = round(funding_sizing["position_size_usdt"] / funding_slot.max_leverage, 2)
                        
                        funding_dict = {
                            **signal.to_signal_dict(self.symbol),
                            "strategy_slot": "funding",
                            "side": "buy" if funding_signal["direction"] == "long" else "sell",
                            "reason": f"{funding_signal['reason']} | EMA9 validated: {current_price:,.0f} {'<' if funding_direction=='short' else '>'} {ema9:,.0f}",
                            "sizing": funding_sizing,  # ← EIGENES SIZING
                            "ema9_validation": {
                                "price": current_price,
                                "ema9": ema9,
                                "direction": funding_direction,
                                "passed": True
                            }
                        }
                        # PROMPT 9: Verwende _submit_signal für Strict Pipeline
                        submitted = await self._submit_signal(funding_dict, "funding")
                        if submitted:
                            self.logger.info(f"FUNDING SIGNAL: {funding_signal['direction'].upper()} | {funding_signal['reason']} | EMA9 cross validated")
                            self._last_funding_signal_time = now

                # BRUNO-FIX-04: Erweiterter Phantom Trade Trigger
                # Jetzt: Phantom wenn
                # (a) Learning Mode aktiv UND
                # (b) Score über Learning-Threshold (15) UND
                # (c) (Sizing blockierte ODER score knapp unter effective_threshold)
                phantom_threshold = float(ConfigCache.get("COMPOSITE_THRESHOLD_LEARNING", 15))
                if (self.deps.config.DRY_RUN
                    and ConfigCache.get("LEARNING_MODE_ENABLED", 0) > 0
                    and abs(signal.composite_score) >= phantom_threshold
                    and not signal.should_trade):
                    await self._record_phantom_trade(signal, best_bid_p)
                    self.logger.info(
                        f"PHANTOM TRADE: Score={signal.composite_score:+.1f}, "
                        f"reason={'sizing' if 'SIZING' in str(signal.signals_active) or 'PHANTOM ELIG' in str(signal.signals_active) else 'score'}"
                    )

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
            tick_count = len(raw) if raw else 0
            
            if not raw or tick_count < 10:
                if tick_count > 0:
                    self.logger.warning(f"OFI Pipeline: Nur {tick_count} Ticks — OFI nicht verfügbar")
                return {"buy_pressure_ratio": None, "mean_imbalance": None, "tick_count": tick_count, "ofi_available": False}

            import json as _json
            ratios = []
            for t in raw:
                try:
                    parsed = _json.loads(t)
                    if "r" in parsed and parsed["r"] is not None:
                        ratios.append(float(parsed["r"]))
                except Exception as e:
                    self.logger.debug(f"OFI Tick Parse Fehler (übersprungen): {e}")
                    continue
            
            if not ratios or len(ratios) < 10:
                self.logger.warning(f"OFI Pipeline: Nur {len(ratios)} gültige Ticks — OFI nicht verfügbar")
                return {"buy_pressure_ratio": None, "mean_imbalance": None, "tick_count": tick_count, "ofi_available": False}
            
            mean_imb = sum(ratios) / len(ratios)
            buy_ticks = sum(1 for r in ratios if r > 1.0)

            return {
                "buy_pressure_ratio": round(buy_ticks / len(ratios), 3),  # 0.0=nur Verkauf, 1.0=nur Kauf
                "mean_imbalance": round(mean_imb, 4),                     # 1.0=neutral
                "tick_count": len(ratios),
                "ofi_available": True
            }
        except Exception as e:
            self.logger.warning(f"OFI Rolling Fetch Fehler: {e}")
            return {"buy_pressure_ratio": None, "mean_imbalance": None, "tick_count": 0, "ofi_available": False}

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

            hold_duration = int(ConfigCache.get("PHANTOM_HOLD_DURATION_MINUTES", 240.0))
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

    async def _log_blocked_sweep(self, sweep_signal: dict, ofi_buy_pressure: float, reason: str) -> None:
        """Loggt blockierte Sweep-Signale für Analyse."""
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "SWEEP_BLOCKED",
                "reason": reason,
                "direction": sweep_signal.get("direction"),
                "ofi_buy_pressure": ofi_buy_pressure,
                "threshold": 0.60 if sweep_signal.get("direction") == "long" else 0.40,
                "sweep_intensity": sweep_signal.get("sweep_intensity", 0),
            }
            await self.deps.redis.redis.lpush("bruno:signals:blocked", json.dumps(entry))
            await self.deps.redis.redis.ltrim("bruno:signals:blocked", 0, 199)
        except Exception as e:
            self.logger.warning(f"Log blocked sweep error: {e}")

    async def _log_blocked_funding(self, funding_signal: dict, price: float, ema9: float, reason: str) -> None:
        """Loggt blockierte Funding-Signale für Analyse."""
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "FUNDING_BLOCKED",
                "reason": reason,
                "direction": funding_signal.get("direction"),
                "price": price,
                "ema9": ema9,
                "funding_rate": funding_signal.get("funding_rate", 0),
                "funding_bps": funding_signal.get("funding_rate", 0) * 10000,
            }
            await self.deps.redis.redis.lpush("bruno:signals:blocked", json.dumps(entry))
            await self.deps.redis.redis.ltrim("bruno:signals:blocked", 0, 199)
        except Exception as e:
            self.logger.warning(f"Log blocked funding error: {e}")

    async def _submit_signal(self, signal_dict: Dict[str, Any], slot_name: str) -> bool:
        """
        PROMPT 9: Zentrale Signal-Submission Methode.
        
        Wählt automatisch zwischen Strict Pipeline Mode und Legacy Pub/Sub:
        - Strict Pipeline: Verwendet Callback zum Orchestrator
        - Legacy Mode: Verwendet Redis Pub/Sub
        
        Args:
            signal_dict: Das vollständige Signal-Dictionary
            slot_name: Name des Strategy Slots (trend, sweep, funding)
            
        Returns:
            True wenn Signal erfolgreich eingereicht, False bei Fehler
        """
        if self._strict_pipeline_mode and self._signal_submit_callback:
            # PROMPT 9: Strict Pipeline - Signal über Callback an Orchestrator
            try:
                result = await self._signal_submit_callback(signal_dict)
                if result:
                    self.logger.info(
                        f"PROMPT 9: Signal via Strict Pipeline eingereicht [{slot_name}]"
                    )
                    return True
                else:
                    self.logger.warning(
                        f"PROMPT 9: Signal-Queue voll oder Pipeline-Fehler [{slot_name}]"
                    )
                    return False
            except Exception as e:
                self.logger.error(
                    f"PROMPT 9: Fehler bei Strict Pipeline Submission [{slot_name}]: {e}"
                )
                return False
        else:
            # Legacy Mode: Redis Pub/Sub
            try:
                await self.deps.redis.publish_message(
                    "bruno:pubsub:signals", json.dumps(signal_dict)
                )
                self.logger.info(f"Signal via Pub/Sub veröffentlicht [{slot_name}]")
                return True
            except Exception as e:
                self.logger.error(f"Fehler bei Pub/Sub Signal-Publikation [{slot_name}]: {e}")
                return False
