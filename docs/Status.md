# Bruno Trading Platform — Project Status

> **Referenz: WINDSURF_MANIFEST.md v2.0 — Einzige Quelle der Wahrheit**
>
> Dieses Dokument zeigt den technischen Ist-Stand.
> Für Architektur, Phasen und Entscheidungen siehe Manifest.
>
> Erstellt: 2026-03-26 | Letzte Aktualisierung: 2026-03-28

---

## Versions-Info

| Attribut | Wert |
|----------|------|
| **Manifest Version** | `v2.0` |
| **Codename** | Fundament & Ehrlichkeit |
| **Status** | Phase A — Fundament (Woche 1–2) |
| **Repository** | https://github.com/Kazuo3o447/Bruno |

---

## Aktueller Fokus: Phase A — Fundament

**Ziel:** Den Bot ehrlich machen. Keine Zufallsdaten mehr.

### Kritische Blocker (Müssen zuerst gelöst werden)
- [ ] **ContextAgent**: Alle `random.uniform()` und `random.random()` entfernen
- [ ] **GRSS-Berechnung**: 100% echte Daten (keine Mocks)
- [ ] **BTC 24h Change**: Aus Redis `market:ticker:BTCUSDT` berechnen

### Phase A Aufgaben (Woche 1–2)
- [ ] Binance REST: Open Interest, OI-Delta, L/S-Ratio, Perp-Basis
- [ ] Deribit Public API: Put/Call Ratio, DVOL (kostenlos, kein Key)
- [ ] GRSS-Funktion: echte Implementierung (Manifest Abschnitt 5)
- [ ] QuantAgent: Polling 5s → 300s
- [ ] ContextAgent: Polling 60s → 900s
- [ ] CVD State: In Redis persistieren (nicht In-Memory)

**Eiserne Regel:** Keine Trades auf Basis von Zufallsdaten. GRSS muss echte Datenquellen nutzen.

---

## System-Status (Ist-Stand)

### ✅ Funktioniert
- Docker Compose Stack (PostgreSQL/TimescaleDB, Redis, FastAPI, Next.js)
- 6 Agenten registriert und startfähig
- IngestionAgent: Binance WebSocket (5 Streams)
- Frontend Dashboard mit Agenten-Zentrale
- LLM-Infrastruktur (Ollama, qwen2.5:14b, deepseek-r1:14b)
- DRY_RUN-Schutz aktiv

### ⚠️ Bekannte Probleme
- **ContextAgent**: ~70% der GRSS-Inputs sind `random.uniform()` — KRITISCH
- **QuantAgent**: Polling-Intervall 5 Sekunden (sollte 300s)
- **CVD**: Verliert State bei Restart (nicht in Redis)
- **ExecutionAgent**: Kein Position-Tracker, keine Exit-Logik

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
| **A** | Woche 1–2 | Fundament — Echte Daten, keine Mocks |
| **B** | Woche 2–3 | Daten + Bybit Integration |
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
