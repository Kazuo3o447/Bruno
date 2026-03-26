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

1. Lies diese `agent.md` vollständig durch
2. Prüfe aktuellen Status in `Status.md`
3. Bei Architektur-Fragen: Lies `arch.md`
4. Bei KI/Agenten-Fragen: Lies `ki.md`
5. Beginne mit dem konkreten Task

---

## System-Status

### ✅ Phase 2 & 3 Backend + Frontend - Abgeschlossen

**Alle System-Komponenten sind implementiert und getestet:**
- FastAPI mit Health-Check, CORS, WebSocket, Backup API
- PostgreSQL mit TimescaleDB + pgvector (262 Tabellen)
- Redis Singleton Connector mit Caching, Streams, Pub/Sub
- Ollama Client Wrapper für Windows-Hybrid GPU-Zugriff
- WebSocket Server mit 4 Live-Daten Streams
- Next.js Frontend mit Dashboard, Charts, Agenten-Monitor

### 🎯 Nächste Prioritäten - Phase 4 Agenten
1. **Ingestion Agent** - Binance WebSocket-Daten-Sammler
2. **Quant Agent** - Technische Analyse & Signale
3. **Sentiment Agent** - LLM-basierte News-Analyse
4. **Risk Agent** - Risiko-Bewertung & Veto
5. **Execution Agent** - Paper-Trading Ausführung

---

*Letzte Aktualisierung: 2026-03-26 - Phase 2 komplett getestet & validiert*
