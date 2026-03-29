# Bruno Trading Bot

> **Medium-Frequency Bitcoin Trading Bot — Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT** für lokale LLM-Inferenz (Ollama native)

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

**Primäre Ziele:** Stabilität & Transparenz vor Rendite. Keine HFT-Logik. Keine Zufallsdaten.

> ⚠️ **WICHTIG:** Alle Architekturentscheidungen sind in `WINDSURF_MANIFEST.md` dokumentiert. Dieses Dokument überschreibt alle anderen bei Widerspruch.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM:** Native Windows Ollama mit qwen2.5:14b und deepseek-r1:14b
- **Agenten:** 5 spezialisierte Python-Agenten (Ingestion, Quant, Sentiment, Risk, Execution)

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

# Alle Services starten
docker compose up -d

# Frontend aufrufen
open http://localhost:3000/dashboard
```

### API-Keys (siehe Manifest Abschnitt 11)
| API | Kosten | Wann benötigt |
|-----|--------|---------------|
| Bybit API | Kostenlos | Phase D (Live-Trading) |
| FRED API | Kostenlos | Phase A |
| CryptoPanic | Kostenlos | Phase A |
| CoinGlass | $29/Monat | Nach 4W stabilem DRY_RUN |

---

## 📊 Dashboard Features

- **Live Trading Chart** mit BTC/USD Candlesticks
- **Echtzeit-Agenten-Monitor** mit CPU/RAM Metriken
- **System-Status** für API, DB, Redis, WebSocket
- **Backup-Management** mit pg_dump Komprimierung

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

| Metrik | Ziel |
|--------|------|
| End-to-End Latenz | < 2 Sekunden |
| LLM-Inferenz | < 500ms (14B-Modelle) |
| Daten-Aktualität | < 100ms (WebSocket) |
| Agenten-Durchsatz | > 1000 Nachrichten/Sekunde |

---

## 📚 Dokumentation

> **Reihenfolge beachten:** Manifest > Architektur > Status > Rest

| Dokument | Zweck |
|----------|-------|
| **[WINDSURF_MANIFEST.md](WINDSURF_MANIFEST.md)** | 🎯 **Einzige Quelle der Wahrheit** — immer zuerst lesen |
| **[docs/arch.md](docs/arch.md)** | Infrastruktur-Stack & Börsen-Architektur |
| **[docs/status.md](docs/status.md)** | Aktueller Projekt-Status |
| **[docs/ki.md](docs/ki.md)** | LLM-Infrastruktur (Ollama, Modelle) |
| **[docs/agent.md](docs/agent.md)** | Agenten-Core Rules |
| **[docs/log.md](docs/log.md)** | Fehler-Logbuch |

---

## 🎯 Implementierungs-Phasen (Manifest v2.0)

**Aktuell: Phase D — Position Tracker & Stop-Loss (Core implementiert)**
- [x] Phase A ✅ COMPLETED — Fundament & Ehrlichkeit (alle `random.uniform()` entfernt)
- [x] Phase B ✅ COMPLETED — Daten-Erweiterung & Hardening
- [x] Phase C ✅ COMPLETED — LLM-Kaskade (3 Layer)
- [x] Phase D — Position Tracker + Stop-Loss im Worker verdrahtet
- [ ] Phase D — SL/TP Tests mit echten Preisen validieren
- [ ] Phase E — Frontend Cockpit
- [ ] Phase F — Lern-System
- [ ] Phase G — Backtest (6 Monate, PF > 1.5)
- [ ] Phase H — Live-Start (500 EUR, -2% Daily Loss Limit)

**Kommend:**
- Phase D — Echte SL/TP-Validierung und Live-Test-Fahrten
- Phase E — Frontend Cockpit
- Phase F — Lern-System
- Phase G — Backtest (6 Monate, PF > 1.5)
- Phase H — Live-Start (500 EUR, -2% Daily Loss Limit)

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
