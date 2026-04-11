import os
import sys
import subprocess
import json

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output

print("=== FIX-01 checks ===")
print("grep Below VWAP:\n", run("powershell -Command \"Select-String -Path backend/app/agents/technical.py -Pattern 'Below VWAP' -Context 0,2\""))
print("grep bearish_wick:\n", run("powershell -Command \"Select-String -Path backend/app/agents/technical.py -Pattern 'bearish_wick' -Context 1,5\""))
print("grep elif rsi:\n", run("powershell -Command \"Select-String -Path backend/app/agents/technical.py -Pattern 'elif rsi' -Context 1,3\""))
print("grep abs_ta_score > 80:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'abs_ta_score > 80' -Context 0,15\""))
print("test exists:\n", os.path.exists('backend/tests/test_composite_symmetry.py'))

print("\n=== FIX-02 checks ===")
print("grep atr_ratio >:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'atr_ratio >'\""))
print("REGIME_CONFIGS:")
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
try:
    from app.services.regime_config import REGIME_CONFIGS
    for name, cfg in REGIME_CONFIGS.items():
        print(f"{name}: longs={cfg.allow_longs}, shorts={cfg.allow_shorts}")
except Exception as e:
    print(f"Error loading configs: {e}")

print("\n=== FIX-03 checks ===")
print("grep blend_ratio = 0:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'blend_ratio = 0'\""))
print("grep confluence_bonus_eligible:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'confluence_bonus_eligible' -Context 0,8\""))

print("\n=== FIX-04 checks ===")
try:
    c = json.load(open('backend/config.json'))
    for k in ['LEVERAGE', 'MIN_NOTIONAL_USDT', 'MIN_NOTIONAL_USDT_LEARNING', 'MIN_RR_AFTER_FEES_LEARNING', 'SCALED_ENTRY_ENABLED', 'STRATEGY_TREND_CAPITAL_PCT', 'POSITION_SIZE_MODE']:
        print(f"{k}: {c.get(k)}")
except Exception as e:
    print(f"Error reading config: {e}")
print("grep math.tanh:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'tanh'\""))
print("grep score_mult:\n", run("powershell -Command \"Select-String -Path backend/app/services/composite_scorer.py -Pattern 'score_mult'\""))

print("\n=== FIX-05 checks ===")
try:
    c = json.load(open('backend/config.json'))
    for k in ['TRADE_COOLDOWN_SECONDS_LEARNING', 'DISABLE_CONVICTION_HALVING_IN_LEARNING', 'DISABLE_OFI_GAP_PENALTY_IN_LEARNING', 'DISABLE_NEWS_SILENCE_VETO_IN_LEARNING', 'PHANTOM_TRADE_MIN_SCORE', 'LOG_EXPLORATION_METRICS']:
        print(f"{k}: {k in c}")
except Exception as e:
    print(f"Error reading config: {e}")
print("grep exploration:\n", run("powershell -Command \"Select-String -Path backend/app/agents/quant_v4.py -Pattern 'bruno:exploration:metrics'\""))

print("\n=== FIX-06 checks ===")
print("grep resilient:\n", run("powershell -Command \"Select-String -Path backend/app/agents/context.py -Pattern '_compute_grss_resilient'\""))
print("grep missing_critical_liquidity:\n", run("powershell -Command \"Select-String -Path backend/app/agents/context.py -Pattern 'missing_critical_liquidity'\""))
print("grep Data_Status:\n", run("powershell -Command \"Select-String -Path backend/app/agents/context.py -Pattern 'Data_Status' -Context 0,5\""))
