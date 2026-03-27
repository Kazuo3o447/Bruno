# Bruno Trading Platform — Master Architecture Plan

> **Vom Prototyp zur robusten, transparenten Trading-Plattform**
>
> **HINWEIS:** Die aktuelle Strategie ist in `WINDSURF_MANIFEST.md` dokumentiert.
> Dieses Dokument ist nur für den technischen Ist-Stand. Für alle Architektur-Entscheidungen siehe Manifest.
>
> Erstellt: 2026-03-26 | Letzte Aktualisierung: 2026-03-27

---

## Versions-Info

| Attribut | Wert |
|----------|------|
| **Version** | `0.4.0` |
| **Codename** | The Cockpit Update |
| **Status** | Phase 7.5 abgeschlossen — Alle 6 Agenten operativ |
| **Repository** | https://github.com/Kazuo3o447/Bruno |

---

## Ehrlicher Ist-Stand

### ✅ Produktiv Funktionsfähig

**Core Infrastructure:**
- [x] Docker Compose (PostgreSQL/TimescaleDB, Redis Stack, FastAPI, Next.js, Worker)
- [x] Alembic Migrations & Smart Backup System
- [x] Log Manager (Redis-basiert, 24h Persistenz + Pub/Sub)
- [x] Multi-Timeframe Candles (Continuous Aggregates 5m, 15m, 1h)

**Agenten-Pipeline (6/6 Agenten):**
- [x] **Ingestion Agent** — Binance WebSocket Multiplexing (L2 Orderbuch, Ticker, Liquidationen, Funding)
- [x] **Quant Agent** — OFI, CVD, technische Indikatoren, Signal-Generierung
- [x] **Context Agent** — Makro-Daten (Fear & Greed, DXY, ETF Flows, Treasury Yields)
- [x] **Sentiment Agent** — FinBERT/CryptoBERT + Zero-Shot Classification für News
- [x] **Risk Agent** — Multi-Faktor Konsens, Position Sizing, R:R Prüfung
- [x] **Execution Agent** — RAM-Veto (0ms), Shadow-Trading mit 0.04% Fee-Simulation

**Frontend:**
- [x] Next.js 14 + TailwindCSS + TypeScript
- [x] Agenten-Zentrale (Chat, Steuerung, Logs, Heartbeats)
- [x] MLOps Cockpit (Veto-Tracking, Slippage-Analytik, Parameter-Hub)
- [x] Lightweight Charts Integration
- [x] Real-time WebSocket (Ticker & Logs)

**Sicherheit:**
- [x] DRY_RUN Kapitalschutz (immer aktiv bis explizit deaktiviert)
- [x] Exchange Client Split (Public vs. Authenticated)
- [x] Shadow-Trading mit exakter Fee-Simulation & Slippage-Tracking

---

## Designprinzipien

| Prinzip | Bedeutung |
|---|---|
| **Transparency First** | Jede Trade-Entscheidung muss nachvollziehbar sein |
| **Crash Isolation** | Ein fehlerhafter Agent darf nie die API oder andere Agenten mitreißen |
| **Honest State** | Dokumentation spiegelt exakt den Ist-Zustand |
| **Observable** | Alles was passiert ist sichtbar — Dashboard, Logs, Alerts |
| **Pragmatic Complexity** | Nur so komplex wie nötig |

---

## Ziel-Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                        Windows Host                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                Docker Desktop (WSL2)                      │    │
│  │                                                           │    │
│  │  ┌───────────┐  ┌────────────┐  ┌───────────────────┐   │    │
│  │  │ Redis     │  │ PostgreSQL │  │ bruno-api         │   │    │
│  │  │ Stack     │  │ TimescaleDB│  │ FastAPI           │   │    │
│  │  │ :6379     │  │ + pgvector │  │ :8000             │   │    │
│  │  └─────┬─────┘  └─────┬──────┘  └────────┬──────────┘   │    │
│  │        │               │                   │              │    │
│  │        │         Redis Pub/Sub             │              │    │
│  │        │               │                   │              │    │
│  │  ┌─────┴───────────────┴───────────────────┴──────────┐  │    │
│  │  │              bruno-worker                           │  │    │
│  │  │         Agent Orchestrator Process                  │  │    │
│  │  │                                                     │  │    │
│  │  │  ┌──────────┐ ┌──────┐ ┌─────────┐ ┌────┐ ┌────┐ │  │    │
│  │  │  │Ingestion │ │Quant │ │Sentiment│ │Risk│ │Exec│ │  │    │
│  │  │  └──────────┘ └──────┘ └─────────┘ └────┘ └────┘ │  │    │
│  │  └─────────────────────────────────────────────────────┘  │    │
│  │                                                           │    │
│  │  ┌───────────────────┐                                   │    │
│  │  │ bruno-frontend    │                                   │    │
│  │  │ Next.js :3000     │                                   │    │
│  │  └───────────────────┘                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            Ollama (native Windows)                        │    │
│  │            http://localhost:11434                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Redis Channel-Architektur:**

| Channel | Publisher | Subscriber | Payload |
|---|---|---|---|
| `bruno:pubsub:signals` | Quant | Risk | Trading-Signale |
| `bruno:pubsub:veto` | Risk | Execution | Veto-Kommandos |
| `risk:decisions` | Risk | Execution, Dashboard | RiskDecision |
| `trades:executed` | Execution | Dashboard, Logging | TradeExecution |
| `heartbeat:{agent_id}` | Alle Agenten | Dashboard | AgentHeartbeat |
| `worker:commands` | API | Worker | Restart/Stop/Pause |
| `logs:live` | LogManager | Dashboard | Log Entries |

---

## Abgeschlossene Phasen (Archiv)

### Phase 0-1: Foundation & Architecture ✅
- API und Worker in separate Container
- BaseAgent Klasse mit Heartbeat, Error-Handling, Auto-Restart
- AgentOrchestrator mit Startup-Stages
- Redis Contracts (Pydantic Schemas)

### Phase 2: Data Foundation ✅
- TimescaleDB Continuous Aggregates (5m, 15m, 1h)
- Multi-Asset Datenmodell (BTC/USDT initial)
- F&G Index Integration
- Feature Store Views

### Phase 3: Agent Pipeline v2 ✅
- 5 Agenten vollständig implementiert (Quant, Sentiment, Risk, Execution + Ingestion)
- Multi-Timeframe Analyse (1m, 5m, 1h)
- Echte Sentiment-Quellen (CryptoPanic API + RSS)
- Risk Management mit Position Sizing, Stop-Loss, Take-Profit
- Trade-Decision Transparency Model (vollständige Entscheidungskette)

### Phase 4: Frontend Premium Dashboard ✅
- 6 Seiten: Dashboard, Trading, Agenten, Analyse, Backup, Logs, Einstellungen
- Agenten-Zentrale mit Chat, Steuerung, Transparenz-Modals
- MLOps Cockpit (Veto-Tracking, Slippage-Analytik)
- Lightweight Charts mit Trade-Markern

### Phase 7-7.5: Zero-Latency & MLOps ✅
- RAM-basiertes Veto-System (0ms Latenz)
- Security Layer Isolation (Public vs. Authenticated Clients)
- Shadow-Trading mit exakter 0.04% Fee-Simulation
- Native Recharts Integration (KPI Matrix, Slippage-Analytik)

---

## Roadmap: Implementierung nach WINDSURF_MANIFEST

Die Implementierung erfolgt in den Phasen A-H wie im Manifest definiert:

- **Phase A (Woche 1-2):** Fundament - echte Daten statt random.uniform()
- **Phase B (Woche 2-3):** Daten-Erweiterung (CoinGlass API, Telegram)
- **Phase C (Woche 3-5):** LLM-Kaskade (3 Layer)
- **Phase D (parallel):** Position Tracker + Exit-Logik
- **Phase E (parallel):** Frontend Cockpit (Open Position Panel, Kill-Switch)
- **Phase F (Woche 5-7):** Lern-System (Post-Trade LLM Debrief)
- **Phase G (Woche 7-9):** Backtest + Kalibrierung
- **Phase H:** Live-Freigabe

**Qualitätsziel:** System gilt als produktionsbereit wenn alle Checklisten aus Manifest erfüllt sind.

---

*Letzte Aktualisierung: 2026-03-27 — Alle 6 Agenten operational, Zero-Latency Execution aktiv*
