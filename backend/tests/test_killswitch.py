"""
PROMPT 01: Globaler Kill-Switch & Circuit Breaker Tests.

Test-Suite für:
- Daily Loss Limit Block
- Consecutive Losses Global Counter
- Kill-Switch Reset
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock, patch


class TestKillSwitchBlocks:
    """Test-Klasse für Kill-Switch Blocking-Logik."""
    
    @pytest.fixture
    async def risk_agent(self):
        """Erstellt einen RiskAgent mit gemockten Dependencies."""
        from app.agents.risk import RiskAgent
        from app.agents.deps import AgentDependencies
        from app.core.redis_client import RedisClient
        from app.core.log_manager import LogManager
        
        # Mock Dependencies
        deps = MagicMock(spec=AgentDependencies)
        deps.redis = AsyncMock(spec=RedisClient)
        deps.log_manager = AsyncMock(spec=LogManager)
        deps.db_session_factory = Mock()
        deps.config = Mock()
        deps.config.DRY_RUN = True
        
        agent = RiskAgent(deps)
        return agent
    
    @pytest.mark.asyncio
    async def test_killswitch_blocks_after_daily_limit(self, risk_agent):
        """
        Test: Wenn bruno:portfolio:daily_limit_hit mit hit=True und date==today existiert,
        wird der Trade hart blockiert mit reason="DAILY_LOSS_LIMIT_HIT".
        """
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Mock: Daily Limit wurde heute erreicht
        risk_agent.deps.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:portfolio:daily_limit_hit": {"hit": True, "date": today},
            "bruno:portfolio:state": {"consecutive_losses_global": 0},
        }.get(key))
        
        # Test: Check Global Kill-Switch
        result = await risk_agent._check_global_killswitch()
        
        assert result["blocked"] is True
        assert result["reason"] == "DAILY_LOSS_LIMIT_HIT"
    
    @pytest.mark.asyncio
    async def test_killswitch_resets_on_new_day(self, risk_agent):
        """
        Test: Wenn daily_limit_hit für gestern gesetzt ist, aber heute ein neuer Tag ist,
        wird der Trade NICHT blockiert (Reset bei Tageswechsel).
        """
        from datetime import timedelta
        
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        
        # Mock: Daily Limit wurde gestern erreicht (veraltet)
        risk_agent.deps.redis.get_cache = AsyncMock(side_effect=lambda key: {
            "bruno:portfolio:daily_limit_hit": {"hit": True, "date": yesterday},
            "bruno:portfolio:state": {"consecutive_losses_global": 0},
        }.get(key))
        
        # Test: Check Global Kill-Switch
        result = await risk_agent._check_global_killswitch()
        
        # Sollte NICHT blockieren, da hit_date != today
        assert result["blocked"] is False
        assert result["reason"] == ""
    
    @pytest.mark.asyncio
    async def test_consecutive_losses_global_counter_blocks(self, risk_agent):
        """
        Test: Wenn consecutive_losses_global >= MAX_CONSECUTIVE_LOSSES,
        wird der Trade hart blockiert mit reason="MAX_CONSECUTIVE_LOSSES_GLOBAL".
        """
        # Mock Config
        with patch('app.agents.risk.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "MAX_CONSECUTIVE_LOSSES": 8,
                "MAX_CONSECUTIVE_LOSSES_LEARNING": 12,
                "LEARNING_MODE_ENABLED": False,
            }.get(key, default)
            
            # Mock: 8 consecutive losses (Limit erreicht)
            risk_agent.deps.redis.get_cache = AsyncMock(side_effect=lambda key: {
                "bruno:portfolio:daily_limit_hit": None,
                "bruno:portfolio:state": {"consecutive_losses_global": 8},
            }.get(key))
            
            # Test: Check Global Kill-Switch
            result = await risk_agent._check_global_killswitch()
            
            assert result["blocked"] is True
            assert result["reason"] == "MAX_CONSECUTIVE_LOSSES_GLOBAL"
    
    @pytest.mark.asyncio
    async def test_consecutive_losses_learning_mode_higher_limit(self, risk_agent):
        """
        Test: Im Learning Mode ist das Limit höher (12 statt 8).
        8 Verluste sollten im Learning Mode NICHT blockieren.
        """
        # Mock Config
        with patch('app.agents.risk.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "MAX_CONSECUTIVE_LOSSES": 8,
                "MAX_CONSECUTIVE_LOSSES_LEARNING": 12,
                "LEARNING_MODE_ENABLED": True,
            }.get(key, default)
            
            # Mock: 8 consecutive losses (unter Learning-Limit von 12)
            risk_agent.deps.redis.get_cache = AsyncMock(side_effect=lambda key: {
                "bruno:portfolio:daily_limit_hit": None,
                "bruno:portfolio:state": {"consecutive_losses_global": 8},
            }.get(key))
            
            # Test: Check Global Kill-Switch
            result = await risk_agent._check_global_killswitch()
            
            # Sollte NICHT blockieren, da Learning Mode Limit = 12
            assert result["blocked"] is False
            assert result["reason"] == ""
    
    @pytest.mark.asyncio
    async def test_consecutive_losses_global_counter_allows_below_limit(self, risk_agent):
        """
        Test: Unter dem Limit sollte der Trade erlaubt sein.
        """
        # Mock Config
        with patch('app.agents.risk.ConfigCache.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "MAX_CONSECUTIVE_LOSSES": 8,
                "MAX_CONSECUTIVE_LOSSES_LEARNING": 12,
                "LEARNING_MODE_ENABLED": False,
            }.get(key, default)
            
            # Mock: 5 consecutive losses (unter Limit)
            risk_agent.deps.redis.get_cache = AsyncMock(side_effect=lambda key: {
                "bruno:portfolio:daily_limit_hit": None,
                "bruno:portfolio:state": {"consecutive_losses_global": 5},
            }.get(key))
            
            # Test: Check Global Kill-Switch
            result = await risk_agent._check_global_killswitch()
            
            assert result["blocked"] is False
            assert result["reason"] == ""


class TestConsecutiveLossesCounter:
    """Test-Klasse für Consecutive Losses Counter in ExecutionAgent."""
    
    @pytest.fixture
    def portfolio_state(self):
        """Erstellt einen frischen Portfolio-State."""
        return {
            "capital_eur": 10000.0,
            "initial_capital_eur": 10000.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "consecutive_losses_global": 0,
            "realized_pnl_eur": 0.0,
            "total_fees_eur": 0.0,
            "total_trades": 0,
            "daily_pnl_eur": 0.0,
            "daily_reset_date": datetime.now(timezone.utc).date().isoformat(),
        }
    
    @pytest.mark.asyncio
    async def test_consecutive_losses_increments_on_loss(self):
        """
        Test: Bei einem Verlust wird consecutive_losses_global um 1 erhöht.
        """
        from app.agents.execution_v4 import ExecutionAgentV4
        
        # Mock setup
        deps = MagicMock()
        deps.config = Mock()
        deps.config.DRY_RUN = True
        deps.config.SIMULATED_CAPITAL_EUR = 10000.0
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        
        # Initial state
        initial_state = {
            "capital_eur": 10000.0,
            "initial_capital_eur": 10000.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "consecutive_losses_global": 3,
            "realized_pnl_eur": 0.0,
            "total_fees_eur": 0.0,
            "total_trades": 0,
            "trade_pnl_history_eur": [],
            "trade_fee_history_eur": [],
            "daily_pnl_eur": 0.0,
            "daily_reset_date": datetime.now(timezone.utc).date().isoformat(),
        }
        
        deps.redis.get_cache = AsyncMock(return_value=initial_state)
        
        # Simuliere einen Verlust-Trade
        with patch.object(agent, '_update_profit_factor', AsyncMock()):
            await agent._update_portfolio({"pnl_eur": -50.0, "fee_eur": 5.0})
        
        # Verifiziere den gespeicherten State
        saved_state = deps.redis.set_cache.call_args[0][1]
        assert saved_state["consecutive_losses_global"] == 4  # Incremented
        assert saved_state["losing_trades"] == 1
    
    @pytest.mark.asyncio
    async def test_consecutive_losses_resets_on_win(self):
        """
        Test: Bei einem Gewinn wird consecutive_losses_global auf 0 zurückgesetzt.
        """
        from app.agents.execution_v4 import ExecutionAgentV4
        
        # Mock setup
        deps = MagicMock()
        deps.config = Mock()
        deps.config.DRY_RUN = True
        deps.config.SIMULATED_CAPITAL_EUR = 10000.0
        deps.redis = AsyncMock()
        
        agent = ExecutionAgentV4(deps)
        
        # Initial state mit 5 Verlusten
        initial_state = {
            "capital_eur": 10000.0,
            "initial_capital_eur": 10000.0,
            "winning_trades": 0,
            "losing_trades": 5,
            "consecutive_losses_global": 5,
            "realized_pnl_eur": -250.0,
            "total_fees_eur": 25.0,
            "total_trades": 5,
            "trade_pnl_history_eur": [],
            "trade_fee_history_eur": [],
            "daily_pnl_eur": -275.0,
            "daily_reset_date": datetime.now(timezone.utc).date().isoformat(),
        }
        
        deps.redis.get_cache = AsyncMock(return_value=initial_state)
        
        # Simuliere einen Gewinn-Trade
        with patch.object(agent, '_update_profit_factor', AsyncMock()):
            await agent._update_portfolio({"pnl_eur": 100.0, "fee_eur": 5.0})
        
        # Verifiziere den gespeicherten State
        saved_state = deps.redis.set_cache.call_args[0][1]
        assert saved_state["consecutive_losses_global"] == 0  # Reset!
        assert saved_state["winning_trades"] == 1


class TestKillSwitchAPI:
    """Test-Klasse für Kill-Switch API Endpoints."""
    
    @pytest.mark.asyncio
    async def test_reset_killswitch_wrong_date_fails(self):
        """
        Test: Reset mit falschem Datum (nicht heute) wird abgelehnt.
        """
        from datetime import timedelta
        
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        
        # Mock request
        request = Mock()
        request.date = yesterday
        request.scope = "all"
        
        # Import und Test
        from fastapi import HTTPException
        from app.routers.risk_api import reset_killswitch
        
        with pytest.raises(HTTPException) as exc_info:
            await reset_killswitch(request)
        
        assert exc_info.value.status_code == 400
        assert "nur für aktuellen Tag" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_reset_killswitch_correct_date_succeeds(self):
        """
        Test: Reset mit korrektem Datum (heute) funktioniert.
        """
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Mock request
        request = Mock()
        request.date = today
        request.scope = "all"
        
        # Mock Redis
        with patch('app.routers.risk_api.RedisClient') as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis
            mock_redis.get_cache = AsyncMock(return_value={"consecutive_losses_global": 10})
            
            from app.routers.risk_api import reset_killswitch
            result = await reset_killswitch(request)
            
            assert result["success"] is True
            assert result["date"] == today
            assert result["scope"] == "all"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
