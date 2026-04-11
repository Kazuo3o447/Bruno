"""
PROMPT 05: Funding Rate Filter Tests.

Test-Suite für:
- Funding Score Berechnung (Range -10..+10)
- Soft-Veto bei hohen Funding Rates
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestFundingScoreCalculation:
    """Test-Klasse für Funding Score Berechnung."""
    
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
        return scorer
    
    @pytest.mark.asyncio
    async def test_funding_score_negative_funding_favors_long(self, composite_scorer, mock_redis):
        """
        Test: Negativer Funding (-0.03%) → Shorts bezahlen Longs → Long-Favorit.
        Erwartet: funding_score > 0 für Long-Trades
        """
        # Mock: Negativer Funding
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": -0.0003,  # -0.03% = -3 bps
            "funding_bps": -3,
        })
        
        funding_score = await composite_scorer._score_funding(direction_hint="long")
        
        # Negativer Funding = Shorts zahlen Longs = Gut für Long
        assert funding_score > 0, f"Funding score für Long bei negativem Funding sollte > 0 sein, got {funding_score}"
        assert funding_score >= 5, f"Bei -3bps sollte Score mindestens 5 sein, got {funding_score}"
    
    @pytest.mark.asyncio
    async def test_funding_score_positive_funding_penalizes_long(self, composite_scorer, mock_redis):
        """
        Test: Positiver Funding > 0.03% → Long zahlt teuer → Negativer Score.
        Erwartet: funding_score = -5 für Long bei Funding > 0.03%
        """
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": 0.0004,  # 0.04% = 4 bps
            "funding_bps": 4,
        })
        
        funding_score = await composite_scorer._score_funding(direction_hint="long")
        
        # Positiver Funding = Longs zahlen = Schlecht für Long
        assert funding_score < 0, f"Funding score für Long bei positivem Funding sollte < 0 sein, got {funding_score}"
        assert funding_score == -5, f"Bei 4bps sollte Score -5 sein, got {funding_score}"
    
    @pytest.mark.asyncio
    async def test_funding_score_high_positive_penalizes_long_more(self, composite_scorer, mock_redis):
        """
        Test: Funding > 0.05% → Stärkere Penalty (-8).
        """
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": 0.0006,  # 0.06% = 6 bps
            "funding_bps": 6,
        })
        
        funding_score = await composite_scorer._score_funding(direction_hint="long")
        
        assert funding_score == -8, f"Bei 6bps sollte Score -8 sein, got {funding_score}"
    
    @pytest.mark.asyncio
    async def test_funding_score_symmetric_for_short(self, composite_scorer, mock_redis):
        """
        Test: Symmetrie für Short-Trades.
        - Negativer Funding = teuer für Short
        - Positiver Funding = gut für Short
        """
        # Positiver Funding = Gut für Short
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": 0.0003,  # 0.03% = 3 bps
            "funding_bps": 3,
        })
        
        score_short = await composite_scorer._score_funding(direction_hint="short")
        assert score_short > 0, f"Kurzes bei positivem Funding sollte positiv sein, got {score_short}"
        
        # Negativer Funding = Teuer für Short
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": -0.0004,  # -0.04% = -4 bps
            "funding_bps": -4,
        })
        
        score_short_negative = await composite_scorer._score_funding(direction_hint="short")
        assert score_short_negative < 0, f"Kurzes bei negativem Funding sollte negativ sein, got {score_short_negative}"
    
    @pytest.mark.asyncio
    async def test_funding_score_range_limits(self, composite_scorer, mock_redis):
        """
        Test: Funding Score ist immer im Bereich -10..+10.
        """
        # Extrem hoher Funding
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": 0.001,  # 0.1% = 10 bps
            "funding_bps": 10,
        })
        
        score = await composite_scorer._score_funding(direction_hint="long")
        assert -10 <= score <= 10, f"Score sollte zwischen -10 und 10 sein, got {score}"
    
    @pytest.mark.asyncio
    async def test_funding_score_no_data(self, composite_scorer, mock_redis):
        """
        Test: Bei fehlenden Daten → Score = 0.
        """
        mock_redis.get_cache = AsyncMock(return_value={})
        
        score = await composite_scorer._score_funding(direction_hint="long")
        assert score == 0, f"Bei fehlenden Daten sollte Score 0 sein, got {score}"
    
    @pytest.mark.asyncio
    async def test_funding_score_neutral_low_funding(self, composite_scorer, mock_redis):
        """
        Test: Niedriger Funding (unter 0.03%) → Neutrales Scoring.
        """
        mock_redis.get_cache = AsyncMock(return_value={
            "funding_rate": 0.0001,  # 0.01% = 1 bps
            "funding_bps": 1,
        })
        
        score = await composite_scorer._score_funding(direction_hint="long")
        assert score == 0, f"Bei niedrigem Funding sollte Score 0 sein, got {score}"


class TestFundingSoftVeto:
    """Test-Klasse für Funding Soft-Veto (Threshold +3)."""
    
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
        return scorer
    
    @pytest.mark.asyncio
    async def test_funding_headwind_warning_increases_threshold(self, composite_scorer, mock_redis):
        """
        Test: Wenn |funding| > 0.05% UND Richtung gegen Funding → Threshold +3.
        
        Dies ist ein Integrationstest der score() Methode mit Funding-Soft-Veto.
        """
        from app.services.composite_scorer import CompositeSignal, ConfigCache
        
        # Mock Funding: Hoher positiver Funding (0.06% = 6 bps)
        mock_redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 20, "mtf_aligned": True},
                "trend": {"direction": "up", "strength": 0.6},
                "macro_trend": {"macro_trend": "neutral"},
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
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
            "market:funding:current": {
                "funding_rate": 0.0006,  # 0.06% = 6 bps (> 5 bps threshold)
                "funding_bps": 6,
                "updated_at": "2026-04-11T10:00:00+00:00",
            },
        }.get(key, {}))
        
        with patch.object(ConfigCache, 'get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
                "FUNDING_VETO_THRESHOLD_BPS": 5,  # 0.05%
                "FUNDING_PREDICTED_HOLD_MIN": 240,
                "RISK_PER_TRADE_PCT": 2.5,
                "LEVERAGE": 5,
                "MIN_NOTIONAL_USDT": 100,
                "MIN_NOTIONAL_USDT_LEARNING": 50,
                "MIN_RR_AFTER_FEES": 1.5,
                "MIN_RR_AFTER_FEES_LEARNING": 1.1,
                "FEE_RATE_TAKER": 0.0004,
            }.get(key, default)
            
            result = await composite_scorer.score()
            
            # Bei Long-Trade mit positivem Funding > 0.05% sollte Soft-Veto aktiv sein
            if result.direction == "long":
                assert any("FUNDING_HEADWIND_WARNING" in s for s in result.signals_active), \
                    f"Sollte FUNDING_HEADWIND_WARNING enthalten, signals: {result.signals_active}"


class TestFundingMonitor:
    """Test-Klasse für FundingMonitor Service."""
    
    @pytest.fixture
    def mock_redis(self):
        """Erstellt einen gemockten Redis-Client."""
        redis = MagicMock()
        redis.get_cache = AsyncMock()
        redis.set_cache = AsyncMock()
        return redis
    
    @pytest.fixture
    def mock_exchange(self):
        """Erstellt einen gemockten Exchange-Client."""
        exchange = MagicMock()
        exchange.bybit = MagicMock()
        return exchange
    
    @pytest.fixture
    def funding_monitor(self, mock_redis, mock_exchange):
        """Erstellt einen FundingMonitor."""
        from app.services.funding_monitor import FundingMonitor
        return FundingMonitor(mock_redis, mock_exchange)
    
    @pytest.mark.asyncio
    async def test_fetch_and_persist_funding(self, funding_monitor, mock_redis, mock_exchange):
        """
        Test: Funding-Daten werden korrekt geholt und in Redis persistiert.
        """
        # Mock API Response
        mock_exchange.bybit.v5_get_market_funding_history = AsyncMock(return_value={
            'result': {
                'list': [
                    {
                        'fundingRate': '0.0001',  # 0.01%
                        'fundingRateTimestamp': '1712832000000',
                        'predictedFundingRate': '0.0002',
                    },
                    {
                        'fundingRate': '0.00015',
                        'fundingRateTimestamp': '1712803200000',
                    },
                ]
            }
        })
        
        await funding_monitor._fetch_and_persist_funding()
        
        # Verify Redis persistence
        assert mock_redis.set_cache.call_count >= 3  # current, 8h_avg, 24h_avg
        
        # Check current funding
        current_call = None
        for call in mock_redis.set_cache.call_args_list:
            if call[0][0] == "market:funding:current":
                current_call = call
                break
        
        assert current_call is not None
        assert current_call[0][1]["funding_rate"] == 0.0001
        assert current_call[0][1]["funding_bps"] == 1.0
    
    @pytest.mark.asyncio
    async def test_get_funding_score_params(self, funding_monitor, mock_redis):
        """
        Test: get_funding_score_params gibt alle benötigten Werte zurück.
        """
        mock_redis.get_cache = AsyncMock(side_effect=lambda key: {
            "market:funding:current": {"funding_rate": 0.0003, "funding_bps": 3},
            "market:funding:8h_avg": {"avg_rate": 0.0002, "avg_bps": 2},
            "market:funding:24h_avg": {"avg_rate": 0.00025, "avg_bps": 2.5},
            "market:funding:predicted_next": {"predicted_rate": 0.0004, "predicted_bps": 4},
        }.get(key))
        
        params = await funding_monitor.get_funding_score_params()
        
        assert "funding_rate" in params
        assert "avg_8h" in params
        assert "avg_24h" in params
        assert "predicted_next" in params
        assert params["funding_rate"] == 0.0003


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
