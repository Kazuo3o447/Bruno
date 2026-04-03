# DEPRECATED — Nicht mehr verwendet. Aktive Version: execution_v3.py
# Dieser Code wird nicht mehr durch worker.py importiert.
raise ImportError("Diese Datei ist deprecated. Nutze execution_v3.py")

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
    Phase 7: Zero-Latency Execution Engine.
    Hält Veto-Entscheidungen im RAM.
    Trennt Order-Firing (0ms Latenz) von Audit/Logging.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("execution", deps)
        self.exm = AuthenticatedExchangeClient(redis=deps.redis)
        self._local_veto_active = True # Default safe State
        self._last_veto_reason = "Initialisierung..."
        self._volatility_multiplier = 1.0
        
        # ── ATR Calculator ───────────────────────────────────────
        from app.services.atr_calculator import ATRCalculator
        self.atr_calc = ATRCalculator(deps.db_session_factory)
        self._last_atr_update: float = 0.0
        self._atr_update_interval: float = 3600.0   # Stündlich
        self._portfolio_initialized = False

    async def setup(self) -> None:
        self.logger.info("ExecutionAgentV3 (Zero-Latency) gestartet.")
        # Startzustand aus Redis laden
        veto_raw = await self.deps.redis.redis.get("bruno:veto:state")
        if veto_raw:
            data = json.loads(veto_raw)
            self._local_veto_active = data.get("Veto_Active", True)
            self._last_veto_reason = data.get("Reason", "Redis Cache")
            self._volatility_multiplier = data.get("Volatility_Size_Multiplier", 1.0)

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
                    self._volatility_multiplier = data.get("Volatility_Size_Multiplier", 1.0)
                    if self._local_veto_active:
                        self.logger.warning(f"LOCAL VETO AKTIV: {self._last_veto_reason}")
            except Exception as e:
                self.logger.error(f"Veto-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def _execute_trade(self, signal: Dict):
        """Der kritische Pfad. 0ms RAM-Check und sofortiges Firing."""
        start_exec = time.perf_counter()

        # 1. RAM-CHECK (0ms Latenz)
        if self._local_veto_active:
            self.logger.info(f"Signal blockiert durch Veto: {self._last_veto_reason}")
            return

        # ── Preis-Validierung ───────────────────────────────────────
        # Verhindert Orders mit price=0 (QuantAgent-Bug war: kein Preis im Signal)
        signal_price = signal.get("price", 0.0)
        if signal_price <= 0:
            self.logger.error(
                f"ABBRUCH: Signal ohne validen Preis empfangen. "
                f"Signal: {signal}. "
                f"Prüfe ob QuantAgent 'price' im Signal-Dict hat."
            )
            return

        symbol = signal.get("symbol")
        side = signal.get("side")
        amount = signal.get("amount", 0.01)

        if not symbol or not isinstance(symbol, str):
            self.logger.error(f"ABBRUCH: Ungültiges oder fehlendes Symbol im Signal: {signal}")
            return

        if side not in {"buy", "sell"}:
            self.logger.error(f"ABBRUCH: Ungültige Signal-Seite empfangen: {signal}")
            return

        if amount <= 0:
            self.logger.error(f"ABBRUCH: Ungültige Signal-Menge empfangen: {signal}")
            return

        # ── ATR aktualisieren (stündlich) ─────────────────────
        now = time.time()
        if now - self._last_atr_update > self._atr_update_interval:
            self._last_atr_update = now
            await self.atr_calc.calculate_atr(symbol)
            await self.atr_calc.calculate_atr_baseline(symbol)

        # ── Volatility-adjusted Position Sizing ───────────────
        vol_multiplier = self.atr_calc.get_volatility_multiplier()
        base_sl_pct = 0.010  # 1% Basis-Stop-Loss
        dynamic_sl_pct = self.atr_calc.get_dynamic_stop_loss(
            base_sl_pct, signal_price
        )

        # Angepasste Positionsgröße
        portfolio = await self.deps.redis.get_cache(
            "bruno:portfolio:state"
        ) or {}
        capital = portfolio.get(
            "capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR
        )

        # Basisgröße: 2% des Kapitals, angepasst durch ATR-Multiplikator UND Risiko-Vola-Multiplikator
        base_risk_eur = capital * 0.02
        # ATR-Multiplier * Risk-Vola-Multiplier (v2)
        total_vol_multiplier = vol_multiplier * self._volatility_multiplier
        adjusted_risk_eur = base_risk_eur * total_vol_multiplier
        
        position_size_btc = max(
            0.001,  # Bybit Minimum
            min(
                adjusted_risk_eur / signal_price,
                (capital * self.deps.config.MAX_LEVERAGE) / signal_price
            )
        )
        amount = max(0.001, min(amount, position_size_btc))

        if total_vol_multiplier < 1.0:
            self.logger.info(
                f"VOLA-ADJUSTMENT: Total={total_vol_multiplier:.2f} "
                f"(ATR={vol_multiplier:.2f}, Risk={self._volatility_multiplier:.2f}) | "
                f"Pos={position_size_btc:.4f} BTC"
            )

        # 2. IMMEDIATE ORDER FIRING (OR SHADOW SIMULATION)
        try:
            if self.deps.config.DRY_RUN:
                # ABSOLUTER DRY-RUN BLOCK (Phase 7.5 Audit)
                exec_latency = (time.perf_counter() - start_exec) * 1000
                simulated_fee = (amount * signal_price) * 0.0004 # 0.04% Taker-Fee

                # Simulation der Netzwerklatenz-Slippage (Random Noise für Audit)
                simulated_fill_price = signal_price * 1.0001 if side == "buy" else signal_price * 0.9999

                self.logger.info(f"🚧 SIMULIERTER TRADE (DRY_RUN): {side.upper()} {amount} {symbol} @ {simulated_fill_price:.2f}")

                # Mock-Order Objekt für Audit-Logging
                order = {
                    "id": f"sim_{int(datetime.now().timestamp())}",
                    "price": simulated_fill_price,
                    "amount": amount,
                    "cost": amount * simulated_fill_price,
                    "fee": simulated_fee,
                    "status": "simulated"
                }

                asyncio.create_task(self._audit_trade(signal, order, exec_latency))
                return

            # ECHTE ORDER AUSFÜHRUNG (Nur wenn DRY_RUN=False)
            order = await self.exm.create_order(symbol, side, amount)
            exec_latency = (time.perf_counter() - start_exec) * 1000
            self.logger.info(f"✅ ECHTE ORDER GEFEUERT: {side.upper()} {amount} {symbol} in {exec_latency:.2f}ms")

            # 3. ASYNCHRONOUS AUDIT & LOGGING (Nicht-blockierend)
            asyncio.create_task(self._audit_trade(signal, order, exec_latency))

        except Exception as e:
            self.logger.error(f"KRITISCHER FEHLER BEI ORDER-AUSFÜHRUNG: {e}")

    async def _audit_trade(self, signal: Dict, order: Dict, latency: float):
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
                    latency_ms=latency # Total processing latency
                )
                session.add(log)
                await session.commit()
                
            await self.log_manager.info(
                category="TRADE",
                source=self.agent_id,
                message=f"Audit completed for order {order.get('id')}",
                details={"latency_ms": latency}
            )
            
            # Portfolio nach Trade aktualisieren
            if self.deps.config.DRY_RUN:
                entry_price = signal.get("price", order.get("price", 0.0))
                exit_price = order.get("price", entry_price)
                qty = order.get("amount", 0.0)
                side = signal.get("side", "buy")

                raw_pnl = (
                    (exit_price - entry_price) * qty
                    if side == "buy"
                    else (entry_price - exit_price) * qty
                )
                await self._update_portfolio({
                    "pnl_eur": raw_pnl,
                    "fee_eur": order.get("fee", 0.0)
                })
                
        except Exception as e:
            self.logger.error(f"Audit-Log Fehler: {e}")

        # Profit Factor nach jedem Trade aktualisieren
        asyncio.create_task(self._update_profit_factor())

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
        """Überwacht offene Positionen mit Mark Price für Stop-Loss/Take-Profit."""
        while self.state.running:
            try:
                # Position aus Redis holen
                pos = await self.deps.redis.get_cache("bruno:position:BTCUSDT")
                if not pos or pos.get("status") != "open":
                    await asyncio.sleep(5)
                    continue

                # Mark Price für Stop-Loss Vergleich nutzen
                # Bybit triggert Liquidationen auf Mark Price, nicht Last Price
                # IngestionAgent speichert mark_price in market:funding:BTCUSDT
                funding_data = await self.deps.redis.get_cache(
                    "market:funding:BTCUSDT"
                ) or {}
                mark_price = float(funding_data.get("mark_price", 0))

                # Fallback auf Ticker wenn kein Mark Price verfügbar
                if mark_price <= 0:
                    ticker = await self.deps.redis.get_cache(
                        "market:ticker:BTCUSDT"
                    ) or {}
                    mark_price = float(ticker.get("last_price", 0))
                    if mark_price > 0:
                        self.logger.debug(
                            "Mark Price nicht verfügbar — nutze Last Price"
                        )

                current_price = mark_price
                sl_price = pos.get("stop_loss_price", 0)
                tp_price = pos.get("take_profit_price", 0)
                side = pos.get("side", "")

                self.logger.debug(
                    f"Position Monitor: Mark Price={current_price:,.0f} | "
                    f"SL={sl_price:,.0f} | TP={tp_price:,.0f}"
                )

                # Stop-Loss Check
                if sl_price > 0:
                    if side == "long" and current_price <= sl_price:
                        self.logger.warning(
                            f"STOP-LOSS TRIGGERED (Long): {current_price:,.0f} <= {sl_price:,.0f}"
                        )
                        await self._close_position("stop_loss", current_price)
                    elif side == "short" and current_price >= sl_price:
                        self.logger.warning(
                            f"STOP-LOSS TRIGGERED (Short): {current_price:,.0f} >= {sl_price:,.0f}"
                        )
                        await self._close_position("stop_loss", current_price)

                # Take-Profit Check
                if tp_price > 0:
                    if side == "long" and current_price >= tp_price:
                        self.logger.info(
                            f"TAKE-PROFIT TRIGGERED (Long): {current_price:,.0f} >= {tp_price:,.0f}"
                        )
                        await self._close_position("take_profit", current_price)
                    elif side == "short" and current_price <= tp_price:
                        self.logger.info(
                            f"TAKE-PROFIT TRIGGERED (Short): {current_price:,.0f} <= {tp_price:,.0f}"
                        )
                        await self._close_position("take_profit", current_price)

            except Exception as e:
                self.logger.error(f"Position Monitor Fehler: {e}")

            await asyncio.sleep(2)  # Alle 2 Sekunden prüfen

    async def _close_position(self, reason: str, exit_price: float):
        """Schließt eine Position und sendet Exit-Signal."""
        try:
            pos = await self.deps.redis.get_cache("bruno:position:BTCUSDT")
            if not pos:
                return

            # Exit-Signal generieren (Gegen-Position)
            side = pos.get("side", "")
            exit_side = "sell" if side == "long" else "buy"
            
            exit_signal = {
                "symbol": "BTCUSDT",
                "side": exit_side,
                "amount": pos.get("quantity", 0),
                "price": exit_price,
                "reason": reason
            }

            # Signal ausführen
            await self._execute_trade(exit_signal)

            # Position als geschlossen markieren
            pos["status"] = "closed"
            pos["exit_price"] = exit_price
            pos["exit_reason"] = reason
            pos["exit_time"] = datetime.now(timezone.utc).isoformat()
            await self.deps.redis.set_cache("bruno:position:BTCUSDT", pos)

            self.logger.info(f"Position geschlossen: {reason} @ {exit_price:,.0f}")

        except Exception as e:
            self.logger.error(f"Position Close Fehler: {e}")

    async def run_stream(self) -> None:
        """Parallele Ausführung der Listener."""
        await asyncio.gather(
            self._listen_to_risk_veto(),
            self._listen_to_signals(),
            self._monitor_position()
        )
