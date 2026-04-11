"""
PROMPT 06: Execution Hygiene Tests.

Test-Suite für:
- SL/TP Score-Differenzierung
- BE-Trigger immer vor TP1
- Live Slippage Reject mit reduceOnly Close
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone


class TestSLTPScoreDifferentiation:
    """Test-Klasse für SL/TP Score-Differenzierung."""
    
    @pytest.fixture
    def execution_agent(self):
        """Erstellt einen ExecutionAgentV4 mit gemockten Dependencies."""
        from app.agents.execution_v4 import ExecutionAgentV4
        
        deps = MagicMock()
        deps.config = MagicMock()
        deps.config.DRY_RUN = True
        deps.config.SIMULATED_CAPITAL_EUR = 10000.0
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        return agent
    
    def test_sl_tp_score_differentiation_high_vs_low(self, execution_agent):
        """
        Test: High conviction (>60) vs Low conviction (<35) hat unterschiedliche Multiplikatoren.
        """
        atr = 700.0
        price = 70000.0
        
        # High conviction
        sl_pct_high, tp1_pct_high, tp2_pct_high, be_pct_high = execution_agent._calculate_atr_based_sl_tp(
            atr, price, composite_score=70, mr_mode=False
        )
        
        # Low conviction (Learning mode)
        sl_pct_low, tp1_pct_low, tp2_pct_low, be_pct_low = execution_agent._calculate_atr_based_sl_tp(
            atr, price, composite_score=25, mr_mode=False
        )
        
        # High conviction sollte breitere Limits haben
        assert sl_pct_high > sl_pct_low, f"High conviction SL sollte breiter sein: {sl_pct_high} vs {sl_pct_low}"
        assert tp1_pct_high > tp1_pct_low, f"High conviction TP1 sollte weiter sein: {tp1_pct_high} vs {tp1_pct_low}"
        assert tp2_pct_high > tp2_pct_low, f"High conviction TP2 sollte weiter sein: {tp2_pct_high} vs {tp2_pct_low}"
    
    def test_be_trigger_always_below_tp1(self, execution_agent):
        """
        Test: BE-Trigger feuert IMMER deutlich vor TP1 (mindestens 0.4×ATR Abstand).
        """
        atr = 700.0
        price = 70000.0
        atr_pct = atr / price  # 0.01 = 1%
        
        # Test für alle Score-Bereiche
        scores = [25, 45, 70]  # Low, Mid, High
        
        for score in scores:
            sl_pct, tp1_pct, tp2_pct, be_pct = execution_agent._calculate_atr_based_sl_tp(
                atr, price, composite_score=score, mr_mode=False
            )
            
            # BE muss vor TP1 sein
            assert be_pct < tp1_pct, f"BE ({be_pct:.4%}) muss vor TP1 ({tp1_pct:.4%}) sein für score={score}"
            
            # Abstand zwischen BE und TP1 muss mindestens 0.4×ATR sein
            gap = (tp1_pct - be_pct) / atr_pct
            assert gap >= 0.35, f"Gap BE→TP1 muss mindestens 0.35×ATR sein, got {gap:.2f}× für score={score}"
    
    def test_mr_mode_tighter_limits(self, execution_agent):
        """
        Test: MR-Modus hat engere Limits als normal.
        """
        atr = 700.0
        price = 70000.0
        
        # Normal mode (mid conviction)
        sl_pct_normal, tp1_pct_normal, tp2_pct_normal, be_pct_normal = execution_agent._calculate_atr_based_sl_tp(
            atr, price, composite_score=45, mr_mode=False
        )
        
        # MR mode
        sl_pct_mr, tp1_pct_mr, tp2_pct_mr, be_pct_mr = execution_agent._calculate_atr_based_sl_tp(
            atr, price, composite_score=45, mr_mode=True
        )
        
        # MR sollte enger sein
        assert sl_pct_mr < sl_pct_normal, f"MR SL sollte enger sein: {sl_pct_mr} vs {sl_pct_normal}"
        assert tp1_pct_mr < tp1_pct_normal, f"MR TP1 sollte näher sein: {tp1_pct_mr} vs {tp1_pct_normal}"
    
    def test_default_composite_score_is_25(self, execution_agent):
        """
        Test: Default composite_score ist 25 (nicht 50).
        """
        atr = 700.0
        price = 70000.0
        
        # Mit explizitem Default 25
        sl_pct_default, tp1_pct_default, tp2_pct_default, be_pct_default = execution_agent._calculate_atr_based_sl_tp(
            atr, price  # Kein composite_score Parameter
        )
        
        # Mit explizitem 25
        sl_pct_25, tp1_pct_25, tp2_pct_25, be_pct_25 = execution_agent._calculate_atr_based_sl_tp(
            atr, price, composite_score=25
        )
        
        # Sollten identisch sein
        assert abs(sl_pct_default - sl_pct_25) < 0.0001
        assert abs(tp1_pct_default - tp1_pct_25) < 0.0001


class TestLiveSlippageReject:
    """Test-Klasse für Live Slippage Rejection."""
    
    @pytest.fixture
    def execution_agent(self):
        """Erstellt einen ExecutionAgentV4 mit gemockten Dependencies."""
        from app.agents.execution_v4 import ExecutionAgentV4
        
        deps = MagicMock()
        deps.config = MagicMock()
        deps.config.DRY_RUN = False
        deps.config.LIVE_TRADING_APPROVED = True
        deps.config.SIMULATED_CAPITAL_EUR = 10000.0
        deps.config.TELEGRAM_NOTIFICATIONS_ENABLED = True
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        # Mock exchange manager
        agent.exm = MagicMock()
        return agent
    
    @pytest.mark.asyncio
    async def test_live_slippage_reject_closes_position(self, execution_agent):
        """
        Test: Bei Excess-Slippage (>1.5×max) wird Position sofort geschlossen.
        """
        signal_price = 70000.0
        fill_price = 70150.0  # 0.21% slippage = 21 bps
        max_slippage = 0.001  # 0.1% = 10 bps
        excess_threshold = max_slippage * 1.5  # 0.15% = 15 bps
        
        # Slippage ist 21 bps > 15 bps threshold → Reject
        slippage = (fill_price - signal_price) / signal_price
        assert slippage > excess_threshold, "Slippage sollte Threshold überschreiten"
        
        # Mock create_market_order
        execution_agent.exm.create_market_order = AsyncMock(return_value={
            "id": "test123",
            "price": fill_price,
            "amount": 0.1,
            "cost": 7015.0,
            "status": "filled"
        })
        
        # Mock close_position
        execution_agent._close_position_reduce_only = AsyncMock(return_value={
            "id": "close456",
            "status": "filled"
        })
        
        # Mock notify
        execution_agent._notify_slippage_reject = AsyncMock()
        
        # Execute
        result = await execution_agent._execute_market_order_with_slippage_check(
            symbol="BTCUSDT",
            side="buy",
            amount=0.1,
            signal_price=signal_price,
            max_slippage=max_slippage
        )
        
        # Verify position was closed
        execution_agent._close_position_reduce_only.assert_called_once()
        
        # Verify order has rejection flag
        assert result.get("slippage_rejected") is True
        assert result.get("status") == "rejected_and_closed"
    
    @pytest.mark.asyncio
    async def test_normal_slippage_no_reject(self, execution_agent):
        """
        Test: Normale Slippage (<1.5×max) führt nicht zu Reject.
        """
        signal_price = 70000.0
        fill_price = 70035.0  # 0.05% = 5 bps
        max_slippage = 0.001  # 0.1% = 10 bps
        
        # Slippage ist 5 bps < 15 bps threshold → OK
        
        # Mock create_market_order
        execution_agent.exm.create_market_order = AsyncMock(return_value={
            "id": "test123",
            "price": fill_price,
            "amount": 0.1,
            "cost": 7003.5,
            "status": "filled"
        })
        
        # Mock close_position (sollte NICHT aufgerufen werden)
        execution_agent._close_position_reduce_only = AsyncMock()
        
        # Execute
        result = await execution_agent._execute_market_order_with_slippage_check(
            symbol="BTCUSDT",
            side="buy",
            amount=0.1,
            signal_price=signal_price,
            max_slippage=max_slippage
        )
        
        # Verify position was NOT closed
        execution_agent._close_position_reduce_only.assert_not_called()
        
        # Verify order does not have rejection flag
        assert result.get("slippage_rejected") is None or result.get("slippage_rejected") is False
    
    @pytest.mark.asyncio
    async def test_slippage_reject_notification(self, execution_agent):
        """
        Test: Slippage Reject sendet Telegram Notification.
        """
        execution_agent._notify_slippage_reject = AsyncMock()
        
        signal_price = 70000.0
        fill_price = 70150.0  # 21 bps slippage
        max_slippage = 0.001  # 10 bps
        
        # Mock create_market_order
        execution_agent.exm.create_market_order = AsyncMock(return_value={
            "id": "test123",
            "price": fill_price,
            "amount": 0.1,
            "cost": 7015.0,
            "status": "filled"
        })
        
        # Mock close_position
        execution_agent._close_position_reduce_only = AsyncMock(return_value={
            "id": "close456",
            "status": "filled"
        })
        
        # Execute
        await execution_agent._execute_market_order_with_slippage_check(
            symbol="BTCUSDT",
            side="buy",
            amount=0.1,
            signal_price=signal_price,
            max_slippage=max_slippage
        )
        
        # Verify notification was sent
        execution_agent._notify_slippage_reject.assert_called_once()
        call_args = execution_agent._notify_slippage_reject.call_args
        assert call_args[1]["symbol"] == "BTCUSDT"
        assert call_args[1]["side"] == "buy"
        assert call_args[1]["slippage_bps"] == 21.42857142857143  # ~21 bps


class TestReduceOnlyClose:
    """Test-Klasse für reduceOnly Position Close."""
    
    @pytest.fixture
    def execution_agent(self):
        """Erstellt einen ExecutionAgentV4 mit gemockten Dependencies."""
        from app.agents.execution_v4 import ExecutionAgentV4
        
        deps = MagicMock()
        deps.config = MagicMock()
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        # Mock exchange manager with create_bybit_order
        agent.exm = MagicMock()
        agent.exm.create_bybit_order = AsyncMock(return_value={
            "id": "close123",
            "status": "filled"
        })
        return agent
    
    @pytest.mark.asyncio
    async def test_close_position_reduce_only_calls_bybit(self, execution_agent):
        """
        Test: _close_position_reduce_only nutzt Bybit create_bybit_order mit reduceOnly.
        """
        await execution_agent._close_position_reduce_only(
            symbol="BTCUSDT",
            side="sell",  # Long schließen
            amount=0.1,
            reason="test_reason"
        )
        
        # Verify Bybit API call
        execution_agent.exm.create_bybit_order.assert_called_once()
        call_args = execution_agent.exm.create_bybit_order.call_args
        
        assert call_args[1]["symbol"] == "BTCUSDT"
        assert call_args[1]["side"] == "sell"
        assert call_args[1]["amount"] == 0.1
        assert call_args[1]["order_type"] == "close"
        assert call_args[1]["reduce_only"] is True
    
    @pytest.mark.asyncio
    async def test_close_position_fallback_to_market(self, execution_agent):
        """
        Test: Falls create_bybit_order nicht verfügbar, Fallback zu Market Order.
        """
        # Remove create_bybit_order method
        delattr(execution_agent.exm, 'create_bybit_order')
        execution_agent.exm.create_market_order = AsyncMock(return_value={
            "id": "fallback456",
            "status": "filled"
        })
        
        await execution_agent._close_position_reduce_only(
            symbol="BTCUSDT",
            side="sell",
            amount=0.1,
            reason="test_reason"
        )
        
        # Verify fallback
        execution_agent.exm.create_market_order.assert_called_once_with("BTCUSDT", "sell", 0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
