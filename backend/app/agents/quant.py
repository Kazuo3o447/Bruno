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
        self.ofi_threshold = 50.0  # Full-Depth OFI. Nach 1 Woche Beobachtung kalibrieren.
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

    def _calculate_ofi(self, current_ob: dict, prev_ob: dict | None = None) -> float:
        """
        Order Flow Imbalance über alle verfügbaren Orderbook-Levels.

        Summiert Volumen-Imbalancen über alle bid/ask-Levels statt nur Top-of-Book.
        Produziert Werte typischerweise zwischen -500 und +500 auf BTC/USDT Futures.

        Positive Werte → Kauf-Druck dominiert
        Negative Werte → Verkauf-Druck dominiert

        Threshold-Empfehlung: 50 (Startwert, nach einer Woche Beobachtung kalibrieren)
        """
        if prev_ob is None:
            return 0.0

        bids_curr = current_ob.get('bids', [])
        asks_curr = current_ob.get('asks', [])
        bids_prev = prev_ob.get('bids', [])
        asks_prev = prev_ob.get('asks', [])

        if not bids_curr or not asks_curr or not bids_prev or not asks_prev:
            return 0.0

        ofi = 0.0
        depth = min(20, len(bids_curr), len(bids_prev))

        # Bid-Seite: Kauf-Druck
        for i in range(depth):
            try:
                p_curr, v_curr = float(bids_curr[i][0]), float(bids_curr[i][1])
                p_prev, v_prev = float(bids_prev[i][0]), float(bids_prev[i][1])

                if p_curr > p_prev:
                    ofi += v_curr          # Preis gestiegen → neues Volumen zählt voll
                elif p_curr == p_prev:
                    ofi += (v_curr - v_prev)  # Gleiches Level → Delta
                # p_curr < p_prev: Bid hat sich entfernt → kein positiver Beitrag
            except (IndexError, ValueError, TypeError):
                continue

        # Ask-Seite: Verkauf-Druck (negiert)
        depth_a = min(20, len(asks_curr), len(asks_prev))
        for i in range(depth_a):
            try:
                p_curr, v_curr = float(asks_curr[i][0]), float(asks_curr[i][1])
                p_prev, v_prev = float(asks_prev[i][0]), float(asks_prev[i][1])

                if p_curr < p_prev:
                    ofi -= v_curr          # Ask gesunken → Verkaufsdruck steigt
                elif p_curr == p_prev:
                    ofi -= (v_curr - v_prev)
            except (IndexError, ValueError, TypeError):
                continue

        return round(ofi, 2)

    def _calculate_liquidation_asymmetry(
        self, walls: list, current_price: float
    ) -> dict:
        """
        Berechnet Richtungs-Asymmetrie der Liquidations-Cluster.

        Shorts oberhalb = Long-Positionen die beim Preisstieg liquidiert werden
        (= Short-Squeeze-Fuel → Preis steigt schneller)

        Longs unterhalb = Long-Positionen die beim Preisfall liquidiert werden
        (= Long-Liquidation-Fuel → Preis fällt schneller)

        Rückgabe:
        {
            "shorts_above_m": float,     # Short-Liquidationen oberhalb, in Mio. USD
            "longs_below_m": float,      # Long-Liquidationen unterhalb, in Mio. USD
            "asymmetry_ratio": float,    # shorts_above / longs_below
            "bias": str,                 # "upside" | "downside" | "balanced"
            "squeeze_potential": bool    # True wenn ratio > 2.0
        }
        """
        if not walls or not current_price:
            return {
                "shorts_above_m": 0.0, "longs_below_m": 0.0,
                "asymmetry_ratio": 1.0, "bias": "balanced",
                "squeeze_potential": False
            }

        # In der Liquidations-DB sind Force-Orders gespeichert
        # Zone > current_price → Short-Liquidationen (Shorts die squeezed werden)
        # Zone < current_price → Long-Liquidationen (Longs die ausgestoppt werden)
        shorts_above = sum(
            w.get("amount", 0) for w in walls
            if w.get("zone", 0) > current_price * 1.001  # mind. 0.1% oberhalb
        )
        longs_below = sum(
            w.get("amount", 0) for w in walls
            if w.get("zone", 0) < current_price * 0.999  # mind. 0.1% unterhalb
        )

        if longs_below == 0:
            ratio = 3.0 if shorts_above > 0 else 1.0
        else:
            ratio = shorts_above / longs_below

        if ratio > 1.5:
            bias = "upside"    # Short-Squeeze-Potential dominiert
        elif ratio < 0.67:
            bias = "downside"  # Long-Liquidation-Potential dominiert
        else:
            bias = "balanced"

        return {
            "shorts_above_m": round(shorts_above / 1e6, 1),
            "longs_below_m": round(longs_below / 1e6, 1),
            "asymmetry_ratio": round(ratio, 2),
            "bias": bias,
            "squeeze_potential": ratio > 2.0,
        }

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
            ofi = self._calculate_ofi(ob, self.prev_ob)
            self.prev_ob = ob
            
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
            liq_asymmetry = self._calculate_liquidation_asymmetry(liq_walls, best_bid_p)

            # 4. Payload & Signal Generation
            payload = {
                "symbol": self.symbol,
                "price": best_bid_p,
                "VAMP": round(vamp, 2),
                "CVD": round(self.cvd_cumulative, 2),
                "OFI": round(ofi, 2),
                "Liquidation_Walls": liq_walls,
                "Liq_Asymmetry": liq_asymmetry,
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
                    "macro_status": grss_data.get("Macro_Status", "unknown"),
                    "vix": grss_data.get("VIX", 0.0),
                    "yields_10y": grss_data.get("Yields_10Y", 0.0),
                    "dxy_change_pct": grss_data.get("DXY_Change_Pct", 0.0),
                    "m2_yoy_pct": grss_data.get("M2_YoY_Pct", 0.0),
                    "funding_rate": grss_data.get("Funding_Rate", 0.0),
                    "funding_divergence": grss_data.get("Funding_Divergence", 0.0),
                    "oi_delta_pct": grss_data.get("OI_Delta_Pct", 0.0),
                    "perp_basis_pct": grss_data.get("Perp_Basis_Pct", 0.0),
                    "long_short_ratio": grss_data.get("Long_Short_Ratio", 1.0),
                    "put_call_ratio": grss_data.get("Put_Call_Ratio", 0.0),
                    "dvol": grss_data.get("DVOL", 0.0),
                    "stablecoin_delta_bn": grss_data.get("Stablecoin_Delta_Bn", 0.0),
                    "llm_news_sentiment": grss_data.get("LLM_News_Sentiment", 0.0),
                    "retail_score": grss_data.get("Retail_Score", 0.0),
                    "retail_fomo_warning": grss_data.get("Retail_FOMO_Warning", False),
                    "fresh_source_count": grss_data.get("Fresh_Source_Count", 0),
                    "news_silence_seconds": grss_data.get("News_Silence_Seconds", 0.0),
                }
                
                # Markt-Kontext für Cascade
                market_context = {
                    "btc_price": best_bid_p,
                    "funding_rate": grss_data.get("Funding_Rate", 0.0),
                    "vix": grss_data.get("VIX", 0.0),
                    "oi_delta_pct": grss_data.get("OI_Delta_Pct", 0.0),
                    "put_call_ratio": grss_data.get("Put_Call_Ratio", 0.0),
                    "ndx_status": grss_data.get("Macro_Status", "unknown"),
                    "llm_news_sentiment": grss_data.get("LLM_News_Sentiment", 0.0),
                    "retail_score": grss_data.get("Retail_Score", 0.0),
                    "retail_fomo_warning": grss_data.get("Retail_FOMO_Warning", False),
                    "fresh_source_count": grss_data.get("Fresh_Source_Count", 0),
                    "news_silence_seconds": grss_data.get("News_Silence_Seconds", 0.0),
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

