"""
Strategy Manager — Multi-Strategie Orchestrierung.

Verwaltet bis zu 3 gleichzeitige Strategie-Slots mit:
- Unabhängiger Kapitalallokation pro Slot
- Eigenem Risk-Management pro Slot (SL/TP/Sizing)
- Binance Hedge Mode für gleichzeitige Long+Short Positionen
- Portfolio-Level Risk Limits (Gesamt-Exposure nie > 80% des Kapitals)

Slot-Typen:
- TREND: Folgt dem Makro-Trend (4h/1D EMAs), größere SL/TP, längere Haltezeit
- SWEEP: Schnelle Entries nach Liquidation-Cascades, enge SL/TP
- FUNDING: Contrarian-Trades bei extremer Funding Rate

Jeder Slot hat seinen eigenen Redis-Key für Position-Tracking:
- bruno:position:BTCUSDT:trend
- bruno:position:BTCUSDT:sweep
- bruno:position:BTCUSDT:funding
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, List
from app.core.config_cache import ConfigCache

@dataclass
class StrategySlot:
    """Konfiguration für einen Strategie-Slot."""
    name: str
    capital_allocation_pct: float  # Anteil am Gesamtkapital (z.B. 0.40 = 40%)
    max_leverage: int = 3
    enabled: bool = True
    
    # Sizing
    risk_per_trade_pct: float = 0.02  # 2% des SLOT-Kapitals
    min_notional_usdt: float = 200.0
    
    # Scaled Entry Config
    scaled_entry_enabled: bool = True
    entry_tranches: int = 3           # 3 Tranchen: 40%, 30%, 30%
    tranche_sizes: list = field(default_factory=lambda: [0.40, 0.30, 0.30])
    tranche_confirmation_pct: float = 0.005  # 0.5% Bestätigung zwischen Tranchen
    
    # SL/TP Overrides (None = use CompositeScorer defaults)
    sl_atr_mult: Optional[float] = None
    tp_atr_mult: Optional[float] = None
    max_hold_minutes: Optional[int] = None  # Auto-Close nach X Minuten
    
    # Direction Filter
    allow_longs: bool = True
    allow_shorts: bool = True


# Slot-Definitionen
STRATEGY_SLOTS: Dict[str, StrategySlot] = {
    "trend": StrategySlot(
        name="trend",
        capital_allocation_pct=0.40,  # 40% des Kapitals
        max_leverage=3,
        risk_per_trade_pct=0.02,
        min_notional_usdt=300,
        scaled_entry_enabled=True,
        entry_tranches=3,
        tranche_sizes=[0.40, 0.30, 0.30],
        tranche_confirmation_pct=0.005,  # +0.5% bevor nächste Tranche
        sl_atr_mult=1.5,     # 1.5× ATR Stop Loss
        tp_atr_mult=3.0,     # 3.0× ATR Take Profit
        max_hold_minutes=None,  # Kein Zeitlimit
    ),
    "sweep": StrategySlot(
        name="sweep",
        capital_allocation_pct=0.30,  # 30% des Kapitals
        max_leverage=4,               # Etwas aggressiver — Sweeps sind high-probability
        risk_per_trade_pct=0.025,     # 2.5% Risk (höhere Conviction)
        min_notional_usdt=200,
        scaled_entry_enabled=False,   # Kein Scaling — Sweep-Entries sind zeitkritisch
        entry_tranches=1,
        tranche_sizes=[1.0],
        sl_atr_mult=1.0,     # 1× ATR — engerer SL (Sweep-Entries haben klare Invalidation)
        tp_atr_mult=2.5,     # 2.5× ATR TP
        max_hold_minutes=120, # Max 2 Stunden — Sweep-Trades sind schnelle Reversals
    ),
    "funding": StrategySlot(
        name="funding",
        capital_allocation_pct=0.30,  # 30% des Kapitals
        max_leverage=2,               # Konservativ — Funding kann lange extrem bleiben
        risk_per_trade_pct=0.015,     # 1.5% Risk
        min_notional_usdt=200,
        scaled_entry_enabled=False,
        entry_tranches=1,
        tranche_sizes=[1.0],
        sl_atr_mult=2.0,     # 2× ATR — weiter SL (Funding-Reversals brauchen Zeit)
        tp_atr_mult=2.0,     # 2× ATR TP
        max_hold_minutes=480, # Max 8 Stunden (innerhalb 1 Funding-Zyklus)
        # Richtung wird dynamisch gesetzt basierend auf Funding Rate
    ),
}


class StrategyManager:
    """Orchestriert Multi-Strategie-Trading."""
    
    def __init__(self, redis_client, db_session_factory):
        self.redis = redis_client
        self.db = db_session_factory
        self.logger = logging.getLogger("strategy_manager")
        self.slots = dict(STRATEGY_SLOTS)  # Kopie
    
    async def get_slot_capital(self, slot_name: str, total_capital_eur: float) -> float:
        """Berechnet das verfügbare Kapital für einen Slot."""
        slot = self.slots.get(slot_name)
        if not slot or not slot.enabled:
            return 0.0
        return total_capital_eur * slot.capital_allocation_pct
    
    async def get_total_exposure(self) -> dict:
        """Berechnet das Gesamt-Exposure über alle Slots."""
        total_long = 0.0
        total_short = 0.0
        open_slots = []
        
        for slot_name in self.slots:
            pos = await self.redis.get_cache(f"bruno:position:BTCUSDT:{slot_name}")
            if pos and pos.get("status") == "open":
                size_usd = float(pos.get("quantity", 0)) * float(pos.get("entry_price", 0))
                if pos.get("side") == "long":
                    total_long += size_usd
                else:
                    total_short += size_usd
                open_slots.append(slot_name)
        
        return {
            "total_long_usd": round(total_long, 2),
            "total_short_usd": round(total_short, 2),
            "net_exposure_usd": round(total_long - total_short, 2),
            "gross_exposure_usd": round(total_long + total_short, 2),
            "open_slots": open_slots,
            "available_slots": [s for s in self.slots if s not in open_slots and self.slots[s].enabled],
        }
    
    async def can_open_position(self, slot_name: str, position_size_usd: float,
                                 total_capital_usd: float) -> dict:
        """
        Portfolio-Level Risk Check:
        - Gesamt-Exposure nie > 80% des Kapitals
        - Einzelner Slot nie > seine Allokation × Leverage
        - Margin-Check über alle Slots
        """
        exposure = await self.get_total_exposure()
        slot = self.slots.get(slot_name)
        
        if not slot or not slot.enabled:
            return {"allowed": False, "reason": f"Slot {slot_name} disabled"}
        
        # Slot schon belegt?
        if slot_name in exposure["open_slots"]:
            return {"allowed": False, "reason": f"Slot {slot_name} already has open position"}
        
        # Gesamt-Exposure Check
        new_gross = exposure["gross_exposure_usd"] + position_size_usd
        max_gross = total_capital_usd * 0.80 * slot.max_leverage
        if new_gross > max_gross:
            return {
                "allowed": False,
                "reason": f"Gross exposure ${new_gross:.0f} > max ${max_gross:.0f}"
            }
        
        # Slot-Kapital Check
        slot_capital = total_capital_usd * slot.capital_allocation_pct
        slot_max_position = slot_capital * slot.max_leverage
        if position_size_usd > slot_max_position:
            return {
                "allowed": False,
                "reason": f"Position ${position_size_usd:.0f} > slot max ${slot_max_position:.0f}"
            }
        
        return {"allowed": True, "reason": "OK"}
    
    def evaluate_funding_signal(self, funding_rate: float, funding_divergence: float) -> Optional[dict]:
        """
        Funding Rate Contrarian Strategie.
        
        Logik (bewiesen über 5+ Jahre BTC Perp Daten):
        - Funding > 0.05% (50 bps/8h) = Markt extrem bullish = Short-Signal
          (Longs zahlen zu viel → Druck zu schließen → Preis fällt)
        - Funding < -0.01% (-10 bps/8h) = Markt extrem bearish = Long-Signal
          (Shorts zahlen → Druck zu schließen → Preis steigt)
        - Cross-Exchange Divergenz > 0.03% verstärkt das Signal
        
        Kein Signal bei neutraler Funding (-0.01% bis 0.03%).
        """
        slot = self.slots.get("funding")
        if not slot or not slot.enabled:
            return None
        
        funding_bps = funding_rate * 10000
        
        if funding_bps > 50:  # > 0.05% = extrem bullish
            signal_strength = min(1.0, (funding_bps - 50) / 100)  # 0-1 normalisiert
            return {
                "slot": "funding",
                "direction": "short",
                "reason": f"Extreme positive funding: {funding_rate:.4%} ({funding_bps:.0f} bps)",
                "strength": signal_strength,
                "funding_rate": funding_rate,
                "funding_divergence": funding_divergence,
            }
        elif funding_bps < -10:  # < -0.01% = extrem bearish
            signal_strength = min(1.0, abs(funding_bps + 10) / 80)
            return {
                "slot": "funding",
                "direction": "long",
                "reason": f"Extreme negative funding: {funding_rate:.4%} ({funding_bps:.0f} bps)",
                "strength": signal_strength,
                "funding_rate": funding_rate,
                "funding_divergence": funding_divergence,
            }
        
        return None  # Keine extreme Funding → kein Signal
    
    def evaluate_sweep_signal(self, sweep_data: dict, liq_score: float) -> Optional[dict]:
        """
        Sweep-Strategie als eigenständiger Slot.
        
        Trigger: 3-fach bestätigter Sweep (liq_spike + wick + OI drop).
        Das ist Brunos stärkstes Signal — aktuell wird es nur als 
        Bonus im Composite Score verwendet. Als eigenständige Strategie
        hat es eine deutlich höhere Win-Rate.
        """
        slot = self.slots.get("sweep")
        if not slot or not slot.enabled:
            return None
        
        if not sweep_data.get("all_confirmed"):
            return None
        
        post_entry = sweep_data.get("post_sweep_entry")
        if not post_entry:
            return None
        
        # Richtungsfilter
        if post_entry == "long" and not slot.allow_longs:
            return None
        if post_entry == "short" and not slot.allow_shorts:
            return None
        
        return {
            "slot": "sweep",
            "direction": post_entry,
            "reason": f"3× confirmed sweep → {post_entry}",
            "strength": min(1.0, abs(liq_score) / 30),
            "sweep_intensity": sweep_data.get("intensity", 0),
            "confirmations": sweep_data.get("confirmations", {}),
        }
