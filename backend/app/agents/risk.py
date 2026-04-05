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
        self._grss_threshold: float = 40.0
        
        # v2 Daily Limits
        self.daily_loss_count = 0
        self.daily_loss_amount = 0.0
        self.daily_reset_time = 0.0
        self.max_daily_loss_pct = 0.03  # 3%
        self.max_daily_loss_trades = 3

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
            "RiskAgent setup completed",
            {"grss_threshold": self._grss_threshold}
        )
        self.last_price = 0.0
        self.last_cvd = 0.0
        
        # Daily Reset initialisieren
        self._daily_reset_time = self._get_next_daily_reset()

    def _load_config_value(self, key: str, default: float) -> float:
        """Lädt einen Wert aus config.json. Fallback auf default wenn nicht gefunden."""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        try:
            with open(config_path, "r") as f:
                return float(json.load(f).get(key, default))
        except Exception:
            return default

    def _get_next_daily_reset(self) -> float:
        """Berechnet den nächsten täglichen Reset-Zeitpunkt (UTC 00:00)."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow.timestamp()

    def _check_daily_limits(self) -> Dict[str, bool]:
        """
        Prüft tägliche Limits: Drawdown und Trade-Anzahl.
        """
        import time
        current_time = time.time()
        
        # Daily Reset durchführen
        if current_time >= self._daily_reset_time:
            self.daily_loss_count = 0
            self.daily_loss_amount = 0.0
            self._daily_reset_time = self._get_next_daily_reset()
            self.logger.info("Daily limits reset")
        
        limits = {
            "drawdown_ok": True,
            "trade_count_ok": True
        }
        
        # Daily Drawdown Check
        if self.daily_loss_count >= self.max_daily_loss_trades:
            limits["trade_count_ok"] = False
            self.logger.warning(f"Daily loss trade limit exceeded: {self.daily_loss_count}")
        
        return limits

    def _get_effective_grss_threshold(self) -> float:
        """
        Gibt den effektiven GRSS-Threshold zurück.
        Im DRY_RUN + LEARNING_MODE: niedrigere Schwelle für mehr Trainingsdaten.
        Im Live-Betrieb: immer Produktions-Schwelle, kein Learning Mode möglich.
        """
        prod_threshold = self._load_config_value("GRSS_Threshold", 40.0)

        if not self.deps.config.DRY_RUN:
            return prod_threshold

        learning_enabled = self._load_config_value("LEARNING_MODE_ENABLED", 0.0)
        if learning_enabled:
            learning_threshold = self._load_config_value("LEARNING_GRSS_Threshold", 25.0)
            self.logger.debug(
                f"Learning Mode aktiv: GRSS-Threshold {prod_threshold} → {learning_threshold}"
            )
            return learning_threshold

        return prod_threshold

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

    async def _check_daily_drawdown(self) -> dict:
        """
        Circuit Breaker: Stoppt Trading für 24h wenn:
        - Tagesverlust > 3% des Kapitals, ODER
        - 3 Fehltrades in Folge
        
        Liest: bruno:portfolio:state (geschrieben vom ExecutionAgent)
        Setzt: bruno:risk:daily_block (Redis, 24h TTL)
        
        Profitrader-Begründung: Algorithmen geraten in Marktphasen die
        nicht zu ihrer Logik passen. Der Drawdown-Limit schützt vor
        unkontrollierten Verlustspiralen ("Bot-Tilt").
        """
        # Prüfe ob Block schon aktiv
        block = await self.deps.redis.get_cache("bruno:risk:daily_block")
        if block and block.get("active"):
            return {"blocked": True, "reason": f"DAILY BLOCK: {block.get('reason', 'Drawdown limit')}"}
        
        # Portfolio-State laden
        portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
        initial = float(portfolio.get("initial_capital_eur", 1000))
        current = float(portfolio.get("capital_eur", initial))
        daily_pnl = float(portfolio.get("daily_pnl_eur", 0))
        
        # Verlust-Trades heute zählen
        # trade_pnl_history_eur ist eine Liste der letzten P&L-Werte
        pnl_history = portfolio.get("trade_pnl_history_eur", [])
        
        # Bedingung 1: > 3% Tagesverlust
        max_daily_loss = float(self._load_config_value("DAILY_MAX_LOSS_PCT", 3.0))
        daily_loss_pct = abs(daily_pnl / initial * 100) if daily_pnl < 0 else 0
        
        if daily_loss_pct >= max_daily_loss:
            block_data = {
                "active": True,
                "reason": f"Tagesverlust {daily_loss_pct:.1f}% >= {max_daily_loss}%",
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.deps.redis.set_cache("bruno:risk:daily_block", block_data, ttl=86400)
            self.logger.critical(f"DAILY DRAWDOWN BLOCK: {block_data['reason']}")
            return {"blocked": True, "reason": f"DAILY BLOCK: {block_data['reason']}"}
        
        # Bedingung 2: 3 Fehltrades in Folge
        max_consecutive = int(self._load_config_value("MAX_CONSECUTIVE_LOSSES", 3))
        if len(pnl_history) >= max_consecutive:
            recent = pnl_history[-max_consecutive:]
            if all(p < 0 for p in recent):
                block_data = {
                    "active": True,
                    "reason": f"{max_consecutive} Verluste in Folge",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }
                await self.deps.redis.set_cache("bruno:risk:daily_block", block_data, ttl=86400)
                self.logger.critical(f"CONSECUTIVE LOSS BLOCK: {block_data['reason']}")
                return {"blocked": True, "reason": f"DAILY BLOCK: {block_data['reason']}"}
        
        return {"blocked": False, "reason": ""}

    async def process(self) -> None:
        try:
            signals = await self._fetch_all_signals()
            context = signals["context"]
            micro = signals["micro"]
            
            veto = False
            reason = "All clear."
            
            # ── 1. Data Gap ────────────────────────────────────
            if not context or not micro:
                veto, reason = True, "DATA GAP: Missing input signals."
            
            # ── 1.1 API Data Gap (institutionell) ───────────────────
            if not veto:
                # Kritische API-Werte müssen vorhanden sein
                dvol = context.get("DVOL")
                ls_ratio = context.get("Long_Short_Ratio")
                
                if dvol is None or ls_ratio is None:
                    veto, reason = True, f"DATA GAP: Critical API missing - DVOL={dvol}, L/S={ls_ratio}"
            
            # ── 2. News Silence (ContextAgent tot) ─────────────
            if not veto:
                ts = context.get("timestamp")
                if ts:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
                    if age > 3600:
                        veto, reason = True, "VETO: Context stale > 1h."
            
            # ── 3. VIX > 45 (systemischer Crash) ──────────────
            if not veto:
                vix = float(context.get("VIX", 20))
                if vix > 45:
                    veto, reason = True, f"VETO: VIX {vix:.1f} > 45."
            
            # ── 4. System Pause (Telegram Kill-Switch) ─────────
            if not veto:
                pause = await self.deps.redis.get_cache("bruno:system:paused")
                if pause and pause.get("paused"):
                    veto, reason = True, "VETO: System manuell pausiert."
            
            # ── 5. Death Zone (< 0.5% zu Mega-Wall) ───────────
            if not veto:
                price = float(micro.get("price", 0))
                liq = await self.deps.redis.get_cache("bruno:liq:intelligence") or {}
                for c in liq.get("clusters", []):
                    if c.get("total_usdt", 0) > 500000 and abs(c.get("distance_pct", 99)) < 0.5:
                        veto, reason = True, f"VETO: Death Zone {c['zone_price']}"
                        break
            
            # ── 6. Daily Drawdown Limit (NEU — Profitrader #6) ─
            if not veto:
                dd = await self._check_daily_drawdown()
                if dd["blocked"]:
                    veto, reason = True, dd["reason"]
            
            # ── Publish ────────────────────────────────────────
            decision = {
                "Veto_Active": veto,
                "Long_Veto_Active": veto,
                "Short_Veto_Active": veto,
                "Reason": reason,
                "Max_Leverage": 0.0 if veto else 1.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            decision_json = json.dumps(decision)
            await self.deps.redis.redis.set("bruno:veto:state", decision_json)
            await self.deps.redis.redis.publish("bruno:pubsub:veto", decision_json)
            
            if veto:
                self.logger.warning(f"VETO: {reason}")
        
        except Exception as e:
            self.logger.error(f"RiskAgent Fehler: {e}")
