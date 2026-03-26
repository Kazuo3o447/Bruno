# Bruno Trading Bot

> **Multi-Agent Bitcoin Trading Bot mit Windows-Hybrid-Architektur**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## 🎯 Projekt-Übersicht

Bruno ist ein hochmoderner, asynchroner Trading Bot für Kryptowährungen, der auf einer Windows-Hybrid-Architektur läuft. Das System kombiniert Docker Desktop für Backend-Services mit nativem Windows für LLM-GPU-Zugriff.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM:** Native Windows Ollama mit qwen2.5:14b und deepseek-r1:14b
- **Agenten:** 5 spezialisierte Python-Agenten (Ingestion, Quant, Sentiment, Risk, Execution)

---

## 🚀 Quick Start

### Voraussetzungen
- Docker Desktop (WSL2)
- Windows mit AMD GPU (für LLM)
- Node.js 18+ (für Frontend)
- Python 3.11+ (wird in Docker verwendet)

### Installation
```bash
# Repository klonen
git clone https://github.com/Kazuo3o447/Bruno.git
cd Bruno

# Alle Services starten
docker compose up -d

# Frontend aufrufen
open http://localhost:3000/dashboard
```

---

## 📊 Dashboard Features

- **Live Trading Chart** mit BTC/USD Candlesticks
- **Echtzeit-Agenten-Monitor** mit CPU/RAM Metriken
- **System-Status** für API, DB, Redis, WebSocket
- **Backup-Management** mit pg_dump Komprimierung

---

## 🤖 Agenten-Architektur

| Agent | Aufgabe | Status |
|-------|--------|--------|
| **Ingestion** | Binance WebSocket Daten | ✅ V2 Online |
| **Quant** | Technische Analyse & Signale | ✅ V2 Online |
| **Sentiment** | LLM-basierte News-Analyse | ✅ V2 Online |
| **Risk** | Risiko-Bewertung & Veto | ✅ V2 Online |
| **Execution** | Paper-Trading Ausführung | ✅ V2 Online |

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

- **[Status.md](docs/Status.md)** - Projekt-Status & Roadmap
- **[arch.md](docs/arch.md)** - Architektur-Manifest
- **[agent.md](docs/agent.md)** - Agenten-Core Rules
- **[ki.md](docs/ki.md)** - KI & LLM Infrastruktur
- **[log.md](docs/log.md)** - Fehler-Logbuch

---

## 🎯 Aktuelle Phase

**Phase 4: Agenten-Zentrale & UI-Oversight - ABGESCHLOSSEN**

✅ Harmonisiertes Premium Layout  
✅ WebSocket Log-Terminal mit Filterung  
✅ Agenten-Steuerungs-Panel (Start/Stop/Reset)  
✅ Interaktiver Agent-Chat & Transparenz-Modals  
✅ Lightweight Charts v5 Fix  

**Nächste Phase: Live-Testing & Performance-Audit**

---

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei

---

**Entwickelt mit ❤️ für algorithmischen Krypto-Handel**
