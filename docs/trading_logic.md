# Bruno v3.0 Trading Logic

## 1. Purpose

Bruno v3.0 is a **deterministic institutional** trading system with zero tolerance for heuristics and hard blocks. The system features:

1. **Strategy Blending (A/B)** - Trend Following + Mean Reversion mit regime-adaptiver Gewichtung
2. **Sweep Signal Integration** - Professional Liquidity Sweep Detection (+30/-30, 5min TTL)
3. **Symmetric Scoring Logic** - Faire Bull/Bear Behandlung (keine Asymmetrie mehr)
4. **No Hard Blocks** - Risk wird in Score gepreist, nicht geblockt
5. **ATR-Ratio Regime Detection** - Volatilität normalisiert auf Preis statt VIX
6. **Bollinger Bands** - BB-Width für präzise Regime-Erkennung
7. **Death Zone Removal** - Liquidation Clusters als Opportunities, nicht Gefahren
8. **Learning Mode Optimization** - Threshold 16 statt 30, kein Hard Floor
9. **Sequential should_trade Logic** - Deterministische Entscheidungsreihenfolge
10. **Robust Data Sources** - Bybit V5 WebSocket als Single Source of Truth
11. **Balanced Scoring** - Keine Conviction-Blocker, nur Threshold Gate
12. **Bybit V5 Single Source** - Exklusive WebSocket-Daten mit präziser CVD
13. **Privacy-First News** - Multi-Source News mit SHA256 Deduplizierung
14. **Deepseek API** - Post-Trade Analyse (kein LLM im Live Trading)

The system maintains **100% deterministic live trading** with **zero heuristics** policy while implementing symmetric scoring and strategy diversification.

## 2. Data Flow Overview (v3.0)

```text
Bybit V5 WebSocket → BybitV5Client → Redis (CVD, VWAP, VPOC)
    ↓
News Sources (CryptoPanic, RSS, Free-Crypto-News) → NewsIngestionService → SentimentAnalyzer
    ↓
TechnicalAnalysisAgent → bruno:ta:snapshot
    ├── Bollinger Bands (BB-Width)
    ├── ATR-Ratio (ATR/Price)
    ├── EMA Stack, RSI, VWAP
    └── Macro Trend (Daily EMA 50/200)
    ↓
Liquidity Engine → bruno:liq:intelligence
    ├── Sweep Detection (3× confirmation)
    ├── Sweep Signal (+30/-30, 5min TTL)
    └── Liquidation Clusters (opportunities, no veto)
    ↓
ContextAgent → bruno:context:grss (GRSS v3, Funding Rate, EUR/USD)
    ↓
CompositeScorer → bruno:decisions:feed
    ├── Strategy A: Trend Following (TA + Liq + Flow + Macro)
    ├── Strategy B: Mean Reversion (RSI + VWAP Distance)
    ├── Strategy Blending (regime-adaptive: 40%/30%/10%)
    └── Symmetric Scoring (Bull/Bear balanced)
    ↓
Regime Detector (v3)
    ├── ATR-Ratio > 2.5% → high_vola
    ├── BB-Width > 4.0% → high_vola
    └── EMA Stack + Macro Trend + Vola-Filter
    ↓
Risk Agent (v3)
    ├── Data Freshness Checks
    ├── Daily Drawdown Limit
    └── ✅ Death Zone REMOVED (no veto)
    ↓
Execution Agent
    ├── Paper Trading Only (PAPER_TRADING_ONLY=true)
    ├── Multi-Level TP (TP1 50% / TP2 50%)
    └── Breakeven Stop @ +0.5%
    ↓
PositionTracker → Multi-Slot Position Management
```

### 2.1 v3 Architecture Changes

**🔴 MAJOR ARCHITECTURE REFINEMENTS:**

1. **Death Zone Removal** - Liquidation Clusters sind jetzt Trading-Opportunities, kein Veto mehr
2. **Symmetric Scoring** - Macro Bull + Long erhält +20% Bonus (wie Bear + Short)
3. **Sweep Signal Integration** - +30/-30 Score mit 5min TTL für SSL/BSL Sweeps
4. **Mean Reversion Sub-Engine** - Contrarian Strategy mit RSI + VWAP Distance (-50..+50)
5. **Strategy Blending (A/B)** - Trend Following + Mean Reversion mit regime-adaptiver Gewichtung
6. **ATR-Ratio Regime Detection** - Volatilität normalisiert auf Preis statt VIX
7. **Bollinger Bands** - BB-Width für präzise Regime-Erkennung
8. **Learning Mode Optimization** - Threshold 16 statt 30, kein Hard Floor
9. **Conviction Gates Removed** - Nur Threshold Gate, keine Conviction-Blocker

### 2.2 Strategy Blending (A/B)

**Zwei Strategien werden regime-adaptiv kombiniert:**

```python
# Strategy A: Trend Following (TA + Liq + Flow + Macro)
strategy_a_score = (
    ta_score * weights["ta"] +
    (liq_score * 2) * weights["liq"] +
    (flow_score * 2) * weights["flow"] +
    (macro_score * 2) * weights["macro"]
)

# Strategy B: Mean Reversion (RSI + VWAP Distance)
strategy_b_score = mean_reversion_score * 2  # Normalize to -100..+100

# Blend Ratio by Regime
blend_ratios = {
    "ranging": 0.4,        # 40% MR, 60% Trend
    "high_vola": 0.3,      # 30% MR, 70% Trend
    "trending_bull": 0.1,  # 10% MR, 90% Trend
    "bear": 0.1,           # 10% MR, 90% Trend
    "default": 0.2         # 20% MR, 80% Trend
}

# Final Composite
composite = (strategy_a * (1 - blend)) + (strategy_b * blend)
```

### 2.3 Mean Reversion Sub-Engine

**Contrarian Strategy für überkaufte/überverkaufte Zustände:**

```python
# RSI Extremes (±20 Punkte)
if rsi < 20:   score += 20  # Stark oversold → bullish
elif rsi < 30: score += 15  # Oversold
elif rsi < 40: score += 8   # Leicht oversold

elif rsi > 80:   score -= 20  # Stark overbought → bearish
elif rsi > 70:   score -= 15  # Overbought
elif rsi > 60:   score -= 8   # Leicht overbought

# VWAP Distanz (±15 Punkte)
vwap_distance_pct = ((price - vwap) / vwap) * 100
if vwap_distance_pct < -1.5:   score += 15  # Preis >1.5% unter VWAP
elif vwap_distance_pct < -0.8: score += 8
elif vwap_distance_pct > 1.5:  score -= 15  # Preis >1.5% über VWAP
elif vwap_distance_pct > 0.8:  score -= 8

# Regime-Adjustment
if regime in ("trending_bull", "bear"):
    score *= 0.5  # 50% Reduktion in Trends
elif regime == "high_vola":
    score *= 0.7  # 30% Reduktion bei hoher Vola
```

**Output:** Mean Reversion Score: -50 bis +50

### 2.4 Sweep Signal (+30/-30)

**Professional Liquidity Sweep Detection mit 3-facher Bestätigung:**

```python
# Sweep-Bedingungen (ALLE müssen erfüllt sein):
1. Liquidation Spike: >$500k in 5 Minuten, >70% eine Seite
2. Wick Formation: Bullish/Bearish Hammer (aus TA Snapshot)
3. OI Delta: Open Interest fällt (Positionen schließen, nicht neu eröffnen)

# Scoring:
SSL Sweep (longs liquidated) → +30 Score (bullish)
BSL Sweep (shorts liquidated) → -30 Score (bearish)

# TTL: 5 Minuten (300 Sekunden)
self._active_sweep_signals = [
    {"side": "long", "score": 30.0, "expiry": now + 300}
]
```

### 2.5 Regime Detection (v3 - ATR-Ratio)

**Volatilität normalisiert auf Preis statt VIX:**

```python
# ATR-Ratio: Volatilität relativ zum Preis
atr = float(ta_data.get("atr_14", 0.0))
price = float(ta_data.get("price", 0.0))
atr_ratio = (atr / price * 100) if price > 0 else 0.0

# BB-Width: Bollinger Band Breite
bb_data = ta_data.get("bollinger_bands", {})
bb_width = float(bb_data.get("width", 0.0))

# High Volatility Detection
if atr_ratio > 2.5 or bb_width > 4.0:
    return "high_vola"

# Trend Detection mit Volatilitäts-Filter
if ema_stack in ("perfect_bull", "bull"):
    if atr_ratio > 1.8:
        return "ranging"  # Zu hohe Vola bricht Trend
    return "trending_bull" if atr_ratio < 1.0 else "ranging"
```

### 2.6 Learning Mode Optimization
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

## 9. Sequential should_trade Logic (v2.1 Critical Fix)

### 9.1 Problem Statement

**Vor v2.1:** Regime/Macro-Blöcke konnten von Threshold überschrieben werden:
```python
# Regime Block (wird überschrieben)
if result.direction == "long" and not regime_cfg.allow_longs:
    result.should_trade = False

# Threshold Check (überschreibt alles)
result.should_trade = abs_score >= effective_threshold  # ← PROBLEM!
```

**Nach v2.1:** Sequenzielle Logik - Blöcke können nur blockieren, nie freigeben:
```python
# === SEQUENTIELLE SHOULD_TRADE LOGIK ===

# SCHRITT 1: Threshold Check (setzt should_trade initial)
result.should_trade = abs_score >= effective_threshold

# SCHRITT 2: Conviction Check
if result.conviction < regime_cfg.confidence_threshold:
    result.should_trade = False
    result.signals_active.append(f"Low conviction {result.conviction:.2f}")

# SCHRITT 3: Regime Direction Filter (kann nur blockieren)
if result.should_trade and result.direction == "long" and not regime_cfg.allow_longs:
    result.should_trade = False
    result.signals_active.append(f"BLOCKED: {regime} regime disallows longs")

# SCHRITT 4: Macro Trend Hard Block (kann nur blockieren)
if result.should_trade and result.direction == "long" and not mt_allow_longs:
    result.should_trade = False
    result.signals_active.append(f"⛔ MACRO BLOCK: No longs in {macro_trend}")

# SCHRITT 5: Sizing Check (kann nur blockieren)
if result.should_trade and not sizing.get("sizing_valid", False):
    result.should_trade = False
    result.signals_active.append(f"SIZING REJECT: {sizing.get('reject_reason')}")
```

### 9.2 Decision Flow Examples

**Example 1: High Score aber Regime Block**
```text
Score: 80 (>= Threshold 40) → should_trade = True
Regime: high_vola, allow_longs = False → should_trade = False
Result: BLOCKED despite high score ✅
```

**Example 2: Low Score**
```text
Score: 25 (< Threshold 40) → should_trade = False
Regime: normal, allow_longs = True → bleibt False
Result: No trade due to low score ✅
```

### 9.3 Logic Invariants

1. **Threshold sets initial state** - can only enable trading
2. **All subsequent steps can only disable** - never enable
3. **Order is deterministic** - Threshold → Conviction → Regime → Macro → Sizing
4. **No overrides possible** - once blocked, stays blocked

## 10. Robust Data Sources (v2.1)

### 10.1 Fear & Greed Index with Retry

**Problem:** Single API failure → 24h no F&G data
**Solution:** 5× Retry with exponential backoff

```python
async def _poll_fg_index(self):
    while self.state.running:
        success = False
        for attempt in range(5):  # Max 5 Versuche
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get("https://api.alternative.me/fng/")
                    if response.status_code == 200:
                        # ... process data ...
                        success = True
                        break
            except Exception as e:
                self.logger.warning(f"F&G Polling Versuch {attempt+1}/5 fehlgeschlagen: {e}")
            
            # Exponentieller Backoff: 30s, 60s, 120s, 240s, 480s
            await asyncio.sleep(30 * (2 ** attempt))
        
        if not success:
            self.logger.error("F&G Index NICHT verfügbar nach 5 Versuchen")
        
        # Nächstes Update: alle 6 Stunden (statt 24h)
        await asyncio.sleep(21600)
```

### 10.2 Dynamic EUR/USD Rates

**Problem:** Hardcoded 1.08 rate
**Solution:** Yahoo Finance API with Redis cache

```python
# ContextAgent
async def _fetch_eur_usd(self) -> float:
    CACHE_KEY = "macro:eurusd"
    cached = await self.deps.redis.get_cache(CACHE_KEY)
    if cached is not None:
        return float(cached)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X",
                headers={"User-Agent": self._user_agent}
            )
            if r.status_code == 200:
                rate = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
                await self.deps.redis.set_cache(CACHE_KEY, rate, ttl=3600)
                return rate
    except Exception as e:
        self.logger.warning(f"EUR/USD Fetch Fehler: {e}")
    return 1.08  # Fallback

# CompositeScorer + ExecutionAgent
eurusd_cached = await self.redis.get_cache("macro:eurusd")
eur_to_usd = float(eurusd_cached) if eurusd_cached else 1.08
capital_usd = capital_eur * eur_to_usd
```

### 10.3 Macro Trend insufficient_data Conservative

**Problem:** <200 Daily candles → allow_longs=True, allow_shorts=True
**Solution:** Conservative - no trading without data

```python
if len(candles_1d) < 200:
    return {
        "macro_trend": "insufficient_data",
        "allow_longs": False,   # GEÄNDERT: konservativ
        "allow_shorts": False,  # GEÄNDERT: konservativ
        "insufficient_data": True,
    }
```

### 10.4 Daily Backfill Retry Logic

```python
# Daily Backfill mit Retry
for attempt in range(3):
    self.logger.info(f"Daily Backfill Versuch {attempt+1}/3: {day_count} Tage vorhanden")
    await self._backfill_daily_candles()
    # Re-check
    day_count = await self._check_daily_candles()
    if day_count >= 200:
        self.logger.info(f"Daily Backfill erfolgreich: {day_count} Tage")
        break
    await asyncio.sleep(5)  # 5s warten zwischen Versuchen
else:
    self.logger.error(f"Daily Backfill FEHLGESCHLAGEN nach 3 Versuchen")
```

## 11. OFI Penalty Cleanup (v2.1)

### 11.1 Problem: Vierfach-Strafe

**Vor v2.1:** OFI unavailable → 4 separate penalties:
1. `_score_flow()`: `score -= 10` (hardcoded)
2. `score()`: `threshold += 8` (Threshold penalty)
3. `score()`: `flow_score *= 0.5` (dead code)
4. `score()`: `conviction *= 0.5` (Data gap penalty)

### 11.2 Solution: Single Penalty

**Nach v2.1:** Only 2 penalties:
1. **Threshold +8** - Makes trading harder
2. **Conviction * 0.5** - Reduces confidence

```python
# ENTFERNT: Hardcoded -10 Penalty aus _score_flow()
# ENTFERNT: Dead flow_score *= 0.5 Block

# BEHALTEN: Threshold +8
if flow_data.get("OFI_Buy_Pressure") is None:
    effective_threshold += 8
    result.signals_active.append("OFI Data Gap: Threshold +8")

# BEHALTEN: Conviction * 0.5 mit deduplizierter Message
critical_data_gap = macro_data.get("DVOL") is None or macro_data.get("Long_Short_Ratio") is None
if not flow_data.get("OFI_Available", True):
    critical_data_gap = True

if critical_data_gap:
    missing = []
    if not ofi_available: missing.append("OFI")
    if macro_data.get("DVOL") is None: missing.append("DVOL")
    if macro_data.get("Long_Short_Ratio") is None: missing.append("L/S Ratio")
    result.signals_active.append(f"Data Gap ({', '.join(missing)}): Conviction halved")
```

## 12. Scoring Hotfix v2.1.1 (April 2026)

### 12.1 Problem Statement

**Vor Hotfix:** Bruno produzierte HOLD bei bullischem Setup durch übermäßig restriktive Scoring-Logik:

```
outcome: COMPOSITE_HOLD
composite_score: 2.4
ta_score: 4.0                    ← bei "Perfect bull EMA stack" + MTF aligned
reason: "Low conviction 0.02 < 0.7; TA: Perfect bull EMA stack"
macro_allows_direction: false
```

**Nach Hotfix:** Balanced Scoring mit fairen Chancen für bullische Setups:

```
outcome: COMPOSITE_HOLD
composite_score: 6.6 (+175%)
ta_score: 10.0 (+150%)
reason: "TA: Perfect bull EMA stack; TA: MTF aligned long"
```

### 12.2 Bug Fixes

#### Bug 1: TA-Score Breakdown Transparency

**Problem:** "Perfect bull EMA stack" ergab nur 4 Punkte statt erwarteter 25+ Punkte.

**Lösung:** Detaillierter TA-Breakdown mit vollständiger Punktwert-Transparenz:

```python
ta_breakdown = {
    "ema_stack": 25,           # Perfect Bull EMA Stack
    "mtf_alignment": 20.0,     # MTF aligned long
    "rsi_signal": -5,          # RSI > 60 (leicht overbought)
    "vwap_position": 0,        # Preis ≈ VWAP
    "volume_bonus": -5,        # Low volume penalty
    "macro_penalty": -5.0,     # Moderate 50% penalty
    "total_before_clamp": 10.0,
    "total_after_clamp": 10.0
}
```

**Ergebnis:** TA-Score von 4.0 → 10.0 (+150%)

#### Bug 2: Conviction-Gate 0.7 Entfernt

**Problem:** Zusätzlicher Conviction-Blocker verhinderte Trades trotz gutem CompositeScore.

**Lösung:** Conviction-Check aus sequenzieller Logik entfernt:

```python
# VORHER:
if result.conviction < regime_cfg.confidence_threshold:  # 0.7 für ranging
    result.should_trade = False
    result.signals_active.append(f"Low conviction {result.conviction:.2f} < {regime_cfg.confidence_threshold}")

# NACHHER:
# SCHRITT 2: Conviction Check (nur für Diagnostik, kein Blocker!)
# Conviction wird berechnet aber darf nicht als separater Gate fungieren
# Der CompositeScore + Threshold ist der einzige Gate
```

**Ergebnis:** "Low conviction < 0.7" verschwunden aus Reason

#### Bug 3: Macro Penalty Moderat

**Problem:** 80% Macro Penalty für bullische Signale im Bärenmarkt zu restriktiv.

**Lösung:** Moderate 50% Penalty statt 80%:

```python
# VORHER:
score *= 0.2  # 80% Penalty - zu restriktiv
signals.append(f"⛔ MACRO BEAR OVERRIDE: score {original_score:.1f} → {score:.1f}")

# NACHHER:
score *= 0.5  # 50% Penalty - weniger restriktiv
signals.append(f"⚠ Macro Bear headwind: score {original_score:.1f} → {score:.1f}")
```

**Ergebnis:** CompositeScore von 2.4 → 6.6 (+175%)

#### Bug 4: Hard-Blocker MTF_NOT_ALIGNED und regime_allows_direction Entfernt

**Problem:** MTF_NOT_ALIGNED und regime_allows_direction fungierten als binäre Gates, die Trades blockierten selbst wenn der CompositeScore den Threshold deutlich überschritt. Dies widersprach dem Bruno v3 Prinzip, dass nur der CompositeScore + Threshold als Entscheidungs-Gate fungieren darf.

**Lösung:** Beide Hard-Blocker entfernt - sie beeinflussen nur noch den Score:

```python
# VORHER (_get_block_reason):
if not result.mtf_aligned:
    return "MTF_NOT_ALIGNED"

# Telemetrie-Output:
"regime_allows_direction": (
    regime_cfg.allow_longs if result.direction == "long"
    else regime_cfg.allow_shorts if result.direction == "short"
    else True
)

# NACHHER (_get_block_reason):
# MTF_NOT_ALIGNED entfernt - MTF beeinflusst nur den Score via Multiplikator
# regime_allows_direction aus Telemetrie entfernt - kein Gate mehr

# Verbleibende Gates:
if macro_data.get("Veto_Active"):
    return f"GRSS_VETO (GRSS={macro_data.get('GRSS_Score', 0):.1f} < threshold)"
if abs(result.composite_score) < threshold:
    return f"SCORE_TOO_LOW (Score={result.composite_score:+.1f}, Gap={gap:.1f}, weakest={biggest_drag})"
return "NONE"
```

**Ergebnis:** Nur noch CompositeScore + Threshold als Gate. MTF und Regime beeinflussen nur noch den Score, nicht die Trade-Entscheidung.

### 12.4 Stage-by-Stage TA-Breakdown Diagnostik

**Problem:** Der TA-Breakdown zeigte eine Residual-Differenz (~21 Punkte), die nicht durch die sichtbaren Komponenten erklärbar war. Dies erschwerte die Fehlersuche und Validierung.

**Lösung:** Implementierung einer vollständigen Stage-by-Stage-Diagnostik, die den Scoreverlauf an jeder relevanten Stelle erfasst und die Breakdown-Komponenten aus den tatsächlichen Stufenänderungen ableitet.

#### Stage Progression Checkpoints
```python
stage_progression = {
    "after_trend": 25.0,          # Nach EMA-Stack
    "after_mtf_alignment": 45.0,  # Nach MTF-Alignment
    "after_rsi": 45.0,            # Nach RSI-Signal
    "after_sr_breakout": 30.0,    # Nach S/R-Kontext + Breakout
    "after_volume": 28.0,         # Nach Volume-Bewertung
    "after_vwap": 25.0,           # Nach VWAP-Position
    "after_wick": 25.0,           # Nach Wick-Signal
    "after_mtf_filter": 25.0,     # Nach MTF-Filter
    "after_macro": 12.5,          # Nach Macro-Trend
    "pre_clamp": 12.5,            # Vor Clamp auf [-100, 100]
    "final": 12.5                 # Finaler TA-Score
}
```

#### Dynamische Breakdown-Komponenten
```python
# Statt statischer Annahmen werden die realen Deltas berechnet:
ta_breakdown["sr_proximity"] = round(
    stage_progression["after_sr_breakout"]
    - stage_progression["after_rsi"]
    - ta_breakdown["breakout_bonus"],
    1
)

ta_breakdown["mtf_penalty"] = round(
    stage_progression["after_mtf_filter"] - stage_progression["after_wick"],
    1
)

ta_breakdown["macro_penalty"] = round(
    stage_progression["after_macro"] - stage_progression["after_mtf_filter"],
    1
)
```

#### Residual-Auflösung
```python
ta_breakdown["known_components_sum"] = round(
    ta_breakdown["ema_stack"]
    + ta_breakdown["mtf_alignment"]
    + ta_breakdown["rsi_signal"]
    + ta_breakdown["sr_proximity"]
    + ta_breakdown["breakout_bonus"]
    + ta_breakdown["vwap_position"]
    + ta_breakdown["volume_bonus"]
    + ta_breakdown["wick_signal"]
    + ta_breakdown["macro_penalty"]
    + ta_breakdown["mtf_penalty"],
    1
)

ta_breakdown["residual_penalty"] = round(
    score - ta_breakdown["known_components_sum"],
    1
)
```

**Ergebnis:**
- **`residual_penalty`**: `0.0` (vorher: ~21)
- **`known_components_sum`**: `12.5` (exakt wie finaler Score)
- **Vollständige Transparenz** des Scoreverlaufs
- **Keine Änderung** an Trading-Logik, Thresholds oder Filtern

### 12.5 Validation Results

**Decision Feed vor Hotfix:**
```json
{
  "outcome": "COMPOSITE_HOLD",
  "composite_score": 2.4,
  "ta_score": 4.0,
  "reason": "Low conviction 0.02 < 0.7; TA: Perfect bull EMA stack; TA: MTF aligned long"
}
```

**Decision Feed nach Hotfix:**
```json
{
  "outcome": "COMPOSITE_HOLD", 
  "composite_score": 6.6,
  "ta_score": 10.0,
  "reason": "TA: Perfect bull EMA stack; TA: MTF aligned long"
}
```

### 12.4 Impact

**Positive Effects:**
- **TA-Score Verbesserung:** +150% (4.0 → 10.0)
- **Composite Score Verbesserung:** +175% (2.4 → 6.6)
- **Gap to Threshold Reduzierung:** -17% (24.3 → 20.1)
- **Reason Quality:** "Low conviction" → "Perfect bull EMA stack"
- **Fair Chancen:** Bullische Setups im Ranging erhalten realistische Bewertung

**System Behavior:**
- **Weniger übermäßig restriktiv**
- **Conservativ bei wirklich schwachen Signalen**
- **Balanced Scoring mit Transparenz**
- **Ready für DRY_RUN Daten-Sammlung**

## 13. Indicators

### 12.1 EMA Stack

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
