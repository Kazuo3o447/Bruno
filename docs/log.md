# Fehler-Logbuch

> **Systematische Dokumentation von kritischen Bugs und deren Lösungen**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Log-Struktur

Jeder Eintrag folgt diesem Schema:

| Feld | Beschreibung |
|------|--------------|
| **Datum** | YYYY-MM-DD |
| **Fehler-Beschreibung** | Was ist passiert? |
| **Ursache** | Root-Cause-Analyse |
| **Lösung** | Code-Anpassung / Workaround |

---

## Log-Einträge

### 2026-03-29 | Phase B Hardening Audit — Kapitalschutz, DRY_RUN-Telemetrie und Doku-Sync

**Fehler-Beschreibung:**
Die Phase-B-Statuslage war fachlich korrekt, aber zwei mittlere Audit-Punkte waren noch nicht sauber aufgelöst: MLOps-/Config-Drift rund um `Max_Leverage` und eine hardcodierte `DRY_RUN`-Anzeige in der Live-Telemetrie. Zusätzlich spiegelten mehrere Dokumente den alten Phase-B-Stand noch nicht vollständig wider.

**Ursache:**
- `backend/app/routers/monitoring.py` lieferte MLOps-Parameter ohne Normalisierung/Drift-Hinweis.
- Die Live-Telemetrie zeigte `dry_run: True` als festen Platzhalter statt den echten Runtime-Wert.
- README, Status- und Architektur-Dokumente enthielten noch den alten 1.5×-Leverage-Text und offene Phase-B-To-dos.

**Lösung:**
- MLOps-Endpoint normalisiert `Max_Leverage` jetzt auf `1.0` und meldet Drift explizit im `safety_guard`.
- Live-Telemetrie nutzt jetzt `settings.DRY_RUN` statt eines Hardcodes.
- README, `docs/status.md`, `docs/arch.md`, `docs/agent.md`, `docs/ki.md` und `BRUNO_REVIEW.md` wurden auf den aktuellen Phase-B-Stand synchronisiert.

**Dateien geändert:**
- `backend/app/routers/monitoring.py`
- `README.md`
- `docs/status.md`
- `docs/arch.md`
- `docs/ki.md`
- `docs/agent.md`
- `BRUNO_REVIEW.md`

---

### 2026-03-26 | Entscheidung für Windows-Hybrid-Setup (Ryzen 7 7800X3D + RX 7900 XT)

> ✅ **Primäre Umgebung:** Windows mit **Ryzen 7 7800X3D + RX 7900 XT** (native Ollama)

**Fehler-Beschreibung:**
ROCm-Passthrough der AMD RX 7900 XT in WSL2/Docker nicht stabil möglich. Kompilierungsfehler und Treiber-Inkompatibilitäten verhindern GPU-Accelerated LLM-Inferenz in Containern.

**Ursache:**
- Windows WSL2 hat keinen nativen ROCm-Support
- Docker Desktop GPU-Passthrough für AMD experimentell/nicht stabil
- Hohe Komplexität bei Treiber-Abstimmung zwischen Host und Container

**Lösung:**
Entscheidung für **Windows-Hybrid-Architektur** (Ryzen 7 7800X3D + RX 7900 XT):
- Ollama läuft nativ auf Windows-Host (direkter GPU-Zugriff)
- Alle anderen Services (Backend, Frontend, DBs) in Docker Desktop (WSL2)
- Kommunikation via `http://host.docker.internal:11434`
- Vermeidung von ROCm/WSL2-Problemen vollständig

---

### 2026-03-27 | Sentiment Agent konnte nicht gestartet werden

**Fehler-Beschreibung:**
Im Frontend unter "Agenten" konnte der Sentiment Agent nicht gestartet werden. Der API-Call gab zwar "success" zurück, aber der Agent blieb im Status "stopped".

**Ursache:**
ID-Diskrepanz zwischen `agents_status.py` (API) und `worker.py` (Orchestrator):
- `AGENT_DEFINITIONS` in `agents_status.py` enthielt den Eintrag `"sentiment"`
- Der Worker in `worker.py` registrierte aber nur: `ingestion`, `quant`, `context`, `risk`, `execution`
- Der `SentimentAgent` war nie implementiert worden (leere `sentiment.py`)

Wenn der Orchestrator das "start"-Kommando empfing, prüfte er `if agent_id not in self._agents` → `sentiment` war nicht in `_agents` → stilles `return False` ohne Fehlermeldung.

**Lösung:**
1. `SentimentAgent`-Klasse erstellt (`app/agents/sentiment.py`) basierend auf `PollingAgent`
2. Nutzt bestehenden `SentimentAnalyzer` Service (FinBERT, CryptoBERT, Zero-Shot)
3. Import in `worker.py` hinzugefügt: `from app.agents.sentiment import SentimentAgent`
4. Registrierung im Orchestrator: `orchestrator.register("sentiment", SentimentAgent(deps))`

**Dateien geändert:**
- `backend/app/agents/sentiment.py` (neu)
- `backend/app/worker.py` (Import + Registrierung)

---

### 2026-03-26 | GPU-Passthrough in Docker unter Windows

**Fehler-Beschreibung:**
AMD GPU (RX 7900 XT) war nicht für Ollama in Docker verfügbar. Versuche, ROCm/WSL2 mit GPU-Passthrough zu konfigurieren, scheiterten an Kompilierungsfehlern und Treiber-Inkompatibilitäten.

**Ursache:**
- Docker Desktop auf Windows hat keinen direkten GPU-Passthrough für AMD/ROCm
- WSL2-Kernel unterstützt ROCm nicht nativ
- ROCm-Container benötigen spezifische Treiber, die in WSL2 nicht verfügbar sind
- Hohe Latenz durch Emulationsschichten

**Lösung:**
Verzicht auf Docker-Passthrough zugunsten eines **nativen Windows-Ollama-Hosts** (Ryzen 7 7800X3D + RX 7900 XT):
- Ollama wird direkt auf Windows installiert (nicht in Docker)
- AMD RX 7900 XT wird nativ vom Windows-Treiber angesprochen
- Docker-Container greifen via `http://host.docker.internal:11434` auf Ollama zu
- Architektur-Update: Windows-Hybrid statt reinem Docker-Setup

**Code-Anpassung:**
```yaml
# docker-compose.yml - Ollama-Container entfernt
# Stattdessen: Ollama lokal auf Windows-Host

services:
  # ollama:  <-- ENTFERNT
  #   image: ollama/ollama
  #   ...

  fastapi:
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
```

**Learnings:**
- GPU-Passthrough unter Windows + Docker + AMD ist nicht produktionsreif
- Hybride Architekturen (nativer Host + Docker) sind pragmatischer
- `host.docker.internal` ist zuverlässig für Host-Dienste

---

## Platzhalter für zukünftige Einträge

### YYYY-MM-DD | [Titel]

**Fehler-Beschreibung:**
[...]

**Ursache:**
[...]

**Lösung:**
[...]

---

## 2026-03-26 | Windows Docker Desktop Context Error

**Fehler-Beschreibung:**
Versuche, `docker compose ps` oder `docker ps` auszuführen, führten zu dem kritischen Fehler:
`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine: Das System kann die angegebene Datei nicht finden.`
Das Frontend war nicht mehr erreichbar, obwohl die Container scheinbar liefen.

**Ursache:**
Docker Desktop auf Windows nutzt standardmäßig den Context `desktop-linux` über eine Named Pipe, die abstürzen oder hängen bleiben kann. Die Verbindung zur Docker Engine im WSL2-Backend wurde unterbrochen.

**Lösung:**
Restart der Docker Desktop Engine und/oder manueller Wechsel auf den Standard-Kontext:
`docker context use default`
Dies stellt die reibungslose Kommunikation zum WSL2-Docker-Daemon wieder her.

---

## 2026-03-26: Live Marktdaten & News Integration

| Feld | Beschreibung |
|------|--------------|
| **Datum** | 2026-03-26 |
| **Fehler-Beschreibung** | Dashboard zeigt keine Live-Preise, News sind Mock-Daten, Agenten haben keine echten Marktdaten |
| **Ursache** | 1. Ingestion Agent veröffentlicht keine Ticker-Daten<br>2. Sentiment Agent hat keine fetch_news Methode<br>3. Database Insert Fehler mit MarketCandle Objects<br>4. RSS Feeds nicht integriert |
| **Lösung** | 1. Ingestion: _handle_kline Methode mit Redis Ticker Publishing<br>2. Sentiment: Vollständige RSS Integration mit Keyword-Analyse<br>3. Database: MarketCandle Objects → Dicts Konvertierung<br>4. RSS Feeds: Cointelegraph & Coindesk Integration |
| **Status** | ✅ BEHOBEN |
| **Testergebnis** | Dashboard zeigt BTC/USDT 68,975 USD mit echten RSS-News |

---

### 2026-03-26 | Phase 1: Architecture Refactoring Abgeschlossen

**Fehler-Beschreibung (Initial-Zustand):**
Alle 5 Agenten liefen als asynchrone Tasks im selben FastAPI-Webserver (`main.py`). Ein Crash im Quant-Agenten konnte den Webserver blockieren, was zu massiven Architektur-Risiken führte.

**Lösung & Architektur-Split:**
Die Monolith-Architektur wurde in ein **Producer/Consumer Muster** zerlegt:
- **`bruno-backend`** (API-Container): Rein für REST/Websockets, `main.py` komplett von Agenten-Code bereinigt.
- **`bruno-worker`** (Agent-Container): Ein neuer Prozess (`worker.py`), der von dem maßgeschneiderten `AgentOrchestrator` kontrolliert wird.
- **`BaseAgent` DI-Pattern:** Jeder Agent erhält Dependencies (`AgentDependencies`) injiziert, ohne auf fehleranfällige globale Instanzen zuzugreifen.
- Strikte Message Contracts (`QuantSignalV2`, etc.) in Redis publiziert.

**Ergebnis:**
Docker Compose startet nun API und Worker als isolierte, hoch-performante Einheiten parallel.

---



**Fehler-Beschreibung:**
- `redis:alpine` unterstützte keine modernen Module (JSON, Search, Streams-Management), die laut Dokumentation vorausgesetzt wurden.
- Fehlende Docker-Healthchecks führten zu Race-Conditions beim Startup (Backend versuchte DB zu verbinden, bevor diese bereit war).

**Ursache:**
- Zu minimalistisches Basis-Image gewählt.
- Standard-Docker-Compose ohne Lifecycle-Management.

**Lösung:**
- **Redis Upgrade:** Umstellung auf `redis/redis-stack-server:latest` für volle Unterstützung von RedisJSON und RediSearch.
- **Healthchecks:** Implementierung von `pg_isready` für PostgreSQL und `redis-cli ping` für Redis mit entsprechenden `depends_on` Conditions.

**Code-Anpassung:**
In `docker-compose.yml`:
```yaml
  redis:
    image: redis/redis-stack-server:latest
### 2026-03-26 | Redis RDB Version Mismatch

**Fehler-Beschreibung:**
Nach einem Neustart oder Image-Update verweigerte der Redis-Container den Dienst mit der Meldung: 
`Fatal error loading the DB, check server logs. Can't handle RDB format version 13. Exiting.`
Dies verhinderte die gesamte Agent-Kommunikation.

**Ursache:**
Inkompatibilität zwischen dem persistierten RDB-Snapshot im (alten) `bruno_redis_data` Volume und dem neuen `redis/redis-stack-server:latest` Image.

**Lösung:**
Löschen des korrupten Volumes für einen sauberen Neustart:
`docker volume rm bruno_redis_data`
Da Redis in diesem Setup primär als Cache und Pub/Sub-Broker dient, war der Datenverlust unkritisch.

---

### 2026-03-26 | Backend-weite Symbol-Inkonsistenz (BTC/USDT vs BTCUSDT)

**Fehler-Beschreibung:**
Der `QuantAgent` lieferte keine Daten ("Nicht genug Kerzen-Daten"), obwohl die Datenbank befüllt war. Trades wurden nicht ausgelöst.

**Ursache:**
Inkonsistente Symbol-Benennung im Code:
- Binance API & TimescaleDB: `BTCUSDT`
- Hardcoded Default in Agents/Worker: `BTC/USDT`
Die SQL-Queries suchten nach `BTC/USDT` und fanden 0 Treffer.

**Lösung:**
Vollständige Umstellung des Backends auf den Binance-Standard `BTCUSDT` (ohne Slash) in `worker.py`, `quant.py`, `sentiment.py` und `ingestion.py`.

---

### 2026-03-26 | Phase 3: Kaltstart-Datenmangel (Cold Start Data Gap)

**Fehler-Beschreibung:**
Direkt nach dem Startup funktionierte die Analyse nicht, da Indikatoren wie RSI(14) mindestens 14 Datenpunkte benötigen, die TimescaleDB-Aggregates aber Zeit zur ersten Materialisierung brauchen.

**Ursache:**
Harte Code-Anforderungen (`if len(df) < 20: return {}`) verhinderten jegliche Signale in der ersten Stunde nach System-Reset.

**Lösung:**
- Reduzierung der Mindest-Kerzen für den Initialen Test.
- Implementierung eines manuellen Trigger-Commands für Continuous Aggregates:
  `CALL refresh_continuous_aggregate('candles_5m', NULL, NULL);`
- Empfehlung: In Produktion sollte ein "Warm-up" Script historische Daten beim Start laden.

---

### 2026-03-26 | Ollama API 404 & Missing Models

**Fehler-Beschreibung:**
`SentimentAgent` und `RiskAgent` meldeten `404 Not Found` bei API-Requests an Ollama.

**Ursache:**
- Die geforderten Modelle (`qwen2.5:14b`, `deepseek-r1:14b`) waren auf dem Host noch nicht per `ollama pull` vorhanden. 
- Ollama meldet 404, wenn ein nicht-existentes Modell via `/api/generate` angesprochen wird.

**Lösung:**
- **Agent Resilience:** Implementierung eines robusten regelbasierten Fallbacks in `risk.py` und `sentiment.py`, falls der LLM-Client Fehler liefert.
- **Auto-Pull:** Initiierung der Pull-Commands direkt vom Admin-Prompt.

---

---

### 2026-03-26 | Lightweight Charts v5 API Breaking Change

**Fehler-Beschreibung:**
Das `ChartWidget` stürzte beim Laden mit dem Fehler `TypeError: chart.addCandlestickSeries is not a function` ab. Der Chart wurde nicht gerendert.

**Ursache:**
Upgrade von `lightweight-charts` auf Version ^5.1.0. In dieser Version wurden spezialisierte Methoden wie `addCandlestickSeries()` entfernt und durch eine vereinheitlichte API ersetzt.

**Lösung:**
Umstellung auf die neue `addSeries`-API:
- Import von `CandlestickSeries` aus dem Paket.
- Aufruf von `chart.addSeries(CandlestickSeries, { ... })`.

**Code-Anpassung:**
```tsx
// Vorher
const series = chart.addCandlestickSeries({ ... });

// Nachher (v5)
import { CandlestickSeries } from 'lightweight-charts';
const series = chart.addSeries(CandlestickSeries, { ... });
```

---

### 2026-03-26 | Phase 4.6: Log-System Stabilisierung (24h Retention)

**Fehler-Beschreibung:**
- Dashboard-Logs waren nach Neuladen leer.
- Keine Persistenz der Agenten-Aktivitäten über die Websocket-Sitzung hinaus.
- Fehlende Transparenz über Hintergrundprozesse der Bots.

**Ursache:**
- Logs wurden nur im Speicher gehalten oder via Pub/Sub gestreamt, aber nicht in Redis-Listen persistiert.
- `LogManager` war unvollständig und nicht in die Agenten-Pipeline integriert.

**Lösung:**
- **Redis-Persistenz:** Implementierung einer `logs:all` Liste in Redis (RPUSH).
- **24-Stunden-Limit:** Automatischer Cleanup-Task im `LogManager`, der bei jedem 10. Schreibvorgang Logs löscht, die älter als 24 Stunden sind (`LREM` basierend auf Timestamps).
- **Agenten-Integration:** `BaseAgent` und alle spezialisierten Agenten (Quant, Risk, etc.) nutzen nun den zentralen `LogManager`.
- **Health-Status:** Einführung eines `degraded` Status. Agenten melden nun im Heartbeat ihren Zustand (z.B. "degraded" wenn Ollama fehlt).

**Ergebnis:**
Das Dashboard zeigt nun auch nach einem Refresh die Aktivitäten der letzten 24 Stunden an. Warnungen und Fehler sind sofort ersichtlich und filterbar.

---

### 2026-03-26 | UI Layout Harmonization (Duplicate Sidebar)

**Fehler-Beschreibung:**
Auf den Unterseiten (`/agenten`, `/logs`, `/dashboard`) wurden zwei Sidebars angezeigt (eine globale und eine lokale), was das Layout und die Bedienbarkeit beeinträchtigte.

**Ursache:**
In Phase 4.1 wurde die `Sidebar` sowohl in `layout.tsx` als auch in jeder Seite einzeln importiert. Zudem fehlte ein einheitlicher Container-Standard.

**Lösung:**
- Entfernung aller lokalen `Sidebar`-Imports in den Page-Files.
- Verschiebung der Sidebar-Logik in das zentrale `RootLayout` (`frontend/src/app/layout.tsx`).
- Einführung eines einheitlichen Flex-Layouts mit `ml-64` Offset für den Hauptinhalt.

---

---

### 2026-03-28 | Frontend Build Error - Missing Node.js Dependencies

**Fehler-Beschreibung:**
Next.js Frontend kompilierte nicht mit dem Fehler "Failed to compile" und "Unexpected token `div`. Expected jsx identifier". Zusätzliche TypeScript-Fehler: "Cannot find module 'react'" und "Cannot find module 'lucide-react'".

**Ursache:**
- `node_modules` Verzeichnis war komplett leer
- Node.js war nicht im System PATH installiert/erreichbar
- Ohne die React/TypeScript-Module konnte der JSX-Parser die Syntax nicht korrekt interpretieren

**Lösung:**
1. **Node.js Installation:** `winget install --id OpenJS.NodeJS --source winget` (v25.8.2)
2. **PATH Update:** Manuelles Hinzufügen von `C:\Program Files\nodejs` zur PATH-Umgebungsvariable
3. **Dependencies Installation:** `npm install` (165 Pakete in 35s installiert)
4. **Container Restart:** Vollständiger Neustart aller Docker-Container

**Ergebnis:**
- Frontend kompiliert wieder erfolgreich
- Alle Container laufen normal (Frontend:3000, Backend:8000, Worker, Postgres:5432, Redis:6379)
- 1 high severity vulnerability verbleibt (kann mit `npm audit fix --force` behoben werden)

---

*Letzte Aktualisierung: 2026-03-28 — Node.js Dependencies & Container Restart abgeschlossen*
