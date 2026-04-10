# Changelog

Alle wichtigen Änderungen und Fixes pro Version.

---

## [v4.0] – 2026-04-09 - Critical Logic Refactoring (Prompts 1-9) Prompts Implementiert

### 🎯 Bruno V4 Refactoring — Alle 9 Prompts Implementiert

#### **Prompt 1: Scoring-Logik & Confluence Fixes**
- **Macro Score Hard Block**: Long in Bärenmarkt → macro_score = 0, Short in Bullenmarkt → macro_score = 0
- **OFI Hard Filter**: ofi_met nur true bei >= 0.60 (Long) oder <= 0.40 (Short)
- **Confluence Bonus Fix**: Bonus nur wenn mtf_aligned == true UND (liq_score > 0 OR flow_score > 20)
- **Datei**: `composite_scorer.py`

#### **Prompt 2: Risk-Based Position Sizing**
- **1% Risiko-Regel**: risk_amount_usd = total_equity × 0.01
- **Dynamische Positionsgröße**: target_position_size_usd = risk_amount_usd / sl_distance_pct
- **Leverage-Cap**: Max 10x, required_leverage = target_size / max_margin
- **Datei**: `execution_v4.py` → `_calculate_risk_based_position_size()`

#### **Prompt 3: Fee Hurdle Check**
- **Net Profit Hurdle**: Net profit muss >= 25% des Risikos sein
- **Roundtrip Fees**: 0.24% (Maker 0.01% + Taker 0.04% + Slippage Buffer)
- **Reject Reason**: "Trade rejected: Net profit at TP1 ($X) < 25% of risk ($Y)"
- **Datei**: `execution_v4.py` → `_check_fee_hurdle()`

#### **Prompt 4: Vola-Adjustiertes Trade Management**
- **ATR-basierte SL/TP/BE**:
  - SL = 1.2 × atr_pct
  - TP1 = 1.5 × atr_pct (50% Position)
  - TP2 = 3.0 × atr_pct (50% Position)
  - Breakeven-Trigger = 1.0 × atr_pct (MUSS vor TP1 feuern!)
- **Breakeven Trail**: SL auf Entry + 0.1% Fee-Puffer bei 1.0x ATR Profit
- **Dateien**: `composite_scorer.py`, `execution_v4.py`

#### **Prompt 5: Sweep & Funding Slot Filter (Anti-Manipulation)**
- **Sweep OFI Validation**: Sweep-Signal nur freigegeben bei OFI >= 0.60 (Long) / <= 0.40 (Short)
  - Verhindert "Falling Knife" Käufe ohne Whale-Absorption
- **Funding EMA9-Cross**: Funding-Signal nur bei strukturellem Shift (Preis kreuzt EMA9)
  - Verhindert Contrarian-Traps bei extremem Funding ohne Trend-Bestätigung
- **Datei**: `quant_v4.py`

#### **Prompt 6: Scaled Entries & Break-Even Trailing**
- **ATR-basierte Steps**:
  - Tranche 2 (30%): Trigger bei 1.0 × ATR Profit
  - Tranche 3 (30%): Trigger bei 2.0 × ATR Profit
- **Break-Even Protection**: Vor Tranche 3 MUSS SL für Tranche 1+2 auf Break-Even (Entry + 0.1%) gezogen sein
- **Datei**: `scaled_entry.py`, `execution_v4.py`

#### **Prompt 7: Strategy Blending Fix (Brei-Effekt)**
- **MR Cap bei starkem Trend**: Wenn TA-Score > 80, dann mean_reversion_score auf 0 gecappt
- **Overbought = Stärke**: In parabolischen Märkten kein Malus für überkaufte Signale
- **Kein Block**: Trend-Trades werden nicht mehr durch Mean-Reversion blockiert
- **Datei**: `composite_scorer.py`

#### **Prompt 8: Slot-spezifischer Circuit Breaker**
- **Slot-spezifische Verlustzählung**: 3 aufeinanderfolgende Losses in einem Slot blockieren nur diesen Slot
- **Hard Daily Drawdown**: Globaler 24h-Block nur bei -3% Daily Drawdown (nicht bei Trade-Anzahl)
- **Redis Keys**: `bruno:risk:slot_losses:{slot}`, `bruno:risk:slot_block:{slot}`
- **Dateien**: `risk.py`, `execution_v4.py`

#### **Prompt 9: Orchestrator Race Condition Fix (Strict Pipeline)**
- **Kritischer Order-Pfad**: Von losem Pub/Sub zu synchroner Pipeline umgebaut
- **Sequentielle Validierung**:
  1. QuantAgent generiert Signal → reicht via Callback an Orchestrator ein
  2. Orchestrator wartet synchron auf `RiskAgent.validate_and_size_order(signal)`
  3. RiskAgent holt FRISCHEN Portfolio-State und führt alle Checks durch
  4. NUR bei Freigabe: Orchestrator ruft `ExecutionAgent.execute_order(order_payload)`
- **Race Condition Elimination**: Keine Timing-Probleme zwischen Signalgenerierung und Portfolio-Validierung
- **Legacy Mode**: Pub/Sub bleibt für Monitoring/Backwards-Kompatibilität erhalten
- **Neue Redis Keys**: `bruno:pipeline:metrics` für Pipeline-Performance-Monitoring
- **Dateien**: `orchestrator.py`, `risk.py`, `execution_v4.py`, `quant_v4.py`, `worker.py`

### 📚 Dokumentation
- CHANGELOG.md – v4.0 Eintrag mit allen 9 Prompts
- WINDSURF_MANIFEST.md – V4 Status Update
- docs/arch.md – V4 Architektur-Refactoring

---

## [v3.0] – 2026-04-06

### 🚀 Bybit Data-Hub & Core Math

#### **Phase 1: Infrastructure Upgrade & Privacy**
- **HF_TOKEN Implementierung** – HuggingFace Login für schnellere Model-Downloads
- **CRITICAL-Log bei Fehlschlag** – SentimentAgent loggt kritisch wenn HF_TOKEN fehlt oder Login fehlschlägt
- **Sentiment-Einfluss auf 0** – RiskAgent setzt Sentiment-Score-Einfluss auf 0 wenn HF_TOKEN nicht verfügbar
- **CryptoPanic API** – Diskrete News-Quelle als Ersatz für Browser-Scraping
- **Browser-Scraper Entfernung** – Alle Browser-basierten News-Scraper und Google-Trends-Logiken gelöscht
- **Dossier-Bereinigung** – Max Pain und Google Trends Referenzen bereinigt (nur in institutionellen GRSS v3 System belassen)

#### **Phase 2: Bybit V5 Primary Integration**
- **Bybit V5 WebSocket Client** – kline.1.BTCUSDT, publicTrade.BTCUSDT, orderbook.50.BTCUSDT (Single Source of Truth)
- **Institutionelle CVD** – Bybit side-Field (Buy=Taker Buy, Sell=Taker Sell) mit execId Deduplizierung (deque maxlen=200)
- **Binance Fallback** – 5-Sekunden Heartbeat-Monitoring, Primary First (sofort zurück zu Bybit wenn verfügbar)
- **VWAP Reset** – Exakt um 00:00:00 UTC (Typical Price Basis)
- **VPOC** – Volume Point of Control mit 10-Dollar-Preisstufen

#### **Phase 3: Data Validation & Config Caching**
- **ConfigCache Singleton** – config.json nur beim Startup laden (keine ständigen Disk-Reads)
- **CompositeScorer Logging Sync** – Synchrones Logging von Reason und Scores mit composite_score
- **OFI=0 Schutz** – Keine "Strong Buy/Sell Pressure" Meldung wenn OFI = 0

### 📚 Dokumentation
- README.md – v3.0 Bybit Data-Hub & Core Math
- docs/arch.md – Bybit V5 Architektur, Binance Fallback
- WINDSURF_MANIFEST.md – v3.0 Status Update

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

#### **Prompt 6 Bug Fixes (Alle bereits behoben)**
- **Bug 1 (KRITISCH):** Orderbuch-Walls Key-Mismatch behoben – TechnicalAgent schreibt `bruno:ta:ob_walls` separat
- **Bug 2 (KRITISCH):** TP1/TP2 Feldweiterleitung zu PositionTracker komplett implementiert
- **Bug 3 (MITTEL):** scale_out_position() Integration in execution_v4 über _partial_close()
- **Bug 4 (MITTEL):** Hardcoded amount entfernt – Signal nutzt `position_size_hint_pct`
- **Bug 5 (KLEIN):** Any Import in execution_v4.py vorhanden
- **Bug 6 (KLEIN):** Alle Legacy-Config-Keys entfernt
- **Bug 7 (MITTEL):** Breakeven-Trigger nutzt dynamischen Position-Wert statt Config
- **Bug 8 (MITTEL):** _score_flow() ist async und akzeptiert analytics_data Parameter

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
