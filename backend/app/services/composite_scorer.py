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
    
    def to_signal_dict(self, symbol: str = "BTCUSDT") -> dict:
        """Signal-Dict kompatibel mit ExecutionAgentV3."""
        return {
            "symbol": symbol,
            "side": "buy" if self.direction == "long" else "sell",
            "amount": 0.0,  # ExecutionAgent berechnet die echte Positionsgröße
            "position_size_hint_pct": self.position_size_pct,  # Hint für Execution
            "price": self.price,
            "composite_score": self.composite_score,
            "ta_score": self.ta_score,
            "liq_score": self.liq_score,
            "flow_score": self.flow_score,
            "macro_score": self.macro_score,
            "mean_reversion_score": self.mean_reversion_score,
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
        
        result.ta_score = ta_score
        result.liq_score = liq_score
        result.flow_score = flow_score
        result.macro_score = macro_score
        result.mean_reversion_score = mean_reversion_score

        trend_strength = float(ta_data.get("trend", {}).get("strength", 0.0))
        weights = self._get_weights(regime, trend_strength)
        result.weight_preset = self._blend_label(self._regime_blend(regime, trend_strength), regime)

        # MTF + Sweep Status (VOR Confluence-Bonus setzen!)
        result.mtf_aligned = ta_data.get("ta_score", {}).get("mtf_aligned", False)
        sweep = liq_data.get("sweep", {})
        result.sweep_confirmed = sweep.get("all_confirmed", False)
        
        # 4. Strategy Blending (A/B)
        # Strategy A (Trend Following): TA + Liq + Flow + Macro
        # Strategy B (Mean Reversion): Mean Reversion Score
        # Blend ratio based on regime: Ranging = more B, Trending = more A
        
        strategy_a_score = (
            ta_score * weights["ta"] +
            (liq_score * 2) * weights["liq"] +
            (flow_score * 2) * weights["flow"] +
            (macro_score * 2) * weights["macro"]
        )
        
        # Blend ratio: 0.0 = pure A, 1.0 = pure B
        if regime == "ranging":
            blend_ratio = 0.4  # 40% Mean Reversion, 60% Trend Following
        elif regime == "high_vola":
            blend_ratio = 0.3  # 30% Mean Reversion, 70% Trend Following
        elif regime in ("trending_bull", "bear"):
            blend_ratio = 0.1  # 10% Mean Reversion, 90% Trend Following
        else:
            blend_ratio = 0.2  # Default: 20% Mean Reversion
        
        # Normalize mean_reversion_score from -50..+50 to -100..+100 for blending
        mr_normalized = mean_reversion_score * 2
        
        # PROMPT 7: Strategy Blending Fix (Der "Brei-Effekt")
        # WENN trend_score extrem hoch (> 80), DANN darf negativer mean_reversion_score
        # den Gesamt-Score NICHT mehr reduzieren.
        abs_ta_score = abs(ta_score)
        mr_contribution = mr_normalized
        
        if abs_ta_score > 80 and mr_normalized < 0:
            # Trend ist extrem stark - "Overbought" ist ein Zeichen von Stärke, kein Malus
            # Cap Mean Reversion auf 0, damit es den Trend-Score nicht blockiert
            mr_contribution = 0.0
            result.signals_active.append(
                f"MR capped: Trend score {abs_ta_score:.0f} > 80, ignoring overbought signal"
            )
            self.logger.info(
                f"PROMPT 7 BLENDING FIX: TA score {abs_ta_score:.0f} > 80, "
                f"MR normalized was {mr_normalized:.1f}, capped to 0.0"
            )
        
        # Blend Strategy A and B
        composite = (strategy_a_score * (1 - blend_ratio)) + (mr_contribution * blend_ratio)
        result.composite_score = round(max(-100, min(100, composite)), 1)
        
        if blend_ratio > 0.2:
            result.signals_active.append(f"Strategy Blend: {blend_ratio*100:.0f}% Mean Reversion ({regime} regime)")

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

        # === PROMPT 1 FIX: Confluence Bonus nur bei harten Fakten ===
        confluence_bonus_eligible = (
            result.mtf_aligned and  # a) MTF muss aligned sein
            (liq_score > 0 or abs(flow_score) > 20)  # b) Liq oder Flow muss stark sein
        )
        
        if dominant_count >= 3 and confluence_bonus_eligible:
            bonus = (dominant_count - 2) * 10  # +10 pro Signal ab dem 3.
            if bull_count > bear_count:
                composite += bonus
                result.signals_active.append(f"Confluence Bonus +{bonus} ({bull_count}/4 aligned, MTF✓)")
            else:
                composite -= bonus
                result.signals_active.append(f"Confluence Bonus -{bonus} ({bear_count}/4 aligned, MTF✓)")
        elif dominant_count >= 3 and not confluence_bonus_eligible:
            # PROMPT 1: Logge warum kein Bonus gegeben wurde
            if not result.mtf_aligned:
                result.signals_active.append(f"Confluence Bonus BLOCKED: MTF not aligned ({bull_count}/4 signals)")
            else:
                result.signals_active.append(f"Confluence Bonus BLOCKED: No liq/flow backing (liq={liq_score}, flow={flow_score})")

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

        # 5. Richtung
        result.direction = "long" if composite > 0 else "short" if composite < 0 else "neutral"
        
        # === PROMPT 1 FIX: Macro Score Hard Block ===
        # WENN macro_trend == 'macro_bear' UND direction == 'LONG' → macro_score MUSS 0 sein
        # WENN macro_trend == 'macro_bull' UND direction == 'SHORT' → macro_score MUSS 0 sein
        if macro_trend_direction == "macro_bear" and result.direction == "long":
            old_macro_score = macro_score
            macro_score = 0.0
            result.macro_score = 0.0
            result.signals_active.append(f"MACRO BLOCK: Long in bear market (macro_score {old_macro_score:+.1f} → 0)")
            self.logger.warning(f"Macro Score Fix: Long trade in bear market - macro_score forced to 0 (was {old_macro_score:+.1f})")
        elif macro_trend_direction == "macro_bull" and result.direction == "short":
            old_macro_score = macro_score
            macro_score = 0.0
            result.macro_score = 0.0
            result.signals_active.append(f"MACRO BLOCK: Short in bull market (macro_score {old_macro_score:+.1f} → 0)")
            self.logger.warning(f"Macro Score Fix: Short trade in bull market - macro_score forced to 0 (was {old_macro_score:+.1f})")

        # 5b. RegimeConfig Integration (NEU)
        regime_cfg = REGIME_CONFIGS.get(regime, REGIME_CONFIGS["unknown"])
        
        # 7. Threshold + Bonus-Logic
        atr = float(ta_data.get("atr_14", 0.0) or 0.0)
        threshold = self._get_threshold(atr, result.price, macro_data)
        abs_score = abs(composite)
        
        # Sweep-Bonus: Ein bestätigter 3×-Sweep senkt den Threshold um 15
        # Begründung: Sweeps sind die höchstwahrscheinlichen Setups
        effective_threshold = threshold
        if result.sweep_confirmed:
            effective_threshold = max(30, threshold - 15)
            result.signals_active.append("Sweep-Bonus: Threshold -15")
        
        # OFI Data Gap Penalty: Wenn OFI keine Daten hat, erhöhe Threshold um 8
        if flow_data.get("OFI_Buy_Pressure") is None:
            effective_threshold += 8
            result.signals_active.append("OFI Data Gap: Threshold +8")
        
        # Critical Data Gap Check (für Conviction)
        critical_data_gap = macro_data.get("DVOL") is None or macro_data.get("Long_Short_Ratio") is None
        ofi_available = flow_data.get("OFI_Available", True)
        if not ofi_available:
            critical_data_gap = True
            
        base_conviction = min(1.0, abs_score / 100.0)
        result.conviction = round(base_conviction * (0.5 if critical_data_gap else 1.0), 3)
        if critical_data_gap:
            # EINE Message, die beschreibt WAS fehlt
            missing = []
            if not ofi_available:
                missing.append("OFI")
            if macro_data.get("DVOL") is None:
                missing.append("DVOL")
            if macro_data.get("Long_Short_Ratio") is None:
                missing.append("L/S Ratio")
            result.signals_active.append(f"Data Gap ({', '.join(missing)}): Conviction halved")
        
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
        
        # SCHRITT 5: Sizing Check (kann nur blockieren, nie freigeben)
        if result.should_trade and not sizing.get("sizing_valid", False):
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
        }

        # SYNCHRONES LOGGING: Reason und Scores zusammen mit composite_score
        reason_str = "; ".join(result.signals_active[:3]) if result.signals_active else "Score below threshold"
        self.logger.info(
            f"Composite Score: {result.composite_score:+.1f} | "
            f"TA: {result.ta_score:+.1f} | Liq: {result.liq_score:+.1f} | Flow: {result.flow_score:+.1f} | Macro: {result.macro_score:+.1f} | "
            f"Reason: {reason_str} | Trade: {result.should_trade}"
        )
        
        return result

    def _get_weights(self, regime: str, trend_strength: float = 0.0) -> dict:
        """
        Wählt Gewichtungs-Preset basierend auf Regime.
        Trending = TA dominiert, Ranging = Liq dominiert.
        
        Kann via config.json überschrieben werden (mit OVERRIDE prefix).
        """
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
        Professionelles Risk-Based Position Sizing.
        
        Prinzip: Der RISIKOBETRAG ist fix (2% des Eigenkapitals).
        Die POSITIONSGRÖSSE ergibt sich aus Risikobetrag ÷ SL-Distanz.
        Leverage macht die Position kapitaleffizient, NICHT riskanter.
        
        Returns: dict mit allen Sizing-Informationen
        """
        leverage = int(ConfigCache.get("LEVERAGE", 3))
        risk_pct = float(ConfigCache.get("RISK_PER_TRADE_PCT", 2.0)) / 100.0
        min_notional = float(ConfigCache.get("MIN_NOTIONAL_USDT", 300))
        fee_rate = float(ConfigCache.get("FEE_RATE_TAKER", 0.0004))
        min_rr = float(ConfigCache.get("MIN_RR_AFTER_FEES", 1.5))
        
        if price <= 0 or capital_eur <= 0:
            return {
                "position_size_btc": 0.0,
                "position_size_usdt": 0.0,
                "margin_required_usdt": 0.0,
                "risk_amount_eur": 0.0,
                "leverage_used": leverage,
                "fee_estimate_usdt": 0.0,
                "rr_after_fees": 0.0,
                "sizing_valid": False,
                "reject_reason": "No price or capital",
            }
        
        # EUR → USD (hardcoded - non-async context)
        eur_to_usd = 1.08  # Fallback für _calc_position_size
        capital_usd = capital_eur * eur_to_usd
        
        # 1. Risikobetrag = fixer Prozentsatz des EIGENKAPITALS
        risk_amount_usd = capital_usd * risk_pct
        
        # 2. Score-basierte Risiko-Skalierung
        if abs_score > 80:
            score_mult = 1.5
        elif abs_score > 60:
            score_mult = 1.2
        elif abs_score > 45:
            score_mult = 1.0
        else:
            score_mult = 0.7  # Niedriger Score = weniger Risiko
        
        risk_amount_usd *= score_mult
        
        # 3. Session-Anpassung
        session_mult = session.get("volatility_bias", 1.0) if isinstance(session, dict) else 1.0
        risk_amount_usd *= min(1.4, max(0.6, session_mult))
        
        # 4. SL-Distanz aus ATR
        atr_pct = atr / price if atr > 0 else 0.01
        sl_pct = max(0.008, min(0.025, atr_pct * 1.5))  # 1.5× ATR als SL
        
        # 5. Positionsgröße = Risikobetrag ÷ SL-Distanz
        position_size_usd = risk_amount_usd / sl_pct
        position_size_btc = position_size_usd / price
        
        # 6. Margin-Check
        margin_required = position_size_usd / leverage
        max_margin = capital_usd * 0.80  # Max 80% des Kapitals als Margin
        
        if margin_required > max_margin:
            position_size_usd = max_margin * leverage
            position_size_btc = position_size_usd / price
            margin_required = max_margin
        
        # 7. Minimum Notional Check
        if position_size_usd < min_notional:
            return {
                "position_size_btc": 0.0,
                "position_size_usdt": round(position_size_usd, 2),
                "margin_required_usdt": round(margin_required, 2),
                "risk_amount_eur": round(risk_amount_usd / eur_to_usd, 2),
                "leverage_used": leverage,
                "fee_estimate_usdt": 0.0,
                "rr_after_fees": 0.0,
                "sizing_valid": False,
                "reject_reason": f"Below min notional: ${position_size_usd:.0f} < ${min_notional:.0f}",
            }
        
        # 8. Fee-bewusstes R:R
        tp1_pct = sl_pct * 1.8  # Minimum TP1 = 1.8× SL
        fees_round_trip = position_size_usd * fee_rate * 2
        
        profit_tp1 = position_size_usd * tp1_pct - fees_round_trip
        loss_sl = position_size_usd * sl_pct + fees_round_trip
        rr_after_fees = profit_tp1 / loss_sl if loss_sl > 0 else 0
        
        if rr_after_fees < min_rr:
            return {
                "position_size_btc": round(position_size_btc, 5),
                "position_size_usdt": round(position_size_usd, 2),
                "margin_required_usdt": round(margin_required, 2),
                "risk_amount_eur": round(risk_amount_usd / eur_to_usd, 2),
                "leverage_used": leverage,
                "fee_estimate_usdt": round(fees_round_trip, 2),
                "rr_after_fees": round(rr_after_fees, 2),
                "sizing_valid": False,
                "reject_reason": f"R:R after fees too low: {rr_after_fees:.2f} < {min_rr}",
            }
        
        # 9. Binance Minimum
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
            "score_mult": score_mult,
            "session_mult": round(session_mult, 2),
            "sizing_valid": True,
            "reject_reason": None,
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
        Regime-Bestimmung mit ATR-Ratio und BB-Width (Bruno v3).
        
        Metriken:
        - ATR-Ratio: ATR(14) / Preis (Volatilitätsmaß)
        - BB-Width: Bollinger Band Breite in % (Volatilitätsmaß)
        - Macro Trend: Daily-Trend für Kontext
        
        Regime-Logik:
        - high_vola: ATR-Ratio > 2.5% oder BB-Width > 4%
        - trending_bull: EMA Stack bull + Macro Bull + moderate Volatilität
        - bear: EMA Stack bear
        - ranging: Default bei gemischten Signalen
        """
        # ATR-Ratio berechnen
        atr = float(ta_data.get("atr_14", 0.0))
        price = float(ta_data.get("price", 0.0))
        atr_ratio = (atr / price * 100) if price > 0 else 0.0
        
        # BB-Width aus TA-Daten (wenn verfügbar, sonst schätzen)
        bb_data = ta_data.get("bollinger_bands", {})
        bb_width = float(bb_data.get("width", 0.0))
        
        # Macro Trend für Kontext
        macro_trend = ta_data.get("macro_trend", {})
        mt = macro_trend.get("macro_trend", "unknown")
        
        # 1. High Volatility Detection (ATR-Ratio oder BB-Width)
        if atr_ratio > 2.5 or bb_width > 4.0:
            return "high_vola"
        
        # 2. Trend Detection mit Macro Override
        trend = ta_data.get("trend", {})
        ema_stack = trend.get("ema_stack", "mixed")
        
        # Macro Override: Daily-Trend schlägt 1h-Trend
        if mt == "macro_bear":
            if ema_stack in ("perfect_bull", "bull"):
                # 1h bull in daily bear = RANGING (Bear Market Rally!)
                return "ranging"
            return "bear"
        
        if mt == "macro_bull":
            if ema_stack in ("perfect_bull", "bull"):
                return "trending_bull"  # Nur wenn AUCH daily bull
            return "ranging"  # 1h bull ohne daily confirmation = ranging
        
        # Ohne klaren Macro-Trend: EMA Stack entscheidet
        if ema_stack in ("perfect_bull", "bull"):
            # Prüfe Volatilität: zu hohe Vola = nicht trending
            if atr_ratio > 1.8:
                return "ranging"  # Hohe Vola bricht Trend
            return "trending_bull" if atr_ratio < 1.0 else "ranging"
        elif ema_stack in ("perfect_bear", "bear"):
            return "bear"
        
        # Default: Ranging bei gemischten Signalen
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

    def _get_threshold(self, atr: float = 0.0, price: float = 0.0, macro_data: dict = None) -> float:
        """Adaptiver Threshold: Basis × Volatilitäts-Multiplikator × Event-Multiplikator."""
        learning_enabled = ConfigCache.get("LEARNING_MODE_ENABLED", False)
        if learning_enabled:
            base = float(ConfigCache.get("COMPOSITE_THRESHOLD_LEARNING", 16))  # Lowered to 16 for Bruno v3
        else:
            base = float(ConfigCache.get("COMPOSITE_THRESHOLD_PROD", 40))

        if atr <= 0 or price <= 0:
            return base

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

        # HARD FLOOR: In Learning Mode, allow lower thresholds (no floor), in Prod: min 25
        if learning_enabled:
            return round(base * vol_mult * event_mult, 1)  # No floor in Learning Mode
        else:
            return round(max(25.0, base * vol_mult * event_mult), 1)  # Prod floor at 25

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
