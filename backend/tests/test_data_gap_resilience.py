"""
Tests für BRUNO-FIX-06: Data Gap Resilience.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.composite_scorer import CompositeScorer
from app.core.config_cache import ConfigCache


@pytest.mark.asyncio
async def test_partial_data_not_critical():
    """Einzelnes DVOL-Missing darf critical_data_gap nicht triggern."""
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": False,  # Prod-Mode
        "COMPOSITE_THRESHOLD_PROD": 40,
        "RISK_PER_TRADE_PCT": 2.0,
        "LEVERAGE": 5,
        "MIN_NOTIONAL_USDT": 100,
        "MIN_RR_AFTER_FEES": 1.5,
    }
    
    redis_mock = MagicMock()
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 50, "vwap": 100_000,
            "ta_score": {"score": 50, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.7},
            "mtf": {"alignment_score": 0.8, "aligned_long": True},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "macro_bull", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 5, "sweep": {}},
        "bruno:quant:micro": {
            "price": 100_000, "OFI_Buy_Pressure": 0.65,
            "OFI_Available": True,  # OFI ist da
        },
        "bruno:context:grss": {
            "GRSS_Score": 58,
            "DVOL": None,  # DVOL fehlt
            "Long_Short_Ratio": 1.2,  # LSR da
            "Data_Status": {
                "components_ok": 5,
                "components_total": 6,
                "grss_blackout": False,  # Nicht Blackout
                "dvol_missing": True,
                "lsr_missing": False,
            },
        },
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))
    
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()
    
    # critical_data_gap sollte False sein, conviction nicht halbiert
    assert result.diagnostics.get("critical_data_gap") is False
    expected_conviction = min(1.0, abs(result.composite_score) / 100.0)
    assert abs(result.conviction - expected_conviction) < 0.02


@pytest.mark.asyncio
async def test_grss_blackout_triggers_critical():
    """Nur bei echtem Blackout (nur 1/6 Komponenten) ist critical_data_gap aktiv."""
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": False,
        "COMPOSITE_THRESHOLD_PROD": 40,
    }
    
    redis_mock = MagicMock()
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 50, "vwap": 100_000,
            "ta_score": {"score": 40, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.5},
            "mtf": {"alignment_score": 0.6, "aligned_long": True},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "unknown", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 0, "sweep": {}},
        "bruno:quant:micro": {
            "price": 100_000, "OFI_Buy_Pressure": None,
            "OFI_Available": False,
        },
        "bruno:context:grss": {
            "GRSS_Score": 50,
            "Data_Status": {
                "components_ok": 1,
                "components_total": 6,
                "grss_blackout": True,
            },
        },
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))
    
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()
    
    assert result.diagnostics.get("critical_data_gap") is True


@pytest.mark.asyncio
async def test_grss_blackout_with_ofi_available():
    """GRSS Blackout aber OFI verfügbar → kein critical_data_gap."""
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": False,
        "COMPOSITE_THRESHOLD_PROD": 40,
    }
    
    redis_mock = MagicMock()
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 50, "vwap": 100_000,
            "ta_score": {"score": 45, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.6},
            "mtf": {"alignment_score": 0.7, "aligned_long": True},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "macro_bull", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 5, "sweep": {}},
        "bruno:quant:micro": {
            "price": 100_000, "OFI_Buy_Pressure": 0.55,
            "OFI_Available": True,  # OFI verfügbar
        },
        "bruno:context:grss": {
            "GRSS_Score": 50,
            "Data_Status": {
                "components_ok": 1,
                "components_total": 6,
                "grss_blackout": True,  # GRSS Blackout
            },
        },
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))
    
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()
    
    # critical_data_gap sollte False sein, da OFI verfügbar
    assert result.diagnostics.get("critical_data_gap") is False


@pytest.mark.asyncio
async def test_partial_data_conviction_not_halved():
    """Partielle Daten sollten die conviction nicht halbieren."""
    ConfigCache._config = {
        "LEARNING_MODE_ENABLED": False,
        "COMPOSITE_THRESHOLD_PROD": 40,
    }
    
    redis_mock = MagicMock()
    redis_mock.get_cache = AsyncMock(side_effect=lambda k: {
        "bruno:ta:snapshot": {
            "price": 100_000, "atr_14": 1500, "rsi": 60, "vwap": 100_000,
            "ta_score": {"score": 65, "mtf_aligned": True, "signals": []},
            "trend": {"ema_stack": "bull", "strength": 0.8},
            "mtf": {"alignment_score": 0.9, "aligned_long": True},
            "session": {"volatility_bias": 1.0},
            "macro_trend": {"macro_trend": "macro_bull", "allow_longs": True, "allow_shorts": True},
        },
        "bruno:liq:intelligence": {"liq_score": 8, "sweep": {}},
        "bruno:quant:micro": {
            "price": 100_000, "OFI_Buy_Pressure": 0.75,
            "OFI_Available": True,
        },
        "bruno:context:grss": {
            "GRSS_Score": 62,
            "DVOL": None,  # DVOL fehlt
            "Long_Short_Ratio": None,  # LSR fehlt
            "Data_Status": {
                "components_ok": 4,  # 4/6 Komponenten verfügbar
                "components_total": 6,
                "grss_blackout": False,  # Kein Blackout
                "dvol_missing": True,
                "lsr_missing": True,
            },
        },
        "bruno:binance:analytics": {},
        "bruno:portfolio:state": {"capital_eur": 1000},
    }.get(k, {}))
    
    scorer = CompositeScorer(redis_mock)
    result = await scorer.score()
    
    # conviction sollte nicht halbiert sein
    assert result.diagnostics.get("critical_data_gap") is False
    expected_conviction = min(1.0, abs(result.composite_score) / 100.0)
    assert abs(result.conviction - expected_conviction) < 0.02


def test_grss_resilient_scoring():
    """Testet die einzelnen Scoring-Methoden für GRSS-Komponenten."""
    from app.agents.context import ContextAgent
    
    # Mock ContextAgent für Test
    context = ContextAgent(MagicMock())
    
    # Test Funding Rate Scoring
    assert context._score_funding_rate(-0.02) == 80.0  # Stark negativ → bullish
    assert context._score_funding_rate(0.02) == 50.0   # Neutral
    assert context._score_funding_rate(0.04) == 30.0   # Leicht positiv → bearish
    assert context._score_funding_rate(0.08) == 10.0    # Stark positiv → sehr bearish
    
    # Test DVOL Scoring
    assert context._score_dvol(35) == 80.0  # Niedrige Vola → bullish
    assert context._score_dvol(50) == 50.0  # Neutrale Vola
    assert context._score_dvol(70) == 30.0  # Erhöhte Vola → bearish
    assert context._score_dvol(85) == 10.0  # Sehr hohe Vola → sehr bearish
    
    # Test LSR Scoring
    assert context._score_lsr(0.8) == 80.0  # Niedriges LSR → bullish
    assert context._score_lsr(1.1) == 50.0  # Neutral
    assert context._score_lsr(1.4) == 30.0  # Erhöhtes LSR → bearish
    assert context._score_lsr(1.7) == 10.0  # Sehr hohes LSR → sehr bearish
    
    # Test OI Delta Scoring
    assert context._score_oi_delta(20) == 20.0  # Stark erhöhtes OI → bearish
    assert context._score_oi_delta(10) == 40.0  # Erhöhtes OI → leicht bearish
    assert context._score_oi_delta(-20) == 60.0  # Stark reduziertes OI → bullish
    assert context._score_oi_delta(-10) == 80.0  # Reduziertes OI → sehr bullish
    assert context._score_oi_delta(0) == 50.0   # Neutral