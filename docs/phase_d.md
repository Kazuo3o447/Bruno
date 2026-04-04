# Phase D — Position Tracker & Stop-Loss

> **Status:** 🟡 AKTIV — Core implementiert, Testing läuft
> 
> **Zeitraum:** Parallel zu Phase C
> 
> **Ziel:** Vollständiges Position-Tracking mit automatischen SL/TP und MAE/MFE

---

## Übersicht

Phase D implementiert das **Position Management System** für Live-Trading. Der Bot kann jetzt echte Positionen verfolgen, überwachen und automatisch schließen.

### Core Services

| Service | Aufgabe | Status |
|---------|--------|--------|
| **PositionTracker** | Redis Live-State + DB Audit Trail | ✅ |
| **PositionMonitor** | Background SL/TP Überwachung | ✅ |
| **Positions API** | REST Endpoints für Dashboard | ✅ |
| **Database Migration** | Positions Table mit JSONB Fields | ✅ |

---

## Architektur

### Dual Storage Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                        Redis (Live-State)                        │
│  - 0ms Check für offene Position                               │
│  - MAE/MFE Updates in Echtzeit                                 │
│  - Key: bruno:position:BTCUSDT                               │
│  - TTL: 60s nach Close (Dashboard Buffer)                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL (Audit Trail)                     │
│  - Vollständige Position History                              │
│  - Phase C LLM Outputs (JSONB)                                 │
│  - Performance Analytics                                       │
│  - Async Writes (nicht-blockierend)                           │
└─────────────────────────────────────────────────────────────────┘
```

### Position Lifecycle

```
Signal → RiskAgent → PositionTracker.open_position()
    ↓
Redis Live-State (0ms Check)
    ↓
PositionMonitor (Background, 30s Intervall)
    ↓
MAE/MFE Updates + TP1/TP2 / Breakeven / SL-Prüfung
    ↓
TP1-Scale-Out → Breakeven-Stop → TP2 oder SL
    ↓
Automatischer Exit → PositionTracker.close_position()
    ↓
DB Audit Trail (async)
```

---

## PositionTracker Core

### Public API

```python
# Check vor Entry
if await position_tracker.has_open_position("BTCUSDT"):
    raise ValueError("Position bereits offen")

# Position öffnen
position_id = await position_tracker.open_position(
    symbol="BTCUSDT",
    side="long",
    entry_price=60000.0,
    quantity=0.001,
    stop_loss_price=59000.0,
    take_profit_price=62000.0,
    entry_trade_id="trade_123",
    take_profit_1_price=61000.0,
    take_profit_2_price=62000.0,
    tp1_size_pct=0.50,
    tp2_size_pct=0.50,
    breakeven_trigger_pct=0.005,
    # Phase C Fields (optional)
    grss_at_entry=55.0,
    layer1_output={"regime": "trending_bull"},
    layer2_output={"decision": "BUY"},
    layer3_output={"blocker": False},
    regime="trending_bull"
)

# Position schließen
position = await position_tracker.close_position(
    symbol="BTCUSDT",
    exit_price=61000.0,
    reason="take_profit",
    exit_trade_id="exit_456"
)
```

### Position State

```python
{
    "id": "uuid-v4",
    "symbol": "BTCUSDT",
    "side": "long",
    "entry_price": 60000.0,
    "entry_time": "2026-03-29T18:00:00Z",
    "entry_trade_id": "trade_123",
    "initial_quantity": 0.001,
    "quantity": 0.001,
    "stop_loss_price": 59000.0,
    "take_profit_price": 62000.0,
    "take_profit_1_price": 61000.0,
    "take_profit_2_price": 62000.0,
    "tp1_size_pct": 0.50,
    "tp2_size_pct": 0.50,
    "breakeven_trigger_pct": 0.005,
    # Phase C LLM Context
    "grss_at_entry": 55.0,
    "layer1_output": {"regime": "trending_bull", "confidence": 0.8},
    "layer2_output": {"decision": "BUY", "confidence": 0.7},
    "layer3_output": {"blocker": False},
    "regime": "trending_bull",
    # Excursion Tracking
    "mae_pct": -0.015,      # -1.5% Max Adverse Excursion
    "mfe_pct": 0.025,       # +2.5% Max Favorable Excursion
    "current_pnl_pct": 0.016, # +1.6% Current P&L
    "realized_pnl_pct": 0.008,
    "realized_pnl_eur": 1.25,
    "tp1_hit": true,
    "breakeven_active": true,
    # Status
    "status": "open",
    "created_at": "2026-03-29T18:00:00Z"
}
```

---

## PositionMonitor

### Background Tasks

```python
class PositionMonitor:
    """Background Service für Position-Überwachung."""
    
    async def _monitor_loop(self):
        while self._running:
            await self._check_all_positions()
            await asyncio.sleep(30.0)  # 30s Intervall
```

### Monitoring Logic

```python
async def _check_symbol(self, symbol: str):
    # 1. Offene Position prüfen
    if not await self.position_tracker.has_open_position(symbol):
        return
    
    # 2. Aktuellen Preis holen
    current_price = await self._get_current_price(symbol)
    
    # 3. MAE/MFE aktualisieren
    await self.position_tracker.update_excursions(symbol, current_price)
    
    # 4. TP1-Scale-Out / Breakeven / SL/TP2 prüfen
    await self._check_stop_loss_take_profit(symbol, current_price)
```

### SL/TP Logic

```python
async def _check_stop_loss_take_profit(self, symbol: str, current_price: float):
    position = await self.position_tracker.get_open_position(symbol)
    
    side = position["side"]
    sl = position["stop_loss_price"]
    tp1 = position.get("take_profit_1_price", position["take_profit_price"])
    tp2 = position.get("take_profit_2_price", position["take_profit_price"])
    
    exit_reason = None

    if not position.get("tp1_hit"):
        if side == "long" and current_price >= tp1:
            await self.position_tracker.scale_out_position(
                symbol=symbol,
                exit_price=current_price,
                reason="take_profit_1",
                fraction=position.get("tp1_size_pct", 0.5),
                move_stop_to_breakeven=True,
            )
        elif side == "short" and current_price <= tp1:
            await self.position_tracker.scale_out_position(
                symbol=symbol,
                exit_price=current_price,
                reason="take_profit_1",
                fraction=position.get("tp1_size_pct", 0.5),
                move_stop_to_breakeven=True,
            )
    
    if side == "long":
        if current_price <= sl: exit_reason = "stop_loss"
        elif current_price >= tp2: exit_reason = "take_profit"
    else:  # short
        if current_price >= sl: exit_reason = "stop_loss"
        elif current_price <= tp2: exit_reason = "take_profit"
    
    if exit_reason:
        await self.position_tracker.close_position(
            symbol=symbol,
            exit_price=current_price,
            reason=exit_reason
        )
```

---

## Database Schema

### Positions Table

```sql
CREATE TABLE positions (
    id VARCHAR(36) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price NUMERIC(18,8) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_trade_id VARCHAR(100) NOT NULL,
    quantity NUMERIC(18,8) NOT NULL,
    stop_loss_price NUMERIC(18,8) NOT NULL,
    take_profit_price NUMERIC(18,8) NOT NULL,
    
    -- Phase C LLM Context
    grss_at_entry NUMERIC(5,2),
    layer1_output JSONB,
    layer2_output JSONB,
    layer3_output JSONB,
    regime VARCHAR(20),
    
    -- Excursion Tracking
    mae_pct NUMERIC(8,6),
    mfe_pct NUMERIC(8,6),
    current_pnl_pct NUMERIC(8,6),
    
    -- Status & Exit
    status VARCHAR(20) NOT NULL,
    exit_price NUMERIC(18,8),
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(20),
    exit_trade_id VARCHAR(100),
    pnl_eur NUMERIC(18,4),
    pnl_pct NUMERIC(8,6),
    hold_duration_minutes INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- Indexes für Performance
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_entry_time ON positions(entry_time);
CREATE INDEX idx_positions_symbol_status ON positions(symbol, status);
```

---

## API Endpoints

### Position Status

```bash
GET /api/v1/positions/open
GET /api/v1/positions/BTCUSDT/status
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "has_position": true,
  "position": {
    "id": "uuid-v4",
    "side": "long",
    "entry_price": 60000.0,
    "current_price": 61000.0,
    "current_pnl_pct": 0.016,
    "current_pnl_eur": 0.96,
    "mae_pct": -0.015,
    "mfe_pct": 0.025,
    "grss_at_entry": 55.0,
    "regime": "trending_bull"
  },
  "status": "open"
}
```

### Test Endpoints

```bash
POST /api/v1/positions/test/open
{
  "symbol": "BTCUSDT",
  "side": "long",
  "entry_price": 60000.0,
  "quantity": 0.001,
  "stop_loss_price": 59000.0,
  "take_profit_price": 62000.0
}

POST /api/v1/positions/test/close
{
  "symbol": "BTCUSDT",
  "exit_price": 61000.0,
  "reason": "take_profit"
}
```

### Monitor Control

```bash
GET /api/v1/positions/monitor/status
POST /api/v1/positions/monitor/start
POST /api/v1/positions/monitor/stop
```

### History

```bash
GET /api/v1/positions/history?symbol=BTCUSDT&limit=50
```

---

## Integration mit Phase C

### LLM Cascade → PositionTracker

```python
# In QuantAgent nach Cascade
if cascade_result.is_actionable:
    # Position öffnen mit LLM Context
    position_id = await position_tracker.open_position(
        symbol="BTCUSDT",
        side=cascade_result.decision.lower(),
        entry_price=current_price,
        quantity=calculated_size,
        stop_loss_price=current_price * (1 - cascade_result.stop_loss_pct),
        take_profit_price=current_price * (1 + cascade_result.take_profit_pct),
        entry_trade_id=trade_id,
        grss_at_entry=grss_score,
        layer1_output=cascade_result.layer1,
        layer2_output=cascade_result.layer2,
        layer3_output=cascade_result.layer3,
        regime=cascade_result.regime
    )
```

### Post-Trade Debrief (Future)

```python
# Nach Close: LLM Analyse mit vollständigen Context
closed_position = await position_tracker.get_closed_position("BTCUSDT")

debrief_prompt = f"""
Analyse diesen abgeschlossenen Trade:

Entry: {closed_position['entry_price']} @ {closed_position['entry_time']}
Exit: {closed_position['exit_price']} @ {closed_position['exit_time']}
P&L: {closed_position['pnl_pct']:.2%} ({closed_position['pnl_eur']:.2f} EUR)
MAE: {closed_position['mae_pct']:.2%}
MFE: {closed_position['mfe_pct']:.2%}
Regime: {closed_position['regime']}
GRSS at Entry: {closed_position['grss_at_entry']}

Layer 1: {closed_position['layer1_output']}
Layer 2: {closed_position['layer2_output']}
Layer 3: {closed_position['layer3_output']}

Was lernen wir daraus für zukünftige Trades?
"""
```

---

## Risk Management

### Position Guards

```python
# 1. Max 1 offene Position pro Symbol
if await position_tracker.has_open_position(symbol):
    raise ValueError("Position bereits offen")

# 2. Kapital-Check (Portfolio State)
portfolio = await redis.get_cache("bruno:portfolio:state")
current_exposure = portfolio.get("total_exposure_eur", 0.0)
max_exposure = portfolio.get("capital_eur", 10000.0) * 0.1  # 10%

if current_exposure + position_value > max_exposure:
    raise ValueError("Max Exposure erreicht")
```

### Dynamic Sizing

```python
# Regime-basierte Size Berechnung
regime_config = regime_manager.get_config()
base_size = 0.001  # 0.001 BTC
position_size = base_size * regime_config.position_size_multiplier

# Volatilitäts-Anpassung
atr = await atr_calculator.get_current_atr(symbol)
if atr > current_price * 0.02:  # > 2% Volatilität
    position_size *= 0.7  # 30% reduzieren
```

---

## Performance & Reliability

### Redis Performance

- **0ms Check** für offene Positionen
- **TTL Management** nach Close (60s Buffer)
- **Connection Pooling** für hohe Frequenz

### Async DB Writes

```python
# Nicht-blockierend für Trading-Pfad
async def _persist_open_to_db(self, position: dict):
    try:
        async with self.db_session_factory() as session:
            await session.execute(sql, position)
            await session.commit()
    except Exception as e:
        logger.error(f"DB Write Error: {e}")  # Trading läuft weiter
```

### Error Handling

```python
# Idempotent Operations
async def open_position(...):
    if await self.has_open_position(symbol):
        raise ValueError("Position bereits offen")  # Guard
    
    # Atomic Redis Write
    await self.redis.set_cache(key, position)
    
    # Async DB Write (Best-Effort)
    asyncio.create_task(self._persist_open_to_db(position))
```

---

## Testing & Validation

### Unit Tests

```python
async def test_position_lifecycle():
    tracker = PositionTracker(redis_mock, db_mock)
    
    # Open
    pos_id = await tracker.open_position(
        symbol="BTCUSDT", side="long", entry_price=60000,
        quantity=0.001, sl=59000, tp=62000, trade_id="test"
    )
    assert await tracker.has_open_position("BTCUSDT")
    
    # Update Excursions
    await tracker.update_excursions("BTCUSDT", 61000)
    pos = await tracker.get_open_position("BTCUSDT")
    assert pos["mfe_pct"] > 0
    
    # Close
    closed = await tracker.close_position("BTCUSDT", 61000, "take_profit")
    assert closed["pnl_pct"] > 0
```

### Integration Tests

```python
async def test_sl_tp_monitoring():
    monitor = PositionMonitor(tracker, redis)
    
    # Position öffnen
    await tracker.open_position(..., sl=59000, tp=62000)
    
    # SL auslösen
    await monitor._check_symbol("BTCUSDT")  # Price = 58500
    
    # Prüfen ob geschlossen
    assert not await tracker.has_open_position("BTCUSDT")
```

---

## Monitoring & Observability

### Dashboard Metrics

```python
# Position Status
{
  "has_position": True,
  "current_pnl_pct": 0.016,
  "mae_pct": -0.015,
  "mfe_pct": 0.025,
  "hold_duration_minutes": 45,
  "regime": "trending_bull"
}

# Monitor Status
{
  "running": True,
  "check_interval": 30.0,
  "symbols": ["BTCUSDT"],
  "last_check": "2026-03-29T18:00:00Z"
}
```

### Alerts

```python
# SL/TP Hit
logger.info(f"Position GESCHLOSSEN ✅: TAKE_PROFIT | LONG BTCUSDT @ 62000 | P&L=+3.33%")

# MAE Warning
if position["mae_pct"] < -0.02:  # -2%
    logger.warning(f"High MAE Alert: {position['mae_pct']:.2%}")

# Monitor Health
if not monitor._running:
    logger.error("PositionMonitor nicht aktiv!")
```

---

## Next Steps

### Immediate (Testing)
- [ ] End-to-End Tests mit echten Preisen
- [ ] SL/TP Automation Validation
- [ ] Performance Benchmarks

### Short Term (Integration)
- [ ] ExecutionAgentV3 Live-Exit Tests
- [ ] Dashboard Frontend
- [ ] Alert System

### Medium Term (Enhancements)
- [ ] Multi-Symbol Support
- [ ] Dynamic SL/TP (Trailing Stops)
- [ ] Post-Trade Debrief LLM

---

## Success Criteria

### Phase D Complete Wenn:
- [x] PositionTracker mit Redis/DB implementiert
- [x] PositionMonitor mit SL/TP Automation
- [x] Positions API mit Test Endpoints
- [x] Database Migration mit JSONB Fields
- [ ] SL/TP Tests erfolgreich
- [ ] MAE/MFE Tracking validiert
- [x] Integration mit ExecutionAgentV3 im Worker
- [ ] Frontend Dashboard Integration

---

*Phase D macht den Bruno Bot "live-trading-fähig" — von Shadow Trading zu echten Positionen mit automatischem Risk Management.*
