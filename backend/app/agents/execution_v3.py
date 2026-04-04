from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import AuthenticatedExchangeClient
from app.schemas.models import TradeAuditLog
from sqlalchemy import text
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

class ExecutionAgentV3(StreamingAgent):
    """
    Phase D: Zero-Latency Execution Engine mit PositionTracker.

    Fixes gegenüber vorheriger Version:
    - PositionTracker Guard: kein Double-Entry mehr möglich
    - _open_position() nach Trade — Position wird jetzt tatsächlich gesetzt
    - _close_position() ruft NICHT mehr _execute_trade() rekursiv auf
    - P&L Berechnung ist im PositionTracker korrekt (Entry vs Exit)
    - Monitor läuft alle 30s (war 2s — unnötiger Redis-Stress)
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("execution", deps)
        self.exm = AuthenticatedExchangeClient(redis=deps.redis)
        self._local_veto_active = True
        self._last_veto_reason = "Initialisierung..."

        # ── ATR Calculator ───────────────────────────────────────
        from app.services.atr_calculator import ATRCalculator
        self.atr_calc = ATRCalculator(deps.db_session_factory)
        self._last_atr_update: float = 0.0
        self._atr_update_interval: float = 3600.0

        # ── Position Tracker (Phase D) ───────────────────────────
        from app.services.position_tracker import PositionTracker
        self.position_tracker = PositionTracker(
            redis=deps.redis,
            db_session_factory=deps.db_session_factory,
        )

        self._portfolio_initialized = False
        
        # v2 Breakeven Stop
        self._breakeven_enabled = True
        self._breakeven_trigger_pct = float(self._load_config_value("BREAKEVEN_TRIGGER_PCT", 0.005))

    def _load_config_value(self, key: str, default: float) -> float:
        """Lädt einen Wert aus config.json. Fallback auf default wenn nicht gefunden."""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        try:
            with open(config_path, "r") as f:
                value = json.load(f).get(key, default)
                if isinstance(value, bool):
                    return 1.0 if value else 0.0
                return float(value)
        except Exception:
            return default

    async def setup(self) -> None:
        self.logger.info("ExecutionAgentV3 (Zero-Latency) gestartet.")
        # Startzustand aus Redis laden
        veto_raw = await self.deps.redis.redis.get("bruno:veto:state")
        if veto_raw:
            data = json.loads(veto_raw)
            self._local_veto_active = data.get("Veto_Active", True)
            self._last_veto_reason = data.get("Reason", "Redis Cache")

        # Simulated Portfolio initialisieren (DRY_RUN)
        if self.deps.config.DRY_RUN:
            portfolio = await self.deps.redis.get_cache(
                "bruno:portfolio:state"
            )
            if not portfolio:
                # Erster Start — Kapital aus Config
                initial_capital = self.deps.config.SIMULATED_CAPITAL_EUR
                await self.deps.redis.set_cache(
                    "bruno:portfolio:state",
                    {
                        "capital_eur": initial_capital,
                        "initial_capital_eur": initial_capital,
                        "realized_pnl_eur": 0.0,
                        "total_fees_eur": 0.0,
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "max_drawdown_eur": 0.0,
                        "peak_capital_eur": initial_capital,
                        "daily_pnl_eur": 0.0,
                        "trade_pnl_history_eur": [],
                        "trade_fee_history_eur": [],
                        "daily_reset_date": datetime.now(timezone.utc).date().isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                self.logger.info(
                    f"Simulated Portfolio initialisiert: {initial_capital:.2f} EUR"
                )
            else:
                self.logger.info(
                    f"Simulated Portfolio geladen: "
                    f"{portfolio.get('capital_eur', 0):.2f} EUR "
                    f"(P&L: {portfolio.get('realized_pnl_eur', 0):.2f} EUR)"
                )

    async def _listen_to_risk_veto(self):
        """Hintergrund-Task: Aktualisiert den lokalen RAM-State (0ms Check)."""
        pubsub = await self.deps.redis.subscribe_channel("bruno:pubsub:veto")
        self.logger.info("Veto-Listener aktiv.")
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    data = json.loads(msg['data'])
                    self._local_veto_active = data.get("Veto_Active", True)
                    self._last_veto_reason = data.get("Reason", "PubSub Update")
                    if self._local_veto_active:
                        self.logger.warning(f"LOCAL VETO AKTIV: {self._last_veto_reason}")
            except Exception as e:
                self.logger.error(f"Veto-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def _execute_trade(self, signal: Dict):
        """
        Kritischer Pfad: 0ms RAM-Check → Position-Guard → Order-Firing → Position-Open.

        Änderungen Phase D:
        - PositionTracker Guard: verhindert Double-Entry
        - Nach erfolgreicher Order: position_tracker.open_position()
        - Exit-Signale (reason=stop_loss/take_profit) gehen über _fire_exit_order()
          und NICHT mehr durch diesen Pfad — kein rekursiver Loop mehr
        """
        start_exec = time.perf_counter()

        # 1. RAM-CHECK (0ms Latenz)
        if self._local_veto_active:
            self.logger.info(f"Signal blockiert durch Veto: {self._last_veto_reason}")
            return

        learning_mode_active = (
            self.deps.config.DRY_RUN
            and self._load_config_value("LEARNING_MODE_ENABLED", 0.0) > 0
        )
        trade_mode = "learning" if learning_mode_active else "production"

        self.logger.info(
            f"Trade Mode: {trade_mode.upper()} | "
            f"DRY_RUN={self.deps.config.DRY_RUN} | "
            f"Learning={learning_mode_active}"
        )

        # ── Preis-Validierung ──────────────────────────────────
        signal_price = signal.get("price", 0.0)
        if signal_price <= 0:
            self.logger.error(
                f"ABBRUCH: Signal ohne validen Preis. Signal: {signal}. "
                f"Prüfe ob QuantAgent/LLM-Cascade 'price' im Signal-Dict hat."
            )
            return

        symbol = signal.get("symbol")
        side = signal.get("side")
        amount = signal.get("amount", 0.01)

        if not symbol or not isinstance(symbol, str):
            self.logger.error(f"ABBRUCH: Ungültiges Symbol: {signal}")
            return

        if side not in {"buy", "sell"}:
            self.logger.error(f"ABBRUCH: Ungültige Seite: {signal}")
            return

        if amount <= 0:
            self.logger.error(f"ABBRUCH: Ungültige Menge: {signal}")
            return

        # ── POSITION GUARD (Phase D) ───────────────────────────
        # Kein neuer Trade wenn bereits eine Position offen ist.
        # Ausnahme: Signal kommt mit reason=close (dann _fire_exit_order nutzen)
        if await self.position_tracker.has_open_position(symbol):
            self.logger.info(
                f"Signal ignoriert — Position für {symbol} bereits offen. "
                f"PositionTracker Guard aktiv. Signal: {side}"
            )
            return

        # Daily Drawdown Limit Check (NEU: liest bruno:risk:daily_block von RiskAgent)
        daily_block = await self.deps.redis.get_cache("bruno:risk:daily_block")
        if daily_block and daily_block.get("active"):
            self.logger.warning(f"ABBRUCH: Daily Drawdown Block aktiv - {daily_block.get('reason', 'Unbekannt')}")
            return

        # ── ATR aktualisieren (stündlich) ──────────────────────
        now = time.time()
        if now - self._last_atr_update > self._atr_update_interval:
            self._last_atr_update = now
            await self.atr_calc.calculate_atr(symbol)
            await self.atr_calc.calculate_atr_baseline(symbol)

        # ── Volatility-adjusted Position Sizing ───────────────
        vol_multiplier = self.atr_calc.get_volatility_multiplier()
        base_sl_pct = 0.010
        dynamic_sl_pct = self.atr_calc.get_dynamic_stop_loss(base_sl_pct, signal_price)

        portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
        capital = portfolio.get("capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR)

        base_risk_eur = capital * 0.02
        adjusted_risk_eur = base_risk_eur * vol_multiplier
        position_size_btc = max(
            0.001,
            min(
                adjusted_risk_eur / signal_price,
                (capital * self.deps.config.MAX_LEVERAGE) / signal_price
            )
        )
        amount = max(0.001, min(amount, position_size_btc))

        if vol_multiplier < 1.0:
            self.logger.info(
                f"ATR-Anpassung: Multiplikator={vol_multiplier:.2f} | "
                f"Position={position_size_btc:.4f} BTC | "
                f"Dynamic SL={dynamic_sl_pct:.2%}"
            )

        # 2. IMMEDIATE ORDER FIRING (OR SHADOW SIMULATION)
        try:
            if self.deps.config.DRY_RUN:
                exec_latency = (time.perf_counter() - start_exec) * 1000
                simulated_fee = (amount * signal_price) * 0.0004

                simulated_fill_price = signal_price * 1.0001 if side == "buy" else signal_price * 0.9999

                self.logger.info(
                    f"🚧 SIMULIERTER TRADE (DRY_RUN): {side.upper()} "
                    f"{amount:.4f} {symbol} @ {simulated_fill_price:,.2f}"
                )

                order = {
                    "id": f"sim_{int(datetime.now().timestamp())}",
                    "price": simulated_fill_price,
                    "amount": amount,
                    "cost": amount * simulated_fill_price,
                    "fee": simulated_fee,
                    "status": "simulated"
                }

            else:
                # ECHTE ORDER — nur wenn DRY_RUN=False UND LIVE_TRADING_APPROVED=True
                if not self.deps.config.LIVE_TRADING_APPROVED:
                    self.logger.error(
                        "ABBRUCH: LIVE_TRADING_APPROVED=False. "
                        "Setze in .env auf True nach bestandenem Backtest."
                    )
                    return

                order = await self.exm.create_order(symbol, side, amount)
                exec_latency = (time.perf_counter() - start_exec) * 1000
                self.logger.info(
                    f"✅ ECHTE ORDER GEFEUERT: {side.upper()} "
                    f"{amount:.4f} {symbol} in {exec_latency:.1f}ms"
                )

            exec_latency = (time.perf_counter() - start_exec) * 1000

            # ── POSITION ÖFFNEN (Phase D) ──────────────────────
            # Jetzt wo die Order durch ist, Position in Tracker eintragen
            fill_price = order["price"]
            position_side = "long" if side == "buy" else "short"

            # SL/TP aus Signal (LLM-Cascade) oder ATR-Default
            sl_pct = signal.get("stop_loss_pct", dynamic_sl_pct)
            tp_pct = signal.get("take_profit_pct", dynamic_sl_pct * 2.0)

            if position_side == "long":
                sl_price = fill_price * (1 - sl_pct)
                tp_price = fill_price * (1 + tp_pct)
            else:
                sl_price = fill_price * (1 + sl_pct)
                tp_price = fill_price * (1 - tp_pct)

            try:
                await self.position_tracker.open_position(
                    symbol=symbol,
                    side=position_side,
                    entry_price=fill_price,
                    quantity=amount,
                    stop_loss_price=round(sl_price, 2),
                    take_profit_price=round(tp_price, 2),
                    entry_trade_id=order["id"],
                    # Phase C Felder — aus Signal wenn vorhanden
                    grss_at_entry=signal.get("grss", 0.0),
                    layer1_output=signal.get("layer1_output"),
                    layer2_output=signal.get("layer2_output"),
                    layer3_output=signal.get("layer3_output"),
                    regime=signal.get("regime", "unknown"),
                )
            except ValueError as ve:
                # Guard hat angeschlagen (race condition) — kein Problem
                self.logger.warning(f"PositionTracker Guard (race): {ve}")

            # Async Audit
            await self._audit_trade(signal, order, exec_latency, trade_mode=trade_mode)

        except Exception as e:
            self.logger.error(f"KRITISCHER FEHLER BEI ORDER-AUSFÜHRUNG: {e}")

    async def _audit_trade(self, signal: Dict, order: Dict, latency: float, trade_mode: str = "production"):
        """Speichert den Audit-Trail in der DB (nachdem die Order raus ist)."""
        try:
            async with self.deps.db_session_factory() as session:
                log = TradeAuditLog(
                    id=order.get('id', str(datetime.now().timestamp())),
                    timestamp=datetime.now(timezone.utc),
                    symbol=signal.get('symbol'),
                    action=signal.get('side'),
                    price=order.get('price', 0.0), # Actual / Simulated price
                    quantity=order.get('amount', 0.0),
                    total=order.get('cost', 0.0),
                    status=order.get('status', 'filled'),
                    
                    # Enhanced Telemetry (Phase 7.5 Audit)
                    latency_exec_ms=latency,
                    signal_price=signal.get('price', 0.0),
                    simulated_fill_price=order.get('price', 0.0),
                    slippage_bps=((order.get('price', 0.0) / signal.get('price', 1.0)) - 1) * 10000,
                    simulated_fee_usdt=order.get('fee', 0.0), # 0.04% for simulated, or real fee
                    latency_ms=latency, # Total processing latency
                    trade_mode=trade_mode,
                )
                session.add(log)
                await session.commit()
                
            self.logger.info(f"Audit completed for order {order.get('id')} | latency={latency:.1f}ms")
                
        except Exception as e:
            self.logger.error(f"Audit-Log Fehler: {e}")

    async def _update_portfolio(self, trade_result: dict) -> None:
        """
        Aktualisiert das simulierte Portfolio nach einem Trade.
        Berechnet P&L, Drawdown und Daily Loss Limit.
        """
        if not self.deps.config.DRY_RUN:
            return

        portfolio = await self.deps.redis.get_cache(
            "bruno:portfolio:state"
        ) or {}

        pnl_eur = trade_result.get("pnl_eur", 0.0)
        fee_eur = trade_result.get("fee_eur", 0.0)
        net_pnl = pnl_eur - fee_eur

        # Kapital aktualisieren
        portfolio["capital_eur"] = portfolio.get(
            "capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR
        ) + net_pnl
        portfolio["realized_pnl_eur"] = portfolio.get(
            "realized_pnl_eur", 0.0
        ) + net_pnl
        portfolio["total_fees_eur"] = portfolio.get(
            "total_fees_eur", 0.0
        ) + fee_eur
        portfolio["total_trades"] = portfolio.get("total_trades", 0) + 1

        # Historie für Profit-Factor / Trend-Analyse
        pnl_history = portfolio.get("trade_pnl_history_eur", [])
        fee_history = portfolio.get("trade_fee_history_eur", [])
        pnl_history.append(net_pnl)
        fee_history.append(fee_eur)
        portfolio["trade_pnl_history_eur"] = pnl_history[-200:]
        portfolio["trade_fee_history_eur"] = fee_history[-200:]

        if net_pnl > 0:
            portfolio["winning_trades"] = portfolio.get(
                "winning_trades", 0
            ) + 1
        else:
            portfolio["losing_trades"] = portfolio.get(
                "losing_trades", 0
            ) + 1

        # Peak + Drawdown
        current = portfolio["capital_eur"]
        peak = portfolio.get(
            "peak_capital_eur",
            self.deps.config.SIMULATED_CAPITAL_EUR
        )
        if current > peak:
            portfolio["peak_capital_eur"] = current
        else:
            drawdown = peak - current
            if drawdown > portfolio.get("max_drawdown_eur", 0.0):
                portfolio["max_drawdown_eur"] = drawdown

        # Daily P&L (Reset bei neuem Tag)
        today = datetime.now(timezone.utc).date().isoformat()
        if portfolio.get("daily_reset_date") != today:
            portfolio["daily_pnl_eur"] = 0.0
            portfolio["daily_reset_date"] = today
        portfolio["daily_pnl_eur"] = portfolio.get(
            "daily_pnl_eur", 0.0
        ) + net_pnl

        # Daily Loss Limit prüfen
        initial = portfolio.get(
            "initial_capital_eur",
            self.deps.config.SIMULATED_CAPITAL_EUR
        )
        daily_limit = initial * self.deps.config.DAILY_LOSS_LIMIT_PCT
        if portfolio["daily_pnl_eur"] < -daily_limit:
            self.logger.warning(
                f"⛔ DAILY LOSS LIMIT ERREICHT: "
                f"{portfolio['daily_pnl_eur']:.2f} EUR "
                f"(Limit: -{daily_limit:.2f} EUR)"
            )
            await self.deps.redis.set_cache(
                "bruno:portfolio:daily_limit_hit",
                {"hit": True, "date": today},
                ttl=86400
            )

        portfolio["last_update"] = datetime.now(timezone.utc).isoformat()
        await self.deps.redis.set_cache("bruno:portfolio:state", portfolio)

    async def _update_profit_factor(self) -> None:
        """
        Berechnet Profit Factor live aus der realisierten Trade-P&L-Historie.

        PF = Gross Profit / Gross Loss (inkl. Fees)
        PF > 1.5 = gut
        PF > 2.0 = sehr gut
        PF < 1.2 = Alarm
        PF < 1.0 = Strategie verliert Geld

        Wird nach jedem Trade aktualisiert.
        Drei Varianten: gesamt, rolling 20, rolling 50.
        """
        try:
            portfolio = await self.deps.redis.get_cache(
                "bruno:portfolio:state"
            ) or {}
            pnl_history = portfolio.get("trade_pnl_history_eur", []) or []
            fee_history = portfolio.get("trade_fee_history_eur", []) or []

            if not pnl_history:
                return

            def calc_pf(pnl_values: list[float]) -> float:
                """Berechnet PF für eine Liste realisierter Net-PnL-Werte."""
                gross_profit = sum(v for v in pnl_values if v > 0)
                gross_loss = abs(sum(v for v in pnl_values if v < 0))

                if gross_loss == 0:
                    return 99.9  # Kein Verlust = theoretisch unendlich
                return round(gross_profit / gross_loss, 3)

            # ── Berechnungen ──────────────────────────────────────
            pf_total = calc_pf(pnl_history)
            pf_20 = calc_pf(pnl_history[-20:]) if len(pnl_history) >= 5 else None
            pf_50 = calc_pf(pnl_history[-50:]) if len(pnl_history) >= 20 else None

            # Win Rate
            winning = sum(1 for v in pnl_history if v > 0)
            win_rate = round(winning / len(pnl_history), 3) if pnl_history else 0

            # Durchschnittlicher Gewinn vs. Verlust
            profits = [v for v in pnl_history if v > 0]
            losses = [abs(v) for v in pnl_history if v < 0]
            avg_win = round(sum(profits) / len(profits), 4) if profits else 0
            avg_loss = round(sum(losses) / len(losses), 4) if losses else 0

            # Alarm-Status
            alarm = False
            alarm_reason = None
            if pf_20 is not None and pf_20 < 1.2:
                alarm = True
                alarm_reason = f"PF(20) unter 1.2: {pf_20}"
            elif pf_total < 1.0:
                alarm = True
                alarm_reason = f"PF(gesamt) unter 1.0: {pf_total}"

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pf_total": pf_total,
                "pf_rolling_20": pf_20,
                "pf_rolling_50": pf_50,
                "total_trades": len(pnl_history),
                "win_rate": win_rate,
                "avg_win_pct": avg_win,
                "avg_loss_pct": avg_loss,
                "alarm_active": alarm,
                "alarm_reason": alarm_reason,
                # Rohdaten für Trend-Chart
                "pf_history": [
                    calc_pf(pnl_history[:n])
                    for n in range(10, min(len(pnl_history), 51), 5)
                ] if len(pnl_history) >= 10 else []
            }

            await self.deps.redis.set_cache(
                "bruno:performance:profit_factor",
                payload,
                ttl=86400
            )

            # Telegram-Alarm wenn PF kritisch
            if alarm:
                from app.core.telegram_bot import get_telegram_bot
                telegram = get_telegram_bot()
                if telegram:
                    await telegram.send_critical_alert(
                        f"⚠️ Profit Factor Alarm\n{alarm_reason}\n"
                        f"Win Rate: {win_rate:.0%} | "
                        f"Trades: {len(pnl_history)}"
                    )

            self.logger.info(
                f"PF Update: gesamt={pf_total:.2f} | "
                f"20={pf_20 or 'n/a'} | "
                f"50={pf_50 or 'n/a'} | "
                f"WR={win_rate:.0%}"
            )

        except Exception as e:
            self.logger.error(f"Profit Factor Berechnung Fehler: {e}")

    async def _listen_to_signals(self):
        """Hintergrund-Task: Empfängt Trading-Signale."""
        pubsub = await self.deps.redis.subscribe_channel("bruno:pubsub:signals")
        self.logger.info("Signal-Listener aktiv.")
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    signal = json.loads(msg['data'])
                    await self._execute_trade(signal)
            except Exception as e:
                self.logger.error(f"Signal-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def _monitor_position(self):
        """
        Hintergrund-Task: SL/TP Watcher.
        30s Intervall — ausreichend für Medium-Frequency Trading.
        Phase D Fix: nutzt PositionTracker, kein direkter Redis-Zugriff mehr.
        """
        self.logger.info("Position-Monitor gestartet (30s Intervall).")
        while self.state.running:
            try:
                pos = await self.position_tracker.get_open_position("BTCUSDT")
                if pos:
                    funding_data = await self.deps.redis.get_cache("market:funding:BTCUSDT") or {}
                    current_price = float(funding_data.get("mark_price", 0))
                    if current_price <= 0:
                        ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
                        current_price = float(ticker.get("last_price", 0))

                    if current_price <= 0:
                        await asyncio.sleep(30)
                        continue

                    await self.position_tracker.update_excursions("BTCUSDT", current_price)

                    sl_price = pos["stop_loss_price"]
                    tp_price = pos["take_profit_price"]
                    side = pos["side"]
                    current_pnl_pct = pos.get("current_pnl_pct", 0)
                    
                    # Breakeven-Stop: Wenn Trade > 0.5% im Plus, SL auf Entry + 0.1% ziehen
                    if pos and self._breakeven_enabled:
                        entry_price = float(pos.get("entry_price", 0))
                        side = pos.get("side", "buy")
                        
                        if entry_price > 0 and current_price > 0:
                            if side == "buy":
                                pnl_pct = (current_price - entry_price) / entry_price
                            else:
                                pnl_pct = (entry_price - current_price) / entry_price
                            
                            if pnl_pct >= self._breakeven_trigger_pct:
                                # SL auf Entry + 0.1% setzen (garantiert kein Verlust)
                                if side == "buy":
                                    new_sl = entry_price * 1.001
                                    current_sl = float(pos.get("stop_loss_price", 0))
                                    if current_sl < new_sl:
                                        pos["stop_loss_price"] = new_sl
                                        await self.position_tracker.update_position("BTCUSDT", pos)
                                        self.logger.info(
                                            f"BREAKEVEN-STOP: SL für BTCUSDT auf {new_sl:.2f} gezogen "
                                            f"(Entry: {entry_price:.2f}, Profit: {pnl_pct:.2%})"
                                        )
                                else:  # sell/short
                                    new_sl = entry_price * 0.999
                                    current_sl = float(pos.get("stop_loss_price", float('inf')))
                                    if current_sl > new_sl:
                                        pos["stop_loss_price"] = new_sl
                                        await self.position_tracker.update_position("BTCUSDT", pos)
                                        self.logger.info(f"BREAKEVEN-STOP: SL auf {new_sl:.2f}")
                                
                                # Disable breakeven after activation to prevent constant updates
                                self._breakeven_enabled = False

                    self.logger.debug(
                        f"Monitor: {current_price:,.0f} | SL={sl_price:,.0f} | "
                        f"TP={tp_price:,.0f} | P&L={pos.get('current_pnl_pct', 0):.2%}"
                    )

                    if side == "long":
                        if current_price <= sl_price:
                            self.logger.warning(f"STOP-LOSS (Long): {current_price:,.0f} <= {sl_price:,.0f}")
                            await self._close_position("stop_loss", current_price)
                        elif current_price >= tp_price:
                            self.logger.info(f"TAKE-PROFIT (Long): {current_price:,.0f} >= {tp_price:,.0f}")
                            await self._close_position("take_profit", current_price)
                    elif side == "short":
                        if current_price >= sl_price:
                            self.logger.warning(f"STOP-LOSS (Short): {current_price:,.0f} >= {sl_price:,.0f}")
                            await self._close_position("stop_loss", current_price)
                        elif current_price <= tp_price:
                            self.logger.info(f"TAKE-PROFIT (Short): {current_price:,.0f} <= {tp_price:,.0f}")
                            await self._close_position("take_profit", current_price)
                    
                else:
                    # No open position, reset breakeven flag
                    self._breakeven_enabled = True

            except Exception as e:
                self.logger.error(f"Position-Monitor Fehler: {e}")

            await asyncio.sleep(30)

    async def _close_position(self, reason: str, exit_price: float):
        """
        Schließt offene Position über PositionTracker.
        Phase D Fix: kein _execute_trade()-Rekursion mehr.
        Feuert direkt eine Exit-Order über den Exchange.
        """
        try:
            pos = await self.position_tracker.get_open_position("BTCUSDT")
            if not pos:
                return

            side = pos["side"]
            exit_side = "sell" if side == "long" else "buy"
            qty = pos["quantity"]
            symbol = pos["symbol"]
            trade_id = None

            if self.deps.config.DRY_RUN:
                learning_mode_active = (
                    self.deps.config.DRY_RUN
                    and self._load_config_value("LEARNING_MODE_ENABLED", 0.0) > 0
                )
                trade_mode = "learning" if learning_mode_active else "production"
                trade_id = f"sim_exit_{int(datetime.now().timestamp())}"
                self.logger.info(
                    f"🚧 SIMULIERTER EXIT (DRY_RUN): {exit_side.upper()} "
                    f"{qty:.4f} {symbol} @ {exit_price:,.2f} | Grund: {reason}"
                )
                # Audit für Exit-Trade
                exit_order = {
                    "id": trade_id,
                    "price": exit_price,
                    "amount": qty,
                    "cost": qty * exit_price,
                    "fee": qty * exit_price * 0.0004,
                    "status": "simulated_exit"
                }
                asyncio.create_task(
                    self._audit_trade(
                        {"symbol": symbol, "side": exit_side, "price": exit_price, "reason": reason},
                        exit_order,
                        0.0,
                        trade_mode=trade_mode,
                    )
                )
            else:
                trade_mode = "production"
                if not self.deps.config.LIVE_TRADING_APPROVED:
                    self.logger.error("Exit abgebrochen: LIVE_TRADING_APPROVED=False")
                    return
                exit_order = await self.exm.create_order(symbol, exit_side, qty)
                trade_id = exit_order.get("id")
                self.logger.info(f"✅ EXIT ORDER GEFEUERT: {exit_side.upper()} {qty} {symbol} @ {exit_price:,.0f}")

            # Position im Tracker schließen + DB updaten
            closed = await self.position_tracker.close_position(
                symbol=symbol,
                exit_price=exit_price,
                reason=reason,
                exit_trade_id=trade_id,
            )

            # Portfolio P&L aktualisieren
            if closed and self.deps.config.DRY_RUN:
                await self._update_portfolio({
                    "pnl_eur": closed.get("pnl_eur", 0.0),
                    "fee_eur": qty * exit_price * 0.0004,
                })
                asyncio.create_task(self._update_profit_factor())

            # Telegram-Notification
            from app.core.telegram_bot import get_telegram_bot
            telegram = get_telegram_bot()
            if telegram and closed:
                emoji = "✅" if closed.get("pnl_pct", 0) > 0 else "❌"
                await telegram.send_trade_notification(
                    f"{emoji} Position geschlossen: {reason.upper()}\n"
                    f"{side.upper()} {symbol} | "
                    f"P&L: {closed.get('pnl_pct', 0):+.2%} ({closed.get('pnl_eur', 0):.2f} EUR)\n"
                    f"Haltezeit: {closed.get('hold_duration_minutes', 0)} Min"
                )

            # Post-Trade Debrief (Phase F)
            if closed and self.deps.config.DRY_RUN:
                try:
                    from app.services.debrief_service import debrief_service
                    
                    # Vollständige Positionsdaten für Debrief vorbereiten
                    position_data = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": pos.get("entry_price", 0),
                        "exit_price": exit_price,
                        "quantity": qty,
                        "pnl_eur": closed.get("pnl_eur", 0),
                        "pnl_pct": closed.get("pnl_pct", 0),
                        "hold_duration_minutes": closed.get("hold_duration_minutes", 0),
                        "entry_time": pos.get("entry_time"),
                        "exit_time": datetime.now(timezone.utc).isoformat(),
                        "exit_reason": reason,
                        "grss_at_entry": pos.get("grss_at_entry", 0),
                        "regime": pos.get("regime", "unknown"),
                        "layer1_output": pos.get("layer1_output", {}),
                        "layer2_output": pos.get("layer2_output", {}),
                        "layer3_output": pos.get("layer3_output", {})
                    }
                    
                    # Debrief asynchron ausführen (nicht blockieren)
                    asyncio.create_task(
                        debrief_service.analyze_trade(
                            trade_id=pos.get("id", trade_id),
                            position_data=position_data
                        )
                    )
                    
                    self.logger.info("Post-Trade Debrief gestartet")
                    
                except Exception as e:
                    self.logger.warning(f"Post-Trade Debrief Fehler: {e}")

        except Exception as e:
            self.logger.error(f"_close_position Fehler: {e}")

    async def run_stream(self) -> None:
        """Parallele Ausführung der Listener."""
        await asyncio.gather(
            self._listen_to_risk_veto(),
            self._listen_to_signals(),
            self._monitor_position()
        )
