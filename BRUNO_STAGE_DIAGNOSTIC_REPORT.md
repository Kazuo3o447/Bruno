# Bruno v2.1.1 Stage-by-Stage TA-Breakdown Diagnostik

## Zusammenfassung

Am 6. April 2026 wurde eine vollständige Stage-by-Stage Diagnostik für den TA-Breakdown implementiert, um eine unerklärliche Residual-Differenz (~21 Punkte) aufzulösen. Die Diagnostik zeigt den exakten Scoreverlauf an jeder relevanten Stelle und leitet die Breakdown-Komponenten aus den tatsächlichen Stufenänderungen ab.

## Problem

Der TA-Breakdown im Redis-Snapshot zeigte eine Residual-Differenz, die nicht durch die sichtbaren Komponenten erklärbar war:

```json
{
  "known_components_sum": 27.5,
  "residual_penalty": -15.0,
  "total_after_clamp": 12.5
}
```

Dies erschwerte die Fehlersuche und Validierung der Scoring-Logik.

## Lösung

### Stage Progression Checkpoints

An jeder relevanten Stelle der Score-Berechnung wird ein Checkpoint gesetzt:

```python
stage_progression = {
    "after_trend": 25.0,          # Nach EMA-Stack
    "after_mtf_alignment": 45.0,  # Nach MTF-Alignment
    "after_rsi": 45.0,            # Nach RSI-Signal
    "after_sr_breakout": 30.0,    # Nach S/R-Kontext + Breakout
    "after_volume": 28.0,         # Nach Volume-Bewertung
    "after_vwap": 25.0,           # Nach VWAP-Position
    "after_wick": 25.0,           # Nach Wick-Signal
    "after_mtf_filter": 25.0,     # Nach MTF-Filter
    "after_macro": 12.5,          # Nach Macro-Trend
    "pre_clamp": 12.5,            # Vor Clamp auf [-100, 100]
    "final": 12.5                 # Finaler TA-Score
}
```

### Dynamische Breakdown-Komponenten

Statt statischer Annahmen werden die realen Deltas berechnet:

```python
# S/R-Proximity aus Stufenänderung ableiten
ta_breakdown["sr_proximity"] = round(
    stage_progression["after_sr_breakout"]
    - stage_progression["after_rsi"]
    - ta_breakdown["breakout_bonus"],
    1
)

# MTF-Filter Penalty
ta_breakdown["mtf_penalty"] = round(
    stage_progression["after_mtf_filter"] - stage_progression["after_wick"],
    1
)

# Macro Penalty
ta_breakdown["macro_penalty"] = round(
    stage_progression["after_macro"] - stage_progression["after_mtf_filter"],
    1
)
```

### Residual-Auflösung

Die Summe aller bekannten Komponenten wird mit dem finalen Score verglichen:

```python
ta_breakdown["known_components_sum"] = round(
    ta_breakdown["ema_stack"]
    + ta_breakdown["mtf_alignment"]
    + ta_breakdown["rsi_signal"]
    + ta_breakdown["sr_proximity"]
    + ta_breakdown["breakout_bonus"]
    + ta_breakdown["vwap_position"]
    + ta_breakdown["volume_bonus"]
    + ta_breakdown["wick_signal"]
    + ta_breakdown["macro_penalty"]
    + ta_breakdown["mtf_penalty"],
    1
)

ta_breakdown["residual_penalty"] = round(
    score - ta_breakdown["known_components_sum"],
    1
)
```

## Ergebnisse

### Vorher (mit Residual)

```json
{
  "known_components_sum": 27.5,
  "residual_penalty": -15.0,
  "total_after_clamp": 12.5
}
```

### Nachher (sauber)

```json
{
  "known_components_sum": 12.5,
  "residual_penalty": 0.0,
  "total_after_clamp": 12.5,
  "stage_progression": {
    "after_trend": 25.0,
    "after_mtf_alignment": 45.0,
    "after_rsi": 45.0,
    "after_sr_breakout": 30.0,
    "after_volume": 28.0,
    "after_vwap": 25.0,
    "after_wick": 25.0,
    "after_mtf_filter": 25.0,
    "after_macro": 12.5,
    "pre_clamp": 12.5,
    "final": 12.5
  }
}
```

## Wichtige Hinweise

- **Keine Änderung an Trading-Logik**: Die Diagnostik ändert nichts an Scores, Filtern oder Thresholds
- **Nur Transparenz**: Die Stage Progression dient nur der besseren Nachvollziehbarkeit
- **Vollständige Auflösung**: Residual-Penalty ist jetzt 0.0
- **Live-Validierung**: Der aktuelle Snapshot zeigt die saubere Umsetzung

## Technische Implementierung

Die Änderungen wurden in folgenden Dateien implementiert:

1. **`backend/app/agents/technical.py`**:
   - Stage Progression Checkpoints in `_calculate_ta_score()`
   - Dynamische Breakdown-Komponenten
   - Residual-Auflösung

2. **Dokumentation**:
   - `docs/trading_logic_v2.md` (Abschnitt 12.4)
   - `docs/Status.md` (Bug 4 hinzugefügt)
   - Diese Datei

## Validation

Die Diagnostik wurde live im System validiert:

- **Redis Snapshot**: `bruno:ta:snapshot` enthält saubere Breakdown-Daten
- **Residual Penalty**: 0.0 (vorher ~21)
- **Stage Progression**: Vollständig nachvollziehbar
- **Trading Logik**: Unverändert

---

*Erstellt: 2026-04-06*  
*Status: COMPLETED*  
*Version: v2.1.1*
