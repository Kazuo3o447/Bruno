# Architektur-Manifest

> **Windows-Hybrid-Plattform für asynchronen Multi-Agenten Trading**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Infrastruktur-Stack

### Docker Desktop (WSL2)
Alle Container-Services laufen in Docker Desktop mit WSL2-Backend:

| Service | Technologie | Zweck |
|---------|-------------|-------|
| **PostgreSQL** | TimescaleDB + pgvector | Zeitserien-Daten, Vektor-Embeddings |
| **Redis** | Redis Stack | Caching, Pub/Sub, Message Queue |
| **FastAPI** | Python ASGI | Backend API, Agenten-Endpoints |
| **Frontend** | Next.js + React | "Bruno" - Trading Dashboard |

---

## Die LLM-Brücke

### Native Windows-Ollama
- **Ollama läuft NATIV auf dem Windows-Host**
- Direkter Zugriff auf **AMD RX 7900 XT GPU**
- Keine Docker-Passthrough-Komplexität
- Keine WSL2-Kompilierungsprobleme

### Docker-Kommunikation
Container greifen auf Ollama zu via:
```
http://host.docker.internal:11434
```

**Vorteile dieser Architektur:**
- Minimale Latenz durch nativen GPU-Zugriff
- Keine ROCm/WSL2-Kompatibilitätsprobleme
- Einfache Skalierung der Container unabhängig vom LLM

---

## Datenfluss-Architektur

### 1. Echtzeit-Datenstrom
```
Binance/CryptoPanic WebSocket (ccxt)
            ↓
      Redis Pub/Sub
            ↓
    Agenten (Python)
            ↓
   TimescaleDB (Aggregation)
```

### 2. Kommunikations-Pfade
- **Redis Streams**: High-Frequency Trading-Daten
- **Redis Pub/Sub**: Agenten-Kommunikation
- **PostgreSQL**: Persistente Marktdaten, Trades, Logs
- **FastAPI WebSocket**: Frontend-Updates

### 3. Agenten-Integration
| Agent | Input | Output |
|-------|-------|--------|
| Ingestion | WebSocket APIs | Redis Streams |
| Quant | Redis + TimescaleDB | Redis Signals |
| Sentiment | News + LLM | Sentiment-Score |
| Risk | Alle Agent-Signals | Veto/Approval |
| Execution | Risk-Clearance | Order-APIs |

---

## Technische Spezifikationen

### Zeitreihen-Datenbank
- **TimescaleDB** für hypertable-optimierte Kursdaten
- **pgvector** für Sentiment-Embeddings
- Automatische Partitionierung nach Zeit

### Caching & Messaging
- **Redis Streams** für Event-Sourcing
- **RedisJSON** für strukturierte Daten
- **RediSearch** für Volltext-Suche (Logs)

### API Layer
- **FastAPI** mit Pydantic-Validierung
- **WebSocket** für Echtzeit-Frontend-Updates
- **CORS** für Next.js-Integration
- **Backup-API** für API-gesteuerte PostgreSQL-Backups (pg_dump -Z 9)

---

## Smart Backup System

### Überblick
Das System verfügt über ein hocheffizientes, API-gesteuertes Backup-Modul für die PostgreSQL-Datenbank:

| Feature | Implementierung |
|---------|-----------------|
| **Kompression** | pg_dump `-Z 9` (maximale Kompression) |
| **Format** | Custom Format (`-Fc`) für schnelle Wiederherstellung |
| **Ausführung** | Asynchron via FastAPI BackgroundTasks |
| **Speicherort** | `./backups` (gemountet in Container) |
| **UI** | Next.js Admin-Panel unter `/backup` |

### API-Endpunkte
| Methode | Endpoint | Beschreibung |
|---------|----------|--------------|
| `GET` | `/api/v1/backups` | Liste aller Backups |
| `POST` | `/api/v1/backups/create` | Backup asynchron starten |
| `DELETE` | `/api/v1/backups/{filename}` | Backup löschen |
| `GET` | `/api/v1/backups/download/{filename}` | Backup herunterladen |
| `POST` | `/api/v1/backups/cleanup?max_age_days=14` | Alte Backups aufräumen |

### Sicherheitsmerkmale
- **Path Traversal Protection**: Nur Dateien im `/app/backups` Verzeichnis
- **Async Execution**: Keine Timeouts bei großen Datenbanken
- **Automatische Bereinigung**: Löschung von Backups älter als 14 Tage

---

## Backend Core & API-Fundament

### Architektur-Komponenten
| Komponente | Technologie | Zweck |
|------------|-------------|-------|
| **FastAPI** | Python ASGI | REST API, WebSocket Server |
| **SQLAlchemy 2.0** | async ORM | Datenbank-Models, Migrationen |
| **Redis** | async Client | Caching, Streams, Pub/Sub |
| **httpx** | async HTTP | Ollama-Client (Windows-Brücke) |
| **WebSockets** | FastAPI | Live-Daten Streaming |

### Datenbank-Schema
| Tabelle | Zweck | Besonderheiten |
|---------|-------|----------------|
| `market_candles` | TimescaleDB Hypertable | Zeitserien-Daten, Primär-Key: (time, symbol) |
| `trade_audit_logs` | Trade-Historie | Agent-Scores, LLM-Reasoning |
| `news_embeddings` | pgvector Vektoren | 1536-Dimension Embeddings |
| `agent_status` | Agenten-Monitoring | Heartbeat, Performance-Metriken |
| `system_metrics` | System-Überwachung | API-Latenz, WebSocket-Connections |
| `alerts` | Benachrichtigungen | Priority, Read/Resolved Status |

### WebSocket-Streams
| Endpoint | Daten | Update-Intervall |
|----------|-------|-----------------|
| `/ws/market/{symbol}` | Orderbook, Ticker, Candle | 1 Sekunde |
| `/ws/agents` | Agenten-Status | 2 Sekunden |
| `/ws/system` | System-Metriken | 5 Sekunden |
| `/ws/alerts` | Alerts & Notifications | 3 Sekunden |

### LLM-Integration
| Feature | Modell | Anwendungsfall |
|---------|--------|---------------|
| **Primary** | `qwen2.5:14b` | Sentiment-Analyse, schnelle Reasoning |
| **Reasoning** | `deepseek-r1:14b` | Trading-Analyse, strategische Planung |
| **Bridge** | `host.docker.internal:11434` | Windows-Hybrid GPU-Zugriff |

### Redis-Datenflüsse
| Pattern | Zweck | Beispiel |
|---------|-------|---------|
| **Cache** | Temporäre Daten | `market:ticker:BTCUSDT` |
| **Streams** | Event-Sourcing | `raw:market:data` |
| **Pub/Sub** | Agenten-Kommunikation | `signals:quant` |
| **Singleton** | Connection Pooling | `redis_client` |

---

## Netzwerk-Topologie

```
┌─────────────────────────────────────────────────────────┐
│                      Windows Host                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Docker Desktop (WSL2)               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │  Redis   │ │ PostgreSQL│ │ FastAPI  │        │   │
│  │  │  :6379   │ │  :5432   │ │  :8000   │        │   │
│  │  └──────────┘ └──────────┘ └──────────┘        │   │
│  └─────────────────────────────────────────────────┘   │
│         ↑                              │               │
│         │ host.docker.internal:11434   │               │
│  ┌──────┴──────────────────────────────▼──────┐       │
│  │          Ollama (native Windows)             │       │
│  │          http://localhost:11434              │       │
│  │              AMD RX 7900 XT                  │       │
│  └─────────────────────────────────────────────┘       │
│                                                         │
│  ┌─────────────────────────────────────────────┐        │
│  │         Next.js Frontend (Bruno)            │        │
│  │            http://localhost:3000             │        │
│  └─────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

---

## System-Status

### ✅ Phase 2 & 3 Backend + Frontend - Produktivbereit

| Komponente | Status | Details |
|------------|--------|---------|
| **FastAPI Backend** | ✅ Produktiv | Health-Check, CORS, WebSocket, Backup API |
| **PostgreSQL** | ✅ Produktiv | TimescaleDB + pgvector, 9 Tabellen |
| **Redis** | ✅ Produktiv | Singleton Connector, Caching, Streams |
| **WebSocket Server** | ✅ Produktiv | 4 Live-Streams, Disconnect Handling |
| **LLM Bridge** | ⚠️ Optional | Client implementiert, Ollama nicht gestartet |
| **Frontend** | ✅ Produktiv | Next.js, Tailwind, Dashboard, Charts, WebSocket |
| **Quant Agent** | ✅ Produktiv | RSI(14), NumPy, Warmup, Threading, Redis Pub/Sub |

### 🎯 Erreichbarkeit
| Service | URL | Status |
|---------|-----|-------|
| Frontend "Bruno" | http://localhost:3000 | ✅ |
| FastAPI Backend | http://localhost:8000 | ✅ |
| API Docs | http://localhost:8000/docs | ✅ |
| Quant Agent Status | http://localhost:8000/api/v1/agents/status/quant | ✅ |
| PostgreSQL | localhost:5432 | ✅ |
| Redis | localhost:6379 | ✅ |

### 📊 Live-Daten Flow (Aktiv)
```
Binance WebSocket → Quant Agent (RSI) → Redis Pub/Sub → Frontend Dashboard
```

### 🚀 System-Status (2026-03-26)
- **Docker Container:** 4/4 laufen
- **Binance API:** Live BTC/USDT: 69.696 USD
- **Quant Agent:** RSI: 42.05 | Signal: 0
- **Paper-Trading:** Bereit

---

*Letzte Aktualisierung: 2026-03-26 - Phase 2 komplett getestet & produktivbereit*
