# Agent Core Documentation

> **Referenz: WINDSURF_MANIFEST.md v2.0 — Dieses Dokument ist sekundär**
> 
> ✅ **Primäre Umgebung:** Windows mit **Ryzen 7 7800X3D + RX 7900 XT** (native Ollama)

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Rolle & Mission

Du bist ein **Elite-KI-Entwickler** für algorithmischen Krypto-Handel. Unser Ziel ist ein **fehlerfreier, transparenter Bot** der auf einer Windows-Hybrid-Architektur (Ryzen 7 7800X3D + RX 7900 XT) läuft.

**Manifest v2.0 gilt vorrangig.** Bei Widerspruch: Manifest gewinnt.

---

## Arbeitsregeln (STRIKT)

### 1. Kontext-Management (Hierarchie beachten!)
1. **WINDSURF_MANIFEST.md** - IMMER zuerst lesen (einige Quelle der Wahrheit)
2. **Status.md** - Aktuellen Stand prüfen
3. **arch.md** - Architektur verstehen
4. **ki.md** - LLM-Details
5. **DANN** Code ändern

### 2. Eiserne Regeln (Aus Manifest — NIEMALS BRECHEN)
```
❌ Polling < 60s für Quant/Context/Risk
❌ random.uniform() in produktivem Code
❌ Echte Orders bei DRY_RUN=True
❌ GRSS aus < 4 echten Datenquellen
❌ Position ohne Stop-Loss UND Take-Profit
❌ API-Keys im Repository
```

### 3. Dokumentations-Pflicht
- **Nach JEDEM Feature**: `Status.md` aktualisieren
- **Nach JEDEM Bug**: `log.md` mit Root-Cause & Lösung
- **Bei Änderungen**: ERST Manifest, DANN Code
- **Bei Phase-B-Hardening**: `docs/status.md`, `docs/arch.md` und `README.md` synchron halten

---

## Aktueller Stand (Manifest v2.0)

> 🔧 **Wir bauen auf Windows:** Docker Desktop (WSL2) + Native Ollama

### Phase C/D — LLM-Kaskade + Position Tracking — AKTIV

Ziel: Phase A/B abgeschlossen — Bot ist "ehrlich" und regime-aware. Jetzt laufen LLM-Kaskade und Positionsverwaltung im Worker.

**Aufgaben:**
- [x] LLM Cascade (3 Layer) im QuantAgent integriert
- [x] **Bruno Pulse**: Echtzeit-Transparency (Sub-States & LLM Pulse)
- [x] **Background Heartbeat Loop**: Unabhängige Vitalzeichen-Übermittlung (15s)
- [x] Regime Manager mit 2-Bestätigungs-Logik + Transition Buffer
- [x] PositionTracker/PositionMonitor im Worker verdrahtet
- [x] CoinGlass Graceful Degradation ohne API-Key
- [x] Telegram Notifications mit Chat-ID-Auth
- [x] Erweiterte Daten-Quellen (Funding Rates, Liquidations)
- [x] Profit-Factor-Tracking aus realisierter P&L-Historie
- [ ] SL/TP Tests mit echten Preisen validieren
- [ ] Frontend Cockpit

### Phase A — Fundament ✅ COMPLETED (2026-03-29)

Ziel erreicht: Den Bot ehrlich machen. Keine Zufallsdaten mehr.

**Erledigt:**
- [x] ContextAgent: Alle `random.uniform()` entfernt
- [x] BTC 24h Change aus Redis berechnet
- [x] Binance REST: OI, OI-Delta, L/S-Ratio, Perp-Basis
- [x] Deribit Public: Put/Call Ratio, DVOL
- [x] GRSS-Funktion: echte Daten (Manifest Abschnitt 5)
- [x] QuantAgent: 5s → 300s Intervall
- [x] ContextAgent: 60s → 900s Intervall
- [x] CVD State in Redis persistiert
- [x] Data-Freshness Fail-Safe: GRSS bricht bei stale data auf 0.0 ab
- [x] Live-Trading Guard: `LIVE_TRADING_APPROVED` Flag implementiert
- [x] CoinMarketCap Health: Health-Telemetrie integriert

**Wichtigste Regel:** GRSS muss 100% echte Daten verwenden. Keine Mocks. ✅ ERLEDIGT

### Phase D — Position Tracker & Stop-Loss ✅ CORE IMPLEMENTED

**Status:** Der Live-Positions-Flow läuft über `ExecutionAgentV3`, `PositionTracker` und `PositionMonitor`.

---

## Quick Reference

| Ressource | Link | Zweck |
|-----------|------|-------|
| **Manifest** | `/WINDSURF_MANIFEST.md` | Einzige Quelle der Wahrheit |
| **Status** | `/docs/status.md` | Aktueller Projekt-Stand |
| **Architektur** | `/docs/arch.md` | Börsen, Datenfluss, 6 Agenten |
| **KI/LLM** | `/docs/ki.md` | Ollama, Modelle, Inferenz |
| **Logbuch** | `/docs/log.md` | Fehler & Lösungen |

---

---
## Agenten-Vitalzeichen (Bruno Pulse)
Jeder Agent erbt von `BaseAgent` und nutzt:
- `_heartbeat_loop`: Ein Hintergrund-Task, der alle 15s Vitalzeichen an Redis sendet.
- `self.state.sub_state`: Ein Feld für granulare Status-Meldungen (z.B. "Analyzing 5/20").
- `_report_pulse` (LLMCascade): Echtzeit-Tracking der Entscheidungs-Schritte.

*Referenz: WINDSURF_MANIFEST.md v2.0 — Phase C: Bruno Pulse*

