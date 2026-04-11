"""
PROMPT 07: Paper Trading Smoke Test Script.

Validiert 4 Szenarien:
1. Trend Bull → LONG mit voller Größe
2. Trend Bear → SHORT mit voller Größe  
3. Konflikt Long-TA vs Bear-Macro → LONG mit MR-Mode (50% Sizing)
4. Pure Ranging → HOLD

Usage:
    cd backend && python scripts/smoke_test_paper.py
"""
import asyncio
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.composite_scorer import CompositeScorer, CompositeSignal


class SmokeTestRunner:
    """Führt 4 Szenarien durch und validiert erwartete Outcomes."""
    
    def __init__(self):
        self.results = []
        self.redis = AsyncMock()
        self.scorer = CompositeScorer(self.redis)
        
    def _mock_config(self, learning_mode=True):
        """Mock ConfigCache für Learning Mode."""
        return {
            "COMPOSITE_THRESHOLD_LEARNING": 8,
            "COMPOSITE_THRESHOLD_PROD": 25,
            "COMPOSITE_FLOOR_LEARNING": 8,
            "CONFLUENCE_BONUS_2OF3": -3,
            "MTF_ALIGN_BONUS": -5,
            "LEARNING_MODE_ENABLED": learning_mode,
            "RISK_PER_TRADE_PCT": 2.5,
            "LEVERAGE": 5,
            "MIN_NOTIONAL_USDT": 100,
            "MIN_NOTIONAL_USDT_LEARNING": 50,
            "MIN_RR_AFTER_FEES": 1.5,
            "MIN_RR_AFTER_FEES_LEARNING": 1.1,
            "FEE_RATE_TAKER": 0.0004,
            "FUNDING_VETO_THRESHOLD_BPS": 5,
            "FUNDING_PREDICTED_HOLD_MIN": 240,
            "FUNDING_SUBSCORE_WEIGHT": 0.05,
        }
    
    async def run_scenario_1_trend_bull(self):
        """
        Szenario 1: Trend Bull
        - TA+, Liq+, Flow+, Macro_bull
        - Erwartet: LONG mit voller Größe, mr_mode=False
        """
        self.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 30, "mtf_aligned": True},  # Stark bullish
                "trend": {"direction": "up", "strength": 0.8},
                "macro_trend": {"macro_trend": "macro_bull"},  # Confluence!
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.7,  # Bullish Flow
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 60,
                "GRSS_Score": 60,
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
            "market:funding:current": {"funding_rate": 0.0001, "funding_bps": 1},
        }.get(key, {}))
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda k, default=None: self._mock_config(True).get(k, default)
            result = await self.scorer.score()
        
        self.results.append({
            "scenario": "1. Trend Bull",
            "composite": result.composite_score,
            "direction": result.direction,
            "mr_mode": result.mr_mode,
            "should_trade": result.should_trade,
            "expected": "LONG, full size, mr_mode=False",
            "pass": result.direction == "long" and not result.mr_mode and result.should_trade,
        })
    
    async def run_scenario_2_trend_bear(self):
        """
        Szenario 2: Trend Bear
        - TA-, Liq-, Flow-, Macro_bear
        - Erwartet: SHORT mit voller Größe, mr_mode=False
        """
        self.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": -30, "mtf_aligned": True},  # Stark bearish
                "trend": {"direction": "down", "strength": 0.8},
                "macro_trend": {"macro_trend": "macro_bear"},  # Confluence!
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.8},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.3,  # Bearish Flow
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 40,
                "GRSS_Score": 40,
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
            "market:funding:current": {"funding_rate": -0.0001, "funding_bps": -1},
        }.get(key, {}))
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda k, default=None: self._mock_config(True).get(k, default)
            result = await self.scorer.score()
        
        self.results.append({
            "scenario": "2. Trend Bear",
            "composite": result.composite_score,
            "direction": result.direction,
            "mr_mode": result.mr_mode,
            "should_trade": result.should_trade,
            "expected": "SHORT, full size, mr_mode=False",
            "pass": result.direction == "short" and not result.mr_mode and result.should_trade,
        })
    
    async def run_scenario_3_conflict_mr_mode(self):
        """
        Szenario 3: Konflikt Long-TA vs Bear-Macro (Prompt 02!)
        - TA+, Liq+, Flow+ = Long, aber Macro_bear = Konflikt
        - Erwartet: LONG mit MR-Mode (50% Sizing)
        """
        self.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 25, "mtf_aligned": True},  # Bullish TA
                "trend": {"direction": "up", "strength": 0.6},
                "macro_trend": {"macro_trend": "macro_bear"},  # KONFLIKT!
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.6},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.6,  # Bullish Flow
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 45,
                "GRSS_Score": 45,
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
            "market:funding:current": {"funding_rate": 0.0001, "funding_bps": 1},
        }.get(key, {}))
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda k, default=None: self._mock_config(True).get(k, default)
            result = await self.scorer.score()
        
        self.results.append({
            "scenario": "3. Conflict (Long-TA vs Bear-Macro)",
            "composite": result.composite_score,
            "direction": result.direction,
            "mr_mode": result.mr_mode,
            "should_trade": result.should_trade,
            "expected": "LONG, 50% size (MR-Mode), mr_mode=True",
            "pass": result.direction == "long" and result.mr_mode and result.should_trade,
        })
    
    async def run_scenario_4_pure_ranging(self):
        """
        Szenario 4: Pure Ranging
        - Alle Scores ~0
        - Erwartet: HOLD (no trade)
        """
        self.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:ta:snapshot": {
                "price": 70000.0,
                "atr_14": 700.0,
                "ta_score": {"score": 5, "mtf_aligned": False},  # Schwach, nicht aligned
                "trend": {"direction": "mixed", "strength": 0.2},  # Schwacher Trend
                "macro_trend": {"macro_trend": "neutral"},  # Neutral
                "session": {"volatility_bias": 1.0},
                "mtf": {"alignment_score": 0.2},
            },
            "bruno:liq:intelligence": {
                "sweep": {"all_confirmed": False},
                "walls": [],
            },
            "bruno:quant:micro": {
                "OFI_Available": True,
                "OFI_Buy_Pressure": 0.5,  # Neutral Flow
                "price": 70000.0,
            },
            "bruno:context:grss": {
                "GRSS_Score_Raw": 50,  # Neutral
                "GRSS_Score": 50,
                "Data_Status": {"components_ok": 6, "components_total": 6},
                "Veto_Active": False,
            },
            "bruno:portfolio:state": {"capital_eur": 10000.0},
            "market:funding:current": {"funding_rate": 0.0001, "funding_bps": 1},
        }.get(key, {}))
        
        with patch('app.services.composite_scorer.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda k, default=None: self._mock_config(True).get(k, default)
            result = await self.scorer.score()
        
        self.results.append({
            "scenario": "4. Pure Ranging",
            "composite": result.composite_score,
            "direction": result.direction,
            "mr_mode": result.mr_mode,
            "should_trade": result.should_trade,
            "expected": "HOLD (no trade)",
            "pass": not result.should_trade or result.direction == "neutral",
        })
    
    def print_results(self):
        """Druckt Ergebnisse als Tabelle."""
        print("\n" + "="*100)
        print("BRUNO PAPER TRADING SMOKE TEST RESULTS")
        print("="*100)
        print(f"{'Szenario':<40} | {'Composite':<10} | {'Direction':<10} | {'MR-Mode':<8} | {'Trade':<6} | {'Status'}")
        print("-"*100)
        
        all_pass = True
        for r in self.results:
            status = "✅ PASS" if r["pass"] else "❌ FAIL"
            if not r["pass"]:
                all_pass = False
            print(
                f"{r['scenario']:<40} | "
                f"{r['composite']:<10.1f} | "
                f"{r['direction']:<10} | "
                f"{'Ja' if r['mr_mode'] else 'Nein':<8} | "
                f"{'Ja' if r['should_trade'] else 'Nein':<6} | "
                f"{status}"
            )
            print(f"  Expected: {r['expected']}")
            print()
        
        print("="*100)
        if all_pass:
            print("🎉 ALL SCENARIOS PASSED! Paper Trading Launch Ready.")
        else:
            print("⚠️  SOME SCENARIOS FAILED! Review before launch.")
        print("="*100)
        
        return all_pass
    
    async def run_all(self):
        """Führt alle Szenarien aus."""
        print("\n🚀 Starting Bruno Paper Trading Smoke Test...")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
        
        await self.run_scenario_1_trend_bull()
        await self.run_scenario_2_trend_bear()
        await self.run_scenario_3_conflict_mr_mode()
        await self.run_scenario_4_pure_ranging()
        
        return self.print_results()


async def main():
    """Hauptfunktion."""
    runner = SmokeTestRunner()
    success = await runner.run_all()
    
    # Exit code 0 bei Erfolg, 1 bei Fehler
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
