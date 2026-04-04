#!/usr/bin/env python3
"""
Bruno v2 Integration Test Suite

Testet alle Komponenten des Bruno v2 Systems auf Import-Fehler
und grundlegende Funktionalität.

Ausführung: python backend/test_imports.py
"""

import sys
import traceback
from datetime import datetime

def test_import(module_name, description):
    """Testet den Import eines Moduls."""
    try:
        __import__(module_name)
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ {description}: {e}")
        traceback.print_exc()
        return False

def test_class_instantiation(module_name, class_name, description):
    """Testet die Instanziierung einer Klasse."""
    try:
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        
        # Versuche Instanziierung mit minimalen Parametern
        if class_name == "TechnicalAnalysisEngine":
            instance = cls(redis=None)
        elif class_name == "LiquidityEngine":
            instance = cls(redis=None)
        elif class_name == "CompositeScorer":
            instance = cls(redis=None)
        elif class_name == "QuantAgentV4":
            # QuantAgent braucht Dependencies - nur Import testen
            print(f"✅ {description} (Import only)")
            return True
        elif class_name == "TradeDebriefServiceV2":
            instance = cls(redis=None, db_session_factory=None)
        else:
            instance = cls()
        
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ {description}: {e}")
        traceback.print_exc()
        return False

def main():
    """Haupt-Test-Funktion."""
    print("=" * 60)
    print("Bruno v2 Integration Test Suite")
    print("=" * 60)
    print(f"Zeitpunkt: {datetime.now()}")
    print()
    
    tests = []
    
    # 1. Core Engine Tests
    print("🔧 CORE ENGINE TESTS")
    print("-" * 30)
    
    tests.append(test_import(
        "app.agents.technical", 
        "TechnicalAnalysisEngine Import"
    ))
    
    tests.append(test_class_instantiation(
        "app.agents.technical",
        "TechnicalAnalysisEngine",
        "TechnicalAnalysisEngine Instanziierung"
    ))
    
    tests.append(test_import(
        "app.services.liquidity_engine", 
        "LiquidityEngine Import"
    ))
    
    tests.append(test_class_instantiation(
        "app.services.liquidity_engine",
        "LiquidityEngine",
        "LiquidityEngine Instanziierung"
    ))
    
    tests.append(test_import(
        "app.services.composite_scorer", 
        "CompositeScorer Import"
    ))
    
    tests.append(test_class_instantiation(
        "app.services.composite_scorer",
        "CompositeScorer",
        "CompositeScorer Instanziierung"
    ))
    
    print()
    
    # 2. Agent Tests
    print("🤖 AGENT TESTS")
    print("-" * 30)
    
    tests.append(test_import(
        "app.agents.quant_v4", 
        "QuantAgentV4 Import"
    ))
    
    tests.append(test_class_instantiation(
        "app.agents.quant_v4",
        "QuantAgentV4",
        "QuantAgentV4 Import (Dependencies needed)"
    ))
    
    tests.append(test_import(
        "app.agents.risk", 
        "RiskAgentV2 Import"
    ))
    
    tests.append(test_import(
        "app.agents.execution_v3", 
        "ExecutionAgentV3 Import"
    ))
    
    tests.append(test_import(
        "app.worker", 
        "Worker Import"
    ))
    
    print()
    
    # 3. Service Tests
    print("🛠️  SERVICE TESTS")
    print("-" * 30)
    
    tests.append(test_import(
        "app.services.trade_debrief_v2", 
        "TradeDebriefServiceV2 Import"
    ))
    
    tests.append(test_class_instantiation(
        "app.services.trade_debrief_v2",
        "TradeDebriefServiceV2",
        "TradeDebriefServiceV2 Instanziierung"
    ))
    
    print()
    
    # 4. Configuration Tests
    print("⚙️  CONFIGURATION TESTS")
    print("-" * 30)
    
    try:
        import json
        config_path = "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        
        required_v2_keys = [
            "ENABLE_LLM_CASCADE_V4",
            "DAILY_LOSS_LIMIT_PCT", 
            "MAX_DAILY_LOSS_TRADES",
            "TRADE_COOLDOWN_SECONDS",
            "BREAK_EVEN_TRIGGER_PCT",
            "BREAK_EVEN_ENABLED"
        ]
        
        missing_keys = []
        for key in required_v2_keys:
            if key not in config:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"❌ Config Keys fehlen: {missing_keys}")
            tests.append(False)
        else:
            print("✅ Alle v2 Config Keys vorhanden")
            tests.append(True)
            
    except Exception as e:
        print(f"❌ Config Test: {e}")
        tests.append(False)
    
    print()
    
    # 5. Integration Tests
    print("🔗 INTEGRATION TESTS")
    print("-" * 30)
    
    # Teste Worker Integration
    try:
        from app.worker import main as worker_main
        print("✅ Worker Main Import")
        tests.append(True)
    except Exception as e:
        print(f"❌ Worker Main Import: {e}")
        tests.append(False)
    
    # Teste Orchestrator Integration
    try:
        from app.agents.orchestrator import AgentOrchestrator
        print("✅ AgentOrchestrator Import")
        tests.append(True)
    except Exception as e:
        print(f"❌ AgentOrchestrator Import: {e}")
        tests.append(False)
    
    print()
    
    # 6. Documentation Tests
    print("📚 DOCUMENTATION TESTS")
    print("-" * 30)
    
    doc_files = [
        "../docs/trading_logic_v2.md",
        "../docs/arch.md", 
        "../WINDSURF_MANIFEST.md"
    ]
    
    for doc_file in doc_files:
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > 1000:  # Mindestlänge prüfen
                print(f"✅ {doc_file} vorhanden und ausreichend")
                tests.append(True)
            else:
                print(f"❌ {doc_file} zu kurz")
                tests.append(False)
        except Exception as e:
            print(f"❌ {doc_file}: {e}")
            tests.append(False)
    
    print()
    
    # 7. Summary
    print("=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    
    passed = sum(tests)
    total = len(tests)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    print(f"Tests bestanden: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("🎉 BRUNO V2 INTEGRATION ERFOLGREICH!")
        print("System ist bereit für den Start.")
    elif success_rate >= 75:
        print("⚠️  BRUNO V2 INTEGRATION MEISTENS ERFOLGREICH")
        print("Einige Probleme müssen noch behoben werden.")
    else:
        print("❌ BRUNO V2 INTEGRATION FEHLGESCHLAGEN")
        print("Erhebliche Probleme müssen behoben werden.")
    
    print()
    print("Nächste Schritte:")
    print("1. Bei Erfolg: System mit 'python -m app.worker' starten")
    print("2. Bei Problemen: Fehler oben beheben und Test wiederholen")
    print("3. Monitoring: Frontend für System-Status prüfen")
    
    return success_rate >= 90

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
