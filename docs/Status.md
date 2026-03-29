# Bruno Trading Platform — Project Status

> **Referenz: WINDSURF_MANIFEST.md v2.0 — Einzige Quelle der Wahrheit**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT** für lokale LLM-Inferenz (Ollama native)
> 
> Dieses Dokument zeigt den technischen Ist-Stand.
> Für Architektur, Phasen und Entscheidungen siehe Manifest.

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Versions-Info

| Attribut | Wert |
|----------|------|
| **Manifest Version** | `v2.0` |
| **Codename** | Fundament & Ehrlichkeit |
| **Status** | ✅ Phase A COMPLETED — Phase B AKTIV |
| **Repository** | https://github.com/Kazuo3o447/Bruno |

---

## Aktueller Fokus: Phase B — Daten-Erweiterung

> 🔧 **Wir bauen auf Windows:** Docker Desktop (WSL2) + Native Ollama auf RX 7900 XT

**Ziel:** Phase A abgeschlossen — Bot ist "ehrlich" mit 100% echten Daten.

### Phase A ✅ COMPLETED (2026-03-29)
- [x] **ContextAgent**: Alle `random.uniform()` und `random.random()` entfernt
- [x] **GRSS-Berechnung**: 100% echte Daten (keine Mocks)
- [x] **BTC 24h Change**: Aus Redis `market:ticker:BTCUSDT` berechnet
- [x] **Binance REST**: Open Interest, OI-Delta, L/S-Ratio, Perp-Basis
- [x] **Deribit Public API**: Put/Call Ratio, DVOL (kostenlos, kein Key)
- [x] **GRSS-Funktion**: echte Implementierung (Manifest Abschnitt 5)
- [x] **QuantAgent**: Polling 5s → 300s
- [x] **ContextAgent**: Polling 60s → 900s
- [x] **CVD State**: In Redis persistiert
- [x] **Data-Freshness Fail-Safe**: GRSS bricht auf 0.0 ab bei stale data
- [x] **Live-Trading Guard**: `LIVE_TRADING_APPROVED` Flag implementiert
- [x] **CryptoPanic Health**: Health-Telemetrie integriert

### Phase B Aufgaben (Woche 2–3)
- [ ] CoinGlass API Integration ($29/Monat)
- [ ] Telegram Notifications
- [ ] Erweiterte Daten-Quellen (Funding Rates, Liquidations)
- [ ] Bybit Integration für Live-Trading

**Eiserne Regel:** Phase A ist abgeschlossen. Keine Zufallsdaten mehr im System.

---

## System-Status (Ist-Stand)

### ✅ Funktioniert
- Docker Compose Stack (PostgreSQL/TimescaleDB, Redis, FastAPI, Next.js)
- 6 Agenten registriert und startfähig
- IngestionAgent: Binance WebSocket (5 Streams)
- Frontend Dashboard mit Agenten-Zentrale
- LLM-Infrastruktur (Ollama, qwen2.5:14b, deepseek-r1:14b)
- DRY_RUN-Schutz aktiv
- **Phase A COMPLETE**: Alle `random.uniform()` entfernt, 100% echte Daten
- **Data-Freshness Fail-Safe**: GRSS bricht bei stale data auf 0.0 ab
- **Live-Trading Guard**: `LIVE_TRADING_APPROVED` Flag implementiert
- **CryptoPanic Health**: Health-Telemetrie mit Latenz-Tracking

### ⚠️ Bekannte Probleme
- **ExecutionAgent**: Kein Position-Tracker, keine Exit-Logik (Phase D)

### ❌ Fehlt Noch (nach Phase A)
- Position Tracker (kritischer Pfad für Live-Trading)
- Stop-Loss / Take-Profit Handler
- LLM-Kaskade (3 Layer)
- Bybit Integration (Phase B)
- Telegram Notifications
- Backtest Engine

---

## Roadmap (Manifest v2.0 Phasen)

| Phase | Zeitraum | Fokus |
|-------|----------|-------|
| **A** | ✅ COMPLETED | Fundament — Echte Daten, keine Mocks |
| **B** | Woche 2–3 | Daten-Erweiterung (CoinGlass API, Telegram) — AKTIV |
| **C** | Woche 3–5 | LLM-Kaskade (3 Layer) |
| **D** | parallel | Position Tracker + Stop-Loss |
| **E** | parallel | Frontend Cockpit |
| **F** | Woche 5–7 | Lern-System |
| **G** | Woche 7–9 | Backtest (6 Monate, PF > 1.5) |
| **H** | Woche 9–10 | Live-Start (500 EUR, -2% Daily Loss Limit) |

---

## Dokumenten-Hierarchie

1. **WINDSURF_MANIFEST.md** — Einzige Quelle der Wahrheit
2. **docs/arch.md** — Architektur & Datenfluss
3. **docs/ki.md** — Agenten-Implementierung
4. **docs/agent.md** — Arbeitsregeln
5. **docs/log.md** — Fehler & Lösungen
6. **docs/status.md** — Dieses Dokument (Ist-Stand)

---

*Siehe WINDSURF_MANIFEST.md v2.0 für vollständige Spezifikation*
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

### Phase A: Fundament & Ehrlichkeit ✅ COMPLETED
- [x] ContextAgent: Alle `random.uniform()` entfernt
- [x] GRSS-Funktion: 100% echte Daten
- [x] Binance REST: OI, OI-Delta, L/S-Ratio, Perp-Basis
- [x] Deribit Public: PCR, DVOL
- [x] QuantAgent: Polling 5s → 300s
- [x] ContextAgent: Polling 60s → 900s
- [x] CVD State: In Redis persistiert
- [x] Data-Freshness Fail-Safe: GRSS bricht bei stale data auf 0.0 ab
- [x] Live-Trading Guard: `LIVE_TRADING_APPROVED` Flag
- [x] CryptoPanic Health-Telemetrie

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

*Letzte Aktualisierung: 2026-03-29 — Phase A COMPLETED, Phase B AKTIV*
