# Changelog

Alle wichtigen Änderungen und Fixes pro Version.

---

## [v2.2.1] – 2026-04-05

### 🔧 Critical Fixes & Dead Code Cleanup

#### **Execution Engine Upgrade**
- **ExecutionAgentV4 aktiviert** – worker.py importiert und registriert jetzt V4 statt V3 (1157 Zeilen Dead Code eliminiert)
- **PAPER_TRADING_ONLY Hardlock entfernt** – Validator wirft jetzt Warnungen statt Exceptions, sauberer Übergang Paper→Live möglich
- **Dynamisches Regime-Blending aktiviert** – COMPOSITE_W_* Keys aus config.json entfernt, _regime_blend() wird jetzt verwendet
- **RiskAgent DVOL/LS-Ratio Veto konfigurierbar** – REQUIRE_INSTITUTIONAL_DATA_FOR_TRADE Flag in config.json (default: false)

#### **ConfigCache Implementation**
- **ConfigCache in Hot Paths** – composite_scorer.py, execution_v4.py, quant_v4.py, risk.py, context.py nutzen jetzt ConfigCache statt File I/O
- **Performance-Optimierung** – 1×/Minute Reload statt pro Zyklus für Konfigurationswerte

#### **Dead Code Cleanup (~4000 Zeilen)**
- **Gelöschte Agenten**: execution_DEPRECATED.py, execution_v3.py, quant_DEPRECATED.py, quant_v3.py
- **Gelöschte Dienste**: liquidity_engine_v2.py, regime_config_v2.py, trade_debrief_v2.py
- **Ollama komplett entfernt**: chat.py, llm_client.py, llm_provider.py, llm/ Ordner, routers/llm_cascade.py
- **Config Cleanup**: OLLAMA_HOST aus config.py entfernt

#### **Bugfixes nach Cleanup**
- **main.py**: chat import entfernt (Startup-Crash durch gelöschtes Modul behoben)
- **context.py**: ConfigCache statt direktem File I/O in _is_learning_mode()
- **Frontend/Monitoring**: gate_4_llm_cascade zu gate_4_composite_scorer umbenannt (irreführende Bezeichnung korrigiert)

### 📚 Dokumentation
- CHANGELOG.md – v2.2.1 Eintrag
- README.md – ExecutionAgentV4, ConfigCache, Dead Code Cleanup
- WINDSURF_MANIFEST.md – Status Update

---

## [v2.2] – 2026-04-05

### 🚀 Institutionelle Fixes & Datenquellen

#### **Core-Agenten**
- **ContextAgent**: Echte Deribit DVOL API mit Zeitparameter-Unterstützung
- **ContextAgent**: Max Pain aus echter Options-Chain (864 Strikes) statt Heuristik
- **ContextAgent**: Put/Call Ratio aus Deribit Options-Book
- **QuantAgentV4**: CVD auf Binance aggTrades umgestellt (statt 1m Klines)
- **QuantAgentV4**: Strikter `last_trade_id` Guard gegen Double-Counting
- **CompositeScorer**: Threshold-Fallback auf config.json korrigiert (35/55)
- **CompositeScorer**: Null-Safe Signal-Sammlung, keine crashes bei leeren Snapshots
- **ExecutionAgentV4**: 3-Phasen Exit (Fix SL/TP → Breakeven → ATR Trailing)
- **ExecutionAgentV4**: TP1 Scaling mit maker fee, Position State Tracking
- **RiskAgent**: Veto-Matrix mit GRSS Threshold und Daily Drawdown Circuit Breaker

#### **Dienste & Daten**
- **BinanceAnalyticsService**: 3 Endpunkte mit 10min Cache (Top Trader, Taker Volume, Global L/S)
- **OnChainClient**: Blockchain.com Hash Rate + Mempool, Glassnode Exchange Balance
- **RetailSentimentService**: Reddit + StockTwits Aggregation, FOMO Warning
- **Market Data Collector**: Robuster Error Handling, 404-Fallbacks

#### **Konfiguration**
- **config.json**: `LEARNING_MODE_ENABLED: true`, `COMPOSITE_THRESHOLD_LEARNING: 35`, `COMPOSITE_THRESHOLD_PROD: 55`
- **Environment**: UTF-8 BOM Handling für .env Dateien
- **Redis Keys**: Neue Keys für Max Pain, Options Chain, CVD State

### 🐛 Bugfixes
- Fixed DVOL `null` durch fehlende API-Parameter
- Fixed Composite Scorer Default-Thresholds
- Fixed CVD Double-Counting mit aggTrades
- Fixed Syntaxfehler in ContextAgent nach Patch
- Fixed None-Value crashes in Signal Collection
- **Fixed OFI Display** — Redis Key Mapping korrigiert (OFI_Buy_Pressure statt OFI)
- **Fixed Dockerfile** — Explizite Datei-Kopie für Tailwind/PostCSS Konfiguration
- **Fixed Log Page** — WebSocket mit REST Fallback für Robustheit
- **Fixed Dashboard** — Kompaktes Layout mit korrekten CSS Styles

### 📈 Performance
- Worker stabil >5 Minuten ohne Crash
- Redis Payloads konsistent und aktuell
- Memory-Nutzung normal, keine Leaks
- Decision Flow deterministisch und schnell

### 📚 Dokumentation
- `BRUNO_V2_2_REVIEW_REPORT.md` – Detailliertes Review & Validation
- `trading_logic_v2.md` – Auf V2.2 aktualisiert
- `README.md` – V2.2 Features ergänzt
- `WINDSURF_MANIFEST.md` – Status V2.2

---

## [v2.1] – 2026-03-XX

### 🚀 Deterministic Composite Scoring
- LLM Cascade ersetzt durch mathematisches Scoring
- Regime-adaptive Gewichtung (trending/ranging)
- Flow Score mit Taker Buy/Sell Ratio
- Diagnostics-Block mit Block Reason

### 🐛 Bugfixes
- Import-Fehler in market_data_collector.py
- UTF-8 BOM Handling für .env
- Redis Health Hub Fixes

---

## [v2.0] – 2026-03-XX

### 🚀 Complete Rewrite
- Multi-Agent Architecture mit Orchestrator
- Redis als zentraler State Store
- Docker Compose Setup
- Frontend Dashboard

### 📚 Initial Documentation
- Architektur-Dokumentation
- API-Dokumentation
- Deployment-Guide

---

*Für ältere Versionen siehe Git History*
