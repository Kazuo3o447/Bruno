"""
Regime Config — Phase C

4 Marktregimes mit eigenen Parameter-Sets.
Regime-Persistenz: mindestens 2 konsekutive Bestätigungen vor Wechsel.
Transition-Buffer: höherer GRSS-Threshold direkt nach einem Regime-Wechsel.

Separation of Concerns: diese Datei ist bewusst frei von LLM-Aufrufen.
Der LLMCascade (layer1) liefert den erkannten Regime-String,
diese Klasse validiert und persistiert ihn.
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Regime Parameter-Sets
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegimeConfig:
    name: str
    grss_threshold: int        # Mindest-GRSS für dieses Regime
    ofi_threshold: int         # Order Flow Imbalance Threshold
    stop_loss_pct: float
    take_profit_pct: float     # Impliziert R:R Ratio
    position_size_multiplier: float
    allow_longs: bool
    allow_shorts: bool

    @property
    def rr_ratio(self) -> float:
        return self.take_profit_pct / self.stop_loss_pct


REGIME_CONFIGS: dict[str, RegimeConfig] = {
    "trending_bull": RegimeConfig(
        name="trending_bull",
        grss_threshold=45,         # Niedrig — Trend gibt Rückenwind
        ofi_threshold=400,
        stop_loss_pct=0.008,
        take_profit_pct=0.020,     # 2.5:1 R:R
        position_size_multiplier=1.0,
        allow_longs=True,
        allow_shorts=False,        # Gegen Trend = strukturelles Risiko
    ),
    "ranging": RegimeConfig(
        name="ranging",
        grss_threshold=55,         # Höher — weniger Richtungsklarheit
        ofi_threshold=600,
        stop_loss_pct=0.006,
        take_profit_pct=0.012,     # 2:1 R:R
        position_size_multiplier=0.5,  # Halbe Größe im Chop
        allow_longs=True,
        allow_shorts=True,
    ),
    "high_vola": RegimeConfig(
        name="high_vola",
        grss_threshold=60,
        ofi_threshold=700,
        stop_loss_pct=0.015,       # Weiterer Stop wegen Rauschen
        take_profit_pct=0.030,     # 2:1 R:R — gleiche Ratio, größere Abstände
        position_size_multiplier=0.3,
        allow_longs=True,
        allow_shorts=True,
    ),
    "bear": RegimeConfig(
        name="bear",
        grss_threshold=50,
        ofi_threshold=500,
        stop_loss_pct=0.010,
        take_profit_pct=0.020,
        position_size_multiplier=0.7,
        allow_longs=False,         # Keine Longs im Bärenmarkt
        allow_shorts=True,
    ),
    # Fallback-Regime wenn Layer 1 kein klares Signal liefert
    "unknown": RegimeConfig(
        name="unknown",
        grss_threshold=65,         # Sehr konservativ
        ofi_threshold=800,
        stop_loss_pct=0.010,
        take_profit_pct=0.020,
        position_size_multiplier=0.3,
        allow_longs=False,
        allow_shorts=False,        # Kein Trade bei unbekanntem Regime
    ),
}

VALID_REGIMES = set(REGIME_CONFIGS.keys()) - {"unknown"}

# ─────────────────────────────────────────────────────────────────────────────
# Regime Manager — Persistenz + Transition Buffer
# ─────────────────────────────────────────────────────────────────────────────

class RegimeManager:
    """
    Verwaltet das aktuelle Marktregime mit Persistenz-Schutz.

    Regel: Ein Regime wechselt erst nach MIN_CONFIRMATIONS konsekutiven
    Layer-1-Signalen desselben Regimes. Verhindert nervöses Hin- und
    Herspringen bei einzelnen Ausreißern.

    Transition Buffer: Direkt nach einem Wechsel gelten für 2 Zyklen
    erhöhte GRSS-Thresholds (Unsicherheit in der Übergangsphase).
    """

    MIN_CONFIRMATIONS = 2   # Mindestanzahl konsekutiver gleicher Signale
    TRANSITION_BUFFER_CYCLES = 2  # Zyklen mit erhöhtem GRSS nach Wechsel
    TRANSITION_GRSS_BOOST = 10    # Zusätzliche GRSS-Punkte während Transition

    def __init__(self, redis_client):
        self.redis = redis_client
        self._current_regime: str = "unknown"
        self._pending_regime: str = "unknown"
        self._pending_count: int = 0
        self._transition_cycle: int = 0

    async def load_from_redis(self) -> None:
        """Lädt gespeicherten State beim Agenten-Start."""
        state = await self.redis.get_cache("bruno:regime:state")
        if state:
            self._current_regime = state.get("regime", "unknown")
            self._transition_cycle = state.get("transition_cycle", 0)
            logger.info(f"RegimeManager geladen: {self._current_regime}")

    async def update(self, layer1_regime: str) -> str:
        """
        Verarbeitet neues Layer-1-Signal.
        Gibt das aktuell gültige Regime zurück (nicht unbedingt das neue).
        """
        if layer1_regime not in VALID_REGIMES:
            layer1_regime = "unknown"

        if layer1_regime == self._pending_regime:
            self._pending_count += 1
        else:
            self._pending_regime = layer1_regime
            self._pending_count = 1

        # Transition Buffer runterzählen
        if self._transition_cycle > 0:
            self._transition_cycle -= 1

        # Regime wechseln wenn genug Bestätigungen
        if (self._pending_count >= self.MIN_CONFIRMATIONS
                and self._pending_regime != self._current_regime
                and self._pending_regime != "unknown"):

            old = self._current_regime
            self._current_regime = self._pending_regime
            self._transition_cycle = self.TRANSITION_BUFFER_CYCLES

            logger.info(
                f"Regime gewechselt: {old} → {self._current_regime} "
                f"(nach {self._pending_count} Bestätigungen)"
            )
            await self._persist()

        return self._current_regime

    def get_config(self) -> RegimeConfig:
        return REGIME_CONFIGS[self._current_regime]

    def get_effective_grss_threshold(self) -> int:
        """
        GRSS-Threshold inkl. Transition-Buffer.
        Direkt nach Regime-Wechsel: +10 Punkte extra Konservatismus.
        """
        base = self.get_config().grss_threshold
        if self._transition_cycle > 0:
            return base + self.TRANSITION_GRSS_BOOST
        return base

    def is_in_transition(self) -> bool:
        return self._transition_cycle > 0

    async def _persist(self) -> None:
        await self.redis.set_cache("bruno:regime:state", {
            "regime": self._current_regime,
            "transition_cycle": self._transition_cycle,
        })
