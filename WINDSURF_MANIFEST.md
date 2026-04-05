# WINDSURF_MANIFEST.md
# Bruno Trading Platform — Master Agent Briefing v2.2

> **PFLICHTLEKTÜRE. Jeder Agent. Jede Session. Jeder Neustart.**
> Dieses Dokument ist die einzige Quelle der Wahrheit.
> Es überschreibt alle anderen Dokumente bei Widerspruch.
> Bei Änderungen: ERST hier dokumentieren, DANN Code ändern.
>
> Erstellt: 2026-03-27 | Architekt: Ruben | Review: Claude (Anthropic)
> Letzte Aktualisierung: 2026-04-05 (Bruno v2.2 Institutionelle Fixes & Complete Purge)
> Repository: https://github.com/Kazuo3o447/Bruno
>

---

## STATUS UPDATE (April 2026)

### ✅ BRUNO v2.2 — Institutionelle Fixes & Complete Purge
- **LLM-Cascade entfernt** — 3-Layer LLM durch deterministischen Composite Scorer ersetzt
- **Technical Analysis Engine** — EMA, RSI (Wilder), VWAP (Tages-Reset), ATR, S/R, MTF-Alignment, Wick-Detection, VPOC
- **Liquidity Intelligence** — Cluster-Magneten, 3×-Sweep-Konfirmation (Spike+Wick+OI-Drop), CVD (aggTrades, last_trade_id Guard)
- **Orderbuch-Walls** — depth=1000 als Live-Liquiditätsradar
- **Institutionelle Daten** — Echte Deribit DVOL, Max Pain aus Options-Chain (864 Strikes), Put/Call Ratio
- **Free-Tier Analytics** — Binance Top Trader / Taker Ratios + Blockchain.com / Glassnode On-Chain Daten
- **Regime-adaptive Gewichtung** — Trending: TA 50%, Ranging: Liq 40%
- **Risk: Veto Matrix** — GRSS Threshold (35/55), Daily Drawdown (3%), 3 Fehltrades → 24h Pause
- **Execution V2.2** — 3-Phasen Exit (Fix SL/TP → Breakeven → ATR Trailing), TP1 Maker Fee (0.01%), Position-Specific State
- **Composite Scorer** — Threshold-Fallback aus config.json, Null-Safe Signal Collection, Diagnostics Block
- **Backtester V2.2** — 1-Minuten-Kerzen, Intrabar Pessimismus-Regel
- **Complete Purge** — Keine veralteten Heuristiken (Google Trends, Fake Max Pain)
- **60s Zykluszeit** — kein LLM-Overhead mehr
- **Post-Trade Deepseek Analysis** — Professionelle Reasoning API nach jedem Trade → DB für Lernloop
- **Binance API Integration v2.1** — Ollama entfernt, BinanceDataClient + MarketDataCollector
- **Live Marktdaten** — Alle 30s: Ticker, Klines, Orderbook, Funding, OI, Liquidations
- **Frontend v2.2** — 7 Seiten: Dashboard, Trading, Monitor, Logs, Reports, Einstellungen, Journey
- **Dashboard** — Status-Cards, Entscheidungs-Timeline, Pipeline Gates, Agenten-Status, Performance
- **Trading Page** — 6-Gate Kaskade-Visualisierung, Quant Micro Daten, GRSS Breakdown
- **Monitor** — API-Health Tests, Agent Heartbeats, Scheduler Steuerung
- **Logs** — Live WebSocket Logs mit Filter und Export
- **Reports** — Trades, Lern-Logs, Performance-Perioden
- **Settings** — 4 Presets, Parameter-Editor, Deepseek-Test
- **Journey** — Dokumentation mit 7 Abschnitten

## AGENT-PIPELINE v2

| Stage | Agenten | Redis Output |
|-------|---------|-------------|
| 1 | ingestion | market_candles, liquidations, market:ticker, market:funding, market:ofi:ticks, market:orderbook |
| 2 | technical, context, sentiment | bruno:ta:snapshot, bruno:context:grss, bruno:sentiment:aggregate |
| 3 | quant | bruno:quant:micro, bruno:liq:intelligence, bruno:decisions:feed, bruno:pubsub:signals |
| 4 | risk | bruno:veto:state |
| 5 | execution | bruno:portfolio:state |

### Binance API Integration (v2.1)

**MarketDataCollector** (Worker-Task, 30s Intervall):
```python
# API Endpoints (keine Keys erforderlich)
get_ticker()           # 67263.7 USD
get_klines()           # 500 Candlesticks
get_orderbook()        # 100 Bids/Asks
get_funding_rate()     # 0.0001
get_open_interest()    # 123456 BTC
get_liquidations()     # [{"side": "SELL", "price": 67000}]
```

**Redis Storage Pattern:**
```bash
# 5-10s TTL (sehr frisch)
market:ticker:BTCUSDT           # {"last_price": 67263.7}
market:orderbook:BTCUSDT        # {"imbalance_ratio": 1.23}
market:ofi:ticks               # [{"t": "...", "r": 1.23}]

# 60s TTL (frisch)
bruno:ta:klines:BTCUSDT        # {"klines": [...], "count": 500}
market:liquidations:BTCUSDT    # [{"side": "SELL", "price": 67000}]

# 300s TTL (mittel-frisch)
market:funding:BTCUSDT         # {"fundingRate": 0.0001}
market:open_interest:BTCUSDT   # {"openInterest": "123456.78"}
```

### Entscheidungslogik: Composite Scorer

Regime-adaptive Gewichtung:

| Regime | TA | Liq | Flow | Macro |
|--------|-----|-----|------|-------|
| Trending (bull/bear) | 50% | 15% | 20% | 15% |
| Ranging/Mixed | 20% | 40% | 25% | 15% |

Sweep-Bonus: 3×-bestätigter Sweep senkt Threshold um 15 Punkte.
MTF-Filter: Score ×0.3 wenn Multi-Timeframe nicht aligned.

---

## LEGACY (v1) — VORHERIGER STATUS (3. April 2026)

### ✅ PHASE F COMPLETED - Critical Fixes & Config-Hot-Reload
- **Doppeltes Prefix behoben** - export, config, decisions Router Endpunkte erreichbar
- **Fresh-Source-Gate repariert** - Health-Reporting für alle Quellen, GRSS nicht mehr blockiert
- **Config-Hot-Reload implementiert** - QuantAgent & RiskAgent lesen live config.json
- **OFI Schema korrigiert** - min=10 statt 200 im Frontend und Backend
- **Preset-System implementiert** - 3 Presets (Standard, Konservativ, Aggressiv) mit visueller Auswahl
- **Startup Warm-Up** - ContextAgent initialisiert Datenquellen sofort nach Start
- **SIGNAL-REFORM S1 (2026-04-03)** - OFI-Gate entfernt, zeitbasierter Zyklus, Decision Feed aktiv
- **PHASE G.0 (2026-04-03)** - Learning Mode für DRY_RUN, Phantom Trades und trade_mode-Tagging abgeschlossen

### 📋 IMPLEMENTIERTE LÖSUNGEN (Legacy v1)
1. **API-Endpunkt Fixes:** Doppeltes /api/v1 Prefix in 3 Routern entfernt
2. **Fresh-Source-Gate:** Health-Reporting für Binance_REST, Deribit_Public, yFinance_Macro
3. **Config-Hot-Reload:** _load_config_value() Methode in QuantAgent & RiskAgent
4. **OFI Schema:** Frontend min=10, max=300, step=5 mit besseren Beschreibungen
5. **Preset-System:** Visuelle Preset-Buttons mit Konfigurations-Erklärungs-Block
6. **Gate-Schwelle:** Von <= 0 auf < 2 gesenkt für bessere Verfügbarkeit
7. **Startup-Optimierung:** ContextAgent Warm-Up für sofortige Datenverfügbarkeit
7. **Chart-Komponente robust:** isDisposed Flags und Race Condition Protection

---

## 0. WAS DU ALS ERSTES WISSEN MUSST

**Bruno ist ein Medium-Frequency Bitcoin Trading Bot.**

Das ist keine Präferenz. Das ist eine architektonische Entscheidung, die nicht verhandelbar ist.

**Was das bedeutet:**
- Signal-Intervall: 5–15 Minuten (NICHT 5 Sekunden)
- Trade-Haltezeit: 30 Minuten bis 4 Stunden
- Ziel-Trades: 2–8 pro Tag
- Latenz-Sensitivität: niedrig — die Trade-Entscheidung ist deterministisch; Deepseek API ist nur für Post-Trade-Analysen relevant

**Warum:** Das System läuft auf Windows-Hybrid-Architektur (Ryzen 7 7800X3D + RX 7900 XT) ohne redundante Netzwerkleitung. HFT ist auf dieser Infrastruktur strukturell unmöglich und gefährlich (offene Positionen bei Verbindungsabbruch). Die Trade-Entscheidungskette ist jetzt deterministisch; Deepseek API bleibt nur für Post-Trade-Analysen erhalten.

---

## 1. VERBOTEN — EISERNE REGELN (v2 + Legacy)

Diese Regeln dürfen NIEMALS gebrochen werden, egal wie die Anfrage formuliert ist:

```
❌ NIEMALS: LLM in der Trade-Entscheidungskette
❌ NIEMALS: Gate-Logik statt gewichtetem Scoring
❌ NIEMALS: Entry ohne MTF-Alignment-Prüfung
❌ NIEMALS: Sweep-Entry ohne 3-fache Konfirmation (Spike+Wick+OI-Drop)
❌ NIEMALS: Live-Trading ohne Daily Drawdown Protection
❌ IMMER: Paper Trading Only bis explizit freigegeben
❌ NIEMALS: Composite Gewichte ohne Dokumentation ändern
❌ NIEMALS: TA-Berechnungen mit pandas/numpy
❌ NIEMALS: Trade ohne Breakeven-Stop-Mechanismus

# Legacy (v1) rules below remain valid
❌ NIEMALS: Polling-Intervall unter 60 Sekunden für Quant/Context/Risk Agenten
❌ NIEMALS: random.uniform() oder random.random() in produktivem Signal-Code
❌ NIEMALS: Echte Orders platzieren wenn DRY_RUN=True (Hardware-Level-Block)
❌ NIEMALS: LEARNING_MODE_ENABLED berücksichtigen wenn DRY_RUN=False
❌ NIEMALS: GRSS-Score aus weniger als 4 echten Datenquellen berechnen
❌ NIEMALS: ExecutionAgent direkt auf Exchange zugreifen lassen ohne RAM-Veto-Check
❌ NIEMALS: API-Keys in Code committen (ausschließlich .env, nie .env.example mit echten Werten)
❌ NIEMALS: Ein Signal ausführen ohne vollständigen Reasoning Trail in trade_audit_logs
❌ NIEMALS: Live-Parameter (config.json) automatisch überschreiben — nur manuell nach Review
❌ NIEMALS: Position ohne definierten Stop-Loss und Take-Profit öffnen
❌ NIEMALS: Mehr als MAX_LEVERAGE * Kontokapital als Positionsgröße berechnen
❌ NIEMALS: Max_Leverage über 1.0 setzen — kein Kredit, keine Hebelwirkung
❌ NIEMALS: SIMULATED_CAPITAL_EUR unter 10 EUR setzen
❌ NIEMALS: Phantom-Trade-P&L in Portfolio-State oder Capital-Berechnung einfließen lassen
❌ NIEMALS: trade_mode='phantom' oder trade_mode='learning' in Live-Profit-Statistiken mischen
```

---

## 2. AKTUELLER PROJEKTSTATUS (Ehrlicher Ist-Stand)

### Was funktioniert ✅
- **Bruno — Strategie-Rewrite: VOM FILTER ZUM TRADER (Phase 2026-03-30) — NEU**
- **VETO-RELAXATION: VIX Limit 45, NDX Bearish blockiert nicht mehr — NEU**
- **INSTITUTIONALE SIGNALE: ETF Flows (Farside), OI-Trend (Binance), Max Pain (Deribit) — NEU**
- **FULL-DEPTH QUANT: 20-Level OFI & Liquidation Asymmetry — NEU**
- **LEARNING MODE (DRY_RUN only):** Niedrigere Signalschwellen für Trainingsdaten-Beschleunigung
- **PHANTOM TRADES:** HOLD-Zyklen werden hypothetisch ausgewertet (240min Outcome-Tracking)
- **TRADE MODE FLAG:** Jeder Trade in DB markiert als "learning" | "production" | "phantom"
- **Bruno Pulse: Real-time Transparenz (Sub-States & LLM Pulse)**
- **Legacy (v1):** LLM-Kaskade (3-Layer Entscheidungslogik mit qwen2.5/deepseek-r1)
- Docker Compose Stack (PostgreSQL/TimescaleDB, Redis Stack, FastAPI, Next.js)
- IngestionAgent: Binance WebSocket Multiplex (5 Streams), Batching, DB-Flush
- AgentOrchestrator: Supervision Tree, Staged Startup, Restart-Logic mit Agent Heartbeats (15s)
- ExecutionAgent: RAM-Veto-Check, DRY_RUN-Schutz, Shadow-Trading mit Fee-Simulation (0.04%)
- Security Isolation: PublicExchangeClient vs AuthenticatedExchangeClient
- NLP-Pipeline: BART-MNLI (Bouncer) → FinBERT (Makro) → CryptoBERT (Crypto)
- Dashboard: WebSocket-Streaming, Agent-Control (Pulse-Ready), Log-Terminal

### Was aktuell offen ist ⚠️
- **Frontend Phase E:** Open Position Panel, Kill-Switch und GRSS Breakdown fehlen noch
- **Dashboard-Integration:** Phase-E-Komponenten sind noch nicht in `dashboard/page.tsx` verdrahtet
- **Phase G:** Backtest Engine / Optuna-Kalibrierung ist noch offen
- **Phase G.0:** Learning Mode / Phantom Trades / trade_mode-Tagging ist jetzt in Arbeit
- **Phase H:** Live-Freigabe (`DRY_RUN=False`) ist noch offen

---

## 3. ZIEL-ARCHITEKTUR (10/10 — Non-Negotiable)

### 3.1 Das Signal-Universum — Alle Datenquellen

Jede Datenquelle hat eine Priorität (P1 = sofort, P2 = Phase B, P3 = Phase C):

#### KOSTENLOS — Binance (bereits teilweise implementiert)
| Quelle | Signal | Priorität | Status |
|--------|--------|-----------|--------|
| `btcusdt@kline_1m` WS | OHLCV 1m | P1 | ✅ implementiert |
| `btcusdt@depth20@100ms` WS | Orderbook Top-20, OFI | P1 | ✅ implementiert |
| `btcusdt@forceOrder` WS | Liquidations Real-time | P1 | ✅ implementiert |
| `btcusdt@markPrice@1s` WS | Funding Rate, Mark Price | P1 | ✅ implementiert |
| `btcdomusdt@kline_1m` WS | BTC Dominanz | P1 | ✅ implementiert |
| Binance REST `/fapi/v1/openInterest` | Open Interest aktuell | P1 | ✅ implementiert |
| Binance REST `/fapi/v1/openInterestHist` | OI History → OI-Delta berechnen | P1 | ❌ fehlt |
| Binance REST `/fapi/v1/globalLongShortAccountRatio` | Long/Short Ratio | P1 | ✅ implementiert |
| Binance Spot REST `/api/v3/ticker/price?symbol=BTCUSDT` | Spot-Preis für Perp-Basis | P1 | ❌ fehlt |
| Binance REST `/fapi/v1/ticker/price?symbol=BTCUSDT` | Futures-Preis für Perp-Basis | P1 | ❌ fehlt |

**Perp Basis Formel (P1, kostenlos):**
```python
perp_basis_pct = (futures_price - spot_price) / spot_price * 100
# positiv = Futures Premium (Bullish-Bias)
# negativ = Futures Discount (Bearish-Bias, sehr selten)
# Extrem > +0.5% oder < -0.1% → Warnsignal
```

#### KOSTENLOS — Deribit Public API (kein API-Key nötig)
| Endpoint | Signal | Priorität |
|----------|--------|-----------|
| `/api/v2/public/get_index_price?index_name=btc_usd` | BTC Index Price | P1 |
| `/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option` | Put/Call Ratio, Max Pain | P1 |
| `/api/v2/public/get_volatility_index_data?currency=BTC` | DVOL (BTC Implied Volatility) | P1 |
| `/api/v2/public/ticker?instrument_name=BTC-PERPETUAL` | Basis, OI Deribit Perp | P2 |

**Put/Call Ratio Logik:**
```python
# Berechnung aus get_book_summary_by_currency
puts_oi = sum(instrument['open_interest'] for i in instruments if '-P' in i['instrument_name'])
calls_oi = sum(instrument['open_interest'] for i in instruments if '-C' in i['instrument_name'])
pcr = puts_oi / calls_oi
# PCR < 0.5 → stark bullish (Calls dominieren)
# PCR 0.5–0.8 → neutral
# PCR > 0.8 → bearish (Hedging-Druck)
# PCR > 1.0 → extremes Hedging → potentieller Boden
```

### 3.1b Signal-Architektur (nach Reform S1, 2026-04-03)

**Paradigma-Wechsel:** Event-gesteuert → Zeitbasiert

Der QuantAgent evaluiert JEDEN 60s-Zyklus — unabhängig vom OFI-Wert.
OFI ist Input für den LLM, nicht Trigger für die Evaluation.

**Pre-Gate (QuantAgent):**
- GRSS < 20 → HOLD (Extremstress, LLM würde nichts lernen)
- Data_Freshness_Active == False → HOLD (keine validen Daten)
- Alles andere → LLM Cascade läuft

**GRSS-Gate (innerhalb LLM Cascade, unverändert):**
- GRSS < effective_threshold (regime-spezifisch, 35–55) → CASCADE_GRSS_HOLD
- Dieser Gate ist korrekt und bleibt erhalten

**OFI-Metrik (neu):**
- `market:ofi:ticks` (Redis List): IngestionAgent schreibt bei jedem @depth20 Update
- `OFI_Buy_Pressure`: Anteil Ticks mit bid_vol > ask_vol (0.0–1.0)
- `OFI_Mean_Imbalance`: Durchschnittliches Verhältnis bid/ask (1.0 = neutral)
- Kein absoluter Threshold — LLM interpretiert den Wert im Kontext

**Decision Feed:**
- Redis Key: `bruno:decisions:feed` (LPUSH, LTRIM 144)
- API: GET /api/v1/decisions/feed (bestehender Router, unverändert)
- Einträge: alle 60s plus event-driven Sweep-Rescoring, format-kompatibel mit bestehendem Frontend Interface

**Fixierte Bugs:**
- `grss_score` Key: war "score" → jetzt korrekt "GRSS_Score"
- `grss_components`: war leeres {} → jetzt volles GRSS-Payload
- `fresh_source_count == 0` → war return 0.0 → jetzt Penalty -20 (Minimum 25)

#### BEZAHLT — CoinGlass API (Hobbyist: $29/Monat — optional / später)
| Endpoint | Signal | Priorität |
|----------|--------|-----------|
| `/api/futures/openInterest/chart` | OI cross-exchange aggregiert | P1 |
| `/api/etf/list` | Bitcoin ETF Net Flows (IBIT, FBTC) 3-Tages-Aggregat | P1 |
| `/api/futures/liquidation/chart` | Liquidation Heatmap / Cluster Map | P2 |
| `/api/indicator/coinbase-premium` | Coinbase Premium Index | P2 |

**Cross-Exchange Funding Divergenz Logik:**
```python
# Wenn Binance-Funding deutlich abweicht von Bybit/OKX → Arbitrage-Druck
# Normaler Spread: < 0.005%
# Alarmierender Spread: > 0.02% → GRSS-Abzug
divergence = abs(binance_funding - bybit_funding)
```

**Hinweis:** Cross-Exchange Funding Divergenz wird jetzt kostenlos über Bybit + OKX Public APIs berechnet und benötigt keinen CoinGlass-Key mehr.

#### KOSTENLOS — Binance Futures Analytics + On-Chain (neu)
| Quelle | Signal | Priorität | Status |
|--------|--------|-----------|--------|
| Binance Futures `/futures/data/topLongShortPositionRatio` | Top Trader Long/Short Ratio | P1 | ✅ implementiert |
| Binance Futures `/futures/data/takerlongshortRatio` | Taker Buy/Sell Ratio | P1 | ✅ implementiert |
| Binance Futures `/futures/data/globalLongShortAccountRatio` | Global Long/Short Ratio | P1 | ✅ implementiert |
| Blockchain.com Charts | Hash Rate, Mempool Size | P2 | ✅ implementiert |
| Glassnode Free Tier | Exchange Balance BTC | P3 | ✅ optional / wenn Key vorhanden |
| Binance aggTrades `/fapi/v1/aggTrades` | CVD ohne Double-Counting | P1 | ✅ implementiert |

#### KOSTENLOS — Bestehende Quellen (bereits geplant/implementiert)
| Quelle | Signal | Status |
|--------|--------|--------|
| FRED API `DGS10` | US 10Y Treasury Yields | ✅ implementiert |
| FRED API `WM2NS` | US M2 Money Supply YoY% | ✅ implementiert |
| CBOE CSV `VIX_History` | VIX Index | ✅ implementiert (31.05 aktuell) |
| Yahoo Finance `^NDX` | Nasdaq SMA200 | ✅ implementiert (429-anfällig) |
| Alternative.me | Fear & Greed Index | ✅ implementiert |
| CryptoCompare API | News, Preise, Historie, Social, Blockchain | ✅ implementiert |
| CoinMarketCap API | Bitcoin-Marktmetriken + Global Metrics | ✅ implementiert |
| 8x RSS Feeds | FinBERT/CryptoBERT Input | ✅ implementiert |
| CoinGecko `coins/markets` | Stablecoin Supply Delta (USDT + USDC, 7d) | ✅ implementiert |
| Bybit Public + OKX Public | Cross-Exchange Funding Divergenz | ✅ implementiert |

**VIX Implementierung (✅ FIXED 30.03.2026):** CBOE CSV als primäre Quelle mit 3-Stufen-Fallback:
1. CBOE CSV (offiziell, keine Rate Limits) - VIX 31.05
2. Yahoo Finance (fallback, 429-anfällig)
3. Alpha Vantage (final, TIME_SERIES_DAILY)

---

### 3.2 Der echte GRSS-Score v2 (Opportunity-Driven)

**GRSS = Global Risk Sentiment Score (0–100)**
Paradigma: "Handeln wenn eine Gelegenheit besteht — mit dem Risiko das die Bedingungen vorgeben."

```python
def calculate_grss(data: dict) -> float:
    score = 50.0  # Neutral-Basis

    # === 1. DERIVATIVES LAYER (40% Gewicht) ===
    # Funding Rate (Binance)
    if -0.01 <= data['funding_rate'] <= 0.03: score += 12.0
    elif data['funding_rate'] > 0.05: score -= 12.0
    
    # OI-Delta + Preis-Richtung
    if data['oi_delta_pct'] > 0 and data['btc_change_1h'] > 0: score += 8.0
    # Put/Call Ratio
    if data['put_call_ratio'] < 0.45: score += 10.0
    elif data['put_call_ratio'] > 0.85: score -= 10.0

    # === 2. INSTITUTIONAL LAYER (20% Gewicht) ===
    # ETF Flows (Farside Investors)
    if data['etf_flow_3d_m'] > 500: score += 12.0
    elif data['etf_flow_3d_m'] < -500: score -= 12.0
    # OI-Trend 7d
    if data['oi_7d_change_pct'] > 5: score += 7.0
    # Stablecoin Delta
    if data['stablecoin_delta_bn'] > 2.0: score += 8.0

    # === 3. SENTIMENT LAYER (20% Gewicht) ===
    score += ((data['fear_greed'] - 50) / 50) * 10.0
    score += data['llm_news_sentiment'] * 8.0

    # === 4. MAKRO LAYER (20% Gewicht) — RELAXED ===
    if data['vix'] < 15: score += 8.0
    elif data['vix'] < 20: score += 4.0
    elif data['vix'] < 35: score -= 7.0
    elif data['vix'] < 45: score -= 14.0
    if data['ndx_status'] == 'BULLISH': score += 8.0
    elif data['ndx_status'] == 'BEARISH': score -= 10.0

    # === 5. PATTERN BONUS (Additive) ===
    score += data.get('pattern_score', 0)

    # === 6. ON-CHAIN TIER (neue freie Datenquellen) ===
    onchain = data.get('onchain', {})
    if onchain:
        if onchain.get('hash_rate_7d_change_pct', 0) > 5:
            score += 3.0
        elif onchain.get('hash_rate_7d_change_pct', 0) < -10:
            score -= 3.0
        if onchain.get('exchange_outflow'):
            score += 4.0
        elif onchain.get('exchange_balance_change_btc', 0) > 5000:
            score -= 4.0

    # === HARD VETOES (Nur Extreme) ===
    if data['vix'] > 45: return 10.0
    if data['news_silence_seconds'] > 7200: score -= 15.0
    elif data['news_silence_seconds'] > 3600: score -= 8.0
    
    return max(25.0, min(100.0, score))
```

**VOLATILITY-ADAPTIVE SIZING (RiskAgent):**
- VIX < 15: 1.0x Größe
- VIX 15-25: 0.8x Größe
- VIX 25-35: 0.6x Größe
- VIX 35-45: 0.3x Größe
- VIX > 45: VETO
```

---

### 3.3 Die LLM-Kaskade (3 Layer, sequenziell)

```
LAYER 1: Schnelle Klassifizierung (qwen2.5:14b, ~1–2s)
         Input: GRSS-Komponenten als strukturiertes JSON
         Output: { regime: "trending_bull|ranging|high_vola|bear",
                   confidence: 0.0–1.0,
                   key_signals: ["OI steigt", "Funding neutral", ...] }
         Gate: Wenn confidence < 0.60 → HOLD, kein Layer 2

         ↓ (nur wenn confidence >= 0.60)

LAYER 2: Strategisches Reasoning (deepseek-r1:14b, ~4–8s)
         Input: Layer 1 Output + vollständiger Marktkontext JSON
         System Prompt: "Du bist ein institutioneller Quant-Trader.
                         Denke Schritt für Schritt.
                         Analysiere das Chance-Risiko-Verhältnis.
                         Sei skeptisch gegenüber dem Offensichtlichen."
         Output: { decision: "BUY|SELL|HOLD",
                   confidence: 0.0–1.0,
                   entry_reasoning: "...",
                   risk_factors: ["...", "..."],
                   suggested_sl_pct: 0.008–0.02,
                   suggested_tp_pct: 0.016–0.04 }
         Gate: Wenn decision == HOLD oder confidence < 0.65 → Stop

         ↓ (nur wenn decision != HOLD und confidence >= 0.65)

LAYER 3: Advocatus Diaboli (qwen2.5:14b, ~1–2s)
         Input: Layer 2 Entscheidung + Marktkontext
         System Prompt: "Deine einzige Aufgabe: Finde Gründe
                         warum dieser Trade FALSCH ist.
                         Sei hart. Sei kritisch."
         Output: { blocker: true|false,
                   blocking_reasons: ["...", "..."],
                   risk_override: true|false }
         Gate: Wenn blocker == true → Signal abgebrochen, Reason geloggt

         ↓ (nur wenn kein Blocker)

LAYER 4: Regel-basiertes Risk-Gate (RiskAgent, 0ms RAM-Check)
         → GRSS < 40 → Veto
         → Liquidation Wall < 0.5% → Veto
         → CVD-Divergenz → Leverage-Reduktion
         → Daily Loss Limit überschritten → Veto

         ↓ (nur wenn kein Veto)

LAYER 5: Execution + Reasoning Trail
         → Order-Firing (DRY_RUN oder Live)
         → ALLE Layer-Outputs in trade_audit_logs speichern
         → Layer 1+2+3 Reasoning als JSON-Column `llm_reasoning` 
```

**LLM Memory zwischen Zyklen:**
Speichere die letzten 3 LLM-Entscheidungen als Rolling Context in Redis:
```
Key: bruno:llm:decision_history
Type: List (LPUSH + LTRIM 3)
```
Übergib diesen Context an Layer 2 als zusätzlichen System-Kontext.

---

### 3.4 Position Tracker (Pflicht vor Live-Betrieb)

```python
# Redis Key: bruno:positions:BTCUSDT
# Typ: JSON Hash
{
    "symbol": "BTCUSDT",
    "side": "long|short|none",
    "entry_price": 84500.0,
    "entry_time": "2026-03-27T14:30:00Z",
    "quantity": 0.01,
    "stop_loss_price": 83745.0,    # entry_price * (1 - sl_pct)
    "take_profit_price": 85770.0,  # entry_price * (1 + tp_pct)
    "max_adverse_excursion": 0.0,  # Tracking für Post-Trade Analyse
    "layer2_confidence": 0.74,
    "layer2_reasoning": "...",
    "grss_at_entry": 67.5,
    "signal_source": "llm_cascade",
    "status": "open|closed",
    "trade_id": "uuid"
}
```

**Stop-Loss Watcher** (separater asyncio Task, läuft alle 30 Sekunden):
```python
async def _watch_position(self):
    while self.state.running:
        position = await self.deps.redis.get_cache("bruno:positions:BTCUSDT")
        if position and position['status'] == 'open':
            current_price = await self._get_current_price()

            # Stop-Loss Check
            if position['side'] == 'long' and current_price <= position['stop_loss_price']:
                await self._close_position(position, reason="STOP_LOSS")

            # Take-Profit Check
            elif position['side'] == 'long' and current_price >= position['take_profit_price']:
                await self._close_position(position, reason="TAKE_PROFIT")

            # MAE Tracking (für Post-Trade Analyse)
            adverse = (current_price - position['entry_price']) / position['entry_price']
            if position['side'] == 'long' and adverse < position['max_adverse_excursion']:
                position['max_adverse_excursion'] = adverse
                await self.deps.redis.set_cache("bruno:positions:BTCUSDT", position)

        await asyncio.sleep(30)
```

**Position Sizing (konservativ, nicht Kelly in Phase 1):**
```python
def calculate_position_size(account_balance: float, grss: float,
                             layer2_confidence: float, max_leverage: float) -> float:
    # Basis: 2% des Kontos pro Trade
    base_risk_pct = 0.02

    # Skalierung basierend auf Signal-Qualität
    confidence_multiplier = layer2_confidence  # 0.65–1.0
    grss_multiplier = min(1.0, (grss - 40) / 60)  # 0–1.0 wenn GRSS 40–100

    position_value = account_balance * base_risk_pct * confidence_multiplier * grss_multiplier
    position_size = position_value / current_price

    # Hard Cap
    max_position = (account_balance * max_leverage) / current_price
    return min(position_size, max_position)
```

---

### 3.5 Regime-Detection (4 Marktregimes)

Der ContextAgent klassifiziert das aktuelle Regime. Vier Regime-Configs statt einer:

*OFI threshold removed in Reform S1 (2026-04-03); OFI is now rolling-buffer input only.*

```python
REGIME_CONFIGS = {
    "trending_bull": {
        "GRSS_Threshold": 45,       # Niedrigere Schwelle — Trend gibt Rückenwind
        "Max_Leverage": 1.0,
        "Stop_Loss_Pct": 0.008,
        "Take_Profit_Pct": 0.020,   # 2.5:1 R:R
        "allow_longs": True,
        "allow_shorts": False,       # Gegen den Trend ist gefährlich
    },
    "ranging": {
        "GRSS_Threshold": 55,       # Höhere Schwelle — weniger Klarheit
        "Max_Leverage": 1.0,
        "Stop_Loss_Pct": 0.006,
        "Take_Profit_Pct": 0.012,   # 2:1 R:R
        "allow_longs": True,
        "allow_shorts": True,
        "position_size_multiplier": 0.5,  # Halbe Größe in Chop
    },
    "high_vola": {
        "GRSS_Threshold": 60,
        "Max_Leverage": 1.0,        # Kein Leverage bei hoher Vola
        "Stop_Loss_Pct": 0.015,     # Weiterer Stop wegen Rauschen
        "Take_Profit_Pct": 0.030,
        "allow_longs": True,
        "allow_shorts": True,
        "position_size_multiplier": 0.3,
    },
    "bear": {
        "GRSS_Threshold": 50,
        "Max_Leverage": 1.0,
        "Stop_Loss_Pct": 0.010,
        "Take_Profit_Pct": 0.020,
        "allow_longs": False,       # Keine Longs im Bärenmarkt
        "allow_shorts": True,
    }
}
```

---

### 3.6 Lern-System (Post-Trade LLM Debrief)

Nach jedem geschlossenen Trade:

```python
async def _post_trade_debrief(self, closed_trade: dict):
    """
    Automatisches Lern-System.
    DeepSeek-R1 analysiert jeden geschlossenen Trade.
    Output wird in trade_debriefs DB-Tabelle gespeichert.
    """
    prompt = f"""
    Du analysierst einen abgeschlossenen Trade für das Bruno Trading System.

    TRADE-DATEN:
    - Symbol: {closed_trade['symbol']}
    - Seite: {closed_trade['side']}
    - Entry: {closed_trade['entry_price']} | Exit: {closed_trade['exit_price']}
    - P&L: {closed_trade['pnl_pct']:.2%} | Exit-Grund: {closed_trade['exit_reason']}
    - GRSS bei Entry: {closed_trade['grss_at_entry']}
    - Layer 2 Reasoning bei Entry: {closed_trade['layer2_reasoning']}
    - Max Adverse Excursion: {closed_trade['mae_pct']:.2%}
    - Haltezeit: {closed_trade['hold_duration_minutes']} Minuten

    ANALYSIERE:
    1. War die ursprüngliche Entscheidung korrekt? (ja/nein/teilweise)
    2. Welches Signal war am wichtigsten für den Ausgang?
    3. Was hätte die Entscheidung verbessert?
    4. Gibt es ein Muster das wir in Zukunft vermeiden/nutzen sollten?

    Antworte ausschließlich als JSON:
    {{
        "decision_quality": "correct|incorrect|timing_error",
        "key_signal": "...",
        "improvement": "...",
        "pattern": "...",
        "regime_assessment": "war das Regime korrekt klassifiziert?"
    }}
    """
    debrief = await ollama_client.generate_response(prompt, use_reasoning=True)
    # Speichern in trade_debriefs Tabelle (neue Migration nötig)
```

---

## 4. FRONTEND — VON BLACKBOX ZUM COCKPIT

Das Frontend ist kein Nice-to-Have. Es ist das Kontrollinstrument.
**Design-Philosophie: Institutionelles Trading Terminal — dunkel, dicht, präzise.**

### Pflicht-Widgets (P1 — vor Live-Betrieb):

**Open Position Panel** (prominenteste Position im Dashboard):
```
┌─────────────────────────────────────────────────┐
│  OPEN POSITION: BTCUSDT LONG                    │
│  Entry: $84,500  |  Qty: 0.01 BTC               │
│  P&L: +$12.50 (+1.48%)        [Live-Update]     │
│  SL: $83,745  |  TP: $85,770                    │
│  Reason: "OI steigt, Funding neutral, PCR 0.38" │
│  GRSS @Entry: 67.5  |  L2 Confidence: 74%       │
│  [CLOSE NOW]  [MOVE SL]  [EXTEND TP]            │
└─────────────────────────────────────────────────┘
```

**Kill-Switch** (immer sichtbar, nie ein modaler Dialog):
```
┌────────────────────────────────────┐
│  🔴 EMERGENCY STOP                 │
│  → Alle Positionen schließen       │
│  → Bot pausieren                   │
│  Require: Doppelklick + Bestätigung│
└────────────────────────────────────┘
```

**GRSS Breakdown Widget** (kein einzelner Score):
```
GRSS: 67.5 / 100  ████████████░░░░  [GRÜN — AKTIV]

Makro (30%):    ████████░░  +18.0 pts
  NDX: BULLISH +15 | VIX: 17.2 +7 | Yields: 4.3% ±0
Derivatives(40%):████████████░  +24.0 pts
  Funding: 0.012% +10 | PCR: 0.41 +12 | OI-Delta: +2 pts
Sentiment(30%): █████░░░░░  +15.0 pts
  F&G: 71 (Gier) +6 | ETF-Flows: +820M +10 | LLM: +4 pts
```

**Reasoning Trail** (für jeden Trade):
```
Trade #47 — BUY 0.01 BTCUSDT @ 84,500
├── Layer 1: regime=trending_bull, confidence=0.82
├── Layer 2: "OI steigt bei steigendem Preis — echte Akkumulation..."
├── Layer 3: "Kein Blocker. Einziges Risiko: Funding könnte überhitzen"
├── Risk Gate: GRSS=67.5 ✅ | Liq-Wall: 83,100 (abstand 1.7%) ✅
└── Execution: $84,502 fill | Slippage: +0.2 BPS | Latenz: 48ms
```

**Daten-Frische-Monitor** (für jede Datenquelle):
```
Binance WS:     ✅ Live  (< 100ms)
FRED Yields:    ✅ 8 Min ago
Deribit PCR:    ✅ 4 Min ago
CoinGlass ETF:  ⚠️ 23 Min ago  [über Threshold]
Fear & Greed:   ✅ 2h ago (täglich OK)
yFinance VIX:   ❌ 47 Min ago  [FEHLER — Fallback aktiv]
```

**Daily P&L + Drawdown Widget:**
```
Heute: +$34.20 (+1.12%)   Max Drawdown: -$8.50 (-0.28%)
Woche: +$127.80           Daily Loss Limit: -$XX (XX% verbleibend)
```

### Alle bestehenden Seiten behalten:
- Dashboard (erweitern)
- Agenten-Zentrale (behalten)
- Monitoring/MLOps (erweitern um Reasoning Trail)
- Backup (behalten)
- Einstellungen (um Regime-Config erweitern)
- Logs (behalten)

---

## 5. API-KEYS — BESCHAFFUNGSLISTE FÜR RUBEN

| API | Zweck | Kosten | Priorität | Env-Variable |
|-----|-------|--------|-----------|--------------|
| **Binance API** | Order Execution (Live) | Kostenlos | P1 | `BINANCE_API_KEY`, `BINANCE_SECRET` |
| **FRED API** | 10Y Yields | Kostenlos | ✅ P1 | `FRED_API_KEY` |
| **CryptoCompare API** | News Aggregation + Market Bundle | Kostenlos | ✅ P1 | `CRYPTOCOMPARE_API_KEY` |
| **CoinMarketCap API** | BTC Quotes + Global Metrics | Kostenlos | ✅ P1 | `COINMARKETCAP_API_KEY` |
| **Alpha Vantage API** | NDX Fallback | Kostenlos | ✅ P1 | `ALPHA_VANTAGE_API_KEY` |
| **CoinGlass API** | Funding, OI, ETF Flows, Liq Maps | $29/Monat (Hobbyist) | P1 | `COINGLASS_API_KEY` |
| **Telegram Bot Token** | Notifications | Kostenlos | P2 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

**Keine weiteren kostenpflichtigen APIs nötig.** Deribit, Binance REST (für OI, L/S-Ratio, Basis), Binance Futures Analytics und die On-Chain Quellen sind kostenlos zugänglich.

---

## 6. DATENBANK — NEUE MIGRATIONS NÖTIG

### Neue Tabellen (Alembic Migrations erstellen):

```sql
-- trade_debriefs: Post-Trade LLM Analyse
CREATE TABLE trade_debriefs (
    id UUID PRIMARY KEY,
    trade_id UUID REFERENCES trade_audit_logs(id),
    timestamp TIMESTAMPTZ NOT NULL,
    decision_quality VARCHAR(20),  -- correct|incorrect|timing_error
    key_signal TEXT,
    improvement TEXT,
    pattern TEXT,
    regime_assessment TEXT,
    raw_llm_response JSONB
);

-- market_regimes: Regime-Klassifizierung History
CREATE TABLE market_regimes (
    time TIMESTAMPTZ NOT NULL,
    regime VARCHAR(20) NOT NULL,  -- trending_bull|ranging|high_vola|bear
    confidence FLOAT,
    key_signals JSONB,
    grss FLOAT
);
SELECT create_hypertable('market_regimes', 'time');

-- agent_decisions: Vollständiger LLM Reasoning Trail
ALTER TABLE trade_audit_logs
ADD COLUMN IF NOT EXISTS llm_reasoning JSONB,
ADD COLUMN IF NOT EXISTS regime VARCHAR(20),
ADD COLUMN IF NOT EXISTS layer1_output JSONB,
ADD COLUMN IF NOT EXISTS layer2_output JSONB,
ADD COLUMN IF NOT EXISTS layer3_output JSONB,
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50),
ADD COLUMN IF NOT EXISTS hold_duration_minutes INTEGER,
ADD COLUMN IF NOT EXISTS pnl_pct FLOAT,
ADD COLUMN IF NOT EXISTS mae_pct FLOAT;
```

---

## 7. IMPLEMENTIERUNGS-PHASEN (Exakte Reihenfolge)

**PHASE A — Fundament (Woche 1–2) ✅ COMPLETED (2026-03-29)**

Ziel erreicht: Der Bot ist ehrlich. Kein Trade auf Basis von Zufallsdaten.

✅ **Erledigt:**
1. `ContextAgent`: Alle `random.uniform()` und `random.random()` entfernt
2. BTC 24h Change: Aus `market:ticker:BTCUSDT` Redis-Key berechnet
3. Binance REST Integration: Open Interest, L/S-Ratio, Perp-Basis hinzugefügt
4. Deribit Public API: Put/Call Ratio, DVOL integriert
5. GRSS-Formel: Durch echte Implementierung aus Abschnitt 3.2 ersetzt
6. `QuantAgent`: Polling-Intervall 5s → 300s
7. `ContextAgent`: Polling-Intervall 60s → 900s
8. CVD State: In Redis persistiert statt In-Memory-Float
9. **Data-Freshness Fail-Safe**: GRSS bricht bei stale data auf 0.0 ab
10. **Live-Trading Guard**: `LIVE_TRADING_APPROVED` Flag implementiert
11. **CryptoCompare + CoinMarketCap Health**: Health-Telemetrie mit Latenz-Tracking

**PHASE B — Daten-Erweiterung (Woche 2–3) ✅ COMPLETED**

1. CoinGlass wird nur noch für ETF Flows / OI / Liquidationen / Coinbase Premium genutzt
2. Telegram-Notifications laufen im Backend für Trade/Veto-Events
3. yFinance-Fix: Nasdaq-Fallback ist umgesetzt
4. Velocity-Layer: GRSS-Veränderungsrate ist integriert

**PHASE C — LLM-Kaskade (Woche 3–5) ✅ COMPLETED**

1. LLM-Kaskade (3 Layer) ist implementiert
2. Rolling Decision History in Redis ist vorhanden
3. LLM-Output wird in `trade_audit_logs` / Reasoning-Pfad geführt
4. Regime-Detection + Regime-Configs sind im Backend vorhanden

**PHASE D — Position Tracker + Exit-Logik (parallel zu C) ✅ COMPLETED**

1. Position Tracker Redis-Schema ist implementiert
2. Stop-Loss Watcher ist vorhanden
3. Take-Profit Handler ist vorhanden
4. Position Sizing ist vorhanden
5. DB-Migrations für die neuen Columns sind deployed

**PHASE E — Frontend Cockpit (parallel zu C/D) ❌ OFFEN**
1. Open Position Panel fehlt noch
2. Kill-Switch fehlt noch
3. GRSS Breakdown Widget fehlt noch
4. Daten-Frische-Monitor fehlt noch
5. Reasoning Trail in Trade-History fehlt noch
6. Daily P&L + Drawdown Widget fehlt noch

**PHASE F — Lern-System (Woche 5–7) ✅ COMPLETED (Backend)**
1. Post-Trade LLM Debrief ist implementiert
2. `trade_debriefs` Tabelle + Migration sind vorhanden
3. Manuelles Feedback-UI im Dashboard ist noch offen
4. Debrief-Analyse im MLOps-Dashboard ist noch offen

**PHASE G.0 — Learning Mode (DRY_RUN only) ✅ COMPLETED (2026-04-03)**
1. DRY_RUN-aware GRSS-Veto-Threshold (30 statt 40 im Learning Mode)
2. DRY_RUN-aware LLM Confidence-Schwellen (0.50/0.55 statt 0.60/0.65)
3. `trade_mode` Flag in `trade_audit_logs` und `trade_debriefs`
4. Phantom Trade System für HOLD-Zyklen (240min Outcome-Tracking)
5. Phantom Trade Evaluator als Scheduler-Loop (30min Intervall)
6. Migration `010_trade_mode_column.py` erstellt
7. `config.json` um Learning-Mode-Keys erweitert

Ziel erreicht: Mehr Paper-Trades/Tag + deutlich mehr Trainingsdaten, ohne Produktions-Logik zu kontaminieren.

**PHASE G — Backtest + Kalibrierung (Woche 7–9)**

1. Historische Binance Klines + Funding Rates laden (6 Monate)
2. offline_optimizer.py durch echtes Optuna-Grid ersetzen
3. Regime-Configs mit historischen Daten kalibrieren
4. Profit Factor > 1.5 verifizieren vor Live-Freigabe

**PHASE H — Live-Freigabe**

1. DRY_RUN=False erst nach bestandenem Backtest
2. Kapital-Allokation definieren (max 10% des Portfolios zu Beginn)
3. Daily Loss Limit setzen (empfohlen: 2% des deployed Kapitals)
4. Telegram-Monitoring aktiv
5. Erste Woche: Manuelles Monitoring jedes Trades

---

### ✅ PHASE F+ - Trade-Pipeline Diagnose & Startup-Race-Fix (2026-04-03)
- Debug Endpoint /api/v1/debug/trade-pipeline implementiert
- ContextAgent Warm-Up schreibt jetzt Minimal-GRSS Payload direkt nach setup()
- worker.py datetime Import Bug behoben (pause_bot NameError)
- /api/v1/agents/kill Endpoint implementiert (KillSwitch war wirkungslos)
- _audit_trade log_manager API Bug behoben (TypeError)
- risk.py News-Silence Key korrigiert: "last_update" → "timestamp"
- OllamaProvider Init-Logging in quant_v3 (LLM Config Transparenz)
- quant.py / execution.py als DEPRECATED markiert

---

### ✅ PHASE v2.1 - Ollama Entfernung & Binance API Integration (2026-04-04)
- **Ollama komplett entfernt**: Keine lokalen LLMs mehr im System
- **BinanceDataClient implementiert**: Zentraler API-Client für alle Marktdaten
- **MarketDataCollector erstellt**: Automatische Datensammlung alle 30s
- **LatencyMonitor bereinigt**: Keine Ollama-Abhängigkeiten mehr
- **Worker Pipeline angepasst**: Ollama-freier Start und Betrieb
- **Live Marktdaten verfügbar**: Ticker, Klines, Orderbook, Funding, OI, Liquidations
- **Frontend Integration**: Frische Daten für Dashboard und Trading-Seite
- **Dokumentation aktualisiert**: arch.md, trading_logic_v2.md, README.md

---

### ✅ PHASE v2.2 - Trade-Cascade Runtime Upgrade (2026-04-04)
- **Event-Driven Liquidation Trigger**: Force-Order-Spikes triggern sofortiges Quant-Rescoring via Redis Pub/Sub
- **Sweep Detection erweitert**: Liquidation-Events fließen direkt in die LiquidityEngine ein
- **TP1/TP2 Scaling-Out**: ExecutionAgentV4 und PositionTracker unterstützen Teilverkauf + Final Exit
- **Breakeven + ATR Trailing**: Nach TP1 wird der Stop auf Entry+0.1% gezogen, danach Chandelier-Trailing
- **MAE/MFE Tracking**: Positions- und Phantom-Trade-Auswertung berücksichtigen Extremwerte während der Haltedauer
- **Deepseek Debrief**: Post-Trade Analyse bleibt Deepseek-only, inklusive Phantom-/Hold-Auswertung
- **Position Monitor**: Hintergrundüberwachung für SL/TP1/TP2 und ATR-Trailing ist Teil des Runtime-Flows
- **Dokumentation aktualisiert**: Phase D, trading_logic_v2.md, arch.md, README.md

---

## 8. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL — NICHT DISKUTIEREN)

Diese Entscheidungen wurden bewusst getroffen und sind nicht verhandelbar:

| Entscheidung | Begründung |
|---|---|
| Medium-Frequency (5–15min Intervall) | Keine redundante Leitung, LLM-Latenz, Windows-Hybrid (Ryzen 7 7800X3D + RX 7900 XT) |
| **Binance API Integration (v2.1)** | **Keine API Keys für öffentliche Daten, 30s Updates, Redis Storage mit TTLs, Binance Analytics + On-Chain Erweiterung** |
| **Ollama entfernt (v2.1)** | **Keine lokalen LLMs mehr, nur Deepseek für Post-Trade Analyse** |
| Deepseek Cloud (Post-Trade) | Professionelle Reasoning API, keine lokalen Ressourcen nötig |
| Composite Scoring (deterministisch) | 100% reproduzierbare Entscheidungen, keine LLM-Latenz |
| GRSS als primäres Gate (nicht optionaler Filter) | Einheitlicher Risk-Score erzwingt Disziplin |
| Read-Only Live-Parameter (kein Auto-Override) | MLOps-Prinzip: Mensch entscheidet über Parameteränderungen |
| DRY_RUN Hardware-Block | Kapitalschutz ist absolut |
| TimescaleDB für Zeitreihendaten | Native Hypertable-Performance für OHLCV-Queries |
| Redis als Kommunikationsbus | Sub-Millisekunde Pub/Sub zwischen Agenten |
| Event-Driven Liquidation Rescoring | Force-Order-Spikes dürfen den normalen 60s-Zyklus überspringen |
| TP1/TP2 Scaling-Out + Breakeven + ATR Trailing | Realistischere Exit-Logik, kein Single-Target-only Verhalten |
| MAE/MFE für Live + Phantom | Trade-Qualität wird über Extremwerte und nicht nur Endpreis beurteilt |
| Reasoning Trail für jeden Trade | Transparenz ist Voraussetzung für Vertrauen und Lernen |
| Learning Mode nur in DRY_RUN | Produktions-Schwellen werden niemals durch Lernmodus kontaminiert. Trennung über trade_mode Flag in DB. |
| Phantom Trades für HOLDs | 288 auswertbare Zyklen/Tag statt 2. Kein Kapital-Einfluss. Outcome nach 240min aus Echtpreisen berechnet. |

---

## 9. QUALITÄTSZIEL

**Architektur: 10/10** → Wird mit Phase C (LLM-Kaskade) + Phase D (Position Tracker) erreicht
**Implementierung: 10/10** → Wird mit Phase A (echte Daten) + Phase G (Backtest) erreicht

Das System gilt als produktionsbereit wenn:
- [ ] GRSS basiert zu 100% auf echten Daten (kein random)
- [ ] Jede Position hat Stop-Loss und Take-Profit beim Entry
- [ ] Jeder Trade hat vollständigen Reasoning Trail (Layer 1+2+3)
- [ ] Backtest auf 6 Monate historische Daten mit Profit Factor > 1.5
- [ ] Dashboard zeigt offene Position, GRSS-Breakdown, Daten-Frische
- [ ] Kill-Switch funktioniert und ist getestet
- [ ] Telegram-Notifications aktiv

---

*Dieses Dokument wird gepflegt. Bei Änderungen der Strategie: zuerst hier dokumentieren, dann Code ändern.*
*Repository: https://github.com/Kazuo3o447/Bruno*
*V2.2 Review abgeschlossen: 2026-04-05 – Alle institutionellen Fixes validiert*
