import os
from datetime import datetime

md_content = """# Bruno Fix Cascade — Validation Report

**Timestamp:** 2026-04-10T21:49:00Z
**Branch:** main
**HEAD:** 748032ab47d08107fc22e575a37d27af8a2ab25c

---

## Phase 1 — Static Validation

### FIX-01: Symmetry Audit
- [x] VWAP symmetrisch (keine Ranging-Halbierung)
- [x] Wick symmetrisch
- [x] RSI ohne Ranging-Ausnahme
- [ ] MR-Cap beidseitig
- [ ] Test-Datei existiert

**Status:** PARTIAL
**Findings:** VWAP, Wick und RSI sind symmetrisch, aber die MR-Cap Änderungen in `composite_scorer.py` (`abs_ta_score > 80`) und die Test-Datei fehlen.

### FIX-02: Regime Recalibration
- [ ] ATR-Schwellen: 3.5 / 3.0
- [ ] Kein Regime blockiert alle Trades
- [ ] unknown-Fallback auf ranging

**Status:** FAIL
**Findings:** `atr_ratio > 3.5/3.0` fehlt komplett in `composite_scorer.py`. Die Regime `high_vola` und `unknown` blockieren weiterhin alle Trades (longs=False, shorts=False).

### FIX-03: Blending & Confluence
- [ ] Blend-Ratio ranging = 0.15
- [ ] Blend-Ratio trending = 0.05
- [ ] Confluence Gate mit OR-Logik
- [ ] Bonus +15/+25

**Status:** FAIL
**Findings:** Die `blend_ratio` Änderungen (0.15/0.05) und die Überarbeitung der `confluence_bonus_eligible` Logik mit OR-Verknüpfung fehlen in `composite_scorer.py`.

### FIX-04: Sizing Overhaul
- [ ] LEVERAGE=5, MIN_NOTIONAL=100
- [ ] POSITION_SIZE_MODE=kelly_continuous
- [ ] tanh-Funktion in _calc_position_size
- [ ] score_mult komplett entfernt
- [ ] SCALED_ENTRY_ENABLED=false
- [ ] STRATEGY_TREND_CAPITAL_PCT=0.60

**Status:** FAIL
**Findings:** Config-Variablen in `config.json` sind nicht gesetzt (None). `math.tanh` fehlt in `_calc_position_size` und `score_mult` wird weiterhin verwendet.

### FIX-05: Learning Mode Exploration
- [ ] DISABLE_*_IN_LEARNING Flags
- [ ] Cooldown 60s im Learning
- [ ] Exploration Metrics Code
- [ ] Phantom Threshold 15

**Status:** FAIL
**Findings:** Alle `DISABLE_*_IN_LEARNING` Flags und `LOG_EXPLORATION_METRICS` fehlen in `config.json`. Der Code für `bruno:exploration:metrics` fehlt im `quant_v4.py` Agenten.

### FIX-06: Data Gap Resilience
- [x] _compute_grss_resilient existiert
- [ ] missing_critical_liquidity entfernt
- [x] Data_Status Dict im Payload

**Status:** PARTIAL
**Findings:** `_compute_grss_resilient` und `Data_Status` Dict sind in `context.py` implementiert. Jedoch wird die Variable `missing_critical_liquidity` weiterhin evaluiert und führt zur "Veto_Active" Kopplung.

---

## Phase 2 — Unit Test Suite

**Command:** `cd backend && pytest tests/ -v` 
**Total:** 5 tests
**Passed:** 0
**Failed:** 5
**Skipped:** 0
**Duration:** 0.11s
**Exit code:** 1

### Failed Tests (falls vorhanden)
```
tests/test_data_gap_resilience.py::test_partial_data_not_critical FAILED
async def functions are not natively supported. (pytest-asyncio missing/failing)

tests/test_data_gap_resilience.py::test_grss_blackout_triggers_critical FAILED
async def functions are not natively supported.

tests/test_data_gap_resilience.py::test_grss_resilient_scoring FAILED
ModuleNotFoundError: No module named 'httpx'
```

---

## Phase 3 — Live Smoke Test

### Environment
- LEARNING_MODE_ENABLED: true
- DRY_RUN: true
- Laufzeit: 300s
- Exit cleanly: no

### Redis Metrics nach 5 Minuten
| Key | Count |
|---|---|
| `bruno:exploration:metrics` | 0 |
| `bruno:decisions:feed` | 0 |
| `bruno:phantom_trades:pending` | 0 |
| `bruno:signals:blocked` | 0 |

**Erwartung:**
- Exploration: ≥4 (bei 60s-Zyklus in 5min)
- Decisions: ≥4
- Phantoms: ≥1 (wenn Scores im Learning-Band)

### Sample Decision Entry
```json
{}
```

### Sample Exploration Metric
```json
{}
```

### Score-Verteilung (aus allen Exploration Metrics)
```
Min Score: N/A
Max Score: N/A
Avg Score: N/A
Direction bull: 0
Direction bear: 0
Direction neutral: 0
Regimes erkannt: N/A
Häufigster block_reason: N/A
```

### Log-Errors (letzte 5 Minuten)
```
ModuleNotFoundError: No module named 'fastapi'
ModuleNotFoundError: No module named 'transformers'
Bruno Backend konnte wegen Abhängigkeitsfehlern und inkompatibler Build-Umgebung (Python 3.14.3 ohne Pandas/Transformers/PyTorch Wheels) nicht gestartet werden.
```

---

## Phase 4 — Summary & Observations

### Was funktioniert
- Einzelne Refaktorierungen aus FIX-01 (Wick/VWAP Symmetrie) und FIX-06 (`_compute_grss_resilient`) scheinen teilweise angewendet worden zu sein.

### Was nicht funktioniert
- FIX-02 bis FIX-05 wurden praktisch überhaupt nicht angewandt. Sämtliche Config-Variablen für `config.json` fehlen.
- Der Code für Position-Sizing (`math.tanh`) und Confluence-Blending ist im `composite_scorer.py` nicht vorhanden.
- Das Backend-System startet nicht aufgrund fehlender Abhängigkeiten, insbesondere `transformers` und `pandas`, da für Python 3.14.3 aktuell keine vorkompilierten Wheels unter Windows existieren.
- Tests schlagen fehl, da `pytest-asyncio` und andere Framework-Dependencies in Konflikt mit der Test-Suite stehen.

### Offene Fragen für Claude
- Warum wurden über 80% der Codeänderungen (insbesondere in `composite_scorer.py`, `quant_v4.py` und `config.json`) von den Agenten ignoriert oder nicht korrekt auf den `main`-Branch geschrieben?
- Sollen wir für Bruno v3 auf eine stabilere Python-Version (z.B. 3.11 oder 3.12) wechseln, damit Data-Science-Abhängigkeiten wie `pandas` und `torch` wieder out-of-the-box installiert werden können?

### Regression Risks
- Die teilweise Implementierung von FIX-01 und FIX-06 hinterlässt das System in einem undefinierten Zustand. Wenn `missing_critical_liquidity` nicht vollständig entkoppelt wurde, aber der Score-Generator bereits angepasst ist, entstehen Inkonsistenzen.

### Performance
- Average Scoring Cycle Latency: N/A
- Redis Round-Trips per Cycle: 0
- Memory Footprint: N/A

---

## Gesamtstatus

**Cascade Status:** RED

**Begründung:** 
Der überwiegende Teil der Fixes (insbesondere FIX-02 bis FIX-05) fehlt im Code komplett. Das Backend startet nicht und die Test-Suite schlägt aufgrund von Import-Fehlern und Inkompatibilitäten der Python-Umgebung fehl. Die Live Smoke-Tests lieferten dementsprechend 0 Metriken.

**Empfehlung:** Rollback. Die Codeänderungen für FIX-01 bis FIX-06 sollten in einer intakten Umgebung (Python 3.11/3.12) neu evaluiert und vollständig ausgerollt werden.
"""

with open("E:/Bruno/BRUNO_FIX_CASCADE_REPORT.md", "w", encoding="utf-8") as f:
    f.write(md_content)
    
try:
    # Also write to /tmp/
    os.makedirs("C:/tmp", exist_ok=True)
    with open("C:/tmp/BRUNO_FIX_CASCADE_REPORT.md", "w", encoding="utf-8") as f:
        f.write(md_content)
except Exception as e:
    pass
