# Bruno v2 Trading Logic

## 1. Purpose

Bruno v2 replaces the LLM-based decision chain with a deterministic, regime-adaptive trading stack. The system is designed for medium-frequency Bitcoin trading and uses three primary decision layers:

1. **Technical Analysis** for trend, structure, and timing.
2. **Liquidity Intelligence** for sweep opportunities and cluster magnetism.
3. **Composite Scoring** for the final trade decision.

The LLM is **legacy-only** and is used exclusively for post-trade debriefing and learning analysis, not for live trade decisions.

## 2. Data Flow Overview

```text
market_candles / liquidations / market:ofi:ticks / orderbook
    ↓
TechnicalAnalysisAgent → bruno:ta:snapshot
    ↓
LiquidityEngine → bruno:liq:intelligence
    ↓
QuantAgentV4 → bruno:quant:micro + bruno:decisions:feed
    ↓
CompositeScorer → trade decision
    ↓
RiskAgent → veto state
    ↓
ExecutionAgentV3 → order / position management
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

#### VWAP (intraday, 15m)

```text
VWAP = Σ(close_i * volume_i) / Σ(volume_i)
```

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

### 3.8 Orderbook Walls

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

### 3.9 TA Score

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

Wall imbalance interpretation:

- `wall_imbalance > 1.5` → `+10`
- `1.2 < wall_imbalance <= 1.5` → `+5`
- `0.83 <= wall_imbalance <= 1.2` → neutral
- `0.67 <= wall_imbalance < 0.83` → `-5`
- `wall_imbalance < 0.67` → `-10`

## 5. Composite Scoring

### 5.1 Score Inputs

The composite score consumes four inputs:

- `ta_score` in `[-100, +100]`
- `liq_score` in `[-50, +50]`
- `flow_score` in `[-50, +50]`
- `macro_score` in `[-50, +50]`

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

Thresholds from config:

- learning: `COMPOSITE_THRESHOLD_LEARNING = 45`
- production: `COMPOSITE_THRESHOLD_PROD = 60`

Sweep bonus:

```text
effective_threshold = max(30, threshold - 15)
```

applies when `sweep_confirmed = true`.

### 5.6 MTF Filter

If MTF is not aligned, the TA contribution is already reduced at the TA layer. The composite layer still records `mtf_aligned` and uses it as a trade-quality flag.

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
- `take_profit_pct = 0.020`

ATR-based clamping:

- if `abs_score > 80`:
  - `sl_mult = 1.5`
  - `tp_mult = 3.0`
- if `abs_score > 60`:
  - `sl_mult = 1.2`
  - `tp_mult = 2.5`
- otherwise:
  - `sl_mult = 0.8`
  - `tp_mult = 1.5`

Clamp boundaries:

- `SL` in `[0.5%, 2.5%]`
- `TP` in `[1.0%, 5.0%]`

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

If a trade is more than `0.5%` in profit, the stop-loss is moved to:

- long: `entry_price * 1.001`
- short: `entry_price * 0.999`

This locks in a small positive expected value and prevents turning winners into losers.

### 6.5 Trade Cooldown

Minimum cooldown:

```text
TRADE_COOLDOWN_SECONDS = 300
```

No new signal is published before this cooldown has expired.

## 7. Execution and Portfolio Handling

ExecutionAgentV3 performs:

- SL / TP monitoring
- breakeven adjustment
- position closing
- portfolio updates in DRY_RUN

Portfolio state keys include:

- `capital_eur`
- `daily_pnl_eur`
- `trade_pnl_history_eur`
- `peak_capital_eur`
- `max_drawdown_eur`

## 8. Redis Keys

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

### Quant / Decisions

- `bruno:quant:micro`
- `bruno:decisions:feed`
- `bruno:pubsub:signals`

### Risk / Execution

- `bruno:veto:state`
- `bruno:risk:daily_block`
- `bruno:portfolio:state`

### Legacy / Post-Trade Learning

- `trade_debriefs` table
- `bruno:learning:metrics`
- `bruno:learning:layer_*`

## 9. Configuration Keys

```json
{
  "COMPOSITE_THRESHOLD_LEARNING": 45,
  "COMPOSITE_THRESHOLD_PROD": 60,
  "COMPOSITE_W_TA": 0.40,
  "COMPOSITE_W_LIQ": 0.25,
  "COMPOSITE_W_FLOW": 0.20,
  "COMPOSITE_W_MACRO": 0.15,
  "TRADE_COOLDOWN_SECONDS": 300,
  "DAILY_MAX_LOSS_PCT": 3.0,
  "MAX_CONSECUTIVE_LOSSES": 3,
  "BREAKEVEN_TRIGGER_PCT": 0.005
}
```

If all four `COMPOSITE_W_*` keys are present, config override can replace the default presets. Otherwise the regime defaults apply.

## 10. Legacy (v1) LLM Debrief

The LLM is no longer part of live trade execution.

Legacy uses:

- post-trade narrative analysis
- trade reasoning archive
- debrief-based learning loop

This is preserved for research, diagnostics, and future strategy evaluation only.

## 11. Migration Notes

### Replaced

- `QuantAgentV3` → `QuantAgentV4`
- LLM decision cascade → deterministic composite scoring

### Added

- TechnicalAnalysisAgent
- LiquidityEngine
- CompositeScorer
- Daily drawdown block
- Breakeven stop logic

### Compatibility

- Redis keys from v1 remain preserved where needed
- Trade audit logs remain compatible
- Legacy LLM debrief tables remain available

## 12. Summary

Bruno v2 is a deterministic, regime-adaptive trading system. The primary trade decision is based on the combination of technical structure, liquidity pressure, and macro flow, with strict risk controls and legacy-only LLM debriefing.

This document is the canonical reference for trading logic in v2.
