# BRUNO PAPER TRADING LAUNCH CHECKLIST

**Version:** v3.0 — Conflict Resolution & Paper Launch Ready  
**Date:** April 2026  
**Goal:** Validate all Prompts 01-06 features before Paper Trading launch

---

## ✅ PRE-LAUNCH VALIDATION

### 1. Test Suite (Prompts 01-06)
- [ ] **All unit tests pass**
  ```bash
  cd backend
  PYTHONPATH=. python -m pytest tests/ -v --tb=short
  ```
  - Expected: 0 failures, all prompts covered
  - Tests to verify:
    - `test_conflict_resolution.py` (Prompt 02)
    - `test_composite_reform.py` (Prompt 03)
    - `test_bybit_hedge_mode.py` (Prompt 04)
    - `test_funding_filter.py` (Prompt 05)
    - `test_execution_hygiene.py` (Prompt 06)

- [ ] **Smoke Test 4/4 scenarios pass**
  ```bash
  cd backend
  PYTHONPATH=. python scripts/smoke_test_paper.py
  ```
  - [ ] Scenario 1: Trend Bull → LONG, full size, mr_mode=False
  - [ ] Scenario 2: Trend Bear → SHORT, full size, mr_mode=False
  - [ ] Scenario 3: Conflict Long-TA vs Bear-Macro → LONG, MR-Mode (50% size)
  - [ ] Scenario 4: Pure Ranging → HOLD (no trade)

### 2. Kill-Switch System Test
- [ ] **Simulate 8 consecutive losses**
  ```bash
  # Use Redis CLI or API to set consecutive_losses_global = 8
  redis-cli HSET bruno:portfolio:state consecutive_losses_global 8
  ```
- [ ] **Verify 9th trade is BLOCKED**
  - Check logs for: `Kill-Switch: Trade rejected due to 8 consecutive losses`
- [ ] **Reset killswitch**
  ```bash
  curl -X POST http://localhost:8000/api/v1/risk/reset-killswitch
  ```
- [ ] **Verify trading resumes**
  - 10th trade should be allowed

### 3. Bybit Testnet 24h Dry-Run
**Setup:**
- [ ] DRY_RUN=false (or use Bybit Testnet API keys)
- [ ] BYBIT_MODE=demo in .env
- [ ] LEARNING_MODE_ENABLED=true in config.json

**Execution:**
- [ ] Run bot for 24h on Testnet
- [ ] Monitor logs continuously

**Acceptance Criteria:**
- [ ] ≥3 Trades ausgeführt (Long OR Short)
- [ ] ≥1 Long UND ≥1 Short im Verlauf
- [ ] 0 Order-Fehler wegen positionIdx/reduceOnly
- [ ] Kill-Switch greift wenn manuell ausgelöst

**Log Checks:**
```bash
# Count trades
grep "Trade executed" logs/bruno.log | wc -l

# Check for order errors
grep -i "order.*error\|positionIdx\|reduceOnly" logs/bruno.log

# Verify MR-Mode trades
grep "MR-MODE" logs/bruno.log
```

### 4. Funding Monitor Validation
- [ ] **Funding data in Redis**
  ```bash
  redis-cli GET market:funding:current
  # Should return: {"funding_rate": X, "funding_bps": Y, ...}
  ```
- [ ] **Funding Score in Composite**
  - Check logs for: `Funding: +X.X` in Composite Score line
- [ ] **Soft-Veto working**
  - When |funding| > 0.05% against trade direction
  - Log should show: `FUNDING_HEADWIND_WARNING`

### 5. Frontend Validation
- [ ] **Killswitch banner visible when active**
  - Navigate to: http://localhost:3000/einstellungen
  - Trigger killswitch via API
  - Verify red banner appears
- [ ] **Killswitch reset works**
  - Click "Reset" button
  - Verify banner disappears
  - Verify trading resumes

### 6. Config Validation
- [ ] **LEARNING_MODE_ENABLED=true**
  ```bash
  grep "LEARNING_MODE_ENABLED" backend/config.json
  ```
- [ ] **DRY_RUN=true OR Bybit Testnet keys**
  ```bash
  # Check .env
  grep -E "DRY_RUN|BYBIT_MODE|BYBIT_API_KEY" backend/.env
  ```

---

## 📊 POST-LAUNCH MONITORING (First Week)

### Daily Checks
- [ ] **Trade Frequency**: 3-8 trades/day expected
- [ ] **Composite Histogram**: Export daily for analysis
  ```bash
  curl http://localhost:8000/api/v1/decisions/histogram?days=1 > composite_hist_$(date +%Y%m%d).json
  ```
- [ ] **Kill-Switch Status**: Verify not triggered unintentionally
- [ ] **Funding Impact**: Monitor funding_score distribution

### Weekly Review
- [ ] **Win Rate Analysis**: Check if MR-Mode trades perform differently
- [ ] **Slippage Report**: Review all slippage_rejected events
- [ ] **Funding Cost**: Calculate actual funding costs vs. predictions

---

## 🚨 EMERGENCY PROCEDURES

### If Kill-Switch Triggers
1. Check `bruno:portfolio:state` in Redis for `consecutive_losses_global`
2. Analyze last 8 trades in database
3. Decide: Reset or keep blocked for manual review

### If Order Errors Occur
1. Check logs for `positionIdx` or `reduceOnly` errors
2. Verify `bruno:bybit:position_mode` in Redis
3. Ensure Hedge Mode is properly detected

### If No Trades for 24h
1. Check Composite Threshold (should be 8 in Learning Mode)
2. Verify GRSS data is flowing
3. Check for `Veto_Active` in context
4. Review Funding Monitor status

---

## 📋 SIGN-OFF

**Verified By:** _________________  **Date:** _________________

**Notes:**
```
[Space for additional notes/issues found during validation]
```

---

## QUICK REFERENCE

### Key Redis Keys to Monitor
```
bruno:portfolio:state                    # Portfolio + consecutive_losses_global
bruno:portfolio:daily_limit_hit          # Kill-switch status
bruno:bybit:position_mode                # hedge or one_way
bruno:context:grss                       # GRSS Score + Data_Status
market:funding:current                   # Current funding rate
```

### Key Log Patterns
```
# Successful trade
"Trade executed" + "RISK-BASED SIZING"

# MR-Mode trade
"MR-MODE: Sizing reduziert um 50%"

# Funding impact
"FUNDING_HEADWIND_WARNING"

# Slippage reject
"EXCESS SLIPPAGE REJECT"

# Kill-switch
"Kill-Switch: Trade rejected"
```

### API Endpoints
```
POST /api/v1/risk/reset-killswitch      # Reset kill-switch
GET  /api/v1/config                      # View config
GET  /api/v1/debug/trade-pipeline        # Pipeline diagnostics
GET  /api/v1/decisions/histogram         # Composite histogram
```

---

**Status:** ⬜ NOT STARTED | 🟡 IN PROGRESS | 🟢 COMPLETE

**Launch Date Target:** ___/___/______
