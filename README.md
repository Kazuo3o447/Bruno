# Bruno Trading Bot

> **Medium-Frequency Bitcoin Trading Bot — Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT**
> ✅ **Trading-Engine:** Deterministischer Composite Scorer mit TA + Liquidity + Macro
> ✅ **Risk-Stack:** Daily Drawdown, Breakeven-Stop, Trade-Cooldown
> ✅ **Legacy LLM:** Nur noch für Post-Trade-Debrief / Analyse, nicht für Entscheidungen
> ✅ **Dashboard:** Live-Daten, Decision Feed und Agent-Status

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## 🎯 Projekt-Identität (Manifest v2.0)

| Parameter | Wert |
|---|---|
| **Strategie** | Medium-Frequency (5–15 Minuten Signale) |
| **Startkapital** | 500 EUR |
| **Execution-Börse** | **Bybit** (Futures, max 1.0× Leverage) |
| **Daten-Börse** | **Binance** (WebSocket + REST) |
| **LLM-Stack** | Legacy (v1): Ollama lokal für Post-Trade-Debrief / Reasoning |
| **Dev-Umgebung** | Windows + Ryzen 7 7800X3D + RX 7900 XT (native Ollama) |
| **Dashboard** | Next.js mit Live-API-Integration und Preset-System |
| **Ports** | Backend:8000, Frontend:3000, API:/api/v1, WS:/ws/* |
| **Local Config** | DB_HOST=localhost, REDIS_HOST=localhost, NEXT_PUBLIC_API_URL=http://localhost:8000 |
| **Config** | Hot-Reload mit 3 Presets (Standard, Konservativ, Aggressiv) |

**Primäre Ziele:** Stabilität & Transparenz vor Rendite. Keine HFT-Logik. Keine Zufallsdaten. Keine LLM-Entscheidungskette.

> ⚠️ **WICHTIG:** Alle Architekturentscheidungen sind in `WINDSURF_MANIFEST.md` dokumentiert. Dieses Dokument überschreibt alle anderen bei Widerspruch.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM (Legacy):** Native Windows Ollama nur für Post-Trade-Debrief und historische Analyse
- **Agenten:** 7 spezialisierte Python-Agenten (Ingestion, Technical, Quant, Context, Sentiment, Risk, Execution)
- **Container:** Docker Compose mit Service-Orchestrierung
- **Port-Konfiguration:** API-Aufrufe über `/api/v1`, WebSockets über `ws://localhost:8000/ws/*` (korrigiert)
- **Local Development:** Alle Services auf localhost (Docker Container-Namen entfernt)

---

## 🚀 Quick Start

> 🔧 **Primäre Entwicklungsumgebung:** Windows mit Docker Desktop (WSL2) + Native Ollama auf RX 7900 XT

### Einfaches Starten mit den neuen Skripten:

**Option 1 - Vollautomatisch (Empfohlen):**
```powershell
# Startet Backend und Frontend automatisch
.\start_bruno.ps1
```

**Option 2 - Individuell:**
```powershell
# Nur Backend starten
.\start_backend.ps1

# Nur Frontend starten (nach Backend-Start)
.\start_frontend.ps1
```

**Option 3 - Manuell (für Entwickler):**
```powershell
# Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (neues Terminal)
cd frontend
npm run dev
```

## ⚙️ Wichtige Konfigurationsänderungen

### Konfiguration für verschiedene Umgebungen:

#### **Lokale Entwicklung (Empfohlen):**
**Backend Konfiguration (`backend/app/core/config.py`):**
```python
DB_HOST: str = "localhost"
REDIS_HOST: str = "localhost"
```

**Umgebungsvariablen (`.env`):**
```
DB_HOST=localhost
REDIS_HOST=localhost
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### **Docker-Entwicklung:**
**Umgebungsvariablen (`.env`):**
```
DB_HOST=postgres
REDIS_HOST=redis
NEXT_PUBLIC_API_URL=http://api-backend:8000
```

**Wichtig für Docker-Builds:** Die Umgebungsvariable `NEXT_PUBLIC_API_URL` muss während des Build-Prozesses übergeben werden, da Next.js sie statisch einbettet.

**Frontend WebSocket URLs (universell):**
Alle Komponenten verwenden die `runtimeUrls.ts` Helper:
```typescript
import { getBrowserWebSocketUrl, getBrowserApiUrl } from "../utils/runtimeUrls";

// WebSocket URL:
const wsUrl = getBrowserWebSocketUrl("/ws/agents");

// API URL:  
const apiUrl = getBrowserApiUrl("/api/v1/health");
```

### Package Installation:
```bash
cd backend
pip install alembic transformers torch --index-url https://download.pytorch.org/whl/cpu
```

## 🛠️ Troubleshooting & Häufige Probleme

### Portkonflikte (Gelöst!)
**Symptom:** `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)`

**Lösung:** Die neuen Startskripte lösen dies automatisch:
- `start_backend.ps1` findet automatisch freie Ports (8000-8010)
- Beendet blockierende Prozesse automatisch
- Passt Konfiguration dynamisch an

### Ollama Verbindungsprobleme
**Symptom:** `Request URL is missing an 'http://' or 'https://' protocol`

**Lösung:** Stelle sicher, dass Ollama läuft:
```bash
# Ollama Service starten (wenn installiert)
ollama serve

# Modelle pullen
ollama pull qwen2.5:14b
ollama pull deepseek-r1:14b
```

### WebSocket Verbindungsfehler
**Symptom:** Frontend zeigt keine Live-Daten/Agent-Status

**Lösung:** 
1. Backend mit `start_backend.ps1` starten
2. Frontend mit `start_frontend.ps1` starten  
3. Browser: http://localhost:3000

### Docker Build-Probleme mit Umgebungsvariablen
**Symptom:** Frontend verliert nach Neubuild die Backend-Verbindung

**Lösung:**
- Umgebungsvariable `NEXT_PUBLIC_API_URL` muss als Build-Argument übergeben werden
- Docker-Compose und Dockerfile wurden für persistente Builds konfiguriert
- Nach Änderungen: `docker-compose up -d --build bruno-frontend`

### Datenbankverbindungsprobleme
**Symptom:** `Connection refused` oder `getaddrinfo failed`

**Lösung:**
- PostgreSQL muss laufen auf localhost:5432
- Datenbank `bruno_trading` muss existieren
- Benutzer `bruno` mit Passwort `bruno_secret`

### Redis Verbindungsprobleme  
**Symptom:** Redis Connection failed

**Lösung:**
- Redis Server muss laufen auf localhost:6379
- Windows: Redis für Windows installieren

## 📋 Startskript-Features

### `start_backend.ps1`
- ✅ Automatische Portkonflikt-Erkennung
- ✅ Dynamische Port-Zuweisung (8000-8010)
- ✅ Automatisches Beenden blockierender Prozesse
- ✅ Echtzeit-Statusüberwachung

### `start_frontend.ps1` 
- ✅ Backend-Connectivity Check
- ✅ Konfigurationsvalidierung
- ✅ WebSocket-Verbindungstest

### `start_bruno.ps1`
- ✅ Vollautomatische Orchestrierung
- ✅ Paralleles Starten von Backend + Frontend
- ✅ PID-Management für einfaches Stoppen
- ✅ Übersichtlicher Systemstatus

## 🚀 Quick Start

> 🔧 **Primäre Entwicklungsumgebung:** Windows mit Docker Desktop (WSL2) + Native Ollama auf RX 7900 XT

### Voraussetzungen
- **Hardware:** Windows mit Ryzen 7 7800X3D + AMD RX 7900 XT GPU (für native LLM-Inferenz)
- Docker Desktop (WSL2)
- Node.js 18+ (für Frontend)
- Python 3.11+ (wird in Docker verwendet)

### Installation
```bash
# Repository klonen
git clone https://github.com/Kazuo3o447/Bruno.git
cd Bruno

# Umgebungsvariablen konfigurieren (Docker-korrekt)
# Environment-Datei ist bereits für Docker konfiguriert:
# DB_HOST=postgres, REDIS_HOST=redis, NEXT_PUBLIC_API_URL=http://api-backend:8000

# Vollständiger Container-Neustart (empfohlen für stabile Port-Konfiguration)
docker compose down --volumes
docker compose up -d --build

# Frontend aufrufen
open http://localhost:3000/dashboard
```

### Service-Status nach Start
```bash
# Alle Services prüfen
docker compose ps
# Erwartete Ports: Backend:8000, Frontend:3000, PostgreSQL:5432, Redis:6379

# Logs überwachen
docker compose logs -f worker-backend  # Agenten-Aktivität
docker compose logs -f api-backend     # API-Aufrufe (sollte 200 OK zeigen)
docker compose logs -f bruno-frontend  # Frontend-Logs

# API-Endpunkte testen
curl http://localhost:8000/api/v1/health
curl http://localhost:3000/api/v1/health  # Über Next.js Proxy
```

---

## 📊 Dashboard Features

### ✅ Voll implementiert (Stand April 2026)

**Dashboard v2.1 — 4 Sections:**
- **Section 1: Trading & Market** — Live Chart, Position P&L, Market Data, Sentiment & Bias, GRSS Components
- **Section 2: Decision Analysis** — Top 3 Blockers, Blocker Distribution Chart, Recent Decisions Timeline
- **Section 3: Pipeline Status** — 6-Gate Status (CLEAR/BLOCKED), Active Blocker Chain
- **Section 4: System Health** — Agent Status, Data Sources Health

**Neue Logic Page (`/logic`):**
- 6-Gate Pipeline Visualisierung
- GRSS Score Composition (VIX 25%, Macro 25%, Yields 15%, PCR 15%, Funding 10%, Sentiment 10%)
- Composite Scoring Radar Chart
- Decision Timeline über 30 Zyklen
- Top Blocker Statistiken
- Agent Pipeline Status

**Features:**
- **Live BTC-Preis** mit 24h/1h Änderungen
- **GRSS-Score** mit real-time Updates (0-100 Skala)
- **Agenten-Status** mit Health-Monitoring
- **Trading Chart** mit Candlesticks
- **Sentiment & Bias** (News, Retail Score, F&G, P/C Ratio)
- **Performance-Metriken** (simuliert in DRY_RUN)
- **WebSocket Logs** mit Echtzeit-Updates
- **System-Status** für API, DB, Redis, WebSocket

### API-Endpunkte (alle aktiv)
```
✅ /api/v1/telemetry/live                    - System-Status
✅ /api/v1/market/grss-full                 - GRSS-Daten
✅ /api/v1/decisions/feed                   - Decision-Feed für Timeline
✅ /api/v1/monitoring/phase-a/status      - GRSS Breakdown & Sentiment
✅ /api/v1/monitoring/debug/trade-pipeline  - 6-Gate Pipeline Status
✅ /api/v1/positions/open                   - Offene Positionen
✅ /api/v1/performance/metrics              - Performance-Kennzahlen
✅ /api/v1/config                           - Konfiguration
```

---

## 🤖 Agenten-Architektur (7 Agenten)

| Agent | Aufgabe | Börse | Status |
|-------|---------|-------|--------|
| **Ingestion** | Binance WebSocket Daten | Binance | ✅ V2 Online |
| **Technical** | TA Engine (EMA, RSI, MTF, Wick) | Binance | ✅ V2 Online |
| **Quant** | Composite Scoring (OFI, CVD, Liquidity) | Binance | ✅ V4 Online |
| **Context** | GRSS-Berechnung, Makro-Daten | FRED/Deribit | ✅ V2 Online |
| **Sentiment** | LLM-basierte News-Analyse | RSS/CryptoCompare/CoinMarketCap | ✅ V2 Online |
| **Risk** | Risiko-Bewertung & 6 Hard Vetos | — | ✅ V2 Online |
| **Execution** | **Bybit Futures** Order-Ausführung | Bybit | ✅ V3 Online |

**Execution-Details:**
- Börse: Bybit Unified Account (Futures)
- Order-Typ: Limit/PostOnly (Maker-Fee 0.01% vs Taker 0.055%)
- Mindest-Order: 0.001 BTC
- Max-Leverage: 1.0× (Kapitalschutz)

---

## 🛠️ Technologien

### Backend
- **FastAPI** - ASGI Web Framework
- **PostgreSQL** - TimescaleDB + pgvector
- **Redis** - Caching, Streams, Pub/Sub
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database Migrations

### Frontend
- **Next.js 14** - React Framework
- **TypeScript** - Type Safety
- **TailwindCSS** - Utility CSS
- **Lightweight Charts** - Trading Charts

### LLM Integration (Legacy v1)
- **Ollama** - Native Windows LLM Server, nur für Post-Trade-Debrief
- **qwen2.5:14b** - Legacy Reasoning Model
- **deepseek-r1:14b** - Legacy Debrief Model

---

## 📈 Performance-Ziele

| Metrik | Ziel | Aktuell |
|--------|------|---------|
| End-to-End Latenz | < 2 Sekunden | ✅ ~1.5s |
| LLM-Debrief (Legacy) | < 500ms (14B-Modelle) | ✅ ~300ms |
| Daten-Aktualität | < 100ms (WebSocket) | ✅ ~50ms |
| Agenten-Durchsatz | > 1000 Nachrichten/Sekunde | ✅ ~1200/s |

---

## 📚 Dokumentation

> **Reihenfolge beachten:** Manifest > Architektur > Status > Rest

| Dokument | Zweck | Status |
|----------|-------|--------|
| **[WINDSURF_MANIFEST.md](WINDSURF_MANIFEST.md)** | 🎯 **Einzige Quelle der Wahrheit** | ✅ Aktuell |
| **[docs/arch.md](docs/arch.md)** | Infrastruktur-Stack & Börsen-Architektur | ✅ Aktuell |
| **[docs/status.md](docs/status.md)** | Aktueller Projekt-Status | ✅ Aktuell |
| **[docs/ki.md](docs/ki.md)** | LLM-Infrastruktur (Ollama, Modelle) | ✅ Aktuell |
| **[docs/agent.md](docs/agent.md)** | Agenten-Core Rules | ✅ Aktuell |
| **[docs/trading_logic_v2.md](docs/trading_logic_v2.md)** | Trading Logic v2 (Deterministisch) | ✅ Aktuell |
| **[docs/api_fixes.md](docs/api_fixes.md)** | API-Verbindung & Fehlerbehebung | ✅ Neu |

---

## 🎯 Implementierungs-Phasen (Manifest v2.0)

**Aktuell: Phase E — Dashboard Integration & Port-Korrektur (COMPLETED)**
- [x] Phase A ✅ COMPLETED — Fundament & Ehrlichkeit (alle `random.uniform()` entfernt)
- [x] Phase B ✅ COMPLETED — Daten-Erweiterung & Hardening
- [x] Phase C ✅ COMPLETED — Legacy LLM-Kaskade (3 Layer, nur für Post-Trade-Debrief) & Bruno Pulse
- [x] Phase D ✅ COMPLETED — Position Tracker + Stop-Loss im Worker verdrahtet
- [x] Phase E ✅ COMPLETED — Frontend Cockpit (Bruno Pulse Dashboard Integration)
- [x] Phase E ✅ COMPLETED — Port-Architektur & WebSocket-Optimierung
- [ ] Phase F — Lern-System
- [ ] Phase G — Backtest (6 Monate, PF > 1.5)
- [ ] Phase H — Live-Start (500 EUR, -2% Daily Loss Limit)

**Neuste Implementierungen (April 2026):**
- ✅ **Deterministische Entscheidungslogik:** Composite Scorer ersetzt LLM-Cascade in der Trade-Entscheidung
- ✅ **Technical Analysis Engine:** EMA, RSI, VWAP, ATR, MTF, Wick, S/R
- ✅ **Liquidity Intelligence:** Cluster-Magneten, OI-Delta, 3× Sweep-Konfirmation
- ✅ **Risk Stack:** Daily Drawdown, Trade-Cooldown, Breakeven-Stop
- ✅ **Decision Feed:** Deterministische Score-Ausgabe für Dashboard und Execution

---

## 🔧 Troubleshooting

### Häufige Probleme & Lösungen
```bash
# Problem: Keine Daten im Dashboard
Lösung: Environment-Datei prüfen (DB_HOST=postgres, REDIS_HOST=redis)

# Problem: API-Aufrufe geben 404
Lösung: Port-Konfiguration prüfen - sollte /api/v1 verwenden

# Problem: WebSocket-Verbindung fehlgeschlagen
Lösung: WebSocket-URLs müssen localhost:3000/ws/* verwenden

# Problem: "Cannot call send once close message has been sent"
Lösung: Backend neu starten - WebSocket-Fehlerbehebung implementiert

# Problem: Frontend zeigt hartcodierte localhost:8001 Fehler
Lösung: Vollständiger Container-Neustart mit sauberen Volumes
docker compose down --volumes && docker compose up -d --build
```

### Port-Konfiguration prüfen
```bash
# Environment-Datei prüfen
cat .env | grep -E "(HOST|PORT|API_URL)"
# Erwartet: DB_HOST=postgres, REDIS_HOST=redis, NEXT_PUBLIC_API_URL=http://api-backend:8000

# API-Endpunkte testen
curl http://localhost:8000/api/v1/health      # Backend direkt
curl http://localhost:3000/api/v1/health      # Über Next.js Proxy

# WebSocket-Verbindung testen
# Browser-Konsole: new WebSocket("ws://localhost:3000/ws/agents")
```

---

## ⚠️ Eiserne Regeln (Aus Manifest)

```
❌ NIEMALS: random.uniform() in produktivem Code
❌ NIEMALS: Polling < 60s für Quant/Context/Risk
❌ NIEMALS: Echte Orders bei DRY_RUN=True
❌ NIEMALS: Position ohne Stop-Loss UND Take-Profit
❌ NIEMALS: API-Keys im Repository
```

**Break-Even:** ~12–16% p.a. auf 500 EUR nach Kosten (~50–67 EUR/Monat)

---

## 📞 Support & Kontakt

**Dashboard:** http://localhost:3000/dashboard  
**Logic Page:** http://localhost:3000/logic  
**API-Dokumentation:** http://localhost:8000/docs  
**Repository:** https://github.com/Kazuo3o447/Bruno

**Letztes Update:** 4. April 2026 - Dashboard v2.1 mit Logic Page, 4 Sections, GRSS Composition
