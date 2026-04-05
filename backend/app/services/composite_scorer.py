from dataclasses import dataclass, field
from typing import Optional
import json
import logging
import os
from datetime import datetime, timezone

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
        }
    
    def to_decision_feed_entry(self) -> dict:
        """Entry für bruno:decisions:feed (Dashboard-Kompatibilität)."""
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ofi": 0.0,
            "ofi_met": True,
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
            "weight_preset": self.weight_preset,
            "take_profit_1_pct": self.take_profit_1_pct,
            "take_profit_2_pct": self.take_profit_2_pct,
            "tp1_size_pct": self.tp1_size_pct,
            "tp2_size_pct": self.tp2_size_pct,
            "breakeven_trigger_pct": self.breakeven_trigger_pct,
        }


class CompositeScorer:
    """
    Deterministische Trade-Entscheidungslogik mit regime-adaptiver Gewichtung.
    Ersetzt die 3-Layer LLM-Cascade.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger("composite_scorer")

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
        
        # 2. Einzelscores
        ta_score = self._score_ta(ta_data)
        liq_score = self._score_liq(liq_data)
        analytics_data = await self.redis.get_cache("bruno:binance:analytics") or {}
        flow_score = await self._score_flow(flow_data, macro_data, analytics_data)
        macro_score = self._score_macro(macro_data)
        
        result.ta_score = ta_score
        result.liq_score = liq_score
        result.flow_score = flow_score
        result.macro_score = macro_score
        
        # 3. Regime bestimmen → Gewichte wählen (NEU: dynamisch)
        regime = self._determine_regime(ta_data, macro_data)
        result.regime = regime

        trend_strength = float(ta_data.get("trend", {}).get("strength", 0.0))
        weights = self._get_weights(regime, trend_strength)
        result.weight_preset = self._blend_label(self._regime_blend(regime, trend_strength), regime)
        
        # 4. Gewichteter Composite Score
        # TA: -100..+100, Liq/Flow/Macro: -50..+50 (×2 normalisiert auf 100)
        composite = (
            ta_score * weights["ta"] +
            (liq_score * 2) * weights["liq"] +
            (flow_score * 2) * weights["flow"] +
            (macro_score * 2) * weights["macro"]
        )
        result.composite_score = round(max(-100, min(100, composite)), 1)
        
        # 5. Richtung
        result.direction = "long" if composite > 0 else "short" if composite < 0 else "neutral"
        
        # 6. MTF + Sweep Status
        result.mtf_aligned = ta_data.get("ta_score", {}).get("mtf_aligned", False)
        sweep = liq_data.get("sweep", {})
        result.sweep_confirmed = sweep.get("all_confirmed", False)
        
        # 7. Threshold + Bonus-Logik
        threshold = self._get_threshold()
        abs_score = abs(composite)
        
        # Sweep-Bonus: Ein bestätigter 3×-Sweep senkt den Threshold um 15
        # Begründung: Sweeps sind die höchstwahrscheinlichen Setups
        effective_threshold = threshold
        if result.sweep_confirmed:
            effective_threshold = max(30, threshold - 15)
            result.signals_active.append("Sweep-Bonus: Threshold -15")
        
        result.should_trade = abs_score >= effective_threshold
        result.conviction = min(1.0, abs_score / 100.0)
        
        # 8. Position Sizing + SL/TP
        atr = ta_data.get("atr_14", 0.0)
        session = ta_data.get("session", {})
        result.position_size_pct = self._calc_position_size(abs_score, atr, result.price, session)
        (
            result.stop_loss_pct,
            result.take_profit_1_pct,
            result.take_profit_2_pct,
            result.tp1_size_pct,
            result.tp2_size_pct,
            result.breakeven_trigger_pct,
        ) = self._calc_sl_tp(atr, result.price, abs_score)
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
            "abs_score": abs_score,
            "gap_to_threshold": round(effective_threshold - abs_score, 1),
            "regime": regime,
            "weights_used": weights,
            "block_reason": self._get_block_reason(result, effective_threshold, macro_data),
        }
        
        return result

    def _get_weights(self, regime: str, trend_strength: float = 0.0) -> dict:
        """
        Wählt Gewichtungs-Preset basierend auf Regime.
        Trending = TA dominiert, Ranging = Liq dominiert.
        
        Kann via config.json überschrieben werden.
        """
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        
        # Config-Überschreibung prüfen
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            if all(k in cfg for k in ["COMPOSITE_W_TA", "COMPOSITE_W_LIQ", 
                                        "COMPOSITE_W_FLOW", "COMPOSITE_W_MACRO"]):
                # Wenn ALLE 4 Keys in config → nutze config (manuelles Override)
                return {
                    "ta": float(cfg["COMPOSITE_W_TA"]),
                    "liq": float(cfg["COMPOSITE_W_LIQ"]),
                    "flow": float(cfg["COMPOSITE_W_FLOW"]),
                    "macro": float(cfg["COMPOSITE_W_MACRO"]),
                }
        except Exception:
            pass

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

    def _calc_position_size(self, abs_score, atr, price, session) -> float:
        """
        ATR + Score + Session-basiertes Position Sizing.
        
        Basis: 1% Risiko.
        Score-Mult: 0.5x (Score 45) bis 1.5x (Score 90+).
        ATR-Mult: 0.3x (extrem) bis 1.2x (ruhig).
        Session-Mult: 0.6x (Asia) bis 1.4x (EU/US Overlap). (NEU)
        """
        base_risk = 1.0
        score_mult = min(1.5, max(0.5, (abs_score - 40) / 50.0 + 0.5))
        
        vol_mult = 1.0
        if price > 0 and atr > 0:
            atr_pct = atr / price
            if atr_pct < 0.005: vol_mult = 1.2
            elif atr_pct < 0.01: vol_mult = 1.0
            elif atr_pct < 0.02: vol_mult = 0.6
            else: vol_mult = 0.3
        
        session_mult = session.get("volatility_bias", 1.0)
        
        return round(min(2.0, base_risk * score_mult * vol_mult * session_mult), 2)

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
        """Deterministische Regime-Bestimmung."""
        trend = ta_data.get("trend", {})
        vix = float(macro_data.get("VIX", 20.0))
        
        if vix > 35: return "high_vola"
        
        ema_stack = trend.get("ema_stack", "mixed")
        if ema_stack in ("perfect_bull", "bull"): return "trending_bull"
        elif ema_stack in ("perfect_bear", "bear"): return "bear"
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

    def _get_threshold(self) -> float:
        """Lädt Threshold aus config.json."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            
            # Learning Mode Check
            learning_enabled = cfg.get("LEARNING_MODE_ENABLED", False)
            if learning_enabled:
                return float(cfg.get("COMPOSITE_THRESHOLD_LEARNING", 35))
            else:
                return float(cfg.get("COMPOSITE_THRESHOLD_PROD", 55))
        except Exception:
            return 55.0  # Default

    def _calc_sl_tp(self, atr: float, price: float, abs_score: float) -> tuple:
        """
        ATR-basierte SL/TP Berechnung mit Scaling-Out.
        
        Ergebnis:
        - SL Prozent
        - TP1 Prozent (konservatives Teilziel)
        - TP2 Prozent (Hauptziel)
        - TP1 Positionsanteil
        - TP2 Positionsanteil
        - Breakeven Trigger Prozent
        """
        if atr <= 0 or price <= 0:
            return 0.010, 0.012, 0.025, 0.50, 0.50, 0.012  # Default
        
        atr_pct = atr / price
        
        # SL Multiplikator basierend auf Score
        if abs_score > 80:
            sl_mult = 1.5
            tp1_mult = 1.2
            tp2_mult = 2.5
        elif abs_score > 60:
            sl_mult = 1.2
            tp1_mult = 1.1
            tp2_mult = 2.2
        else:
            sl_mult = 0.8
            tp1_mult = 1.0
            tp2_mult = 1.8
        
        sl_pct = round(max(0.005, min(0.025, atr_pct * sl_mult)), 3)
        tp1_pct = round(max(0.008, min(0.030, atr_pct * tp1_mult)), 3)
        tp2_pct = round(max(tp1_pct + 0.004, min(0.060, atr_pct * tp2_mult)), 3)
        
        tp1_size_pct = 0.50
        tp2_size_pct = 0.50
        breakeven_trigger_pct = tp1_pct

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
        if ofi > 0.65:
            signals.append("Strong OFI Buy Pressure")
        elif ofi < 0.35:
            signals.append("Strong OFI Sell Pressure")
        
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
        if not result.mtf_aligned:
            return "MTF_NOT_ALIGNED"
        return "NONE"

    async def get_health_status(self) -> dict:
        """Health-Check für den Composite Scorer."""
        return {
            "status": "online",
            "weight_presets": list(WEIGHT_PRESETS.keys()),
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
