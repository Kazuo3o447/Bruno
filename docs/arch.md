# Architektur-Manifest

> **Referenz: WINDSURF_MANIFEST.md v3.0**
>
> ✅ **V3.0 Bybit Data-Hub:** Bybit V5 WebSocket als primäre "Single Source of Truth", Binance Fallback (5s Heartbeat), Institutionelle CVD mit Bybit side-Field
> ✅ **V3.0 Privacy & Stability:** CryptoPanic API (diskrete News), HF_TOKEN für HuggingFace, ConfigCache Singleton, CompositeScorer Logging Sync
> ✅ **V2.2 Institutionelle Features:** Multi-Level Exit (TP1/TP2), ATR Trailing Stop, Volume Profile VPOC, Data Gap Veto, 1m Backtester
> ✅ **V2.2 Purge Complete:** Max Pain & Google Trends entfernt, None-basierte Data-Gap-Behandlung
> ✅ **Execution-State isoliert:** Position-spezifischer State statt globaler Flags
> ✅ **Prompt 7 Score-Kalibrierung:** Confluence-Bonus, Regime-Kompensation, Ranging-aware TA/Volume/Liq
> ✅ **Primäre Umgebung:** Windows mit **Ryzen 7 7800X3D + RX 7900 XT** (Cloud API Trading Stack)

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
| **Frontend** | Next.js + React | Trading Cockpit mit 7 Seiten (Dashboard, Trading, Logic, Monitor, Logs, Reports, Settings/Journey) |

### Frontend Pages (v2.2 - Neuaufbau)

| Route | Zweck | Features |
|-------|-------|----------|
| `/` (Dashboard) | **Übersicht & Status** | 4 Key Metrics (GRSS, OFI, VIX, Funding), Entscheidungszyklen-Bar-Chart, Agenten-Grid, Datenquellen-Badges, Market Sentiment Bars, Offene Position, Chart Placeholder |
| `/trading` | **Trading Detailansicht** | 6-Gate Kaskade-Visualisierung, Quant Micro Daten, GRSS Breakdown, OFI/Metriken |
| `/logic` | **Pipeline-Visualisierung** | 6-Gate Pipeline, Decision Timeline, Blocker-Analyse |
| `/monitor` | **System-Überwachung** | API-Health Tests, Agent Heartbeats, Scheduler Steuerung, Datenquellen-Status |
| `/logs` / `/logviewer` | **System-Logging** | Live WebSocket Logs, Filter (Level/Kategorie/Quelle), Export, Auto-Scroll |
| `/reports` | **Analysen & Export** | Geschlossene Trades, Deepseek-Analysen, Lern-Logs (24h), Performance-Perioden |
| `/settings` / `/einstellungen` | **Konfiguration** | 4 Presets (Konservativ/Balanced/Opportunistisch/Test), Parameter-Editor, Exit-Management (ATR Trailing, TP1/TP2 Split), Deepseek-Test |
| `/journey` | **Dokumentation** | 7 Abschnitte: Übersicht, Agenten, Pipeline, APIs, Features, Sicherheit, Tech Stack |

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
- Multi-Level Exit Status (TP1/TP2/Trailing)

**Section 3: Pipeline Status**
- 6-Gate Pipeline Status (CLEAR/BLOCKED)
- Active Blocker Chain
- Gate Details: Data Freshness → Context → Sentiment → Quant → Risk → Portfolio

**Section 4: System Health**
- Agent Status (Ingestion, Technical, Quant, Context, Risk, Execution)
- Data Sources Health (mit Zeitstempeln)
- Volume Profile Status (VPOC Level, Bucket Distribution)

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

## Binance API Integration (v2.1)

### BinanceDataClient
**Zentraler API-Client für alle Marktdaten:**
- **Keine API Keys erforderlich** für öffentliche Endpunkte
- **Automatische Rate-Limiting** mit Connection Pooling
- **Fehlerbehandlung** mit Retry-Logic und Fallbacks

**Unterstützte Endpunkte:**
```python
# Core Market Data
get_ticker(symbol="BTCUSDT")           # Aktueller Preis
get_klines(symbol="BTCUSDT", interval="1m", limit=500)  # Candlesticks
get_orderbook(symbol="BTCUSDT", limit=100)             # Orderbuch

# Futures Data
get_funding_rate(symbol="BTCUSDT")     # Funding Rate
get_open_interest(symbol="BTCUSDT")     # Open Interest
get_liquidations(symbol="BTCUSDT")      # Liquidation Orders

# System
get_server_time()                       # Binance Server-Zeit
health_check()                          # API-Erreichbarkeit
```

### MarketDataCollector
**Automatische Datensammlung im Worker:**
- **30-Sekunden Intervall** für alle wichtigen Daten
- **Parallel Fetching** für optimale Performance
- **Redis Storage** mit verschiedenen TTLs:
  - Ticker: 10s (sehr frisch)
  - Orderbook: 5s (extrem frisch)
  - Klines: 60s (Technical Analysis)
  - Funding/OI: 300s (5 Minuten)

**Redis Keys:**
```bash
market:ticker:BTCUSDT          # {"last_price": 67263.7, "timestamp": "..."}
market:orderbook:BTCUSDT       # {"bids_volume": 1234567, "imbalance_ratio": 1.23}
market:funding:BTCUSDT         # {"fundingRate": 0.0001, "nextFundingTime": "..."}
market:liquidations:BTCUSDT    # [{"side": "SELL", "price": 67000, "qty": 0.1}]
bruno:ta:klines:BTCUSDT        # {"klines": [...], "count": 500}
market:ofi:ticks               # [{"t": "...", "r": 1.23}, ...]  # 300 Ticks
```

### Free-Tier Macro / Flow Extensions

- `bruno:binance:analytics` — Top Trader Long/Short, Taker Buy/Sell, Global Long/Short Ratio
- `bruno:onchain:data` — Blockchain.com Hash Rate / Mempool + Glassnode Exchange Balance (wenn Key vorhanden)
- `bruno:cvd:BTCUSDT` — aggTrades-basierter CVD-State mit `last_trade_id`
- Refresh: Binance Analytics 5m, On-Chain 6h, CVD kontinuierlich im Quant-Agent

---

## Börsen-Architektur (Manifest v3.0)

```
Bybit V5 WS ──► IngestionAgent + TechnicalAgent + QuantAgent ──► Redis
                                                           │
                                                      alle Agenten
                                                           │
Binance REST ◄── ContextAgent (Fallback) ◄── RiskAgent (RAM-Veto) ◄─┘
                        │
                        └──► PositionTracker (Redis Live-State + DB Audit)
```

| Börse | Nutzung | Daten |
|-------|---------|-------|
| **Bybit V5** | **Daten (Primär)** | WebSocket (kline.1, publicTrade, orderbook.50) - Single Source of Truth |
| **Binance** | **Daten (Fallback)** | REST (OI, Funding, Perp-Basis) - 5s Heartbeat Monitoring |
| **Bybit** | **Execution** | Unified Account Futures (max 1.0× Leverage) |
| **Deribit** | Options-Daten | Put/Call Ratio, DVOL (kostenlos, kein Key) |
| **Free-Tier Analytics** | Context + Flow | Binance Analytics (Top Trader / Taker Ratios) + On-Chain (Blockchain.com / Glassnode Free) + CryptoPanic News |

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

### 7-Agenten Kaskade (v2.2 - Deterministisch)

1. **IngestionAgent** - WebSocket Stream (Binance) → Redis Cache
2. **MarketAgent** - Marktdaten-Aufbereitung, Indikatoren, Sentiment
3. **QuantAgent** - Quantitative Analyse, Composite Score (deterministisch)
4. **RiskAgent** - Risiko-Management, Position-Sizing, Limits
5. **DecisionAgent** - 6-Gate Trade Pipeline (deterministisch)
6. **ExecutionAgent** - Order-Management, Slippage-Kontrolle
7. **LearningAgent** - Post-Trade Analyse mit Deepseek Reasoning API

### v2 Service Layer

| Service | Zweck | Integration |
|---------|-------|-------------|
| **TechnicalAnalysisAgent** | MTF-Alignment, Wick Detection, Session Bias, Orderbuch-Walls | QuantAgent |
| **LiquidityEngine** | OI-Delta, Sweep Detection, Entry Confirmation | QuantAgent |
| **CompositeScorer** | Dynamic Weighting, Regime Detection, Binance Analytics Flow Hooks | QuantAgent |
| **TradeDebriefV2** | Post-Trade Debrief mit Deepseek Reasoning API | ExecutionAgentV4 |
| **PositionTracker / PositionMonitor** | MAE/MFE, TP1-Scale-Out, Breakeven, ATR Trailing, SL/TP2 Runtime | ExecutionAgentV4 |

---

## Sicherheits-Isolation

### API-Key Isolation
- **PublicExchangeClient** (Quant/Context): Keine Keys nötig (Binance Public)
- **AuthenticatedExchangeClient** (Execution): Nur Bybit API-Keys

### DRY_RUN Protection
- Hardware-naher Block in ExecutionAgentV4
- Bei `DRY_RUN=True`: Keine echten Orders möglich
- Shadow-Trading mit Fee-Simulation (0.04% Taker, plus Slippage-Logging)

### Phase B Hardening (abgeschlossen)
- CoinGlass läuft im Graceful-Degradation-Modus ohne API-Key
- Telegram-Buttons und Commands sind an die konfigurierte Chat-ID gebunden
- Profit Factor wird aus realisierter P&L-Historie berechnet und per Endpoint angezeigt
- Funding- und Liquidations-Daten sind in GRSS und Status-Checks integriert

### Learning System (v2.2)
- **LearningAgent** führt Post-Trade Analyse mit Deepseek Reasoning API durch
- Keine lokalen LLMs mehr im System (Ollama entfernt in v2.1)
- Analyse wird nur für abgeschlossene Trades verwendet, nicht für Live-Entscheidungen

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

### Phase v2.2 — Institutionelle Mathematik & Complete Purge (April 2026) ✅ COMPLETED
- [x] Phase 1 ✅ COMPLETED — Execution & State-Bugs (global state fix, TP1 price trigger)
- [x] Phase 2 ✅ COMPLETED — Mathematische Kernlogik (VWAP Tages-Reset, CVD Deduplizierung, VPOC)
- [x] Phase 3 ✅ COMPLETED — Backtester Realitäts-Check (1m-Kerzen, Intrabar High/Low)
- [x] Phase 4 ✅ COMPLETED — The True Purge (Max Pain & Google Trends eliminieren)
- [x] Phase 5 ✅ COMPLETED — Full-Stack Synchronisation (regime_config.py, UI Multi-Level-Exit)
- [x] **TechnicalAnalysisEngine**: MTF-Alignment, Wick Detection, Session Awareness, VWAP Daily Reset, VPOC
- [x] **LiquidityEngine**: OI-Delta, Sweep Detection, Entry Confirmation, CVD Deduplication
- [x] **CompositeScorer**: Dynamic Weighting, Regime Detection, None-Safe Flow Scoring
- [x] **QuantAgentV4**: Service Integration, Daily Limits, Trade Cooldowns, Timestamp Guard
- [x] **RiskAgentV2**: Enhanced Risk Management, Breakeven Stops, Missing Data Veto
- [x] **ExecutionAgentV4**: Breakeven Stop Logic, Position Management, TP1/TP2 Scaling (0.01% Maker), ATR Trailing, Position-Specific State
- [x] **BacktesterV2**: 1-Minute Candles, Intrabar High/Low, Pessimism Rule
- [x] **Configuration**: v2.2 Parameters, Dynamic Thresholds, Multi-Level Exit
- [x] **Documentation**: Complete v2.2 Architecture Documentation
- [x] **Purge**: No Max Pain or Google Trends references in system

### Phase v2.1 — Ollama Entfernung & Binance API Integration (April 2026) ✅ COMPLETED
- [x] **Ollama komplett entfernt**: Keine lokalen LLMs mehr im System
- [x] **BinanceDataClient**: Neuer API-Client für alle Marktdaten
- [x] **MarketDataCollector**: Automatische Datensammlung alle 30s
- [x] **LatencyMonitor**: Bereinigt von Ollama-Abhängigkeiten
- [x] **Worker Pipeline**: Ollama-freier Start und Betrieb
- [x] **Live Marktdaten**: Ticker, Klines, Orderbook, Funding, OI, Liquidations
- [x] **Frontend Integration**: Frische Daten für Dashboard und Trading-Seite

### Phase v3.0 — Bybit Data-Hub & Core Math (April 2026) ✅ COMPLETED
- [x] Phase 1 ✅ COMPLETED — Infrastructure Upgrade & Privacy (HF_TOKEN, CryptoPanic API, Browser-Scraper Entfernung)
- [x] Phase 2 ✅ COMPLETED — Bybit V5 Primary Integration (WebSocket Client, Binance Fallback, Institutionelle CVD, VWAP Reset, VPOC)
- [x] Phase 3 ✅ COMPLETED — Data Validation & Config Caching (ConfigCache Singleton, CompositeScorer Logging Sync)
- [x] **Bybit V5 WebSocket:** kline.1.BTCUSDT, publicTrade.BTCUSDT, orderbook.50.BTCUSDT (Single Source of Truth)
- [x] **Institutionelle CVD:** Bybit side-Field (Buy=Taker Buy, Sell=Taker Sell) mit execId Deduplizierung (deque maxlen=200)
- [x] **Binance Fallback:** 5-Sekunden Heartbeat-Monitoring, Primary First (sofort zurück zu Bybit wenn verfügbar)
- [x] **CryptoPanic API:** Diskrete News-Quelle als Ersatz für Browser-Scraping
- [x] **HuggingFace Login:** HF_TOKEN für schnellere Model-Downloads, CRITICAL-Log bei Fehlschlag, Sentiment-Einfluss=0 bei Ausfall
- [x] **VWAP Reset:** Exakt um 00:00:00 UTC (Typical Price Basis)
- [x] **VPOC:** Volume Point of Control mit 10-Dollar-Preisstufen
- [x] **ConfigCache Singleton:** config.json nur beim Startup laden (keine ständigen Disk-Reads)
- [x] **CompositeScorer Logging:** Synchrones Logging von Reason und Scores mit composite_score
- [x] **OFI=0 Schutz:** Keine "Strong Buy/Sell Pressure" Meldung wenn OFI = 0

**Begründung:** Bruno erkannte Chancen korrekt, aber der Composite Score konnte in Ranging-Märkten (60-70% der Zeit bei BTC) mathematisch kaum den Threshold überschreiten. Die Kalibrierung ermöglicht jetzt Trade-Generierung bei aligned Signalen ohne die Systemstabilität zu gefährden.

### Geplant: Phasen v3.0+
- [x] **V3.0 Bybit Data-Hub**: Bybit V5 WebSocket Primary, Binance Fallback, Institutionelle CVD
- [x] **V3.0 Privacy & Stability**: CryptoPanic API, HF_TOKEN, ConfigCache Singleton, Logging Sync
- [ ] Advanced Regimes, ML Integration
- [ ] Portfolio Management, Advanced Risk Analytics

---

*Referenz: WINDSURF_MANIFEST.md v3.0 — Einzige Quelle der Wahrheit*
*V3.0 Bybit Data-Hub abgeschlossen: 2026-04-06 – Bybit V5 Primary, CryptoPanic API, ConfigCache Singleton*
*V2.2 Review abgeschlossen: 2026-04-05 – Alle institutionellen Fixes validiert*
*V2.3 Score-Kalibrierung abgeschlossen: 2026-04-05 – Confluence-Bonus, Regime-Kompensation, Ranging-aware scoring*
