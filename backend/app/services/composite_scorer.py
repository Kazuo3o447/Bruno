import os
import os
from dataclasses import dataclass, field
from typing import Optional
import json
import logging
from datetime import datetime, timezone
from app.core.config_cache import ConfigCache
from app.services.regime_config import REGIME_CONFIGS

# Regime-basierte Gewichtungs-Presets
WEIGHT_PRESETS = {
    "trending": {"ta": 0.50, "liq": 0.15, "flow": 0.20, "macro": 0.15},
    "ranging":  {"ta": 0.20, "liq": 0.40, "flow": 0.25, "macro": 0.15},
}

@dataclass
class CompositeSignal:
    """Output des Composite Scorers — ersetzt CascadeResult."""
    direction: str = "neutral"
    should_trade: bool = False
    composite_score: float = 0.0
    ta_score: float = 0.0
    liq_score: float = 0.0
    flow_score: float = 0.0
    macro_score: float = 0.0
    mean_reversion_score: float = 0.0  # NEU: Mean Reversion Sub-Engine
    funding_score: float = 0.0         # PROMPT 05: Funding Rate Score
    conviction: float = 0.0
    position_size_pct: float = 0.0
    stop_loss_pct: float = 0.010
    take_profit_pct: float = 0.020
    take_profit_1_pct: float = 0.012
    take_profit_2_pct: float = 0.025
    tp1_size_pct: float = 0.50
    tp2_size_pct: float = 0.50
    breakeven_trigger_pct: float = 0.012
    signals_active: list = field(default_factory=list)
    regime: str = "unknown"
    weight_preset: str = "trending"   # NEU: welches Preset aktiv ist
    price: float = 0.0
    mtf_aligned: bool = False         # NEU: aus TA-Snapshot
    sweep_confirmed: bool = False     # NEU: aus Liq-Intelligence
    diagnostics: dict = field(default_factory=dict)  # NEU: Decision Diagnostics
    mr_mode: bool = False             # PROMPT 02: Mean-Reversion-Modus bei Macro-Konflikt
    
    def to_signal_dict(self, symbol: str = "BTCUSDT") -> dict:
        """Signal-Dict kompatibel mit ExecutionAgentV3."""
        # BRUNO-FIX-08: Echte Position aus sizing übernehmen
        sizing = getattr(self, 'sizing', {}) or {}
        position_btc = float(sizing.get("position_size_btc", 0.0))

        return {
            "symbol": symbol,
            "side": "buy" if self.direction == "long" else "sell",
            "amount": position_btc,  # War 0.0 — jetzt echte Größe
            "position_size_hint_pct": self.position_size_pct,  # Hint für Execution
            "price": self.price,
            "composite_score": self.composite_score,
            "ta_score": self.ta_score,
            "liq_score": self.liq_score,
            "flow_score": self.flow_score,
            "macro_score": self.macro_score,
            "mean_reversion_score": self.mean_reversion_score,
            "funding_score": self.funding_score,  # PROMPT 05
            "conviction": self.conviction,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "take_profit_1_pct": self.take_profit_1_pct,
            "take_profit_2_pct": self.take_profit_2_pct,
            "tp1_size_pct": self.tp1_size_pct,
            "tp2_size_pct": self.tp2_size_pct,
            "breakeven_trigger_pct": self.breakeven_trigger_pct,
            "regime": self.regime,
            "signals": self.signals_active,
            "cascade_confidence": self.conviction,
            "weight_preset": self.weight_preset,
            "mtf_aligned": self.mtf_aligned,
            "sweep_confirmed": self.sweep_confirmed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sizing": getattr(self, 'sizing', {}),  # Ganzes Dict für ExecutionAgent
            "mr_mode": self.mr_mode,  # PROMPT 02: Mean-Reversion-Modus für ExecutionAgent
        }
    
    def to_decision_feed_entry(self) -> dict:
        """Entry für bruno:decisions:feed (Dashboard-Kompatibilität)."""
        # === PROMPT 1 FIX: OFI Hard Filter ===
        # ofi_met ist NUR true, WENN:
        # - Für Longs: ofi_buy_pressure >= 0.60
        # - Für Shorts: ofi_buy_pressure <= 0.40
        # Werte dazwischen → ofi_met = false
        ofi_raw = self.diagnostics.get("ofi_buy_pressure", 0.5)
        ofi_available = self.diagnostics.get("ofi_available", True)
        
        if not ofi_available or ofi_raw is None:
            ofi_met = False
            ofi_status = "no_data"
        elif self.direction == "long":
            ofi_met = ofi_raw >= 0.60  # Hard threshold für Longs
            ofi_status = f"long_threshold_{'pass' if ofi_met else 'fail'}"
        elif self.direction == "short":
            ofi_met = ofi_raw <= 0.40  # Hard threshold für Shorts  
            ofi_status = f"short_threshold_{'pass' if ofi_met else 'fail'}"
        else:
            ofi_met = False  # Neutral direction
            ofi_status = "neutral_direction"
        
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ofi": ofi_raw,
            "ofi_met": ofi_met,
            "ofi_status": ofi_status,  # PROMPT 1: Extra logging für OFI Status
            "grss": self.macro_score,
            "outcome": f"SIGNAL_{self.direction.upper()}" if self.should_trade else "COMPOSITE_HOLD",
            "reason": "; ".join(self.signals_active[:3]) if self.signals_active else "Score below threshold",
            "regime": self.regime,
            "layer1_confidence": self.conviction,
            "layer2_decision": self.direction.upper() if self.should_trade else "HOLD",
            "layer3_blocked": None,
            "price": self.price,
            "composite_score": self.composite_score,
            "ta_score": self.ta_score,
            "liq_score": self.liq_score,
            "flow_score": self.flow_score,
            "macro_score": self.macro_score,
            "mean_reversion_score": self.mean_reversion_score,
            "weight_preset": self.weight_preset,
            "take_profit_1_pct": self.take_profit_1_pct,
            "take_profit_2_pct": self.take_profit_2_pct,
            "tp1_size_pct": self.tp1_size_pct,
            "tp2_size_pct": self.tp2_size_pct,
            "breakeven_trigger_pct": self.breakeven_trigger_pct,
            "diagnostics": self.diagnostics
        }


class CompositeScorer:
    """
    Deterministische Trade-Entscheidungslogik mit regime-adaptiver Gewichtung.
    Ersetzt die 3-Layer LLM-Cascade.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger("composite_scorer")
        
        # Initialize ConfigCache
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        ConfigCache.init(config_path)

    async def score(self) -> CompositeSignal:
        """Haupteinstieg - berechnet Composite Score mit dynamischer Gewichtung."""
        result = CompositeSignal()
        
        # 1. Daten laden
        ta_data = await self.redis.get_cache("bruno:ta:snapshot") or {}
        liq_data = await self.redis.get_cache("bruno:liq:intelligence") or {}
        flow_data = await self.redis.get_cache("bruno:quant:micro") or {}
        macro_data = await self.redis.get_cache("bruno:context:grss") or {}
        
        result.price = ta_data.get("price", flow_data.get("price", 0.0))
        if result.price <= 0:
            return result
        
        # Extract macro trend from TA data
        macro_trend = ta_data.get("macro_trend", {})
        macro_trend_direction = macro_trend.get("macro_trend", "unknown")
        
        # 2. Regime bestimmen → Gewichte wählen (NEU: dynamisch)
        regime = self._determine_regime(ta_data, macro_data)
        result.regime = regime
        
        # 3. Einzelscores
        ta_score = self._score_ta(ta_data)
        liq_score = self._score_liq(liq_data)
        analytics_data = await self.redis.get_cache("bruno:binance:analytics") or {}
        flow_score = await self._score_flow(flow_data, macro_data, analytics_data)
        macro_score = self._score_macro(macro_data)
        
        # === PROMPT 1 FIX: Macro Score Hard Block ===
        # Richtung wird später aus composite Score bestimmt, aber wir können den Macro-Score
        # vorab auf 0 setzen wenn klar ist, dass der Macro-Trend entgegensteht
        # Dies wird nach der Richtungsbestimmung (Schritt 5) strenger geprüft
        
        mean_reversion_score = self._score_mean_reversion(ta_data, regime)
        
        # PROMPT 05: Funding Rate Score berechnen
        funding_score = await self._score_funding(direction_hint="long" if preliminary_composite_check > 0 else "short")
        
        result.ta_score = ta_score
        result.liq_score = liq_score
        result.flow_score = flow_score
        result.macro_score = macro_score
        result.mean_reversion_score = mean_reversion_score
        result.funding_score = funding_score  # PROMPT 05

        trend_strength = float(ta_data.get("trend", {}).get("strength", 0.0))
        
        # PROMPT 03: Preliminary MR-Modus Erkennung für Gewichtung
        # (wird später in der Conflict Resolution verfeinert)
        preliminary_mr_mode = False
        preliminary_composite_check = ta_score + liq_score + flow_score
        preliminary_dir_check = "long" if preliminary_composite_check > 0 else "short" if preliminary_composite_check < 0 else "neutral"
        if macro_trend_direction in ["macro_bull", "macro_bear"]:
            macro_dir_check = "long" if macro_trend_direction == "macro_bull" else "short"
            if preliminary_dir_check != "neutral" and preliminary_dir_check != macro_dir_check:
                preliminary_mr_mode = True
        
        weights = self._get_weights(regime, trend_strength, mr_mode=preliminary_mr_mode)
        result.weight_preset = self._blend_label(self._regime_blend(regime, trend_strength), regime)

        # MTF + Sweep Status (VOR Confluence-Bonus setzen!)
        result.mtf_aligned = ta_data.get("ta_score", {}).get("mtf_aligned", False)
        sweep = liq_data.get("sweep", {})
        result.sweep_confirmed = sweep.get("all_confirmed", False)
        
        # 4. Strategy Blending (A/B)
        # Strategy A (Trend Following): TA + Liq + Flow + Macro
        # Strategy B (Mean Reversion): Mean Reversion Score
        # Blend ratio based on regime: Ranging = more B, Trending = more A
        
        # PROMPT 03: Dominant Signal Wins - Konflikt-Penalty entfernt
        # Stärkstes Signal gewinnt, schwächere werden auf 50% reduziert (nicht negiert)
        raw_scores = {"ta": ta_score, "liq": liq_score, "flow": flow_score}
        dominant_signal = max(raw_scores.items(), key=lambda x: abs(x[1]))
        dominant_name = dominant_signal[0]
        dominant_value = dominant_signal[1]
        dominant_sign = 1 if dominant_value > 0 else -1 if dominant_value < 0 else 0
        
        # Anwenden der Konflikt-Resolution: Signale in gleiche Richtung = 100%,
        # Signale in Gegenrichtung = 50% (nicht negiert)
        adjusted_scores = {}
        for name, value in raw_scores.items():
            if dominant_sign == 0:
                adjusted_scores[name] = value
            else:
                value_sign = 1 if value > 0 else -1 if value < 0 else 0
                if value_sign == dominant_sign or value_sign == 0:
                    adjusted_scores[name] = value  # Gleiche Richtung = 100%
                else:
                    adjusted_scores[name] = value * 0.5  # Gegenrichtung = 50% (nicht negiert)
        
        # Log wenn Konflikt auftrat
        if any(s != 0 for s in [1 if raw_scores[k]*dominant_sign < 0 else 0 for k in raw_scores]):
            result.signals_active.append(
                f"Conflict resolved: {dominant_name} dominates ({dominant_value:+.1f}), "
                f"opposing reduced to 50%"
            )
        
        # PROMPT 05: Funding Score mit 5% Gewichtung
        funding_weight = float(ConfigCache.get("FUNDING_SUBSCORE_WEIGHT", 0.05))
        
        strategy_a_score = (
            adjusted_scores["ta"] * weights["ta"] +
            (adjusted_scores["liq"] * 2) * weights["liq"] +
            (adjusted_scores["flow"] * 2) * weights["flow"] +
            (macro_score * 2) * weights["macro"] +
            (funding_score * 2) * funding_weight  # PROMPT 05: Funding Score
        )
        
        # BRUNO-FIX-03: Reduzierte Blend-Ratios + MR als reiner Verstärker
        # MR darf Strategy A nur verstärken, nie auslöschen
        if regime == "ranging":
            blend_ratio = 0.15  # war 0.40 — Trend bleibt dominant
        elif regime == "high_vola":
            blend_ratio = 0.20  # war 0.30
        elif regime in ("trending_bull", "bear"):
            blend_ratio = 0.05  # war 0.10 — fast reiner Trend
        else:
            blend_ratio = 0.10  # Default

        # Normalize mean_reversion_score from -50..+50 to -100..+100 for blending
        mr_normalized = mean_reversion_score * 2

        # BRUNO-FIX-03: MR Contribution nur bei Vorzeichen-Übereinstimmung mit Strategy A
        # MR verstärkt Trend, löscht ihn nicht aus
        abs_ta_score = abs(ta_score)
        mr_contribution = mr_normalized

        # Regel 1: Gegensätzliche Vorzeichen → MR-Beitrag = 0
        strategy_a_sign = 1 if strategy_a_score > 0 else -1 if strategy_a_score < 0 else 0
        mr_sign = 1 if mr_normalized > 0 else -1 if mr_normalized < 0 else 0

        if strategy_a_sign != 0 and mr_sign != 0 and strategy_a_sign != mr_sign:
            mr_contribution = 0.0
            result.signals_active.append(
                f"MR neutralized: sign conflict (A={strategy_a_score:+.1f}, MR={mr_normalized:+.1f})"
            )
            self.logger.debug(
                f"MR sign conflict: strategy_a={strategy_a_score:+.1f}, "
                f"mr_normalized={mr_normalized:+.1f} → 0"
            )

        # Regel 2: Bei starkem Trend (abs_ta > 80) — BRUNO-FIX-01
        if abs_ta_score > 80:
            if ta_score > 0 and mr_normalized < 0:
                mr_contribution = 0.0
                result.signals_active.append(
                    f"MR capped: Strong bull trend (TA={ta_score:.0f}), ignoring overbought"
                )
            elif ta_score < 0 and mr_normalized > 0:
                mr_contribution = 0.0
                result.signals_active.append(
                    f"MR capped: Strong bear trend (TA={ta_score:.0f}), ignoring oversold"
                )

        # Blend Strategy A and B
        composite = (strategy_a_score * (1 - blend_ratio)) + (mr_contribution * blend_ratio)
        result.composite_score = round(max(-100, min(100, composite)), 1)

        if blend_ratio >= 0.15:
            result.signals_active.append(
                f"Strategy Blend: {int(blend_ratio*100)}% MR ({regime} regime)"
            )

        # 4b. Signal-Confluence-Bonus (NEU) - PROMPT 1 FIX: Härtere Bedingungen
        # Der Bonus darf NUR addiert werden, WENN:
        # a) mtf_aligned == true (Higher Timeframes stimmen überein)
        # b) liq_score > 0 ODER flow_score > 20 (echte Liquiditäts-/Flow-Backing)
        confluence_signals = []

        # TA Richtung
        if ta_score > 10:
            confluence_signals.append("ta_bull")
        elif ta_score < -10:
            confluence_signals.append("ta_bear")

        # Liq Richtung
        if liq_score > 5:
            confluence_signals.append("liq_bull")
        elif liq_score < -5:
            confluence_signals.append("liq_bear")

        # Flow Richtung
        if flow_score > 10:
            confluence_signals.append("flow_bull")
        elif flow_score < -10:
            confluence_signals.append("flow_bear")

        # Macro Richtung
        if macro_score > 5:
            confluence_signals.append("macro_bull")
        elif macro_score < -5:
            confluence_signals.append("macro_bear")

        # Zähle Bull vs Bear Signale (nur 4 unabhängige Signalquellen: ta, liq, flow, macro)
        bull_count = sum(1 for s in confluence_signals if s.endswith("_bull"))
        bear_count = sum(1 for s in confluence_signals if s.endswith("_bear"))

        dominant_count = max(bull_count, bear_count)

        # BRUNO-FIX-03: Confluence Gate gelockert (ODER statt UND)
        # Bonus ist erreichbar, wenn ENTWEDER MTF aligned ODER Liq/Flow stark sind
        # Zusätzlich: höhere Boni pro aligned signal
        confluence_bonus_eligible = (
            result.mtf_aligned  # MTF alleine reicht
            or (liq_score > 5 and abs(flow_score) > 10)  # ODER starke Liq+Flow Confluence
            or abs(flow_score) > 20  # ODER sehr starker Flow alleine
        )

        if dominant_count >= 3 and confluence_bonus_eligible:
            # BRUNO-FIX-03: Höhere Boni — der Bonus ist kritisch für Learning-Threshold
            # 3/4 aligned → +15 (war 10)
            # 4/4 aligned → +25 (war 20)
            bonus = 15 if dominant_count == 3 else 25
            if bull_count > bear_count:
                composite += bonus
                result.signals_active.append(
                    f"Confluence Bonus +{bonus} ({bull_count}/4 aligned)"
                )
            else:
                composite -= bonus
                result.signals_active.append(
                    f"Confluence Bonus -{bonus} ({bear_count}/4 aligned)"
                )
        elif dominant_count >= 3 and not confluence_bonus_eligible:
            result.signals_active.append(
                f"Confluence Bonus pending: {dominant_count}/4 signals aligned but no gate"
            )

        result.composite_score = round(max(-100, min(100, composite)), 1)

        # 4c. Regime-Kompensation (NEU)
        # Ranging-Märkte produzieren strukturell niedrigere TA-Scores weil
        # der Trend-Block (25 Punkte) bei "mixed" EMA-Stack ~0 ist.
        # Kompensiere durch Score-Scaling damit Ranging-Setups nicht
        # systematisch benachteiligt werden.
        if regime in ("ranging", "high_vola"):
            # In Ranging: Der relevante Signal ist nicht Trend, sondern
            # Confluence + Flow + Liq. Wenn diese positiv sind, scale up.
            if abs(composite) > 10:  # Minimum-Signal vorhanden
                ranging_boost = abs(composite) * 0.15  # +15% Score Boost
                if composite > 0:
                    composite += ranging_boost
                else:
                    composite -= ranging_boost
                result.signals_active.append(f"Ranging regime boost: +{ranging_boost:.1f}")

        result.composite_score = round(max(-100, min(100, composite)), 1)

        # === PROMPT 02: Macro Conflict Resolution VOR Direction-Bestimmung ===
        # Schritt 1: Preliminary Direction aus TA + Liq + Flow (ohne Macro)
        preliminary_composite = ta_score + liq_score + flow_score
        preliminary_dir = "long" if preliminary_composite > 0 else "short" if preliminary_composite < 0 else "neutral"
        
        # Schritt 2: Macro Direction bestimmen
        macro_dir = "neutral"
        if macro_trend_direction == "macro_bull":
            macro_dir = "long"
        elif macro_trend_direction == "macro_bear":
            macro_dir = "short"
        
        # Schritt 3: Konflikt-Erkennung
        conflict = (macro_dir != "neutral" and macro_dir != preliminary_dir and preliminary_dir != "neutral")
        
        if conflict:
            # Mean-Reversion-Modus: Trade gegen Macro erlaubt, aber mit reduziertem Risiko
            result.mr_mode = True
            macro_score = 0  # Kein Macro-Bonus im MR-Modus
            result.macro_score = 0
            result.signals_active.append(
                f"MR MODE: {preliminary_dir.upper()} vs Macro {macro_dir.upper()} "
                f"(TA+Liq+Flow={preliminary_composite:+.1f}, Macro={macro_trend_direction})"
            )
            self.logger.warning(
                f"PROMPT 02: Mean-Reversion Modus aktiviert - {preliminary_dir} vs {macro_dir} "
                f"| Sizing: 50%, SL: 0.8x, TP1: 1.0x"
            )
        else:
            # Trend-Aligned: Voller Macro-Bonus, normales Sizing
            result.mr_mode = False
            if preliminary_dir != "neutral":
                result.signals_active.append(
                    f"TREND ALIGNED: {preliminary_dir.upper()} with Macro {macro_dir.upper()}"
                )
        
        # 5. Richtung (jetzt mit berücksichtigtem Macro-Score)
        result.direction = "long" if composite > 0 else "short" if composite < 0 else "neutral"

        # 5b. RegimeConfig Integration (NEU)
        regime_cfg = REGIME_CONFIGS.get(regime, REGIME_CONFIGS["unknown"])
        
        # 7. Threshold + Bonus-Logic
        atr = float(ta_data.get("atr_14", 0.0) or 0.0)
        
        # PROMPT 03: Confluence zählen für Threshold-Bonus
        confluence_aligned = 0
        if adjusted_scores["ta"] != 0 and ((adjusted_scores["ta"] > 0) == (composite > 0)):
            confluence_aligned += 1
        if adjusted_scores["liq"] != 0 and ((adjusted_scores["liq"] > 0) == (composite > 0)):
            confluence_aligned += 1
        if adjusted_scores["flow"] != 0 and ((adjusted_scores["flow"] > 0) == (composite > 0)):
            confluence_aligned += 1
        
        threshold = self._get_threshold(
            atr, result.price, macro_data,
            confluence_aligned=confluence_aligned,
            mtf_aligned=result.mtf_aligned
        )
        abs_score = abs(composite)
        
        # PROMPT 05: Funding-Daten für Soft-Veto und Diagnostics
        funding_data = await self.redis.get_cache("market:funding:current") or {}
        
        # Sweep-Bonus: Ein bestätigter 3×-Sweep senkt den Threshold um 15
        # Begründung: Sweeps sind die höchstwahrscheinlichen Setups
        effective_threshold = threshold
        if result.sweep_confirmed:
            effective_threshold = max(30, threshold - 15)
            result.signals_active.append("Sweep-Bonus: Threshold -15")
        
        # BRUNO-FIX-05: OFI Penalty nur in Prod-Mode
        learning_mode = bool(ConfigCache.get("LEARNING_MODE_ENABLED", False))
        disable_ofi_penalty = bool(ConfigCache.get("DISABLE_OFI_GAP_PENALTY_IN_LEARNING", True))
        if flow_data.get("OFI_Buy_Pressure") is None:
            if learning_mode and disable_ofi_penalty:
                result.signals_active.append("OFI Data Gap: noted (learning mode, no penalty)")
            else:
                effective_threshold += 8
                result.signals_active.append("OFI Data Gap: Threshold +8")
        
        # PROMPT 05: Soft-Veto für hohe Funding Rates
        # Wenn |funding| > 0.05% UND Richtung gegen Funding → Threshold +3
        funding_veto_threshold_bps = float(ConfigCache.get("FUNDING_VETO_THRESHOLD_BPS", 5))
        funding_hold_min = float(ConfigCache.get("FUNDING_PREDICTED_HOLD_MIN", 240))
        
        # funding_data wurde bereits oben geholt
        funding_rate = funding_data.get("funding_rate", 0)
        funding_bps = funding_data.get("funding_bps", abs(funding_rate * 10000))
        
        if funding_bps > funding_veto_threshold_bps:
            # Prüfe ob Trade-Richtung gegen Funding läuft
            # Long-Trade bei positivem Funding = teuer
            # Short-Trade bei negativem Funding = teuer
            direction_against_funding = (
                (result.direction == "long" and funding_rate > 0) or
                (result.direction == "short" and funding_rate < 0)
            )
            
            if direction_against_funding:
                # Lange Hold-Zeit würde Funding-Kosten signifikant machen
                # Für Scalping (< 4h) ist Funding oft vernachlässigbar
                # Für Swings (> 4h) ist Funding ein Faktor
                # Wir gehen konservativ davon aus, dass durchschnittliche Hold-Zeit
                # bei 4h+ liegt → Soft-Veto
                effective_threshold += 3
                result.signals_active.append(
                    f"FUNDING_HEADWIND_WARNING: {funding_rate:.4%} against {result.direction}, "
                    f"Threshold +3"
                )
                self.logger.warning(
                    f"PROMPT 05: Funding Headwind detected | {funding_rate:.4%} vs {result.direction} | "
                    f"Consider shorter hold or skip trade"
                )
        
        # BRUNO-FIX-06: critical_data_gap ist jetzt eine ECHTE Blackout-Bedingung
        data_status = macro_data.get("Data_Status", {})
        components_ok = data_status.get("components_ok", 0)
        components_total = data_status.get("components_total", 6)

        # Echter Daten-Blackout: <33% der GRSS-Komponenten verfügbar
        grss_blackout = data_status.get("grss_blackout", False)

        # OFI-Verfügbarkeit bleibt als separater Gate
        ofi_available = flow_data.get("OFI_Available", True)

        # critical_data_gap = nur wenn sowohl GRSS als auch OFI fehlen
        critical_data_gap = grss_blackout and not ofi_available

        disable_halving = bool(ConfigCache.get("DISABLE_CONVICTION_HALVING_IN_LEARNING", True))

        base_conviction = min(1.0, abs_score / 100.0)

        if critical_data_gap and not (learning_mode and disable_halving):
            # Prod: Conviction halbieren
            result.conviction = round(base_conviction * 0.5, 3)
        else:
            result.conviction = round(base_conviction, 3)

        if critical_data_gap:
            missing = []
            if not ofi_available:
                missing.append("OFI")
            if macro_data.get("DVOL") is None:
                missing.append("DVOL")
            if macro_data.get("Long_Short_Ratio") is None:
                missing.append("L/S Ratio")

            if learning_mode and disable_halving:
                result.signals_active.append(
                    f"Data Gap ({', '.join(missing)}): noted (learning mode, no halving)"
                )
            else:
                result.signals_active.append(
                    f"Data Gap ({', '.join(missing)}): Conviction halved"
                )
        
        # Macro Trend Hard Block Daten
        mt_allow_longs = macro_trend.get("allow_longs", True)
        mt_allow_shorts = macro_trend.get("allow_shorts", True)
        
        # 8. Position Sizing (NEU: mit Capital)
        portfolio = await self.redis.get_cache("bruno:portfolio:state") or {}
        capital_eur = float(portfolio.get("capital_eur", 1000.0))
        
        session = ta_data.get("session", {})
        sizing = self._calc_position_size(abs_score, atr, result.price, session, capital_eur)
        
        # === SEQUENTIELLE SHOULD_TRADE LOGIK (BUG 8 FIX) ===
        
        # SCHRITT 1: Threshold Check (setzt should_trade initial)
        result.should_trade = abs_score >= effective_threshold
        
        # SCHRITT 2: Conviction Check (nur für Diagnostik, kein Blocker!)
        # Conviction wird berechnet aber darf nicht als separater Gate fungieren
        # Der CompositeScore + Threshold ist der einzige Gate
        
        # SCHRITT 3: Regime Direction Filter (DEACTIVATED - Macro risk already priced in)
        # Regime direction restrictions are redundant since macro risk is already reflected in macro_score
        # The composite_score + threshold should be the only gate
        # if result.should_trade and result.direction == "long" and not regime_cfg.allow_longs:
        #     result.should_trade = False
        #     result.signals_active.append(f"BLOCKED: {regime} regime disallows longs")
        # elif result.should_trade and result.direction == "short" and not regime_cfg.allow_shorts:
        #     result.should_trade = False
        #     result.signals_active.append(f"BLOCKED: {regime} regime disallows shorts")
        
        # SCHRITT 4: Macro Trend Diagnostics (pure diagnostic, NO GATE)
        # Macro risk is ONLY priced into the score via TA-Score penalty (50% reduction for macro_bear + long)
        # No additional signal reasons needed - the score already reflects macro conditions
        
        # BRUNO-FIX-04: Sizing Check mit Phantom-Fallback
        if result.should_trade and not sizing.get("sizing_valid", False):
            if sizing.get("phantom_eligible", False):
                # Learning-Mode: Position zu klein für echten Trade, aber als Phantom aufzeichnen
                # should_trade bleibt False für Execution, aber signals_active markiert Phantom
                result.should_trade = False
                result.signals_active.append(
                    f"PHANTOM ELIGIBLE: {sizing.get('reject_reason', 'below_notional')}"
                )
            else:
                result.should_trade = False
                result.signals_active.append(
                    f"SIZING REJECT: {sizing.get('reject_reason', 'unknown')}"
                )
        
        result.position_size_pct = sizing.get("position_size_btc", 0.0)
        # Speichere sizing für ExecutionAgent
        result.sizing = sizing
        (
            result.stop_loss_pct,
            result.take_profit_1_pct,
            result.take_profit_2_pct,
            result.tp1_size_pct,
            result.tp2_size_pct,
            result.breakeven_trigger_pct,
        ) = self._calc_sl_tp(atr, result.price, abs_score, regime)
        result.take_profit_pct = result.take_profit_2_pct
        
        # 9. Signale sammeln
        result.signals_active += self._collect_signals(ta_data, liq_data, flow_data, macro_data)
        
        # 10. Diagnostik-Block (immer loggen, nicht nur bei should_trade)
        result.diagnostics = {
            "grss_raw": float(macro_data.get("GRSS_Score_Raw", 0)),
            "grss_ema": float(macro_data.get("GRSS_Score", 0)),
            "veto_active": bool(macro_data.get("Veto_Active", True)),
            "ta_score_pre_mtf": float(ta_data.get("ta_score", {}).get("score", 0)) if ta_data.get("ta_score") else 0,
            "ta_score_post_mtf": result.ta_score,
            "mtf_aligned": result.mtf_aligned,
            "mtf_alignment_score": float(ta_data.get("mtf", {}).get("alignment_score", 0)),
            "effective_threshold": effective_threshold,
            "threshold_base": threshold,
            "threshold_multiplier": round(threshold / max(1.0, float(ConfigCache.get("COMPOSITE_THRESHOLD_LEARNING", 35) if ConfigCache.get("LEARNING_MODE_ENABLED", False) else ConfigCache.get("COMPOSITE_THRESHOLD_PROD", 55))), 3),
            "atr_14": atr,
            "price": result.price,
            "abs_score": abs_score,
            "gap_to_threshold": round(effective_threshold - abs_score, 1),
            "regime": regime,
            "weights_used": weights,
            "critical_data_gap": critical_data_gap,
            "ofi_available": flow_data.get("OFI_Available", True),
            "ofi_buy_pressure": flow_data.get("OFI_Buy_Pressure", 0.0),
            "macro_trend": macro_trend.get("macro_trend", "unknown"),
            "macro_data_sufficient": not macro_trend.get("insufficient_data", False),
            "daily_ema_200": macro_trend.get("daily_ema_200", 0),
            "price_vs_daily_ema200": macro_trend.get("price_vs_ema200", "unknown"),
            "block_reason": self._get_block_reason(result, effective_threshold, macro_data),
            # PROMPT 05: Funding Rate Diagnostics
            "funding_score": result.funding_score,
            "funding_rate": funding_data.get("funding_rate", 0) if funding_data else 0,
            "funding_bps": funding_data.get("funding_bps", 0) if funding_data else 0,
        }

        # SYNCHRONES LOGGING: Reason und Scores zusammen mit composite_score
        reason_str = "; ".join(result.signals_active[:3]) if result.signals_active else "Score below threshold"
        self.logger.info(
            f"Composite Score: {result.composite_score:+.1f} | "
            f"TA: {result.ta_score:+.1f} | Liq: {result.liq_score:+.1f} | Flow: {result.flow_score:+.1f} | "
            f"Macro: {result.macro_score:+.1f} | Funding: {result.funding_score:+.1f} | "  # PROMPT 05
            f"Reason: {reason_str} | Trade: {result.should_trade}"
        )
        
        return result

    def _get_weights(self, regime: str, trend_strength: float = 0.0, mr_mode: bool = False) -> dict:
        """
        Wählt Gewichtungs-Preset basierend auf Regime.
        Trending = TA dominiert, Ranging = Liq dominiert.
        
        PROMPT 03: MR-Modus hat asymmetrische Gewichtung:
        - Liq: 30%, Flow: 30%, TA: 25%, Macro: 15%
        
        Kann via config.json überschrieben werden (mit OVERRIDE prefix).
        """
        # PROMPT 03: MR-Modus asymmetrische Gewichtung
        if mr_mode:
            return {
                "ta": 0.25,
                "liq": 0.30,
                "flow": 0.30,
                "macro": 0.15,
            }
        
        # Config-Überschreibung prüfen (nur wenn explizit OVERRIDE_ Keys vorhanden)
        if all(ConfigCache.get(k) is not None for k in ["COMPOSITE_W_OVERRIDE_TA", "COMPOSITE_W_OVERRIDE_LIQ", 
                                                        "COMPOSITE_W_OVERRIDE_FLOW", "COMPOSITE_W_OVERRIDE_MACRO"]):
            # Wenn ALLE 4 OVERRIDE Keys in config → nutze config (manuelles Override)
            return {
                "ta": float(ConfigCache.get("COMPOSITE_W_OVERRIDE_TA", 0.4)),
                "liq": float(ConfigCache.get("COMPOSITE_W_OVERRIDE_LIQ", 0.25)),
                "flow": float(ConfigCache.get("COMPOSITE_W_OVERRIDE_FLOW", 0.2)),
                "macro": float(ConfigCache.get("COMPOSITE_W_OVERRIDE_MACRO", 0.15)),
            }

        # Default: weiche Interpolation zwischen Trending und Ranging
        blend = self._regime_blend(regime, trend_strength)
        return self._blend_weights(WEIGHT_PRESETS["ranging"], WEIGHT_PRESETS["trending"], blend)

    def _regime_blend(self, regime: str, trend_strength: float) -> float:
        """0.0 = ranging, 1.0 = trending; harte Regime werden weich überblendet."""
        if regime in ("trending_bull", "bear"):
            return 1.0
        if regime == "high_vola":
            return 0.25
        return max(0.0, min(1.0, float(trend_strength)))

    def _blend_label(self, blend: float, regime: str) -> str:
        if blend >= 0.75:
            return "trending"
        if blend <= 0.25:
            return "ranging"
        return f"blended_{regime}_{blend:.2f}"

    def _blend_weights(self, ranging: dict, trending: dict, blend: float) -> dict:
        """Lineare Interpolation zwischen zwei Gewichtungs-Sets."""
        blend = max(0.0, min(1.0, blend))
        return {
            "ta": round(ranging["ta"] + (trending["ta"] - ranging["ta"]) * blend, 4),
            "liq": round(ranging["liq"] + (trending["liq"] - ranging["liq"]) * blend, 4),
            "flow": round(ranging["flow"] + (trending["flow"] - ranging["flow"]) * blend, 4),
            "macro": round(ranging["macro"] + (trending["macro"] - ranging["macro"]) * blend, 4),
        }

    def _calc_position_size(self, abs_score: float, atr: float, price: float,
                            session: dict, capital_eur: float = 0.0) -> dict:
        """
        Kontinuierliches Kelly-inspiriertes Position Sizing (BRUNO-FIX-04).

        Prinzip:
        - Base risk = fixer Prozentsatz des Kapitals (z.B. 2.5%)
        - size_factor = tanh(abs_score / 40) → monoton, glatt, beschränkt
        - Effective risk = base_risk * size_factor
        - Position = effective_risk / SL-Distanz

        Learning-Mode-Relaxation:
        - MIN_NOTIONAL reduziert (50 vs 100 USDT)
        - MIN_RR_AFTER_FEES reduziert (1.1 vs 1.5)
        - Unter-Notional-Positionen werden als Phantom-Trades markiert, nicht gekillt

        Returns: dict mit Sizing-Infos inkl. 'sizing_valid' und 'phantom_eligible'
        """
        import math

        learning_mode = bool(ConfigCache.get("LEARNING_MODE_ENABLED", False))

        leverage = int(ConfigCache.get("LEVERAGE", 5))
        risk_pct = float(ConfigCache.get("RISK_PER_TRADE_PCT", 2.5)) / 100.0

        # Learning-Mode-Relaxation
        if learning_mode:
            min_notional = float(ConfigCache.get("MIN_NOTIONAL_USDT_LEARNING", 50))
            min_rr = float(ConfigCache.get("MIN_RR_AFTER_FEES_LEARNING", 1.1))
        else:
            min_notional = float(ConfigCache.get("MIN_NOTIONAL_USDT", 100))
            min_rr = float(ConfigCache.get("MIN_RR_AFTER_FEES", 1.5))

        fee_rate = float(ConfigCache.get("FEE_RATE_TAKER", 0.0004))

        if price <= 0 or capital_eur <= 0:
            return self._sizing_reject(
                "No price or capital", leverage, 0, 0, 0, 0
            )

        eur_to_usd = 1.08
        capital_usd = capital_eur * eur_to_usd

        # === KELLY-INSPIRIERTE SIZING FUNCTION ===
        # size_factor = tanh(abs_score / 40)
        # Monoton steigend, glatt, beschränkt auf (0, 1)
        size_factor = math.tanh(abs_score / 40.0) if abs_score > 0 else 0.0

        # Floor: Im Learning-Mode mindestens 30% des Base-Risk
        # (verhindert, dass niedrige Scores zu Quasi-Null-Positionen führen)
        if learning_mode:
            size_factor = max(0.30, size_factor)

        risk_amount_usd = capital_usd * risk_pct * size_factor

        # Session-Anpassung
        session_mult = session.get("volatility_bias", 1.0) if isinstance(session, dict) else 1.0
        session_mult = min(1.4, max(0.6, session_mult))
        risk_amount_usd *= session_mult

        # SL-Distanz aus ATR
        atr_pct = atr / price if atr > 0 else 0.01
        sl_pct = max(0.008, min(0.025, atr_pct * 1.5))

        # Positionsgröße
        position_size_usd = risk_amount_usd / sl_pct
        position_size_btc = position_size_usd / price

        # Margin-Check (Cap bei 80% des Kapitals als Margin)
        margin_required = position_size_usd / leverage
        max_margin = capital_usd * 0.80

        if margin_required > max_margin:
            position_size_usd = max_margin * leverage
            position_size_btc = position_size_usd / price
            margin_required = max_margin

        # Fee-bewusstes R:R
        tp1_pct = sl_pct * 1.8
        fees_round_trip = position_size_usd * fee_rate * 2
        profit_tp1 = position_size_usd * tp1_pct - fees_round_trip
        loss_sl = position_size_usd * sl_pct + fees_round_trip
        rr_after_fees = profit_tp1 / loss_sl if loss_sl > 0 else 0

        # === HARD CHECKS ===
        phantom_eligible = False
        sizing_valid = True
        reject_reason = None

        # Min-Notional-Check
        if position_size_usd < min_notional:
            if learning_mode:
                # Learning: Phantom statt Kill
                sizing_valid = False
                phantom_eligible = True
                reject_reason = f"below_min_notional_phantom (${position_size_usd:.0f} < ${min_notional:.0f})"
                self.logger.info(
                    f"SIZING → PHANTOM: Position ${position_size_usd:.0f} < ${min_notional:.0f} "
                    f"(Learning Mode → Trade als Phantom aufgezeichnet)"
                )
            else:
                sizing_valid = False
                reject_reason = f"Below min notional: ${position_size_usd:.0f} < ${min_notional:.0f}"

        # R:R-Check
        elif rr_after_fees < min_rr:
            if learning_mode:
                # Learning: Warning statt Hard-Reject, aber Trade geht trotzdem
                self.logger.warning(
                    f"SIZING WARN: R:R {rr_after_fees:.2f} < {min_rr} "
                    f"(Learning Mode → Trade trotzdem ausgeführt)"
                )
                # sizing_valid bleibt True!
            else:
                sizing_valid = False
                reject_reason = f"R:R after fees too low: {rr_after_fees:.2f} < {min_rr}"

        # Binance Minimum Precision
        position_size_btc = max(0.001, round(position_size_btc, 4))

        return {
            "position_size_btc": position_size_btc,
            "position_size_usdt": round(position_size_btc * price, 2),
            "margin_required_usdt": round(position_size_btc * price / leverage, 2),
            "risk_amount_eur": round(risk_amount_usd / eur_to_usd, 2),
            "risk_amount_usd": round(risk_amount_usd, 2),
            "leverage_used": leverage,
            "fee_estimate_usdt": round(fees_round_trip, 2),
            "rr_after_fees": round(rr_after_fees, 2),
            "sl_pct": round(sl_pct, 4),
            "tp1_pct_minimum": round(tp1_pct, 4),
            "size_factor": round(size_factor, 3),
            "session_mult": round(session_mult, 2),
            "sizing_valid": sizing_valid,
            "phantom_eligible": phantom_eligible,  # NEU: Phantom-Trade Kandidat
            "reject_reason": reject_reason,
        }

    def _sizing_reject(self, reason: str, leverage: int, position_usd: float,
                       margin: float, risk_usd: float, fees: float) -> dict:
        """Helper für klare Reject-Returns."""
        eur_to_usd = 1.08
        return {
            "position_size_btc": 0.0,
            "position_size_usdt": round(position_usd, 2),
            "margin_required_usdt": round(margin, 2),
            "risk_amount_eur": round(risk_usd / eur_to_usd, 2),
            "risk_amount_usd": round(risk_usd, 2),
            "leverage_used": leverage,
            "fee_estimate_usdt": round(fees, 2),
            "rr_after_fees": 0.0,
            "sl_pct": 0.0,
            "tp1_pct_minimum": 0.0,
            "size_factor": 0.0,
            "session_mult": 1.0,
            "sizing_valid": False,
            "phantom_eligible": False,
            "reject_reason": reason,
        }

    async def _score_flow(self, flow_data: dict, macro_data: dict, 
                        analytics_data: dict = None) -> float:
        """
        Orderflow-Score mit Funding-Rate Integration.
        Range: -50 bis +50
        """
        score = 0.0
        
        # OFI (±20)
        ofi_raw = flow_data.get("OFI_Buy_Pressure")
        if ofi_raw is not None:
            ofi = float(ofi_raw)
            if ofi > 0.65: score += 20 * min(1.0, (ofi - 0.5) * 4)
            elif ofi < 0.35: score -= 20 * min(1.0, (0.5 - ofi) * 4)
        
        # CVD Direction (±10)
        cvd_raw = flow_data.get("CVD")
        if cvd_raw is not None:
            cvd = float(cvd_raw)
            if cvd > 100: score += 10
            elif cvd < -100: score -= 10
        
        # Taker Buy/Sell Ratio (±10)
        analytics_data = analytics_data or {}
        taker_ratio_raw = analytics_data.get("taker_buy_sell_ratio")
        if taker_ratio_raw is not None:
            taker_ratio = float(taker_ratio_raw)
            if taker_ratio > 1.3:  # Starker Kaufdruck
                score += 10
            elif taker_ratio > 1.1:
                score += 5
            elif taker_ratio < 0.7:  # Starker Verkaufsdruck
                score -= 10
            elif taker_ratio < 0.9:
                score -= 5
        
        # Top Trader Contrarian Signal (±8)
        top_ls_raw = analytics_data.get("top_trader_ls_ratio")
        if top_ls_raw is not None:
            top_ls = float(top_ls_raw)
            if top_ls > 2.0:  # Top Trader extrem Long → contrarian bearish
                score -= 8
            elif top_ls < 0.5:  # Top Trader extrem Short → contrarian bullish
                score += 8
        
        # Funding Rate: nicht als harter Additiv-Block, sondern als Multiplikator
        funding = float(macro_data.get("Funding_Rate", 0.0))
        funding_bps = funding * 10000.0
        funding_multiplier = 1.0
        if funding_bps > 20:
            funding_multiplier -= min(0.30, (funding_bps - 20) / 200.0)
        elif funding_bps < -5:
            funding_multiplier += min(0.20, abs(funding_bps + 5) / 200.0)
        funding_multiplier = max(0.75, min(1.20, funding_multiplier))

        # OFI Imbalance (±5)
        imbalance_raw = flow_data.get("OFI_Mean_Imbalance")
        if imbalance_raw is not None:
            imbalance = float(imbalance_raw)
            if imbalance > 1.15: score += 5
            elif imbalance < 0.85: score -= 5

        score = score * funding_multiplier
        return round(max(-50, min(50, score)), 1)

    def _determine_regime(self, ta_data, macro_data) -> str:
        """
        Regime-Bestimmung mit BTC-realistisch kalibrierten ATR-Schwellen (BRUNO-FIX-02).

        Historischer Fix: Alte Schwellen (atr_ratio < 1.0 für trending) waren für BTC
        praktisch unerreichbar. BTC hat auf 1h typischerweise atr_ratio 1.2-2.8%.

        Neue Kalibrierung:
        - high_vola: atr_ratio > 3.5% ODER bb_width > 5.0%
        - trending_bull/bear: ema_stack klar + atr_ratio < 3.0%
        - ranging: Default bei gemischten Signalen (NICHT unknown!)
        """
        atr = float(ta_data.get("atr_14", 0.0))
        price = float(ta_data.get("price", 0.0))
        atr_ratio = (atr / price * 100) if price > 0 else 0.0

        bb_data = ta_data.get("bollinger_bands", {})
        bb_width = float(bb_data.get("width", 0.0))

        macro_trend = ta_data.get("macro_trend", {})
        mt = macro_trend.get("macro_trend", "unknown")

        trend = ta_data.get("trend", {})
        ema_stack = trend.get("ema_stack", "mixed")

        # 1. High Volatility (BTC-realistisch: >3.5% ATR-Ratio ist WIRKLICH hoch)
        if atr_ratio > 3.5 or bb_width > 5.0:
            self.logger.info(
                f"Regime: high_vola (atr_ratio={atr_ratio:.2f}%, bb_width={bb_width:.2f}%)"
            )
            return "high_vola"

        # 2. Trending Bull — gelockerte Schwellen
        if ema_stack in ("perfect_bull", "bull"):
            if atr_ratio > 3.0:
                return "ranging"
            # Macro-Override: Nur wenn Daily NICHT bear
            if mt == "macro_bear":
                return "ranging"  # Bear Market Rally
            return "trending_bull"

        # 3. Bear Trend — gelockerte Schwellen
        if ema_stack in ("perfect_bear", "bear"):
            if atr_ratio > 3.0:
                return "ranging"
            if mt == "macro_bull":
                return "ranging"  # Bull Market Correction
            return "bear"

        # 4. Mixed / unklar → ranging (NICHT unknown!)
        return "ranging"

    def _score_ta(self, ta_data: dict) -> float:
        """Technical Analysis Score -100 bis +100."""
        ta_score_data = ta_data.get("ta_score", {})
        return float(ta_score_data.get("score", 0.0))

    def _score_liq(self, liq_data: dict) -> float:
        """Liquidity Score -50 bis +50."""
        return float(liq_data.get("liq_score", 0.0))

    def _score_macro(self, macro_data: dict) -> float:
        """Macro Score -50 bis +50."""
        grss = float(macro_data.get("GRSS_Score", 50.0))
        # GRSS: 0-100, konvertiere zu -50 bis +50 (50 = neutral)
        return round(grss - 50, 1)

    def _score_mean_reversion(self, ta_data: dict, regime: str) -> float:
        """
        Mean Reversion Sub-Engine Score -50 bis +50.
        
        Signalisiert überkauft/überverkauft Zustände für Kontrarian-Trades.
        Höherer Score = bullish mean reversion (buy dip), negativer = bearish (sell rip).
        
        Komponenten:
        - RSI Extrem (oversold/overbought)
        - VWAP Distanz
        - Bollinger Band Position (wenn verfügbar)
        - Support/Resistance Nähe
        """
        score = 0.0
        
        # RSI aus TA-Daten
        rsi = float(ta_data.get("rsi", 50.0))
        vwap = float(ta_data.get("vwap", 0.0))
        price = float(ta_data.get("price", 0.0))
        
        if price <= 0 or vwap <= 0:
            return 0.0
        
        # 1. RSI Mean Reversion (±20 Punkte)
        # RSI < 25 = stark oversold (bullish MR), RSI > 75 = stark overbought (bearish MR)
        if rsi < 20:
            score += 20  # Stark oversold
        elif rsi < 30:
            score += 15  # Oversold
        elif rsi < 40:
            score += 8   # Leicht oversold
        elif rsi > 80:
            score -= 20  # Stark overbought
        elif rsi > 70:
            score -= 15  # Overbought
        elif rsi > 60:
            score -= 8   # Leicht overbought
        
        # 2. VWAP Distanz (±15 Punkte)
        # Preis weit unter VWAP = bullish MR, weit über = bearish MR
        vwap_distance_pct = ((price - vwap) / vwap) * 100
        
        if vwap_distance_pct < -1.5:  # Preis >1.5% unter VWAP
            score += 15
        elif vwap_distance_pct < -0.8:
            score += 8
        elif vwap_distance_pct > 1.5:  # Preis >1.5% über VWAP
            score -= 15
        elif vwap_distance_pct > 0.8:
            score -= 8
        
        # 3. Regime-Adjustment
        # In trending Märkten ist Mean Reversion riskanter → reduziere Score
        if regime in ("trending_bull", "bear"):
            score *= 0.5  # 50% Reduktion in starken Trends
        elif regime == "high_vola":
            score *= 0.7  # 30% Reduktion bei hoher Volatilität
        
        return round(max(-50, min(50, score)), 1)

    async def _score_funding(self, direction_hint: str = "neutral") -> float:
        """
        PROMPT 05: Funding Rate Score -10 bis +10.
        
        Best Practice für BTC Perpetual Trading:
        - Negativer Funding (Shorts bezahlen Longs) → Long-Favorit
        - Positiver Funding (Longs bezahlen Shorts) → Short-Favorit
        
        Score-Berechnung:
        - Long bei negativem Funding: +5 (Shorts bezahlen Longs)
        - Long bei Funding > 0.03%: -8 (Long zahlt teuer)
        - Symmetrisch für Short
        
        Args:
            direction_hint: "long" oder "short" für gerichtete Scoring
            
        Returns:
            float: Funding Score -10..+10
        """
        # Hole Funding-Daten aus Redis
        funding_data = await self.redis.get_cache("market:funding:current") or {}
        funding_rate = funding_data.get("funding_rate", 0)
        funding_bps = funding_data.get("funding_bps", 0)  # Basis-Punkten
        
        if funding_rate is None:
            return 0.0
        
        score = 0.0
        
        # Konvertiere Funding Rate zu Basis-Punkten (1% = 100 bps)
        bps = funding_bps if funding_bps else (funding_rate * 10000)
        
        # Richtungsabhängige Scoring
        if direction_hint == "long":
            # Für Long-Trades
            if bps < 0:
                # Negativer Funding = Shorts zahlen Longs → Gut für Long
                score = min(10, max(5, abs(bps) * 2))
            elif bps > 5:
                # Funding > 0.05% = teuer für Long
                score = -8
            elif bps > 3:
                # Funding > 0.03% = moderat teuer
                score = -5
            else:
                # Neutral
                score = 0
                
        elif direction_hint == "short":
            # Für Short-Trades (inverse Logik)
            if bps > 0:
                # Positiver Funding = Longs zahlen Shorts → Gut für Short
                score = min(10, max(5, bps * 2))
            elif bps < -5:
                # Negativer Funding < -0.05% = teuer für Short
                score = -8
            elif bps < -3:
                # Negativer Funding < -0.03% = moderat teuer
                score = -5
            else:
                score = 0
        else:
            # Neutral / keine klare Richtung
            score = 0
        
        self.logger.debug(
            f"PROMPT 05 Funding Score: {score:+.1f} | "
            f"Funding: {funding_rate:.4%} ({bps:.1f} bps) | Direction: {direction_hint}"
        )
        
        return round(max(-10, min(10, score)), 1)

    def _get_threshold(self, atr: float = 0.0, price: float = 0.0, macro_data: dict = None,
                       confluence_aligned: int = 0, mtf_aligned: bool = False) -> float:
        """
        PROMPT 03: Adaptiver Threshold mit Konfidenz-Bonuses.
        
        Basis × Volatilitäts-Multiplikator × Event-Multiplikator - Konfidenz-Bonuses
        
        Konfidenz-Bonuses (senken Threshold):
        - ≥2 Sub-Scores aligned: -3 Punkte
        - MTF aligned: -5 Punkte
        - Hard Floor in Learning: 8 (war 15)
        """
        learning_enabled = ConfigCache.get("LEARNING_MODE_ENABLED", False)
        if learning_enabled:
            base = float(ConfigCache.get("COMPOSITE_THRESHOLD_LEARNING", 8))  # PROMPT 03: 8 statt 16
            hard_floor = float(ConfigCache.get("COMPOSITE_FLOOR_LEARNING", 8))  # PROMPT 03: Hard floor
        else:
            base = float(ConfigCache.get("COMPOSITE_THRESHOLD_PROD", 25))  # PROMPT 03: 25 statt 40
            hard_floor = 25.0

        if atr <= 0 or price <= 0:
            threshold = base
        else:
            atr_pct = atr / price
            # Hohe Vola -> konservativer, niedrige Vola -> aggressiver
            vol_mult = 0.65 + min(0.6, (atr_pct / 0.02) * 0.6)
            
            # Event Guard Logic
            event_mult = 1.0
            if macro_data:
                active_event = macro_data.get("Active_Event")
                if active_event:
                    event_mult = float(active_event.get("threshold_mult", 1.0))
                    self.logger.info(f"Event Guard: {active_event.get('name')} — Threshold ×{event_mult}")
            
            threshold = base * vol_mult * event_mult
        
        # PROMPT 03: Konfidenz-basierte Threshold-Reduktion
        threshold_bonus = 0
        
        # ≥2 Sub-Scores in gleiche Richtung
        confluence_bonus = float(ConfigCache.get("CONFLUENCE_BONUS_2OF3", -3))
        if confluence_aligned >= 2:
            threshold_bonus += confluence_bonus
            self.logger.debug(f"Threshold bonus: {confluence_aligned} signals aligned = {confluence_bonus}")
        
        # MTF aligned
        mtf_bonus = float(ConfigCache.get("MTF_ALIGN_BONUS", -5))
        if mtf_aligned:
            threshold_bonus += mtf_bonus
            self.logger.debug(f"Threshold bonus: MTF aligned = {mtf_bonus}")
        
        threshold += threshold_bonus
        
        # HARD FLOOR: Nie unter hard_floor (8 in Learning, 25 in Prod)
        return round(max(hard_floor, threshold), 1)

    def _calc_sl_tp(self, atr: float, price: float, abs_score: float, regime="unknown") -> tuple:
        """
        PROMPT 4: Vola-Adjustiertes Trade Management.
        
        Strikte ATR-basierte SL/TP Berechnung:
        - SL: 1.2x ATR
        - TP1: 1.5x ATR (50% Position)
        - TP2: 3.0x ATR (50% Position)
        - Breakeven: 1.0x ATR (MUSS vor TP1 feuern!)
        """
        if atr <= 0 or price <= 0:
            return 0.012, 0.015, 0.030, 0.50, 0.50, 0.010  # Default: 1.2%/1.5%/3.0%, BE=1.0%
        
        atr_pct = atr / price
        
        # PROMPT 4: Strikte Multiplikatoren (unabhängig vom Score)
        sl_mult = 1.2
        tp1_mult = 1.5
        tp2_mult = 3.0
        be_mult = 1.0  # Breakeven MUSS vor TP1 feuern (1.0 < 1.5)
        
        # Berechnung mit harten Grenzen
        sl_pct = round(max(0.008, min(0.025, atr_pct * sl_mult)), 4)
        tp1_pct = round(max(0.012, min(0.040, atr_pct * tp1_mult)), 4)  # Min 1.2%
        tp2_pct = round(max(tp1_pct + 0.01, min(0.080, atr_pct * tp2_mult)), 4)
        
        # PROMPT 4: Breakeven bei 1.0x ATR (NICHT bei TP1!)
        breakeven_trigger_pct = round(max(0.005, min(0.020, atr_pct * be_mult)), 4)
        
        # Logging für Transparenz
        self.logger.info(
            f"ATR SL/TP: ATR={atr:.0f} ({atr_pct:.2%}) | "
            f"SL={sl_pct:.2%} (1.2x) | TP1={tp1_pct:.2%} (1.5x) | "
            f"TP2={tp2_pct:.2%} (3.0x) | BE={breakeven_trigger_pct:.2%} (1.0x)"
        )
        
        tp1_size_pct = 0.50
        tp2_size_pct = 0.50

        return sl_pct, tp1_pct, tp2_pct, tp1_size_pct, tp2_size_pct, breakeven_trigger_pct

    def _collect_signals(self, ta_data: dict, liq_data: dict, flow_data: dict, macro_data: dict) -> list:
        """Sammelt aktive Signale für Logging."""
        signals = []
        
        # TA Signale
        ta_score_data = ta_data.get("ta_score", {})
        ta_signals = ta_score_data.get("signals", [])
        signals.extend([f"TA: {s}" for s in ta_signals[:2]])
        
        # Liquidity Signale
        sweep = liq_data.get("sweep", {})
        if sweep.get("all_confirmed"):
            signals.append(f"3× Sweep: {sweep.get('post_sweep_entry')}")
        elif sweep.get("active"):
            signals.append("Sweep Active (not confirmed)")
        
        # Flow Signale
        ofi_raw = flow_data.get("OFI_Buy_Pressure")
        ofi = float(ofi_raw) if ofi_raw is not None else 0.5
        # FIX: Wenn OFI = 0, keine "Strong" Meldung
        if ofi > 0.65 and ofi != 0:
            signals.append("Strong OFI Buy Pressure")
        elif ofi < 0.35 and ofi != 0:
            signals.append("Strong OFI Sell Pressure")
        elif ofi == 0:
            signals.append("OFI Neutral (No Flow Data)")
        
        # Macro Signale
        grss_raw = macro_data.get("GRSS_Score")
        grss = float(grss_raw) if grss_raw is not None else 50.0
        if grss > 70:
            signals.append("High GRSS (Bullish)")
        elif grss < 30:
            signals.append("Low GRSS (Bearish)")
        
        return signals[:5]  # Max 5 Signale

    def _get_block_reason(self, result, threshold, macro_data) -> str:
        """Gibt den primären Grund zurück warum NICHT getradet wird."""
        if macro_data.get("Veto_Active"):
            return f"GRSS_VETO (GRSS={macro_data.get('GRSS_Score', 0):.1f} < threshold)"
        if abs(result.composite_score) < threshold:
            gap = threshold - abs(result.composite_score)
            biggest_drag = "ta" if abs(result.ta_score) < 20 else "liq" if abs(result.liq_score) < 5 else "flow"
            return f"SCORE_TOO_LOW (Score={result.composite_score:+.1f}, Gap={gap:.1f}, weakest={biggest_drag})"
        return "NONE"

    async def get_health_status(self) -> dict:
        """Health-Check für den Composite Scorer."""
        return {
            "status": "online",
            "weight_presets": list(WEIGHT_PRESETS.keys()),
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
