"""
PROMPT 03: Composite Reform für Trainingsdaten-Generierung Tests.

Test-Suite für:
- Dominant signal wins (statt summieren-und-cancellen)
- Konfidenz-basierter dynamischer Threshold
- MR-Modus asymmetrische Gewichtung
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestDominantSignalWins:
    """Test-Klasse für 'Dominant Signal Wins' Logik."""
    
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
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_THRESHOLD_PROD": 25,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
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
    async def test_dominant_signal_wins_over_conflict(self, composite_scorer, mock_redis):
        """
        Test: Wenn TA+12.5, Liq-20, Flow+19.4
        Erwartet: Liq dominiert (stärkstes Signal), TA und Flow werden auf 50% reduziert.
        - Liq: -20 * 100% = -20
        - TA: +12.5 * 50% = +6.25  (reduziert, da gegen dominant)
        - Flow: +19.4 * 50% = +9.7 (reduziert, da gegen dominant)
        
        Vorher (alte Logik): 12.5 - 20 + 19.4 = 11.9 (schwach positiv, evtl. HOLD)
        Nachher (neue Logik): 6.25 - 20 + 9.7 = -4.05 (klar negativ, SHORT)
        """
        # Setup: TA bullish, Liq stark bearish, Flow bullish
        mock_redis.get_cache.side_effect = lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 12.5, "mtf_aligned": True},  # Bullish aber schwach
                "trend": {"direction": "up", "strength": 0.4},
                "macro_trend": {"macro_trend": "neutral"},  # Kein Macro-Konflikt
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.6},
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
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Der starke Liq-Score (-20) sollte dominieren
        # TA (+12.5) und Flow (+19.4) sind gegen die Richtung, werden auf 50% reduziert
        # Erwartetes Composite sollte negativ sein (SHORT)
        assert result.direction == "short", f"Direction sollte SHORT sein, got {result.direction} with score {result.composite_score}"
        assert any("Conflict resolved" in s for s in result.signals_active), "Signal sollte 'Conflict resolved' enthalten"
    
    @pytest.mark.asyncio
    async def test_no_conflict_all_aligned(self, composite_scorer, mock_redis):
        """
        Test: Wenn alle Sub-Scores in gleiche Richtung zeigen, keine Reduktion.
        """
        mock_redis.get_cache.side_effect = lambda key: {
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
                "OFI_Buy_Pressure": 0.7,  # Bullish
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 55,
                "GRSS_Score": 55,
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
        }.get(key, {})
        
        result = await composite_scorer.score()
        
        # Alle Signale aligned, keine Konflikt-Resolution nötig
        assert result.direction == "long", f"Direction sollte LONG sein, got {result.direction}"
        assert not any("Conflict resolved" in s for s in result.signals_active), "Kein 'Conflict resolved' wenn alle aligned"


class TestConfluenceThresholdBonus:
    """Test-Klasse für Konfidenz-basierte Threshold-Bonuses."""
    
    def test_confluence_2of3_lowers_threshold(self):
        """
        Test: Wenn ≥2 Sub-Scores aligned, sinkt Threshold um -3.
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
            }.get(key, default)
            
            # Mit 2 aligned Sub-Scores
            threshold_with_confluence = scorer._get_threshold(
                atr=700, price=70000, macro_data={},
                confluence_aligned=2, mtf_aligned=False
            )
            
            # Ohne aligned Sub-Scores
            threshold_without = scorer._get_threshold(
                atr=700, price=70000, macro_data={},
                confluence_aligned=0, mtf_aligned=False
            )
            
            # Erwartung: Threshold mit Confluence sollte niedriger sein (8 - 3 = 5, aber floor ist 8)
            assert threshold_with_confluence <= threshold_without, \
                f"Threshold mit Confluence ({threshold_with_confluence}) sollte <= ohne ({threshold_without}) sein"
    
    def test_mtf_align_lowers_threshold(self):
        """
        Test: Wenn MTF aligned, sinkt Threshold um -5.
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
            }.get(key, default)
            
            # Mit MTF aligned
            threshold_with_mtf = scorer._get_threshold(
                atr=700, price=70000, macro_data={},
                confluence_aligned=0, mtf_aligned=True
            )
            
            # Ohne MTF aligned
            threshold_without = scorer._get_threshold(
                atr=700, price=70000, macro_data={},
                confluence_aligned=0, mtf_aligned=False
            )
            
            # Erwartung: Threshold mit MTF sollte niedriger sein (aber nicht unter 8)
            assert threshold_with_mtf <= threshold_without, \
                f"Threshold mit MTF ({threshold_with_mtf}) sollte <= ohne ({threshold_without}) sein"
    
    def test_hard_floor_learning_mode(self):
        """
        Test: Threshold sinkt nie unter 8 in Learning Mode (hard floor).
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
            }.get(key, default)
            
            # Mit MTF + Confluence (sollte -8 reduzieren, aber floor ist 8)
            threshold = scorer._get_threshold(
                atr=700, price=70000, macro_data={},
                confluence_aligned=3, mtf_aligned=True
            )
            
            # Erwartung: Nie unter 8
            assert threshold >= 8, f"Threshold ({threshold}) sollte nie unter 8 sinken"


class TestMRModeAsymmetricWeights:
    """Test-Klasse für MR-Modus asymmetrische Gewichtung."""
    
    def test_mr_mode_asymmetric_weights(self):
        """
        Test: Im MR-Modus hat Liq+Flow je 30%, TA 25%, Macro 15%.
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        # MR-Modus Gewichtung
        weights = scorer._get_weights("trending_bull", trend_strength=0.7, mr_mode=True)
        
        assert weights["liq"] == 0.30, f"Liq-Gewichtung sollte 0.30 sein, got {weights['liq']}"
        assert weights["flow"] == 0.30, f"Flow-Gewichtung sollte 0.30 sein, got {weights['flow']}"
        assert weights["ta"] == 0.25, f"TA-Gewichtung sollte 0.25 sein, got {weights['ta']}"
        assert weights["macro"] == 0.15, f"Macro-Gewichtung sollte 0.15 sein, got {weights['macro']}"
    
    def test_normal_mode_standard_weights(self):
        """
        Test: Im normalen Modus werden Standard-Gewichtungen verwendet.
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        # Normale Gewichtung
        weights = scorer._get_weights("trending_bull", trend_strength=0.7, mr_mode=False)
        
        # Trending-Preset: TA dominiert
        assert weights["ta"] > weights["liq"], "TA sollte in Trending dominieren"
        assert weights["ta"] > weights["flow"], "TA sollte in Trending dominieren"


class TestCompositeThresholdValues:
    """Test-Klasse für neue Threshold-Werte."""
    
    def test_learning_threshold_is_8(self):
        """
        Test: Learning Mode Threshold ist 8 (nicht 15).
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_LEARNING": 8,
                "COMPOSITE_FLOOR_LEARNING": 8,
                "CONFLUENCE_BONUS_2OF3": -3,
                "MTF_ALIGN_BONUS": -5,
                "LEARNING_MODE_ENABLED": True,
            }.get(key, default)
            
            threshold = scorer._get_threshold(
                atr=0, price=0, macro_data={},
                confluence_aligned=0, mtf_aligned=False
            )
            
            assert threshold == 8, f"Learning Threshold sollte 8 sein, got {threshold}"
    
    def test_prod_threshold_is_25(self):
        """
        Test: Prod Mode Threshold ist 25 (nicht 40).
        """
        from app.services.composite_scorer import CompositeScorer
        
        scorer = CompositeScorer(MagicMock())
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "COMPOSITE_THRESHOLD_PROD": 25,
                "LEARNING_MODE_ENABLED": False,
            }.get(key, default)
            
            threshold = scorer._get_threshold(
                atr=0, price=0, macro_data={},
                confluence_aligned=0, mtf_aligned=False
            )
            
            assert threshold == 25, f"Prod Threshold sollte 25 sein, got {threshold}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
