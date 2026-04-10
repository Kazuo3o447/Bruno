import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import text
from typing import Dict, Any, List, Optional
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.core.config_cache import ConfigCache
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
        # Initialize ConfigCache
        from app.core.config_cache import ConfigCache
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        ConfigCache.init(config_path)
        
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
        prod_threshold = ConfigCache.get("GRSS_Threshold", 40.0)

        if not self.deps.config.DRY_RUN:
            return prod_threshold

        learning_enabled = ConfigCache.get("LEARNING_MODE_ENABLED", 0.0)
        if learning_enabled:
            learning_threshold = ConfigCache.get("LEARNING_GRSS_Threshold", 25.0)
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
        PROMPT 8: Circuit Breaker überarbeitet.
        
        Globaler Block (24h) NUR bei:
        - Hartem prozentualen Daily Drawdown (z.B. -3% vom Portfolio)
        
        Slot-spezifische Verlustzählung:
        - 3 aufeinanderfolgende Losses im gleichen Slot blockieren nur diesen Slot
        - Andere Slots können weiter traden
        
        Liest: bruno:portfolio:state (geschrieben vom ExecutionAgent)
        Setzt: bruno:risk:daily_block (Redis, 24h TTL)
              bruno:risk:slot_block:{slot_name} (Redis, 24h TTL)
        
        Profitrader-Begründung: Normale Streuung über verschiedene Slots
        sollte den Bot nicht für 24 Stunden abschalten.
        """
        # Prüfe ob globaler Block schon aktiv
        block = await self.deps.redis.get_cache("bruno:risk:daily_block")
        if block and block.get("active"):
            return {"blocked": True, "reason": f"DAILY BLOCK: {block.get('reason', 'Drawdown limit')}"}
        
        # Portfolio-State laden
        portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
        initial = float(portfolio.get("initial_capital_eur", 1000))
        daily_pnl = float(portfolio.get("daily_pnl_eur", 0))
        
        # Bedingung 1: > 3% Tagesverlust (HARD DRAWDOWN BLOCK)
        max_daily_loss = float(ConfigCache.get("DAILY_MAX_LOSS_PCT", 3.0))
        daily_loss_pct = abs(daily_pnl / initial * 100) if daily_pnl < 0 else 0
        
        if daily_loss_pct >= max_daily_loss:
            block_data = {
                "active": True,
                "reason": f"HARD DRAWDOWN: {daily_loss_pct:.1f}% >= {max_daily_loss}%",
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "type": "hard_drawdown",
            }
            await self.deps.redis.set_cache("bruno:risk:daily_block", block_data, ttl=86400)
            self.logger.critical(f"HARD DRAWDOWN BLOCK: {block_data['reason']}")
            return {"blocked": True, "reason": f"DAILY BLOCK: {block_data['reason']}"}
        
        # PROMPT 8: Kein globaler Block mehr bei 3 aufeinanderfolgenden Losses
        # Stattdessen: Slot-spezifische Verlustzählung in _check_slot_consecutive_losses()
        
        return {"blocked": False, "reason": ""}
    
    async def _check_slot_consecutive_losses(self, slot_name: str) -> dict:
        """
        PROMPT 8: Slot-spezifische Circuit Breaker Logik.
        
        Zählt aufeinanderfolgende Verluste pro Slot separat.
        Ein Slot mit 3 Losses wird blockiert, andere Slots laufen weiter.
        
        Redis Keys:
        - bruno:risk:slot_losses:{slot_name} - Liste der letzten P&Ls pro Slot
        - bruno:risk:slot_block:{slot_name} - Block-Status pro Slot
        """
        # Prüfe ob Slot bereits blockiert
        slot_block = await self.deps.redis.get_cache(f"bruno:risk:slot_block:{slot_name}")
        if slot_block and slot_block.get("active"):
            return {"blocked": True, "reason": f"SLOT BLOCK: {slot_block.get('reason')}"}
        
        # Lade Slot-spezifische Trade-Historie
        slot_losses = await self.deps.redis.get_cache(f"bruno:risk:slot_losses:{slot_name}") or []
        
        max_consecutive = int(ConfigCache.get("MAX_CONSECUTIVE_LOSSES", 3))
        
        # Zähle aufeinanderfolgende Verluste
        if len(slot_losses) >= max_consecutive:
            recent = slot_losses[-max_consecutive:]
            if all(p < 0 for p in recent):
                block_data = {
                    "active": True,
                    "reason": f"{max_consecutive} consecutive losses in {slot_name} slot",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "slot": slot_name,
                    "type": "slot_consecutive_losses",
                }
                await self.deps.redis.set_cache(
                    f"bruno:risk:slot_block:{slot_name}", block_data, ttl=86400
                )
                self.logger.critical(f"SLOT CONSECUTIVE LOSS BLOCK [{slot_name}]: {block_data['reason']}")
                return {"blocked": True, "reason": f"SLOT BLOCK: {block_data['reason']}"}
        
        return {"blocked": False, "reason": ""}
    
    async def record_slot_trade_result(self, slot_name: str, pnl: float) -> None:
        """
        PROMPT 8: Speichert Trade-Ergebnis für slot-spezifische Verlustzählung.
        
        Args:
            slot_name: Name des Slots (trend, sweep, funding)
            pnl: P&L des Trades in EUR (positiv oder negativ)
        """
        try:
            key = f"bruno:risk:slot_losses:{slot_name}"
            slot_losses = await self.deps.redis.get_cache(key) or []
            
            # Füge neues Ergebnis hinzu, behalte letzte 10
            slot_losses.append(pnl)
            slot_losses = slot_losses[-10:]
            
            await self.deps.redis.set_cache(key, slot_losses, ttl=86400)
            
            self.logger.info(
                f"Slot trade recorded [{slot_name}]: PnL={pnl:+.2f} EUR, "
                f"history={len(slot_losses)} trades"
            )
        except Exception as e:
            self.logger.warning(f"Record slot trade error: {e}")

    async def validate_and_size_order(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        PROMPT 9: Synchrone Order-Validierung und Sizing.
        
        Wird vom Orchestrator im Strict Pipeline Mode aufgerufen.
        Holt FRISCHEN Portfolio-State und führt alle Risk-Checks durch.
        
        Args:
            signal: Das Trading-Signal vom QuantAgent
            
        Returns:
            Order-Payload wenn validiert und sized, None wenn abgelehnt
        """
        from datetime import datetime, timezone
        
        slot_name = signal.get("strategy_slot", "unknown")
        direction = signal.get("direction", "long")
        
        self.logger.info(
            f"PROMPT 9 RISK: Validiere Signal [{slot_name}] {direction.upper()} - "
            f"Frischer Portfolio-State wird geladen..."
        )
        
        try:
            # === SCHRITT 1: Frischer Portfolio-State ===
            portfolio = await self.deps.redis.get_cache("bruno:portfolio:state")
            if not portfolio:
                self.logger.error("PROMPT 9 RISK: Kein Portfolio-State gefunden - Signal abgelehnt")
                return None
            
            capital_eur = portfolio.get("capital_eur", 0.0)
            capital_usd = capital_eur * 1.08  # Annäherung EUR->USD
            
            self.logger.info(
                f"PROMPT 9 RISK: Portfolio geladen - Capital={capital_eur:.2f} EUR "
                f"({capital_usd:.2f} USD)"
            )
            
            # === SCHRITT 2: Slot-spezifische Circuit Breaker Prüfung ===
            slot_check = await self._check_slot_consecutive_losses(slot_name)
            if slot_check["blocked"]:
                self.logger.warning(
                    f"PROMPT 9 RISK: SLOT BLOCK [{slot_name}] - {slot_check['reason']}"
                )
                return None
            
            # === SCHRITT 3: Daily Drawdown Prüfung (Hard -3%) ===
            dd_check = await self._check_daily_drawdown()
            if dd_check["blocked"]:
                self.logger.warning(
                    f"PROMPT 9 RISK: DAILY DRAWDOWN BLOCK - {dd_check['reason']}"
                )
                return None
            
            # === SCHRITT 4: Veto-State Prüfung ===
            veto_data = await self.deps.redis.redis.get("bruno:veto:state")
            if veto_data:
                veto = json.loads(veto_data)
                if veto.get("Veto_Active", False):
                    self.logger.warning(
                        f"PROMPT 9 RISK: GLOBAL VETO aktiv - {veto.get('Reason', 'Unknown')}"
                    )
                    return None
            
            # === SCHRITT 5: Sizing überprüfen/ergänzen ===
            sizing = signal.get("sizing")
            if not sizing or not sizing.get("sizing_valid", False):
                self.logger.error(
                    f"PROMPT 9 RISK: Kein gültiges Sizing im Signal [{slot_name}]"
                )
                return None
            
            # === SCHRITT 6: Fee Hurdle Check (falls noch nicht gemacht) ===
            # Das Signal sollte bereits vom ExecutionAgent validiert sein,
            # aber wir prüfen nochmal als Sicherheit
            position_size_usdt = sizing.get("position_size_usdt", 0)
            if position_size_usdt <= 0:
                self.logger.error(
                    f"PROMPT 9 RISK: Ungültige Position Size: {position_size_usdt}"
                )
                return None
            
            self.logger.info(
                f"PROMPT 9 RISK: Signal FREIGEGEBEN [{slot_name}] "
                f"Size={position_size_usdt:.2f} USDT, Leverage={sizing.get('leverage_used', 0):.1f}x"
            )
            
            # Bereite vollständiges Order-Payload vor
            order_payload = {
                **signal,
                "capital_usd_at_validation": capital_usd,
                "capital_eur_at_validation": capital_eur,
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "risk_validation": {
                    "slot_block_checked": True,
                    "daily_drawdown_checked": True,
                    "veto_checked": True,
                    "portfolio_fresh": True
                }
            }
            
            return order_payload
            
        except Exception as e:
            self.logger.error(f"PROMPT 9 RISK: Validierungsfehler: {e}", exc_info=True)
            return None

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
                # Kritische API-Werte müssen vorhanden sein (nur wenn konfiguriert)
                require_inst_data = ConfigCache.get("REQUIRE_INSTITUTIONAL_DATA_FOR_TRADE", False)
                if require_inst_data:
                    dvol = context.get("DVOL")
                    ls_ratio = context.get("Long_Short_Ratio")
                    
                    if dvol is None or ls_ratio is None:
                        veto, reason = True, f"DATA GAP: Critical API missing - DVOL={dvol}, L/S={ls_ratio}"
                else:
                    # Learning Mode: Missing data reduces conviction but doesn't hard veto
                    dvol = context.get("DVOL")
                    ls_ratio = context.get("Long_Short_Ratio")
                    if dvol is None or ls_ratio is None:
                        self.logger.warning(f"DATA GAP: Institutional data missing (DVOL={dvol}, L/S={ls_ratio}) - trading with reduced conviction")
            
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
            
            # ── 5. Death Zone (REMOVED in v3 — Clusters are opportunities) ──
            if not veto:
                pass
                # price = float(micro.get("price", 0))
                # liq = await self.deps.redis.get_cache("bruno:liq:intelligence") or {}
                # for c in liq.get("clusters", []):
                #     if c.get("total_usdt", 0) > 500000 and abs(c.get("distance_pct", 99)) < 0.5:
                #         veto, reason = True, f"VETO: Death Zone {c['zone_price']}"
                #         break
            
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
