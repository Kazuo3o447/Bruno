# Phase C — LLM-Kaskade (3 Layer) - LEGACY v1
  
> **Status:** 📦 ARCHIVIERT — Wurde in v2.2 durch deterministische Engine ersetzt
> 
> **Zeitraum:** Woche 3–5 (Historie)
> 
> **Historisches Ziel:** Intelligente Handels-Entscheidungen durch 3-stufige LLM-Kaskade

---

## Übersicht (Historisch)

Phase C implementierte die **intelligente Entscheidungsschicht** des Bruno Trading Bots in v1. Anstatt simpler OFI-Signale nutzte der Bot eine 3-Layer LLM-Kaskade für fundierte Handels-Entscheidungen.

**Aktueller Stand (v2.2):** Diese LLM-Kaskade wurde entfernt und durch eine deterministische Composite Scoring Engine ersetzt. Nur Deepseek Reasoning API wird noch für Post-Trade Analysen verwendet.

### Die 3 Layer

| Layer | Aufgabe | Modell | Output | Gate |
|-------|---------|--------|--------|------|
| **Layer 1** | Regime-Erkennung | `qwen2.5:14b` | `{regime, confidence, key_signals}` | confidence ≥ 0.60 |
| **Layer 2** | Strategisches Reasoning | `deepseek-r1:14b` | `{decision, confidence, sl_pct, tp_pct}` | decision ≠ HOLD, confidence ≥ 0.65 |
| **Layer 3** | Advocatus Diaboli | `qwen2.5:14b` | `{blocker, blocking_reasons}` | blocker == false |

---

## Architektur

### Flow-Diagramm

```
GRSS Score (≥ 30) ──► QuantAgent
                         │
                         ▼
                   LLM Cascade
                         │
                    ┌────┴────┐
                    │ Layer 1 │ ← Regime (qwen2.5)
                    └────┬────┘
                         │ confidence ≥ 0.60
                    ┌────┴────┐
                    │ Layer 2 │ ← Strategy (deepseek-r1)
                    └────┬────┘
                         │ confidence ≥ 0.65
                    ┌────┴────┐
                    │ Layer 3 │ ← Devil's Advocate (qwen2.5)
                    └────┬────┘
                         │ blocker == false
                         ▼
                   Signal → RiskAgent → ExecutionAgentV3
```

### Integration

- **QuantAgent** ruft LLM-Kaskade auf (statt einfacher OFI-Signale)
- **RiskAgent** erhält Cascade-Extras für Risiko-Checks
- **ExecutionAgentV3** nutzt SL/TP aus Layer 2 und übergibt Positionen an den PositionTracker

---

## Implementierungsdetails

### Core Module

#### 1. `app/llm/llm_cascade.py`
- **LLMCascade** Klasse mit 3-Layer Logik
- **CascadeResult** Datenstruktur für vollständigen Output
- **Gate-Mechanismus** mit klaren HOLD-Pfaden
- **Redis-Logging** für Dashboard-Anzeige

#### 2. `app/services/regime_config_v2.py`
- **RegimeManager** mit 2-Bestätigungs-Logik
- **RegimeConfig** für regime-spezifische Parameter
- **REGIME_CONFIGS** Dictionary mit allen Regimen

#### 3. `app/routers/llm_cascade.py`
- **API-Endpoints** für Monitoring und Debugging
- **Status**, **Metrics**, **Decision History**
- **Force Regime** für Testing

### Runtime-Status

- **QuantAgent** publiziert nur actionable Signale nach der 3-Layer-Kaskade
- **ExecutionAgentV3** übernimmt die Order-Ausführung und öffnet die Position im `PositionTracker`
- **PositionTracker** und **PositionMonitor** bilden den Phase-D-Flow für Open/Close/SL/TP

### Prompts

#### Layer 1: Regime-Erkennung
```python
Analysiere das aktuelle Bitcoin-Marktregime.

GRSS-Komponenten: {grss_components}
Markt-Snapshot: {market_snapshot}

Gib zurück als JSON:
{
    "regime": "trending_bull|ranging|high_vola|bear",
    "confidence": 0.0 bis 1.0,
    "key_signals": ["Signal 1", "Signal 2", "Signal 3"],
    "reasoning": "Ein Satz warum dieses Regime (max 30 Wörter)"
}
```

#### Layer 2: Strategisches Reasoning
```python
Du bist ein institutioneller Quant-Trader für Bitcoin.
Analysiere das Chance-Risiko-Verhältnis dieses Setups.

Layer 1 Output: {layer1_output}
Market Context: {market_context}
Failure Patterns: {failure_watchlist}

Gib zurück als JSON:
{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0.0 bis 1.0,
    "entry_reasoning": "Haupt-Argument (max 50 Wörter)",
    "risk_factors": ["Risiko 1", "Risiko 2"],
    "suggested_sl_pct": 0.008 bis 0.020,
    "suggested_tp_pct": 0.016 bis 0.040
}
```

#### Layer 3: Advocatus Diaboli
```python
Du hast EINE Aufgabe: Finde Gründe warum der folgende Trade FALSCH ist.
Sei hart. Sei kritisch. Keine Höflichkeit.

Trade Decision: {layer2_output}
Market Context: {market_context}

Gib zurück als JSON:
{
    "blocker": true oder false,
    "blocking_reasons": ["Grund 1", "Grund 2"],
    "risk_override": false
}
```

---

## Regime-Konfigurationen

### Regime-Typen

| Regime | Trading | SL | TP | Max Size | Confidence |
|--------|---------|----|----|----------|------------|
| **trending_bull** | Longs only | 1.2% | 2.5% | 15% | 0.60 |
| **ranging** | Both | 0.8% | 1.6% | 8% | 0.70 |
| **high_vola** | None | 1.5% | 3.0% | 5% | 0.75 |
| **bear** | Shorts only | 1.0% | 2.0% | 10% | 0.65 |
| **unknown** | None | 1.0% | 2.0% | 5% | 0.80 |

### 2-Bestätigungs-Logik

- Regime wird erst nach **2x gleicher Detection** aktiv
- Verhindert häufige Regime-Wechsel
- Persistiert in Redis für Cross-Run-Konsistenz

---

## Gates & Safety

### Gate 1: Regime Confidence
- **Mindestens 0.60** Konfidenz für Regime
- Bei Unterschreitung → HOLD @ Gate1
- Loggt Regime-Wechsel für Debugging

### Gate 2: Decision Confidence
- **Mindestens 0.65** Konfidenz für Entscheidung
- **HOLD** wird immer blockiert
- Bei Unterschreitung → HOLD @ Gate2

### Gate 3: Risk Blocker
- **Advocatus Diaboli** prüft auf Risiken
- **blocker == false** erforderlich
- Bei Blocker → HOLD @ Layer3

### Regime Gate
- **Longs/Shorts** nur wenn erlaubt
- Regime-spezifische Limits
- Bei Verstoß → HOLD @ Regime Gate

---

## Failure WatchList

### Mechanismus
- **Post-Trade Debrief** analysiert fehlgeschlagene Trades
- **Pattern-Erkennung** für wiederkehrende Fehler
- **Injection** in Layer 2 als Kontext

### Pattern-Typen
```python
{
    "pattern": "high_vola_buy_reversal",
    "description": "Longs in hoher Volatilität scheitern oft",
    "frequency": 3,
    "avg_loss_pct": 0.015,
    "last_occurrence": "2026-03-29T18:00:00Z"
}
```

---

## API-Endpoints

### Cascade Status
```
GET /api/v1/llm/cascade/status
```

### Cascade Metrics
```
GET /api/v1/llm/cascade/metrics
```

### Force Regime (Testing)
```
POST /api/v1/llm/cascade/force-regime
{
    "regime": "trending_bull"
}
```

### Decision History
```
GET /api/v1/llm/cascade/decision-history?limit=20
```

---

## Performance

### Timing-Ziele
- **Layer 1**: < 500ms (qwen2.5)
- **Layer 2**: < 1000ms (deepseek-r1)
- **Layer 3**: < 500ms (qwen2.5)
- **Gesamt**: < 2000ms

### Caching
- **Regime**: 5 Minuten Cache
- **Decision History**: Rolling 3
- **Failure Patterns**: 24 Stunden Cache

---

## Testing & Validation

### Unit Tests
- **LLMCascade.run()** mit Mock-Daten
- **RegimeManager** 2-Bestätigungs-Logik
- **Gate-Mechanismen** Edge Cases

### Integration Tests
- **QuantAgent → Cascade → RiskAgent** Flow
- **Redis-Persistenz** über Restarts
- **LLM-Timeout** Handling

### Live Testing
- **Shadow Trading** mit Cascade-Signalen
- **Performance-Monitoring** < 2s
- **Decision Quality** Tracking

---

## Monitoring

### Dashboard-Metriken
- **Cascade Success Rate** (BUY/SELL vs HOLD)
- **Gate Pass Rates** (Gate1/2/3)
- **Regime Distribution** (welche Regimen wann)
- **Decision Latency** (durchschnittliche Dauer)

### Alerts
- **Cascade Timeout** > 3s
- **Gate Failure Rate** > 80%
- **Regime Flapping** (> 3 Wechsel/h)
- **LLM Parse Errors**

---

## Next Steps

### Immediate (Woche 3) ✅
- [x] Core Implementation
- [x] QuantAgent Integration
- [x] API Router
- [x] Live Testing mit echten GRSS-Daten
- [x] Performance-Optimierung

### Short Term (Woche 4) ✅
- [x] Bruno Pulse Implementation (Real-time Transparency)
- [x] Decision History Tracking
- [x] Failure WatchList Integration (Core)
- [x] Frontend Integration (AgentStatusMonitor)

### Medium Term (Woche 5) ✅
- [x] Cascade Performance Analysis
- [x] Regime-Specific Optimierungen
- [x] A/B Testing vs Simple Signals
- [x] Documentation Complete

---

## Troubleshooting

### Häufige Issues

#### 1. LLM Parse Errors
```python
# Lösung: Robuster JSON Parser mit Fallback
try:
    start = response.find('{')
    end = response.rfind('}') + 1
    json_str = response[start:end]
    return json.loads(json_str)
except:
    return {"_parse_error": True, "raw_response": response}
```

#### 2. Cascade Timeout
```python
# Lösung: Timeout pro Layer
async def _generate_json(self, prompt, layer_name, use_reasoning):
    try:
        response = await asyncio.wait_for(
            ollama_client.generate_response(...),
            timeout=2.0  # 2s pro Layer
        )
        return self._parse_json(response)
    except asyncio.TimeoutError:
        return {"_parse_error": True, "error": "timeout"}
```

#### 3. Regime Flapping
```python
# Lösung: 2-Bestätigungs-Logik
if detected_regime == self._current_regime:
    self._confirmation_count = min(self._confirmation_count + 1, 2)
else:
    self._confirmation_count = 1  # Reset bei Wechsel
```

---

## Success Criteria

### Phase C Complete Wenn:
- [x] LLM Cascade implementiert und integriert
- [ ] Cascade Success Rate > 60%
- [ ] Average Latency < 2s
- [ ] No Gate Failure Rate > 80%
- [ ] Regime Stability > 80%
- [ ] Frontend Dashboard zeigt Cascade-Metriken
- [ ] Documentation vollständig

---

*Phase C macht den Bruno Bot "intelligent" — von simplen Signalen zu fundierten LLM-basierten Entscheidungen.*
