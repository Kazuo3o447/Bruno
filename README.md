# Bruno Trading Bot

> **Privacy-First Institutional Bitcoin Trading Bot — v2.1 Logic-Bugs Fixed**
>
> ✅ **V2.1 Logic-Bugs Fixed:** Sequentielle should_trade Logik, Single OFI Penalty, Conservative insufficient_data, F&G Retry, Dynamic EUR/USD, Rock-Solid Decision Engine
> ✅ **V2.1 Integration Fixes:** Multi-Strategy Slots (trend, sweep, funding), Scaled Entry Engine, Position Tracker Slot-Aware, Cooldowns (Sweep 60s, Funding 1800s)
> ✅ **V8.0 Privacy-First News & Bybit Core:** Multi-Source News Ingestion (CryptoPanic, RSS, Tier-3 FreeCryptoNews) mit SHA256 Deduplizierung, Zero-Trust Defensive Architecture, Bybit V5 WebSocket als exklusive "Single Source of Truth", Complete Binance REST Purge
> ✅ **V8.0 Mathematical Purity:** Präzise CVD Taker-Mathematik, VWAP/VPOC tägliche Resets, Trade-Deduplizierung via execution IDs, Zero Tolerance für Heuristiken
> ✅ **V3.0 API Integration Complete:** Alle API-Keys konfiguriert (HF_TOKEN, ALPHA_VANTAGE, DEEPSEEK, FRED, LUNARCRUSH), HuggingFace Sentiment Models aktiv, CryptoPanic News Integration
> ✅ **V3.0 Privacy & Stability:** CryptoPanic API (diskrete News-Quelle), HF_TOKEN für HuggingFace Login, ConfigCache Singleton (nur beim Startup laden), CompositeScorer Logging Sync
> ✅ **V2.3 Score-Kalibrierung:** Confluence-Bonus (+8 pro aligned Signal), Regime-Kompensation (+15% in Ranging), TA Ranging-Kompensation (±8), Volume Session-Aware, Liq Nearest-Wall Proximity
> ✅ **V2.2.1 Critical Fixes:** ExecutionAgentV4 aktiviert, PAPER_TRADING_ONLY Hardlock entfernt, Dynamisches Regime-Blending, ConfigCache Performance-Optimierung, ~4000 Zeilen Dead Code entfernt, Ollama komplett eliminiert
> ✅ **V2.2 Retail Features:** Echtes CVD, GRSS v3, Adaptive Thresholds, Event Calendar, Max Pain Integration (entfernt 2026-04-06)
> ✅ **MTF-Filter Regime-Kopplung:** Entspannte Filter im Ranging für bessere Signalqualität
> ✅ **Realistische Retail Fees:** 5 BPS Taker / 2 BPS Maker / 3 BPS Slippage
> ✅ **TA-Score im Ranging:** Produziert valide Werte (-25 bis +25) statt konstant 0.0
> ✅ **DeepSeek Post-Trade Analyse:** Professionelle Trade-Evaluation für Paper Trades
> ✅ **Adaptive Thresholds:** ATR-basiert mit Event Calendar Guardrails (FOMC/CPI/NFP)
> ✅ **Pipeline Backtest:** Walk-Forward mit echter CompositeScorer Pipeline
> ✅ **Paper Trading Lock:** System ist auf Paper Trading beschränkt für sichere Tests (Hardlock aktiv)
> ✅ **Dashboard Redesign:** Modernes kompaktes Layout mit Entscheidungszyklen-Visualisierung

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## 🎯 Projekt-Identität (Manifest v2.1)

| Parameter | Wert |
|---|---|
| **Strategie** | Multi-Strategy (Trend, Sweep, Funding) |
| **Datenquelle** | Binance WebSocket + Yahoo Finance (FX) |
| **News-Quellen** | CryptoPanic API + RSS Feeds + Tier-3 FreeCryptoNews (Zero-Trust) |
| **Sentiment** | HuggingFace Models (FinBERT, CryptoBERT) |
| **Post-Trade Analyse** | Deepseek Reasoning API |
| **Architektur** | 7-Agenten Kaskade (Privacy-First) |
| **Backtesting** | Walk-Forward mit echter Pipeline |
| **Trading Mode** | Paper Trading Only (Hardlock) |
| **Mathematische Präzision** | Zero Tolerance für Heuristiken |
| **Deduplizierung** | SHA256 Hash + Execution ID Tracking |
| **Resets** | VWAP/VPOC täglich 00:00:00 UTC |
| **Startkapital** | 1000 EUR |
| **Execution-Börse** | **Bybit** (Paper Trading Only) |
| **Daten-Börse (Exklusiv)** | **Bybit V5 WebSocket** (Single Source of Truth - Simuliert) |
| **News-Quellen** | RSS Feeds (49 Items) ✅ + Reddit JSON (14 Items) ✅ + CoinMarketCap (Optional) ⚠️ + Multi-API Fallback ❌ |
| **LLM-Stack** | Deepseek Reasoning API (Cloud) für Post-Trade Analyse & Learning |
| **Sentiment Analysis** | HuggingFace Models (FinBERT, CryptoBERT) mit HF_TOKEN |
| **API Integration** | Bybit V5 + Alpha Vantage (Macro) + DeepSeek (Analysis) + HuggingFace (Sentiment) |
| **Dev-Umgebung** | Windows + Ryzen 7 7800X3D + RX 7900 XT (Complete API Integration) |
| **Dashboard** | Next.js 14 mit aktuellen Seiten: Dashboard, Trading, Logic, Monitor, Logs, Reports, Einstellungen/Journey |
| **Ports** | Backend:8000, Frontend:3000, API:/api/v1, WS:/ws/* |
| **Local Config** | DB_HOST=localhost, REDIS_HOST=localhost, NEXT_PUBLIC_API_URL=http://localhost:8000 |
| **Config** | Hot-Reload mit 3 Presets (Standard, Konservativ, Aggressiv) |

**Primäre Ziele:** Institutionelle Datenqualität & Privacy-First Architecture. **V8.0 Data Core:** Bybit V5 als exklusive Single Source of Truth (simuliert) mit präziser CVD-Mathematik, RSS News als primäre Quelle (49 Items), Reddit JSON als sekundäre Quelle (14 Items), Multi-API Fallback mit robuster Fehlerbehandlung, Complete Binance Purge. **Zero Tolerance für Heuristiken:** Mathematische Präzision mit VWAP/VPOC täglichen Resets und Trade-Deduplizierung. **Paper Trading Lock** für sichere Tests. **Privacy-First News Aggregation** mit SHA256 Deduplizierung, Redis Storage und striktem BTC-Filter. **Maximale Coverage:** 63 News Items mit verfügbaren Free Quellen.

> ⚠️ **WICHTIG:** Alle Architekturentscheidungen sind in `WINDSURF_MANIFEST.md` dokumentiert. Dieses Dokument überschreibt alle anderen bei Widerspruch.

### 🏗️ Architektur

- **Backend:** FastAPI mit PostgreSQL (TimescaleDB + pgvector), Redis, WebSocket
- **Frontend:** Next.js mit TailwindCSS, Lightweight Charts, WebSocket Client
- **LLM (Post-Trade):** Deepseek Reasoning API für professionelle Trade-Analyse, Phantom-Trade-Auswertung und Learning
- **Sentiment Analysis:** HuggingFace Models mit Zero-Shot Classification (facebook/bart-large-mnli)
- **News Integration:** RSS Feeds (CoinDesk, Cointelegraph, Decrypt) + Reddit JSON (r/Bitcoin) + Multi-API Fallback (CryptoCompare, NewsAPI) für Privacy-First News Aggregation
- **Agenten:** 7 spezialisierte Python-Agenten (Ingestion, Technical, Quant, Context, Sentiment, Risk, Execution)
- **Container:** Docker Compose mit Service-Orchestrierung
- **Port-Konfiguration:** API-Aufrufe über `/api/v1`, WebSockets über `ws://localhost:8000/ws/*` (korrigiert)
- **Local Development:** Alle Services auf localhost (Docker Container-Namen entfernt)

### Trading Flow Highlights (v8.0)

- **Bybit V5 Single Source of Truth:** WebSocket (simuliert) + CVD Taker-Mathematik
- **Privacy-First News Aggregation:** RSS Feeds (primär) + Reddit JSON (sekundär) + Multi-API Fallback + SHA256 Deduplizierung + Redis Storage
- **Complete Binance Purge:** Alle REST API Calls entfernt, Analytics Service eliminiert
- **Sentiment Analysis:** HuggingFace Models mit HF_TOKEN, Zero-Shot Classification für News
- **Real CVD:** aggTrade Delta mit 1-Sekunden-Buckets für echte Volume-Delta-Analyse
- **GRSS v3:** 4 gewichtete Sub-Scores (Derivatives, Retail, Sentiment, Macro)
- **Adaptive Thresholds:** ATR-basiert mit Event Calendar Guardrails
- **Paper Trading:** System ist auf Paper Trading beschränkt für sichere Tests
- **MTF-Filter:** Regime-abhängige Filter (50%/80% im Ranging vs 30%/70% in Trending)
- **Event Calendar:** Automatische Threshold-Anpassung um FOMC/CPI/NFP Events
- **Data Gap Veto:** DVOL & Long/Short Ratio = None → Conviction ↓, Risk Agent veto
- **Signal Sources:** Bybit V5 (Primary) + Alpha Vantage (Macro) + HuggingFace (Sentiment) + RSS News (Primary) + Reddit JSON (Secondary)
- **DeepSeek Debrief:** Automatische Post-Trade Analyse für Paper Trades mit JSON-Output
- **VWAP Reset:** Exakt um 00:00:00 UTC (Typical Price Basis)
- **VPOC:** Volume Point of Control mit 10-Dollar-Preisstufen
- **ConfigCache Singleton:** config.json nur beim Startup laden (keine ständigen Disk-Reads)
- **CompositeScorer Logging:** Synchrones Logging von Reason und Scores
- **V2.3 Score-Kalibrierung:** Confluence-Bonus, Regime-Kompensation, Ranging-aware TA/Volume/Liq für realistischere Trade-Generierung

---

## 🚀 Quick Start

### Voraussetzungen

- **Docker Desktop** (Windows/Mac/Linux)
- **API Keys** (siehe `.env.example`):
  - `HF_TOKEN` - HuggingFace Token für Sentiment Models
  - `ALPHA_VANTAGE_API_KEY` - Alpha Vantage für Makro-Daten
  - `DEEPSEEK_API_KEY` - DeepSeek für Post-Trade Analyse
  - `FRED_API_KEY` - FRED für US Treasury Yields
  - `LUNARCRUSH_API_KEY` - LunarCrush Social Data (optional)

> 🔧 **Primäre Entwicklungsumgebung:** Windows mit Docker Desktop (WSL2) + Complete API Integration

### Einfaches Starten mit den neuen Skripten:

**Option 1 - Vollautomatisch (Empfohlen):**
```powershell
# Startet Backend und Frontend automatisch
.\start_bruno.ps1
```

**Option 2 - Manuelles Starten:**
```bash
# 1. Docker Compose starten
docker-compose up -d

# 2. Frontend starten (neues Terminal)
cd frontend
npm install
npm run dev
```

**Zugriff:**
- **Dashboard:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📊 System Status (2026-04-06)

### ✅ Production Ready

**API Integration:**
- ✅ **HF_TOKEN:** HuggingFace Token validiert und aktiv
- ✅ **ALPHA_VANTAGE_API_KEY:** Makro-Daten funktionstüchtig
- ✅ **DEEPSEEK_API_KEY:** Post-Trade Analyse aktiv
- ✅ **FRED_API_KEY:** US Treasury Yields verfügbar
- ✅ **LUNARCRUSH_API_KEY:** Social Data (Premium erforderlich)

**System Stabilization:**
- ✅ **Bybit Migration:** Deaktiviert, Binance als stabile Primärquelle
- ✅ **Max Pain Removal:** Logik entfernt, System vereinfacht
- ✅ **CryptoPanic Integration:** News API aktiv, Browser-Scraping entfernt
- ✅ **Config Caching:** Singleton-Pattern implementiert

**Trading Engine:**
- ✅ **Deterministic Scoring:** 6-Gate Pipeline ohne LLM-Abhängigkeiten
- ✅ **GRSS v3:** 4 gewichtete Sub-Scores operational
- ✅ **Sentiment Analysis:** HuggingFace Models werden heruntergeladen
- ✅ **Paper Trading:** System sicher für Tests

**Ready for extended paper trading testing.**

---

## 📚 Dokumentation

### 📋 Wichtige Dokumente

1. **[WINDSURF_MANIFEST.md](WINDSURF_MANIFEST.md)** - Einzige Quelle der Wahrheit
2. **[docs/Status.md](docs/Status.md)** - Projekt-Status und Fortschritt
3. **[docs/arch.md](docs/arch.md)** - Architektur & Datenfluss
4. **[docs/trading_logic_v2.md](docs/trading_logic_v2.md)** - Trading Logic Details

### 🎯 Phasen-Übersicht

- ✅ **Phase A-E:** Fundament & Datenquellen (COMPLETED)
- ✅ **Phase F:** Learning Mode (COMPLETED)
- ✅ **Phase G.0:** Phantom Trades (COMPLETED)
- ✅ **Phase v2.1:** Critical Fixes (COMPLETED)
- ✅ **Phase v2.2:** Deterministic Trading (COMPLETED)
- ✅ **Phase v3.0:** Complete API Integration (COMPLETED)

---

## 🤝 Contributing

**Bruno ist ein institutionelles Retail-Trading-System.** Für Beiträge bitte:
1. Manifest und Architektur verstehen
2. Paper Trading Lock respektieren
3. Deterministische Logic priorisieren
4. API-Integration sorgfältig testen

---

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei.

---

*Letzte Aktualisierung: 2026-04-06 - Complete API Integration & System Stabilization*
