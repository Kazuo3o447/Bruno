# Bruno v3 Architektur-Manifest

> **Version: 3.0.0 (April 2026)**
>
> ✅ **V3.0 Architecture Refinement:** Death Zone Removal, Symmetric Scoring, Sweep Signals, Mean Reversion Sub-Engine, ATR-Ratio Regime Detection, Learning Mode Optimization
> ✅ **V3.0 Strategy Blending:** Trend Following + Mean Reversion mit regime-adaptiver Gewichtung (40%/30%/10%)
> ✅ **V3.0 No Hard Blocks:** Risk wird in Score gepreist, keine Hard Direction Vetoes mehr
> ✅ **V8.0 Bybit Data Core:** Bybit V5 WebSocket als exklusive "Single Source of Truth", Zero Binance REST
> ✅ **V8.0 Privacy-First News:** Multi-Source News (CryptoPanic, RSS, FreeCryptoNews) mit SHA256-Deduplizierung
> ✅ **Mathematical Purity:** Präzise CVD Taker-Mathematik, VWAP/VPOC tägliche Resets, Zero Tolerance für Heuristiken
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

## V3.0 Datenquellen-Architektur (Bybit Core + Advanced Indicators)

### News Ingestion (Multi-Source, SHA256 Deduplizierung, Zero-Trust Architecture)
```
CryptoPanic API (60s) ──┐
                        ├─► NewsIngestionService ──► SentimentAnalyzer ──► Redis
Tier-3 FreeCryptoNews (60s) ─┤        (BTC-Filter, SHA256 Hash, Redis Storage)
RSS Scraper (30s) ───────┘        │
                                └─► SentimentAgent (vor-analysierte Daten)
```

**Tier-3 FreeCryptoNewsClient Features:**
- **Zero Trust Architecture**: 5s hartes Timeout, keine Exception-Weitergabe
- **Defensive HTTP-Polling**: Strikte try...except Exception Blöcke
- **Fail-Safe Verhalten**: Bei Fehlern sofort `[]` Rückgabe, keine Blockierung
- **BTC Pre-Filter**: Nur Bitcoin-spezifische Inhalte werden verarbeitet
- **Redis Integration**: Verarbeitete News werden für SentimentAgent gespeichert
- **Dual Endpoints**: `/api/news` (general) + `/api/bitcoin` (BTC-spezifisch)

### Bybit V5 Single Source of Truth
```
Bybit V5 WebSocket ──► BybitV5Client ──► Redis
├── kline.1.BTCUSDT (1m-Kerzen)
├── publicTrade.BTCUSDT (CVD Berechnung)
└── Reconnect-Callback bei Disconnect
```

**CVD Taker-Mathematik (ABSOLUTE PRÄZISION):**
```python
for trade in message["data"]:
    exec_id = trade["i"]  # Deduplizierung
    vol = float(trade["v"])
    side = trade["S"]  # "Buy"/"Sell"
    
    if exec_id not in self._processed_trades:
        if side == "Buy":
            self.current_1m_taker_buy += vol
        elif side == "Sell":
            self.current_1m_taker_sell += vol
```

### V3.0 New Features
- ✅ **Bollinger Bands** für Regime Detection (BB-Width)
- ✅ **ATR-Ratio** (ATR/Price) für Volatilitäts-Normalisierung
- ✅ **Sweep Signals** (+30/-30) mit 5min TTL
- ✅ **Mean Reversion Score** (-50..+50) für Contrarian-Trades
- ✅ **Strategy Blending** (Trend Following + Mean Reversion)
- ❌ **Death Zone Veto** entfernt - Clusters sind Opportunities
- ❌ **Conviction Gates** entfernt - nur Threshold Gate

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

## Börsen-Architektur (Manifest v8.0)

```
Bybit V5 WS ──► IngestionAgent + TechnicalAgent + QuantAgent ──► Redis
                                                           │
                                                      alle Agenten
                                                           │
News Sources ──► NewsIngestionService ──► SentimentAnalyzer ──┘
                        │
                        └──► PositionTracker (Redis Live-State + DB Audit)
```

| Börse | Nutzung | Daten | Status |
|-------|---------|-------|--------|
| **Bybit V5** | **Daten (Exklusiv)** | WebSocket (kline.1, publicTrade) - Single Source of Truth | ✅ AKTIV (Simuliert) |
| **RSS Feeds** | **News (Primär)** | CoinDesk, Cointelegraph, Decrypt - Zero Latency | ✅ AKTIV (49 Items) |
| **Reddit JSON** | **News (Sekundär)** | r/Bitcoin Hot Posts - Community Sentiment | ✅ AKTIV (14 Items) |
| **CoinMarketCap** | **Marktdaten (Optional)** | BTC Preis, Volume, Market Cap - API Key erforderlich | ⚠️ INAKTIV (API Key fehlt) |
| **CryptoCompare** | **News (Fallback)** | Free Tier News API - Leere Antwort | ❌ INAKTIV (0 Items) |
| **NewsAPI** | **News (Fallback)** | Demo Key ungültig - 401 Unauthorized | ❌ INAKTIV (Auth Error) |
| **Binance** | **Deaktiviert** | REST Analytics - Complete Purge | ❌ REMOVED |

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

### 7-Agenten Kaskade (v8.0 - Privacy-First & Deterministisch)

1. **IngestionAgent** - WebSocket Stream (Bybit V5) → Redis Cache
2. **NewsIngestionService** - Multi-Source News (RSS primär, Reddit JSON sekundär, Multi-API Fallback) → SentimentAnalyzer → Redis Storage
3. **TechnicalAnalysisAgent** - MTF-Alignment, Wick Detection, Session Bias, Orderbuch-Walls
4. **ContextAgent** - GRSS v3, Macro-Daten, On-Chain, News-Sentiment (Binance-frei, Redis-integriert)
5. **QuantAgentV4** - Quantitative Analyse, Composite Score (deterministisch, News-integriert)
6. **RiskAgent** - Risiko-Management, Position-Sizing, Limits (Daily Drawdown Circuit Breaker)
7. **ExecutionAgentV4** - Trade Execution, ATR Trailing Stop, TP1/TP2 Scaling (Paper-Only)

### v8.0 Service Layer (Privacy-First & Mathematical Purity)

| Service | Zweck | Integration | Status |
|---------|-------|-------------|--------|
| **NewsIngestionService** | Multi-Source News, SHA256 Deduplizierung, BTC-Filter, Multi-API Fallback | SentimentAnalyzer → ContextAgent | ✅ AKTIV (RSS 49 Items, Reddit 14 Items, Total 63) |
| **BybitV5Client** | WebSocket CVD, VWAP, VPOC, Trade Deduplizierung | TechnicalAnalysisAgent | ✅ AKTIV (Simuliert) |
| **TechnicalAnalysisAgent** | MTF-Alignment, Wick Detection, Session Bias | QuantAgentV4 | ✅ AKTIV |
| **SentimentAnalyzer** | FinBERT, CryptoBERT, Zero-Shot Classification | ContextAgent | ✅ AKTIV |
| **CompositeScorer** | Dynamic Weighting, Regime Detection, News-Flow Hooks | QuantAgentV4 | ✅ AKTIV |
| **TradeDebriefV2** | Post-Trade Debrief mit Deepseek Reasoning API | ExecutionAgentV4 | ✅ AKTIV |
| **PositionTracker** | MAE/MFE, TP1-Scale-Out, Breakeven, ATR Trailing | ExecutionAgentV4 | ✅ AKTIV |

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

### Phase v8.0 — Privacy-First News & Bybit Data Core (April 2026) ✅ COMPLETED
- [x] Phase 1 ✅ COMPLETED — Multi-Source News Ingestion (CryptoPanic, RSS, Tier-3 FreeCryptoNews, SHA256 Deduplizierung, BTC-Filter, Zero-Trust Architecture)
- [x] Phase 2 ✅ COMPLETED — Bybit V5 Single Source of Truth (WebSocket Client, CVD Taker-Mathematik, VWAP/VPOC Resets, Trade Deduplizierung)
- [x] Phase 3 ✅ COMPLETED — Mathematical Purity & Purge (BinanceAnalyticsService entfernt, Max Pain deaktiviert, Heuristik-frei)
- [x] Phase 4 ✅ COMPLETED — Backtest Identity (CompositeScorer Import, Fee Simulation, Pessimismus-Regel)
- [x] **NewsIngestionService**: 3 Quellen mit strikter Deduplizierung, Redis Storage, Sentiment-Integration
- [x] **Tier-3 FreeCryptoNewsClient**: Zero-Trust Defensive Architecture, 5s Timeout, Graceful Degradation
- [x] **BybitV5Client**: Präzise CVD Berechnung ohne close>open Verletzungen, execution ID Deduplizierung
- [x] **Complete Binance Purge**: Alle REST API Calls aus ContextAgent und Worker entfernt
- [x] **Worker Integration**: News-Ingestion Task mit Bybit V5 Health Check und Redis Integration
- [x] **Dependencies**: feedparser, pybit zu requirements.txt hinzugefügt
- [x] **VPOC:** Volume Point of Control mit 10-Dollar-Preisstufen
- [x] **ConfigCache Singleton:** config.json nur beim Startup laden (keine ständigen Disk-Reads)
- [x] **SentimentAgent Integration**: Vor-analysierte News aus Redis, Zero-Shot Fallback
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
