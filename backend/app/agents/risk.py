import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import text
from typing import Dict, Any, List, Optional
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import SignalDirection
from app.core.log_manager import LogManager, LogCategory, LogLevel

class RiskAgent(PollingAgent):
    """
    Phase 6: Risk Agent (Veto-Matrix).
    Guard-Vetos (News Silence, CVD Divergences, Liquidation Clusters).
    Refined: Cluster-Buster ±0.25% & Health/Latency Telemetry.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("risk", deps)
        self.last_price = 0.0
        self.last_cvd = 0.0

    def get_interval(self) -> float:
        """1-Minuten-Intervall — ausreichend für Medium-Frequency."""
        return 60.0

    async def setup(self) -> None:
        """Initialisierung der Risiko-Matrix."""
        self.logger.info("RiskAgent gestartet. Veto-Matrix aktiv.")
        await self.deps.log_manager.add_log(
            LogLevel.INFO,
            LogCategory.AGENT,
            "agent.risk",
            "RiskAgent gestartet. Veto-Matrix aktiv."
        )
        self.last_price = 0.0
        self.last_cvd = 0.0

    async def _report_health(self, source: str, status: str, latency: float):
        """Meldet Status und Latenz an den globalen Redis-Health-Hub."""
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.deps.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.deps.redis.set_cache("bruno:health:sources", current_map)

    async def _check_liquidation_zones(self, current_price: float, walls: List[Dict]) -> Optional[str]:
        """Prüft die Distanz zu den vom QuantAgent gemeldeten Liquidation Walls."""
        if current_price <= 0:
            return None
        for wall in walls:
            zone_price = wall.get("zone", 0.0)
            amount = wall.get("amount", 0.0)
            if zone_price > 0 and abs(zone_price - current_price) / current_price <= 0.005:
                return f"VETO: Death Zone! Wall von {amount:,.0f} USDT bei {zone_price} (0.5% Range)."
        return None

    async def _fetch_all_signals(self) -> Dict[str, Any]:
        return {
            "context": await self.deps.redis.get_cache("bruno:context:grss") or {},
            "micro": await self.deps.redis.get_cache("bruno:quant:micro") or {}
        }

    async def process(self) -> None:
        try:
            # 1. Signale sammeln
            signals = await self._fetch_all_signals()
            context = signals["context"]
            micro = signals["micro"]

            # Defaults, damit der Agent bei Startup oder Teilausfällen nicht crasht
            grss = 0.0
            vix = 0.0
            yields = 0.0
            dvol = 55.0
            pcr = 0.6
            macro_status = "BULLISH"
            price = 0.0
            walls: List[Dict] = []
            
            # Veto-Initialisierung
            veto = False
            reason = "Monitoring..."
            leverage = 1.0 
            reason_notes: List[str] = []
            
            if not context or not micro:
                veto, reason, leverage = True, "DATA GAP: Missing input signals.", 0.0
            else:
                # 2. News Silence Watchdog (Harter Checkout 3600s)
                last_update_str = context.get("last_update")
                if last_update_str:
                    last_update = datetime.fromisoformat(last_update_str)
                    age = (datetime.now(timezone.utc) - last_update).total_seconds()
                    if age > 3600:
                        veto, reason, leverage = True, "VETO: News Silence > 3600s. Bot in Standby.", 0.0

                # 3. Market Metrics & GRSS
                grss = context.get("GRSS_Score", 0.0)
                vix = context.get("VIX", 0.0)
                yields = context.get("Yields_10Y", 0.0)
                
                # Neue Keys aus erweitertem ContextAgent-Payload
                dvol = context.get("DVOL", 55.0)
                pcr = context.get("Put_Call_Ratio", 0.6)
                
                if grss < 40:
                    veto, reason, leverage = True, f"VETO: Low GRSS ({grss}). Risk-Off Mode.", 0.0
                elif vix > 25:
                    veto, reason, leverage = True, f"VETO: Market Stress High (VIX: {vix}).", 0.0
                elif yields > 4.5:
                    veto, reason, leverage = True, f"VETO: Yields High (10Y: {yields}%).", 0.0
                
                # DVOL > 80: Hohe implizite Vola → Leverage halbieren (kein harter Veto)
                if not veto and dvol > 80:
                    leverage = leverage * 0.5 if leverage > 0 else 0
                    dvol_note = f"DVOL hoch ({dvol:.0f}) — Leverage auf 50% reduziert"
                    reason_notes.append(dvol_note)
                    self.logger.warning(dvol_note)
                
                # 4. Nasdaq SMA200 Hard Veto (Longs ONLY)
                macro_status = context.get("Macro_Status", "BULLISH")
                
                # 5. Todeszonen-Filter (<0.5% Distanz zu Liq-Wall)
                price = micro.get("price", 0.0)
                walls = micro.get("Liquidation_Walls", [])
                liq_veto = await self._check_liquidation_zones(price, walls)
                if liq_veto:
                    veto, reason, leverage = True, liq_veto, 0.0

                # 6. CVD Divergence Check
                cvd = micro.get("CVD", 0.0)
                if self.last_price > 0:
                    price_dir = 1 if price > self.last_price else -1 if price < self.last_price else 0
                    cvd_dir = 1 if cvd > self.last_cvd else -1 if cvd < self.last_cvd else 0
                    if price_dir == 1 and cvd_dir == -1:
                        # CVD Veto ist weicher (Abwertung statt Sperre)
                        leverage *= 0.5
                
                self.last_price, self.last_cvd = price, cvd

            # 7. Finale Entscheidung mit Nasdaq Filter-Check (Institutional 2026)
            long_veto = veto or (macro_status == "BEARISH")
            short_veto = veto # Shorts bleiben erlaubt bei Nasdaq Bear-State
            
            # 7. Finale Entscheidung
            final_reason = reason if veto else ("Nasdaq BEARISH: Longs blocked." if long_veto else "All clear.")
            if reason_notes:
                final_reason = f"{final_reason} | {'; '.join(reason_notes)}"

            final_decision = {
                "Veto_Active": veto,
                "Long_Veto_Active": long_veto,
                "Short_Veto_Active": short_veto,
                "Reason": final_reason,
                "Max_Leverage": leverage if not long_veto else (leverage * 0.5 if not veto else 0.0),
                "DVOL_At_Decision": round(dvol, 1),
                "PCR_At_Decision": round(pcr, 3),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Veto-State-Change detektieren und loggen
            prev_veto_raw = await self.deps.redis.redis.get("bruno:veto:previous")
            prev_veto = json.loads(prev_veto_raw).get("Veto_Active", None) if prev_veto_raw else None

            if prev_veto != veto:  # Nur bei Zustandswechsel
                veto_event = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "veto_active": veto,
                    "reason": final_reason,
                    "grss": decision.get("GRSS_Score") if not veto else None,
                    "vix": decision.get("VIX"),
                    "change": "VETO_ON" if veto else "VETO_OFF",
                }
                await self.deps.redis.redis.lpush(
                    "bruno:veto:history", json.dumps(veto_event)
                )
                await self.deps.redis.redis.ltrim("bruno:veto:history", 0, 49)

            await self.deps.redis.redis.set(
                "bruno:veto:previous", json.dumps({"Veto_Active": veto})
            )

            # DIRECT REDIS CALLS FOR ZERO LATENCY
            # Wir nutzen das interne redis-Objekt für maximale Performance
            decision_json = json.dumps(final_decision)
            await self.deps.redis.redis.set("bruno:veto:state", decision_json)
            await self.deps.redis.redis.publish("bruno:pubsub:veto", decision_json)

            if veto:
                self.logger.warning(f"VETO AKTIVIERT: {reason}")

        except Exception as e:
            self.logger.error(f"RiskAgent Fehler: {e}")

