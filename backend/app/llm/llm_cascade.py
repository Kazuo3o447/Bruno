"""
LLM Cascade — Phase C Core

3-Layer sequentielle Entscheidungslogik mit 4 Gates.

Aufruf: ContextAgent oder QuantAgent — nach GRSS-Check, vor ExecutionAgent.
Der Cascade-Output wird als Signal-Felder weitergereicht:
  signal["layer1_output"], signal["layer2_output"], signal["layer3_output"]
  signal["regime"], signal["grss"]

Alle LLM-Aufrufe nutzen llm_provider.generate_json() — nie rohe Strings.
Der FailureWatchList-Mechanismus injiziert aktive Fehler-Patterns in Layer 2.

Integration in bestehenden Flow:
  QuantAgent → [LLMCascade.run()] → RiskAgent → ExecutionAgent
  (Der QuantAgent sendet das Signal erst NACH der Kaskade)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.llm_provider import BaseLLMProvider as LLMProvider
from app.services.regime_config_v2 import RegimeManager, REGIME_CONFIGS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Datenstrukturen
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CascadeResult:
    """Vollständiger Output der LLM-Kaskade."""

    # Finale Entscheidung
    decision: str = "HOLD"         # "BUY" | "SELL" | "HOLD"
    aborted_at: Optional[str] = None  # Gate wo abgebrochen wurde, oder None

    # Layer-Outputs (für Reasoning Trail + Post-Trade Debrief)
    layer1: dict = field(default_factory=dict)
    layer2: dict = field(default_factory=dict)
    layer3: dict = field(default_factory=dict)

    # Extrahierte Werte für ExecutionAgent
    regime: str = "unknown"
    final_confidence: float = 0.0
    stop_loss_pct: float = 0.010
    take_profit_pct: float = 0.020

    # Timing
    duration_ms: float = 0.0

    @property
    def is_actionable(self) -> bool:
        """True wenn der Cascade ein ausführbares Signal produziert hat."""
        return self.decision in ("BUY", "SELL") and self.aborted_at is None

    def to_signal_extras(self) -> dict:
        """
        Felder die an das QuantAgent-Signal angehängt werden.
        ExecutionAgent liest diese für PositionTracker und Reasoning Trail.
        """
        return {
            "layer1_output": self.layer1,
            "layer2_output": self.layer2,
            "layer3_output": self.layer3,
            "regime": self.regime,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "cascade_confidence": self.final_confidence,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

def _build_layer1_prompt(grss_components: dict, market_snapshot: dict) -> str:
    return f"""Analysiere das aktuelle Bitcoin-Marktregime mit Fokus auf institutionelle Flows.

GRSS-Komponenten & Neue Signale:
{json.dumps(grss_components, ensure_ascii=False, indent=2)}

Markt-Snapshot (Micro/Liquidity):
{json.dumps(market_snapshot, ensure_ascii=False, indent=2)}

Institutionelle Kontexte:
- ETF Flows: {market_snapshot.get('etf_flows_3d_m', 'N/A')}
- OI-Trend: {market_snapshot.get('oi_trend', 'N/A')}
- Market Patterns: {market_snapshot.get('active_patterns', 'N/A')}

Bestimme das aktuelle Regime und deine Konfidenz.
Gib zurück als JSON:
{{
    "regime": "trending_bull|ranging|high_vola|bear|capitulation_rebound",
    "confidence": 0.0 bis 1.0,
    "key_signals": ["Signal 1", "Signal 2", "Signal 3"],
    "reasoning": "Warum dieses Regime? (max 30 Wörter)"
}}"""


def _build_layer2_prompt(
    layer1_output: dict,
    market_context: dict,
    failure_watchlist: list,
    decision_history: list,
) -> str:
    failure_block = ""
    if failure_watchlist:
        failure_block = f"""
AKTIVE FAILURE-PATTERNS (aus vergangenen Trades — beachte diese besonders):
{json.dumps(failure_watchlist[-3:], ensure_ascii=False, indent=2)}
Prüfe explizit ob das aktuelle Setup diese Muster wiederholt.
"""

    history_block = ""
    if decision_history:
        history_block = f"""
LETZTE 3 ENTSCHEIDUNGEN:
{json.dumps(decision_history, ensure_ascii=False, indent=2)}
"""

    return f"""Du bist ein institutioneller Quant-Trader für Bitcoin.
Analysiere das Chance-Risiko-Verhältnis dieses Setups.
Denke Schritt für Schritt. Sei skeptisch gegenüber dem Offensichtlichen.
{failure_block}
LAYER 1 REGIME-ANALYSE:
{json.dumps(layer1_output, ensure_ascii=False, indent=2)}

VOLLSTÄNDIGER MARKTKONTEXT:
{json.dumps(market_context, ensure_ascii=False, indent=2)}
{history_block}
Gib zurück als JSON:
{{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.0 bis 1.0,
    "entry_reasoning": "Haupt-Argument für die Entscheidung (max 50 Wörter)",
    "risk_factors": ["Risiko 1", "Risiko 2"],
    "suggested_sl_pct": 0.008 bis 0.020,
    "suggested_tp_pct": 0.016 bis 0.040
}}"""


def _build_layer3_prompt(layer2_output: dict, market_context: dict) -> str:
    return f"""Du hast EINE Aufgabe: Finde Gründe warum der folgende Trade FALSCH ist.
Sei hart. Sei kritisch. Keine Höflichkeit.

TRADE-ENTSCHEIDUNG (Layer 2):
{json.dumps(layer2_output, ensure_ascii=False, indent=2)}

MARKTDATEN (Bear-Case Suche):
Funding: {market_context.get('funding_rate', 'N/A')}
GRSS: {market_context.get('grss', 'N/A')}
ETF Flows: {market_context.get('etf_flow_today_m', 'N/A')}
OI-7d: {market_context.get('oi_7d_change_pct', 'N/A')}
OI-Trend: {market_context.get('oi_trend', 'N/A')}
Max Pain Distance: {market_context.get('max_pain_dist_pct', 'N/A')}%
VIX: {market_context.get('vix', 'N/A')}

Gib zurück als JSON:
{{
    "blocker": true oder false,
    "blocking_reasons": ["Grund 1", "Grund 2"],
    "risk_override": false
}}

Setze blocker=true wenn mindestens ein schwerwiegender Grund vorliegt."""


# ─────────────────────────────────────────────────────────────────────────────
# LLM Cascade
# ─────────────────────────────────────────────────────────────────────────────

# Gate-Schwellwerte
GATE1_MIN_CONFIDENCE = 0.60
GATE2_MIN_CONFIDENCE = 0.65


class LLMCascade:
    """
    3-Layer LLM-Entscheidungskaskade.

    Flow:
        GRSS Gate (extern, vor Cascade-Aufruf)
            ↓
        Layer 1: Regime (qwen2.5:14b, temp 0.1)
            ↓ Gate 1: confidence >= 0.60
        Layer 2: Decision (deepseek-r1:14b, temp 0.3) + FailureWatchList
            ↓ Gate 2: decision != HOLD und confidence >= 0.65
        Layer 3: Advocatus Diaboli (qwen2.5:14b, temp 0.5)
            ↓ Gate 3: blocker == False
        → CascadeResult(decision=BUY/SELL)

    Alle Gates produzieren CascadeResult(decision=HOLD) — kein Exception-Pfad.
    """

    def __init__(self, redis_client, llm_provider: LLMProvider):
        self.redis = redis_client
        self.llm_provider = llm_provider
        self.regime_manager = RegimeManager(redis_client)
        self._initialized = False

    def _get_confidence_thresholds(self) -> tuple[float, float]:
        """
        Gibt (layer1_min, layer2_min) zurück.
        DRY_RUN + Learning Mode: niedrigere Schwellen.
        Live: immer Produktions-Schwellen.
        """
        import os

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except Exception:
            return 0.60, 0.65

        dry_run = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")

        if not dry_run:
            return (
                float(cfg.get("LEARNING_Layer1_Confidence_PROD", 0.60)),
                float(cfg.get("LEARNING_Layer2_Confidence_PROD", 0.65)),
            )

        if cfg.get("LEARNING_MODE_ENABLED", False):
            return (
                float(cfg.get("LEARNING_Layer1_Confidence", 0.50)),
                float(cfg.get("LEARNING_Layer2_Confidence", 0.55)),
            )

        return (
            float(cfg.get("LEARNING_Layer1_Confidence_PROD", 0.60)),
            float(cfg.get("LEARNING_Layer2_Confidence_PROD", 0.65)),
        )

    async def initialize(self) -> None:
        """Einmalig beim Agenten-Start aufrufen."""
        await self.regime_manager.load_from_redis()
        self._initialized = True
        logger.info("LLMCascade initialisiert.")

    async def run(
        self,
        grss_components: dict,
        market_context: dict,
        grss_score: float,
    ) -> CascadeResult:
        """
        Führt die vollständige 3-Layer-Kaskade aus.

        grss_components: Dict mit allen GRSS-Einzelwerten (für Layer 1 Kontext)
        market_context:  Vollständiger Markt-Snapshot (für Layer 2+3)
        grss_score:      Aggregierter GRSS-Wert (0-100)

        Gibt immer ein CascadeResult zurück — nie eine Exception.
        """
        t_start = time.perf_counter()
        market_context["grss"] = grss_score  # Layer 3 braucht GRSS direkt

        result = CascadeResult()
        layer1_min_confidence, layer2_min_confidence = self._get_confidence_thresholds()

        # ── GRSS Gate (vor Cascade) ───────────────────────────────────────
        await self._report_pulse("gate_grss", "checking")
        effective_threshold = self.regime_manager.get_effective_grss_threshold()
        if grss_score < effective_threshold:
            result.aborted_at = "grss_gate"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            logger.info(
                f"Cascade HOLD @ GRSS Gate: {grss_score:.1f} < {effective_threshold} "
                f"(Regime: {self.regime_manager._current_regime}, "
                f"Transition: {self.regime_manager.is_in_transition()})"
            )
            await self._report_pulse("gate_grss", "aborted", {"reason": f"{grss_score:.1f} < {effective_threshold}"})
            await self._log_to_redis(result)
            return result
        await self._report_pulse("gate_grss", "passed")

        # ── Layer 1: Regime-Klassifikation ──────────────────────────────────
        await self._report_pulse("layer1", "running")
        logger.debug("Cascade: Layer 1 gestartet...")
        l1_raw = await self.llm_provider.generate_json(
            prompt=_build_layer1_prompt(grss_components, {
                "btc_price": market_context.get("btc_price"),
                "funding_rate": market_context.get("funding_rate"),
                "vix": market_context.get("vix"),
                "oi_delta_pct": market_context.get("oi_delta_pct"),
                "put_call_ratio": market_context.get("put_call_ratio"),
                "ndx_status": market_context.get("ndx_status"),
                "etf_flows_3d_m": market_context.get("etf_flow_3d_m"),
                "oi_trend": market_context.get("oi_trend"),
                "active_patterns": market_context.get("active_patterns")
            }),
            layer_name="layer1_regime",
            use_reasoning_model=False,
        )
        result.layer1 = l1_raw

        # Regime persistieren (2-Bestätigungs-Logik)
        raw_regime = l1_raw.get("regime", "unknown")
        confirmed_regime = await self.regime_manager.update(raw_regime)
        result.regime = confirmed_regime

        # Gate 1
        l1_confidence = float(l1_raw.get("confidence", 0.0))
        if l1_raw.get("_parse_error") or l1_confidence < layer1_min_confidence:
            result.aborted_at = "gate1"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            logger.info(
                f"Cascade HOLD @ Gate1: confidence={l1_confidence:.2f} "
                f"(min={layer1_min_confidence}) | regime={raw_regime}"
            )
            await self._report_pulse("layer1", "aborted", {"reason": f"confidence {l1_confidence:.2f} < {layer1_min_confidence}"})
            await self._log_to_redis(result)
            return result
        await self._report_pulse("layer1", "passed", {"regime": confirmed_regime})

        # ── Layer 2: Strategisches Reasoning ────────────────────────────────
        await self._report_pulse("layer2", "running")
        logger.debug("Cascade: Layer 2 gestartet...")
        failure_watchlist = await self._get_failure_watchlist()
        decision_history = await self._get_decision_history()

        l2_raw = await self.llm_provider.generate_json(
            prompt=_build_layer2_prompt(
                layer1_output=l1_raw,
                market_context=market_context,
                failure_watchlist=failure_watchlist,
                decision_history=decision_history,
            ),
            layer_name="layer2_reasoning",
            use_reasoning_model=True,  # deepseek-r1:14b
        )
        result.layer2 = l2_raw

        # Gate 2
        l2_decision = l2_raw.get("decision", "HOLD").upper()
        l2_confidence = float(l2_raw.get("confidence", 0.0))

        if (l2_raw.get("_parse_error")
                or l2_decision == "HOLD"
                or l2_confidence < layer2_min_confidence):
            result.aborted_at = "gate2"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            logger.info(
                f"Cascade HOLD @ Gate2: decision={l2_decision} "
                f"confidence={l2_confidence:.2f} (min={layer2_min_confidence})"
            )
            await self._report_pulse("layer2", "aborted", {"decision": l2_decision, "confidence": l2_confidence})
            await self._log_to_redis(result)
            return result
        await self._report_pulse("layer2", "passed", {"decision": l2_decision})

        # Regime-Config validieren: erlaubt das Regime diese Richtung?
        regime_cfg = self.regime_manager.get_config()
        if l2_decision == "BUY" and not regime_cfg.allow_longs:
            logger.info(f"Cascade HOLD: Longs im Regime '{confirmed_regime}' nicht erlaubt.")
            result.aborted_at = "regime_gate"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            await self._report_pulse("layer2", "aborted", {"reason": "regime avoids longs"})
            return result
        if l2_decision == "SELL" and not regime_cfg.allow_shorts:
            logger.info(f"Cascade HOLD: Shorts im Regime '{confirmed_regime}' nicht erlaubt.")
            result.aborted_at = "regime_gate"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            await self._report_pulse("layer2", "aborted", {"reason": "regime avoids shorts"})
            return result

        # ── Layer 3: Advocatus Diaboli ───────────────────────────────────────
        await self._report_pulse("layer3", "running")
        logger.debug("Cascade: Layer 3 gestartet...")
        l3_raw = await self.llm_provider.generate_json(
            prompt=_build_layer3_prompt(l2_raw, market_context),
            layer_name="layer3_devil",
            use_reasoning_model=False,
        )
        result.layer3 = l3_raw

        # Gate 3
        if l3_raw.get("_parse_error") or l3_raw.get("blocker", True):
            result.aborted_at = "layer3_blocker"
            result.duration_ms = (time.perf_counter() - t_start) * 1000
            reasons = l3_raw.get("blocking_reasons", [])
            logger.info(f"Cascade HOLD @ Layer3 Blocker: {reasons}")
            await self._report_pulse("layer3", "aborted", {"reasons": reasons})
            await self._log_to_redis(result)
            return result
        await self._report_pulse("layer3", "passed")

        # ── Alles grün — Signal produzieren ─────────────────────────────────
        result.decision = l2_decision
        result.final_confidence = l2_confidence

        # SL/TP: Layer-2-Vorschlag oder Regime-Default
        result.stop_loss_pct = float(
            l2_raw.get("suggested_sl_pct", regime_cfg.stop_loss_pct)
        )
        result.take_profit_pct = float(
            l2_raw.get("suggested_tp_pct", regime_cfg.take_profit_pct)
        )

        # Hard-Clamp: SL nie über 2%, TP nie über 4%
        result.stop_loss_pct = max(0.005, min(result.stop_loss_pct, 0.020))
        result.take_profit_pct = max(0.010, min(result.take_profit_pct, 0.040))

        result.duration_ms = (time.perf_counter() - t_start) * 1000

        logger.info(
            f"Cascade SIGNAL: {result.decision} | "
            f"Regime={result.regime} | Confidence={result.final_confidence:.2f} | "
            f"SL={result.stop_loss_pct:.1%} | TP={result.take_profit_pct:.1%} | "
            f"Dauer={result.duration_ms:.0f}ms"
        )

        # Rolling Decision History aktualisieren
        await self._update_decision_history(result)
        await self._log_to_redis(result)
        await self._report_pulse("signal", "generated", {"decision": result.decision})

        return result

    # ── Redis Helpers ────────────────────────────────────────────────────────

    async def _get_failure_watchlist(self) -> list:
        """Aktive Failure-Patterns aus BRUNO_LEARNING (FailureWatchList)."""
        data = await self.redis.get_cache("bruno:failure_watchlist")
        return data if isinstance(data, list) else []

    async def _get_decision_history(self) -> list:
        """Letzte 3 Cascade-Entscheidungen als Rolling Context für Layer 2."""
        data = await self.redis.get_cache("bruno:llm:decision_history")
        return data if isinstance(data, list) else []

    async def _update_decision_history(self, result: CascadeResult) -> None:
        """Fügt die aktuelle Entscheidung zur Rolling History hinzu (max 3)."""
        history = await self._get_decision_history()
        history.append({
            "decision": result.decision,
            "regime": result.regime,
            "confidence": result.final_confidence,
            "sl_pct": result.stop_loss_pct,
            "tp_pct": result.take_profit_pct,
            "l1_signals": result.layer1.get("key_signals", []),
        })
        await self.redis.set_cache(
            "bruno:llm:decision_history",
            history[-3:],   # Nur letzte 3 behalten
        )

    async def _log_to_redis(self, result: CascadeResult) -> None:
        """Speichert letzten Cascade-Run für Dashboard-Anzeige."""
        await self.redis.set_cache(
            "bruno:llm:last_cascade",
            {
                "decision": result.decision,
                "aborted_at": result.aborted_at,
                "regime": result.regime,
                "confidence": result.final_confidence,
                "duration_ms": result.duration_ms,
                "layer1_regime": result.layer1.get("regime"),
                "layer1_confidence": result.layer1.get("confidence"),
                "layer2_decision": result.layer2.get("decision"),
                "layer3_blocker": result.layer3.get("blocker"),
                "transition_active": self.regime_manager.is_in_transition(),
                "transition_cycles_left": self.regime_manager._transition_cycle,
                "effective_grss_threshold": self.regime_manager.get_effective_grss_threshold(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            ttl=600,  # 10 Minuten
        )

    async def _report_pulse(self, step: str, status: str, data: Optional[dict] = None) -> None:
        """Sendet Echtzeit-Fortschritt an Redis für das Dashboard."""
        pulse = {
            "step": step,
            "status": status,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.redis.set_cache("bruno:llm:pulse", pulse, ttl=120)
        logger.debug(f"Cascade Pulse: {step} -> {status}")
