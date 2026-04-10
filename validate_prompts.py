#!/usr/bin/env python3
"""
Validierungsskript für Bruno V4 Refactoring Prompts 1-8
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_imports():
    """Teste alle importierten Module"""
    errors = []
    
    try:
        from app.services.composite_scorer import CompositeScorer, CompositeSignal
        print("✓ CompositeScorer import OK")
    except Exception as e:
        errors.append(f"✗ CompositeScorer import failed: {e}")
    
    try:
        from app.agents.quant_v4 import QuantAgentV4
        print("✓ QuantAgentV4 import OK")
    except Exception as e:
        errors.append(f"✗ QuantAgentV4 import failed: {e}")
    
    try:
        from app.agents.execution_v4 import ExecutionAgentV4
        print("✓ ExecutionAgentV4 import OK")
    except Exception as e:
        errors.append(f"✗ ExecutionAgentV4 import failed: {e}")
    
    try:
        from app.agents.risk import RiskAgent
        print("✓ RiskAgent import OK")
    except Exception as e:
        errors.append(f"✗ RiskAgent import failed: {e}")
    
    try:
        from app.services.scaled_entry import ScaledEntryEngine
        print("✓ ScaledEntryEngine import OK")
    except Exception as e:
        errors.append(f"✗ ScaledEntryEngine import failed: {e}")
    
    return errors

def test_functions_exist():
    """Teste ob alle kritischen Funktionen existieren"""
    errors = []
    
    # Prompt 1-4 in composite_scorer.py
    from app.services.composite_scorer import CompositeScorer
    required_methods = ['score', '_calc_sl_tp', '_score_flow', '_score_macro', '_score_mean_reversion']
    for method in required_methods:
        if not hasattr(CompositeScorer, method):
            errors.append(f"✗ CompositeScorer missing method: {method}")
        else:
            print(f"✓ CompositeScorer.{method} exists")
    
    # Prompt 2-4 in execution_v4.py
    from app.agents.execution_v4 import ExecutionAgentV4
    required_methods = ['_calculate_risk_based_position_size', '_check_fee_hurdle', '_calculate_atr_based_sl_tp', 'execute_order']
    for method in required_methods:
        if not hasattr(ExecutionAgentV4, method):
            errors.append(f"✗ ExecutionAgentV4 missing method: {method}")
        else:
            print(f"✓ ExecutionAgentV4.{method} exists")
    
    # Prompt 5 in quant_v4.py
    from app.agents.quant_v4 import QuantAgentV4
    required_methods = ['_log_blocked_sweep', '_log_blocked_funding', '_fetch_ofi_rolling', '_submit_signal']
    for method in required_methods:
        if not hasattr(QuantAgentV4, method):
            errors.append(f"✗ QuantAgentV4 missing method: {method}")
        else:
            print(f"✓ QuantAgentV4.{method} exists")
    
    # Prompt 6 in scaled_entry.py
    from app.services.scaled_entry import ScaledEntryEngine
    required_methods = ['initiate_entry', 'check_pending_tranches', 'cancel_remaining']
    for method in required_methods:
        if not hasattr(ScaledEntryEngine, method):
            errors.append(f"✗ ScaledEntryEngine missing method: {method}")
        else:
            print(f"✓ ScaledEntryEngine.{method} exists")
    
    # Prompt 8 in risk.py
    from app.agents.risk import RiskAgent
    required_methods = ['_check_daily_drawdown', '_check_slot_consecutive_losses', 'record_slot_trade_result', 'validate_and_size_order']
    for method in required_methods:
        if not hasattr(RiskAgent, method):
            errors.append(f"✗ RiskAgent missing method: {method}")
        else:
            print(f"✓ RiskAgent.{method} exists")
    
    # Prompt 9 in orchestrator.py
    from app.agents.orchestrator import AgentOrchestrator
    required_methods = ['submit_signal_for_validation', '_run_strict_pipeline', 'get_pipeline_metrics']
    for method in required_methods:
        if not hasattr(AgentOrchestrator, method):
            errors.append(f"✗ AgentOrchestrator missing method: {method}")
        else:
            print(f"✓ AgentOrchestrator.{method} exists")
    
    return errors

def test_prompt_implementations():
    """Teste Prompt-spezifische Implementierungen"""
    errors = []
    
    # Prompt 1: OFI Filter in composite_scorer.py
    import inspect
    from app.services.composite_scorer import CompositeSignal
    source = inspect.getsource(CompositeSignal.to_decision_feed_entry)
    if "ofi_buy_pressure >= 0.60" in source and "ofi_buy_pressure <= 0.40" in source:
        print("✓ Prompt 1: OFI Hard Filter (>=0.60 / <=0.40) gefunden")
    else:
        errors.append("✗ Prompt 1: OFI Hard Filter nicht korrekt implementiert")
    
    # Prompt 2: Risk-Based Sizing
    from app.agents.execution_v4 import ExecutionAgentV4
    source = inspect.getsource(ExecutionAgentV4._calculate_risk_based_position_size)
    if "risk_percent = 0.01" in source and "risk_amount_usd = total_equity_usd * risk_percent" in source:
        print("✓ Prompt 2: Risk-Based Sizing (1% Risk) gefunden")
    else:
        errors.append("✗ Prompt 2: Risk-Based Sizing nicht korrekt implementiert")
    
    # Prompt 3: Fee Hurdle
    source = inspect.getsource(ExecutionAgentV4._check_fee_hurdle)
    if "0.0024" in source and "hurdle_threshold = risk_amount_usd * 0.25" in source:
        print("✓ Prompt 3: Fee Hurdle (0.24% roundtrip, 25% hurdle) gefunden")
    else:
        errors.append("✗ Prompt 3: Fee Hurdle nicht korrekt implementiert")
    
    # Prompt 4: ATR-basiertes SL/TP
    source = inspect.getsource(ExecutionAgentV4._calculate_atr_based_sl_tp)
    if "sl_mult = 1.2" in source and "tp1_mult = 1.5" in source and "tp2_mult = 3.0" in source:
        print("✓ Prompt 4: ATR-basiertes SL/TP (1.2x/1.5x/3.0x) gefunden")
    else:
        errors.append("✗ Prompt 4: ATR-basiertes SL/TP nicht korrekt implementiert")
    
    # Prompt 5: Sweep OFI Validation
    from app.agents.quant_v4 import QuantAgentV4
    # Die Logik ist in _run_scoring_cycle, nicht process
    source = inspect.getsource(QuantAgentV4._run_scoring_cycle)
    if "ofi_buy_pressure >= 0.60" in source and "_log_blocked_sweep" in source:
        print("✓ Prompt 5: Sweep OFI Validation gefunden")
    else:
        errors.append("✗ Prompt 5: Sweep OFI Validation nicht korrekt implementiert")
    
    # Prompt 6: ATR-basierte Scaled Entries
    from app.services.scaled_entry import ScaledEntryEngine
    source = inspect.getsource(ScaledEntryEngine.initiate_entry)
    if "trigger_atr_mult = 1.0" in source and "trigger_atr_mult = 2.0" in source:
        print("✓ Prompt 6: ATR-basierte Scaled Entries (1.0x/2.0x) gefunden")
    else:
        errors.append("✗ Prompt 6: ATR-basierte Scaled Entries nicht korrekt implementiert")
    
    # Prompt 7: Strategy Blending Fix
    from app.services.composite_scorer import CompositeScorer
    source = inspect.getsource(CompositeScorer.score)
    if "PROMPT 7" in source and "mr_contribution = 0.0" in source:
        print("✓ Prompt 7: Strategy Blending Fix (MR capped bei TA>80) gefunden")
    else:
        errors.append("✗ Prompt 7: Strategy Blending Fix nicht korrekt implementiert")
    
    # Prompt 8: Slot-spezifischer Circuit Breaker
    from app.agents.risk import RiskAgent
    source = inspect.getsource(RiskAgent._check_slot_consecutive_losses)
    if "slot_block" in source and "bruno:risk:slot_block" in source:
        print("✓ Prompt 8: Slot-spezifischer Circuit Breaker gefunden")
    else:
        errors.append("✗ Prompt 8: Slot-spezifischer Circuit Breaker nicht korrekt implementiert")
    
    # Prompt 9: Strict Pipeline
    from app.agents.orchestrator import AgentOrchestrator
    from app.agents.risk import RiskAgent
    from app.agents.execution_v4 import ExecutionAgentV4
    from app.agents.quant_v4 import QuantAgentV4
    
    source = inspect.getsource(AgentOrchestrator._run_strict_pipeline)
    if "validate_and_size_order" in source and "execute_order" in source:
        print("✓ Prompt 9: Strict Pipeline Flow gefunden")
    else:
        errors.append("✗ Prompt 9: Strict Pipeline Flow nicht korrekt implementiert")
    
    source = inspect.getsource(RiskAgent.validate_and_size_order)
    if "portfolio" in source and "validate_and_size_order" in RiskAgent.__dict__:
        print("✓ Prompt 9: RiskAgent validate_and_size_order gefunden")
    else:
        errors.append("✗ Prompt 9: RiskAgent validate_and_size_order nicht korrekt implementiert")
    
    source = inspect.getsource(QuantAgentV4._submit_signal)
    if "_strict_pipeline_mode" in source and "_signal_submit_callback" in source:
        print("✓ Prompt 9: QuantAgent _submit_signal mit Pipeline-Mode gefunden")
    else:
        errors.append("✗ Prompt 9: QuantAgent _submit_signal nicht korrekt implementiert")
    
    return errors

def main():
    print("=" * 60)
    print("Bruno V4 Refactoring - Prompts 1-9 Validierung")
    print("=" * 60)
    
    all_errors = []
    
    print("\n[1/3] Teste Imports...")
    all_errors.extend(test_imports())
    
    print("\n[2/3] Teste Funktions-Existenz...")
    all_errors.extend(test_functions_exist())
    
    print("\n[3/3] Teste Prompt-Implementierungen...")
    all_errors.extend(test_prompt_implementations())
    
    print("\n" + "=" * 60)
    if all_errors:
        print(f"VALIDIERUNG FEHLGESCHLAGEN - {len(all_errors)} Fehler:")
        for error in all_errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        print("✓ VALIDIERUNG ERFOLGREICH")
        print("Alle 9 Prompts sind korrekt implementiert!")
        sys.exit(0)

if __name__ == "__main__":
    main()
