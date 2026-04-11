"""
Symmetrie-Invarianten für den CompositeScorer (BRUNO-FIX-01).
Bull- und Bear-Setups müssen identische absolute Scores produzieren.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.composite_scorer import CompositeScorer


def _make_ta_snapshot(score: float, rsi: float = 50.0, vwap_dist: float = 0.0) -> dict:
    """Erzeuge ein (a)symmetrisches TA-Snapshot."""
    return {
        "price": 100_000.0,
        "atr_14": 500.0,
        "rsi": rsi,
        "vwap": 100_000.0 * (1 - vwap_dist),
        "ta_score": {
            "score": score,
            "mtf_aligned": True,
            "signals": [],
        },
        "trend": {
            "ema_stack": "bull" if score > 0 else "bear" if score < 0 else "mixed",
            "strength": abs(score) / 100.0,
        },
        "mtf": {
            "alignment_score": 0.8 if score > 0 else -0.8,
            "aligned_long": score > 0,
            "aligned_short": score < 0,
        },
        "session": {"session": "us", "volatility_bias": 1.0},
        "macro_trend": {"macro_trend": "unknown", "allow_longs": True, "allow_shorts": True},
        "bollinger_bands": {"width": 2.0},
    }


def _base_cache(ta_score: float = 40.0, rsi: float = 50.0) -> dict:
    return {
        "bruno:ta:snapshot": _make_ta_snapshot(ta_score, rsi=rsi),
        "bruno:liq:intelligence": {"liq_score": 0.0, "sweep": {}},
        "bruno:quant:micro": {
            "CVD": 0.0, "OFI_Buy_Pressure": 0.5, "OFI_Available": True,
            "OFI_Mean_Imbalance": 1.0, "price": 100_000.0,
        },
        "bruno:context:grss": {"GRSS_Score": 50.0, "Funding_Rate": 0.0},
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000.0},
    }


@pytest.mark.asyncio
async def test_symmetry_bull_vs_bear_basic():
    """TA=+40 vs TA=-40 müssen gleichen abs(composite_score) haben."""
    redis_mock = MagicMock()

    # Bull
    cache = _base_cache(ta_score=40.0)
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    bull_result = await scorer.score()

    # Bear
    cache = _base_cache(ta_score=-40.0)
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    bear_result = await scorer.score()

    delta = abs(abs(bull_result.composite_score) - abs(bear_result.composite_score))
    assert delta < 0.5, (
        f"Symmetry violation: bull={bull_result.composite_score}, "
        f"bear={bear_result.composite_score}, delta={delta}"
    )
    assert bull_result.direction == "long"
    assert bear_result.direction == "short"


@pytest.mark.asyncio
async def test_symmetry_rsi_extremes():
    """RSI=20 und RSI=80 müssen gleich starke (gegensätzliche) Score-Beiträge liefern."""
    redis_mock = MagicMock()

    cache = _base_cache(ta_score=0.0, rsi=20.0)
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    oversold = await scorer.score()

    cache = _base_cache(ta_score=0.0, rsi=80.0)
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    overbought = await scorer.score()

    delta = abs(abs(oversold.composite_score) - abs(overbought.composite_score))
    assert delta < 2.0, (
        f"RSI symmetry violation: os={oversold.composite_score}, "
        f"ob={overbought.composite_score}"
    )


@pytest.mark.asyncio
async def test_mr_cap_applies_to_bear_trend():
    """Bei starkem Bear-Trend (TA=-85) darf oversold MR den Score NICHT abschwächen."""
    redis_mock = MagicMock()

    # Starker Bear-Trend + oversold RSI (würde MR positiv machen)
    cache = _base_cache(ta_score=-85.0, rsi=15.0)
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    # Erwartung: direction bleibt short, mr_contribution ist gecapped
    assert result.direction == "short", f"Expected short, got {result.direction}"
    assert any("MR capped" in s for s in result.signals_active), (
        "MR cap should have triggered for bear trend"
    )


@pytest.mark.asyncio
async def test_mr_sign_conflict_neutralized():
    """MR mit gegensätzlichem Vorzeichen zu Strategy A → mr_contribution = 0."""
    redis_mock = MagicMock()

    # Bull-TA, aber Preis ist weit über VWAP → MR negativ (overbought)
    cache = _base_cache(ta_score=35.0, rsi=50.0)
    # Override VWAP so that price is 2% above → MR negative
    cache["bruno:ta:snapshot"]["vwap"] = 98_000.0  # price=100k, 2% über VWAP

    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    # Composite darf NICHT gegen Null gedrückt sein
    assert result.composite_score > 10, (
        f"MR sign conflict should have been neutralized, composite={result.composite_score}"
    )
    assert any("MR neutralized" in s or "MR capped" in s for s in result.signals_active), (
        f"Expected MR neutralization signal, got: {result.signals_active}"
    )


@pytest.mark.asyncio
async def test_confluence_bonus_with_mtf_only():
    """Mit MTF aligned + 3 Signalen → Confluence Bonus wird gegeben (ohne Liq-Requirement)."""
    redis_mock = MagicMock()

    cache = _base_cache(ta_score=20.0)
    cache["bruno:quant:micro"]["OFI_Buy_Pressure"] = 0.72  # Flow bullish
    cache["bruno:context:grss"]["GRSS_Score"] = 62  # Macro bullish
    # TA, Flow, Macro = 3 bullish Signals; MTF aligned

    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    assert any("Confluence Bonus +" in s for s in result.signals_active), (
        f"Confluence bonus should have triggered, signals={result.signals_active}"
    )


@pytest.mark.asyncio
async def test_blend_ratio_reduced_in_ranging():
    """Im ranging regime muss Strategy A dominieren (blend_ratio=0.15)."""
    redis_mock = MagicMock()

    cache = _base_cache(ta_score=40.0)
    # ranging regime durch EMA mixed
    cache["bruno:ta:snapshot"]["trend"]["ema_stack"] = "mixed"

    redis_mock.get_cache = AsyncMock(side_effect=lambda k: cache.get(k, {}))
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()

    # Composite sollte deutlich über 10 liegen (war früher durch Blending unter 0)
    assert result.composite_score > 5, (
        f"Expected composite > 5 after blend reduction, got {result.composite_score}"
    )
