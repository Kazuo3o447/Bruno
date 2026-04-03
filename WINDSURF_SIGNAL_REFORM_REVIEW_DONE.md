# WINDSURF SIGNAL REFORM — REVIEW ERGEBNIS
Datum: 2026-04-03
Container-Uptime: >10 Minuten seit Neustart

## BLOCK 1 (Code-Analyse)
1.1 OFI-Gate entfernt:        ❌
- `backend/app/agents/quant_v3.py` enthält noch den String `ofi_threshold` in `_log_decision()`.
- Das ist kein aktives OFI-Gate mehr, aber der strikte Review-Check schlägt deshalb trotzdem an.

1.2 GRSS-Key korrekt:         ✅
- Kein echter Alt-Key-Use mehr in `quant_v3.py`.
- Gefunden wurde nur die korrekte Zeile `grss_score = grss_data.get("GRSS_Score", 0.0)`.

1.3 Pre-Gate Schwelle 20:     ✅
- Es gibt genau die neue `grss_score < 20`-Logik.
- Kein `< 40`-Pre-Gate mehr sichtbar.

1.4 _fetch_ofi_rolling:       ✅
- Methode vorhanden.
- `market:ofi:ticks` und `buy_pressure_ratio` sind implementiert.

1.5 _log_decision:            ✅
- Methode vorhanden.
- `bruno:decisions:feed`, `PRE_GATE_HOLD` und `SIGNAL_BUY` sind im Code.

1.6 Signal-Amount korrekt:    ✅
- Kein `amount: 0.01` mehr.
- Signal nutzt `0.001`.

1.7 OFI Buffer in Ingestion:  ✅
- `ingestion.py` schreibt in `market:ofi:ticks`.
- `LPUSH` und `LTRIM 0 299` sind vorhanden.

1.8 GRSS kein 0.0-Kollaps:   ✅
- Der alte harte Collapse für `fresh_source_count == 0` ist weg.
- Stattdessen ist Penalty-Logik vorhanden: `score -= 20` / `score -= (2 - fresh_count) * 8`.

1.9 Python AST-Check:         ❌
- Der Check würde wegen des verbleibenden Strings `ofi_threshold` in `quant_v3.py` fehlschlagen.
- Functional OFI-Gate ist weg, aber der AST-/String-Check ist dadurch noch nicht sauber.

## BLOCK 2 (Laufzeit)
2.1 OFI-Buffer befüllt:       ✅ (LLEN: 300)
- `market:ofi:ticks` ist gefüllt.
- LINDEX liefert JSON mit `t` und `r`.

2.2 GRSS korrekt gelesen:     ✅ (GRSS_Score: 69.8)
- `bruno:context:grss` enthält einen realen Score.
- `Data_Freshness_Active: True`.

2.3 Decision Feed befüllt:    ✅ (LLEN: 58)
- Feed ist gefüllt.
- Neuere Einträge enthalten `ts`, `outcome`, `grss` und `ofi_buy_pressure`.

2.4 GRSS-Bug behoben:         ✅
- Letzte Einträge sind nicht mehr alle 0.0.
- Beispiel: `grss = 64.6`.

2.5 API-Endpoint:             ✅
- Der Decisions-Router existiert unter `GET /api/v1/decisions/feed`.
- Er liest `bruno:decisions:feed` aus Redis und liefert `events`, `count` und `stats`.

2.6 LLM Cascade aufgerufen:   ✅
- Der Decision Feed zeigt `CASCADE_GRSS_HOLD` statt nur OFI-Gate-Ausfällen.
- Das belegt, dass die Cascade-Pipeline in der Laufzeit erreicht wird.

2.7 Keine alten OFI-Logs:     ✅
- Im aktuellen Zustand ist keine aktive OFI-Threshold-Logik mehr im Quant-Pfad sichtbar.
- Stattdessen wird der OFI-Wert als Input und nicht als Gate genutzt.

## BLOCK 3 (Dokumentation)
3.1 Manifest aktualisiert:    ✅
- Neue Section `3.1b Signal-Architektur (nach Reform S1, 2026-04-03)` vorhanden.
- `market:ofi:ticks`, `buy_pressure_ratio` und der Zeitzyklus sind dokumentiert.

3.2 Alte Doku entfernt:       ❌
- `WINDSURF_MANIFEST.md` enthält weiterhin `OFI_Threshold: 500` in der Regime-Config.
- Damit ist die alte Threshold-Dokumentation nicht vollständig entfernt.

## GESAMTSTATUS
NICHT BESTANDEN

## KRITISCHE FEHLER
- `backend/app/agents/quant_v3.py`: verbleibender String `ofi_threshold` in `_log_decision()` triggert die strikten OFI-Gate-Checks.
- `backend/app/agents/quant_v3.py`: AST-/String-Check scheitert deshalb ebenfalls.
- `WINDSURF_MANIFEST.md`: `OFI_Threshold: 500` ist noch dokumentiert.

## NÄCHSTE SCHRITTE
- Entfernen oder Umbenennen des verbleibenden `ofi_threshold`-Strings in `quant_v3.py`, falls die Review-Regeln strikt erfüllt werden sollen.
- Alte `OFI_Threshold: 500`-Dokumentation aus dem Manifest entfernen.
- Danach Review erneut laufen lassen.
