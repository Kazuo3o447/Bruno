# Bruno Trading Bot

> **Medium-Frequency Bitcoin Trading Bot — Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT** für lokale LLM-Inferenz (Ollama native)
> ✅ **Dashboard:** Voll funktionsfähig mit Live-Daten und API-Integration
> ✅ **Port-Architektur:** Vollständig korrigiert und stabilisiert

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## 🎯 Projekt-Identität (Manifest v2.0)

| Parameter | Wert |
|---|---|
| **Strategie** | Medium-Frequency (5–15 Minuten Signale) |
| **Startkapital** | 500 EUR |
| **Execution-Börse** | **Bybit** (Futures, max 1.0× Leverage) |
| **Daten-Börse** | **Binance** (WebSocket + REST) |
| **LLM-Stack** | Ollama lokal: qwen2.5:14b + deepseek-r1:14b |
| **Dev-Umgebung** | Windows + Ryzen 7 7800X3D + RX 7900 XT (native Ollama) |
| **Dashboard** | Next.js mit Live-API-Integration |
| **Ports** | Backend:8000, Frontend:3000, API:/api/v1, WS:/ws/* |

**Primäre Ziele:** Stabilität & Transparenz vor Rendite. Keine HFT-Logik. Keine Zufallsdaten.

> ⚠️ **WICHTIG:** Alle Architekturentscheidungen sind in `WINDSURF_MANIFEST.md` dokumentiert. Dieses Dokument überschreibt alle anderen bei Widerspruch.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM:** Native Windows Ollama mit qwen2.5:14b und deepseek-r1:14b
- **Agenten:** 6 spezialisierte Python-Agenten (Ingestion, Quant, Context, Sentiment, Risk, Execution)
- **Container:** Docker Compose mit Service-Orchestrierung
- **Port-Konfiguration:** API-Aufrufe über `/api/v1`, WebSockets über `ws://localhost:3000/ws/*`

---

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

### ✅ Voll implementiert (Stand März 2026)
- **Live BTC-Preis** mit 24h/1h Änderungen
- **GRSS-Score** mit实时 Updates (0-100 Skala)
- **Agenten-Status** mit Health-Monitoring
- **Trading Chart** mit Candlesticks und Preis-Changes
- **Performance-Metriken** (simuliert in DRY_RUN)
- **WebSocket Logs** mit Echtzeit-Updates
- **System-Status** für API, DB, Redis, WebSocket

### API-Endpunkte (alle aktiv)
```
✅ /api/v1/telemetry/live      - System-Status
✅ /api/v1/market/grss-full    - GRSS-Daten
✅ /api/v1/decisions/feed      - Decision-Feed
✅ /api/v1/positions/open      - Offene Positionen
✅ /api/v1/performance/metrics - Performance-Kennzahlen
✅ /api/v1/config              - Konfiguration
```

---

## 🤖 Agenten-Architektur (6 Agenten)

| Agent | Aufgabe | Börse | Status |
|-------|---------|-------|--------|
| **Ingestion** | Binance WebSocket Daten | Binance | ✅ V2 Online |
| **Quant** | Technische Analyse (OFI, CVD) | Binance | ✅ V2 Online |
| **Context** | GRSS-Berechnung, Makro-Daten | FRED/Deribit | ✅ V2 Online |
| **Sentiment** | LLM-basierte News-Analyse | RSS/CryptoPanic | ✅ V2 Online |
| **Risk** | Risiko-Bewertung & RAM-Veto | — | ✅ V2 Online |
| **Execution** | **Bybit Futures** Order-Ausführung | Bybit | ✅ V2 Online |

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

### LLM Integration
- **Ollama** - Native Windows LLM Server
- **qwen2.5:14b** - Primary Model
- **deepseek-r1:14b** - Reasoning Model

---

## 📈 Performance-Ziele

| Metrik | Ziel | Aktuell |
|--------|------|---------|
| End-to-End Latenz | < 2 Sekunden | ✅ ~1.5s |
| LLM-Inferenz | < 500ms (14B-Modelle) | ✅ ~300ms |
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
| **[docs/log.md](docs/log.md)** | Fehler-Logbuch | ✅ Aktuell |
| **[docs/api_fixes.md](docs/api_fixes.md)** | API-Verbindung & Fehlerbehebung | ✅ Neu |

---

## 🎯 Implementierungs-Phasen (Manifest v2.0)

**Aktuell: Phase E — Dashboard Integration & Port-Korrektur (COMPLETED)**
- [x] Phase A ✅ COMPLETED — Fundament & Ehrlichkeit (alle `random.uniform()` entfernt)
- [x] Phase B ✅ COMPLETED — Daten-Erweiterung & Hardening
- [x] Phase C ✅ COMPLETED — LLM-Kaskade (3 Layer) & Bruno Pulse
- [x] Phase D ✅ COMPLETED — Position Tracker + Stop-Loss im Worker verdrahtet
- [x] Phase E ✅ COMPLETED — Frontend Cockpit (Bruno Pulse Dashboard Integration)
- [x] Phase E ✅ COMPLETED — Port-Architektur & WebSocket-Optimierung
- [ ] Phase F — Lern-System
- [ ] Phase G — Backtest (6 Monate, PF > 1.5)
- [ ] Phase H — Live-Start (500 EUR, -2% Daily Loss Limit)

**Neuste Implementierungen (31. März 2026):**
- ✅ **Vollständige Port-Korrektur:** Alle localhost:8001 URLs auf /api/v1 korrigiert
- ✅ **WebSocket-Optimierung:** Alle WebSockets über localhost:3000/ws/*
- ✅ **Environment-Konfiguration:** DB_HOST=postgres, REDIS_HOST=redis
- ✅ **Container-Neustart:** Vollständiger Neustart mit sauberen Volumes
- ✅ **WebSocket-Fehlerbehebung:** "Cannot call send once close message" behoben
- ✅ **Frontend-URL-Korrekturen:** 10+ Dateien mit Port-Problemen korrigiert

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
**API-Dokumentation:** http://localhost:8000/docs  
**Repository:** https://github.com/Kazuo3o447/Bruno

**Letztes Update:** 31. März 2026 - Voll funktionsfähiges Dashboard mit API-Integration
