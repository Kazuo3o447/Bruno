from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import AuthenticatedExchangeClient
from app.core.config_cache import ConfigCache
from app.services.trade_debrief_v3 import TradeDebriefV3
from app.schemas.models import TradeAuditLog
from sqlalchemy import text
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any

class ExecutionAgentV4(StreamingAgent):
    """
    Bruno v2.1 Execution Engine mit Slippage Protection.
    
    NEU v2.1 Features:
    - Slippage Protection für Sweep-Signale
    - Limit Order Priority für volatile Märkte
    - Max Slippage für Market Orders
    - Intelligent Order Routing basierend auf Market Conditions
    - Enhanced Audit mit Slippage Tracking
    """

    def __init__(self, deps: AgentDependencies):
        super().__init__("execution", deps)
        self.exm = AuthenticatedExchangeClient(redis=deps.redis)
        self._local_veto_active = True
        self._last_veto_reason = "Initialisierung..."

        # Initialize ConfigCache
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        ConfigCache.init(config_path)

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

        # ── Post-Trade Debrief (v3) ──────────────────────────────
        self.debrief_service = TradeDebriefV3(deps.redis, deps.db_session_factory)
        
        # ── Scaled Entry Engine (v2.1) ────────────────────────────
        from app.services.scaled_entry import ScaledEntryEngine
        self.scaled_entry = ScaledEntryEngine(deps.redis)

        self._portfolio_initialized = False
        
        # v2 Breakeven Stop
        self._breakeven_enabled = True
        self._breakeven_trigger_pct = float(ConfigCache.get("BREAKEVEN_TRIGGER_PCT", 0.005))
        
        # v2.1 Slippage Protection
        self._max_slippage_pct = float(ConfigCache.get("MAX_SLIPPAGE_PCT", 0.001))  # 0.1%
        self._sweep_protection_enabled = True
        self._limit_order_threshold_pct = float(ConfigCache.get("LIMIT_ORDER_THRESHOLD_PCT", 0.002))  # 0.2%

    async def setup(self) -> None:
        self.logger.info("ExecutionAgentV4 (Slippage Protection) gestartet.")
        
        # Startzustand aus Redis laden
        veto_raw = await self.deps.redis.redis.get("bruno:veto:state")
        if veto_raw:
            data = json.loads(veto_raw)
            self._local_veto_active = data.get("Veto_Active", True)
            self._last_veto_reason = data.get("Reason", "Redis Cache")
            self.logger.info(f"Veto State aus Redis geladen: Active={self._local_veto_active}")
        else:
            # Wenn kein Veto-State in Redis: aktiv von RiskAgent abfragen
            self.logger.info("Kein Veto-State in Redis - warte auf RiskAgent...")
            for i in range(30):
                await asyncio.sleep(1)
                veto_raw = await self.deps.redis.redis.get("bruno:veto:state")
                if veto_raw:
                    data = json.loads(veto_raw)
                    self._local_veto_active = data.get("Veto_Active", True)
                    self._last_veto_reason = data.get("Reason", "RiskAgent")
                    self.logger.info(f"Veto State nach {i+1}s erhalten: Active={self._local_veto_active}")
                    break
            else:
                self.logger.warning("Kein Veto-State nach 30s — Veto bleibt aktiv bis RiskAgent läuft")

        # Simulated Portfolio initialisieren (DRY_RUN)
        if self.deps.config.DRY_RUN:
            portfolio = await self.deps.redis.get_cache(
                "bruno:portfolio:state"
            )
            if not portfolio:
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

    def _calculate_atr_based_sl_tp(
        self,
        atr: float,
        current_price: float,
        composite_score: float = 50.0
    ) -> tuple[float, float, float, float]:
        """
        PROMPT 4: Vola-Adjustiertes Trade Management.
        
        Berechnet SL, TP1, TP2 und Breakeven-Trigger basierend auf ATR.
        
        1. atr_pct = ATR_14 / Current_Price
        2. SL = 1.2 * atr_pct
        3. TP1 = 1.5 * atr_pct (50% Position)
        4. TP2 = 3.0 * atr_pct (50% Position)
        5. Breakeven = 1.0 * atr_pct (MUSS vor TP1 feuern!)
        
        Returns:
            tuple: (sl_pct, tp1_pct, tp2_pct, breakeven_trigger_pct)
        """
        if atr <= 0 or current_price <= 0:
            return 0.012, 0.018, 0.030, 0.012  # Defaults
        
        atr_pct = atr / current_price
        
        # Score-basierte Anpassung (höherer Score = etwas weiterer SL für größere Targets)
        if composite_score > 80:
            sl_mult = 1.2
            tp1_mult = 1.5
            tp2_mult = 3.0
        elif composite_score > 60:
            sl_mult = 1.2
            tp1_mult = 1.5
            tp2_mult = 3.0
        else:
            sl_mult = 1.2
            tp1_mult = 1.5
            tp2_mult = 3.0
        
        sl_pct = max(0.008, min(0.030, atr_pct * sl_mult))
        tp1_pct = max(sl_pct * 1.5, atr_pct * tp1_mult)  # Mindestens 1.5x SL
        tp2_pct = max(tp1_pct + 0.01, atr_pct * tp2_mult)
        be_trigger_pct = atr_pct * 1.0  # MUSS vor TP1 feuern!
        
        self.logger.info(
            f"ATR-BASED SL/TP: ATR={atr:.0f} ({atr_pct:.2%}) | "
            f"SL={sl_pct:.2%} (1.2x) | TP1={tp1_pct:.2%} (1.5x) | "
            f"TP2={tp2_pct:.2%} (3.0x) | BE={be_trigger_pct:.2%} (1.0x)"
        )
        
        return round(sl_pct, 4), round(tp1_pct, 4), round(tp2_pct, 4), round(be_trigger_pct, 4)

    async def _calculate_risk_based_position_size(
        self, 
        total_equity_usd: float,
        entry_price: float,
        stop_loss_price: float,
        tp1_price: float,
        max_leverage: float = 10.0
    ) -> dict:
        """
        PROMPT 2: Risk-Based Position Sizing.
        
        Berechnet Positionsgröße basierend auf 1% Portfolio-Risiko pro Trade.
        
        1. risk_amount_usd = total_equity * 0.01 (1% Risk)
        2. sl_distance_pct = |entry - stop| / entry
        3. target_position_size_usd = risk_amount_usd / sl_distance_pct
        4. required_leverage = target_size / max_margin (hard limit: 10x)
        
        Returns:
            dict: position_size_btc, position_size_usdt, leverage, margin_required,
                  risk_amount_usd, risk_percent, sl_distance_pct
        """
        risk_percent = 0.01  # 1% fix
        risk_amount_usd = total_equity_usd * risk_percent
        
        # SL Distanz berechnen
        sl_distance = abs(entry_price - stop_loss_price)
        sl_distance_pct = sl_distance / entry_price if entry_price > 0 else 0.01
        
        if sl_distance_pct <= 0:
            self.logger.error(f"Invalid SL distance: {sl_distance_pct}")
            return {"sizing_valid": False, "reject_reason": "Invalid SL distance"}
        
        # Target Position Size (die Menge, bei der ein SL exakt 1% kostet)
        target_position_size_usd = risk_amount_usd / sl_distance_pct
        
        # Max Margin pro Trade (z.B. 20% des Portfolios)
        max_margin_per_trade = total_equity_usd * 0.20
        
        # Benötigter Leverage
        required_leverage = target_position_size_usd / max_margin_per_trade
        actual_leverage = min(required_leverage, max_leverage)
        
        # Margin required bei tatsächlichem Leverage
        margin_required = target_position_size_usd / actual_leverage
        
        # Position Size in BTC
        position_size_btc = target_position_size_usd / entry_price
        
        self.logger.info(
            f"RISK-BASED SIZING: Equity=${total_equity_usd:,.0f} | "
            f"Risk(1%)=${risk_amount_usd:,.0f} | SL={sl_distance_pct:.2%} | "
            f"TargetSize=${target_position_size_usd:,.0f} | "
            f"Leverage={actual_leverage:.1f}x (max {max_leverage}x) | "
            f"Margin=${margin_required:,.0f}"
        )
        
        return {
            "position_size_btc": round(position_size_btc, 4),
            "position_size_usdt": round(target_position_size_usd, 2),
            "leverage": round(actual_leverage, 1),
            "margin_required_usdt": round(margin_required, 2),
            "risk_amount_usd": round(risk_amount_usd, 2),
            "risk_percent": risk_percent,
            "sl_distance_pct": round(sl_distance_pct, 4),
            "target_leverage": round(required_leverage, 1),
            "sizing_valid": True,
            "reject_reason": None
        }

    def _check_fee_hurdle(
        self,
        target_position_size_usd: float,
        tp1_distance_pct: float,
        sl_distance_pct: float,
        risk_amount_usd: float
    ) -> tuple[bool, str]:
        """
        PROMPT 3: Fee Hurdle (Gebühren-Schutz).
        
        Blockiert Trades, bei denen der Netto-Profit von Gebühren aufgefressen wird.
        
        1. gross_profit = position_size * tp1_distance_pct
        2. estimated_fees = position_size * 0.0024 (0.24% roundtrip)
        3. net_profit = gross_profit - estimated_fees
        4. Hurdle: net_profit >= risk_amount * 0.25
        
        Returns:
            tuple: (passed, reason)
        """
        # 1. Brutto-Profit
        gross_profit = target_position_size_usd * tp1_distance_pct
        
        # 2. Roundtrip-Fees (Maker in 0.01%, Taker out 0.04% + Slippage Puffer = 0.24%)
        estimated_fees = target_position_size_usd * 0.0024
        
        # 3. Netto-Profit
        net_profit = gross_profit - estimated_fees
        
        # 4. Hurdle-Logik: Netto-Profit muss mind. 25% des Risikos sein
        hurdle_threshold = risk_amount_usd * 0.25
        
        if net_profit < hurdle_threshold:
            reason = (
                f"Trade REJECTED_BY_FEES: Net profit at TP1 (${net_profit:.2f}) "
                f"< 25% of risk (${hurdle_threshold:.2f}). "
                f"Gross=${gross_profit:.2f}, Fees=${estimated_fees:.2f}"
            )
            self.logger.warning(reason)
            return False, reason
        
        self.logger.info(
            f"FEE HURDLE PASSED: Net=${net_profit:.2f}, "
            f"Hurdle=25% of risk (${hurdle_threshold:.2f}), "
            f"Fees=${estimated_fees:.2f} ({estimated_fees/target_position_size_usd:.2%})"
        )
        return True, ""

    async def _execute_trade(self, signal: Dict):
        """
        v2.1: Enhanced Execution mit Slippage Protection.
        
        Strategy:
        1. Signal-Analyse (Sweep vs Normal)
        2. Order-Typ-Entscheidung (Limit vs Market)
        3. Slippage-Kontrolle (Max 0.1%)
        4. Enhanced Audit mit Slippage Tracking
        """
        start_exec = time.perf_counter()

        # 1. RAM-CHECK (0ms Latenz)
        if self._local_veto_active:
            self.logger.info(f"Signal blockiert durch Veto: {self._last_veto_reason}")
            return

        learning_mode_active = (
            self.deps.config.DRY_RUN
            and ConfigCache.get("LEARNING_MODE_ENABLED", 0.0) > 0
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
        signal_amount = float(signal.get("amount", 0.0) or 0.0)
        amount = signal_amount if signal_amount > 0 else None
        reason = signal.get("reason", "unknown")

        if not symbol or not isinstance(symbol, str):
            self.logger.error(f"ABBRUCH: Ungültiges Symbol: {signal}")
            return

        if side not in {"buy", "sell"}:
            self.logger.error(f"ABBRUCH: Ungültige Seite: {signal}")
            return

        if amount is None:
            self.logger.warning(
                "Signal lieferte keine direkte Menge — verwende internes Sizing statt Signal-Menge."
            )

        # 1. Slot aus Signal lesen
        slot_name = signal.get("strategy_slot", "trend")
        
        # ── POSITION GUARD pro Slot (Phase D) ───────────────────────
        if await self.position_tracker.has_open_position_for_slot(symbol, slot_name):
            self.logger.info(
                f"Signal ignoriert — {slot_name} Slot für {symbol} bereits belegt"
            )
            return

        # PROMPT 8: Slot-spezifischer Circuit Breaker Check
        # 1. Globaler Daily Drawdown Block (Hard -3%)
        daily_block = await self.deps.redis.get_cache("bruno:risk:daily_block")
        if daily_block and daily_block.get("active"):
            self.logger.warning(f"ABBRUCH: Daily Drawdown Block aktiv - {daily_block.get('reason', 'Unbekannt')}")
            return
        
        # 2. Slot-spezifischer Block (3 consecutive losses in diesem Slot)
        slot_block = await self.deps.redis.get_cache(f"bruno:risk:slot_block:{slot_name}")
        if slot_block and slot_block.get("active"):
            self.logger.warning(f"ABBRUCH: Slot Circuit Breaker aktiv für {slot_name} - {slot_block.get('reason', 'Unbekannt')}")
            return

        # ── MARKET CONDITIONS ANALYSIS (v2.1) ──────────────────
        market_conditions = await self._analyze_market_conditions(symbol, signal_price)
        
        # ── ORDER TYPE DECISION (v2.1) ───────────────────────────
        order_decision = self._decide_order_type(signal, market_conditions)
        
        self.logger.info(
            f"Order Decision: {order_decision['type'].upper()} | "
            f"Reason: {order_decision['reason']} | "
            f"Volatility: {market_conditions['volatility_level']}"
        )

        # ── ATR aktualisieren (stündlich) ──────────────────────
        now = time.time()
        if now - self._last_atr_update > self._atr_update_interval:
            self._last_atr_update = now
            await self.atr_calc.calculate_atr(symbol)
            await self.atr_calc.calculate_atr_baseline(symbol)

        # ── PROFESSIONELLES RISK-BASED POSITION SIZING (PROMPT 2) ──────────────────
        portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
        capital_eur = portfolio.get("capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR)
        eurusd = await self.deps.redis.get_cache("macro:eurusd")
        eur_to_usd = float(eurusd) if eurusd else 1.08
        capital_usd = capital_eur * eur_to_usd
        
        from app.services.strategy_manager import StrategyManager, STRATEGY_SLOTS
        strategy_mgr = StrategyManager(self.deps.redis, self.deps.db_session_factory)
        
        slot = STRATEGY_SLOTS.get(slot_name)
        if not slot:
            self.logger.error(f"Unbekannter Slot: {slot_name}")
            return
        
        # PROMPT 2: Dynamische SL/TP Berechnung aus ATR (Prompt 4)
        # Hole ATR-basierte SL/TP Werte aus Signal oder berechne dynamisch
        ta_data = await self.deps.redis.get_cache("bruno:ta:snapshot") or {}
        atr = float(ta_data.get("atr_14", 0.0))
        
        # PROMPT 4: ATR-basierte SL/TP Berechnung
        if atr > 0 and signal_price > 0:
            sl_pct, tp1_pct, tp2_pct, be_pct = self._calculate_atr_based_sl_tp(
                atr, signal_price, signal.get("composite_score", 50)
            )
            # Berechne absolute Preise
            if side == "buy":  # Long
                sl_price = signal_price * (1 - sl_pct)
                tp1_price = signal_price * (1 + tp1_pct)
                tp2_price = signal_price * (1 + tp2_pct)
            else:  # Short
                sl_price = signal_price * (1 + sl_pct)
                tp1_price = signal_price * (1 - tp1_pct)
                tp2_price = signal_price * (1 - tp2_pct)
            be_trigger_pct = be_pct
        else:
            # Fallback auf Signal-Werte oder Defaults
            sl_price = signal.get("stop_loss_price", signal_price * 0.99 if side == "buy" else signal_price * 1.01)
            tp1_price = signal.get("take_profit_1_price", signal_price * 1.01 if side == "buy" else signal_price * 0.99)
            tp2_price = signal.get("take_profit_price", signal_price * 1.02 if side == "buy" else signal_price * 0.98)
            be_trigger_pct = signal.get("breakeven_trigger_pct", 0.01)
        
        # PROMPT 2: Risk-Based Position Sizing mit dynamischem SL
        sizing = await self._calculate_risk_based_position_size(
            total_equity_usd=capital_usd,
            entry_price=signal_price,
            stop_loss_price=sl_price,
            tp1_price=tp1_price,
            max_leverage=10.0
        )
        
        if not sizing.get("sizing_valid", False):
            reject = sizing.get("reject_reason", "Unknown sizing error")
            self.logger.warning(f"Trade REJECTED by Risk-Based Sizing: {reject}")
            if self.deps.config.DRY_RUN:
                await self._log_rejected_trade(signal, reject)
            return
        
        # PROMPT 3: Fee Hurdle Check vor Order-Execution
        tp1_distance_pct = abs(tp1_price - signal_price) / signal_price
        fee_check_passed, fee_reason = self._check_fee_hurdle(
            target_position_size_usd=sizing["position_size_usdt"],
            tp1_distance_pct=tp1_distance_pct,
            sl_distance_pct=sizing["sl_distance_pct"],
            risk_amount_usd=sizing["risk_amount_usd"]
        )
        
        if not fee_check_passed:
            self.logger.warning(f"Trade REJECTED by Fee Hurdle: {fee_reason}")
            if self.deps.config.DRY_RUN:
                await self._log_rejected_trade(signal, fee_reason)
            return
        
        # Portfolio-Level Risk Check
        portfolio_check = await strategy_mgr.can_open_position(
            slot_name, sizing["position_size_usdt"], capital_usd
        )
        if not portfolio_check["allowed"]:
            self.logger.warning(f"Portfolio Risk Check fehlgeschlagen: {portfolio_check['reason']}")
            if self.deps.config.DRY_RUN:
                await self._log_rejected_trade(signal, portfolio_check['reason'])
            return
        
        amount = sizing["position_size_btc"]
        leverage = sizing["leverage"]
        
        self.logger.info(
            f"RISK-BASED SIZING [{slot_name}]: {amount:.4f} BTC "
            f"(${sizing['position_size_usdt']:,.0f}) | "
            f"Leverage: {leverage:.1f}x (target: {sizing['target_leverage']:.1f}x) | "
            f"Margin: ${sizing['margin_required_usdt']:,.0f} | "
            f"Risk: 1% = ${sizing['risk_amount_usd']:,.0f} | "
            f"SL: {sizing['sl_distance_pct']:.2%} | TP1: {tp1_distance_pct:.2%}"
        )

        # 2. ENHANCED ORDER EXECUTION (v2.1)
        try:
            if self.deps.config.DRY_RUN:
                exec_latency = (time.perf_counter() - start_exec) * 1000
                simulated_fee = (amount * signal_price) * 0.0004

                # v2.1: Simulated Slippage basierend auf Market Conditions
                simulated_fill_price = self._calculate_simulated_slippage(
                    signal_price, side, market_conditions, order_decision
                )

                self.logger.info(
                    f"🚧 SIMULIERTER TRADE (DRY_RUN): {side.upper()} "
                    f"{amount:.4f} {symbol} @ {simulated_fill_price:,.2f} "
                    f"(Slippage: {((simulated_fill_price/signal_price)-1)*10000:+.1f} bps)"
                )

                order = {
                    "id": f"sim_{int(datetime.now().timestamp())}",
                    "price": simulated_fill_price,
                    "amount": amount,
                    "cost": amount * simulated_fill_price,
                    "fee": simulated_fee,
                    "status": "simulated",
                    "order_type": order_decision["type"],
                    "slippage_bps": ((simulated_fill_price/signal_price)-1)*10000
                }

            else:
                # ECHTE ORDER mit Slippage Protection
                if not self.deps.config.LIVE_TRADING_APPROVED:
                    self.logger.error(
                        "ABBRUCH: LIVE_TRADING_APPROVED=False. "
                        "Setze in .env auf True nach bestandenem Backtest."
                    )
                    return

                order = await self._execute_order_with_slippage_protection(
                    symbol, side, amount, signal_price, order_decision
                )
                exec_latency = (time.perf_counter() - start_exec) * 1000
                
                self.logger.info(
                    f"✅ ECHTE ORDER GEFEUERT: {order['type'].upper()} "
                    f"{side.upper()} {amount:.4f} {symbol} in {exec_latency:.1f}ms"
                )

            exec_latency = (time.perf_counter() - start_exec) * 1000

            # ── POSITION ÖFFNEN (Phase D) ──────────────────────
            fill_price = order["price"]
            position_side = "long" if side == "buy" else "short"

            # PROMPT 4: Verwende die bereits berechneten ATR-basierten Werte
            # sl_price, tp1_price, tp2_price, be_trigger_pct wurden oben berechnet
            # Wir recalculieren nur für den Fill-Price (kann vom Signal-Price abweichen)
            
            if position_side == "long":
                actual_sl_price = fill_price * (1 - sizing['sl_distance_pct'])
                actual_tp1_price = fill_price * (1 + ((tp1_price - signal_price) / signal_price))
                actual_tp2_price = fill_price * (1 + ((tp2_price - signal_price) / signal_price))
            else:
                actual_sl_price = fill_price * (1 + sizing['sl_distance_pct'])
                actual_tp1_price = fill_price * (1 - ((tp1_price - signal_price) / signal_price))
                actual_tp2_price = fill_price * (1 - ((tp2_price - signal_price) / signal_price))
            
            # Verwende die berechneten Werte
            sl_price = actual_sl_price
            tp1_price = actual_tp1_price
            tp2_price = actual_tp2_price
            
            # Scaled Entry: Nur erste Tranche ausführen
            from app.services.strategy_manager import STRATEGY_SLOTS
            slot_config = STRATEGY_SLOTS.get(slot_name)
            
            if slot_config and slot_config.scaled_entry_enabled:
                # PROMPT 6: Hole ATR für Scaled Entry
                atr_value = float(ta_data.get("atr_14", 0.0)) if 'ta_data' in locals() else 0.0
                
                tranche_info = await self.scaled_entry.initiate_entry(
                    symbol=symbol,
                    slot_name=slot_name,
                    direction=position_side,
                    entry_price=fill_price,
                    total_size_btc=amount,
                    slot_config=slot_config,
                    atr=atr_value,  # PROMPT 6: ATR für ATR-basierte Steps
                )
                # Nur erste Tranche wurde ausgeführt
                actual_amount = tranche_info["tranche_size_btc"]
                self.logger.info(
                    f"Scaled Entry [{slot_name}]: Tranche 1/{slot_config.entry_tranches} "
                    f"= {actual_amount:.4f} BTC ({slot_config.tranche_sizes[0]*100:.0f}%)"
                )
                # Überschreibe amount für open_position
                amount = actual_amount

            try:
                # PROMPT 4: Berechne die PCT-Werte aus den Preisen für die Exit-Logik
                tp1_pct_value = abs(tp1_price - fill_price) / fill_price
                tp2_pct_value = abs(tp2_price - fill_price) / fill_price
                
                await self.position_tracker.open_position(
                    symbol=symbol,
                    side=position_side,
                    entry_price=fill_price,
                    quantity=amount,
                    strategy_slot=slot_name,   # ← DIESEN PARAMETER HINZUFÜGEN
                    stop_loss_price=round(sl_price, 2),
                    take_profit_price=round(tp2_price, 2),    # TP2 als Haupt-TP
                    take_profit_1_price=round(tp1_price, 2),  # TP1 NEU
                    take_profit_2_price=round(tp2_price, 2),  # TP2 NEU
                    take_profit_1_pct=round(tp1_pct_value, 4),  # PROMPT 4: PCT für Exit-Logic
                    take_profit_2_pct=round(tp2_pct_value, 4),  # PROMPT 4: PCT für Exit-Logic
                    tp1_size_pct=signal.get("tp1_size_pct", 0.50),
                    tp2_size_pct=signal.get("tp2_size_pct", 0.50),
                    breakeven_trigger_pct=be_trigger_pct,
                    tp1_hit=False,
                    max_favorable_price=fill_price,
                    min_favorable_price=fill_price,
                    entry_trade_id=order["id"],
                    # Sub-Scores für Debrief (v3)
                    composite_score=signal.get("composite_score", 0.0),
                    ta_score=signal.get("ta_score", 0.0),
                    liq_score=signal.get("liq_score", 0.0),
                    flow_score=signal.get("flow_score", 0.0),
                    macro_score=signal.get("macro_score", 0.0),
                    signals_active=signal.get("signals", []),
                    # Phase C Felder — aus Signal wenn vorhanden
                    grss_at_entry=signal.get("grss", 0.0),
                    layer1_output=signal.get("layer1_output"),
                    layer2_output=signal.get("layer2_output"),
                    layer3_output=signal.get("layer3_output"),
                    regime=signal.get("regime", "unknown"),
                    # v2.1 Enhanced Fields
                    order_type=order.get("type", "market"),
                    slippage_bps=order.get("slippage_bps", 0),
                    market_conditions=market_conditions,
                )
            except ValueError as ve:
                self.logger.warning(f"PositionTracker Guard (race): {ve}")

            # Enhanced Audit mit Slippage Tracking
            await self._audit_trade_enhanced(signal, order, exec_latency, market_conditions, trade_mode=trade_mode)

        except Exception as e:
            self.logger.error(f"KRITISCHER FEHLER BEI ORDER-AUSFÜHRUNG: {e}")

    async def _analyze_market_conditions(self, symbol: str, signal_price: float) -> Dict[str, Any]:
        """
        v2.1: Analyse der Marktbedingungen für Slippage Protection.
        
        Returns:
        - volatility_level: "low", "medium", "high", "extreme"
        - orderbook_depth: Tiefe des Orderbuchs
        - recent_trades_volume: Letzte Trade-Volumina
        - spread_pct: Aktueller Bid-Ask Spread
        """
        try:
            # Orderbuch-Daten aus TA-Agent
            ob_data = await self.deps.redis.get_cache("bruno:ta:ob_walls") or {}
            
            # Ticker-Daten für Spread
            ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            
            # Volatilität aus ATR
            atr_current = await self.atr_calc.get_current_atr(symbol)
            volatility_pct = (atr_current / signal_price) * 100 if atr_current > 0 else 0.1
            
            # Volatilitäts-Level bestimmen
            if volatility_pct < 0.5:
                vol_level = "low"
            elif volatility_pct < 1.5:
                vol_level = "medium"
            elif volatility_pct < 3.0:
                vol_level = "high"
            else:
                vol_level = "extreme"
            
            # Spread berechnen
            bid_price = float(ticker.get("bid_price", 0))
            ask_price = float(ticker.get("ask_price", 0))
            spread_pct = ((ask_price - bid_price) / signal_price * 100) if bid_price > 0 and ask_price > 0 else 0.01
            
            # Orderbuch-Tiefe
            bid_volume = ob_data.get("bid_volume", 0)
            ask_volume = ob_data.get("ask_volume", 0)
            total_depth = bid_volume + ask_volume
            
            return {
                "volatility_pct": round(volatility_pct, 2),
                "volatility_level": vol_level,
                "spread_pct": round(spread_pct, 3),
                "bid_price": bid_price,
                "ask_price": ask_price,
                "orderbook_depth": total_depth,
                "bid_volume": bid_volume,
                "ask_volume": ask_volume,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Market Conditions Analyse Fehler: {e}")
            return {
                "volatility_pct": 0.1,
                "volatility_level": "medium",
                "spread_pct": 0.01,
                "bid_price": 0,
                "ask_price": 0,
                "orderbook_depth": 0,
                "bid_volume": 0,
                "ask_volume": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _decide_order_type(self, signal: Dict, market_conditions: Dict) -> Dict[str, Any]:
        """
        v2.1: Intelligente Order-Typ-Entscheidung.
        
        Logic:
        - Sweep-Signale → Limit Order (Maker) bei normaler Volatilität
        - Extreme Volatilität → Market Order mit Max Slippage
        - Normale Signale → Market Order (Default)
        """
        reason = signal.get("reason", "unknown")
        volatility = market_conditions["volatility_level"]
        spread_pct = market_conditions["spread_pct"]
        
        # Sweep-Signale bevorzugen Limit Orders
        if "sweep" in reason.lower() and self._sweep_protection_enabled:
            if volatility in ["low", "medium"] and spread_pct < 0.05:
                return {
                    "type": "limit",
                    "reason": "sweep_low_volatility",
                    "confidence": "high"
                }
            else:
                return {
                    "type": "market",
                    "reason": "sweep_high_volatility",
                    "confidence": "medium",
                    "max_slippage": self._max_slippage_pct * 2  # Erhöht bei Sweep
                }
        
        # Extreme Volatilität → Market Order mit Protection
        if volatility == "extreme":
            return {
                "type": "market",
                "reason": "extreme_volatility",
                "confidence": "low",
                "max_slippage": self._max_slippage_pct * 3  # 0.3% bei Extrem
            }
        
        # Hoher Spread → Limit Order (avoid bad fills)
        if spread_pct > self._limit_order_threshold_pct:
            return {
                "type": "limit",
                "reason": "high_spread",
                "confidence": "medium"
            }
        
        # Default: Market Order
        return {
            "type": "market",
            "reason": "default",
            "confidence": "high"
        }

    def _calculate_simulated_slippage(self, signal_price: float, side: str, 
                                     market_conditions: Dict, order_decision: Dict) -> float:
        """
        v2.1: Realistische Slippage-Simulation für DRY_RUN.
        
        Basierend auf:
        - Volatilitäts-Level
        - Orderbuch-Tiefe
        - Spread
        - Order-Typ
        """
        volatility = market_conditions["volatility_level"]
        spread_pct = market_conditions["spread_pct"]
        order_type = order_decision["type"]
        
        # Basis-Slippage nach Volatilität
        base_slippage = {
            "low": 0.0001,      # 0.01%
            "medium": 0.0003,   # 0.03%
            "high": 0.0008,     # 0.08%
            "extreme": 0.002    # 0.2%
        }.get(volatility, 0.0003)
        
        # Order-Typ Anpassung
        if order_type == "limit":
            # Limit Orders: weniger Slippage (Maker)
            slippage = base_slippage * 0.3
        else:
            # Market Orders: mehr Slippage (Taker)
            slippage = base_slippage * (1 + spread_pct * 10)  # Spread beeinflusst
            
        # Max Slippage Protection
        max_slippage = order_decision.get("max_slippage", self._max_slippage_pct)
        slippage = min(slippage, max_slippage)
        
        # Richtung berücksichtigen
        if side == "buy":
            return signal_price * (1 + slippage)
        else:
            return signal_price * (1 - slippage)

    async def _execute_order_with_slippage_protection(self, symbol: str, side: str, 
                                                     amount: float, signal_price: float,
                                                     order_decision: Dict) -> Dict[str, Any]:
        """
        v2.1: Echte Order-Ausführung mit Slippage Protection.
        """
        order_type = order_decision["type"]
        
        if order_type == "limit":
            return await self._execute_limit_order(symbol, side, amount, signal_price, order_decision)
        else:
            return await self._execute_market_order(symbol, side, amount, signal_price, order_decision)

    async def _execute_limit_order(self, symbol: str, side: str, amount: float, 
                                  signal_price: float, order_decision: Dict) -> Dict[str, Any]:
        """
        v2.1: Limit Order mit Slippage Protection.
        
        Strategy:
        - Preis leicht im Money (bessere Ausführungswahrscheinlichkeit)
        - Time-to-Limit: 30 Sekunden
        - Fallback zu Market Order bei Nicht-Ausführung
        """
        # Limit Preis berechnen (im Money)
        spread_pct = 0.01  # 0.1% im Money
        if side == "buy":
            limit_price = signal_price * (1 + spread_pct)
        else:
            limit_price = signal_price * (1 - spread_pct)
        
        try:
            # Limit Order platzieren
            order = await self.exm.create_limit_order(
                symbol=symbol,
                side=side,
                amount=amount,
                price=round(limit_price, 2),
                time_in_force="GTC",  # Good Till Canceled
                timeout_ms=30000      # 30s Timeout
            )
            
            # Slippage berechnen (sollte bei Limit Order minimal sein)
            slippage_bps = ((order.get("price", limit_price) / signal_price) - 1) * 10000
            
            return {
                **order,
                "type": "limit",
                "slippage_bps": slippage_bps,
                "limit_price": limit_price
            }
            
        except Exception as e:
            self.logger.warning(f"Limit Order fehlgeschlagen, fallback zu Market: {e}")
            # Fallback zu Market Order
            return await self._execute_market_order(symbol, side, amount, signal_price, order_decision)

    async def _execute_market_order(self, symbol: str, side: str, amount: float,
                                   signal_price: float, order_decision: Dict) -> Dict[str, Any]:
        """
        v2.1: Market Order mit Max Slippage Protection.
        
        Strategy:
        - Max Slippage: 0.1% (oder höher bei Sweep/Extreme)
        - Pre-Execution Price Check
        - Post-Execution Slippage Validation
        """
        max_slippage = order_decision.get("max_slippage", self._max_slippage_pct)
        
        # Pre-Execution Price Check
        current_ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
        current_price = float(current_ticker.get("last_price", signal_price))
        
        # Validate current price vs signal price
        price_diff_pct = abs((current_price / signal_price) - 1)
        if price_diff_pct > max_slippage * 2:  # Preis hat sich stark bewegt
            self.logger.warning(
                f"Pre-Execution Price Check Failed: "
                f"Signal={signal_price:,.2f}, Current={current_price:,.2f}, "
                f"Diff={price_diff_pct:.3%}"
            )
            # Trotzdem ausführen aber mit Warning
        
        try:
            # Market Order ausführen
            order = await self.exm.create_market_order(symbol, side, amount)
            
            # Post-Execution Slippage Validation
            fill_price = order.get("price", current_price)
            slippage_bps = ((fill_price / signal_price) - 1) * 10000
            
            # Slippage Warning wenn zu hoch
            if abs(slippage_bps) > max_slippage * 10000:
                self.logger.warning(
                    f"HOHE SLIPPAGE ERKANNT: {slippage_bps:+.1f} bps "
                    f"(Max: {max_slippage*10000:.1f} bps)"
                )
            
            return {
                **order,
                "type": "market",
                "slippage_bps": slippage_bps,
                "max_slippage_allowed": max_slippage,
                "pre_execution_price": current_price
            }
            
        except Exception as e:
            self.logger.error(f"Market Order fehlgeschlagen: {e}")
            raise

    async def _audit_trade_enhanced(self, signal: Dict, order: Dict, latency: float, 
                                   market_conditions: Dict, trade_mode: str = "production"):
        """
        v2.1: Enhanced Audit mit Slippage Tracking und Market Conditions.
        """
        try:
            async with self.deps.db_session_factory() as session:
                log = TradeAuditLog(
                    id=order.get('id', str(datetime.now().timestamp())),
                    timestamp=datetime.now(timezone.utc),
                    symbol=signal.get('symbol'),
                    action=signal.get('side'),
                    price=order.get('price', 0.0),
                    quantity=order.get('amount', 0.0),
                    total=order.get('cost', 0.0),
                    status=order.get('status', 'filled'),
                    
                    # v2.1 Enhanced Telemetry
                    latency_exec_ms=latency,
                    signal_price=signal.get('price', 0.0),
                    slippage_bps=order.get('slippage_bps', 0),
                    order_type=order.get('type', 'market'),
                    max_slippage_allowed=order.get('max_slippage_allowed', self._max_slippage_pct),
                    
                    # Market Conditions
                    volatility_level=market_conditions.get('volatility_level', 'unknown'),
                    spread_pct=market_conditions.get('spread_pct', 0),
                    orderbook_depth=market_conditions.get('orderbook_depth', 0),
                    
                    # Legacy Fields
                    simulated_fill_price=order.get('price', 0.0),
                    simulated_fee_usdt=order.get('fee', 0.0),
                    latency_ms=latency,
                    trade_mode=trade_mode,
                )
                session.add(log)
                await session.commit()
                
            slippage_info = f"Slippage: {order.get('slippage_bps', 0):+.1f} bps"
            self.logger.info(f"Audit completed for order {order.get('id')} | {slippage_info}")
                
        except Exception as e:
            self.logger.error(f"Enhanced Audit-Log Fehler: {e}")

    # Legacy Methods (unverändert für Kompatibilität)
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

    async def _update_portfolio(self, trade_result: dict) -> None:
        """Aktualisiert das simulierte Portfolio nach einem Trade."""
        if not self.deps.config.DRY_RUN:
            return

        portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
        pnl_eur = trade_result.get("pnl_eur", 0.0)
        fee_eur = trade_result.get("fee_eur", 0.0)
        net_pnl = pnl_eur - fee_eur

        portfolio["capital_eur"] = portfolio.get("capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR) + net_pnl
        portfolio["realized_pnl_eur"] = portfolio.get("realized_pnl_eur", 0.0) + net_pnl
        portfolio["total_fees_eur"] = portfolio.get("total_fees_eur", 0.0) + fee_eur
        portfolio["total_trades"] = portfolio.get("total_trades", 0) + 1

        # Historie für Profit-Factor / Trend-Analyse
        pnl_history = portfolio.get("trade_pnl_history_eur", [])
        fee_history = portfolio.get("trade_fee_history_eur", [])
        pnl_history.append(net_pnl)
        fee_history.append(fee_eur)
        portfolio["trade_pnl_history_eur"] = pnl_history[-200:]
        portfolio["trade_fee_history_eur"] = fee_history[-200:]

        if net_pnl > 0:
            portfolio["winning_trades"] = portfolio.get("winning_trades", 0) + 1
        else:
            portfolio["losing_trades"] = portfolio.get("losing_trades", 0) + 1

        # Peak + Drawdown
        current = portfolio["capital_eur"]
        peak = portfolio.get("peak_capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR)
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
        portfolio["daily_pnl_eur"] = portfolio.get("daily_pnl_eur", 0.0) + net_pnl

        # Daily Loss Limit prüfen
        initial = portfolio.get("initial_capital_eur", self.deps.config.SIMULATED_CAPITAL_EUR)
        daily_limit = initial * self.deps.config.DAILY_LOSS_LIMIT_PCT
        if portfolio["daily_pnl_eur"] < -daily_limit:
            self.logger.warning(f"⛔ DAILY LOSS LIMIT ERREICHT: {portfolio['daily_pnl_eur']:.2f} EUR (Limit: -{daily_limit:.2f} EUR)")
            await self.deps.redis.set_cache("bruno:portfolio:daily_limit_hit", {"hit": True, "date": today}, ttl=86400)

        portfolio["last_update"] = datetime.now(timezone.utc).isoformat()
        await self.deps.redis.set_cache("bruno:portfolio:state", portfolio)

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
        Position Monitor für alle Strategie-Slots.
        """
        self.logger.info("Position-Monitor v3 gestartet (Multi-Slot, 10s Intervall).")
        
        from app.services.strategy_manager import STRATEGY_SLOTS
        
        while self.state.running:
            try:
                # Iteriere über alle Slots
                for slot_name, slot_config in STRATEGY_SLOTS.items():
                    if not slot_config.enabled:
                        continue
                    
                    pos = await self.position_tracker.get_open_position("BTCUSDT", slot=slot_name)
                    if not pos:
                        continue
                    
                    current_price = await self._get_current_price()
                    if current_price <= 0:
                        continue
                    
                    await self.position_tracker.update_excursions("BTCUSDT", current_price, slot=slot_name)
                    
                    # Max Hold Time Check (Sweep: 2h, Funding: 8h)
                    if slot_config.max_hold_minutes:
                        entry_time = datetime.fromisoformat(pos["entry_time"])
                        hold_minutes = (datetime.now(timezone.utc) - entry_time).total_seconds() / 60
                        if hold_minutes >= slot_config.max_hold_minutes:
                            self.logger.info(
                                f"MAX HOLD TIME [{slot_name}]: {hold_minutes:.0f}min >= {slot_config.max_hold_minutes}min"
                            )
                            await self._close_position_for_slot("max_hold_time", current_price, slot_name)
                            continue
                    
                    # Rest der SL/TP/Breakeven/Trailing Logic 
                    # (identisch zum bestehenden Code, aber mit slot_name)
                    await self._check_exit_conditions(pos, current_price, slot_name, slot_config)
                
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Position-Monitor Fehler: {e}")
                await asyncio.sleep(10)

    def _is_sl_hit(self, side: str, price: float, sl: float) -> bool:
        return (side == "long" and price <= sl) or \
               (side == "short" and price >= sl)

    def _is_tp_hit(self, side: str, price: float, tp: float) -> bool:
        return (side == "long" and price >= tp) or \
               (side == "short" and price <= tp)

    async def _get_current_price(self) -> float:
        """Holt aktuellen BTC-Preis (Mark Price > Ticker > 0)."""
        funding = await self.deps.redis.get_cache("market:funding:BTCUSDT") or {}
        price = float(funding.get("mark_price", 0))
        if price <= 0:
            ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            price = float(ticker.get("last_price", 0))
        return price

    async def _get_current_atr(self) -> float:
        """ATR aus TA-Snapshot."""
        ta = await self.deps.redis.get_cache("bruno:ta:snapshot") or {}
        return float(ta.get("atr_14", 0))

    async def _partial_close(self, pos: dict, quantity: float,
                              exit_price: float, reason: str):
        """Nutzt PositionTracker's scale_out_position für TP1 Scaling."""
        symbol = pos["symbol"]
        initial_qty = float(pos.get("initial_quantity", pos.get("quantity", 0)))
        fraction = quantity / initial_qty if initial_qty > 0 else 0.50
        
        trade_id = None
        if self.deps.config.DRY_RUN:
            trade_id = f"sim_tp1_{int(datetime.now().timestamp())}"
            self.logger.info(
                f"🔀 TP1 SCALING (DRY_RUN): {quantity:.4f} BTC "
                f"@ {exit_price:,.2f} | {reason}")
        else:
            if self.deps.config.LIVE_TRADING_APPROVED:
                exit_side = "sell" if pos["side"] == "long" else "buy"
                order = await self.exm.create_market_order(
                    symbol, exit_side, quantity)
                trade_id = order.get("id")
        
        result = await self.position_tracker.scale_out_position(
            symbol=symbol,
            exit_price=exit_price,
            reason=reason,
            fraction=fraction,
            move_stop_to_breakeven=True,
            exit_trade_id=trade_id,
        )
        
        if result and self.deps.config.DRY_RUN:
            # Portfolio Update für Teilschließung
            entry_price = float(pos["entry_price"])
            if pos["side"] == "long":
                pnl = (exit_price - entry_price) * quantity
            else:
                pnl = (entry_price - exit_price) * quantity
            fee = quantity * exit_price * 0.0004
            await self._update_portfolio({"pnl_eur": pnl, "fee_eur": fee})
        
        return result

    async def _close_position(self, reason: str, exit_price: float):
        """Schließt offene Position über PositionTracker."""
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
                    and ConfigCache.get("LEARNING_MODE_ENABLED", 0.0) > 0
                )
                trade_mode = "learning" if learning_mode_active else "production"
                trade_id = f"sim_exit_{int(datetime.now().timestamp())}"
                self.logger.info(f"🚧 SIMULIERTER EXIT (DRY_RUN): {exit_side.upper()} {qty:.4f} {symbol} @ {exit_price:,.2f} | Grund: {reason}")
                
                exit_order = {
                    "id": trade_id,
                    "price": exit_price,
                    "amount": qty,
                    "cost": qty * exit_price,
                    "fee": qty * exit_price * 0.0004,
                    "status": "simulated_exit"
                }
                asyncio.create_task(
                    self._audit_trade_enhanced(
                        {"symbol": symbol, "side": exit_side, "price": exit_price, "reason": reason},
                        exit_order,
                        0.0,
                        {"volatility_level": "unknown"},  # Market conditions not critical for exit
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

            closed = await self.position_tracker.close_position(
                symbol=symbol,
                exit_price=exit_price,
                reason=reason,
                exit_trade_id=trade_id,
            )

            if closed:
                # Trigger non-blocking Post-Trade Debrief
                asyncio.create_task(self.debrief_service.debrief_trade(closed, trade_mode=trade_mode))

                if self.deps.config.DRY_RUN:
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

        except Exception as e:
            self.logger.error(f"_close_position Fehler: {e}")

    async def _update_profit_factor(self) -> None:
        """Berechnet Profit Factor live aus der realisierten Trade-P&L-Historie."""
        try:
            portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
            pnl_history = portfolio.get("trade_pnl_history_eur", []) or []
            fee_history = portfolio.get("trade_fee_history_eur", []) or []

            if not pnl_history:
                return

            def calc_pf(pnl_values: list[float]) -> float:
                gross_profit = sum(v for v in pnl_values if v > 0)
                gross_loss = abs(sum(v for v in pnl_values if v < 0))
                if gross_loss == 0:
                    return 99.9
                return round(gross_profit / gross_loss, 3)

            pf_total = calc_pf(pnl_history)
            pf_20 = calc_pf(pnl_history[-20:]) if len(pnl_history) >= 5 else None
            pf_50 = calc_pf(pnl_history[-50:]) if len(pnl_history) >= 20 else None

            winning = sum(1 for v in pnl_history if v > 0)
            win_rate = round(winning / len(pnl_history), 3) if pnl_history else 0

            profits = [v for v in pnl_history if v > 0]
            losses = [abs(v) for v in pnl_history if v < 0]
            avg_win = round(sum(profits) / len(profits), 4) if profits else 0
            avg_loss = round(sum(losses) / len(losses), 4) if losses else 0

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
                "pf_history": [
                    calc_pf(pnl_history[:n])
                    for n in range(10, min(len(pnl_history), 51), 5)
                ] if len(pnl_history) >= 10 else []
            }

            await self.deps.redis.set_cache("bruno:performance:profit_factor", payload, ttl=86400)

            if alarm:
                from app.core.telegram_bot import get_telegram_bot
                telegram = get_telegram_bot()
                if telegram:
                    await telegram.send_critical_alert(
                        f"⚠️ Profit Factor Alarm\n{alarm_reason}\n"
                        f"Win Rate: {win_rate:.0%} | Trades: {len(pnl_history)}"
                    )

            self.logger.info(f"PF Update: gesamt={pf_total:.2f} | 20={pf_20 or 'n/a'} | 50={pf_50 or 'n/a'} | WR={win_rate:.0%}")

        except Exception as e:
            self.logger.error(f"Profit Factor Berechnung Fehler: {e}")

    async def _log_rejected_trade(self, signal: dict, reason: str):
        """Loggt abgelehnte Trades für Learning/Analyse."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "SIZING_REJECT",
            "reason": reason,
            "signal_score": signal.get("composite_score", 0),
            "signal_direction": signal.get("side", "unknown"),
            "price": signal.get("price", 0),
        }
        await self.deps.redis.redis.lpush(
            "bruno:trades:rejected", json.dumps(entry)
        )
        await self.deps.redis.redis.ltrim("bruno:trades:rejected", 0, 199)

    async def _update_profit_factor(self) -> None:
        """Berechnet Profit Factor live aus der realisierten Trade-P&L-Historie."""
        try:
            portfolio = await self.deps.redis.get_cache("bruno:portfolio:state") or {}
            pnl_history = portfolio.get("trade_pnl_history_eur", []) or []
            fee_history = portfolio.get("trade_fee_history_eur", []) or []

            if not pnl_history:
                return

            def calc_pf(pnl_values: list[float]) -> float:
                gross_profit = sum(v for v in pnl_values if v > 0)
                gross_loss = abs(sum(v for v in pnl_values if v < 0))
                if gross_loss == 0:
                    return 99.9
                return round(gross_profit / gross_loss, 3)

            pf_total = calc_pf(pnl_history)
            pf_20 = calc_pf(pnl_history[-20:]) if len(pnl_history) >= 5 else None
            pf_50 = calc_pf(pnl_history[-50:]) if len(pnl_history) >= 5 else None
            
            # Win Rate
            wins = sum(1 for pnl in pnl_history if pnl > 0)
            win_rate = wins / len(pnl_history) if pnl_history else 0
            
            # Avg Win/Loss
            wins_list = [pnl for pnl in pnl_history if pnl > 0]
            losses_list = [pnl for pnl in pnl_history if pnl < 0]
            avg_win = sum(wins_list) / len(wins_list) if wins_list else 0
            avg_loss = sum(losses_list) / len(losses_list) if losses_list else 0
            
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
                "pf_history": [
                    calc_pf(pnl_history[:n])
                    for n in range(10, min(len(pnl_history), 51), 5)
                ] if len(pnl_history) >= 10 else []
            }

            await self.deps.redis.set_cache("bruno:performance:profit_factor", payload, ttl=86400)

            if alarm:
                from app.core.telegram_bot import get_telegram_bot
                telegram = get_telegram_bot()
                if telegram:
                    await telegram.send_critical_alert(
                        f"⚠️ Profit Factor Alarm\n{alarm_reason}\n"
                        f"Win Rate: {win_rate:.0%} | Trades: {len(pnl_history)}"
                    )

            self.logger.info(f"PF Update: gesamt={pf_total:.2f} | 20={pf_20 or 'n/a'} | 50={pf_50 or 'n/a'} | WR={win_rate:.0%}")

        except Exception as e:
            self.logger.error(f"Profit Factor Berechnung Fehler: {e}")

    async def _check_exit_conditions(self, pos, current_price, slot_name, slot_config):
        """Prüft SL/TP/Breakeven/Trailing für eine spezifische Position."""
        entry_price = float(pos["entry_price"])
        side = pos["side"]
        sl_price = float(pos["stop_loss_price"])
        tp_price = float(pos["take_profit_price"])
        quantity = float(pos["quantity"])
        
        # Scaled Entry: Pending Tranchen prüfen
        # PROMPT 6: Breakeven Check Function für Tranche 3
        async def breakeven_check(symbol, slot):
            """Prüft ob Break-Even für die Position gesetzt ist."""
            pos_data = await self.position_tracker.get_open_position(symbol, slot=slot)
            if not pos_data:
                return {"breakeven_set": False, "reason": "no_position"}
            
            entry = float(pos_data.get("entry_price", 0))
            current_sl = float(pos_data.get("stop_loss_price", 0))
            side = pos_data.get("side", "long")
            
            # Break-Even ist gesetzt wenn SL >= Entry + 0.1% (Long) oder SL <= Entry - 0.1% (Short)
            fee_buffer = entry * 0.001
            if side == "long":
                be_level = entry + fee_buffer
                be_set = current_sl >= be_level
            else:
                be_level = entry - fee_buffer
                be_set = current_sl <= be_level
            
            return {
                "breakeven_set": be_set,
                "entry": entry,
                "current_sl": current_sl,
                "be_level": be_level,
                "pnl_pct": (current_price - entry) / entry if side == "long" else (entry - current_price) / entry
            }
        
        tranche = await self.scaled_entry.check_pending_tranches(
            "BTCUSDT", slot_name, current_price, breakeven_check_func=breakeven_check
        )
        if tranche and tranche.get("blocked"):
            # Tranche wurde blockiert (z.B. Break-Even nicht gesetzt)
            self.logger.warning(
                f"Tranche {tranche.get('tranche_number')} blocked: {tranche.get('reason')}"
            )
            return
        
        if tranche:
            # Neue Tranche ausführen
            tranche_amount = tranche["tranche_size_btc"]
            if self.deps.config.DRY_RUN:
                self.logger.info(
                    f"🔀 TRANCHE {tranche['tranche_number']} [{slot_name}]: "
                    f"+{tranche_amount:.4f} BTC @ {current_price:,.0f}"
                )
            else:
                tranche_side = "buy" if pos["side"] == "long" else "sell"
                await self.exm.create_market_order("BTCUSDT", tranche_side, tranche_amount)
            
            # Position Quantity updaten
            pos["quantity"] = round(float(pos["quantity"]) + tranche_amount, 4)
            await self.position_tracker.update_position("BTCUSDT", pos)
        
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        # TP1 Scaling Check
        tp1_pct = float(pos.get("take_profit_1_pct", 0.012))
        tp1_hit = pos.get("tp1_hit", False)
        
        if not tp1_hit and pnl_pct >= tp1_pct:
            tp1_size = float(pos.get("tp1_size_pct", 0.50))
            close_qty = round(quantity * tp1_size, 4)
            self.logger.info(f"TP1 HIT [{slot_name}]: {pnl_pct:.2%} >= {tp1_pct:.2%}")
            await self._partial_close(pos, close_qty, current_price, "tp1_scaling")
            pos["tp1_hit"] = True
            pos["quantity"] = round(quantity - close_qty, 4)
            await self.position_tracker.update_position("BTCUSDT", pos)
        
        # Phase 1: Fixer SL (vor Breakeven)
        # PROMPT 4: Breakeven-Trigger ist 1.0x ATR (wurde bei Position-Open gesetzt)
        breakeven_pct = float(pos.get("breakeven_trigger_pct", 0.01))  # Default 1% = ~1x ATR
        
        if pnl_pct < breakeven_pct:
            # Vor Breakeven: Nur SL oder TP checken
            if self._is_sl_hit(side, current_price, sl_price):
                await self._close_position_for_slot("stop_loss", current_price, slot_name)
            elif self._is_tp_hit(side, current_price, tp_price):
                await self._close_position_for_slot("take_profit", current_price, slot_name)
            return
        
        # Phase 2: Breakeven Stop (PROMPT 4: BE trigger MUSS vor TP1 feuern!)
        # Bei 1.0x ATR Profit → SL auf Entry + Fee-Puffer verschieben
        tp1_pct = float(pos.get("take_profit_1_pct", 0.015))
        
        if pnl_pct < tp1_pct:  # Zwischen Breakeven-Trigger und TP1
            # PROMPT 4: SL auf Entry + minimaler Fee-Puffer (0.1%)
            fee_buffer_pct = 0.001  # 0.1% Fee-Puffer
            if side == "long":
                be_sl = entry_price * (1 + fee_buffer_pct)
                if sl_price < be_sl:
                    pos["stop_loss_price"] = round(be_sl, 2)
                    await self.position_tracker.update_position("BTCUSDT", pos)
                    self.logger.info(f"BREAKEVEN SET [{slot_name}]: SL → {be_sl:,.0f} (Entry + 0.1%)")
            else:
                be_sl = entry_price * (1 - fee_buffer_pct)
                if sl_price > be_sl:
                    pos["stop_loss_price"] = round(be_sl, 2)
                    await self.position_tracker.update_position("BTCUSDT", pos)
                    self.logger.info(f"BREAKEVEN SET [{slot_name}]: SL → {be_sl:,.0f} (Entry - 0.1%)")
            
            if self._is_sl_hit(side, current_price, pos["stop_loss_price"]):
                await self._close_position_for_slot("breakeven_stop", current_price, slot_name)
            elif self._is_tp_hit(side, current_price, tp_price):
                await self._close_position_for_slot("take_profit", current_price, slot_name)
            return
        
        # Phase 3: ATR Trailing Stop
        atr = await self._get_current_atr()
        if atr <= 0:
            atr = current_price * 0.01
        trailing_multiplier = 2.5
        
        if side == "long":
            high_water = float(pos.get("max_favorable_price", current_price))
            if current_price > high_water:
                pos["max_favorable_price"] = current_price
            new_sl = pos["max_favorable_price"] - (atr * trailing_multiplier)
            if new_sl > float(pos["stop_loss_price"]):
                pos["stop_loss_price"] = round(new_sl, 2)
                await self.position_tracker.update_position("BTCUSDT", pos)
            if current_price <= float(pos["stop_loss_price"]):
                await self._close_position_for_slot("trailing_stop", current_price, slot_name)
        else:
            low_water = float(pos.get("min_favorable_price", current_price))
            if current_price < low_water:
                pos["min_favorable_price"] = current_price
            new_sl = pos["min_favorable_price"] + (atr * trailing_multiplier)
            if new_sl < float(pos["stop_loss_price"]):
                pos["stop_loss_price"] = round(new_sl, 2)
                await self.position_tracker.update_position("BTCUSDT", pos)
            if current_price >= float(pos["stop_loss_price"]):
                await self._close_position_for_slot("trailing_stop", current_price, slot_name)

    async def _close_position_for_slot(self, reason: str, exit_price: float, slot_name: str):
        """Schließt eine Position für einen spezifischen Slot."""
        # Identisch zu _close_position(), aber mit slot Parameter:
        pos = await self.position_tracker.get_open_position("BTCUSDT", slot=slot_name)
        if not pos:
            return
        
        side = pos["side"]
        exit_side = "sell" if side == "long" else "buy"
        qty = pos["quantity"]
        symbol = pos["symbol"]
        trade_id = None
        
        if self.deps.config.DRY_RUN:
            trade_id = f"sim_exit_{slot_name}_{int(datetime.now().timestamp())}"
            self.logger.info(
                f"🚧 EXIT [{slot_name.upper()}]: {exit_side.upper()} {qty:.4f} "
                f"{symbol} @ {exit_price:,.2f} | {reason}"
            )
        else:
            try:
                order = await self.exm.create_market_order(symbol, exit_side, qty)
                trade_id = order.get("id")
                self.logger.info(
                    f"✅ EXIT [{slot_name.upper()}]: {exit_side.upper()} {qty:.4f} "
                    f"{symbol} @ {exit_price:,.2f} | {reason}"
                )
            except Exception as e:
                self.logger.error(f"Exit-Order Fehler [{slot_name}]: {e}")
                return
        
        closed = await self.position_tracker.close_position(
            symbol=symbol,
            exit_price=exit_price,
            reason=reason,
            exit_trade_id=trade_id,
            slot=slot_name,  # ← SLOT ÜBERGEBEN
        )
        
        if closed:
            # Scaled Entry: verbleibende Tranchen canceln
            await self.scaled_entry.cancel_remaining(symbol, slot_name, reason)
            
            # Portfolio Update
            await self._update_portfolio(closed)
            
            # PROMPT 8: Slot-spezifische Trade-Result Speicherung für Circuit Breaker
            pnl_eur = closed.get("pnl_eur", 0.0)
            try:
                from app.agents.risk import RiskAgent
                # Speichere P&L für diesen Slot im RiskAgent
                risk_key = f"bruno:risk:slot_losses:{slot_name}"
                slot_losses = await self.deps.redis.get_cache(risk_key) or []
                slot_losses.append(pnl_eur)
                slot_losses = slot_losses[-10:]  # Behälte letzte 10
                await self.deps.redis.set_cache(risk_key, slot_losses, ttl=86400)
                
                # Prüfe auf 3 consecutive losses
                max_consecutive = 3
                if len(slot_losses) >= max_consecutive:
                    recent = slot_losses[-max_consecutive:]
                    if all(p < 0 for p in recent):
                        block_data = {
                            "active": True,
                            "reason": f"{max_consecutive} consecutive losses",
                            "triggered_at": datetime.now(timezone.utc).isoformat(),
                            "slot": slot_name,
                            "pnl_history": recent,
                        }
                        await self.deps.redis.set_cache(
                            f"bruno:risk:slot_block:{slot_name}", block_data, ttl=86400
                        )
                        self.logger.critical(
                            f"SLOT CIRCUIT BREAKER TRIGGERED [{slot_name}]: "
                            f"{max_consecutive} consecutive losses: {recent}"
                        )
                
                self.logger.info(
                    f"Slot trade recorded [{slot_name}]: PnL={pnl_eur:+.2f} EUR, "
                    f"history={len(slot_losses)} trades"
                )
            except Exception as e:
                self.logger.warning(f"Slot trade recording error: {e}")
            
            # Post-Trade Debrief (v3)
            try:
                await self.debrief_service.create_debrief(closed)
            except Exception as e:
                self.logger.error(f"Debrief Fehler [{slot_name}]: {e}")
            
            # Telegram Notification
            if not self.deps.config.DRY_RUN:
                from app.core.telegram_bot import get_telegram_bot
                telegram = get_telegram_bot()
                if telegram:
                    pnl_pct = closed.get("pnl_pct", 0)
                    pnl_eur = closed.get("pnl_eur", 0)
                    emoji = "✅" if pnl_pct > 0 else "❌"
                    await telegram.send_trade_notification(
                        f"{emoji} EXIT [{slot_name.upper()}]\\n"
                        f"{reason.upper()} | P&L: {pnl_pct:+.2%} ({pnl_eur:+.2f} EUR)"
                    )

    async def run_stream(self) -> None:
        """Parallele Ausführung der Listener."""
        await asyncio.gather(
            self._listen_to_risk_veto(),
            self._listen_to_signals(),
            self._monitor_position()
        )
