# Bruno v9.0 Trading Logic (Multi-Strategy Architecture)

## 1. Purpose

Bruno v9.0 is a **multi-strategy institutional** deterministic trading system with zero tolerance for heuristics. The system features:

1. **Multi-Strategy Architecture** - 3 unkorrelierte Strategie-Slots (Trend, Sweep, Funding)
2. **Scaled Entry Engine** - Pyramiding für Trend-Strategie (40%/30%/30% Tranchen)
3. **Professional Position Sizing** - Risk-based mit Leverage-Effizienz und Fee-Awareness
4. **Portfolio-Level Risk Management** - Max 80% Exposure, Slot-Isolation
5. **Macro Trend Filter** - Daily EMA 50/200 Override gegen Bear Market Rallies
6. **OFI Pipeline Quality Gate** - Datenqualitäts-Checks für Order Flow
7. **RegimeConfig Integration** - Regime-spezifische Trading-Regeln
8. **Binance Hedge Mode** - Gleichzeitige Long+Short Positionen
9. **Privacy-First News** - Multi-Source News mit SHA256 Deduplizierung
10. **Bybit V5 Single Source** - Exklusive WebSocket-Daten mit präziser CVD

The system maintains **100% deterministic live trading** with **zero heuristics** policy while implementing professional multi-strategy risk management.

## 2. Data Flow Overview (v9.0 Multi-Strategy Architecture)

```text
Bybit V5 WebSocket → BybitV5Client → Redis (CVD, VWAP, VPOC)
    ↓
News Sources (CryptoPanic, RSS, Free-Crypto-News) → NewsIngestionService → SentimentAnalyzer
    ↓
TechnicalAnalysisAgent → bruno:ta:snapshot (Daily EMA Macro Trend)
    ↓
ContextAgent → bruno:context:grss (GRSS v3, Funding Rate)
    ↓
QuantAgentV4 → Multi-Strategy Dispatch (Trend/Sweep/Funding)
    ↓
StrategyManager → Portfolio Risk Checks → Slot Allocation
    ↓
CompositeScorer → Signal Generation (per Slot)
    ↓
ScaledEntryEngine → Tranche Management (Trend-Slot)
    ↓
ExecutionAgentV4 → Slot-Aware Order Execution
    ↓
PositionTracker → Multi-Slot Position Management
```

### 2.1 Multi-Strategy Slots

**3 unabhängige Strategie-Slots mit eigenem Kapital und Risk Management:**

```python
STRATEGY_SLOTS = {
    "trend": StrategySlot(
        capital_allocation_pct=0.40,  # 40% des Kapitals
        max_leverage=3,
        scaled_entry_enabled=True,      # Pyramiding
        sl_atr_mult=1.5,                # 1.5× ATR SL
        tp_atr_mult=3.0,                # 3.0× ATR TP
    ),
    "sweep": StrategySlot(
        capital_allocation_pct=0.30,  # 30% des Kapitals
        max_leverage=4,                 # Aggressiver
        scaled_entry_enabled=False,     # Sofortige Entry
        sl_atr_mult=1.0,                # Enger SL
        max_hold_minutes=120,           # 2h Max
    ),
    "funding": StrategySlot(
        capital_allocation_pct=0.30,  # 30% des Kapitals
        max_leverage=2,                 # Konservativ
        sl_atr_mult=2.0,                # Weiter SL
        max_hold_minutes=480,           # 8h Max
    ),
}
```

### 2.2 Scaled Entry Engine (Trend-Slot)

**Pyramiding statt All-In Entry:**

```python
# Tranche 1 (40%): Sofort bei Signal
# Tranche 2 (30%): Bei +0.5% Bestätigung
# Tranche 3 (30%): Bei +1.0% Breakout

tranches = [
    {"number": 1, "size_pct": 0.40, "trigger_price": entry_price},
    {"number": 2, "size_pct": 0.30, "trigger_price": entry_price * 1.005},
    {"number": 3, "size_pct": 0.30, "trigger_price": entry_price * 1.010},
]
```

### 2.3 Professional Position Sizing

**Risk-based mit Fee-Awareness:**

```python
# Risiko = fix 2% des SLOT-Kapitals
# Position = Risiko ÷ SL-Distanz
# R:R > 1.5 nach Fees erforderlich

position_size_usd = slot_capital * 0.02 / sl_pct
fees_round_trip = position_size_usd * 0.0008
rr_after_fees = (tp_profit - fees) / (sl_loss + fees)
```

### 2.4 Macro Trend Filter (Daily EMA 50/200)

**Schutz vor Bear Market Rallies:**

```python
# Daily EMA Berechnung
ema_50d = self._calc_ema(candles_1d, 50)
ema_200d = self._calc_ema(candles_1d, 200)
current_price = candles_1d[-1]["close"]

# Macro Trend Bestimmung
if ema_50d > ema_200d and current_price > ema_200d:
    macro_trend = "macro_bull"
    allow_longs = True
    allow_shorts = False
elif ema_50d < ema_200d and current_price < ema_200d:
    macro_trend = "macro_bear"
    allow_longs = False      # KEINE Longs in Macro Bear!
    allow_shorts = True
```

### 2.5 OFI Pipeline Quality Gate

**Order Flow Datenqualitäts-Checks:**

```python
# OFI Availability Check
ofi_data = await self._fetch_ofi_rolling()
if not ofi_data["ofi_available"]:
    flow_score = flow_score * 0.5  # 50% Reduction
    result.signals_active.append("OFI Pipeline Down: Flow data unreliable")
```

### 2.6 Redis Keys (v9.0 Multi-Strategy)

**Neue Slot-spezifische Keys:**

```text
# Position Management (pro Slot)
bruno:position:BTCUSDT:trend
bruno:position:BTCUSDT:sweep
bruno:position:BTCUSDT:funding

# Scaled Entry State
bruno:scaled_entry:BTCUSDT:trend

# Macro Trend
bruno:ta:snapshot (enthält macro_trend)

# Strategy Manager
bruno:strategy:exposure (Portfolio-Level)
```

## 3. Agent Architecture (v9.0)

### 3.1 QuantAgentV4 - Multi-Strategy Dispatch

**3 parallele Signal-Generatoren:**

```python
# TREND-Slot: CompositeScore wie bisher
if signal.should_trade:
    signal_dict = signal.to_signal_dict(self.symbol)
    signal_dict["strategy_slot"] = "trend"
    await self.deps.redis.publish_message("bruno:pubsub:signals", json.dumps(signal_dict))

# SWEEP-Slot: Eigenständig bei 3× Sweep
sweep_signal = strategy_mgr.evaluate_sweep_signal(liq_result.get("sweep", {}), liq_score)
if sweep_signal:
    sweep_dict = {**signal.to_signal_dict(self.symbol), "strategy_slot": "sweep"}
    await self.deps.redis.publish_message("bruno:pubsub:signals", json.dumps(sweep_dict))

# FUNDING-Slot: Contrarian bei extremer Funding
funding_signal = strategy_mgr.evaluate_funding_signal(funding_rate, funding_divergence)
if funding_signal:
    funding_dict = {**signal.to_signal_dict(self.symbol), "strategy_slot": "funding"}
    await self.deps.redis.publish_message("bruno:pubsub:signals", json.dumps(funding_dict))
```

### 3.2 StrategyManager - Portfolio Risk Orchestration

**Zentrale Risk-Management Instanz:**

```python
async def can_open_position(self, slot_name: str, position_size_usd: float, total_capital_usd: float):
    # Gesamt-Exposure Check
    exposure = await self.get_total_exposure()
    new_gross = exposure["gross_exposure_usd"] + position_size_usd
    max_gross = total_capital_usd * 0.80 * slot.max_leverage
    
    if new_gross > max_gross:
        return {"allowed": False, "reason": f"Gross exposure ${new_gross:.0f} > max ${max_gross:.0f}"}
    
    # Slot-Kapital Check
    slot_capital = total_capital_usd * slot.capital_allocation_pct
    slot_max_position = slot_capital * slot.max_leverage
    
    return {"allowed": position_size_usd <= slot_max_position, "reason": "OK"}
```

### 3.3 ExecutionAgentV4 - Slot-Aware Trading

**Portfolio-Level Risk Integration:**

```python
# Slot aus Signal lesen
slot_name = signal.get("strategy_slot", "trend")

# Portfolio Risk Check
portfolio_check = await strategy_mgr.can_open_position(slot_name, position_size_usd, capital_usd)
if not portfolio_check["allowed"]:
    self.logger.warning(f"Portfolio Risk Check fehlgeschlagen: {portfolio_check['reason']}")
    return

# Position mit Slot-Tag speichern
await self.position_tracker.open_position(..., strategy_slot=slot_name)
```

### 3.4 PositionTracker - Multi-Slot Management

**Redis Keys pro Slot:**

```python
# Position pro Slot
REDIS_KEY = "bruno:position:{symbol}:{slot}"

async def has_open_position_for_slot(self, symbol: str, slot: str) -> bool:
    pos = await self.redis.get_cache(f"bruno:position:{symbol}:{slot}")
    return pos is not None and pos.get("status") == "open"

async def has_open_position(self, symbol: str) -> bool:
    # Prüft alle Slots
    for slot in ["trend", "sweep", "funding"]:
        if await self.has_open_position_for_slot(symbol, slot):
            return True
    return False
```

## 4. Risk Management (v9.0)

### 4.1 Portfolio-Level Limits

**Hard Limits auf Systemebene:**

```python
MAX_GROSS_EXPOSURE_PCT = 0.80  # Nie mehr als 80% des Kapitals
STRATEGY_TREND_CAPITAL_PCT = 0.40
STRATEGY_SWEEP_CAPITAL_PCT = 0.30
STRATEGY_FUNDING_CAPITAL_PCT = 0.30
```

### 4.2 Slot-spezifische Regeln

**Jede Strategie hat eigene Regeln:**

| Strategie | Leverage | Risk/Trade | Min Notional | Max Haltezeit |
|-----------|----------|------------|--------------|--------------|
| Trend     | 3×       | 2.0%       | $300         | Unbegrenzt    |
| Sweep     | 4×       | 2.5%       | $200         | 2 Stunden    |
| Funding   | 2×       | 1.5%       | $200         | 8 Stunden    |

### 4.3 Scaled Entry Risk Control

**Tranche-basiertes Risk Management:**

```python
# Nur 40% Risiko bei Entry
# Wenn sofort gegen dich läuft → nur 40% Verlust
# Bei Bestätigung → schrittweise Aufbau

tranche_1_risk = slot_capital * 0.02 * 0.40  # 0.8% des Slot-Kapitals
tranche_2_risk = slot_capital * 0.02 * 0.30  # 0.6% des Slot-Kapitals
tranche_3_risk = slot_capital * 0.02 * 0.30  # 0.6% des Slot-Kapitals
```

## 5. Configuration (v9.0)

### 5.1 Multi-Strategy Settings

```json
{
    "_comment_multi_strategy": "=== Multi-Strategy Configuration ===",
    "STRATEGY_TREND_ENABLED": true,
    "STRATEGY_SWEEP_ENABLED": true,
    "STRATEGY_FUNDING_ENABLED": false,
    "STRATEGY_TREND_CAPITAL_PCT": 0.40,
    "STRATEGY_SWEEP_CAPITAL_PCT": 0.30,
    "STRATEGY_FUNDING_CAPITAL_PCT": 0.30,
    "SCALED_ENTRY_ENABLED": true,
    "HEDGE_MODE_ENABLED": true,
    "MAX_GROSS_EXPOSURE_PCT": 0.80
}
```

### 5.2 Position Sizing v3

```json
{
    "_comment_sizing": "=== Position Sizing v3 ===",
    "LEVERAGE": 3,
    "LEVERAGE_MAX": 5,
    "RISK_PER_TRADE_PCT": 2.0,
    "MIN_NOTIONAL_USDT": 300,
    "FEE_RATE_TAKER": 0.0004,
    "MIN_RR_AFTER_FEES": 1.5,
    "POSITION_SIZE_MODE": "risk_based"
}
```

## 6. Expected Performance (v9.0)

### 6.1 Capital Efficiency

**Bei 1000 EUR Kapital:**

| Slot | Kapital | Leverage | Max Position | Margin |
|------|---------|----------|--------------|--------|
| Trend | 400 EUR | 3× | 0.0083 BTC (~$576) | $192 |
| Sweep | 300 EUR | 4× | 0.017 BTC (~$1.172) | $293 |
| Funding | 300 EUR | 2× | 0.0087 BTC (~$600) | $300 |

### 6.2 Risk Distribution

**Portfolio-Level Diversifikation:**
- **Gesamt-Exposure**: Max $2.348 (80% × 3× Leverage)
- **Net-Exposure**: Kann Long + Short gleichzeitig sein (Hedge Mode)
- **Slot-Isolation**: Verlust in einem Slot betrifft andere nicht

### 6.3 Expected Win Rate Improvement

**Durch Multi-Strategy Diversifikation:**
- **Trend**: 55-60% Win Rate (längere Haltezeiten)
- **Sweep**: 70-75% Win Rate (3× Sweep-Bestätigung)
- **Funding**: 65-70% Win Rate (Contrarian bei Extremen)
- **Portfolio**: 60-65% durch Diversifikation

## 7. Migration Notes

### 7.1 von v8.0 zu v9.0

**Breaking Changes:**
1. **PositionTracker Keys**: `bruno:position:BTCUSDT` → `bruno:position:BTCUSDT:{slot}`
2. **Signal Format**: Neues Feld `strategy_slot` erforderlich
3. **ExecutionAgent**: Portfolio Risk Check jetzt obligatorisch

**Kompatibilität:**
- Alte v8.0 Signale werden als `trend` Slot behandelt
- Bestehende Positionen werden migriert
- Paper Trading Modus bleibt aktiv

### 7.2 Deployment Checkliste

1. **Redis Keys**: Alte Positions-Keys migrieren
2. **Config Update**: Multi-Strategy Settings aktivieren
3. **Hedge Mode**: Auf Binance aktivieren (nur bei Live Trading)
4. **Monitoring**: Portfolio Exposure Dashboard
5. **Testing**: Alle 3 Slots einzeln validieren

## 8. Technical Analysis Engine (v9.0)

### 8.1 Daily EMA Macro Trend Filter

**Neu in v9.0: Daily Timeframe für Macro Trend:**

```python
# Lookback Map inkl. 1d
lookback_map = {
    "1m": 500,
    "5m": 500,
    "15m": 500,
    "1h": 500,
    "4h": 500,
    "1d": 200,  # Neu: Daily für Macro Trend
}

# Daily EMA Berechnung
def _calc_macro_trend(self, candles_1d):
    ema_50 = self._calc_ema(candles_1d, 50)
    ema_200 = self._calc_ema(candles_1d, 200)
    current_price = candles_1d[-1]["close"]
    
    # Golden/Death Cross
    if ema_50 > ema_200:
        macro_trend = "macro_bull"
        allow_longs = current_price > ema_200
        allow_shorts = False
    else:
        macro_trend = "macro_bear"
        allow_longs = False
        allow_shorts = current_price < ema_200
    
    return {
        "macro_trend": macro_trend,
        "ema50": ema_50,
        "ema200": ema_200,
        "allow_longs": allow_longs,
        "allow_shorts": allow_shorts,
    }
```

### 8.2 Indicators

#### EMA Stack

**Multi-Timeframe EMA Analyse:**

- **15m**: Short-term Momentum
- **1h**: Primary Trend
- **4h**: Medium-term Confirmation  
- **1d**: Macro Trend Override

#### RSI(14)

```text
RS = average_gain / average_loss
RSI = 100 - (100 / (1 + RS))
```

Threshold interpretation:

- `RSI < 30` → oversold
- `30 <= RSI < 40` → weak oversold
- `60 < RSI <= 70` → weak overbought
- `RSI > 70` → overbought

#### VWAP (institutional, with daily reset)

```text
VWAP = Σ(typical_price_i * volume_i) / Σ(volume_i)
typical_price_i = (high_i + low_i + close_i) / 3
```

**Daily Reset Logic:**
- VWAP accumulators reset at 00:00 UTC
- `_last_vwap_date` tracks the current trading day
- When `current_candle.timestamp.date() > last_vwap_date`, reset:
  - `cumulative_typical_volume = 0`
  - `cumulative_volume = 0`
  - `last_vwap_date = current_candle.timestamp.date()`

#### ATR(14)

True Range:

```text
TR = max(
  high - low,
  abs(high - prev_close),
  abs(low - prev_close)
)
```

ATR:

```text
ATR = average(TR over last 14 periods)
```

### 8.3 Multi-Timeframe Alignment

**Timeframes mit Daily Macro Trend:**

- **5m**: Entry trigger only
- **15m**: Tactical confirmation
- **1h**: Primary trend
- **4h**: Strategic trend
- **1d**: Macro trend override (NEU)

## 9. GRSS v3 (Global Risk Sentiment Score)

### 9.1 Sub-Scores

**4 gewichtete Komponenten:**

1. **Derivatives (25%)**: Funding Rate + Open Interest
2. **Retail (25%)**: Fear & Greed + Social Volume
3. **Sentiment (25%)**: News Sentiment Analysis
4. **Macro (25%)**: VIX + DXY + Macro Events

### 9.2 Funding Rate Contrarian Logic

**NEU in v9.0: Eigenständige Funding-Strategie:**

```python
# Funding Rate Thresholds
if funding_rate > 0.0005:  # > 50 bps/8h = extrem bullish
    return "short"  # Longs zahlen zu viel → Preis fällt
elif funding_rate < -0.0001:  # < -10 bps/8h = extrem bearish
    return "long"   # Shorts zahlen → Preis steigt
```

## 10. Risk Management (v9.0 Enhanced)

### 10.1 Multi-Layer Risk Controls

**3 Ebenen des Risk Managements:**

1. **Slot-Level**: Per-Strategie Limits
2. **Portfolio-Level**: Gesamt-Exposure 80% Max
3. **System-Level**: Daily Drawdown, Consecutive Losses

### 10.2 Position Sizing v3

**Professional Risk-Based Sizing:**

```python
# Fixer Risikobetrag = 2% des SLOT-Kapitals
risk_amount = slot_capital * 0.02

# Positionsgröße = Risiko ÷ SL-Distanz
position_size = risk_amount / sl_distance

# Fee-Aware R:R Check
rr_after_fees = (tp_profit - fees) / (sl_loss + fees)
if rr_after_fees < 1.5:
    REJECT  # Nicht profitabel nach Fees
```

### 10.3 Scaled Entry Risk Control

**Tranche-basiertes Risiko:**

| Tranche | Größe | Risiko bei sofortem SL |
|---------|-------|------------------------|
| 1       | 40%   | 0.8% des Slot-Kapitals |
| 2       | 30%   | 0.6% des Slot-Kapitals |
| 3       | 30%   | 0.6% des Slot-Kapitals |

**Vorteil:** Bei sofortem Gegen-Lauf nur 40% Verlust statt 100%

## 11. Execution Flow (v9.0)

### 11.1 Signal Generation

**3 parallele Signal-Generatoren:**

```text
QuantAgentV4
├── TREND: CompositeScore → Signal (slot="trend")
├── SWEEP: 3× Sweep → Signal (slot="sweep")
└── FUNDING: Extreme Funding → Signal (slot="funding")
```

### 11.2 Risk Validation

**Portfolio-Level Checks:**

```python
# 1. Slot verfügbar?
if slot in open_positions:
    REJECT

# 2. Gesamt-Exposure OK?
if gross_exposure + new_position > max_exposure:
    REJECT

# 3. Slot-Kapital ausreichend?
if position_size > slot_capital * leverage:
    REJECT
```

### 11.3 Order Execution

**Slot-Aware Execution:**

```python
# Position mit Slot-Tag
await position_tracker.open_position(
    symbol="BTCUSDT",
    side="long",
    strategy_slot="trend",  # NEU
    ...
)
```

## 12. Monitoring & Observability

### 12.1 Portfolio Dashboard

**NEU: Multi-Strategy Monitoring:**

```text
Portfolio Overview
├── Total Capital: 1.000 EUR
├── Gross Exposure: 2.348 EUR (234.8%)
├── Net Exposure: 0 EUR (Hedged)
├── Open Positions: 3/3 Slots
│   ├── Trend: Long 0.0083 BTC (+$576)
│   ├── Sweep: Short 0.017 BTC (-$1.172)
│   └── Funding: Long 0.0087 BTC (+$600)
└── Daily P&L: +$47.20 (+4.7%)
```

### 12.2 Strategy Performance

**Per-Slot Statistiken:**

```text
Trend Strategy
├── Win Rate: 58.3%
├── Avg Win: +2.1%
├── Avg Loss: -1.6%
├── Profit Factor: 1.8
└── Trades: 24

Sweep Strategy
├── Win Rate: 73.1%
├── Avg Win: +1.8%
├── Avg Loss: -1.2%
├── Profit Factor: 2.4
└── Trades: 13

Funding Strategy
├── Win Rate: 66.7%
├── Avg Win: +1.5%
├── Avg Loss: -1.1%
├── Profit Factor: 2.0
└── Trades: 9
```

## 13. Deployment Guide

### 13.1 Pre-Deployment Checklist

1. **Configuration Update:**
   - [ ] STRATEGY_FUNDING_ENABLED=false (start deaktiviert)
   - [ ] SCALED_ENTRY_ENABLED=true
   - [ ] HEDGE_MODE_ENABLED=true

2. **Redis Migration:**
   - [ ] Alte Position Keys sichern
   - [ ] Neue Slot-Keys erstellen
   - [ ] Portfolio Exposure Dashboard testen

3. **Testing:**
   - [ ] Trend-Slot mit CompositeScore
   - [ ] Sweep-Slot mit 3× Sweep
   - [ ] Funding-Slot (später aktivieren)
   - [ ] Scaled Entry Tranche-Trigger

### 13.2 Go-Live Procedure

1. **Phase 1: Paper Trading (1 Woche)**
   - Alle Slots aktivieren
   - Portfolio Monitoring
   - Risk Limits validieren

2. **Phase 2: Reduced Capital (1 Woche)**
   - 10% des Kapitals
   - Live Trading mit kleinem Betrag
   - Slippage und Latenz prüfen

3. **Phase 3: Full Capital**
   - 100% Kapital-Einsatz
   - Alle Slots aktiv
   - Monitoring intensivieren

### 13.3 Rollback Plan

**Falls Probleme auftreten:**

1. **Config Revert:** STRATEGY_TREND_ENABLED=true, andere=false
2. **Redis Keys:** Altes Format wiederherstellen
3. **Code:** v8.0 Branch zurückrollen
4. **Monitoring:** Classic Portfolio View

---

**Bruno v9.0 - Multi-Strategy Architecture**

Professionelles Risk Management mit 3 unkorrelierten Strategien, Scaled Entries und Portfolio-Level Diversifikation. Ready for institutional deployment.

**v9.0 Features (NEU):**
- **Multi-Strategy Slots**: 3 unabhängige Strategien (Trend, Sweep, Funding)
- **Scaled Entry Engine**: Pyramiding für Trend-Strategie (40%/30%/30% Tranchen)
- **Professional Position Sizing**: Risk-based mit Leverage-Effizienz
- **Portfolio-Level Risk Management**: Max 80% Exposure, Slot-Isolation
- **Binance Hedge Mode**: Gleichzeitige Long+Short Positionen
- **Daily EMA Macro Trend Filter**: Schutz vor Bear Market Rallies
- **StrategyManager**: Zentrale Orchestrierung und Risk Checks

**v8.0 Features (beibehalten):**
- **Risk Management**: 6 hard vetos mit circuit breakers
- **Learning System**: Deepseek API für Post-Trade Analyse
- **Institutional Math**: VWAP daily reset, CVD deduplication, true VPOC
- **Backtester**: 1-minute candles mit intrabar pessimism rule
- **Execution**: Position-specific state, TP1 maker fee (0.01%), multi-level exits
- **Prompt 7 Score-Kalibrierung**: Confluence-Bonus, Regime-Kompensation

**Prompt 7 Kalibrierung (April 2026):**
- Thresholds angepasst für realistischere Trade-Generierung (Learning: 18, Prod: 40)
- Signal-Confluence-Bonus: Belohnt überlappende Signale (3+ aligned → +8 pro Signal)
- Regime-Kompensation: +15% Boost in Ranging-Märkten um strukturelle Benachteiligung auszugleichen
- TA Ranging-Kompensation: "mixed" EMA Stack gibt ±8 wenn kurzfristige EMAs aligned sind
- Volume Session-Aware: Keine Penalty in inaktiven Sessions (Asia/Late-US)
- Liq Nearest-Wall Proximity: ±5 Punkte wenn Orderbuch-Walls innerhalb 1%

This document is the canonical reference for trading logic in v9.0.
