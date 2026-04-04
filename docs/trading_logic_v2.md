# Bruno v2.2 Trading Logic

## 1. Purpose

Bruno v2.2 replaces the LLM-based decision chain with a deterministic, regime-adaptive trading stack. The system is designed for medium-frequency Bitcoin trading and uses three primary decision layers:

1. **Technical Analysis** for trend, structure, and timing.
2. **Liquidity Intelligence** for sweep opportunities and cluster magnetism.
3. **Composite Scoring** for the final trade decision.

The LLM is **legacy-only** and has been removed from live trading. Only the **Deepseek Reasoning API** is used exclusively for post-trade debriefing and learning analysis by the LearningAgent, not for live trade decisions.

## 2. Data Flow Overview

```text
Binance API (REST + WebSocket) → MarketDataCollector → Redis
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

### 2.1 Binance API Integration (v2.1)

**MarketDataCollector** holt automatisch alle 30 Sekunden:
- **Ticker**: Aktueller Preis und 24h Statistiken
- **Klines**: 1-Minuten Candlesticks für Technical Analysis
- **Orderbook**: Bids/Asks mit Imbalance Ratio für OFI
- **Funding Rate**: Futures Funding für Sentiment
- **Open Interest**: Markttiefe und Liquidität
- **Liquidations**: Liquidation Orders für Risk Management

**Redis Storage Pattern:**
```bash
# Sehr frisch (5-10s TTL)
market:ticker:BTCUSDT           # {"last_price": 67263.7}
market:orderbook:BTCUSDT        # {"imbalance_ratio": 1.23}
market:ofi:ticks               # [{"t": "...", "r": 1.23}, ...]

# Frisch (60s TTL)
bruno:ta:klines:BTCUSDT        # {"klines": [...], "count": 500}
market:liquidations:BTCUSDT    # [{"side": "SELL", "price": 67000}]

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

### 6.5 Trade Cooldown

Minimum cooldown:

```text
TRADE_COOLDOWN_SECONDS = 300
```

No new signal is published before this cooldown has expired.

## 7. Execution and Portfolio Handling

ExecutionAgentV3 performs:

- SL / TP monitoring
- TP1 scale-out
- breakeven adjustment
- TP2 final exit
- position closing
- portfolio updates in DRY_RUN

PositionTracker stores the live state for:

- `initial_quantity`
- `take_profit_1_price`
- `take_profit_2_price`
- `tp1_size_pct`
- `tp2_size_pct`
- `breakeven_trigger_pct`
- `realized_pnl_eur` / `realized_pnl_pct`
- `tp1_hit` / `breakeven_active`

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
- `market:liquidations:{symbol}:events`

### Legacy / Post-Trade Learning

- `trade_debriefs` table
- `bruno:learning:metrics`
- `bruno:learning:layer_*`

### Phantom Trade Learning

- `bruno:phantom_trades:pending`
- `market_candles` scan for MAE/MFE evaluation

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
  "BREAKEVEN_TRIGGER_PCT": 0.005,
  "TAKE_PROFIT_1_PCT": 0.012,
  "TAKE_PROFIT_2_PCT": 0.020,
  "TP1_SIZE_PCT": 0.50,
  "TP2_SIZE_PCT": 0.50
}
```

If all four `COMPOSITE_W_*` keys are present, config override can replace the default presets. Otherwise the regime defaults apply.

## 10. Post-Trade Analysis with Deepseek API

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

## 11. Migration Notes

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

## 12. Summary

Bruno v2 is a deterministic, regime-adaptive trading system. The primary trade decision is based on the combination of technical structure, liquidity pressure, and macro flow, with strict risk controls and **Deepseek Reasoning API** for post-trade debriefing and learning.

**Key Features:**
- **Live Trading:** 100% deterministic without LLM interference
- **Post-Trade Analysis:** Professional Deepseek API integration
- **Risk Management:** 6 hard vetos with circuit breakers
- **Learning System:** Cloud-based intelligence for continuous improvement
- **Performance:** Sub-2s response times for trade analysis

This document is the canonical reference for trading logic in v2.
