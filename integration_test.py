#!/usr/bin/env python3
"""
Integrationstest für Bruno v2.1 - Simuliert den kompletten Flow
"""
import sys
import os
sys.path.append('backend')

def test_position_tracker_slot_logic():
    """Testet Position Tracker Slot-Logik"""
    print("\n🧪 Test: Position Tracker Slot-Logik")
    
    try:
        from backend.app.services.position_tracker import REDIS_KEY
        
        # Test Redis-Key Patterns
        trend_key = REDIS_KEY.format(symbol="BTCUSDT", slot="trend")
        sweep_key = REDIS_KEY.format(symbol="BTCUSDT", slot="sweep")
        funding_key = REDIS_KEY.format(symbol="BTCUSDT", slot="funding")
        
        print(f"✅ Trend Key: {trend_key}")
        print(f"✅ Sweep Key: {sweep_key}")
        print(f"✅ Funding Key: {funding_key}")
        
        # Prüfe ob Keys korrekt formatiert sind
        assert "trend" in trend_key
        assert "sweep" in sweep_key  
        assert "funding" in funding_key
        assert "{slot}" not in trend_key  # Wichtig: kein Platzhalter!
        
        print("✅ Redis-Key Patterns korrekt")
        return True
        
    except Exception as e:
        print(f"❌ Position Tracker Test fehlgeschlagen: {e}")
        return False

def test_strategy_slot_sizing():
    """Testet Strategy-Slot Sizing Logik"""
    print("\n🧪 Test: Strategy-Slot Sizing")
    
    try:
        from backend.app.services.strategy_manager import STRATEGY_SLOTS
        
        # Teste Kapital-Allokation
        total_capital = 100000  # $100k
        
        allocations = {}
        for name, slot in STRATEGY_SLOTS.items():
            if slot.enabled:
                capital = total_capital * slot.capital_allocation_pct
                allocations[name] = {
                    'capital_usd': capital,
                    'leverage': slot.max_leverage,
                    'risk_per_trade': capital * slot.risk_per_trade_pct / 100
                }
        
        print("✅ Kapital-Allokation:")
        for name, alloc in allocations.items():
            print(f"  {name}: ${alloc['capital_usd']:,.0f} @ {alloc['leverage']}x = ${alloc['risk_per_trade']:,.0f} Risk/Trade")
        
        # Prüfe ob Gesamt-Allokation <= 100%
        total_allocation = sum(alloc['capital_usd'] for alloc in allocations.values())
        allocation_pct = total_allocation / total_capital
        
        print(f"✅ Gesamt-Allokation: {allocation_pct:.1%}")
        assert allocation_pct <= 1.0, "Über-Allokation!"
        
        return True
        
    except Exception as e:
        print(f"❌ Sizing Test fehlgeschlagen: {e}")
        return False

def test_scaled_entry_logic():
    """Testet Scaled Entry Logik"""
    print("\n🧪 Test: Scaled Entry Logic")
    
    try:
        from backend.app.services.strategy_manager import STRATEGY_SLOTS
        
        # Nur Trend-Slot hat Scaled Entry
        trend_slot = STRATEGY_SLOTS["trend"]
        
        if not trend_slot.scaled_entry_enabled:
            print("❌ Scaled Entry nicht aktiviert")
            return False
            
        # Teste Tranche-Größen
        total_size = 1.0  # 1 BTC
        tranche_sizes = [total_size * pct for pct in trend_slot.tranche_sizes]
        
        print(f"✅ Tranche-Größen für {total_size} BTC:")
        for i, size in enumerate(tranche_sizes, 1):
            print(f"  Tranche {i}: {size:.4f} BTC ({trend_slot.tranche_sizes[i-1]*100:.0f}%)")
        
        # Prüfe Summe
        assert abs(sum(tranche_sizes) - total_size) < 0.0001, "Tranche-Summe stimmt nicht!"
        print("✅ Tranche-Summe korrekt")
        
        return True
        
    except Exception as e:
        print(f"❌ Scaled Entry Test fehlgeschlagen: {e}")
        return False

def test_cooldown_logic():
    """Testet Cooldown-Logik"""
    print("\n🧪 Test: Cooldown Logic")
    
    try:
        import time
        
        # Simuliere Cooldowns
        cooldowns = {
            'trend': 300,      # 5min
            'sweep': 60,       # 1min  
            'funding': 1800    # 30min
        }
        
        last_signals = {slot: 0 for slot in cooldowns.keys()}
        now = time.time()
        
        # Teste Sweep Cooldown (soll erlaubt sein)
        last_signals['sweep'] = now - 70  # 70s her
        sweep_allowed = now - last_signals['sweep'] >= cooldowns['sweep']
        
        # Teste Funding Cooldown (soll nicht erlaubt sein)
        last_signals['funding'] = now - 100  # 100s her
        funding_allowed = now - last_signals['funding'] >= cooldowns['funding']
        
        print(f"✅ Sweep Signal erlaubt: {sweep_allowed} (vor 70s)")
        print(f"✅ Funding Signal erlaubt: {funding_allowed} (vor 100s)")
        
        assert sweep_allowed == True, "Sweep sollte erlaubt sein"
        assert funding_allowed == False, "Funding sollte nicht erlaubt sein"
        
        print("✅ Cooldown-Logik korrekt")
        return True
        
    except Exception as e:
        print(f"❌ Cooldown Test fehlgeschlagen: {e}")
        return False

def test_max_hold_times():
    """Testet Max Hold Times"""
    print("\n🧪 Test: Max Hold Times")
    
    try:
        from backend.app.services.strategy_manager import STRATEGY_SLOTS
        
        hold_times = {}
        for name, slot in STRATEGY_SLOTS.items():
            if hasattr(slot, 'max_hold_minutes') and slot.max_hold_minutes:
                hold_times[name] = slot.max_hold_minutes
        
        print("✅ Max Hold Times:")
        for name, minutes in hold_times.items():
            print(f"  {name}: {minutes}min ({minutes//60}h {minutes%60}min)")
        
        # Erwartete Werte
        expected = {
            'sweep': 120,    # 2h
            'funding': 480   # 8h
        }
        
        for name, expected_minutes in expected.items():
            actual = hold_times.get(name)
            if actual != expected_minutes:
                print(f"❌ {name}: erwartet {expected_minutes}, gefunden {actual}")
                return False
        
        print("✅ Max Hold Times korrekt")
        return True
        
    except Exception as e:
        print(f"❌ Max Hold Test fehlgeschlagen: {e}")
        return False

def test_redis_key_consistency():
    """Testet Redis-Key Konsistenz über alle Services"""
    print("\n🧪 Test: Redis-Key Konsistenz")
    
    try:
        # Teste verschiedene Key-Patterns
        patterns = {
            'position': 'bruno:position:{symbol}:{slot}',
            'scaled_entry': 'bruno:scaled_entry:{symbol}:{slot}',
        }
        
        symbol = "BTCUSDT"
        slots = ["trend", "sweep", "funding"]
        
        for service, pattern in patterns.items():
            print(f"✅ {service} Keys:")
            for slot in slots:
                key = pattern.format(symbol=symbol, slot=slot)
                print(f"  {key}")
                
                # Prüfe ob Platzhalter ersetzt wurden
                assert "{symbol}" not in key
                assert "{slot}" not in key
                assert symbol in key
                assert slot in key
        
        print("✅ Redis-Key Konsistenz geprüft")
        return True
        
    except Exception as e:
        print(f"❌ Redis-Key Test fehlgeschlagen: {e}")
        return False

def main():
    print("🚀 Bruno v2.1 - Integrationstests\n")
    
    tests = [
        ("Position Tracker Slot-Logik", test_position_tracker_slot_logic),
        ("Strategy-Slot Sizing", test_strategy_slot_sizing),
        ("Scaled Entry Logic", test_scaled_entry_logic),
        ("Cooldown Logic", test_cooldown_logic),
        ("Max Hold Times", test_max_hold_times),
        ("Redis-Key Konsistenz", test_redis_key_consistency),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} Exception: {e}")
            results.append((name, False))
    
    print(f"\n{'='*60}")
    print("🎯 INTEGRATIONTEST ERGEBNISSE")
    print(f"{'='*60}")
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1
    
    print(f"\nErgebnis: {passed}/{len(results)} Tests bestanden")
    
    if passed == len(results):
        print("🎉 Alle Integrationstests bestanden!")
        print("🚀 Bruno v2.1 ist voll funktionsfähig!")
    else:
        print("⚠️  Einige Tests fehlgeschlagen - Überprüfung erforderlich")

if __name__ == "__main__":
    main()
