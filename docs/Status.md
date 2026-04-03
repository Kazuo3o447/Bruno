# Bruno Trading Platform — Project Status

> **Referenz: WINDSURF_MANIFEST.md v2.0 — Einzige Quelle der Wahrheit**
> 
> ✅ **Entwicklungsumgebung:** Windows mit **Ryzen 7 7800X3D + AMD RX 7900 XT** für lokale LLM-Inferenz (Ollama native)
> ✅ **Dashboard:** Voll funktionsfähig mit Live-API-Integration
> ✅ **Port-Architektur:** Vollständig korrigiert und stabilisiert
> ✅ **Critical Fixes:** Alle 8 kritischen Probleme behoben
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
| **Status** | ✅ Phase A COMPLETED — Phase B COMPLETED — Phase C COMPLETED — Phase D COMPLETED — Phase E COMPLETED — Phase F COMPLETED — Phase G.0 COMPLETED |
| **Dashboard** | ✅ Voll funktionsfähig mit API-Integration |
| **Port-Konfiguration** | ✅ Vollständig korrigiert (Backend:8000, Frontend:3000, API:/api/v1, WS:/ws/*) |
| **Critical Fixes** | ✅ Alle 8 Probleme behoben (API, Config, OFI, Presets) |
| **Repository** | https://github.com/Kazuo3o447/Bruno |
| **Letztes Update** | 3. April 2026 (Learning Mode, Phantom Trades, trade_mode-Tagging, abgeschlossen) |

---

## 🎯 Aktueller Fokus: Phase F — Critical Fixes & Config-Hot-Reload (COMPLETED)

> 🚀 **System-Status:** Voll funktionsfähig mit allen kritischen Fixes implementiert
> 📊 **Dashboard-Status:** Alle API-Endpunkte erreichbar, Live-Daten funktionieren
> 🔧 **Container-Status:** Vollständig neu aufgebaut mit sauberen Volumes und stabiler Konfiguration
> ⚙️ **Config-System:** Hot-Reload implementiert, Presets verfügbar

**Ziel:** Vollständiges Cockpit mit Live-Daten, Agenten-Status und Trading-Chart. Das Dashboard ist jetzt vollständig implementiert und funktionsfähig.

### Aktueller Zusatz-Fokus: Phase G.0 — Learning Mode (DRY_RUN only) ✅ COMPLETED

**Ziel:** Mehr Paper-Trades und deutlich mehr auswertbare HOLD-Daten, ohne die Produktionslogik zu kontaminieren.

**Implementiert:**
- DRY_RUN-aware GRSS-Threshold: 40 → 25 im Learning Mode
- DRY_RUN-aware LLM Confidence-Schwellen: 0.60/0.65 → 0.50/0.55 im Learning Mode
- `trade_mode`-Markierung in `trade_audit_logs` und `trade_debriefs`
- Phantom Trades für HOLD-Zyklen mit 240 Minuten Outcome-Tracking
- Scheduler-Auswertung der Phantom Trades alle 30 Minuten

**Eiserne Regel:** Learning Mode wirkt nur bei `DRY_RUN=True`. Bei `DRY_RUN=False` gelten immer die Produktions-Schwellen.

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

### Phase B ✅ COMPLETED (2026-03-29)
- [x] CoinGlass graceful degradation ohne API-Key
- [x] Telegram Notifications mit Chat-ID-Auth
- [x] Erweiterte Daten-Quellen (Funding Rates, Liquidations)
- [x] Profit-Factor-Tracking aus realisierter P&L-Historie
- [x] Phase-B Verifikationsendpoint mit echten Checks
- [x] Bybit Live-Trading bleibt gesperrt, bis `LIVE_TRADING_APPROVED=True`

### Phase C ✅ COMPLETED (2026-03-30)
- [x] LLM Cascade Core (3-Layer) implementiert & verifiziert
- [x] **Bruno Pulse**: Echtzeit-Transparency für Agenten & Kaskade
- [x] Regime Manager mit 2-Bestätigungs-Logik
- [x] QuantAgent Integration mit Cascade-Aufruf
- [x] LLM Cascade API Router für Monitoring
- [x] LLM Provider Architektur mit JSON-Reliability
- [x] Regime Config v2 mit Transition Buffer

### Phase D ✅ COMPLETED (2026-03-31)
- [x] PositionTracker Core Service (Redis Live-State + DB Audit)
- [x] PositionMonitor Background Service (SL/TP Automation)
- [x] Positions API Router mit Test Endpoints
- [x] Database Migration für Positions Table
- [x] Integration mit ExecutionAgentV3 im Worker
- [x] RiskAgent vol_multiplier Bug gefixt
- [x] Performance-Metrics API Endpunkt hinzugefügt
- [x] Docker-Netzwerk und API-Verbindung optimiert

### Phase E ✅ COMPLETED (2026-03-31)
- [x] Dashboard API-Integration (alle Endpunkte aktiv)
- [x] Next.js Proxy-Konfiguration für Docker-Netzwerk
- [x] lightweight-charts "Object is disposed" Fehler behoben
- [x] Live BTC-Preis und GRSS-Score im Dashboard
- [x] Agenten-Status mit Health-Monitoring
- [x] Trading Chart mit Candlesticks und Preis-Changes
- [x] WebSocket Logs mit Echtzeit-Updates
- [x] Container-Neustart mit vollständiger API-Integration

**Eiserne Regel:** Phase A-E abgeschlossen. Dashboard voll funktionsfähig.

---

## System-Status (Ist-Stand)

### ✅ Funktioniert
- **Bruno Pulse: Real-time Transparenz (Sub-States & LLM Pulse)**
- **Background Heartbeat Architecture** (robuster gegen LLM-Blockaden)
- **Dashboard mit Live-API-Integration** (voll funktionsfähig)
- **Docker Compose Stack** (Postgres, Redis, FastAPI, Next.js)
- **6 Agenten registriert und startfähig**
- **IngestionAgent: Binance WebSocket (5 Streams)**
- **LLM-Infrastruktur** (Ollama, qwen2.5:14b, deepseek-r1:14b)
- **Phase A-E Complete**: 100% echte Daten + LLM-Kaskade + Dashboard
- **API-Endpunkte** alle aktiv (telemetry, market, decisions, positions, performance)
- **Trading Chart** mit robustem lightweight-charts
- **Container-Netzwerk** mit korrektem Routing

### ⚠️ Bekannte Probleme
- **GRSS-Score oft niedrig** (< 40) → Veto-Modus, System im Standby (korrektes Verhalten)
- **Performance-Metriken leer** in DRY_RUN (normal, da keine echten Trades)

### ✅ Kürzlich Gelöst (2026-04-03 - Learning Mode)
- **Learning Mode vorbereitet:** config.json um Learning-Mode-Keys erweitert
- **RiskAgent:** effektive GRSS-Schwelle ist jetzt DRY_RUN-aware
- **LLM Cascade:** Confidence-Schwellen lesen jetzt Learning-Mode-Konfiguration
- **ExecutionAgentV3:** `trade_mode` wird im Audit-Log mitgeschrieben
- **QuantAgent:** HOLD-Zyklen erzeugen Phantom Trades für Debrief-Training
- **Scheduler:** Phantom-Trade-Auswertung wird im 30-Minuten-Loop angestoßen
- **Dokumentation:** Manifest, `docs/ki.md` und `docs/data.md` sind aktualisiert

### ✅ Kürzlich Gelöst (2026-04-02 - Critical Fixes)
- **Doppeltes Prefix behoben:** export, config, decisions Router Endpunkte jetzt erreichbar
- **Fresh-Source-Gate repariert:** Health-Reporting für alle 5 Datenquellen implementiert
- **Config-Hot-Reload:** QuantAgent & RiskAgent lesen config.json live ohne Neustart
- **OFI Schema korrigiert:** Frontend min=10 statt 200, bessere Beschreibungen und Warnungen
- **Preset-System implementiert:** 3 Presets (Standard, Konservativ, Aggressiv) mit visueller Auswahl
- **Gate-Schwelle optimiert:** Von <= 0 auf < 2 für bessere GRSS-Verfügbarkeit
- **Startup Warm-Up:** ContextAgent initialisiert Datenquellen sofort nach Start
- **API-Endpunkte verifiziert:** Alle kritischen Endpunkte geben 200 OK

### ✅ Kürzlich Gelöst (2026-03-31 - Port-Korrektur)
- **Vollständige Port-Architektur korrigiert:** Alle localhost:8001 URLs auf /api/v1 umgestellt
- **WebSocket-Optimierung:** Alle WebSockets verwenden jetzt localhost:3000/ws/*
- **Environment-Konfiguration:** DB_HOST=postgres, REDIS_HOST=redis statt localhost
- **Container-Neustart:** Vollständiger Neuaufbau mit sauberen Volumes für stabile Port-Konfiguration
- **WebSocket-Fehlerbehebung:** "Cannot call send once close message" behoben
- **Frontend-URL-Korrekturen:** 10+ Dateien mit Port-Problemen systematisch korrigiert
- **Next.js Proxy:** WebSocket-Proxy /ws/* hinzugefügt für stabile Verbindungen

### ✅ Kürzlich Gelöst (2026-03-31 - API-Integration)
- **Dashboard API-Verbindung**: Docker-Netzwerk und Next.js Proxy korrigiert
- **lightweight-charts Fehler**: "Object is disposed" vollständig behoben
- **RiskAgent Bug**: vol_multiplier Variable in allen Code-Pfaden initialisiert
- **API-Routing**: Fehlende /api/v1 Prefix für decisions und config hinzugefügt
- **Container-Neustart**: Vollständiger Neuaufbau mit sauberen Volumes
- **Performance-Endpunkt**: /api/v1/performance/metrics implementiert

### ✅ Kürzlich Gelöst (2026-03-30)
- **API Rate Limit Probleme**: Alle API-Blockaden behoben
  - VIX: CBOE CSV Fallback (offizielle Quelle, kein Rate Limit)
  - Reddit: OAuth + Anonym Fallback (kein 429 mehr)
  - StockTwits: Graceful Skip (keine 403-Fehler mehr)
  - Alpha Vantage: NDX Fallback implementiert (QQQ als Proxy)
  - HuggingFace: Token-Integration für schnellere Model-Downloads
- **API Keys Implementiert**: Alle kritischen API-Keys sind aktiv
  - ✅ FRED_API_KEY: US Treasury Yields working
  - ✅ CRYPTOPANIC_API_KEY: v2 API working (20 posts)
  - ✅ ALPHA_VANTAGE_API_KEY: NDX Fallback working

### ✅ Kürzlich Gelöst (2026-03-31)
- **Dashboard Health-/Status-Mapping**: Frontend normalisiert jetzt `online`, `healthy`, `connected`, `success` und `running` als grüne Zustände
  - `SystemMatrix` liest den echten Core-Health-Endpoint `/health` statt Platzhalterwerte
  - Die Datenquellen-Ansicht akzeptiert zusätzlich Warnzustände wie `degraded` und zeigt sie gelb statt rot
  - `systemtest/news_health` wird jetzt korrekt ausgewertet, auch wenn Feeds `healthy` statt `success` liefern

### ❌ Fehlt Noch (nach Phase D)
- Bybit Live-Trading-Freigabe (Phase H)
- Backtest Engine (Phase G)
- Vollständige Auswertung der Learning-Mode-Daten über mehrere Tage

---

## Roadmap (Manifest v2.0 Phasen)

| Phase | Zeitraum | Fokus |
|-------|----------|-------|
| **A** | ✅ COMPLETED | Fundament — Echte Daten, keine Mocks |
| **B** | ✅ COMPLETED | Daten-Erweiterung & Hardening |
| **C** | Woche 3–5 | LLM-Kaskade (3 Layer) — AKTIV |
| **D** | ✅ CORE IMPLEMENTED | Position Tracker + Stop-Loss |
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

*Letzte Aktualisierung: 2026-03-30 — API-Stabilität erreicht, alle 6 Agenten laufen stabil*
