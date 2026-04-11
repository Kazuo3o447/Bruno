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
    
    return "".join(results) if results else "NO MATCH\n"

with open("validate_out.txt", "w", encoding="utf-8") as out:
    out.write("=== FIX-01 checks ===\n")
    out.write("grep Below VWAP:\n")
    out.write(grep("backend/app/agents/technical.py", "Below VWAP", 0, 2))
    out.write("---\n")
    out.write("grep bearish_wick:\n")
    out.write(grep("backend/app/agents/technical.py", "bearish_wick", 1, 5))
    out.write("---\n")
    out.write("grep elif rsi:\n")
    out.write(grep("backend/app/agents/technical.py", "elif rsi", 1, 3))
    out.write("---\n")
    out.write("grep abs_ta_score > 80:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "abs_ta_score > 80", 0, 15))
    out.write("---\n")
    out.write(f"test exists: {os.path.exists('backend/tests/test_composite_symmetry.py')}\n")

    out.write("\n=== FIX-02 checks ===\n")
    out.write("grep atr_ratio >:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "atr_ratio >", 0, 0))
    out.write("---\n")
    out.write("REGIME_CONFIGS:\n")
    sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
    try:
        from app.services.regime_config import REGIME_CONFIGS
        for name, cfg in REGIME_CONFIGS.items():
            out.write(f"{name}: longs={cfg.allow_longs}, shorts={cfg.allow_shorts}\n")
    except Exception as e:
        out.write(f"Error loading configs: {e}\n")

    out.write("\n=== FIX-03 checks ===\n")
    out.write("grep blend_ratio = 0.:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "blend_ratio = 0.", 0, 0))
    out.write("---\n")
    out.write("grep confluence_bonus_eligible:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "confluence_bonus_eligible", 0, 8))

    out.write("\n=== FIX-04 checks ===\n")
    try:
        c = json.load(open('backend/config.json', encoding='utf-8'))
        for k in ['LEVERAGE', 'MIN_NOTIONAL_USDT', 'MIN_NOTIONAL_USDT_LEARNING', 'MIN_RR_AFTER_FEES_LEARNING', 'SCALED_ENTRY_ENABLED', 'STRATEGY_TREND_CAPITAL_PCT', 'POSITION_SIZE_MODE']:
            out.write(f"{k}: {c.get(k)}\n")
    except Exception as e:
        out.write(f"Error reading config: {e}\n")
    out.write("---\n")
    out.write("grep math.tanh:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "math.tanh", 0, 0))
    out.write("---\n")
    out.write("grep score_mult:\n")
    out.write(grep("backend/app/services/composite_scorer.py", "score_mult", 0, 0))

    out.write("\n=== FIX-05 checks ===\n")
    try:
        c = json.load(open('backend/config.json', encoding='utf-8'))
        for k in ['TRADE_COOLDOWN_SECONDS_LEARNING', 'DISABLE_CONVICTION_HALVING_IN_LEARNING', 'DISABLE_OFI_GAP_PENALTY_IN_LEARNING', 'DISABLE_NEWS_SILENCE_VETO_IN_LEARNING', 'PHANTOM_TRADE_MIN_SCORE', 'LOG_EXPLORATION_METRICS']:
            out.write(f"{k}: {k in c}\n")
    except Exception as e:
        out.write(f"Error reading config: {e}\n")
    out.write("---\n")
    out.write("grep exploration:\n")
    out.write(grep("backend/app/agents/quant_v4.py", "bruno:exploration:metrics", 0, 0))

    out.write("\n=== FIX-06 checks ===\n")
    out.write("grep resilient:\n")
    out.write(grep("backend/app/agents/context.py", "_compute_grss_resilient", 0, 0))
    out.write("---\n")
    out.write("grep missing_critical_liquidity:\n")
    out.write(grep("backend/app/agents/context.py", "missing_critical_liquidity", 0, 0))
    out.write("---\n")
    out.write("grep Data_Status:\n")
    out.write(grep("backend/app/agents/context.py", "\"Data_Status\"", 0, 5))
