# Regime Config — Phase C

> **Status:** ✅ IMPLEMENTIERT — 4 Marktregimes mit Transition Buffer
> 
> **Ziel:** Stabile Regime-Erkennung mit 2-Bestätigungs-Logik und Transition Protection

---

## Marktregimes

### 1. **trending_bull** — Aufwärtstrend
```python
grss_threshold=45,         # Niedrig — Trend gibt Rückenwind
ofi_threshold=400,
stop_loss_pct=0.008,
take_profit_pct=0.020,     # 2.5:1 R:R
position_size_multiplier=1.0,
allow_longs=True,
allow_shorts=False,        # Gegen Trend = strukturelles Risiko
```

### 2. **ranging** — Seitwärts/Chop
```python
grss_threshold=55,         # Höher — weniger Richtungsklarheit
ofi_threshold=600,
stop_loss_pct=0.006,
take_profit_pct=0.012,     # 2:1 R:R
position_size_multiplier=0.5,  # Halbe Größe im Chop
allow_longs=True,
allow_shorts=True,
```

### 3. **high_vola** — Hohe Volatilität
```python
grss_threshold=60,
ofi_threshold=700,
stop_loss_pct=0.015,       # Weiterer Stop wegen Rauschen
take_profit_pct=0.030,     # 2:1 R:R — gleiche Ratio, größere Abstände
position_size_multiplier=0.3,
allow_longs=True,
allow_shorts=True,
```

### 4. **bear** — Bärenmarkt
```python
grss_threshold=50,
ofi_threshold=500,
stop_loss_pct=0.010,
take_profit_pct=0.020,
position_size_multiplier=0.7,
allow_longs=False,         # Keine Longs im Bärenmarkt
allow_shorts=True,
```

### 5. **unknown** — Fallback
```python
grss_threshold=65,         # Sehr konservativ
ofi_threshold=800,
stop_loss_pct=0.010,
take_profit_pct=0.020,
position_size_multiplier=0.3,
allow_longs=False,
allow_shorts=False,        # Kein Trade bei unbekanntem Regime
```

---

## Regime Manager

### 2-Bestätigungs-Logik
```python
MIN_CONFIRMATIONS = 2   # Mindestanzahl konsekutiver gleicher Signale
```

**Flow:**
1. Layer 1 erkennt "trending_bull"
2. `pending_count = 1`
3. Nächstes Layer 1 erkennt wieder "trending_bull"
4. `pending_count = 2` → **Regime wechselt**
5. Bei abweichendem Signal → `pending_count = 1` (Reset)

### Transition Buffer
```python
TRANSITION_BUFFER_CYCLES = 2  # Zyklen mit erhöhtem GRSS nach Wechsel
TRANSITION_GRSS_BOOST = 10    # Zusätzliche GRSS-Punkte während Transition
```

**Beispiel:**
- Regime wechselt zu "trending_bull" (GRSS threshold: 45)
- Für 2 Zyklen gilt: `45 + 10 = 55` als effektiver Threshold
- Danach normaler Threshold: 45

---

## GRSS Gate Integration

### Vor Cascade-Aufruf
```python
effective_threshold = regime_manager.get_effective_grss_threshold()
if grss_score < effective_threshold:
    return CascadeResult(aborted_at="grss_gate")
```

### Transition-Logik
```python
def get_effective_grss_threshold(self) -> int:
    base = self.get_config().grss_threshold
    if self._transition_cycle > 0:
        return base + self.TRANSITION_GRSS_BOOST
    return base
```

---

## Persistenz & State

### Redis State
```python
{
    "regime": "trending_bull",
    "transition_cycle": 1,  # 0-2
    "updated_at": "2026-03-29T18:00:00Z"
}
```

### LLM Cascade Integration
```python
# Layer 1 Output
l1_raw = {"regime": "trending_bull", "confidence": 0.8}

# Regime Manager Update
confirmed_regime = await regime_manager.update(l1_raw["regime"])

# Config für Layer 2+3
config = regime_manager.get_config()
if not config.allow_longs and decision == "BUY":
    return CascadeResult(aborted_at="regime_gate")
```

---

## API Monitoring

### Status Endpoint
```bash
GET /api/v1/llm/cascade/status
```

**Response:**
```json
{
  "status": "active",
  "last_run": {
    "decision": "BUY",
    "regime": "trending_bull",
    "transition_active": true,
    "transition_cycles_left": 1,
    "effective_grss_threshold": 55
  },
  "regime": {
    "current": "trending_bull",
    "transition_cycle": 1,
    "transition_active": true,
    "config": {
      "grss_threshold": 45,
      "stop_loss_pct": 0.008,
      "take_profit_pct": 0.020,
      "rr_ratio": 2.5,
      "allow_longs": true,
      "allow_shorts": false
    }
  }
}
```

### Force Regime (Testing)
```bash
POST /api/v1/llm/cascade/force-regime
{
  "regime": "ranging"
}
```

---

## Risk Management

### Regime-spezifische Limits
| Regime | Longs | Shorts | Size Multiplier | SL | TP | R:R |
|--------|-------|--------|----------------|----|----|-----|
| **trending_bull** | ✅ | ❌ | 1.0x | 0.8% | 2.0% | 2.5:1 |
| **ranging** | ✅ | ✅ | 0.5x | 0.6% | 1.2% | 2:1 |
| **high_vola** | ✅ | ✅ | 0.3x | 1.5% | 3.0% | 2:1 |
| **bear** | ❌ | ✅ | 0.7x | 1.0% | 2.0% | 2:1 |
| **unknown** | ❌ | ❌ | 0.3x | 1.0% | 2.0% | 2:1 |

### Transition Protection
- **+10 GRSS Points** nach Regime-Wechsel
- **2 Zyklen** erhöhte Vorsicht
- **Verhindert Fehltrades** in unsicheren Phasen

---

## Testing & Validation

### Unit Tests
```python
async def test_regime_confirmation():
    manager = RegimeManager(redis_mock)
    
    # Erste Detection
    regime = await manager.update("trending_bull")
    assert regime == "unknown"  # Noch nicht bestätigt
    
    # Zweite Detection
    regime = await manager.update("trending_bull")
    assert regime == "trending_bull"  # Jetzt bestätigt
```

### Transition Buffer Test
```python
async def test_transition_buffer():
    manager = RegimeManager(redis_mock)
    manager._current_regime = "trending_bull"
    manager._transition_cycle = 2
    
    # Erhöhter Threshold während Transition
    threshold = manager.get_effective_grss_threshold()
    assert threshold == 45 + 10  # 55
```

### Integration Tests
```python
async def test_regime_gate():
    # GRSS unter Threshold → HOLD
    result = await cascade.run(grss_score=40, ...)
    assert result.aborted_at == "grss_gate"
    
    # GRSS über Threshold → Cascade läuft
    result = await cascade.run(grss_score=50, ...)
    assert result.aborted_at != "grss_gate"
```

---

## Benefits

### 1. **Stability**
- **2-Bestätigungs-Logik** verhindert nervöse Wechsel
- **Transition Buffer** für zusätzliche Sicherheit
- **Conservative Thresholds** für unknown Regime

### 2. **Adaptability**
- **Regime-spezifische Parameter** für optimale Performance
- **Dynamic GRSS Thresholds** basierend auf Regime
- **Position Sizing** an Volatilität angepasst

### 3. **Risk Management**
- **Directional Restrictions** (Longs/Shorts)
- **Size Limits** für volatile Phasen
- **Conservative Defaults** für unknown Regime

### 4. **Observability**
- **Full State Tracking** in Redis
- **Transition Monitoring** über API
- **Regime History** für Analysis

---

## Troubleshooting

### Regime Stuck in "unknown"
```python
# Prüfen ob Layer 1 valide Regimes erkennt
l1_output = await llm_provider.generate_json(...)
if l1_output.get("regime") not in VALID_REGIMES:
    # Prompt oder Model prüfen
```

### Too Frequent Regime Changes
```python
# MIN_CONFIRMATIONS erhöhen
MIN_CONFIRMATIONS = 3  # Statt 2
```

### Transition Buffer Too Long
```python
# TRANSITION_BUFFER_CYCLES reduzieren
TRANSITION_BUFFER_CYCLES = 1  # Statt 2
```

---

## Future Enhancements

### 1. **Adaptive Thresholds**
- ML-basierte Threshold-Optimierung
- Historische Performance-Analyse

### 2. **Multi-Timeframe Regimes**
- 1h für kurzfristige Entscheidungen
- 4h für mittelfristige Strategien

### 3. **Regime Confidence Scores**
- Weighted Confirmation Logic
- Probabilistic Regime Assignment

---

*Die Regime Config macht Phase C intelligent und stabil — von einfachen Signalen zu regime-aware Trading mit Transition Protection.*
