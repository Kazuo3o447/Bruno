"""
Regime Manager für LLM-Kaskade — Phase C

Verwaltet Regime-Konfigurationen und 2-Bestätigungs-Logik.
Persistiert in Redis für Cross-Run-Konsistenz.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RegimeConfig:
    """Konfiguration für ein Markt-Regime."""
    
    # Trading-Erlaubnisse
    allow_longs: bool = True
    allow_shorts: bool = True
    
    # Risk-Parameter (Defaults)
    stop_loss_pct: float = 0.010      # 1.0%
    take_profit_pct: float = 0.020    # 2.0%
    max_position_size_pct: float = 0.10  # 10% vom Kapital
    
    # FIX: V2.2 Multi-Level-Exit Parameter
    tp1_size_pct: float = 0.5          # 50% bei TP1
    atr_multiplier: float = 1.5        # ATR Multiplier für Trailing SL
    breakeven_trigger_pct: float = 0.005  # 0.5% für Breakeven
    
    # Regime-spezifische Anpassungen
    volatility_multiplier: float = 1.0
    confidence_threshold: float = 0.65


# Regime-Konfigurationen (BRUNO-FIX-02: Keine stillen Hard-Blocks!)
REGIME_CONFIGS: Dict[str, RegimeConfig] = {
    "trending_bull": RegimeConfig(
        allow_longs=True,
        allow_shorts=True,    # War False — Counter-Trend-Shorts bei Break möglich
        stop_loss_pct=0.012,
        take_profit_pct=0.025,
        max_position_size_pct=0.15,
        tp1_size_pct=0.6,
        atr_multiplier=1.8,
        breakeven_trigger_pct=0.004,
        volatility_multiplier=1.2,
        confidence_threshold=0.60,
    ),
    "ranging": RegimeConfig(
        allow_longs=True,
        allow_shorts=True,
        stop_loss_pct=0.010,
        take_profit_pct=0.020,
        max_position_size_pct=0.10,
        tp1_size_pct=0.5,
        atr_multiplier=1.3,
        breakeven_trigger_pct=0.005,
        volatility_multiplier=1.0,
        confidence_threshold=0.65,
    ),
    "crash": RegimeConfig(
        allow_longs=False,      # Nur bei Crash: keine Longs (Verkaufspanik)
        allow_shorts=True,
        stop_loss_pct=0.018,
        take_profit_pct=0.040,
        max_position_size_pct=0.06,
        tp1_size_pct=0.3,
        atr_multiplier=2.0,
        breakeven_trigger_pct=0.008,
        volatility_multiplier=0.8,
        confidence_threshold=0.70,
    ),
    "high_vola": RegimeConfig(
        allow_longs=True,     # War False — high_vola ist OPPORTUNITY, nicht Block
        allow_shorts=True,    # War False
        stop_loss_pct=0.020,  # Weiter SL wegen höherer Vola
        take_profit_pct=0.040,
        max_position_size_pct=0.07,
        tp1_size_pct=0.4,
        atr_multiplier=1.8,
        breakeven_trigger_pct=0.010,
        volatility_multiplier=1.3,
        confidence_threshold=0.70,
    ),
    "bear": RegimeConfig(
        allow_longs=True,     # War False — Bear-Rally-Longs möglich
        allow_shorts=True,
        stop_loss_pct=0.012,
        take_profit_pct=0.024,
        max_position_size_pct=0.10,
        tp1_size_pct=0.5,
        atr_multiplier=1.5,
        breakeven_trigger_pct=0.006,
        volatility_multiplier=1.0,
        confidence_threshold=0.65,
    ),
    # "unknown" bleibt als Safety-Fallback bestehen, aber mit vollen Permissions
    "unknown": RegimeConfig(
        allow_longs=True,     # War False — kein stiller Block mehr
        allow_shorts=True,    # War False
        stop_loss_pct=0.012,
        take_profit_pct=0.024,
        max_position_size_pct=0.08,
        tp1_size_pct=0.5,
        atr_multiplier=1.3,
        breakeven_trigger_pct=0.006,
        volatility_multiplier=1.0,
        confidence_threshold=0.70,
    ),
}


class RegimeManager:
    """Verwaltet Regime-Erkennung mit 2-Bestätigungs-Logik."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self._current_regime: Optional[str] = None
        self._current_config: Optional[RegimeConfig] = None
        self._confirmation_count: int = 0
        self._required_confirmations: int = 2
        
    async def load_from_redis(self) -> None:
        """Lädt aktuellen Regime-Zustand aus Redis."""
        try:
            data = await self.redis.get_cache("bruno:regime:state")
            if data:
                self._current_regime = data.get("regime", "unknown")
                self._confirmation_count = data.get("confirmation_count", 0)
                self._current_config = REGIME_CONFIGS.get(self._current_regime, REGIME_CONFIGS["unknown"])
                logger.info(f"Regime geladen: {self._current_regime} ({self._confirmation_count}/{self._required_confirmations})")
            else:
                # Initialer Zustand
                self._current_regime = "unknown"
                self._confirmation_count = 0
                self._current_config = REGIME_CONFIGS["unknown"]
                await self._save_state()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Regime-Zustands: {e}")
            self._current_regime = "unknown"
            self._confirmation_count = 0
            self._current_config = REGIME_CONFIGS["unknown"]
    
    async def update(self, detected_regime: str) -> str:
        """
        Aktualisiert Regime mit 2-Bestätigungs-Logik.
        
        Args:
            detected_regime: Neuer Regime-Vorschlag von Layer 1
            
        Returns:
            Bestätigtes Regime (nach 2x gleicher Detection)
        """
        if detected_regime == self._current_regime:
            # Gleiche Detection → Zähler erhöhen
            self._confirmation_count = min(self._confirmation_count + 1, self._required_confirmations)
        else:
            # Neue Detection → Zähler zurücksetzen
            logger.info(f"Regime-Wechsel erkannt: {self._current_regime} → {detected_regime}")
            self._current_regime = detected_regime
            self._confirmation_count = 1
            self._current_config = REGIME_CONFIGS.get(detected_regime, REGIME_CONFIGS["unknown"])
        
        await self._save_state()
        
        # Bestätigt erst nach 2x gleicher Detection
        if self._confirmation_count >= self._required_confirmations:
            logger.info(f"Regime bestätigt: {self._current_regime}")
            return self._current_regime
        else:
            logger.debug(f"Regime vorläufig: {self._current_regime} ({self._confirmation_count}/{self._required_confirmations})")
            return self._current_regime
    
    def get_config(self) -> RegimeConfig:
        """Gibt aktuelle Regime-Konfiguration zurück."""
        return self._current_config or REGIME_CONFIGS["unknown"]
    
    def get_regime(self) -> str:
        """Gibt aktuelles Regime zurück."""
        return self._current_regime or "unknown"
    
    def is_confirmed(self) -> bool:
        """Prüft ob Regime bestätigt ist (2x Detection)."""
        return self._confirmation_count >= self._required_confirmations
    
    async def _save_state(self) -> None:
        """Speichert aktuellen Zustand in Redis."""
        try:
            state = {
                "regime": self._current_regime,
                "confirmation_count": self._confirmation_count,
                "confirmed": self.is_confirmed(),
                "config": {
                    "allow_longs": self._current_config.allow_longs,
                    "allow_shorts": self._current_config.allow_shorts,
                    "stop_loss_pct": self._current_config.stop_loss_pct,
                    "take_profit_pct": self._current_config.take_profit_pct,
                    "max_position_size_pct": self._current_config.max_position_size_pct,
                },
                "updated_at": str(self.redis.get_current_time())
            }
            await self.redis.set_cache("bruno:regime:state", state, ttl=3600)  # 1 Stunde
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Regime-Zustands: {e}")
    
    async def force_regime(self, regime: str) -> None:
        """Setzt Regime manuell (für Testing/Debug)."""
        if regime in REGIME_CONFIGS:
            self._current_regime = regime
            self._confirmation_count = self._required_confirmations
            self._current_config = REGIME_CONFIGS[regime]
            await self._save_state()
            logger.info(f"Regime manuell gesetzt: {regime}")
        else:
            logger.warning(f"Unbekanntes Regime: {regime}")
