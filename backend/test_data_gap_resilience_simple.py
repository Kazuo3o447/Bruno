"""
Simple test script for BRUNO-FIX-06: Data Gap Resilience.
This runs without pytest dependency.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.composite_scorer import CompositeScorer
from app.core.config_cache import ConfigCache


async def test_partial_data_not_critical():
    """Einzelnes DVOL-Missing darf critical_data_gap nicht triggern."""
    print("Testing: Partial data should not trigger critical_data_gap...")
    
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
    
    print("✓ PASS: Partial data correctly does not trigger critical_data_gap")


async def test_grss_blackout_triggers_critical():
    """Nur bei echtem Blackout (nur 1/6 Komponenten) ist critical_data_gap aktiv."""
    print("Testing: GRSS blackout should trigger critical_data_gap...")
    
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
    
    print("✓ PASS: GRSS blackout correctly triggers critical_data_gap")


async def main():
    """Run all tests."""
    print("Running BRUNO-FIX-06 Data Gap Resilience Tests...\n")
    
    try:
        await test_partial_data_not_critical()
        await test_grss_blackout_triggers_critical()
        
        print("\n🎉 All tests passed! BRUNO-FIX-06 implementation is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())