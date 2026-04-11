"""
Tests für BRUNO-FIX-05: Learning Mode als echte Exploration.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.composite_scorer import CompositeScorer
from app.core.config_cache import ConfigCache


@pytest.mark.asyncio
async def test_conviction_not_halved_in_learning_mode():
    """Bei aktivem Learning Mode darf Data Gap die Conviction NICHT halbieren."""
    # Setup Learning Mode
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": True,
        "DISABLE_CONVICTION_HALVING_IN_LEARNING": True,
        "COMPOSITE_THRESHOLD_LEARNING": 15,
        "RISK_PER_TRADE_PCT": 2.5,
        "LEVERAGE": 5,
        "MIN_NOTIONAL_USDT_LEARNING": 50,
        "MIN_RR_AFTER_FEES_LEARNING": 1.1,
    }

    redis_mock = MagicMock()
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 50,
            "vwap": 100_000,
            "ta_score": {"score": 40, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.6},
            "mtf": {"alignment_score": 0.8, "aligned_long": True, "aligned_short": False},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "macro_bull", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 5, "sweep": {}},
        "bruno:quant:micro": {
            "price": 100_000, "CVD": 100,
            "OFI_Buy_Pressure": None,  # ← OFI nicht verfügbar
            "OFI_Available": False,
        },
        "bruno:context:grss": {
            "GRSS_Score": 55,
            "DVOL": None,  # ← DVOL fehlt
            "Long_Short_Ratio": None,  # ← LSR fehlt
        },
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))

    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    # Conviction sollte NICHT halbiert sein
    expected_base = min(1.0, abs(result.composite_score) / 100.0)
    assert abs(result.conviction - expected_base) < 0.01, (
        f"Conviction halved despite learning mode: {result.conviction} vs expected {expected_base}"
    )
    # Signal enthält "learning mode, no halving"
    assert any("learning mode" in s.lower() for s in result.signals_active)


@pytest.mark.asyncio
async def test_ofi_penalty_disabled_in_learning():
    """Im Learning Mode darf OFI Gap nicht effective_threshold erhöhen."""
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": True,
        "DISABLE_OFI_GAP_PENALTY_IN_LEARNING": True,
        "COMPOSITE_THRESHOLD_LEARNING": 15,
        "COMPOSITE_THRESHOLD_PROD": 40,
    }

    redis_mock = MagicMock()
    # Minimales Cache, OFI fehlt
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 50, "vwap": 100_000,
            "ta_score": {"score": 20, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.4},
            "mtf": {"alignment_score": 0.5, "aligned_long": True},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "unknown", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 0, "sweep": {}},
        "bruno:quant:micro": {"price": 100_000, "OFI_Buy_Pressure": None, "OFI_Available": False},
        "bruno:context:grss": {"GRSS_Score": 50},
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))

    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    # effective_threshold sollte NICHT erhöht sein (immer noch im Bereich des Basis-Thresholds)
    eff_t = result.diagnostics.get("effective_threshold", 0)
    assert eff_t < 20, f"effective_threshold should not be elevated: {eff_t}"
    assert not any("OFI Data Gap: Threshold +8" in s for s in result.signals_active)
