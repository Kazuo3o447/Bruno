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

Wir haben **Phase 7.5 (Shadow Trading & MLOps)** erfolgreich abgeschlossen!
Das System verfügt nun über ein professionelles Monitoring und einen exakten Audit-Trail.

### ✅ Was wirklich steht (Stand Phase 7.5)
- **Zero-Latency Core:** Der ExecutionAgent nutzt einen lokalen RAM-Veto-Check (0ms Latenz).
- **Shadow-Trading Audit:** Exakte 0.04% Fee-Simulation & Slippage-Tracking in BPS.
- **Monitoring Hub:** Natives Next.js Dashboard mit Recharts (Live-Telemetrie & MLOps).
- **MLOps Hub:** Read-Only Parameter-Vergleich (Strict MLOps Security).
- **Offline Optimizer:** PnL-Formel nach Lead Architect Standard (PF > 1.5).
- **Security Isolation:** Strikte Trennung zwischen Public & Authenticated Clients + DRY_RUN Block.

### 🎯 Nächster Schritt: Phase 8 (Stresstest & Refinement)
**WICHTIGSTE AUFGABE:** Durchführung von Lasttests unter Echtzeit-Bedingungen. Validierung der Slippage-Präzision im Dashboard bei hoher Volatilität.

---

*Letzte Aktualisierung: 2026-03-27 - Status Update nach Phase 7.5 Dashboard & Audit Integration*

