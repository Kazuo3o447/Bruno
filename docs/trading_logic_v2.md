# Bruno v8.0 Trading Logic (Privacy-First News & Bybit Data Core)

## 1. Purpose

Bruno v8.0 is a **privacy-first institutional** deterministic trading system with zero tolerance for heuristics. The system features:

1. **Privacy-First News Ingestion** - Multi-Source News (CryptoPanic, RSS, Free-Crypto-News) mit SHA256 Deduplizierung
2. **Bybit V5 Single Source of Truth** - Exklusive WebSocket-Daten mit präziser CVD Taker-Mathematik
3. **Mathematical Purity** - VWAP/VPOC tägliche Resets, Trade-Deduplizierung, keine Heuristiken
4. **GRSS v3** - 4 gewichtete Sub-Scores (Derivatives, Retail, Sentiment, Macro) ohne Binance-Abhängigkeit
5. **Adaptive Thresholds** - ATR-basiert mit Event Calendar Guardrails
6. **MTF-Filter** - Regime-abhängige Filter für bessere Signalqualität im Ranging
7. **DeepSeek Post-Trade Analyse** - Automatische Trade-Evaluation für Paper Trades
8. **Complete Binance Purge** - Alle REST API Calls entfernt, Bybit V5 als exklusive Quelle

The system maintains **100% deterministic live trading** with **zero heuristics** policy while integrating privacy-first news aggregation for enhanced market context.

## 2. Data Flow Overview (v8.0 Privacy-First Architecture)

```text
Bybit V5 WebSocket → BybitV5Client → Redis (CVD, VWAP, VPOC)
    ↓
News Sources (CryptoPanic, RSS, Free-Crypto-News) → NewsIngestionService → SentimentAnalyzer
    ↓
TechnicalAnalysisAgent → bruno:ta:snapshot (präzise CVD)
    ↓
ContextAgent → bruno:context:grss (GRSS v3, Binance-frei)
    ↓
SentimentAgent → HuggingFace Models (Zero-Shot Classification)
    ↓
LiquidityEngine → bruno:liq:intelligence
    ↓
QuantAgentV4 → bruno:quant:micro + bruno:decisions:feed (News-integriert)
    ↓
CompositeScorer → trade decision (adaptive thresholds)
    ↓
RiskAgent → veto state (event calendar)
    ↓
ExecutionAgentV4 → order / position management (paper trading)
```

### 2.1 Bybit V5 WebSocket Integration (v8.0 Single Source of Truth)

**Exklusive Datenquelle mit mathematischer Präzision:**

```python
# CVD Taker-Mathematik (ABSOLUTE PRÄZISION)
for trade in message["data"]:
    exec_id = trade["i"]  # Execution ID für Deduplizierung
    vol = float(trade["v"])
    side = trade["S"]  # "Buy" oder "Sell"
    
    # Deduplizierung zwingend erforderlich
    if exec_id not in self._processed_trades:
        if side == "Buy":
            self.current_1m_taker_buy += vol
        elif side == "Sell":
            self.current_1m_taker_sell += vol

# CVD-Berechnung: Delta = current_1m_taker_buy - current_1m_taker_sell
```

**VWAP/VPOC mit institutionellen Resets:**
- **VWAP Reset**: Exakt um 00:00:00 UTC 
- **VPOC Reset**: Exakt um 00:00:00 UTC mit 10-Dollar Preis-Buckets
- **Trade Deduplizierung**: Rolling deque (maxlen=10000) via execution IDs

### 2.2 News Ingestion Service (v8.0 Privacy-First)

**Multi-Source mit SHA256 Deduplizierung:**

```python
# SHA256 Hash für Deduplizierung
hash_input = title.lower().strip()
if timestamp:
    hash_input += f"_{timestamp}"
news_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

# BTC-Filter (case-insensitive)
if "btc" not in combined_text.lower() and "bitcoin" not in combined_text.lower():
    return None  # Rauschunterdrückung
```

**Quellen-Abdeckung (Aktueller Status):**
- **RSS Feeds** (30s Polling) - CoinDesk, Cointelegraph, Decrypt ✅ **AKTIV (49 Items)**
- **Reddit JSON** (120s Fallback) - r/Bitcoin Hot Posts ✅ **AKTIV (14 Items)**
- **CoinMarketCap** (60s Polling) - BTC Marktdaten ⚠️ **INAKTIV (API Key fehlt)**
- **CryptoCompare** (120s Fallback) - Free Tier News ❌ **INAKTIV (0 Items)**
- **NewsAPI** (120s Fallback) - Demo Key ungültig ❌ **INAKTIV (401 Error)**
- **Total News Coverage** ✅ **63 Items (Maximum mit Free Quellen)**

**Bybit V5 WebSocket (Aktueller Status):**
- **Bybit V5** als Single Source of Truth ✅ **AKTIV (Simuliert)**
- **CVD Taker-Mathematik** mit execution ID Deduplizierung ✅ **IMPLEMENTIERT**
- **VWAP/VPOC Resets** um 00:00:00 UTC ✅ **IMPLEMENTIERT**
- **Trade Deduplizierung** via rolling deque ✅ **IMPLEMENTIERT**

**Hinweis:** Die Bybit V5 WebSocket Verbindung ist aktuell simuliert aufgrund von pybit API Kompatibilitätsproblemen. Die Architektur ist jedoch vollständig implementiert und bereit für echte WebSocket-Daten.

**Current Data Source Architecture (v8.0):**

**Redis Storage Pattern:**
```bash
# Sehr frisch (5-10s TTL)
market:ticker:BTCUSDT           # {"last_price": 67263.7}
market:orderbook:BTCUSDT        # {"imbalance_ratio": 1.23}
market:ofi:ticks               # [{"t": "...", "r": 1.23}, ...]
market:cvd:ticks               # [{"ts": "...", "delta": 1.23}, ...]
market:cvd:cumulative           # "1234.56"

# Frisch (60s TTL)
bruno:ta:klines:BTCUSDT        # {"klines": [...], "count": 500}
market:liquidations:BTCUSDT    # [{"side": "SELL", "price": 67000}]
bruno:ta:snapshot              # {"ta_score": {...}, "regime": "ranging"}
bruno:context:grss             # {"GRSS_Score": 62.0, "regime_hint": "ranging"}

# Mittel-frisch (300s TTL)
market:funding:BTCUSDT         # {"fundingRate": 0.0001}
market:open_interest:BTCUSDT   # {"openInterest": "123456.78"}
```

## 3. Technical Analysis Engine

### 3.1 Inputs

- 1m OHLCV from `market_candles`
- Aggregated 5m, 15m, 1h, 4h candles
- Binance orderbook depth with `limit=1000`

### 3.2 Indicators

#### EMA

The engine calculates:

- `EMA(9)`
- `EMA(21)`
- `EMA(50)`
- `EMA(200)`

Formula:

```text
EMA_t = price_t * α + EMA_(t-1) * (1 - α)
α = 2 / (period + 1)
```

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

### 3.3 Multi-Timeframe Alignment

Timeframes:

- 5m: entry trigger only
- 15m: tactical confirmation
- 1h: primary trend
- 4h: strategic trend

Direction per timeframe:

- `bull` if `EMA(9) > EMA(21)`
- `bear` otherwise

Weighted alignment score:

```text
alignment_score = (4h * 3 + 1h * 2 + 15m * 1) / 6
```

where each bullish timeframe contributes `+weight`, each bearish timeframe `-weight`.

Interpretation:

- `aligned_long = true` if 15m, 1h, and 4h are bullish
- `aligned_short = true` if 15m, 1h, and 4h are bearish
- `conflicting_tf` identifies the first disagreeing higher timeframe

### 3.4 Support / Resistance

Support and resistance are detected through swing highs and swing lows on 4h candles.

A swing high is valid if the candle high is greater than the highs of two candles on both sides.

A swing low is valid if the candle low is lower than the lows of two candles on both sides.

Strength heuristic:

```text
strength = min(5, int(price_distance_factor))
```

The engine stores the top 10 levels sorted by strength and proximity.

### 3.5 Breakout Proximity

Near-level threshold:

```text
near_threshold_pct = 0.5%
near_threshold_atr = (ATR / price) * 100
effective_threshold = max(near_threshold_pct, near_threshold_atr)
```

The engine marks a breakout candidate if price is near a strong support or resistance zone with strength `>= 3`.

### 3.6 Wick Detection

For each of the last 3 five-minute candles:

```text
body = abs(close - open)
upper_wick = high - max(open, close)
lower_wick = min(open, close) - low
```

Bullish wick (hammer):

- `lower_wick > 2 * body`
- `upper_wick < 0.5 * body`

Bearish wick (shooting star):

- `upper_wick > 2 * body`
- `lower_wick < 0.5 * body`

Wick strength:

```text
wick_strength = min(1.0, wick_length / body / 4.0)
```

### 3.7 Session Awareness

Sessions are detected in UTC:

- `asia`: 00:00–08:00
- `europe`: 08:00–14:00
- `eu_us_overlap`: 14:00–16:00
- `us`: 16:00–21:00
- `late_us`: everything else

Each session returns:

- `session`
- `volatility_bias`
- `trend_expected`

### 3.10 VPOC (Volume Point of Control)

**Volume-at-Price Matrix:**
- Uses fixed tick size buckets ($10 for BTC)
- Builds exact volume distribution: `price_level -> cumulative_volume`
- VPOC = price level with maximum volume in the matrix

**Implementation:**
```python
volume_at_price = {}
for candle in candles:
    price_bucket = round(candle["close"] / tick_size) * tick_size
    volume_at_price[price_bucket] = volume_at_price.get(price_bucket, 0) + candle["volume"]
    
vpoc_price = max(volume_at_price, key=volume_at_price.get)
```

### 3.11 Orderbook Walls

Binance depth endpoint:

```text
GET https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000
```

Wall threshold:

```text
wall_threshold = median_order_size * 5
```

Each wall includes:

- price
- size in BTC
- size in USDT
- distance from current price

The engine also calculates `wall_imbalance`:

```text
wall_imbalance = total_bid_wall_size / total_ask_wall_size
```

### 3.12 CVD (Cumulative Volume Delta)

**Deduplication Logic:**
- Uses 1-minute klines for precise delta calculation
- Strict timestamp guard prevents double processing:
  - `_last_processed_kline_ts` stores last processed timestamp
  - Only processes klines with `timestamp > _last_processed_kline_ts`
- Cumulative delta: `CVD += (taker_buy_volume - taker_sell_volume)`

**Implementation:**
```python
if latest_kline_ts > self._last_processed_kline_ts:
    minute_delta = taker_buy_volume - taker_sell_volume
    self.cvd_cumulative += minute_delta
    self._last_processed_kline_ts = latest_kline_ts
```

### 3.13 TA Score

TA score range:

- `-100` to `+100`

Component weights:

- Trend: 25%
- MTF alignment: 20%
- RSI: 10%
- S/R context: 20%
- Volume: 10%
- VWAP: 10%
- Wick bonus: 5%

**Trend-Block mit Ranging-Kompensation (Prompt 7 NEU):**
- `perfect_bull` / `perfect_bear`: ±25
- `bull` / `bear`: ±18
- `mixed`: ±8 wenn EMA9/21 aligned (Trend building)
  - EMA9 > EMA21: +8 (Short-term EMAs bullish)
  - EMA9 < EMA21: -8 (Short-term EMAs bearish)

**Volume-Block Session-Aware (Prompt 7 NEU):**
- `vol_ratio > 1.5`: +8 (High volume confirmation)
- `vol_ratio > 1.2`: +4
- `vol_ratio < 0.5`: -5 (nur in EU/US/Overlap Sessions)
  - Asia/Late-US: Keine Penalty (low volume ist normal)

MTF filter:

- If the resulting direction is long and `aligned_long == false`, multiply the TA score by `0.3`.
- If the resulting direction is short and `aligned_short == false`, multiply the TA score by `0.3`.

This is intentionally strict because counter-trend low-timeframe signals have a high fakeout rate.

## 4. Liquidity Intelligence

### 4.1 Cluster Detection

Source:

- `liquidations` table (24h lookback)

Filter:

- `total_usdt > 100000`
- cluster zones grouped around `$200` price buckets

Each cluster stores:

- zone price
- total liquidation volume in USDT
- count
- average/min/max liquidation price
- distance from current price
- side relation (`is_above`)

### 4.2 Magnetic Pull

The magnetic pull is modeled with a gravity-inspired function:

```text
force = G * mass / distance²
mass = total_usdt / 1,000,000
```

with `G = 1.0`.

Interpretation:

- positive force → attraction upward
- negative force → attraction downward

The final `strength` is normalized to `0.0..1.0`.

### 4.3 Asymmetry

Liquidation asymmetry compares:

- `long_liq_below` = liquidation volume below current price
- `short_liq_above` = liquidation volume above current price

Ratio:

```text
ratio = long_liq_below / short_liq_above
```

Bias:

- `ratio > 1.5` → `bullish_sweep`
- `ratio < 0.67` → `bearish_sweep`
- otherwise → `balanced`

### 4.4 OI Delta

Open Interest is polled once per minute from:

```text
GET https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT
```

History:

- rolling window of 10 values

Derived values:

- `oi_1min_change = current_oi - prev_oi`
- `oi_5min_change = current_oi - first_oi`
- `oi_change_pct = (oi_5min_change / first_oi) * 100`

`oi_dropping` is true when the latest readings show consecutive declines.

### 4.5 3× Sweep Confirmation

An entry is only confirmed when **all three** conditions are true:

1. **Liquidations spike**
   - `total_liq > 500000` USDT over 5 minutes
   - dominant side must exceed `70%`
2. **Wick formed**
   - bullish wick after long liquidation sweep
   - bearish wick after short liquidation sweep
3. **OI dropping**
   - open interest must fall

Sweep direction:

- `SELL` liquidations correspond to **longs liquidated**
- `BUY` liquidations correspond to **shorts liquidated**

### 4.6 Event-Driven Liquidation Trigger

Liquidation spikes are now published by the IngestionAgent via Redis Pub/Sub and can trigger an immediate rescoring path in `QuantAgentV4` without waiting for the 60s polling cycle.

Event channel:

```text
market:liquidations:{symbol}:events
```

Trigger rules:

- force-order payload must exceed the configured liquidation spike threshold
- the liquidation event is forwarded into `LiquidityEngine.analyze(...)`
- the resulting sweep confirmation can bypass the normal cooldown for immediate evaluation

Post-sweep entry:

- `long` sweep + bullish wick + OI drop → `post_sweep_entry = long`
- `short` sweep + bearish wick + OI drop → `post_sweep_entry = short`

### 4.6 Liquidity Score

Liquidity score range:

- `-50` to `+50`

Components:

- Magnetic pull: `±10`
- Asymmetry bias: `±10`
- Confirmed sweep: `±20`
- Orderbook wall imbalance: `±10`
- **Nearest-Wall Proximity (Prompt 7 NEU): `±5`**

Wall imbalance interpretation:

- `wall_imbalance > 1.5` → `+10`
- `1.2 < wall_imbalance <= 1.5` → `+5`
- `0.83 <= wall_imbalance <= 1.2` → neutral
- `0.67 <= wall_imbalance < 0.83` → `-5`
- `wall_imbalance < 0.67` → `-10`

**Nearest-Wall Proximity (Prompt 7):**
- Bid-Wall innerhalb 1%: `+5` (Support = bullish)
- Ask-Wall innerhalb 1%: `-5` (Resistance = bearish)

Begründung: Wenn ein Wall in der Nähe ist, wird Preis davon angezogen/abgestoßen.

## 5. Composite Scoring

### 5.1 Score Inputs

The composite score consumes four core inputs plus auxiliary analytics data:

- `ta_score` in `[-100, +100]`
- `liq_score` in `[-50, +50]`
- `flow_score` in `[-50, +50]`
- `macro_score` in `[-50, +50]`

Auxiliary flow sources now include Binance Futures analytics (`bruno:binance:analytics`) and on-chain context (`bruno:onchain:data`) feeding the ContextAgent / CompositeScorer pipeline.

### 5.2 Regime Detection

Regime is derived from:

- TA trend stack
- VIX from macro context

Rules:

- `VIX > 35` → `high_vola`
- `EMA stack in [perfect_bull, bull]` → `trending_bull`
- `EMA stack in [perfect_bear, bear]` → `bear`
- otherwise → `ranging`

### 5.3 Weight Presets

Trending preset:

```text
TA    = 0.50
Liq   = 0.15
Flow  = 0.20
Macro = 0.15
```

Ranging preset:

```text
TA    = 0.20
Liq   = 0.40
Flow  = 0.25
Macro = 0.15
```

Rationale:

- **Trending**: trend-following dominates; liquidity sweeps are less reliable.
- **Ranging**: price oscillates between liquidity clusters; sweeps are primary opportunities.

### 5.4 Composite Formula

Normalization:

- `liq_score`, `flow_score`, and `macro_score` are multiplied by `2` before weighting so they operate on the same scale as `ta_score`.

Formula:

```text
composite = ta_score * w_ta + (liq_score * 2) * w_liq + (flow_score * 2) * w_flow + (macro_score * 2) * w_macro
```

Final clamp:

```text
composite_score = clamp(composite, -100, +100)
```

Direction:

- `composite > 0` → `long`
- `composite < 0` → `short`
- `composite == 0` → `neutral`

### 5.5 Threshold and Sweep Bonus

Thresholds from config (Prompt 7 Kalibrierung):

- learning: `COMPOSITE_THRESHOLD_LEARNING = 18` (was 35)
- production: `COMPOSITE_THRESHOLD_PROD = 40` (was 55)

**Begründung:** Learning Mode soll Daten sammeln - jeder Trade mit Score > 18 und Confluence ist ein Datenpunkt. Production 40 ist selektiv genug nach Score-Fixes.

Sweep bonus:

```text
effective_threshold = max(30, threshold - 15)
```

applies when `sweep_confirmed = true`.

### 5.5.1 Signal-Confluence-Bonus (Prompt 7 NEU)

Wenn 3+ unabhängige Signal-Quellen in dieselbe Richtung zeigen, ist die Wahrscheinlichkeit eines erfolgreichen Trades signifikant höher.

**Signal-Quellen:**
- TA Richtung (ta_score > 10 / < -10)
- Liq Richtung (liq_score > 5 / < -5)
- Flow Richtung (flow_score > 10 / < -10)
- Macro Richtung (macro_score > 5 / < -5)
- MTF Alignment (mtf_aligned + ta_score direction)
- VWAP Position (Above/Below VWAP)

**Bonus-Formel:**
```text
dominant_count = max(bull_count, bear_count)
if dominant_count >= 3:
    bonus = (dominant_count - 2) * 8  # +8 pro Signal ab dem 3.
```

Beispiel: 5 aligned bull signals → bonus = (5-2) × 8 = +24

### 5.5.2 Regime-Kompensation (Prompt 7 NEU)

Ranging-Märkte produzieren strukturell niedrigere TA-Scores weil der Trend-Block (25 Punkte) bei "mixed" EMA-Stack ~0 ist.

**Boost-Logik:**
```text
if regime in ("ranging", "high_vola") and abs(composite) > 10:
    ranging_boost = abs(composite) * 0.15  # +15% Score Boost
    if composite > 0:
        composite += ranging_boost
    else:
        composite -= ranging_boost
```

Kompensiert systematische Benachteiligung von Ranging-Setups.

### 5.6 MTF Filter

If MTF is not aligned, the TA contribution is already reduced at the TA layer. The composite layer still records `mtf_aligned` and uses it as a trade-quality flag. The TA layer now uses a graded alignment score (0.3× / 0.6× / 1.0×) instead of a binary pass/fail.

### 5.7 Position Sizing

Position size is session-aware and score-aware.

Score multiplier:

```text
score_mult = clamp((abs_score - 40) / 50 + 0.5, 0.5, 1.5)
```

ATR multiplier:

- `ATR/price < 0.5%` → `1.2`
- `0.5% <= ATR/price < 1.0%` → `1.0`
- `1.0% <= ATR/price < 2.0%` → `0.6`
- `ATR/price >= 2.0%` → `0.3`

Session multiplier uses `volatility_bias` from TA session context.

Final sizing is clamped to `<= 2.0%`.

### 5.8 SL / TP

Default values:

- `stop_loss_pct = 0.010`
- `take_profit_1_pct = 0.012`
- `take_profit_2_pct = 0.020`
- `tp1_size_pct = 0.50`
- `tp2_size_pct = 0.50`

Breakeven trigger:

- `breakeven_trigger_pct = 0.005`

ATR-based clamping:

- if `abs_score > 80`:
  - `sl_mult = 1.5`
  - `tp1_mult = 1.5`
  - `tp2_mult = 3.0`
- if `abs_score > 60`:
  - `sl_mult = 1.2`
  - `tp1_mult = 1.2`
  - `tp2_mult = 2.5`
- otherwise:
  - `sl_mult = 0.8`
  - `tp1_mult = 1.0`
  - `tp2_mult = 1.5`

Clamp boundaries:

- `SL` in `[0.5%, 2.5%]`
- `TP1` in `[0.8%, 2.5%]`
- `TP2` in `[1.0%, 5.0%]`

## 6. Risk Management

### 6.1 Hard Vetos

RiskAgent v2 uses six hard vetos:

1. Data gap
2. Context stale > 1h
3. VIX > 45
4. System pause / kill-switch
5. Death zone near mega-wall
6. Daily drawdown block

### 6.2 Daily Drawdown

24h block triggers when:

- daily loss `>= 3.0%`, or
- `3` consecutive losing trades

Daily loss calculation:

```text
daily_loss_pct = abs(daily_pnl / initial_capital * 100)
```

Block state is stored in Redis under `bruno:risk:daily_block` with 24h TTL.

### 6.3 Death Zone

If a cluster has:

- `total_usdt > 500000`
- `abs(distance_pct) < 0.5%`

then the RiskAgent vetoes the trade.

### 6.4 Breakeven Stop

If a trade is more than `0.5%` in profit, the first take-profit is hit and the stop-loss is moved to:

- long: `entry_price * 1.001`
- short: `entry_price * 0.999`

This locks in a small positive expected value and prevents turning winners into losers. After TP1, the remaining size continues toward TP2 or the adjusted stop.

**Position-Specific State:**
- Each position tracks its own `tp1_hit` and `breakeven_active` flags
- No global state variables interfere between multiple positions
- State is stored in the position dictionary via PositionTracker

### 6.5 Trade Cooldown

Minimum cooldown:

```text
TRADE_COOLDOWN_SECONDS = 300
```

No new signal is published before this cooldown has expired.

## 7. Execution and Portfolio Handling

ExecutionAgentV4 performs:

- TP1 scale-out
- breakeven adjustment
- ATR-based trailing stop (Chandelier Exit)
- TP2 final exit
- position closing
- portfolio updates in DRY_RUN

**TP1 Scale-Out Fee Model:**
- Uses **0.01% maker fee** for limit order simulation
- `fee_estimate = (qty_to_close * exit_price) * 0.0001`
- Reflects institutional fee structure for passive liquidity provision

PositionTracker stores the live state for:

- `initial_quantity`
- `take_profit_1_price`
- `take_profit_2_price`
- `tp1_size_pct`
- `tp2_size_pct`
- `breakeven_trigger_pct`
- `realized_pnl_eur` / `realized_pnl_pct`
- `tp1_hit` / `breakeven_active`
- `max_favorable_price` / `min_favorable_price`

Portfolio state keys include:

- `capital_eur`
- `daily_pnl_eur`
- `trade_pnl_history_eur`
- `peak_capital_eur`
- `max_drawdown_eur`

## 8. Backtester Realitäts-Check

### 8.1 1-Minute Candle Iteration
The backtester now iterates over **1-minute candles** instead of hourly candles for realistic simulation:
```python
for candle in candles_1m:
    # Check intrabar high/low conditions
    # Apply pessimism rule for SL/TP conflicts
```

### 8.2 Intrabar High/Low Checks
Each candle checks both price extremes:
- **High**: Tests for take-profit triggers
- **Low**: Tests for stop-loss triggers
- Enables realistic intrabar price action simulation

### 8.3 Pessimismus-Regel (SL Priority)
If both SL and TP are touched in the same candle:
```python
if low_price <= stop_loss and high_price >= take_profit:
    # SL wins - assume stop-loss hit first
    exit_price = stop_loss
    exit_reason = "stop_loss"
```
This conservative approach reflects real-world execution where stop-loss orders typically execute faster than take-profit orders.

## 9. Redis Keys

### Technical Analysis

- `bruno:ta:snapshot`
- `bruno:ta:ob_walls`

### Liquidity Intelligence

- `bruno:liq:intelligence`
- `bruno:liq:intelligence` contains:
  - clusters
  - magnetic pull
  - asymmetry
  - OI delta
  - sweep confirmation
  - liquidity score

### Free-Tier Analytics / On-Chain

- `bruno:binance:analytics`
- `bruno:onchain:data`
- `bruno:cvd:BTCUSDT`

### Sentiment Analysis (NEW 2026-04-06)

- `bruno:sentiment:analysis`
- `bruno:sentiment:news_sentiment`
- HuggingFace Models: `facebook/bart-large-mnli` (Zero-Shot Classification)
- CryptoPanic API Integration (replaces Google Trends)

### Execution / Positions

- `bruno:position:BTCUSDT`
- `bruno:risk:daily_block`

### Quant / Decisions

- `bruno:quant:micro`
- `bruno:decisions:feed`
- `bruno:pubsub:signals`

### Risk / Execution

- `bruno:veto:state`
- `bruno:risk:daily_block`
- `bruno:portfolio:state`
- `market:liquidations:{symbol}:events`

### Legacy / Post-Trade Learning

- `trade_debriefs` table
- `bruno:learning:metrics`
- `bruno:learning:layer_*`

### Phantom Trade Learning

- `bruno:phantom_trades:pending`
- `market_candles` scan for MAE/MFE evaluation

## 10. Configuration Keys

```json
{
  "COMPOSITE_THRESHOLD_LEARNING": 18,  // Prompt 7: war 35
  "COMPOSITE_THRESHOLD_PROD": 40,     // Prompt 7: war 55
  "COMPOSITE_W_TA": 0.40,
  "COMPOSITE_W_LIQ": 0.25,
  "COMPOSITE_W_FLOW": 0.20,
  "COMPOSITE_W_MACRO": 0.15,
  "TRADE_COOLDOWN_SECONDS": 300,
  "DAILY_MAX_LOSS_PCT": 3.0,
  "MAX_CONSECUTIVE_LOSSES": 3,
  "BREAKEVEN_TRIGGER_PCT": 0.005,
  "TAKE_PROFIT_1_PCT": 0.012,
  "TAKE_PROFIT_2_PCT": 0.020,
  "TP1_SIZE_PCT": 0.50,
  "TP2_SIZE_PCT": 0.50
}
```

If all four `COMPOSITE_W_*` keys are present, config override can replace the default presets. Otherwise the regime defaults apply.

**Prompt 7 Kalibrierungs-Änderungen:**
- Learning Threshold: 35 → 18 (für mehr Trades im Learning Mode)
- Production Threshold: 55 → 40 (nach Score-Fixes realistischer)
- Signal-Confluence-Bonus: +8 pro aligned Signal ab dem 3.
- Regime-Kompensation: +15% Boost in ranging/high_vola
- TA Ranging-Kompensation: ±8 für "mixed" EMA mit aligned short-term EMAs
- Volume Session-Aware: Keine Penalty in Asia/Late-US
- Liq Nearest-Wall: ±5 für Walls innerhalb 1%

## 11. Post-Trade Analysis with Deepseek API

The LLM is no longer part of live trade execution but is used exclusively for post-trade analysis.

**Deepseek Reasoning API Integration:**
- Post-trade narrative analysis
- Trade reasoning archive  
- Debrief-based learning loop
- Performance improvement recommendations
- Structured JSON responses for data analysis
- Phantom-trade evaluation with MAE/MFE context

**API Configuration:**
- Provider: Deepseek Reasoning API
- Model: deepseek-chat
- Purpose: Post-trade debrief and learning only
- Fallback: Graceful degradation when API unavailable

This is preserved for research, diagnostics, and continuous strategy improvement.

## 12. Migration Notes

### Replaced

- `QuantAgentV3` → `QuantAgentV4`
- LLM decision cascade → deterministic composite scoring
- Ollama local LLMs → Deepseek Reasoning API
- Local model management → Cloud-based intelligence

### Added

- Deepseek Reasoning API integration
- Post-trade debrief with structured JSON responses
- Cloud-based learning system
- Professional trade analysis capabilities
- Robust error handling and fallback mechanisms
- TechnicalAnalysisAgent
- LiquidityEngine
- CompositeScorer
- Daily drawdown block
- Breakeven stop logic

### Compatibility

- Redis keys from v1 remain preserved where needed
- Trade audit logs remain compatible
- Legacy LLM debrief tables remain available
- Deepseek API replaces Ollama for post-trade analysis only

## 13. Summary

Bruno v2.2 is a deterministic, regime-adaptive trading system with institutional-grade mathematical precision. The primary trade decision is based on the combination of technical structure, liquidity pressure, and macro flow, with strict risk controls and **Deepseek Reasoning API** for post-trade debriefing and learning.

**V2.2 Key Features:**
- **Live Trading:** 100% deterministic without LLM interference
- **Post-Trade Analysis:** Professional Deepseek API integration
- **Risk Management:** 6 hard vetos with circuit breakers
- **Learning System:** Cloud-based intelligence for continuous improvement
- **Performance:** Sub-2s response times for trade analysis
- **Institutional Math:** VWAP daily reset, CVD deduplication, true VPOC
- **Backtester:** 1-minute candles with intrabar pessimism rule
- **Execution:** Position-specific state, TP1 maker fee (0.01%), multi-level exits
- **Purge Complete:** No Max Pain or Google Trends references in system
- **Prompt 7 Score-Kalibrierung:** Confluence-Bonus, Regime-Kompensation, Ranging-aware scoring

**Prompt 7 Kalibrierung (April 2026):**
- Thresholds angepasst für realistischere Trade-Generierung (Learning: 18, Prod: 40)
- Signal-Confluence-Bonus: Belohnt überlappende Signale (3+ aligned → +8 pro Signal)
- Regime-Kompensation: +15% Boost in Ranging-Märkten um strukturelle Benachteiligung auszugleichen
- TA Ranging-Kompensation: "mixed" EMA Stack gibt ±8 wenn kurzfristige EMAs aligned sind
- Volume Session-Aware: Keine Penalty in inaktiven Sessions (Asia/Late-US)
- Liq Nearest-Wall Proximity: ±5 Punkte wenn Orderbuch-Walls innerhalb 1%

This document is the canonical reference for trading logic in v2.2.
