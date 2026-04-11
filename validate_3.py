import os
import sys
import json

def grep(filepath, search_str, before=0, after=0):
    if not os.path.exists(filepath):
        return f"File not found: {filepath}"
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    results = []
    for i, line in enumerate(lines):
        if search_str in line:
            start = max(0, i - before)
            end = min(len(lines), i + after + 1)
            results.append("".join(lines[start:end]))
    
    return "".join(results) if results else "NO MATCH"

print("=== FIX-01 checks ===")
print("grep Below VWAP:")
print(grep("backend/app/agents/technical.py", "Below VWAP", 0, 2))
print("---")
print("grep bearish_wick:")
print(grep("backend/app/agents/technical.py", "bearish_wick", 1, 5))
print("---")
print("grep elif rsi:")
print(grep("backend/app/agents/technical.py", "elif rsi", 1, 3))
print("---")
print("grep abs_ta_score > 80:")
print(grep("backend/app/services/composite_scorer.py", "abs_ta_score > 80", 0, 15))
print("---")
print("test exists:", os.path.exists('backend/tests/test_composite_symmetry.py'))

print("\n=== FIX-02 checks ===")
print("grep atr_ratio >:")
print(grep("backend/app/services/composite_scorer.py", "atr_ratio >", 0, 0))
print("---")
print("REGIME_CONFIGS:")
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
try:
    from app.services.regime_config import REGIME_CONFIGS
    for name, cfg in REGIME_CONFIGS.items():
        print(f"{name}: longs={cfg.allow_longs}, shorts={cfg.allow_shorts}")
except Exception as e:
    print(f"Error loading configs: {e}")

print("\n=== FIX-03 checks ===")
print("grep blend_ratio = 0.:")
print(grep("backend/app/services/composite_scorer.py", "blend_ratio = 0.", 0, 0))
print("---")
print("grep confluence_bonus_eligible:")
print(grep("backend/app/services/composite_scorer.py", "confluence_bonus_eligible", 0, 8))

print("\n=== FIX-04 checks ===")
try:
    c = json.load(open('backend/config.json', encoding='utf-8'))
    for k in ['LEVERAGE', 'MIN_NOTIONAL_USDT', 'MIN_NOTIONAL_USDT_LEARNING', 'MIN_RR_AFTER_FEES_LEARNING', 'SCALED_ENTRY_ENABLED', 'STRATEGY_TREND_CAPITAL_PCT', 'POSITION_SIZE_MODE']:
        print(f"{k}: {c.get(k)}")
except Exception as e:
    print(f"Error reading config: {e}")
print("---")
print("grep math.tanh:")
print(grep("backend/app/services/composite_scorer.py", "math.tanh", 0, 0))
print("---")
print("grep score_mult:")
print(grep("backend/app/services/composite_scorer.py", "score_mult", 0, 0))

print("\n=== FIX-05 checks ===")
try:
    c = json.load(open('backend/config.json', encoding='utf-8'))
    for k in ['TRADE_COOLDOWN_SECONDS_LEARNING', 'DISABLE_CONVICTION_HALVING_IN_LEARNING', 'DISABLE_OFI_GAP_PENALTY_IN_LEARNING', 'DISABLE_NEWS_SILENCE_VETO_IN_LEARNING', 'PHANTOM_TRADE_MIN_SCORE', 'LOG_EXPLORATION_METRICS']:
        print(f"{k}: {k in c}")
except Exception as e:
    print(f"Error reading config: {e}")
print("---")
print("grep exploration:")
print(grep("backend/app/agents/quant_v4.py", "bruno:exploration:metrics", 0, 0))

print("\n=== FIX-06 checks ===")
print("grep resilient:")
print(grep("backend/app/agents/context.py", "_compute_grss_resilient", 0, 0))
print("---")
print("grep missing_critical_liquidity:")
print(grep("backend/app/agents/context.py", "missing_critical_liquidity", 0, 0))
print("---")
print("grep Data_Status:")
print(grep("backend/app/agents/context.py", "\"Data_Status\"", 0, 5))
