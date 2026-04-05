"""
Backtesting Framework - Bruno V2.2 Institutional

Hardcore Fee & Slippage Modell für institutionelle Validierung.
Simuliert realistische Handelskosten und Latenz-Effekte.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import text
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    """Konfiguration für Backtest."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    # Fee Modell (retail realistisch)
    taker_fee_bps: float = 5.0  # 0.05% für Market Orders (Binance Retail)
    maker_fee_bps: float = 2.0  # 0.02% für Limit Orders (TP1/TP2)
    slippage_bps: float = 3.0   # 0.03% realistische Retail-Latenz
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
    - TimescaleDB 1m Candle-Data als Ground Truth
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
        """Lädt 1m Candles aus TimescaleDB."""
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
            (
                exit_time,
                exit_price,
                exit_reason,
                tp1_hit,
                tp1_exit_time,
                tp1_exit_price,
            ) = await self._find_exit(
                signal, entry_time, candle_dict, config
            )
            
            if not exit_time:
                continue
            
            # Position sizing (1% Risk)
            atr = signal["atr"]
            risk_amount = config.initial_capital * 0.01  # 1% Risk
            stop_distance = abs(entry_price - signal["stop_loss"])
            quantity = risk_amount / stop_distance if stop_distance > 0 else 0.1
            
            tp1_quantity = quantity * config.tp1_size_pct if tp1_hit else 0.0
            remaining_quantity = max(0.0, quantity - tp1_quantity)

            # Kostenberechnung: Entry immer Taker, TP1 immer Maker, finaler Exit abhängig vom Exit-Grund.
            entry_fee = entry_price * quantity * (config.taker_fee_bps / 10000)

            tp1_fee = 0.0
            tp1_pnl = 0.0
            tp1_slippage = 0.0
            if tp1_hit and tp1_exit_price and tp1_quantity > 0:
                tp1_fee = tp1_exit_price * tp1_quantity * (config.maker_fee_bps / 10000)
                if signal["side"] == "long":
                    tp1_pnl = (tp1_exit_price - entry_price) * tp1_quantity
                else:
                    tp1_pnl = (entry_price - tp1_exit_price) * tp1_quantity
                tp1_slippage = abs(tp1_exit_price - entry_price) * tp1_quantity * (config.slippage_bps / 10000)

            exit_fee_rate = config.maker_fee_bps if exit_reason.startswith("take_profit") else config.taker_fee_bps
            exit_fee = exit_price * remaining_quantity * (exit_fee_rate / 10000)

            if signal["side"] == "long":
                gross_pnl = (exit_price - entry_price) * remaining_quantity
            else:
                gross_pnl = (entry_price - exit_price) * remaining_quantity

            slippage = abs(exit_price - entry_price) * remaining_quantity * (config.slippage_bps / 10000)
            total_cost = entry_fee + exit_fee + tp1_fee + slippage + tp1_slippage
            net_pnl = gross_pnl + tp1_pnl - total_cost
            
            trade = TradeResult(
                entry_time=entry_time,
                exit_time=exit_time,
                side=signal["side"],
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl_eur=gross_pnl,
                fee_eur=entry_fee + exit_fee + tp1_fee,
                slippage_eur=slippage + tp1_slippage,
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
        tp1_exit_time: Optional[datetime] = None
        tp1_exit_price: Optional[float] = None
        
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
                return current_time, exit_price, exit_reason, tp1_hit, tp1_exit_time, tp1_exit_price
            elif tp2_hit_in_candle:
                # TP2 getroffen
                return current_time, tp2_price, "take_profit_2", tp1_hit, tp1_exit_time, tp1_exit_price
            elif tp1_hit_in_candle:
                # TP1 erreicht - Scale-Out (Maker-Fee)
                tp1_hit = True
                tp1_exit_time = current_time
                tp1_exit_price = tp1_price
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
        return None, None, "no_exit", tp1_hit, tp1_exit_time, tp1_exit_price
    
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


class MockRedis:
    """Mock Redis for backtesting without side effects."""
    def __init__(self):
        self.data = {}
        # Backtest uses a real redis client internally sometimes, 
        # so we mock the .redis attribute if needed
        self.redis = self

    async def get_cache(self, key: str) -> Optional[dict]:
        val = self.data.get(key)
        if isinstance(val, str):
            return json.loads(val)
        return val

    async def set_cache(self, key: str, value: any, ttl: int = None):
        self.data[key] = value

    async def publish_message(self, channel: str, message: str):
        pass

    # For pipeline compatibility if it uses raw redis commands
    async def get(self, key: str):
        val = self.data.get(key)
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        return val

    async def set(self, key: str, value: str, ex: int = None):
        self.data[key] = value

    async def lpush(self, key: str, value: str):
        if key not in self.data:
            self.data[key] = []
        self.data[key].insert(0, value)

    async def ltrim(self, key: str, start: int, stop: int):
        if key in self.data:
            self.data[key] = self.data[key][start:stop+1]


class PipelineBacktester:
    """
    Walk-Forward Backtest using the real CompositeScorer pipeline.
    Validates the actual strategy logic against historical data.
    """
    def __init__(self, db_session_factory):
        self.db = db_session_factory
        self.mock_redis = MockRedis()
        self.logger = logging.getLogger("pipeline_backtester")

    async def run(self, start_date: datetime, end_date: datetime, initial_capital: float = 10000.0) -> Dict:
        self.logger.info(f"Starting Pipeline Backtest: {start_date} to {end_date}")
        
        # 1. Load Candles
        candles = await self._load_candles(start_date, end_date)
        if not candles:
            return {"error": "No candle data found"}

        # 2. Setup Static Macro State (GRSS neutral default)
        await self.mock_redis.set_cache("bruno:context:grss", {
            "GRSS_Score": 55.0,
            "GRSS_Score_Raw": 55.0,
            "VIX": 18.0,
            "Macro_Status": "BULLISH",
            "DVOL": 45.0,
            "Long_Short_Ratio": 1.1,
            "Active_Event": None
        })

        # 3. Setup Dummy Flow
        await self.mock_redis.set_cache("bruno:quant:micro", {
            "price": 0.0,
            "CVD": 0.0,
            "OFI_Buy_Pressure": 0.5,
            "OFI_Mean_Imbalance": 1.0
        })

        # 4. Simulation Loop
        trades = []
        
        from app.services.composite_scorer import CompositeScorer
        scorer = CompositeScorer(self.mock_redis)

        i = 200
        while i < len(candles):
            current_candle = candles[i]
            price = current_candle["close"]

            # Every 60 minutes (or at start), refresh TA Snapshot
            if i % 60 == 0 or i == 200:
                snapshot = await self._create_ta_snapshot(candles[:i+1])
                await self.mock_redis.set_cache("bruno:ta:snapshot", snapshot)
            
            # Update flow price
            flow = await self.mock_redis.get_cache("bruno:quant:micro")
            flow["price"] = price
            await self.mock_redis.set_cache("bruno:quant:micro", flow)

            # Check Signal
            signal = await scorer.score()
            
            if signal.should_trade:
                # Execute Trade Simulation
                trade_result = await self._simulate_trade(signal, candles[i:], initial_capital)
                if trade_result:
                    trades.append(trade_result)
                    # Skip candles until trade exit
                    exit_time = trade_result.exit_time
                    while i < len(candles) and candles[i]["time"] < exit_time:
                        i += 1
                    continue # Skip the i += 1 at the end of loop

            i += 1

        # 5. Calculate Performance
        performance = await self._calculate_performance(trades, initial_capital)
        
        # Store result in real redis for dashboard
        try:
            from app.core.redis_client import redis_client
            await redis_client.set_cache("bruno:backtest:latest", performance)
        except:
            pass

        return performance

    async def _load_candles(self, start: datetime, end: datetime) -> List[Dict]:
        async with self.db() as session:
            result = await session.execute(text("""
                SELECT time, open, high, low, close, volume
                FROM market_candles
                WHERE symbol = 'BTCUSDT' AND time >= :start AND time <= :end
                ORDER BY time ASC
            """), {"start": start, "end": end})
            return [{"time": r[0], "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in result.fetchall()]

    async def _create_ta_snapshot(self, window_candles: List[Dict]) -> Dict:
        closes = [c["close"] for c in window_candles]
        price = closes[-1]
        
        def ema(data, period):
            if len(data) < period: return data[-1]
            alpha = 2 / (period + 1)
            val = data[0]
            for p in data[1:]:
                val = alpha * p + (1 - alpha) * val
            return val

        ema9 = ema(closes, 9)
        ema21 = ema(closes, 21)
        ema50 = ema(closes, 50)
        ema200 = ema(closes, 200)
        
        stack = "mixed"
        if ema9 > ema21 > ema50 > ema200: stack = "perfect_bull"
        elif ema9 < ema21 < ema50 < ema200: stack = "perfect_bear"
        
        atr = 0.01 * price
        if len(window_candles) > 14:
            tr_sum = 0
            for k in range(len(window_candles)-14, len(window_candles)):
                c = window_candles[k]
                pc = window_candles[k-1]["close"]
                tr = max(c["high"]-c["low"], abs(c["high"]-pc), abs(c["low"]-pc))
                tr_sum += tr
            atr = tr_sum / 14

        return {
            "price": price,
            "atr_14": atr,
            "trend": {"ema_stack": stack, "strength": 0.8 if "perfect" in stack else 0.4},
            "ta_score": {"score": 60.0 if "bull" in stack else -60.0 if "bear" in stack else 0.0, "mtf_aligned": True},
            "mtf": {"alignment_score": 1.0 if "bull" in stack else -1.0 if "bear" in stack else 0.0}
        }

    async def _simulate_trade(self, signal, candles: List[Dict], initial_capital: float) -> Optional[TradeResult]:
        if len(candles) < 2: return None
        
        entry_price_raw = candles[0]["close"]
        # Fees in bps
        taker_fee = 0.0004
        maker_fee = 0.0001
        slippage = 0.00005 # 0.5 bps
        
        # Entry (always taker)
        entry_price = entry_price_raw * (1 + slippage) if signal.direction == "long" else entry_price_raw * (1 - slippage)
        entry_fee = entry_price * taker_fee
        
        # SL/TP in percent from Signal
        sl_pct = signal.stop_loss_pct
        tp1_pct = signal.take_profit_1_pct
        tp2_pct = signal.take_profit_2_pct
        
        sl_price = entry_price_raw * (1 - sl_pct) if signal.direction == "long" else entry_price_raw * (1 + sl_pct)
        tp1_price = entry_price_raw * (1 + tp1_pct) if signal.direction == "long" else entry_price_raw * (1 - tp1_pct)
        tp2_price = entry_price_raw * (1 + tp2_pct) if signal.direction == "long" else entry_price_raw * (1 - tp2_pct)
        
        tp1_hit = False
        tp1_exit_time = None
        tp1_exit_price = None
        tp1_pnl = 0.0
        tp1_fee = 0.0
        
        # We assume 1.0 unit for simplicity in percent calculation, 
        # then multiply by capital at the end if needed.
        # But TradeResult expects pnl_eur, net_pnl_eur etc.
        
        for candle in candles[1:]:
            high, low = candle["high"], candle["low"]
            
            # SL check (pessimistic: SL before TP if both hit)
            if (signal.direction == "long" and low <= sl_price) or (signal.direction == "short" and high >= sl_price):
                exit_price = sl_price
                exit_reason = "stop_loss" if not tp1_hit else "trailing_stop"
                exit_fee = exit_price * taker_fee # Stop is always taker
                
                # Calculate PNL
                if signal.direction == "long":
                    gross_pnl = (exit_price - entry_price)
                else:
                    gross_pnl = (entry_price - exit_price)
                
                return TradeResult(
                    entry_time=candles[0]["time"],
                    exit_time=candle["time"],
                    side=signal.direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=1.0,
                    pnl_eur=gross_pnl,
                    fee_eur=entry_fee + exit_fee + tp1_fee,
                    slippage_eur=entry_price_raw * slippage + abs(exit_price - entry_price_raw) * 0.0, # slippage already in entry_price
                    total_cost_eur=entry_fee + exit_fee + tp1_fee,
                    net_pnl_eur=gross_pnl + tp1_pnl - (entry_fee + exit_fee + tp1_fee),
                    hold_time_hours=(candle["time"] - candles[0]["time"]).total_seconds() / 3600,
                    exit_reason=exit_reason
                )
            
            # TP2 check
            if (signal.direction == "long" and high >= tp2_price) or (signal.direction == "short" and low <= tp2_price):
                exit_price = tp2_price
                exit_fee = exit_price * maker_fee # TP is always maker
                
                if signal.direction == "long":
                    gross_pnl = (exit_price - entry_price)
                else:
                    gross_pnl = (entry_price - exit_price)
                    
                return TradeResult(
                    entry_time=candles[0]["time"],
                    exit_time=candle["time"],
                    side=signal.direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=1.0,
                    pnl_eur=gross_pnl,
                    fee_eur=entry_fee + exit_fee + tp1_fee,
                    slippage_eur=0.0,
                    total_cost_eur=entry_fee + exit_fee + tp1_fee,
                    net_pnl_eur=gross_pnl + tp1_pnl - (entry_fee + exit_fee + tp1_fee),
                    hold_time_hours=(candle["time"] - candles[0]["time"]).total_seconds() / 3600,
                    exit_reason="take_profit_2"
                )

            # TP1 check (Scale out 50%)
            if not tp1_hit:
                if (signal.direction == "long" and high >= tp1_price) or (signal.direction == "short" and low <= tp1_price):
                    tp1_hit = True
                    tp1_exit_time = candle["time"]
                    tp1_exit_price = tp1_price
                    tp1_fee = tp1_price * 0.5 * maker_fee
                    
                    if signal.direction == "long":
                        tp1_pnl = (tp1_price - entry_price) * 0.5
                    else:
                        tp1_pnl = (entry_price - tp1_price) * 0.5
                    
                    # Entry price stays same for the remaining 50%, but we effectively closed half
                    # To keep it simple, we just adjust the final calculation.
                    # Move SL to breakeven
                    sl_price = entry_price_raw * (1.001 if signal.direction == "long" else 0.999)

        return None

    async def _calculate_performance(self, trades: List[TradeResult], initial_capital: float) -> Dict:
        if not trades:
            return {
                "total_trades": 0,
                "total_pnl_eur": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0
            }
        
        total_net_pnl_pct = sum(t.net_pnl_eur for t in trades)
        winning_trades = [t for t in trades if t.net_pnl_eur > 0]
        losing_trades = [t for t in trades if t.net_pnl_eur <= 0]
        
        win_rate = len(winning_trades) / len(trades) * 100
        
        gross_profit = sum(t.net_pnl_eur for t in winning_trades)
        gross_loss = abs(sum(t.net_pnl_eur for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.9
        
        # Simple Max Drawdown calculation
        peak = 0.0
        current_pnl = 0.0
        max_dd = 0.0
        for t in trades:
            current_pnl += t.net_pnl_eur
            if current_pnl > peak:
                peak = current_pnl
            dd = peak - current_pnl
            if dd > max_dd:
                max_dd = dd
        
        return {
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "total_pnl_eur": round(initial_capital * total_net_pnl_pct, 2),
            "max_drawdown_pct": round(max_dd * 100, 2), # Simplified
            "avg_pnl_pct": round((total_net_pnl_pct / len(trades)) * 100, 4),
            "trades": [
                {
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "side": t.side,
                    "pnl_pct": round(t.net_pnl_eur * 100, 2),
                    "exit_reason": t.exit_reason
                } for t in trades
            ]
        }
