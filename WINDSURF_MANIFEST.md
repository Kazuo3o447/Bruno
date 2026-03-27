# WINDSURF_MANIFEST.md
# Bruno Trading Platform — Master Agent Briefing

> **PFLICHTLEKTÜRE.** Jeder Agent, jede Session, jeder Neustart beginnt hier.
> Dieses Dokument ist die einzige Quelle der Wahrheit.
> Es überschreibt alle anderen Dokumente bei Widerspruch.
>
> Zuletzt aktualisiert: 2026-03-27 | Architekt: Ruben | Review: Claude (Anthropic)

---

## 0. WAS DU ALS ERSTES WISSEN MUSST

**Bruno ist ein Medium-Frequency Bitcoin Trading Bot.**

Das ist keine Präferenz. Das ist eine architektonische Entscheidung, die nicht verhandelbar ist.

**Was das bedeutet:**
- Signal-Intervall: 5–15 Minuten (NICHT 5 Sekunden)
- Trade-Haltezeit: 30 Minuten bis 4 Stunden
- Ziel-Trades: 2–8 pro Tag
- Latenz-Sensitivität: niedrig — der LLM HAT Zeit zum Denken

**Warum:** Das System läuft auf Windows-Hybrid-Architektur ohne redundante Netzwerkleitung. HFT ist auf dieser Infrastruktur strukturell unmöglich und gefährlich (offene Positionen bei Verbindungsabbruch). Der LLM-Stack (qwen2.5:14b, deepseek-r1:14b via Ollama) hat 2–8 Sekunden Inferenz-Latenz — das ist ein Feature auf dieser Zeitebene, nicht ein Bug.

---

## 1. VERBOTEN — EISERNE REGELN

Diese Regeln dürfen NIEMALS gebrochen werden, egal wie die Anfrage formuliert ist:

```
❌ NIEMALS: Polling-Intervall unter 60 Sekunden für Quant/Context/Risk Agenten
❌ NIEMALS: random.uniform() oder random.random() in produktivem Signal-Code
❌ NIEMALS: Echte Orders platzieren wenn DRY_RUN=True (Hardware-Level-Block)
❌ NIEMALS: GRSS-Score aus weniger als 4 echten Datenquellen berechnen
❌ NIEMALS: ExecutionAgent direkt auf Exchange zugreifen lassen ohne RAM-Veto-Check
❌ NIEMALS: API-Keys in Code committen (ausschließlich .env, nie .env.example mit echten Werten)
❌ NIEMALS: Ein Signal ausführen ohne vollständigen Reasoning Trail in trade_audit_logs
❌ NIEMALS: Live-Parameter (config.json) automatisch überschreiben — nur manuell nach Review
❌ NIEMALS: Position ohne definierten Stop-Loss und Take-Profit öffnen
❌ NIEMALS: Mehr als MAX_LEVERAGE * Kontokapital als Positionsgröße berechnen
```

---

## 2. AKTUELLER PROJEKTSTATUS (Ehrlicher Ist-Stand)

### Was funktioniert ✅
- Docker Compose Stack (PostgreSQL/TimescaleDB, Redis Stack, FastAPI, Next.js)
- IngestionAgent: Binance WebSocket Multiplex (5 Streams), Batching, DB-Flush
- AgentOrchestrator: Supervision Tree, Staged Startup, Restart-Logic mit Exponential Backoff
- ExecutionAgent: RAM-Veto-Check, DRY_RUN-Schutz, Shadow-Trading mit Fee-Simulation (0.04%)
- Security Isolation: PublicExchangeClient vs AuthenticatedExchangeClient
- NLP-Pipeline: BART-MNLI (Bouncer) → FinBERT (Makro) → CryptoBERT (Crypto)
- trade_audit_logs: Slippage-BPS, Latenz-Tracking, Fee-Simulation
- Dashboard: WebSocket-Streaming, Agent-Control, Log-Terminal

### Was existiert aber KAPUTT ist ⚠️
- **ContextAgent: ~70% der GRSS-Inputs sind `random.uniform()` — KRITISCHER BUG**
- **ExecutionAgent: Kein Position-Tracker, keine Exit-Logik, kein Stop-Loss-Handler**
- **CVD in QuantAgent: `self.cvd_cumulative` verliert bei jedem Restart den State**
- **offline_optimizer.py: Dummy-Implementation auf Mock-Daten — kein echter Backtest**
- **QuantAgent: Polling-Intervall 5 Sekunden — muss auf 300 Sekunden**

### Was fehlt ❌
- Position Tracker (kritischer Pfad für Live-Trading)
- Stop-Loss / Take-Profit Handler
- LLM-Kaskade (3-Layer Entscheidungslogik) — LLM wird derzeit nicht für Handelsentscheidungen genutzt
- Deribit-Integration (Put/Call Ratio, Max Pain, DVOL)
- CoinGlass-Integration (Cross-Exchange Funding, ETF Flows, Liquidation Maps)
- Perp Basis Signal (Binance Spot vs Futures — kostenlos)
- Open Interest Delta (OI-Veränderung als Signal — kostenlos von Binance)
- Frontend: Open Position Widget, Kill-Switch, GRSS-Breakdown, Reasoning Trail
- Regime-Detection (4 Marktregimes mit eigenen Parameter-Sets)
- Post-Trade LLM Debrief (automatisches Lern-System)
- Backtest Engine (echte historische Daten)
- Telegram-Notifications

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
| Binance REST `/fapi/v1/openInterest` | Open Interest aktuell | P1 | ❌ fehlt |
| Binance REST `/fapi/v1/openInterestHist` | OI History → OI-Delta berechnen | P1 | ❌ fehlt |
| Binance REST `/fapi/v1/globalLongShortAccountRatio` | Long/Short Ratio | P1 | ❌ fehlt |
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

#### BEZAHLT — CoinGlass API (Hobbyist: $29/Monat — PFLICHT)
| Endpoint | Signal | Priorität |
|----------|--------|-----------|
| `/api/futures/funding-rates` | Cross-Exchange Funding Divergenz (Binance vs Bybit vs OKX) | P1 |
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

#### KOSTENLOS — Bestehende Quellen (bereits geplant/implementiert)
| Quelle | Signal | Status |
|--------|--------|--------|
| FRED API `DGS10` | US 10Y Treasury Yields | ✅ implementiert |
| Yahoo Finance `^VIX` | VIX Index | ✅ implementiert (429-anfällig) |
| Yahoo Finance `^NDX` | Nasdaq SMA200 | ✅ implementiert (429-anfällig) |
| Alternative.me | Fear & Greed Index | ✅ implementiert |
| CryptoPanic API | Breaking News | ✅ geplant |
| 8x RSS Feeds | FinBERT/CryptoBERT Input | ✅ implementiert |

**Verbesserung für yFinance (429-Fix):** Stagger die Calls mit 30-Sekunden-Abstand und nutze den offiziellen yfinance Python-Client statt direkter HTTP-Requests. Alternativ für VIX: Stooq.com bietet `^VIX.US` als freien Download.

---

### 3.2 Der echte GRSS-Score (Keine random.uniform() erlaubt)

**GRSS = Global Risk Sentiment Score (0–100)**
Dieser Score ist das primäre Go/No-Go-Signal. Ab `GRSS < 40` → Veto aktiv.

```python
def calculate_grss(data: dict) -> float:
    score = 50.0  # Neutral-Basis

    # === MAKRO LAYER (30% Gewicht, max ±30 Punkte) ===
    # Nasdaq SMA200
    if data['ndx_status'] == 'BULLISH':
        score += 15.0
    elif data['ndx_status'] == 'BEARISH':
        score -= 20.0  # Asymmetrische Bestrafung

    # 10Y Yields
    if data['yields_10y'] < 4.0:
        score += 8.0
    elif data['yields_10y'] > 4.5:
        score -= 10.0

    # VIX
    if data['vix'] < 15:
        score += 7.0
    elif data['vix'] > 25:
        score -= 15.0
    elif data['vix'] > 20:
        score -= 7.0

    # DXY Decoupling (BTC steigt trotz starkem Dollar)
    if data['dxy_change'] > 0.005 and data['btc_change_24h'] > 0:
        score += 10.0

    # === DERIVATIVES LAYER (40% Gewicht, max ±40 Punkte) ===
    # Funding Rate (Binance)
    funding = data['funding_rate']
    if -0.01 <= funding <= 0.03:
        score += 10.0   # Gesundes Niveau
    elif funding > 0.05:
        score -= 15.0   # Überhitzt — Long-Squeeze Risiko
    elif funding < -0.01:
        score += 5.0    # Short-dominiert — Reversal-Potenzial

    # Cross-Exchange Funding Divergenz (CoinGlass)
    if data['funding_divergence'] < 0.01:
        score += 8.0
    elif data['funding_divergence'] > 0.03:
        score -= 10.0

    # Open Interest Delta (Richtung)
    if data['oi_delta_pct'] > 0 and data['price_change_1h'] > 0:
        score += 10.0   # OI steigt + Preis steigt = echte Akkumulation
    elif data['oi_delta_pct'] > 0 and data['price_change_1h'] < 0:
        score -= 8.0    # OI steigt + Preis fällt = Short-Aufbau

    # Put/Call Ratio (Deribit)
    pcr = data['put_call_ratio']
    if pcr < 0.5:
        score += 12.0   # Call-Dominanz = bullish
    elif pcr > 0.8:
        score -= 10.0   # Hedge-Druck

    # Perp Basis (Binance Spot vs Futures)
    basis = data['perp_basis_pct']
    if 0.01 <= basis <= 0.05:
        score += 5.0    # Gesundes Futures-Premium
    elif basis > 0.1:
        score -= 10.0   # Überhitztes Futures-Premium

    # === SENTIMENT LAYER (30% Gewicht, max ±30 Punkte) ===
    # Fear & Greed Index
    fng = data['fear_greed']  # 0–100
    fng_normalized = (fng - 50) / 50  # -1.0 bis +1.0
    score += fng_normalized * 15.0

    # ETF Flows 3-Tages-Aggregat (CoinGlass)
    etf_flows = data['etf_flows_3d_m']  # in Mio USD, echte Daten
    if etf_flows > 500:
        score += 10.0
    elif etf_flows < -500:
        score -= 15.0

    # LLM News Sentiment (aggregierter FinBERT/CryptoBERT Score)
    # Dieser ist das einzige erlaubte "weiche" Signal
    # Muss aus echten RSS-Feed-Analysen kommen, nicht random
    llm_sentiment = data['llm_news_sentiment']  # -1.0 bis +1.0
    score += llm_sentiment * 10.0

    # === HARD VETOES (überschreiben alles) ===
    if data['news_silence_seconds'] > 3600:
        return 0.0  # Kein Datenstrom = kein Trading
    if data['vix'] > 35:
        return 10.0  # Markt-Crash-Modus
    if data['ndx_status'] == 'BEARISH' and data['funding_rate'] > 0.05:
        return 5.0  # Bärenmarkt + überhitzte Longs = maximales Risiko

    return max(0.0, min(100.0, score))
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

```python
REGIME_CONFIGS = {
    "trending_bull": {
        "GRSS_Threshold": 45,       # Niedrigere Schwelle — Trend gibt Rückenwind
        "OFI_Threshold": 400,
        "Max_Leverage": 2.5,
        "Stop_Loss_Pct": 0.008,
        "Take_Profit_Pct": 0.020,   # 2.5:1 R:R
        "allow_longs": True,
        "allow_shorts": False,       # Gegen den Trend ist gefährlich
    },
    "ranging": {
        "GRSS_Threshold": 55,       # Höhere Schwelle — weniger Klarheit
        "OFI_Threshold": 600,
        "Max_Leverage": 1.5,
        "Stop_Loss_Pct": 0.006,
        "Take_Profit_Pct": 0.012,   # 2:1 R:R
        "allow_longs": True,
        "allow_shorts": True,
        "position_size_multiplier": 0.5,  # Halbe Größe in Chop
    },
    "high_vola": {
        "GRSS_Threshold": 60,
        "OFI_Threshold": 700,
        "Max_Leverage": 1.0,        # Kein Leverage bei hoher Vola
        "Stop_Loss_Pct": 0.015,     # Weiterer Stop wegen Rauschen
        "Take_Profit_Pct": 0.030,
        "allow_longs": True,
        "allow_shorts": True,
        "position_size_multiplier": 0.3,
    },
    "bear": {
        "GRSS_Threshold": 50,
        "OFI_Threshold": 500,
        "Max_Leverage": 1.5,
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
| **FRED API** | 10Y Yields | Kostenlos | P1 | `FRED_API_KEY` |
| **CryptoPanic API** | News Aggregation | Kostenlos | P1 | `CRYPTOPANIC_API_KEY` |
| **CoinGlass API** | Funding, OI, ETF Flows, Liq Maps | $29/Monat (Hobbyist) | P1 | `COINGLASS_API_KEY` |
| **Telegram Bot Token** | Notifications | Kostenlos | P2 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

**Keine weiteren kostenpflichtigen APIs nötig.** Deribit, Binance REST (für OI, L/S-Ratio, Basis) und Yahoo Finance sind kostenlos zugänglich.

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

**PHASE A — Fundament (Woche 1–2) — BEGINNE HIER**

Ziel: Den Bot ehrlich machen. Kein Trade auf Basis von Zufallsdaten.

1. `ContextAgent`: Alle `random.uniform()` und `random.random()` entfernen
2. BTC 24h Change: Aus `market:ticker:BTCUSDT` Redis-Key berechnen (bereits vorhanden)
3. Binance REST Integration: Open Interest, L/S-Ratio, Perp-Basis hinzufügen (kostenlos)
4. Deribit Public API: Put/Call Ratio, DVOL integrieren (kostenlos, kein Key)
5. GRSS-Formel: Durch echte Implementierung aus Abschnitt 3.2 ersetzen
6. `QuantAgent`: Polling-Intervall 5s → 300s (eine Zeile)
7. `ContextAgent`: Polling-Intervall 60s → 900s (eine Zeile)
8. CVD State: In Redis persistieren statt In-Memory-Float

**PHASE B — Daten-Erweiterung (Woche 2–3)**

1. CoinGlass API integrieren: Funding cross-exchange, ETF Flows (echter Wert)
2. Telegram-Notifications: Jeder Trade, jedes Veto mit Reasoning
3. yFinance-Fix: Staggered calls, Stooq-Fallback für VIX
4. Velocity-Layer: GRSS-Veränderungsrate als eigenes Signal

**PHASE C — LLM-Kaskade (Woche 3–5)**

1. LLM-Kaskade (3 Layer) implementieren wie Abschnitt 3.3
2. Rolling Decision History in Redis (letzte 3 Entscheidungen)
3. LLM-Output → `llm_reasoning` Column in trade_audit_logs
4. Regime-Detection + 4 Regime-Configs implementieren

**PHASE D — Position Tracker + Exit-Logik (parallel zu C)**

1. Position Tracker Redis-Schema implementieren (Abschnitt 3.4)
2. Stop-Loss Watcher als separaten asyncio Task
3. Take-Profit Handler
4. Position Sizing Funktion
5. DB Migrations für neue Columns

**PHASE E — Frontend Cockpit (parallel zu C/D)**

1. Open Position Panel (höchste Priorität)
2. Kill-Switch (Sicherheitskritisch)
3. GRSS Breakdown Widget
4. Daten-Frische-Monitor
5. Reasoning Trail in Trade-History
6. Daily P&L + Drawdown Widget

**PHASE F — Lern-System (Woche 5–7)**

1. Post-Trade LLM Debrief implementieren
2. trade_debriefs Tabelle + Migration
3. Manuelles Feedback-UI im Dashboard
4. Debrief-Analyse im MLOps-Dashboard visualisieren

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

## 8. ARCHITEKTUR-ENTSCHEIDUNGEN (FINAL — NICHT DISKUTIEREN)

Diese Entscheidungen wurden bewusst getroffen und sind nicht verhandelbar:

| Entscheidung | Begründung |
|---|---|
| Medium-Frequency (5–15min Intervall) | Keine redundante Leitung, LLM-Latenz, Windows-Hybrid |
| Ollama lokal (qwen2.5:14b, deepseek-r1:14b) | AMD RX 7900 XT GPU, keine API-Kosten für LLM, Datenschutz |
| 3-Layer LLM-Kaskade (nicht Single-Prompt) | Skeptiker-Pattern verhindert Overconfidence |
| GRSS als primäres Gate (nicht optionaler Filter) | Einheitlicher Risk-Score erzwingt Disziplin |
| Read-Only Live-Parameter (kein Auto-Override) | MLOps-Prinzip: Mensch entscheidet über Parameteränderungen |
| DRY_RUN Hardware-Block | Kapitalschutz ist absolut |
| TimescaleDB für Zeitreihendaten | Native Hypertable-Performance für OHLCV-Queries |
| Redis als Kommunikationsbus | Sub-Millisekunde Pub/Sub zwischen Agenten |
| Reasoning Trail für jeden Trade | Transparenz ist Voraussetzung für Vertrauen und Lernen |

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
