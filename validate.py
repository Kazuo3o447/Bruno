import os
import re
import sys

# Füge backend zum Pfad hinzu für Imports
sys.path.append('e:/Bruno/backend')

print('--- FIX-01 ---')
try:
    tech_py = open('e:/Bruno/backend/app/agents/technical.py', encoding='utf-8').read()
    match_vwap = re.search(r'Below VWAP.*?(?:score -= \d+)', tech_py, re.DOTALL | re.IGNORECASE)
    print('VWAP symmetrisch:', 'ranging' not in match_vwap.group() if match_vwap else 'FAIL (not found)')
    
    match_wick = re.search(r'bearish_wick.*?(?:score -= \d+)', tech_py, re.DOTALL | re.IGNORECASE)
    print('Wick symmetrisch:', 'ranging' not in match_wick.group() if match_wick else 'FAIL (not found)')
    
    match_rsi = re.search(r'elif rsi.*?score -=', tech_py, re.DOTALL | re.IGNORECASE)
    print('RSI symmetrisch:', 'ranging' not in match_rsi.group() if match_rsi else 'FAIL (not found)')
except Exception as e:
    print(f'Error reading technical.py: {e}')

try:
    comp_py = open('e:/Bruno/backend/app/services/composite_scorer.py', encoding='utf-8').read()
    print('MR-Cap symmetrisch:', 'abs_ta_score > 80' in comp_py)
except Exception as e:
    print(f'Error reading composite_scorer.py: {e}')

print('Test-Datei existiert:', os.path.exists('e:/Bruno/backend/tests/test_composite_symmetry.py'))

print('\n--- FIX-02 ---')
print('ATR-Schwellen kalibriert:', 'atr_ratio >' in comp_py and '3.5' in comp_py)
try:
    from app.services.regime_config import REGIME_CONFIGS
    print('Kein Regime blockiert alle Trades:')
    for name, cfg in REGIME_CONFIGS.items():
        blocked = not cfg.allow_longs and not cfg.allow_shorts
        status = 'BLOCKED' if blocked else 'OK'
        print(f'  {name}: longs={cfg.allow_longs}, shorts={cfg.allow_shorts} [{status}]')
except Exception as e:
    print(f'Error loading REGIME_CONFIGS: {e}')

print('\n--- FIX-03 ---')
print('Blend-Ratios reduziert:', '0.15' in comp_py and '0.05' in comp_py)
match_conf = re.search(r'confluence_bonus_eligible =.*', comp_py)
print('Confluence Gate gelockert:', ' or ' in match_conf.group() if match_conf else 'FAIL (not found)')

print('\n--- FIX-04 ---')
import json
try:
    c = json.load(open('e:/Bruno/backend/config.json', encoding='utf-8'))
    print('config.json Updates:')
    for k, expected in {
        'LEVERAGE': 5, 
        'MIN_NOTIONAL_USDT': 100, 
        'MIN_NOTIONAL_USDT_LEARNING': 50,
        'MIN_RR_AFTER_FEES_LEARNING': 1.1,
        'SCALED_ENTRY_ENABLED': False,
        'STRATEGY_TREND_CAPITAL_PCT': 0.60,
        'POSITION_SIZE_MODE': 'kelly_continuous'
    }.items():
        actual = c.get(k)
        print(f'  {k}: {actual} == {expected} -> {actual == expected}')
except Exception as e: 
    print(f'Error reading config.json: {e}')

print('Kelly-Funktion im Sizing:', 'math.tanh' in comp_py)
print('Score-Buckets entfernt:', 'score_mult' not in comp_py)

print('\n--- FIX-05 ---')
try:
    print('Learning-Mode Flags in config:')
    for flag in [
        'TRADE_COOLDOWN_SECONDS_LEARNING', 
        'DISABLE_CONVICTION_HALVING_IN_LEARNING',
        'DISABLE_OFI_GAP_PENALTY_IN_LEARNING',
        'DISABLE_NEWS_SILENCE_VETO_IN_LEARNING',
        'PHANTOM_TRADE_MIN_SCORE',
        'LOG_EXPLORATION_METRICS'
    ]:
        print(f'  {flag}: {flag in c}')
except Exception as e: 
    print(e)
    
try:
    quant_py = open('e:/Bruno/backend/app/agents/quant_v4.py', encoding='utf-8').read()
    print('Exploration Metrics Code existiert:', 'bruno:exploration:metrics' in quant_py)
except Exception as e:
    print(f'Error reading quant_v4.py: {e}')

print('\n--- FIX-06 ---')
try:
    context_py = open('e:/Bruno/backend/app/agents/context.py', encoding='utf-8').read()
    print('_compute_grss_resilient existiert:', '_compute_grss_resilient' in context_py)
    print('missing_critical_liquidity entfernt:', 'missing_critical_liquidity' not in context_py)
    print('Data_Status Dict im Payload:', '"Data_Status": {' in context_py)
except Exception as e:
    print(f'Error reading context.py: {e}')
