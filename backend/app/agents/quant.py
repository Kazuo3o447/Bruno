import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import text
from typing import Dict, Any, Optional, List
from app.agents.base import BaseAgent, PollingAgent
from app.agents.deps import AgentDependencies
from app.core.redis_client import redis_client
from app.core.log_manager import LogManager, LogCategory, LogLevel
from app.core.exchange_manager import PublicExchangeClient
from app.llm import LLMCascade

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
        self.cascade = LLMCascade(deps.redis)  # Phase C: LLM Cascade
        
    async def setup(self) -> None:
        self.logger.info(f"QuantAgent für {self.symbol} gestartet.")
        
        # Log to central LogManager with AGENT category
        await self.deps.log_manager.add_log(
            LogLevel.INFO,
            LogCategory.AGENT,
            "agent.quant",
            f"QuantAgent für {self.symbol} wird initialisiert..."
        )
        
        # Phase C: LLM Cascade initialisieren
        await self.cascade.initialize()
        await self.deps.log_manager.add_log(
            LogLevel.INFO,
            LogCategory.AGENT,
            "agent.quant",
            "LLM Cascade initialisiert"
        )

        # CVD-State aus Redis laden (überlebt Restarts)
        cvd_cached = await self.deps.redis.get_cache("bruno:cvd:BTCUSDT")
        if cvd_cached:
            self.cvd_cumulative = float(cvd_cached.get("value", 0.0))
            self.logger.info(f"CVD State aus Redis geladen: {self.cvd_cumulative:.2f}")
            await self.deps.log_manager.add_log(
                LogLevel.INFO,
                LogCategory.AGENT,
                "agent.quant",
                f"CVD State aus Redis geladen: {self.cvd_cumulative:.2f}"
            )
        else:
            self.cvd_cumulative = 0.0
            self.logger.info("CVD State: Kein Cache — starte bei 0.0")
            await self.deps.log_manager.add_log(
                LogLevel.INFO,
                LogCategory.AGENT,
                "agent.quant",
                "CVD State: Kein Cache — starte bei 0.0"
            )

        await self.deps.redis.set_cache(
            "bruno:cvd:BTCUSDT",
            {
                "value": self.cvd_cumulative,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            ttl=86400
        )

        self.prev_ob = None
        await self.deps.log_manager.add_log(
            LogLevel.INFO,
            LogCategory.AGENT,
            "agent.quant",
            "QuantAgent vollständig initialisiert und betriebsbereit"
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
            self.state.sub_state = "fetching orderbook"
            ob = await self.exm.fetch_order_book_redundant(self.symbol, limit=20)
            if not ob or not ob.get('bids') or not ob.get('asks'):
                self.state.sub_state = "error (no orderbook)"
                return

            best_bid_p, best_bid_v = ob['bids'][0][0], ob['bids'][0][1]
            best_ask_p, best_ask_v = ob['asks'][0][0], ob['asks'][0][1]

            # 2. HFT Metriken
            self.state.sub_state = "calculating metrics"
            vamp = (best_bid_p * best_ask_v + best_ask_p * best_bid_v) / (best_bid_v + best_ask_v)
            ofi = self._calculate_ofi(ob)
            
            # 3. CVD & Liq Walls
            self.state.sub_state = "fetching trades & liq"
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
            
            # PHASE C: LLM Cascade statt einfacher OFI-Signal-Generation
            if abs(ofi) >= self.ofi_threshold:
                # GRSS-Daten für Cascade holen
                grss_data = await self.deps.redis.get_cache("bruno:context:grss") or {}
                grss_score = grss_data.get("GRSS_Score", 50.0)
                grss_components = {
                    "macro_sentiment": grss_data.get("Macro_Sentiment", 0.0),
                    "derivatives_flow": grss_data.get("Derivatives_Flow", 0.0),
                    "funding_pressure": grss_data.get("Funding_Pressure", 0.0),
                    "retail_fomo": grss_data.get("Retail_FOMO", 0.0),
                }
                
                # Markt-Kontext für Cascade
                market_context = {
                    "btc_price": best_bid_p,
                    "funding_rate": grss_data.get("Funding_Rate", 0.0),
                    "vix": grss_data.get("VIX", 0.0),
                    "oi_delta_pct": grss_data.get("OI_Delta_Pct", 0.0),
                    "put_call_ratio": grss_data.get("Put_Call_Ratio", 0.0),
                    "ndx_status": grss_data.get("NDX_Status", "unknown"),
                    "ofi": ofi,
                    "vamp": vamp,
                    "cvd": self.cvd_cumulative,
                }
                
                # LLM Cascade ausführen
                self.state.sub_state = "running llm cascade"
                cascade_result = await self.cascade.run(
                    grss_components=grss_components,
                    market_context=market_context,
                    grss_score=grss_score
                )
                
                # Nur wenn Cascade ein Signal gibt, senden
                if cascade_result.is_actionable:
                    signal = {
                        "symbol": self.symbol,
                        "side": cascade_result.decision.lower(),
                        "amount": 0.001,   # Bybit Futures Minimum
                        "ofi": ofi,
                        "price": best_bid_p,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        # Phase C: Cascade-Extras für RiskAgent und ExecutionAgent
                        **cascade_result.to_signal_extras()
                    }
                    await self.deps.redis.publish_message("bruno:pubsub:signals", json.dumps(signal))
                    self.logger.info(
                        f"LLM Cascade Signal: {cascade_result.decision} {self.symbol} "
                        f"(Regime: {cascade_result.regime}, Confidence: {cascade_result.final_confidence:.2f})"
                    )
                else:
                    self.logger.info(
                        f"LLM Cascade HOLD @ {cascade_result.aborted_at} "
                        f"(Regime: {cascade_result.regime})"
                    )

            # ── Decision Event: jeder Zyklus wird dokumentiert ───────────────────
            decision_event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "ofi": round(ofi, 1),
                "ofi_threshold": self.ofi_threshold,
                "ofi_met": abs(ofi) >= self.ofi_threshold,
                "grss": None,
                "outcome": None,
                "reason": None,
                "regime": None,
                "layer1_confidence": None,
                "layer2_decision": None,
                "layer3_blocked": None,
                "price": best_bid_p,
                "cvd": round(self.cvd_cumulative, 1),
                "vamp": round(vamp, 2),
            }

            if not abs(ofi) >= self.ofi_threshold:
                decision_event["outcome"] = "OFI_BELOW_THRESHOLD"
                decision_event["reason"] = f"OFI {ofi:.1f} unter Schwelle {self.ofi_threshold}"
            elif not cascade_result.is_actionable:
                decision_event["outcome"] = f"CASCADE_{cascade_result.aborted_at.upper()}"
                decision_event["reason"] = f"Abgebrochen bei {cascade_result.aborted_at}"
                decision_event["grss"] = grss_score
                decision_event["regime"] = cascade_result.regime
                decision_event["layer1_confidence"] = cascade_result.layer1.get("confidence")
                decision_event["layer2_decision"] = cascade_result.layer2.get("decision")
                decision_event["layer3_blocked"] = cascade_result.layer3.get("blocker")
            else:
                decision_event["outcome"] = f"SIGNAL_{cascade_result.decision}"
                decision_event["reason"] = f"Signal: {cascade_result.decision}"
                decision_event["grss"] = grss_score
                decision_event["regime"] = cascade_result.regime
                decision_event["layer1_confidence"] = cascade_result.layer1.get("confidence")
                decision_event["layer2_decision"] = cascade_result.layer2.get("decision")
                decision_event["layer3_blocked"] = False

            # In Redis-Liste schreiben (neueste zuerst, max 200 Events)
            event_json = json.dumps(decision_event)
            await self.deps.redis.redis.lpush("bruno:decisions:feed", event_json)
            await self.deps.redis.redis.ltrim("bruno:decisions:feed", 0, 199)

        except Exception as e:
            self.logger.error(f"QuantAgent Fehler: {e}")
            await self.deps.log_manager.add_log(
                LogLevel.ERROR,
                LogCategory.AGENT,
                "agent.quant",
                f"QuantAgent Fehler: {e}"
            )

