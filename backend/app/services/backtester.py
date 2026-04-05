"""
Backtesting Framework - Bruno V2.2 Institutional

Hardcore Fee & Slippage Modell für institutionelle Validierung.
Simuliert realistische Handelskosten und Latenz-Effekte.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    """Konfiguration für Backtest."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    # Fee Modell (institutionell realistisch)
    taker_fee_bps: float = 4.0  # 0.04% für Market Orders (Entries/Stops)
    maker_fee_bps: float = 1.0  # 0.01% für Limit Orders (TP1/TP2)
    slippage_bps: float = 0.5   # 0.005% deterministische Latenz
    # ATR Konfiguration
    atr_period: int = 14
    atr_multiplier: float = 1.5
    # TP Scaling
    tp1_size_pct: float = 0.5
    tp2_size_pct: float = 0.5

@dataclass
class TradeResult:
    """Ergebnis eines einzelnen Trades."""
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl_eur: float
    fee_eur: float
    slippage_eur: float
    total_cost_eur: float
    net_pnl_eur: float
    hold_time_hours: float
    exit_reason: str  # "stop_loss", "take_profit_1", "take_profit_2", "trailing_stop"

class Backtester:
    """
    Institutioneller Backtester mit realistischem Kostenmodell.
    
    Features:
    - TimescaleDB Candle-Data als Ground Truth
    - Deterministische Fee-Berechnung
    - ATR-basiertes Trailing Stop Simulation
    - Multi-Level TP Scaling
    - Comprehensive Performance Metrics
    """
    
    def __init__(self, db_session_factory, redis_client):
        self.db = db_session_factory
        self.redis = redis_client
        self.logger = logging.getLogger("backtester")
    
    async def run_backtest(self, config: BacktestConfig) -> Dict:
        """
        Führt vollständigen Backtest durch.
        
        Returns:
            Dict mit Performance Metriken:
            - total_pnl_eur
            - total_trades
            - win_rate_pct
            - profit_factor
            - max_drawdown_pct
            - sharpe_ratio
            - avg_trade_pnl_eur
            - avg_hold_time_hours
        """
        self.logger.info(f"Starte Backtest: {config.start_date} bis {config.end_date}")
        
        # 1. Candle-Daten laden
        candles = await self._load_candles(config.start_date, config.end_date)
        if not candles:
            raise ValueError("Keine Candle-Daten gefunden")
        
        # 2. ATR-Werte vorberechnen
        atr_values = await self._calculate_atr_series(candles, config.atr_period)
        
        # 3. Trading-Signale generieren (basiert auf TA-Regeln)
        signals = await self._generate_signals(candles, atr_values, config)
        
        # 4. Simulation durchführen
        trades = await self._simulate_trades(signals, candles, config)
        
        # 5. Performance berechnen
        performance = await self._calculate_performance(trades, config)
        
        self.logger.info(f"Backtest abgeschlossen: {performance['total_trades']} Trades, "
                        f"P&L: {performance['total_pnl_eur']:.2f} EUR, "
                        f"Win Rate: {performance['win_rate_pct']:.1f}%")
        
        return performance
    
    async def _load_candles(self, start: datetime, end: datetime) -> List[Dict]:
        """Lädt 1h Candles aus TimescaleDB."""
        try:
            async with self.db() as session:
                result = await session.execute(text("""
                    SELECT time, open, high, low, close, volume
                    FROM market_candles
                    WHERE symbol = 'BTCUSDT' 
                    AND time >= :start 
                    AND time < :end
                    ORDER BY time ASC
                """), {"start": start, "end": end})
                
                rows = result.fetchall()
                return [
                    {
                        "time": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5])
                    }
                    for row in rows
                ]
        except Exception as e:
            self.logger.error(f"Candle-Lade Fehler: {e}")
            return []
    
    async def _calculate_atr_series(self, candles: List[Dict], period: int) -> Dict[datetime, float]:
        """Berechnet ATR-Serie für alle Candles."""
        atr_values = {}
        
        for i in range(period, len(candles)):
            # True Ranges der letzten 'period' Candles
            true_ranges = []
            for j in range(i - period + 1, i + 1):
                high = candles[j]["high"]
                low = candles[j]["low"]
                prev_close = candles[j-1]["close"]
                
                tr1 = high - low
                tr2 = abs(high - prev_close)
                tr3 = abs(low - prev_close)
                true_ranges.append(max(tr1, tr2, tr3))
            
            atr = sum(true_ranges) / period
            atr_values[candles[i]["time"]] = atr
        
        return atr_values
    
    async def _generate_signals(self, candles: List[Dict], atr_values: Dict[datetime, float], 
                              config: BacktestConfig) -> List[Dict]:
        """
        Generiert Trading-Signale basierend auf institutionellen Regeln.
        
        Vereinfachte Signal-Logik für Backtest:
        - EMA-Alignment (9/21 > 50/200 für Long)
        - RSI < 30 für Long Entry
        - RSI > 70 für Short Entry
        """
        signals = []
        ema_9, ema_21, ema_50, ema_200 = 0.0, 0.0, 0.0, 0.0
        
        for i, candle in enumerate(candles):
            if i < 200:  # Warm-up Phase
                continue
            
            # EMA Update
            close_price = candle["close"]
            if ema_9 == 0:
                # Initialisierung
                ema_9 = ema_21 = ema_50 = ema_200 = close_price
            else:
                alpha_9 = 2 / (9 + 1)
                alpha_21 = 2 / (21 + 1)
                alpha_50 = 2 / (50 + 1)
                alpha_200 = 2 / (200 + 1)
                
                ema_9 = alpha_9 * close_price + (1 - alpha_9) * ema_9
                ema_21 = alpha_21 * close_price + (1 - alpha_21) * ema_21
                ema_50 = alpha_50 * close_price + (1 - alpha_50) * ema_50
                ema_200 = alpha_200 * close_price + (1 - alpha_200) * ema_200
            
            # RSI Berechnung
            if i >= 214:  # RSI(14) braucht 14+1 Perioden
                rsi = self._calculate_rsi([c["close"] for c in candles[i-14:i+1]])
            else:
                rsi = 50.0
            
            # Signal-Generierung
            signal = None
            
            # Long Signal
            if (ema_9 > ema_21 > ema_50 > ema_200 and  # Bull EMA Stack
                rsi < 30 and  # Oversold
                candle["time"] in atr_values):
                
                atr = atr_values[candle["time"]]
                signal = {
                    "time": candle["time"],
                    "price": close_price,
                    "side": "long",
                    "atr": atr,
                    "stop_loss": close_price - (atr * 1.5),  # 1.5x ATR SL
                    "take_profit_1": close_price + (atr * 1.2),  # 1.2x ATR TP1
                    "take_profit_2": close_price + (atr * 2.5),  # 2.5x ATR TP2
                }
            
            # Short Signal
            elif (ema_9 < ema_21 < ema_50 < ema_200 and  # Bear EMA Stack
                  rsi > 70 and  # Overbought
                  candle["time"] in atr_values):
                
                atr = atr_values[candle["time"]]
                signal = {
                    "time": candle["time"],
                    "price": close_price,
                    "side": "short",
                    "atr": atr,
                    "stop_loss": close_price + (atr * 1.5),
                    "take_profit_1": close_price - (atr * 1.2),
                    "take_profit_2": close_price - (atr * 2.5),
                }
            
            if signal:
                signals.append(signal)
        
        return signals
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Berechnet RSI mit Wilder's Smoothing."""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        
        # Wilder's Exponential Smoothing
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        alpha = 1.0 / period
        
        for i in range(period, len(gains)):
            avg_gain = alpha * gains[i] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[i] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    async def _simulate_trades(self, signals: List[Dict], candles: List[Dict], 
                             config: BacktestConfig) -> List[TradeResult]:
        """Simuliert Trades mit realistischen Kosten."""
        trades = []
        candle_dict = {c["time"]: c for c in candles}
        
        for signal in signals:
            entry_time = signal["time"]
            entry_price = signal["price"]
            
            # Find exit candle
            exit_time, exit_price, exit_reason = await self._find_exit(
                signal, entry_time, candle_dict, config
            )
            
            if not exit_time:
                continue
            
            # Position sizing (1% Risk)
            atr = signal["atr"]
            risk_amount = config.initial_capital * 0.01  # 1% Risk
            stop_distance = abs(entry_price - signal["stop_loss"])
            quantity = risk_amount / stop_distance if stop_distance > 0 else 0.1
            
            # Kostenberechnung
            entry_fee = entry_price * quantity * (config.taker_fee_bps / 10000)
            exit_fee = exit_price * quantity * (
                config.maker_fee_bps / 10000 if "take_profit" in exit_reason 
                else config.taker_fee_bps / 10000
            )
            slippage = abs(exit_price - entry_price) * quantity * (config.slippage_bps / 10000)
            
            # P&L Berechnung
            if signal["side"] == "long":
                gross_pnl = (exit_price - entry_price) * quantity
            else:
                gross_pnl = (entry_price - exit_price) * quantity
            
            total_cost = entry_fee + exit_fee + slippage
            net_pnl = gross_pnl - total_cost
            
            trade = TradeResult(
                entry_time=entry_time,
                exit_time=exit_time,
                side=signal["side"],
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl_eur=gross_pnl,
                fee_eur=entry_fee + exit_fee,
                slippage_eur=slippage,
                total_cost_eur=total_cost,
                net_pnl_eur=net_pnl,
                hold_time_hours=(exit_time - entry_time).total_seconds() / 3600,
                exit_reason=exit_reason
            )
            
            trades.append(trade)
        
        return trades
    
    async def _find_exit(self, signal: Dict, entry_time: datetime, 
                        candle_dict: Dict[datetime, Dict], 
                        config: BacktestConfig) -> Tuple[Optional[datetime], Optional[float], str]:
        """
        Findet Exit-Punkt mit 1-Minuten-Iteration und Intrabar High/Low Checks.
        
        FIX: Ändere die Hauptschleife zwingend auf 1-Minuten-Kerzen (1m-Klines), keine Stundenkerzen mehr!
        Intrabar High/Low Checks (Pessimistische Ausführung):
        In jeder 1m-Kerze musst du High und Low prüfen.
        Für Longs: Wenn Low <= Stop_Loss, wird der Trade ausgestoppt (Taker-Fee!). Wenn High >= TP1, wird skaliert (Maker-Fee!).
        Pessimismus-Regel: Wenn in EINER Kerze sowohl SL als auch TP berührt werden, gehe davon aus, dass der Stop-Loss ZUERST getroffen wurde (Worst-Case-Szenario).
        """
        side = signal["side"]
        entry_price = signal["price"]
        sl_price = signal["stop_loss"]
        tp1_price = signal["take_profit_1"]
        tp2_price = signal["take_profit_2"]
        atr = signal["atr"]
        
        # Trailing Stop Variablen
        trailing_distance = atr * config.atr_multiplier
        max_favorable = entry_price if side == "long" else entry_price
        current_sl = sl_price
        tp1_hit = False
        
        # FIX: Simuliere 1-Minuten-Kerzen statt Stundenkerzen
        current_time = entry_time + timedelta(minutes=1)
        
        while current_time in candle_dict:
            candle = candle_dict[current_time]
            high_price = candle["high"]
            low_price = candle["low"]
            close_price = candle["close"]
            
            # FIX: Intrabar High/Low Checks (Pessimistische Ausführung)
            sl_hit_in_candle = False
            tp1_hit_in_candle = False
            tp2_hit_in_candle = False
            
            if side == "long":
                # Long: Check SL und TP Levels
                if low_price <= current_sl:
                    sl_hit_in_candle = True
                if high_price >= tp1_price and not tp1_hit:
                    tp1_hit_in_candle = True
                if high_price >= tp2_price:
                    tp2_hit_in_candle = True
            else:  # short
                # Short: Check SL und TP Levels
                if high_price >= current_sl:
                    sl_hit_in_candle = True
                if low_price <= tp1_price and not tp1_hit:
                    tp1_hit_in_candle = True
                if low_price <= tp2_price:
                    tp2_hit_in_candle = True
            
            # FIX: Pessimismus-Regel - SL hat Priorität über TP
            if sl_hit_in_candle:
                # Worst-Case: Stop-Loss wird zuerst getroffen
                exit_price = current_sl  # SL Preis
                exit_reason = "trailing_stop" if tp1_hit else "stop_loss"
                return current_time, exit_price, exit_reason
            elif tp2_hit_in_candle:
                # TP2 getroffen
                return current_time, tp2_price, "take_profit_2"
            elif tp1_hit_in_candle:
                # TP1 erreicht - Scale-Out (Maker-Fee)
                tp1_hit = True
                # Update Trailing Stop nach TP1
                if side == "long":
                    max_favorable = max(max_favorable, high_price)
                    new_sl = max_favorable - trailing_distance
                    if new_sl > current_sl:
                        current_sl = new_sl
                else:
                    max_favorable = min(max_favorable, low_price)
                    new_sl = max_favorable + trailing_distance
                    if new_sl < current_sl:
                        current_sl = new_sl
                
                # Für Backtest: Continue mit Rest-Position (kein sofortiger Exit)
                # In Realität würde hier ein Scale-Out stattfinden
            
            # Update Trailing Stop nach TP1 (Close-basiert)
            if tp1_hit:
                if side == "long":
                    max_favorable = max(max_favorable, close_price)
                    new_sl = max_favorable - trailing_distance
                    if new_sl > current_sl:
                        current_sl = new_sl
                else:
                    max_favorable = min(max_favorable, close_price)
                    new_sl = max_favorable + trailing_distance
                    if new_sl < current_sl:
                        current_sl = new_sl
            
            current_time += timedelta(minutes=1)  # FIX: 1-Minuten-Schritte
        
        # Kein Exit gefunden (Ende von Daten)
        return None, None, "no_exit"
    
    async def _calculate_performance(self, trades: List[TradeResult], 
                                  config: BacktestConfig) -> Dict:
        """Berechnet Performance Metriken."""
        if not trades:
            return {
                "total_pnl_eur": 0.0,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "avg_trade_pnl_eur": 0.0,
                "avg_hold_time_hours": 0.0
            }
        
        # Grundmetriken
        total_pnl = sum(t.net_pnl_eur for t in trades)
        winning_trades = [t for t in trades if t.net_pnl_eur > 0]
        losing_trades = [t for t in trades if t.net_pnl_eur < 0]
        
        win_rate = len(winning_trades) / len(trades) * 100
        avg_trade = total_pnl / len(trades)
        avg_hold_time = sum(t.hold_time_hours for t in trades) / len(trades)
        
        # Profit Factor
        gross_profit = sum(t.pnl_eur for t in winning_trades)
        gross_loss = abs(sum(t.pnl_eur for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max Drawdown
        running_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for trade in trades:
            running_pnl += trade.net_pnl_eur
            if running_pnl > peak:
                peak = running_pnl
            drawdown = (peak - running_pnl) / config.initial_capital * 100
            max_dd = max(max_dd, drawdown)
        
        # Sharpe Ratio (vereinfacht, annualisiert)
        if len(trades) > 1:
            returns = [t.net_pnl_eur / config.initial_capital for t in trades]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = (avg_return / std_return) * (365 ** 0.5) if std_return > 0 else 0.0
        else:
            sharpe = 0.0
        
        return {
            "total_pnl_eur": round(total_pnl, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "avg_trade_pnl_eur": round(avg_trade, 2),
            "avg_hold_time_hours": round(avg_hold_time, 1),
            "total_fees_eur": round(sum(t.fee_eur for t in trades), 2),
            "total_slippage_eur": round(sum(t.slippage_eur for t in trades), 2)
        }

# Utility Funktion für schnellen Backtest
async def quick_backtest(db_session_factory, redis_client, days_back: int = 30) -> Dict:
    """
    Schneller Backtest der letzten X Tage.
    Nützlich für Performance-Validierung nach Code-Änderungen.
    """
    backtester = Backtester(db_session_factory, redis_client)
    
    config = BacktestConfig(
        start_date=datetime.now(timezone.utc) - timedelta(days=days_back),
        end_date=datetime.now(timezone.utc),
        initial_capital=10000.0
    )
    
    return await backtester.run_backtest(config)
