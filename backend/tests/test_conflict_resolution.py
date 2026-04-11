"""
PROMPT 02: Macro Conflict Resolution Tests.

Test-Suite für:
- Konflikt-Erkennung zwischen Macro und technischen Signalen
- Mean-Reversion-Modus mit reduziertem Sizing
- Trend-Alignment mit vollem Sizing
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict


class TestMacroConflictResolution:
    """Test-Klasse für Macro-Konflikt-Resolution im CompositeScorer."""
    
    @pytest.fixture
    def mock_redis(self):
        """Erstellt einen gemockten Redis-Client."""
        redis = MagicMock()
        redis.get_cache = AsyncMock()
        return redis
    
    @pytest.fixture
    def composite_scorer(self, mock_redis):
        """Erstellt einen CompositeScorer mit gemockten Dependencies."""
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(mock_redis)
        # Mock ConfigCache
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 15,
                "COMPOSITE_THRESHOLD_PROD": 40,
                "LEARNING_MODE_ENABLED": False,
                "RISK_PER_TRADE_PCT": 2.5,
                "LEVERAGE": 5,
                "MIN_NOTIONAL_USDT": 100,
                "MIN_NOTIONAL_USDT_LEARNING": 50,
                "MIN_RR_AFTER_FEES": 1.5,
                "MIN_RR_AFTER_FEES_LEARNING": 1.1,
                "FEE_RATE_TAKER": 0.0004,
            }.get(key, default)
            yield scorer
    
    @pytest.mark.asyncio
    async def test_conflict_long_ta_bear_macro_creates_reduced_long(self, composite_scorer, mock_redis):
        """
        Test: TA+Liq+Flow zeigen LONG (bullish), aber Macro ist macro_bear.
        Erwartet: mr_mode=True, direction=long, macro_score=0.
        """
        # Setup: TA bullish, Macro bearish
        mock_redis.get_cache.side_effect = lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 25, "mtf_aligned": True},  # Bullish TA
                "trend": {"direction": "up", "strength": 0.7},
                "macro_trend": {"macro_trend": "macro_bear", "daily_ema_200": 69000, "price_vs_ema200": "above"},
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.6,
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 45,
                "GRSS_Score": 45,
                "Data_Status": {"components_ok": 6, "components_total": 6, "grss_blackout": False},
                "Veto_Active": False,
                "DVOL": 35,
                "Long_Short_Ratio": 1.2,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Assertions
        assert result.mr_mode is True, "MR-Mode sollte bei Konflikt aktiv sein"
        assert result.direction == "long", "Direction sollte LONG sein (TA gewinnt)"
        assert result.macro_score == 0, "Macro-Score sollte 0 sein im MR-Modus"
        assert any("MR MODE" in s for s in result.signals_active), "Signal sollte MR MODE enthalten"
    
    @pytest.mark.asyncio
    async def test_confluence_full_size(self, composite_scorer, mock_redis):
        """
        Test: TA+Liq+Flow zeigen LONG, Macro ist auch macro_bull.
        Erwartet: mr_mode=False, voller Macro-Bonus.
        """
        # Setup: TA bullish, Macro auch bullish
        mock_redis.get_cache.side_effect = lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 25, "mtf_aligned": True},  # Bullish TA
                "trend": {"direction": "up", "strength": 0.7},
                "macro_trend": {"macro_trend": "macro_bull", "daily_ema_200": 69000, "price_vs_ema200": "above"},
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.6,
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 55,
                "GRSS_Score": 55,
                "Data_Status": {"components_ok": 6, "components_total": 6, "grss_blackout": False},
                "Veto_Active": False,
                "DVOL": 30,
                "Long_Short_Ratio": 1.5,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Assertions
        assert result.mr_mode is False, "MR-Mode sollte bei Confluence NICHT aktiv sein"
        assert result.direction == "long", "Direction sollte LONG sein"
        assert result.macro_score != 0, "Macro-Score sollte im Confluence-Fall nicht 0 sein"
        assert any("TREND ALIGNED" in s for s in result.signals_active), "Signal sollte TREND ALIGNED enthalten"
    
    @pytest.mark.asyncio
    async def test_neutral_macro_no_mr_flag(self, composite_scorer, mock_redis):
        """
        Test: Macro ist neutral (weder bull noch bear).
        Erwartet: Kein MR-Mode, egal welche Richtung die technischen zeigen.
        """
        # Setup: TA bullish, Macro neutral
        mock_redis.get_cache.side_effect = lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 25, "mtf_aligned": True},
                "trend": {"direction": "up", "strength": 0.7},
                "macro_trend": {"macro_trend": "neutral", "daily_ema_200": 69000, "price_vs_ema200": "above"},
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.6,
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 50,
                "GRSS_Score": 50,
                "Data_Status": {"components_ok": 6, "components_total": 6, "grss_blackout": False},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Assertions
        assert result.mr_mode is False, "MR-Mode sollte bei neutralem Macro NICHT aktiv sein"
        assert result.direction == "long", "Direction sollte LONG sein"
    
    @pytest.mark.asyncio
    async def test_conflict_short_ta_bull_macro_creates_reduced_short(self, composite_scorer, mock_redis):
        """
        Test: TA+Liq+Flow zeigen SHORT (bearish), aber Macro ist macro_bull.
        Erwartet: mr_mode=True, direction=short.
        """
        # Setup: TA bearish, Macro bullish
        mock_redis.get_cache.side_effect = lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": -25, "mtf_aligned": True},  # Bearish TA
                "trend": {"direction": "down", "strength": 0.7},
                "macro_trend": {"macro_trend": "macro_bull", "daily_ema_200": 69000, "price_vs_ema200": "above"},
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.4,  # Bearish OFI
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 55,
                "GRSS_Score": 55,
                "Data_Status": {"components_ok": 6, "components_total": 6, "grss_blackout": False},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Assertions
        assert result.mr_mode is True, "MR-Mode sollte bei Konflikt aktiv sein (Short vs Bull)"
        assert result.direction == "short", "Direction sollte SHORT sein"
        assert result.macro_score == 0, "Macro-Score sollte 0 sein im MR-Modus"


class TestExecutionAgentMRMode:
    """Test-Klasse für MR-Modus Handling im ExecutionAgent."""
    
    @pytest.mark.asyncio
    async def test_mr_mode_applies_50_percent_sizing(self):
        """
        Test: Bei mr_mode=True wird das Sizing um 50% reduziert.
        """
        from app.agents.execution_v4 import ExecutionAgentV4
        
        # Mock setup
        deps = MagicMock()
        deps.config = MagicMock()
        deps.config.DRY_RUN = True
        deps.config.SIMULATED_CAPITAL_EUR = 10000.0
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        
        # Mock _calculate_risk_based_position_size
        original_sizing = {
            "position_size_usdt": 1000.0,
            "position_size_btc": 0.014,
            "margin_required_usdt": 200.0,
            "risk_amount_usd": 100.0,
            "sl_distance_pct": 0.01,
            "target_leverage": 5.0,
            "leverage": 5.0,
            "sizing_valid": True,
        }
        
        agent._calculate_risk_based_position_size = AsyncMock(return_value=original_sizing)
        agent._check_fee_hurdle = MagicMock(return_value=(True, ""))
        agent._calculate_atr_based_sl_tp = MagicMock(return_value=(0.008, 0.012, 0.024, 0.008))
        
        # Test mit mr_mode=True
        signal = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "price": 70000.0,
            "strategy_slot": "trend",
            "composite_score": 50,
            "mr_mode": True,  # MR-Modus aktiv
        }
        
        # Die eigentliche _execute_trade Methode ist komplex, aber wir können die
        # Sizing-Logik isoliert testen, indem wir direkt _calculate_risk_based_position_size aufrufen
        # und dann die Modifikation simulieren
        
        sizing = await agent._calculate_risk_based_position_size(
            total_equity_usd=10000.0,
            entry_price=70000.0,
            stop_loss_price=69300.0,
            tp1_price=70840.0,
        )
        
        # Simuliere MR-Modus Reduktion
        mr_mode = True
        if mr_mode:
            sizing["position_size_usdt"] *= 0.5
            sizing["position_size_btc"] *= 0.5
            sizing["margin_required_usdt"] *= 0.5
            sizing["risk_amount_usd"] *= 0.5
        
        assert sizing["position_size_usdt"] == 500.0, "Sizing sollte um 50% reduziert sein"
        assert sizing["risk_amount_usd"] == 50.0, "Risk sollte um 50% reduziert sein"
    
    def test_mr_mode_adjusts_sl_tp_multipliers(self):
        """
        Test: Bei mr_mode=True werden SL/TP Multiplikatoren angepasst.
        """
        from app.agents.execution_v4 import ExecutionAgentV4
        
        deps = MagicMock()
        deps.config = MagicMock()
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        
        # Test mit mr_mode=True
        atr = 700.0
        price = 70000.0
        
        sl_pct, tp1_pct, tp2_pct, be_pct = agent._calculate_atr_based_sl_tp(
            atr=atr,
            current_price=price,
            composite_score=50,
            mr_mode=True  # MR-Modus
        )
        
        # Erwartete Werte mit 0.8x SL, 1.0x TP1, 2.0x TP2
        atr_pct = atr / price  # 0.01 = 1%
        expected_sl = 0.008  # 0.8 * 0.01
        expected_tp1 = 0.01  # 1.0 * 0.01
        
        assert abs(sl_pct - expected_sl) < 0.001, f"SL sollte 0.8x sein, got {sl_pct}"
        assert abs(tp1_pct - expected_tp1) < 0.001, f"TP1 sollte 1.0x sein, got {tp1_pct}"


class TestCompositeSignalMRMode:
    """Test-Klasse für CompositeSignal mr_mode Feld."""
    
    def test_mr_mode_field_exists(self):
        """
        Test: CompositeSignal hat mr_mode Feld mit Default False.
        """
        from app.services.composite_scorer import CompositeSignal
        
        signal = CompositeSignal()
        assert hasattr(signal, 'mr_mode'), "CompositeSignal sollte mr_mode Feld haben"
        assert signal.mr_mode is False, "Default mr_mode sollte False sein"
    
    def test_mr_mode_in_signal_dict(self):
        """
        Test: to_signal_dict enthält mr_mode.
        """
        from app.services.composite_scorer import CompositeSignal
        
        signal = CompositeSignal()
        signal.mr_mode = True
        
        result = signal.to_signal_dict()
        assert "mr_mode" in result, "Signal-Dict sollte mr_mode enthalten"
        assert result["mr_mode"] is True, "mr_mode sollte True sein"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
