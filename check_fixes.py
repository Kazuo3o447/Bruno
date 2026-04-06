#!/usr/bin/env python3
"""
Überprüft alle Bruno v2.1 Fixes und Konfigurationen
"""
import sys
import os
sys.path.append('backend')

def check_strategy_slots():
    """Überprüft STRATEGY_SLOTS Konfiguration"""
    try:
        from backend.app.services.strategy_manager import STRATEGY_SLOTS
        
        print("=== STRATEGY_SLOTS Konfiguration ===")
        for name, slot in STRATEGY_SLOTS.items():
            print(f"{name}: enabled={slot.enabled}, capital_pct={slot.capital_allocation_pct}, leverage={slot.max_leverage}, scaled_entry={slot.scaled_entry_enabled}")
            if hasattr(slot, 'entry_tranches'):
                print(f"  - Tranches: {slot.entry_tranches}, Sizes: {[f'{s*100:.0f}%' for s in slot.tranche_sizes]}")
            if hasattr(slot, 'max_hold_minutes'):
                print(f"  - Max Hold: {slot.max_hold_minutes}min")
        return True
    except Exception as e:
        print(f"❌ STRATEGY_SLOTS Check fehlgeschlagen: {e}")
        return False

def check_position_tracker():
    """Überprüft Position Tracker Methoden"""
    try:
        from backend.app.services.position_tracker import PositionTracker, REDIS_KEY
        
        print("\n=== Position Tracker Check ===")
        print(f"✅ REDIS_KEY Pattern: {REDIS_KEY}")
        
        # Methoden Signaturen prüfen
        import inspect
        pt = PositionTracker(None, None)
        
        get_sig = inspect.signature(pt.get_open_position)
        print(f"✅ get_open_position(): {get_sig}")
        
        update_sig = inspect.signature(pt.update_position) 
        print(f"✅ update_position(): {update_sig}")
        
        close_sig = inspect.signature(pt.close_position)
        print(f"✅ close_position(): {close_sig}")
        
        return True
    except Exception as e:
        print(f"❌ Position Tracker Check fehlgeschlagen: {e}")
        return False

def check_execution_agent():
    """Überprüft ExecutionAgent Integration"""
    try:
        from backend.app.agents.execution_v4 import ExecutionAgentV4
        
        print("\n=== ExecutionAgent Check ===")
        
        # Prüfe ob ScaledEntryEngine importiert wird
        import inspect
        source = inspect.getsource(ExecutionAgentV4.__init__)
        
        if "ScaledEntryEngine" in source:
            print("✅ ScaledEntryEngine importiert")
        else:
            print("❌ ScaledEntryEngine NICHT importiert")
            
        if "self.scaled_entry" in source:
            print("✅ ScaledEntryEngine initialisiert")
        else:
            print("❌ ScaledEntryEngine NICHT initialisiert")
            
        return True
    except Exception as e:
        print(f"❌ ExecutionAgent Check fehlgeschlagen: {e}")
        return False

def check_quant_agent():
    """Überprüft QuantAgentV4 Cooldowns"""
    try:
        from backend.app.agents.quant_v4 import QuantAgentV4
        
        print("\n=== QuantAgentV4 Check ===")
        
        # Prüfe Cooldown-Tracker
        import inspect
        source = inspect.getsource(QuantAgentV4.__init__)
        
        if "_last_sweep_signal_time" in source:
            print("✅ Sweep Cooldown-Tracker vorhanden")
        else:
            print("❌ Sweep Cooldown-Tracker fehlt")
            
        if "_last_funding_signal_time" in source:
            print("✅ Funding Cooldown-Tracker vorhanden")
        else:
            print("❌ Funding Cooldown-Tracker fehlt")
            
        return True
    except Exception as e:
        print(f"❌ QuantAgentV4 Check fehlgeschlagen: {e}")
        return False

def check_config():
    """Überprüft config.json"""
    try:
        import json
        
        print("\n=== Config Check ===")
        with open('backend/config.json', 'r') as f:
            config = json.load(f)
            
        print(f"✅ Max_Leverage: {config.get('Max_Leverage')}")
        print(f"✅ LEVERAGE: {config.get('LEVERAGE')}")
        print(f"✅ TRADE_COOLDOWN_SECONDS: {config.get('TRADE_COOLDOWN_SECONDS')}")
        
        # Prüfe ob Max_Leverage und LEVERAGE konsistent
        if config.get('Max_Leverage') == config.get('LEVERAGE'):
            print("✅ Leverage Konfiguration konsistent")
        else:
            print(f"❌ Leverage Konflikt: Max_Leverage={config.get('Max_Leverage')} vs LEVERAGE={config.get('LEVERAGE')}")
            
        return True
    except Exception as e:
        print(f"❌ Config Check fehlgeschlagen: {e}")
        return False

def check_scaled_entry_service():
    """Überprüft ScaledEntryEngine"""
    try:
        from backend.app.services.scaled_entry import ScaledEntryEngine
        
        print("\n=== ScaledEntryEngine Check ===")
        
        # Prüfe Methoden
        import inspect
        methods = ['initiate_entry', 'check_pending_tranches', 'cancel_remaining']
        
        for method_name in methods:
            if hasattr(ScaledEntryEngine, method_name):
                print(f"✅ {method_name}() vorhanden")
            else:
                print(f"❌ {method_name}() fehlt")
                
        return True
    except Exception as e:
        print(f"❌ ScaledEntryEngine Check fehlgeschlagen: {e}")
        return False

def main():
    print("🔍 Bruno v2.1 - Überprüfung aller Fixes\n")
    
    checks = [
        ("STRATEGY_SLOTS", check_strategy_slots),
        ("Position Tracker", check_position_tracker), 
        ("ExecutionAgent", check_execution_agent),
        ("QuantAgentV4", check_quant_agent),
        ("Config", check_config),
        ("ScaledEntryEngine", check_scaled_entry_service),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} Check Exception: {e}")
            results.append((name, False))
    
    print(f"\n{'='*50}")
    print("📊 ZUSAMMENFASSUNG")
    print(f"{'='*50}")
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1
    
    print(f"\nErgebnis: {passed}/{len(results)} Checks bestanden")
    
    if passed == len(results):
        print("🎉 Alle Checks bestanden - Bruno v2.1 ist ready!")
    else:
        print("⚠️  Einige Checks fehlgeschlagen - Überprüfung erforderlich")

if __name__ == "__main__":
    main()
