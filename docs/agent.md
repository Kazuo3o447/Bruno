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

## Quick-Start für neue Agenten

### ✅ Phase 4 Abgeschlossen - Vollständiges Multi-Agenten-System

**Alle 5 Kern-Agenten sind implementiert und live:**

1. **📡 Ingestion Agent** - WebSocket Daten-Sammler
2. **📊 Quant Agent** - Technische Analyse mit RSI
3. **🧠 Sentiment Agent** - LLM-basierte News-Analyse
4. **⚖️ Risk Agent** - Konfluenz-Check & Risiko-Management
5. **💰 Execution Agent** - Paper-Trading & Audit Logging

### 🔧 Technische Architektur
- **Backend:** FastAPI mit AsyncIO
- **Daten:** PostgreSQL + TimescaleDB, Redis Streams
- **Frontend:** Next.js Dashboard mit Live-Agenten-Status
- **LLM:** Ollama qwen2.5 (mit Fallback)
- **Trading:** Paper-Trading Mode (audit only)

### 📊 Live-Performance (2026-03-26)
- **System Status:** 5/5 Agenten aktiv
- **Live-Signale:** Quant BUY (RSI: 18.85)
- **Daten-Flow:** 42,451+ Ticks → Signale → PostgreSQL
- **Frontend:** Agenten Dashboard live

### 🎯 Nächste Phase
**Phase 5: Testing & Deployment**
- Unit-Tests für alle Agenten
- Integration-Tests (End-to-End)
- Paper-Trading über mehrere Tage
- Live-Trading Vorbereitung

1. Lies diese `agent.md` vollständig durch
2. Prüfe aktuellen Status in `Status.md`
3. Bei Architektur-Fragen: Lies `arch.md`
4. Bei KI/Agenten-Fragen: Lies `ki.md`
5. Beginne mit dem konkreten Task

---

## System-Status

### ✅ Phase 4: Multi-Agenten-System ABGESCHLOSSEN
- **Status:** Vollständig implementiert & live
- **Agenten:** 5/5 aktiv (Ingestion, Quant, Sentiment, Risk, Execution)
- **Frontend:** Agenten Dashboard mit Live-Status
- **Backend:** FastAPI mit Redis Pub/Sub
- **Daten:** PostgreSQL + Redis Streams
- **Trading:** Paper-Trading Mode aktiv

### 🎯 Phase 5: Testing & Deployment
- **Status:** Nächste Phase
- **Fokus:** Unit-Tests, Integration-Tests, Paper-Trading
- **Ziel:** Live-Trading Vorbereitung

| Test-Kategorie | Ergebnis | Status |
|----------------|----------|--------|
| **Docker Container** | ✅ BESTANDEN | 4/4 Container laufen |
| **Backend API** | ✅ BESTANDEN | Health-Check OK |
| **Datenbanken** | ✅ BESTANDEN | PostgreSQL (9 Tabellen), Redis |
| **Binance API** | ✅ BESTANDEN | Live BTC/USDT: 68.912 USD |
| **Agenten System** | ✅ BESTANDEN | 5/5 Agenten aktiv |
| **WebSocket** | ✅ BESTANDEN | Ports offen & stabil |

### 📊 Live-Daten Flow (Aktiv)
```
Binance WebSocket → 42,451 Ticks → Quant Agent (RSI: 18.85) → BUY Signal → Risk Agent → Execution Agent → PostgreSQL
```

### 🎯 Paper-Trading Bereit
- **Quant Agent:** Produziert live Signale
- **Dashboard:** Zeigt Echtzeitdaten
- **Risk-Management:** Alle Health-Checks aktiv
- **Backup-Management:** PostgreSQL Sicherungen

**Fazit:** Das Bruno Trading Bot System ist 100% PRODUKTIVBEREIT!

---

*Letzte Aktualisierung: 2026-03-26 - Vollsystem-Test bestanden & dokumentiert*
