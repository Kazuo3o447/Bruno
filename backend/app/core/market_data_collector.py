# PROMPT 4/5 * Exit Strategy Overhaul: Trailing Stop & TP1/TP2 Scaling

## Kontext
# Bruno hat aktuell nur einen simplen Breakeven-Stop (SL auf Entry + 0.1% nach 0.5% Gewinn) und einen fixen TP. Das CompositeScorer-Signal enthält bereits TP1/TP2 mit Size-Splits, aber der ExecutionAgent ignoriert diese komplett. Ohne Trailing Stop verschenkt Bruno systematisch Gewinn bei starken Moves.

## Scope
# Datei: `backend/app/agents/execution_v4.py` (Position Monitor, Trade Execution)  
# Datei: `backend/app/services/position_tracker.py` (Position State)

# ---

## Feature 1: ATR-basierter Trailing Stop (Chandelier Exit)

### Konzept
# Der Trailing Stop folgt dem Preis mit einem ATR-Abstand. Bei Longs: Trailing Stop = Höchstpreis - (ATR * Multiplikator). Der Stop kann nur nach oben bewegt werden, nie nach unten.

### Phasen des Exits:
# ```
# Phase 1: Fixer SL (Entry bis Breakeven-Trigger)
# Phase 2: Breakeven (SL auf Entry + 0.1%)
# Phase 3: Trailing Stop (SL folgt dem Preis mit ATR-Abstand)
# ```

### Implementation
# In `execution_v4.py`, ersetze die bestehende `_monitor_position()` Methode:

# ```python
# async def _monitor_position(self):
#     """
#     Position Monitor mit 3-Phasen Exit-Management.
    
#     Phase 1: Fixer SL/TP (0% bis +0.5%)
#     Phase 2: Breakeven Stop (+0.5% bis +1.2%)
#     Phase 3: ATR Trailing Stop (ab +1.2%)
    
#     TP1 Scaling: Bei TP1 wird 50% der Position geschlossen.
#     TP2: Restposition wird bei TP2 oder via Trailing Stop geschlossen.
#     """
#     self.logger.info("Position-Monitor v2 gestartet (10s Intervall).")
    
#     while self.state.running:
#         try:
#             pos = await self.position_tracker.get_open_position("BTCUSDT")
#             if not pos:
#                 await asyncio.sleep(10)
#                 continue
            
            # Aktuellen Preis holen
#             current_price = await self._get_current_price()
#             if current_price <= 0:
#                 await asyncio.sleep(10)
#                 continue
            
#             await self.position_tracker.update_excursions("BTCUSDT", current_price)
            
#             entry_price = float(pos["entry_price"])
#             side = pos["side"]
#             sl_price = float(pos["stop_loss_price"])
#             tp_price = float(pos["take_profit_price"])
#             quantity = float(pos["quantity"])
            
            # P&L berechnen
#             if side == "long":
#                 pnl_pct = (current_price - entry_price) / entry_price
#             else:
#                 pnl_pct = (entry_price - current_price) / entry_price
            
            # ── TP1 Scaling Check ──────────────────────────────
#             tp1_pct = float(pos.get("take_profit_1_pct", 0.012))
#             tp1_hit = pos.get("tp1_hit", False)
            
#             if not tp1_hit and pnl_pct >= tp1_pct:
#                 tp1_size = float(pos.get("tp1_size_pct", 0.50))
#                 close_qty = round(quantity * tp1_size, 4)
                
#                 self.logger.info(
#                     f"TP1 HIT: {pnl_pct:.2%} >= {tp1_pct:.2%} | "
#                     f"Schließe {tp1_size:.0%} ({close_qty} BTC)"
#                 )
                
#                 await self._partial_close(
#                     pos, close_qty, current_price, "tp1_scaling"
#                 )
                
                # Position State updaten
#                 pos["tp1_hit"] = True
#                 pos["quantity"] = round(quantity - close_qty, 4)
#                 await self.position_tracker.update_position("BTCUSDT", pos)
            
            # ── Phase 1: Fixer SL (vor Breakeven) ──────────────
#             breakeven_pct = float(pos.get("breakeven_trigger_pct", 0.005))
            
#             if pnl_pct < breakeven_pct:
                # Normaler SL/TP Check
#                 if self._is_sl_hit(side, current_price, sl_price):
#                     self.logger.warning(f"STOP-LOSS: {current_price:,.0f}")
#                     await self._close_position("stop_loss", current_price)
#                 elif self._is_tp_hit(side, current_price, tp_price):
#                     self.logger.info(f"TAKE-PROFIT: {current_price:,.0f}")
#                     await self._close_position("take_profit", current_price)
#                 await asyncio.sleep(10)
#                 continue
            
            # ── Phase 2: Breakeven Stop ────────────────────────
#             trailing_trigger_pct = float(pos.get(
#                 "take_profit_1_pct", 0.012))  # Trailing ab TP1
            
#             if pnl_pct < trailing_trigger_pct:
                # Breakeven: SL auf Entry + 0.1%
#                 if side == "long":
#                     be_sl = entry_price * 1.001
#                     if sl_price < be_sl:
#                         pos["stop_loss_price"] = be_sl
#                         await self.position_tracker.update_position(
#                             "BTCUSDT", pos)
#                         self.logger.info(
#                             f"BREAKEVEN: SL → {be_sl:.2f} "
#                             f"(PnL: {pnl_pct:.2%})")
#                 else:
#                     be_sl = entry_price * 0.999
#                     if sl_price > be_sl:
#                         pos["stop_loss_price"] = be_sl
#                         await self.position_tracker.update_position(
#                             "BTCUSDT", pos)
                
                # SL Check mit neuem Breakeven-SL
#                 if self._is_sl_hit(side, current_price, 
#                                    pos["stop_loss_price"]):
#                     await self._close_position("breakeven_stop", 
#                                                current_price)
#                 await asyncio.sleep(10)
#                 continue
            
            # ── Phase 3: ATR Trailing Stop ─────────────────────
#             atr = await self._get_current_atr()
#             if atr <= 0:
#                 atr = current_price * 0.01  # Fallback: 1% ATR
            
#             trailing_multiplier = 2.5  # Chandelier: 2.5* ATR
            
#             if side == "long":
                # Trailing SL = Höchstkurs - ATR * Mult
#                 high_water = float(pos.get("max_favorable_price", 
#                                            current_price))
#                 if current_price > high_water:
#                     high_water = current_price
#                     pos["max_favorable_price"] = high_water
                
#                 new_trailing_sl = high_water - (atr * trailing_multiplier)
                
                # SL kann nur steigen, nie fallen
#                 if new_trailing_sl > float(pos["stop_loss_price"]):
#                     pos["stop_loss_price"] = round(new_trailing_sl, 2)
#                     await self.position_tracker.update_position(
#                         "BTCUSDT", pos)
#                     self.logger.info(
#                         f"TRAILING SL: → {new_trailing_sl:.2f} | "
#                         f"High={high_water:.2f} | "
#                         f"ATR={atr:.0f} | PnL={pnl_pct:.2%}")
                
#                 if current_price <= float(pos["stop_loss_price"]):
#                     await self._close_position("trailing_stop", 
#                                                current_price)
            
#             else:  # short
#                 low_water = float(pos.get("min_favorable_price",
#                                           current_price))
#                 if current_price < low_water:
#                     low_water = current_price
#                     pos["min_favorable_price"] = low_water
                
#                 new_trailing_sl = low_water + (atr * trailing_multiplier)
                
#                 if new_trailing_sl < float(pos["stop_loss_price"]):
#                     pos["stop_loss_price"] = round(new_trailing_sl, 2)
#                     await self.position_tracker.update_position(
#                         "BTCUSDT", pos)
                
#                 if current_price >= float(pos["stop_loss_price"]):
#                     await self._close_position("trailing_stop",
#                                                current_price)
        
#         except Exception as e:
#             self.logger.error(f"Position-Monitor Fehler: {e}")
        
#         await asyncio.sleep(10)  # 10s statt 30s für bessere Reaktion
# ```

### Hilfsmethoden:

# ```python
# def _is_sl_hit(self, side: str, price: float, sl: float) -> bool:
#     return (side == "long" and price <= sl) or \
#            (side == "short" and price >= sl)

# def _is_tp_hit(self, side: str, price: float, tp: float) -> bool:
#     return (side == "long" and price >= tp) or \
#            (side == "short" and price <= tp)

# async def _get_current_price(self) -> float:
#     """Holt aktuellen BTC-Preis (Mark Price > Ticker > 0)."""
#     funding = await self.deps.redis.get_cache("market:funding:BTCUSDT") or {}
#     price = float(funding.get("mark_price", 0))
#     if price <= 0:
#         ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
#         price = float(ticker.get("last_price", 0))
#     return price

# async def _get_current_atr(self) -> float:
#     """ATR aus TA-Snapshot."""
#     ta = await self.deps.redis.get_cache("bruno:ta:snapshot") or {}
#     return float(ta.get("atr_14", 0))

# async def _partial_close(self, pos: dict, quantity: float,
#                           exit_price: float, reason: str):
#     """Schließt einen Teil der Position (TP1 Scaling)."""
#     side = pos["side"]
#     exit_side = "sell" if side == "long" else "buy"
    
#     if self.deps.config.DRY_RUN:
#         trade_id = f"sim_partial_{int(datetime.now().timestamp())}"
#         fee = quantity * exit_price * 0.0004
        
#         self.logger.info(
#             f"🔀 PARTIAL CLOSE (DRY_RUN): {exit_side.upper()} "
#             f"{quantity:.4f} BTCUSDT @ {exit_price:,.2f} | {reason}")
        
        # Portfolio Update für Teilschließung
#         entry_price = float(pos["entry_price"])
#         if side == "long":
#             pnl = (exit_price - entry_price) * quantity
#         else:
#             pnl = (entry_price - exit_price) * quantity
        
#         await self._update_portfolio({
#             "pnl_eur": pnl,
#             "fee_eur": fee,
#         })
#     else:
#         if self.deps.config.LIVE_TRADING_APPROVED:
#             await self.exm.create_market_order(
#                 "BTCUSDT", exit_side, quantity)
# ```

# ---

## Feature 2: TP1/TP2 Daten im Position State speichern

### Problem
# Der CompositeScorer berechnet `tp1_pct, tp2_pct, tp1_size_pct, tp2_size_pct, breakeven_trigger_pct` * aber `_execute_trade()` speichert nur einen einzigen `take_profit_pct` in der Position.

### Fix
# In `_execute_trade()`, beim `open_position()` Call, ergänze die TP-Felder:

# ```python
# await self.position_tracker.open_position(
#     symbol=symbol,
#     side=position_side,
#     entry_price=fill_price,
#     quantity=amount,
#     stop_loss_price=round(sl_price, 2),
#     take_profit_price=round(tp_price, 2),
    # NEU: Scaling-Out Felder
#     take_profit_1_pct=signal.get("take_profit_1_pct", 0.012),
#     take_profit_2_pct=signal.get("take_profit_2_pct", 0.025),
#     tp1_size_pct=signal.get("tp1_size_pct", 0.50),
#     tp2_size_pct=signal.get("tp2_size_pct", 0.50),
#     breakeven_trigger_pct=signal.get("breakeven_trigger_pct", 0.012),
#     tp1_hit=False,
#     max_favorable_price=fill_price,
#     min_favorable_price=fill_price,
    # ... bestehende Felder
#     entry_trade_id=order["id"],
#     grss_at_entry=signal.get("grss", 0.0),
# )
# ```

### In position_tracker.py
# Prüfe ob `open_position()` und `get_open_position()` diese zusätzlichen Felder unterstützen. Sie werden vermutlich als Teil des Redis-Dicts gespeichert * stelle sicher, dass alle Felder durchgereicht werden:

# ```python
# async def open_position(self, symbol, side, entry_price, quantity,
#                         stop_loss_price, take_profit_price,
#                         entry_trade_id=None, **kwargs):
#     """Öffnet eine Position mit allen zusätzlichen Feldern."""
#     position = {
#         "symbol": symbol,
#         "side": side,
#         "entry_price": entry_price,
#         "quantity": quantity,
#         "stop_loss_price": stop_loss_price,
#         "take_profit_price": take_profit_price,
#         "entry_trade_id": entry_trade_id,
#         "opened_at": datetime.now(timezone.utc).isoformat(),
#         **kwargs  # Alle TP1/TP2/Trailing Felder
#     }
    # ... Redis speichern
# ```

### Acceptance Criteria
# - [ ] Position State enthält tp1_pct, tp2_pct, tp1_size_pct, breakeven_trigger_pct
# - [ ] `tp1_hit` Flag wird gesetzt wenn TP1 erreicht wird
# - [ ] `max_favorable_price` / `min_favorable_price` werden bei jedem Check aktualisiert

# ---

## Feature 3: Monitoring Interval von 30s auf 10s

### Begründung
# 30 Sekunden sind zu langsam für einen SL/TP-Monitor bei BTC Perps. In 30 Sekunden kann BTC bei hoher Volatilität 1-2% bewegen. Der Monitor muss mindestens alle 10 Sekunden laufen.

### Fix
# In der neuen `_monitor_position()`: `await asyncio.sleep(10)` statt 30.

# Zusätzlich: Bei extremer Volatilität (ATR > 2% des Preises) auf 5s wechseln:
# ```python
# atr_pct = atr / current_price if current_price > 0 else 0
# sleep_interval = 5 if atr_pct > 0.02 else 10
# await asyncio.sleep(sleep_interval)
# ```

# ---

## Feature 4: Close-Reason Tracking für Debrief

### Begründung
# Für den Trade Debrief (Phase C) ist es kritisch zu wissen WARUM eine Position geschlossen wurde. Aktuell gibt es "stop_loss" und "take_profit". Erweitere um:

# ```python
# Mögliche close_reasons:
# CLOSE_REASONS = [
#     "stop_loss",           # Fixer SL getroffen
#     "breakeven_stop",      # Breakeven SL getroffen
#     "trailing_stop",       # Trailing SL getroffen
#     "take_profit",         # TP2 (oder einziger TP) getroffen
#     "tp1_scaling",         # TP1 Teilschließung (50%)
#     "manual_close",        # Manuell via Telegram/API
#     "daily_drawdown",      # Circuit Breaker
#     "regime_change",       # Marktregime hat sich geändert (future)
# ]
# ```

### Acceptance Criteria
# - [ ] `close_reason` wird in der Position History gespeichert
# - [ ] Telegram-Notification zeigt den genauen Grund
# - [ ] Trade Debrief kann nach Close-Reason filtern

# ---

## Validierung nach Umsetzung

### Test 1: TP1 Scaling
# 1. Simuliere eine Long-Position bei 100.000
# 2. Preis steigt auf 101.200 (TP1 = +1.2%)
# 3. Erwartung: 50% der Position wird geschlossen, Log zeigt "TP1 HIT"
# 4. Restposition läuft weiter mit Trailing Stop

### Test 2: Trailing Stop
# 1. Position bei 100.000, Preis steigt auf 105.000 (+5%)
# 2. ATR = 1000 → Trailing SL = 105.000 - 2500 = 102.500
# 3. Preis fällt auf 102.400
# 4. Erwartung: Position wird bei ~102.500 geschlossen, Grund "trailing_stop"

### Test 3: Phase-Übergänge
# 1. Phase 1 (0% bis +0.5%): Fixer SL unverändert
# 2. Phase 2 (+0.5%): SL wird auf Entry + 0.1% gezogen
# 3. Phase 3 (+1.2%): Trailing beginnt, SL folgt dem Preis

### Metriken nach 48h Laufzeit
# - Durchschnittlicher Trailing-Stop-Gewinn vs. fixer TP-Gewinn
# - Anzahl TP1-Hits vs. TP2-Hits
# - Anzahl Trailing-Stop-Exits vs. SL-Exits# PROMPT 4/5 * Exit Strategy Overhaul: Trailing Stop & TP1/TP2 Scaling

## Kontext
# Bruno hat aktuell nur einen simplen Breakeven-Stop (SL auf Entry + 0.1% nach 0.5% Gewinn) und einen fixen TP. Das CompositeScorer-Signal enthält bereits TP1/TP2 mit Size-Splits, aber der ExecutionAgent ignoriert diese komplett. Ohne Trailing Stop verschenkt Bruno systematisch Gewinn bei starken Moves.

## Scope
# Datei: `backend/app/agents/execution_v4.py` (Position Monitor, Trade Execution)  
# Datei: `backend/app/services/position_tracker.py` (Position State)

# ---

## Feature 1: ATR-basierter Trailing Stop (Chandelier Exit)

### Konzept
# Der Trailing Stop folgt dem Preis mit einem ATR-Abstand. Bei Longs: Trailing Stop = Höchstpreis - (ATR * Multiplikator). Der Stop kann nur nach oben bewegt werden, nie nach unten.

### Phasen des Exits:
# ```
# Phase 1: Fixer SL (Entry bis Breakeven-Trigger)
# Phase 2: Breakeven (SL auf Entry + 0.1%)
# Phase 3: Trailing Stop (SL folgt dem Preis mit ATR-Abstand)
# ```

### Implementation
# In `execution_v4.py`, ersetze die bestehende `_monitor_position()` Methode:

# ```python
# async def _monitor_position(self):
#     """
#     Position Monitor mit 3-Phasen Exit-Management.
    
#     Phase 1: Fixer SL/TP (0% bis +0.5%)
#     Phase 2: Breakeven Stop (+0.5% bis +1.2%)
#     Phase 3: ATR Trailing Stop (ab +1.2%)
    
#     TP1 Scaling: Bei TP1 wird 50% der Position geschlossen.
#     TP2: Restposition wird bei TP2 oder via Trailing Stop geschlossen.
#     """
#     self.logger.info("Position-Monitor v2 gestartet (10s Intervall).")
    
#     while self.state.running:
#         try:
#             pos = await self.position_tracker.get_open_position("BTCUSDT")
#             if not pos:
#                 await asyncio.sleep(10)
#                 continue
            
            # Aktuellen Preis holen
#             current_price = await self._get_current_price()
#             if current_price <= 0:
#                 await asyncio.sleep(10)
#                 continue
            
#             await self.position_tracker.update_excursions("BTCUSDT", current_price)
            
#             entry_price = float(pos["entry_price"])
#             side = pos["side"]
#             sl_price = float(pos["stop_loss_price"])
#             tp_price = float(pos["take_profit_price"])
#             quantity = float(pos["quantity"])
            
            # P&L berechnen
#             if side == "long":
#                 pnl_pct = (current_price - entry_price) / entry_price
#             else:
#                 pnl_pct = (entry_price - current_price) / entry_price
            
            # ── TP1 Scaling Check ──────────────────────────────
#             tp1_pct = float(pos.get("take_profit_1_pct", 0.012))
#             tp1_hit = pos.get("tp1_hit", False)
            
#             if not tp1_hit and pnl_pct >= tp1_pct:
#                 tp1_size = float(pos.get("tp1_size_pct", 0.50))
#                 close_qty = round(quantity * tp1_size, 4)
                
#                 self.logger.info(
#                     f"TP1 HIT: {pnl_pct:.2%} >= {tp1_pct:.2%} | "
#                     f"Schließe {tp1_size:.0%} ({close_qty} BTC)"
#                 )
                
#                 await self._partial_close(
#                     pos, close_qty, current_price, "tp1_scaling"
#                 )
                
                # Position State updaten
#                 pos["tp1_hit"] = True
#                 pos["quantity"] = round(quantity - close_qty, 4)
#                 await self.position_tracker.update_position("BTCUSDT", pos)
            
            # ── Phase 1: Fixer SL (vor Breakeven) ──────────────
#             breakeven_pct = float(pos.get("breakeven_trigger_pct", 0.005))
            
#             if pnl_pct < breakeven_pct:
                # Normaler SL/TP Check
#                 if self._is_sl_hit(side, current_price, sl_price):
#                     self.logger.warning(f"STOP-LOSS: {current_price:,.0f}")
#                     await self._close_position("stop_loss", current_price)
#                 elif self._is_tp_hit(side, current_price, tp_price):
#                     self.logger.info(f"TAKE-PROFIT: {current_price:,.0f}")
#                     await self._close_position("take_profit", current_price)
#                 await asyncio.sleep(10)
#                 continue
            
            # ── Phase 2: Breakeven Stop ────────────────────────
#             trailing_trigger_pct = float(pos.get(
#                 "take_profit_1_pct", 0.012))  # Trailing ab TP1
            
#             if pnl_pct < trailing_trigger_pct:
                # Breakeven: SL auf Entry + 0.1%
#                 if side == "long":
#                     be_sl = entry_price * 1.001
#                     if sl_price < be_sl:
#                         pos["stop_loss_price"] = be_sl
#                         await self.position_tracker.update_position(
#                             "BTCUSDT", pos)
#                         self.logger.info(
#                             f"BREAKEVEN: SL → {be_sl:.2f} "
#                             f"(PnL: {pnl_pct:.2%})")
#                 else:
#                     be_sl = entry_price * 0.999
#                     if sl_price > be_sl:
#                         pos["stop_loss_price"] = be_sl
#                         await self.position_tracker.update_position(
#                             "BTCUSDT", pos)
                
                # SL Check mit neuem Breakeven-SL
#                 if self._is_sl_hit(side, current_price, 
#                                    pos["stop_loss_price"]):
#                     await self._close_position("breakeven_stop", 
#                                                current_price)
#                 await asyncio.sleep(10)
#                 continue
            
            # ── Phase 3: ATR Trailing Stop ─────────────────────
#             atr = await self._get_current_atr()
#             if atr <= 0:
#                 atr = current_price * 0.01  # Fallback: 1% ATR
            
#             trailing_multiplier = 2.5  # Chandelier: 2.5* ATR
            
#             if side == "long":
                # Trailing SL = Höchstkurs - ATR * Mult
#                 high_water = float(pos.get("max_favorable_price", 
#                                            current_price))
#                 if current_price > high_water:
#                     high_water = current_price
#                     pos["max_favorable_price"] = high_water
                
#                 new_trailing_sl = high_water - (atr * trailing_multiplier)
                
                # SL kann nur steigen, nie fallen
#                 if new_trailing_sl > float(pos["stop_loss_price"]):
#                     pos["stop_loss_price"] = round(new_trailing_sl, 2)
#                     await self.position_tracker.update_position(
#                         "BTCUSDT", pos)
#                     self.logger.info(
#                         f"TRAILING SL: → {new_trailing_sl:.2f} | "
#                         f"High={high_water:.2f} | "
#                         f"ATR={atr:.0f} | PnL={pnl_pct:.2%}")
                
#                 if current_price <= float(pos["stop_loss_price"]):
#                     await self._close_position("trailing_stop", 
#                                                current_price)
            
#             else:  # short
#                 low_water = float(pos.get("min_favorable_price",
#                                           current_price))
#                 if current_price < low_water:
#                     low_water = current_price
#                     pos["min_favorable_price"] = low_water
                
#                 new_trailing_sl = low_water + (atr * trailing_multiplier)
                
#                 if new_trailing_sl < float(pos["stop_loss_price"]):
#                     pos["stop_loss_price"] = round(new_trailing_sl, 2)
#                     await self.position_tracker.update_position(
#                         "BTCUSDT", pos)
                
#                 if current_price >= float(pos["stop_loss_price"]):
#                     await self._close_position("trailing_stop",
#                                                current_price)
        
#         except Exception as e:
#             self.logger.error(f"Position-Monitor Fehler: {e}")
        
#         await asyncio.sleep(10)  # 10s statt 30s für bessere Reaktion
# ```

### Hilfsmethoden:

# ```python
# def _is_sl_hit(self, side: str, price: float, sl: float) -> bool:
#     return (side == "long" and price <= sl) or \
#            (side == "short" and price >= sl)

# def _is_tp_hit(self, side: str, price: float, tp: float) -> bool:
#     return (side == "long" and price >= tp) or \
#            (side == "short" and price <= tp)

# async def _get_current_price(self) -> float:
#     """Holt aktuellen BTC-Preis (Mark Price > Ticker > 0)."""
#     funding = await self.deps.redis.get_cache("market:funding:BTCUSDT") or {}
#     price = float(funding.get("mark_price", 0))
#     if price <= 0:
#         ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
#         price = float(ticker.get("last_price", 0))
#     return price

# async def _get_current_atr(self) -> float:
#     """ATR aus TA-Snapshot."""
#     ta = await self.deps.redis.get_cache("bruno:ta:snapshot") or {}
#     return float(ta.get("atr_14", 0))

# async def _partial_close(self, pos: dict, quantity: float,
#                           exit_price: float, reason: str):
#     """Schließt einen Teil der Position (TP1 Scaling)."""
#     side = pos["side"]
#     exit_side = "sell" if side == "long" else "buy"
    
#     if self.deps.config.DRY_RUN:
#         trade_id = f"sim_partial_{int(datetime.now().timestamp())}"
#         fee = quantity * exit_price * 0.0004
        
#         self.logger.info(
#             f"🔀 PARTIAL CLOSE (DRY_RUN): {exit_side.upper()} "
#             f"{quantity:.4f} BTCUSDT @ {exit_price:,.2f} | {reason}")
        
        # Portfolio Update für Teilschließung
#         entry_price = float(pos["entry_price"])
#         if side == "long":
#             pnl = (exit_price - entry_price) * quantity
#         else:
#             pnl = (entry_price - exit_price) * quantity
        
#         await self._update_portfolio({
#             "pnl_eur": pnl,
#             "fee_eur": fee,
#         })
#     else:
#         if self.deps.config.LIVE_TRADING_APPROVED:
#             await self.exm.create_market_order(
#                 "BTCUSDT", exit_side, quantity)
# ```

# ---

## Feature 2: TP1/TP2 Daten im Position State speichern

### Problem
# Der CompositeScorer berechnet `tp1_pct, tp2_pct, tp1_size_pct, tp2_size_pct, breakeven_trigger_pct` * aber `_execute_trade()` speichert nur einen einzigen `take_profit_pct` in der Position.

### Fix
# In `_execute_trade()`, beim `open_position()` Call, ergänze die TP-Felder:

# ```python
# await self.position_tracker.open_position(
#     symbol=symbol,
#     side=position_side,
#     entry_price=fill_price,
#     quantity=amount,
#     stop_loss_price=round(sl_price, 2),
#     take_profit_price=round(tp_price, 2),
    # NEU: Scaling-Out Felder
#     take_profit_1_pct=signal.get("take_profit_1_pct", 0.012),
#     take_profit_2_pct=signal.get("take_profit_2_pct", 0.025),
#     tp1_size_pct=signal.get("tp1_size_pct", 0.50),
#     tp2_size_pct=signal.get("tp2_size_pct", 0.50),
#     breakeven_trigger_pct=signal.get("breakeven_trigger_pct", 0.012),
#     tp1_hit=False,
#     max_favorable_price=fill_price,
#     min_favorable_price=fill_price,
    # ... bestehende Felder
#     entry_trade_id=order["id"],
#     grss_at_entry=signal.get("grss", 0.0),
# )
# ```

### In position_tracker.py
# Prüfe ob `open_position()` und `get_open_position()` diese zusätzlichen Felder unterstützen. Sie werden vermutlich als Teil des Redis-Dicts gespeichert * stelle sicher, dass alle Felder durchgereicht werden:

# ```python
# async def open_position(self, symbol, side, entry_price, quantity,
#                         stop_loss_price, take_profit_price,
#                         entry_trade_id=None, **kwargs):
#     """Öffnet eine Position mit allen zusätzlichen Feldern."""
#     position = {
#         "symbol": symbol,
#         "side": side,
#         "entry_price": entry_price,
#         "quantity": quantity,
#         "stop_loss_price": stop_loss_price,
#         "take_profit_price": take_profit_price,
#         "entry_trade_id": entry_trade_id,
#         "opened_at": datetime.now(timezone.utc).isoformat(),
#         **kwargs  # Alle TP1/TP2/Trailing Felder
#     }
    # ... Redis speichern
# ```

### Acceptance Criteria
# - [ ] Position State enthält tp1_pct, tp2_pct, tp1_size_pct, breakeven_trigger_pct
# - [ ] `tp1_hit` Flag wird gesetzt wenn TP1 erreicht wird
# - [ ] `max_favorable_price` / `min_favorable_price` werden bei jedem Check aktualisiert

# ---

## Feature 3: Monitoring Interval von 30s auf 10s

### Begründung
# 30 Sekunden sind zu langsam für einen SL/TP-Monitor bei BTC Perps. In 30 Sekunden kann BTC bei hoher Volatilität 1-2% bewegen. Der Monitor muss mindestens alle 10 Sekunden laufen.

### Fix
# In der neuen `_monitor_position()`: `await asyncio.sleep(10)` statt 30.

# Zusätzlich: Bei extremer Volatilität (ATR > 2% des Preises) auf 5s wechseln:
# ```python
# atr_pct = atr / current_price if current_price > 0 else 0
# sleep_interval = 5 if atr_pct > 0.02 else 10
# await asyncio.sleep(sleep_interval)
# ```

# ---

## Feature 4: Close-Reason Tracking für Debrief

### Begründung
# Für den Trade Debrief (Phase C) ist es kritisch zu wissen WARUM eine Position geschlossen wurde. Aktuell gibt es "stop_loss" und "take_profit". Erweitere um:

# ```python
# Mögliche close_reasons:
# CLOSE_REASONS = [
#     "stop_loss",           # Fixer SL getroffen
#     "breakeven_stop",      # Breakeven SL getroffen
#     "trailing_stop",       # Trailing SL getroffen
#     "take_profit",         # TP2 (oder einziger TP) getroffen
#     "tp1_scaling",         # TP1 Teilschließung (50%)
#     "manual_close",        # Manuell via Telegram/API
#     "daily_drawdown",      # Circuit Breaker
#     "regime_change",       # Marktregime hat sich geändert (future)
# ]
# ```

### Acceptance Criteria
# - [ ] `close_reason` wird in der Position History gespeichert
# - [ ] Telegram-Notification zeigt den genauen Grund
# - [ ] Trade Debrief kann nach Close-Reason filtern

# ---

## Validierung nach Umsetzung

### Test 1: TP1 Scaling
# 1. Simuliere eine Long-Position bei 100.000
# 2. Preis steigt auf 101.200 (TP1 = +1.2%)
# 3. Erwartung: 50% der Position wird geschlossen, Log zeigt "TP1 HIT"
# 4. Restposition läuft weiter mit Trailing Stop

### Test 2: Trailing Stop
# 1. Position bei 100.000, Preis steigt auf 105.000 (+5%)
# 2. ATR = 1000 → Trailing SL = 105.000 - 2500 = 102.500
# 3. Preis fällt auf 102.400
# 4. Erwartung: Position wird bei ~102.500 geschlossen, Grund "trailing_stop"

### Test 3: Phase-Übergänge
# 1. Phase 1 (0% bis +0.5%): Fixer SL unverändert
# 2. Phase 2 (+0.5%): SL wird auf Entry + 0.1% gezogen
# 3. Phase 3 (+1.2%): Trailing beginnt, SL folgt dem Preis

### Metriken nach 48h Laufzeit
# - Durchschnittlicher Trailing-Stop-Gewinn vs. fixer TP-Gewinn
# - Anzahl TP1-Hits vs. TP2-Hits
# - Anzahl Trailing-Stop-Exits vs. SL-Exits
import httpx
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MarketDataCollector:
    """Marktdaten-Sammler für Bruno Trading Bot.
    
    Holt automatisch alle wichtigen Marktdaten von Binance
    und speichert sie in Redis für die Agenten.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.base_url = "https://api.binance.com"
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def collect_all_data(self, symbol: str = "BTCUSDT"):
        """Sammelt alle Marktdaten und speichert sie in Redis."""
        try:
            # Parallel fetch aller Daten
            tasks = [
                self._fetch_ticker(symbol),
                self._fetch_klines(symbol),
                self._fetch_orderbook(symbol),
                self._fetch_funding_rate(symbol),
                self._fetch_open_interest(symbol),
                self._fetch_liquidations(symbol)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Daten in Redis speichern
            await self._save_to_redis(symbol, results)
            
            logger.info(f"Marktdaten für {symbol} aktualisiert")
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei Datensammlung: {e}")
            return False

    async def _fetch_ticker(self, symbol: str) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/ticker/price?symbol={symbol}")
            response.raise_for_status()
            return {"ticker": response.json()}
        except Exception as e:
            logger.error(f"Ticker fetch error: {e}")
            return {"ticker": {}}

    async def _fetch_klines(self, symbol: str, limit: int = 500) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}")
            response.raise_for_status()
            return {"klines": response.json()}
        except Exception as e:
            logger.error(f"Klines fetch error: {e}")
            return {"klines": []}

    async def _fetch_orderbook(self, symbol: str, limit: int = 100) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/depth?symbol={symbol}&limit={limit}")
            response.raise_for_status()
            data = response.json()
            
            # Orderbook Metriken berechnen
            bids_volume = sum(float(bid[0]) * float(bid[1]) for bid in data.get("bids", []))
            asks_volume = sum(float(ask[0]) * float(ask[1]) for ask in data.get("asks", []))
            imbalance_ratio = bids_volume / asks_volume if asks_volume > 0 else 1.0
            
            return {
                "orderbook": data,
                "bids_volume": bids_volume,
                "asks_volume": asks_volume,
                "imbalance_ratio": imbalance_ratio
            }
        except Exception as e:
            logger.error(f"Orderbook fetch error: {e}")
            return {"orderbook": {}, "bids_volume": 0, "asks_volume": 0, "imbalance_ratio": 1.0}

    async def _fetch_funding_rate(self, symbol: str) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/premiumIndex?symbol={symbol}")
            response.raise_for_status()
            return {"funding_rate": response.json()}
        except Exception as e:
            logger.error(f"Funding rate fetch error: {e}")
            return {"funding_rate": {}}

    async def _fetch_open_interest(self, symbol: str) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/openInterest?symbol={symbol}")
            response.raise_for_status()
            return {"open_interest": response.json()}
        except Exception as e:
            logger.error(f"Open interest fetch error: {e}")
            return {"open_interest": {}}

    async def _fetch_liquidations(self, symbol: str, limit: int = 100) -> dict:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/fapi/v1/allForceOrders?symbol={symbol}&limit={limit}")
            response.raise_for_status()
            return {"liquidations": response.json()}
        except Exception as e:
            logger.error(f"Liquidations fetch error: {e}")
            return {"liquidations": []}

    async def _save_to_redis(self, symbol: str, results: list[dict]):
        """Speichert alle Daten in Redis."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Einzelne Daten speichern
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Result error: {result}")
                continue
                
            for key, data in result.items():
                redis_key = f"market:{key}:{symbol}"
                
                if key == "ticker":
                    # Ticker mit kurzer TTL
                    await self.redis.set_cache(redis_key, data, ttl=10)
                elif key == "klines":
                    # Klines für Technical Analysis
                    klines_data = {
                        "symbol": symbol,
                        "klines": data,
                        "timestamp": timestamp,
                        "count": len(data)
                    }
                    await self.redis.set_cache(f"bruno:ta:klines:{symbol}", klines_data, ttl=60)
                elif key == "orderbook":
                    # Orderbook Daten
                    ob_data = {
                        "symbol": symbol,
                        "bids": data.get("orderbook", {}).get("bids", []),
                        "asks": data.get("orderbook", {}).get("asks", []),
                        "bids_volume": data.get("bids_volume", 0),
                        "asks_volume": data.get("asks_volume", 0),
                        "imbalance_ratio": data.get("imbalance_ratio", 1.0),
                        "timestamp": timestamp
                    }
                    await self.redis.set_cache(redis_key, ob_data, ttl=5)
                    
                    # OFI Tick für QuantAgent
                    ofi_tick = {
                        "t": timestamp,
                        "r": round(data.get("imbalance_ratio", 1.0), 4)
                    }
                    pipe = self.redis.redis.pipeline()
                    pipe.lpush(f"market:ofi:ticks", str(ofi_tick))
                    pipe.ltrim(f"market:ofi:ticks", 0, 299)
                    await pipe.execute()
                elif key == "funding_rate":
                    # Funding Rate
                    await self.redis.set_cache(redis_key, data, ttl=300)
                elif key == "open_interest":
                    # Open Interest
                    await self.redis.set_cache(redis_key, data, ttl=300)
                elif key == "liquidations":
                    # Liquidations
                    liq_data = {
                        "symbol": symbol,
                        "liquidations": data,
                        "timestamp": timestamp,
                        "count": len(data)
                    }
                    await self.redis.set_cache(f"market:liquidations:{symbol}", liq_data, ttl=60)

        # Zusammengefasste Market Data
        market_snapshot = {
            "symbol": symbol,
            "timestamp": timestamp,
            "ticker": results[0].get("ticker", {}) if not isinstance(results[0], Exception) else {},
            "orderbook_imbalance": results[2].get("imbalance_ratio", 1.0) if not isinstance(results[2], Exception) else 1.0,
            "funding_rate": results[3].get("funding_rate", {}).get("fundingRate", 0) if not isinstance(results[3], Exception) else 0,
            "open_interest": results[4].get("open_interest", {}).get("openInterest", "0") if not isinstance(results[4], Exception) else "0",
            "liquidation_count": len(results[5].get("liquidations", [])) if not isinstance(results[5], Exception) else 0
        }
        
        await self.redis.set_cache(f"market:snapshot:{symbol}", market_snapshot, ttl=30)

    async def health_check(self) -> bool:
        """Prüft ob Binance API erreichbar ist."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/v3/time")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Binance health check failed: {e}")
            return False
