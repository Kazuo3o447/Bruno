# Bruno Trading Bot

> **Privacy-First Institutional Bitcoin Trading Bot — v3.0 Conflict Resolution & Paper Launch Ready**

> ✅ **V3.0 Conflict Resolution:** Macro Conflict Resolver (Prompt 02), Composite v3 Reform (Prompt 03), Bybit Hedge Mode (Prompt 04), Funding-Aware Trading (Prompt 05), Execution Hygiene v4.1 (Prompt 06)
> ✅ **V3.0 Paper Trading Ready:** Smoke Test Script, Launch Checklist, 24h Testnet Validation, Kill-Switch Integration
> ✅ **V2.1.1 Scoring Hotfix:** Balanced Scoring Logic, Conviction-Gate Removal, TA-Breakdown Transparenz, Moderate Macro Penalties
> ✅ **V8.0 Privacy-First News & Bybit Core:** Multi-Source News Ingestion, Bybit V5 WebSocket als "Single Source of Truth", Zero Tolerance für Heuristiken
> ✅ **DeepSeek Post-Trade Analyse:** Professionelle Trade-Evaluation für Paper Trades

### V3.0 Highlights (Prompts 02-06)

| Feature | Beschreibung |
|---------|-------------|
| **MR-Mode** | Mean-Reversion bei Macro-Konflikt (50% Sizing, 0.8×SL, 1.0×TP1) |
| **Composite v3** | Dominant Signal Wins, Threshold 8 (Learning), 3-8 Trades/Tag |
| **Hedge Mode** | Bybit positionIdx (0/1/2), reduceOnly, orderLinkId Idempotenz |
| **Funding Filter** | Funding Score ±10 (5% Gewicht), Soft-Veto bei >0.05% |
| **SL/TP v4.1** | Score-basierte Differenzierung, BE garantiert vor TP1 |
| **Slippage Reject** | Live Excess-Slippage Detection + reduceOnly Close |

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

### Trading Flow Highlights (v3.0)

- **Bybit V5 Single Source of Truth:** WebSocket (simuliert) + CVD Taker-Mathematik
- **Bybit Hedge Mode v2:** positionIdx (0/1/2), reduceOnly für SL/TP, orderLinkId Idempotenz
- **Privacy-First News Aggregation:** RSS Feeds (primär) + Reddit JSON (sekundär) + SHA256 Deduplizierung
- **Funding-Aware Trading:** Funding Score ±10 (5% Gewicht), Soft-Veto bei >0.05%
- **Macro Conflict Resolution:** MR-Mode bei TA+Macro-Konflikt (50% Sizing, 0.8×SL)
- **Execution Hygiene v4.1:** Score-basierte SL/TP, BE garantiert vor TP1, Live Slippage Reject
- **Sentiment Analysis:** HuggingFace Models mit HF_TOKEN, Zero-Shot Classification
- **Real CVD:** aggTrade Delta mit 1-Sekunden-Buckets
- **GRSS v3:** 4 gewichtete Sub-Scores (Derivatives, Retail, Sentiment, Macro)
- **Adaptive Thresholds:** ATR-basiert, Threshold 8 (Learning) / 25 (Prod)
- **Composite v3:** Dominant Signal Wins, 3-8 Trades/Tag erwartet
- **Paper Trading:** Hard-Lock auf Paper Trading, Launch Checklist
- **Kill-Switch System:** 8 Consecutive Losses → Block, Reset → Resume
- **MTF-Filter:** Regime-abhängige Filter (50%/80% im Ranging)
- **Event Calendar:** Automatische Threshold-Anpassung um FOMC/CPI/NFP
- **DeepSeek Debrief:** Automatische Post-Trade Analyse mit JSON-Output
- **VWAP/VPOC:** Tägliche Resets um 00:00:00 UTC

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
