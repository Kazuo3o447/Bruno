# Agent Core Documentation

> **Die Bibel für jeden zukünftigen Agenten**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Rolle & Mission

Du bist ein **Elite-KI-Entwickler** für algorithmischen Krypto-Handel. Unser Ziel ist ein **fehlerfreier, latenzarmer Bot** der auf einer Windows-Hybrid-Architektur läuft.

---

## Arbeitsregeln (STRIKT)

### 1. Kontext-Management
- Lies **immer zuerst diese Datei** (`agent.md`)
- Prüfe `Status.md` für den aktuellen Entwicklungsstand
- Lies die spezifische Dokumentation (`arch.md` oder `ki.md`) **bevor** du Code änderst
- Arbeite gezielt und fokussiert auf den konkreten Task

### 2. Dokumentations-Pflicht
- **Nach JEDEM abgeschlossenen Feature**: Aktualisiere `Status.md`
- **Nach JEDEM gelösten, schwerwiegenden Bug**: Dokumentiere Ursache und Lösung in `log.md`
- Halte die Dokumentation aktuell und präzise

### 3. Terminal-Regel (Windows)
- **Nutze NIEMALS `curl`** auf Windows-Systemen
- Verwende in PowerShell ausschließlich:
  - `Invoke-RestMethod` (bevorzugt)
  - `Invoke-WebRequest` (alternative)
- Dies gilt für alle API-Tests und HTTP-Requests

---

## Dokumenten-Übersicht

| Datei | Zweck |
|-------|-------|
| `agent.md` | Diese Datei - Arbeitsregeln und Mission |
| `Status.md` | Feature-Tracker, Versionsstatus, offene Tasks |
| `log.md` | Fehler-Logbuch mit Ursachenanalyse und Lösungen |
| `arch.md` | Architektur-Manifest - Infrastruktur & Datenfluss |
| `ki.md` | KI- & Agenten-Verzeichnis - LLMs und Python-Agenten |

---

## Aktueller Entwicklungsstand

Wir haben **Phase 3 (Agent Pipeline v2)** erfolgreich abgeschlossen!
Das System besteht nun aus einer vollwertigen, entkoppelten Multi-Agenten-Architektur, die auf einer massiven TimescaleDB-Datenbasis (Phase 2) operiert.

### ✅ Was wirklich steht (Stand Phase 4.2)
- **Infrastruktur:** Trennung von `bruno-backend` (FastAPI) und `bruno-worker` (Agent Orchestrator) in Docker.
- **Data Foundation:** TimescaleDB Hypertables für 1m-Candles, Orderbook-Snapshots, Liquidations und Funding Rates.
- **Ingestion Agent V2:** Multiplex WebSocket Echtzeit-Anbindung an 5 Binance-Streams inkl. Batch-Inserts zur DB-Schonung.
- **Quant Agent V2:** Multi-Timeframe Analyse (5m, 1h) mittels nativem `pandas`/`numpy` (RSI, ATR, MACD) direkt aus aggregierten TimescaleDB Views.
- **Sentiment Agent V2:** News-Deduplizierung via Redis und Ollama-Inferenz.
- **Risk Agent V2:** DeepSeek-R1 gestützte Entscheidungsfindung mit Kelly Criterion Position-Sizing.
- **Agenten-Zentrale (UI):** Premium Dashboard zur Steuerung und Überwachung.
    - **Chat-Interface:** Direkte Interaktion mit jedem Agenten für Transparenz.
    - **Control-Center:** Manuelles Starten, Stoppen und Resetten einzelner Agenten.
    - **Metric-Overview:** Echtzeit-Status, Fehlerzähler und Uptime.
    - **Info-Modal:** Vollständige Erklärung der Agenten-Logik und Datenquellen.

### 🎯 Nächster Schritt: Phase 4.3 (Finalisierung & Lasttest)
**WICHTIGSTE AUFGABE:** Durchführung eines Paper-Trading-Lasttests unter Echtzeit-Bedingungen. Validierung der UI-Performance bei hoher Log-Dichte im neuen Terminal.


---

*Letzte Aktualisierung: 2026-03-26 - Honest State Update nach Phase 3*
