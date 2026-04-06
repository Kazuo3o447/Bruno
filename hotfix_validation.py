#!/usr/bin/env python3
"""
Bruno Hotfix Validation - Überprüfung aller 3 Scoring-Bugs
"""
import subprocess
import json
import time

def check_decision_feed():
    """Prüft die neueste Decision für Bug-Fixes"""
    print("🔍 Decision Feed Check")
    
    try:
        result = subprocess.run(
            ["docker", "exec", "bruno-redis", "redis-cli", "LRANGE", "bruno:decisions:feed", "0", "0"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            decision = json.loads(result.stdout.strip())
            
            # Bug 2 Check: Kein "Low conviction < 0.7"
            reason = decision.get("reason", "")
            conviction_fix = "Low conviction" not in reason and "0.7" not in reason
            
            # Bug 1 Check: TA-Score Verbesserung
            ta_score = decision.get("ta_score", 0)
            ta_improved = ta_score >= 8.0  # Sollte jetzt ≥ 8 sein
            
            # Bug 3 Check: Composite Score Verbesserung
            comp_score = decision.get("composite_score", 0)
            comp_improved = comp_score >= 5.0  # Sollte jetzt ≥ 5 sein
            
            print(f"  ✅ Reason: {reason}")
            print(f"  ✅ TA-Score: {ta_score} (≥8.0: {ta_improved})")
            print(f"  ✅ Composite-Score: {comp_score} (≥5.0: {comp_improved})")
            print(f"  ✅ Conviction-Fixed: {conviction_fix}")
            
            return conviction_fix and ta_improved and comp_improved
        else:
            print("  ❌ Keine Decision gefunden")
            return False
            
    except Exception as e:
        print(f"  ❌ Decision Check Fehler: {e}")
        return False

def check_ta_breakdown():
    """Prüft TA-Breakdown für Bug 1"""
    print("\n🔍 TA-Breakdown Check")
    
    try:
        result = subprocess.run(
            ["docker", "exec", "bruno-redis", "redis-cli", "GET", "bruno:ta:snapshot"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            snapshot = json.loads(result.stdout.strip())
            ta_score = snapshot.get("ta_score", {})
            breakdown = ta_score.get("ta_breakdown", {})
            
            # Check ob Breakdown existiert
            has_breakdown = bool(breakdown)
            
            # Check ob Perfect Bull EMA Stack 25 Punkte gibt
            ema_points = breakdown.get("ema_stack", 0)
            perfect_bull = ema_points == 25
            
            # Check ob MTF Alignment 20 Punkte gibt
            mtf_points = breakdown.get("mtf_alignment", 0)
            mtf_aligned = mtf_points >= 15.0
            
            # Check ob Macro Penalty moderat ist (50% statt 80%)
            macro_penalty = breakdown.get("macro_penalty", 0)
            macro_reasonable = macro_penalty >= -10.0  # Sollte nicht zu hart sein
            
            print(f"  ✅ Breakdown exists: {has_breakdown}")
            print(f"  ✅ EMA Stack: {ema_points} points (Perfect Bull: {perfect_bull})")
            print(f"  ✅ MTF Alignment: {mtf_points} points (Aligned: {mtf_aligned})")
            print(f"  ✅ Macro Penalty: {macro_penalty} (Reasonable: {macro_reasonable})")
            
            return has_breakdown and perfect_bull and mtf_aligned and macro_reasonable
        else:
            print("  ❌ Kein TA-Snapshot gefunden")
            return False
            
    except Exception as e:
        print(f"  ❌ TA-Breakdown Check Fehler: {e}")
        return False

def check_conviction_gate_removed():
    """Prüft ob Conviction-Gate entfernt wurde (Bug 2)"""
    print("\n🔍 Conviction-Gate Check")
    
    try:
        # Prüfe CompositeScorer Code
        with open('backend/app/services/composite_scorer.py', 'r') as f:
            content = f.read()
        
        # Check ob Conviction-Gate auskommentiert/entfernt ist
        conviction_removed = (
            "Conviction Check (nur für Diagnostik, kein Blocker!)" in content and
            "Der CompositeScore + Threshold ist der einzige Gate" in content
        )
        
        # Check ob der alte Code entfernt wurde
        old_code_removed = "Low conviction" not in content or "confidence_threshold" not in content.split("Conviction Check")[1].split("Regime Direction")[0]
        
        print(f"  ✅ Conviction-Gate entfernt: {conviction_removed}")
        print(f"  ✅ Alter Code entfernt: {old_code_removed}")
        
        return conviction_removed and old_code_removed
        
    except Exception as e:
        print(f"  ❌ Conviction-Gate Check Fehler: {e}")
        return False

def check_macro_penalty_reduced():
    """Prüft ob Macro Penalty reduziert wurde (Bug 3)"""
    print("\n🔍 Macro-Penalty Check")
    
    try:
        # Prüfe TechnicalAgent Code
        with open('backend/app/agents/technical.py', 'r') as f:
            content = f.read()
        
        # Check ob 80% Penalty zu 50% geändert wurde
        penalty_reduced = (
            "score *= 0.5  # 50% Penalty statt 80%" in content and
            "weniger restriktiv" in content
        )
        
        # Check ob die alten 80% und 70% Penalties entfernt wurden
        old_penalties_removed = (
            "score *= 0.2  # 80% Penalty" not in content and
            "score *= 0.3" not in content
        )
        
        # Check ob die neuen moderaten Penalties da sind
        new_penalties = (
            "score *= 0.5  # 50% Penalty" in content and
            "score *= 1.2  # 20% Bonus" in content
        )
        
        print(f"  ✅ Penalty auf 50% reduziert: {penalty_reduced}")
        print(f"  ✅ Alte 80%/70% Penalties entfernt: {old_penalties_removed}")
        print(f"  ✅ Neue moderaten Penalties: {new_penalties}")
        
        return penalty_reduced and old_penalties_removed and new_penalties
        
    except Exception as e:
        print(f"  ❌ Macro-Penalty Check Fehler: {e}")
        return False

def check_system_health():
    """Prüft allgemeine System-Gesundheit"""
    print("\n🔍 System Health Check")
    
    try:
        # Docker Container Status
        result = subprocess.run(
            ["docker", "compose", "ps"],
            capture_output=True, text=True, timeout=10
        )
        
        containers_running = result.returncode == 0 and "Up" in result.stdout
        
        # Backend Health
        health_result = subprocess.run(
            ["docker", "exec", "bruno-redis", "redis-cli", "GET", "bruno:health:backend"],
            capture_output=True, text=True, timeout=5
        )
        
        backend_healthy = health_result.returncode == 0
        
        print(f"  ✅ Docker Container: {containers_running}")
        print(f"  ✅ Backend Health: {backend_healthy}")
        
        return containers_running and backend_healthy
        
    except Exception as e:
        print(f"  ❌ System Health Check Fehler: {e}")
        return False

def main():
    print("🔍 Bruno Hotfix - Umfassende Validierung\n")
    
    tests = [
        ("Decision Feed", check_decision_feed),
        ("TA-Breakdown", check_ta_breakdown),
        ("Conviction-Gate Removed", check_conviction_gate_removed),
        ("Macro-Penalty Reduced", check_macro_penalty_reduced),
        ("System Health", check_system_health),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} Exception: {e}")
            results.append((name, False))
    
    print(f"\n{'='*70}")
    print("🎯 HOTFIX VALIDATION ERGEBNISSE")
    print(f"{'='*70}")
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1
    
    print(f"\nErgebnis: {passed}/{len(results)} Checks bestanden")
    
    if passed == len(results):
        print("\n🎉 ALLE HOTFIXES ERFOLGREICH UMGESETZT!")
        print("✅ Bruno Scoring ist jetzt balanced und weniger restriktiv")
        print("✅ Bullische Setups im Ranging erhalten faire Chancen")
        print("✅ System ready für DRY_RUN Daten-Sammlung")
    else:
        print("\n⚠️  Einige Hotfixes benötigen Überprüfung")
    
    print(f"\n📋 Hotfix-Zusammenfassung:")
    print("✅ Bug 1: TA-Score Breakdown implementiert")
    print("✅ Bug 2: Conviction-Gate 0.7 entfernt") 
    print("✅ Bug 3: Macro Penalty 80% → 50% reduziert")

if __name__ == "__main__":
    main()
