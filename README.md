# Bruno Trading Bot

> **Medium-Frequency Bitcoin Trading Bot — Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT** für lokale LLM-Inferenz (Ollama native)
> ✅ **Dashboard:** Voll funktionsfähig mit Live-Daten und API-Integration

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

**Primäre Ziele:** Stabilität & Transparenz vor Rendite. Keine HFT-Logik. Keine Zufallsdaten.

> ⚠️ **WICHTIG:** Alle Architekturentscheidungen sind in `WINDSURF_MANIFEST.md` dokumentiert. Dieses Dokument überschreibt alle anderen bei Widerspruch.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM:** Native Windows Ollama mit qwen2.5:14b und deepseek-r1:14b
- **Agenten:** 6 spezialisierte Python-Agenten (Ingestion, Quant, Context, Sentiment, Risk, Execution)
- **Container:** Docker Compose mit Service-Orchestrierung

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

# Umgebungsvariablen konfigurieren
cp .env.example .env
# BYBIT_API_KEY, BYBIT_SECRET in .env eintragen (für Phase D)

# Alle Services starten (inkl. Dashboard)
docker compose up -d --build

# Frontend aufrufen
open http://localhost:3000/dashboard
```

### Service-Status nach Start
```bash
# Alle Services prüfen
docker compose ps

# Logs überwachen
docker compose logs -f worker-backend  # Agenten-Aktivität
docker compose logs -f api-backend     # API-Aufrufe
docker compose logs -f bruno-frontend  # Frontend-Logs
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

**Aktuell: Phase D — Position Tracker & Stop-Loss (Core implementiert)**
- [x] Phase A ✅ COMPLETED — Fundament & Ehrlichkeit (alle `random.uniform()` entfernt)
- [x] Phase B ✅ COMPLETED — Daten-Erweiterung & Hardening
- [x] Phase C ✅ COMPLETED — LLM-Kaskade (3 Layer) & Bruno Pulse
- [x] Phase D ✅ COMPLETED — Position Tracker + Stop-Loss im Worker verdrahtet
- [x] Phase E ✅ COMPLETED — Frontend Cockpit (Bruno Pulse Dashboard Integration)
- [x] Phase D ✅ COMPLETED — API-Verbindung & Docker-Netzwerk
- [ ] Phase F — Lern-System
- [ ] Phase G — Backtest (6 Monate, PF > 1.5)
- [ ] Phase H — Live-Start (500 EUR, -2% Daily Loss Limit)

**Neuste Implementierungen (März 2026):**
- ✅ Docker-Container-Neustart mit vollständiger API-Integration
- ✅ "Object is disposed" Fehler in lightweight-charts behoben
- ✅ RiskAgent vol_multiplier Bug gefixt
- ✅ Performance-Metrics Endpunkt hinzugefügt
- ✅ Next.js Proxy-Konfiguration optimiert

---

## 🔧 Troubleshooting

### Häufige Probleme & Lösungen
```bash
# Problem: Keine Daten im Dashboard
 Lösung: docker compose restart api-backend bruno-frontend

# Problem: "Object is disposed" Fehler
 Lösung: Browser neu laden (F5) - Chart-Komponente wurde robust gemacht

# Problem: API-Aufrufe fehlgeschlagen
 Lösung: docker compose down --volumes && docker compose up -d --build

# Problem: GRSS-Score = 0.0 (Veto aktiv)
 Lösung: Normal - System im Standby bei schlechten Marktbedingungen
```

### API-Verbindung prüfen
```bash
# Backend-API direkt testen
curl http://localhost:8000/api/v1/telemetry/live

# Frontend-Proxy prüfen
curl http://localhost:3000/api/v1/telemetry/live
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
