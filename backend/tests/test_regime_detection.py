"""
Tests für _determine_regime (BRUNO-FIX-02).
Validiert BTC-realistische Regime-Klassifikation.
"""
import pytest
from unittest.mock import MagicMock
from app.services.composite_scorer import CompositeScorer


@pytest.fixture
def scorer():
    return CompositeScorer(redis_client=MagicMock())


def _ta_data(atr: float, price: float, ema_stack: str, macro_trend: str = "unknown",
             bb_width: float = 2.0) -> dict:
    return {
        "atr_14": atr,
        "price": price,
        "trend": {"ema_stack": ema_stack, "strength": 0.5},
        "macro_trend": {"macro_trend": macro_trend},
        "bollinger_bands": {"width": bb_width},
    }


def test_regime_trending_bull_realistic_atr(scorer):
    """BTC mit 1.5% ATR-Ratio und Bull-Stack → trending_bull (vorher: ranging)."""
    ta = _ta_data(atr=1500, price=100_000, ema_stack="perfect_bull", macro_trend="macro_bull")
    assert scorer._determine_regime(ta, {}) == "trending_bull"


def test_regime_bear_realistic_atr(scorer):
    ta = _ta_data(atr=1500, price=100_000, ema_stack="perfect_bear", macro_trend="macro_bear")
    assert scorer._determine_regime(ta, {}) == "bear"


def test_regime_high_vola_only_extreme(scorer):
    """ATR-Ratio 2.8% ist NICHT high_vola mehr, 4.0% schon."""
    ta_moderate = _ta_data(atr=2800, price=100_000, ema_stack="bull")
    ta_extreme = _ta_data(atr=4000, price=100_000, ema_stack="bull")
    assert scorer._determine_regime(ta_moderate, {}) != "high_vola"
    assert scorer._determine_regime(ta_extreme, {}) == "high_vola"


def test_regime_mixed_defaults_to_ranging_not_unknown(scorer):
    """Mixed EMA stack → ranging, niemals unknown."""
    ta = _ta_data(atr=1500, price=100_000, ema_stack="mixed")
    result = scorer._determine_regime(ta, {})
    assert result == "ranging"
    assert result != "unknown"


def test_regime_bear_market_rally(scorer):
    """1h bull in daily bear → ranging (Bear Market Rally)."""
    ta = _ta_data(atr=1500, price=100_000, ema_stack="bull", macro_trend="macro_bear")
    assert scorer._determine_regime(ta, {}) == "ranging"


def test_no_regime_blocks_all_trades():
    """Invariante: Kein Regime darf sowohl Longs als auch Shorts blockieren."""
    from app.services.regime_config import REGIME_CONFIGS
    for name, cfg in REGIME_CONFIGS.items():
        assert cfg.allow_longs or cfg.allow_shorts, (
            f"Regime '{name}' blockiert sowohl Longs als auch Shorts — stiller Hard-Block!"
        )
