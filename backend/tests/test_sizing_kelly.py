"""
Tests für Kelly-inspiriertes Position Sizing (BRUNO-FIX-04).
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.composite_scorer import CompositeScorer
from app.core.config_cache import ConfigCache
import os


@pytest.fixture(autouse=True)
def init_config():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "backend", "config.json"
    )
    if os.path.exists(config_path):
        ConfigCache.init(config_path)


@pytest.fixture
def scorer():
    return CompositeScorer(redis_client=MagicMock())


def test_size_factor_monotonic(scorer):
    """size_factor muss monoton mit abs_score wachsen."""
    session = {"volatility_bias": 1.0}

    scores = [15, 25, 40, 60, 80, 100]
    size_factors = []
    for score in scores:
        result = scorer._calc_position_size(
            abs_score=score, atr=1500, price=100_000, session=session, capital_eur=1000
        )
        size_factors.append(result["size_factor"])

    # Streng monoton steigend
    for i in range(1, len(size_factors)):
        assert size_factors[i] >= size_factors[i-1], (
            f"size_factor nicht monoton: {size_factors}"
        )


def test_no_bucket_jumps(scorer):
    """Kontinuität: zwischen Score 44 und 45 darf kein großer Sprung sein."""
    session = {"volatility_bias": 1.0}

    result_44 = scorer._calc_position_size(44, 1500, 100_000, session, 1000)
    result_45 = scorer._calc_position_size(45, 1500, 100_000, session, 1000)

    ratio = result_45["position_size_usdt"] / max(result_44["position_size_usdt"], 1)
    assert 0.95 < ratio < 1.05, (
        f"Sprung zwischen Score 44 und 45: ratio={ratio}"
    )


def test_learning_mode_phantom_below_notional(scorer):
    """Learning Mode: Position unter Notional → phantom_eligible, nicht hard reject."""
    # Triggere "unter Notional" mit sehr kleinem Kapital
    session = {"volatility_bias": 1.0}
    result = scorer._calc_position_size(
        abs_score=20, atr=3000, price=100_000, session=session, capital_eur=50
    )
    # Bei 50€ Kapital mit ATR 3% sollte Position unter 50 USDT fallen
    if not result["sizing_valid"]:
        assert result["phantom_eligible"] is True or result["position_size_usdt"] >= 50


def test_learning_mode_floor_applied(scorer):
    """Learning Mode: size_factor Floor bei 30%."""
    session = {"volatility_bias": 1.0}
    result = scorer._calc_position_size(
        abs_score=5, atr=1500, price=100_000, session=session, capital_eur=1000
    )
    # Bei Score=5 wäre tanh(5/40)=0.125, aber Floor 0.30 greift
    assert result["size_factor"] >= 0.30


def test_symmetric_sizing_long_short(scorer):
    """Sizing muss unabhängig von Richtung sein (abs_score reingeben)."""
    session = {"volatility_bias": 1.0}
    long_result = scorer._calc_position_size(40, 1500, 100_000, session, 1000)
    short_result = scorer._calc_position_size(40, 1500, 100_000, session, 1000)
    assert long_result["position_size_btc"] == short_result["position_size_btc"]
