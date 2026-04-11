import subprocess
import time
import sys
import redis
import json
import os

print("Starting Bruno backend...")
process = subprocess.Popen([sys.executable, "-m", "app.main"], cwd="e:/Bruno/backend")

print(f"Bruno started with PID {process.pid}. Waiting for 300 seconds...")
try:
    time.sleep(300)
except KeyboardInterrupt:
    pass
finally:
    print("Stopping Bruno...")
    process.terminate()
    process.wait(timeout=10)
    print("Bruno stopped.")

# Collect metrics
print("\n--- METRICS ---")
try:
    r = redis.Redis()
    exp_len = r.llen('bruno:exploration:metrics')
    dec_len = r.llen('bruno:decisions:feed')
    phan_len = r.llen('bruno:phantom_trades:pending')
    block_len = r.llen('bruno:signals:blocked')
    
    print(f"Exploration metrics count: {exp_len}")
    print(f"Decisions count: {dec_len}")
    print(f"Phantoms count: {phan_len}")
    print(f"Blocked signals count: {block_len}")
    
    print("\n--- Last exploration sample ---")
    if exp_len > 0:
        sample_exp = r.lindex('bruno:exploration:metrics', 0)
        print(json.dumps(json.loads(sample_exp), indent=2))
    else:
        print("None")
        
    print("\n--- Sample decisions ---")
    for i in range(min(5, dec_len)):
        dec = r.lindex('bruno:decisions:feed', i)
        print(json.dumps(json.loads(dec), indent=2)[:1000])
        print("---")
        
    print("\n--- Score Verteilung ---")
    if exp_len > 0:
        scores = []
        directions = {'bull': 0, 'bear': 0, 'neutral': 0}
        regimes = set()
        reasons = {}
        
        for i in range(exp_len):
            try:
                data = json.loads(r.lindex('bruno:exploration:metrics', i))
                scores.append(data.get('composite_score', 0))
                directions[data.get('direction', 'neutral')] += 1
                regimes.add(data.get('regime', 'unknown'))
                reason = data.get('block_reason', 'none')
                reasons[reason] = reasons.get(reason, 0) + 1
            except:
                pass
                
        if scores:
            print(f"Min Score: {min(scores)}")
            print(f"Max Score: {max(scores)}")
            print(f"Avg Score: {sum(scores)/len(scores):.2f}")
            print(f"Direction bull: {directions['bull']}")
            print(f"Direction bear: {directions['bear']}")
            print(f"Direction neutral: {directions['neutral']}")
            print(f"Regimes erkannt: {list(regimes)}")
            if reasons:
                most_common = max(reasons.items(), key=lambda x: x[1])[0]
                print(f"Häufigster block_reason: {most_common}")
except Exception as e:
    print(f"Error collecting metrics: {e}")

print("\n--- Logs ---")
try:
    with open("e:/Bruno/backend/logs/bruno.log", "r", encoding="utf-8") as f:
        lines = f.readlines()
        errors = [l for l in lines[-500:] if "error" in l.lower() or "critical" in l.lower() or "exception" in l.lower()]
        for e in errors[:20]:
            print(e.strip())
except Exception as e:
    print(f"Error reading logs: {e}")
