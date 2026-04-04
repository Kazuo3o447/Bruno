# Architektur-Manifest

> **Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ✅ **Primäre Umgebung:** Windows mit **Ryzen 7 7800X3D + RX 7900 XT** (native Ollama)

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Infrastruktur-Stack

### Umgebungen

| Umgebung | Hardware | Zweck |
|----------|----------|-------|
| **Primär** | Windows + Ryzen 7 7800X3D + RX 7900 XT | Entwicklung, Cloud API Integration, Trading |

### Docker Services (WSL2)

> 🔧 **Docker Desktop:** Windows (WSL2-Backend) mit GPU-Passthrough

| Service | Technologie | Zweck |
|---------|-------------|-------|
| **PostgreSQL** | TimescaleDB + pgvector | Zeitserien-Daten, Positionen, Trades |
| **Redis** | Redis Stack | Caching, Pub/Sub, State-Management |
| **FastAPI** | Python ASGI | Backend API, Agenten-Orchestration |
| **Frontend** | Next.js + React | Trading Cockpit mit 4 Dashboard-Sections + Logic Page |

### Frontend Pages

| Route | Zweck | Features |
|-------|-------|----------|
| `/` (Dashboard) | **Trading Command Center** | Live Chart, Position Status, Market Data, Sentiment & Bias, GRSS Breakdown |
| `/dashboard` | **Trading View** | Detaillierte Trading-Ansicht mit allen Marktdaten |
| `/logic` | **Decision Logic** | 6-Gate Pipeline, GRSS Composition, Composite Scoring, Decision Timeline, Top Blockers |
| `/logs` | **System Logs** | Echtzeit-Logs aus allen Agenten |
| `/einstellungen` | **Settings** | Konfigurationsmanagement |

### Dashboard Abschnitte (v2.1)

**Section 1: Trading & Market**
- TradingChart (BTCUSDT) mit Lightweight Charts
- Position Panel (Live P&L, Entry, SL, TP)
- Market Data Sidebar (24h/1h Change, OFI, Funding)
- Sentiment & Bias (News Sentiment, Retail Score, F&G, P/C Ratio)
- GRSS Components (VIX, Macro Status, Yields, DVOL)

**Section 2: Decision Analysis**
- Top 3 Blockers (mit Fortschrittsbalken)
- Blocker Distribution (Bar Chart)
- Recent Timeline (20 Entscheidungen, Signal vs Blocked)

**Section 3: Pipeline Status**
- 6-Gate Pipeline Status (CLEAR/BLOCKED)
- Active Blocker Chain
- Gate Details: Data Freshness → Context → Sentiment → Quant → Risk → Portfolio

**Section 4: System Health**
- Agent Status (Ingestion, Technical, Quant, Context, Risk, Execution)
- Data Sources Health (mit Zeitstempeln)

### Neue API-Endpunkte (Dashboard v2.1)

```
✅ /api/v1/decisions/feed        - Decision Feed für Timeline
✅ /api/v1/monitoring/phase-a/status  - GRSS Breakdown & Sentiment
✅ /api/v1/monitoring/debug/trade-pipeline  - 6-Gate Pipeline Status
```

---

## Die LLM-Brücke

### Deepseek Reasoning API (Cloud)
- **Deepseek API läuft als Cloud-Service** (https://api.deepseek.com)
- **Keine lokalen Modelle mehr** - Speicher- und Ressourcen-optimiert
- **Professionelle Reasoning Engine** für Post-Trade Analyse
- **Stabile HTTPS-Verbindung** mit Retry-Logic und Fallback

**API Konfiguration:**
- **Model:** deepseek-chat (Chat & Reasoning)
- **Purpose:** Post-Trade Debrief und Learning Only
- **Response Format:** Strukturiertes JSON
- **Performance:** Sub-2s Response Times
- **Error Handling:** Graceful Fallback bei API-Ausfällen

### Docker-Kommunikation
Container greifen auf Deepseek API zu via:
```
https://api.deepseek.com/v1/chat/completions
```

**Environment Variables:**
```bash
DEEPSEEK_API_KEY=sk-2f93b3854d8b4d1f8a42e2fc00d55da3
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

---

## Börsen-Architektur (Manifest v2.0)

```
Binance WS/REST  ──► IngestionAgent + ContextAgent ──► Redis
                                                           │
                                                      alle Agenten
                                                           │
Bybit REST  ◄── ExecutionAgentV3 ◄── RiskAgent (RAM-Veto) ◄─┘
                        │
                        └──► PositionTracker (Redis Live-State + DB Audit)
```

| Börse | Nutzung | Daten |
|-------|---------|-------|
| **Binance** | Daten & Analyse | WebSocket (5 Streams), REST (OI, Funding, Perp-Basis) |
| **Bybit** | **Execution** | Unified Account Futures (max 1.0× Leverage) |
| **Deribit** | Options-Daten | Put/Call Ratio, DVOL (kostenlos, kein Key) |

**Bybit Order-Format:**
```python
{
    "category": "linear",
    "symbol": "BTCUSDT",
    "side": "Buy",
    "orderType": "Limit",
    "qty": "0.001",          # Minimum
    "price": "84500",
    "timeInForce": "PostOnly"  # Maker-Fee 0.01%
}
```

---

## Die 7-Agenten-Kaskade (v2)

| Agent | Version | Input | Output | Zweck |
|-------|---------|-------|--------|-------|
| **Ingestion** | V2 | Binance WebSocket (5 Streams) | Redis Streams | OHLCV, OFI, Liquidations, Funding |
| **Technical** | V2 | `market_candles` + Binance depth | `bruno:ta:snapshot` | EMA, RSI, VWAP, ATR, MTF, Wick, S/R |
| **Context** | V1 | Makro-Daten (FRED, Deribit, RSS) | Redis `bruno:context:grss` | **GRSS Score** (0–100) |
| **Sentiment** | V1 | RSS Feeds + CryptoCompare + CoinMarketCap | Redis `bruno:sentiment` | News- und Ereignis-Sentiment |
| **Quant** | **V4** | Redis + Orderbook + TA/Liquidity Services | Redis `bruno:quant:micro`, `bruno:liq:intelligence`, `bruno:decisions:feed` | **Composite Scoring**, MTF, Liquidity Intelligence |
| **Risk** | V2 | Alle Signals (RAM-Check) | Redis `bruno:veto:state` | **Daily Limits**, Cooldowns, **0ms Veto** |
| **Execution** | V3 | Risk + Signals | **Bybit API** | **Breakeven Stops**, PositionTracker |

### v2 Service Layer

| Service | Zweck | Integration |
|---------|-------|-------------|
| **TechnicalAnalysisAgent** | MTF-Alignment, Wick Detection, Session Bias, Orderbuch-Walls | QuantAgentV4 |
| **LiquidityEngine** | OI-Delta, Sweep Detection, Entry Confirmation | QuantAgentV4 |
| **CompositeScorer** | Dynamic Weighting, Regime Detection | QuantAgentV4 |
| **TradeDebriefV2** | Post-Trade Debrief mit Deepseek Reasoning API | ExecutionAgentV3 |

---

## Sicherheits-Isolation

### API-Key Isolation
- **PublicExchangeClient** (Quant/Context): Keine Keys nötig (Binance Public)
- **AuthenticatedExchangeClient** (Execution): Nur Bybit API-Keys

### DRY_RUN Protection
- Hardware-naher Block in ExecutionAgentV3
- Bei `DRY_RUN=True`: Keine echten Orders möglich
- Shadow-Trading mit Fee-Simulation (0.04% Taker, plus Slippage-Logging)

### Phase B Hardening (abgeschlossen)
- CoinGlass läuft im Graceful-Degradation-Modus ohne API-Key
- Telegram-Buttons und Commands sind an die konfigurierte Chat-ID gebunden
- Profit Factor wird aus realisierter P&L-Historie berechnet und per Endpoint angezeigt
- Funding- und Liquidations-Daten sind in GRSS und Status-Checks integriert

### Phase C/D Runtime (v2) - AKTUELL
- **QuantAgentV4** mit vollständiger Service-Integration
- **TechnicalAnalysisAgent**: MTF-Alignment, Wick Detection, Session Awareness, Orderbuch-Walls
- **LiquidityEngine**: OI-Delta, Sweep Detection, Entry Confirmation
- **CompositeScorer**: Dynamic Weighting, Regime-adaptive Scoring
- **RiskAgentV2**: Daily Limits (3%), Trade Cooldowns (5min)
- **ExecutionAgentV3**: Breakeven Stops, Enhanced Position Management
- **Post-Trade Analysis:** Deepseek Reasoning API für professionelle Trade-Analyse
- **Learning System:** Cloud-basierte Intelligenz für kontinuierliche Verbesserung

---

## Datenbank-Schema (Neue Migrationen)

### Migration 005: Positions
```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    side VARCHAR(10),
    entry_price FLOAT,
    entry_time TIMESTAMPTZ,
    quantity FLOAT,
    stop_loss_price FLOAT,
    take_profit_price FLOAT,
    grss_at_entry FLOAT,
    layer1_output JSONB,
    layer2_output JSONB,
    layer3_output JSONB,
    regime VARCHAR(20),
    exit_price FLOAT,
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(50),
    exit_trade_id VARCHAR(100),
    pnl_eur FLOAT,
    pnl_pct FLOAT,
    mae_pct FLOAT,
    mfe_pct FLOAT,
    hold_duration_minutes INTEGER,
    status VARCHAR(20),
    created_at TIMESTAMPTZ
);
```

### Migration 006: LLM Reasoning Trail
```sql
ALTER TABLE trade_audit_logs
ADD COLUMN llm_reasoning JSONB,
ADD COLUMN regime VARCHAR(20),
ADD COLUMN layer1_output JSONB,
ADD COLUMN layer2_output JSONB,
ADD COLUMN layer3_output JSONB;
```

---

## System-Status

### Phase A — Fundament (Woche 1–2) ✅ COMPLETED (2026-03-29)
- [x] ContextAgent: `random.uniform()` entfernt — 100% echte Daten
- [x] Binance REST: OI, OI-Delta, L/S-Ratio, Perp-Basis
- [x] Deribit Public: Put/Call Ratio, DVOL
- [x] GRSS-Funktion: echte Daten (Manifest Abschnitt 5)
- [x] Data-Freshness Fail-Safe: GRSS bricht bei stale data auf 0.0 ab
- [x] Live-Trading Guard: `LIVE_TRADING_APPROVED` Flag implementiert
- [x] CryptoCompare + CoinMarketCap Health: Health-Telemetrie integriert

### Phase B — Daten-Erweiterung (Woche 2–3) ✅ COMPLETED
- [x] CoinGlass API Integration ($29/Monat)
- [x] Telegram Notifications
- [x] Erweiterte Daten-Quellen (Funding Rates, Liquidations)

### Phase v2 — Prompt Kaskade (April 2026) ✅ COMPLETED
- [x] **TechnicalAnalysisEngine**: MTF-Alignment, Wick Detection, Session Awareness
- [x] **LiquidityEngine**: OI-Delta, Sweep Detection, Entry Confirmation
- [x] **CompositeScorer**: Dynamic Weighting, Regime Detection
- [x] **QuantAgentV4**: Service Integration, Daily Limits, Trade Cooldowns
- [x] **RiskAgentV2**: Enhanced Risk Management, Breakeven Stops
- [x] **ExecutionAgentV3**: Breakeven Stop Logic, Position Management
- [x] **Configuration**: v2 Parameters, Dynamic Thresholds
- [x] **Documentation**: Complete v2 Architecture Documentation

### Geplant: Phasen v2.1–v2.2
- [ ] Trailing Stops, Multi-Symbol Support
- [ ] Advanced Regimes, ML Integration
- [ ] Portfolio Management, Advanced Risk Analytics

---

*Referenz: WINDSURF_MANIFEST.md v2.0 — Einzige Quelle der Wahrheit*
