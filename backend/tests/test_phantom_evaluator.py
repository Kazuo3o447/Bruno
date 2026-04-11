"""Tests für BRUNO-FIX-09: Phantom Evaluator."""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.services.phantom_evaluator import PhantomEvaluator


@pytest.mark.asyncio
async def test_evaluator_skips_not_yet_due():
    """Phantoms die noch nicht fällig sind werden nicht ausgewertet."""
    redis_mock = MagicMock()
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    phantom = {
        "phantom_id": "test-1",
        "evaluate_at": future,
        "entry_price": 100_000,
        "direction": "long",
        "ts": datetime.now(timezone.utc).isoformat(),
        "composite_score": 25, "regime": "ranging",
        "ta_score": 30, "liq_score": 0, "flow_score": 5, "macro_score": 0,
        "mtf_aligned": True, "sweep_confirmed": False,
    }
    redis_mock.redis.lrange = AsyncMock(return_value=[json.dumps(phantom)])
    redis_mock.redis.pipeline = MagicMock(return_value=MagicMock(execute=AsyncMock()))
    
    evaluator = PhantomEvaluator(redis_mock, MagicMock(), MagicMock())
    count = await evaluator.evaluate_pending()
    assert count == 0


@pytest.mark.asyncio
async def test_evaluator_processes_due_phantom():
    """Fällige Phantoms werden ausgewertet."""
    redis_mock = MagicMock()
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    phantom = {
        "phantom_id": "test-2",
        "evaluate_at": past,
        "entry_price": 100_000,
        "direction": "long",
        "ts": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
        "composite_score": 35, "regime": "trending_bull",
        "ta_score": 45, "liq_score": 5, "flow_score": 10, "macro_score": 5,
        "mtf_aligned": True, "sweep_confirmed": False,
        "signals_active": ["TA: bull"],
    }
    redis_mock.redis.lrange = AsyncMock(return_value=[json.dumps(phantom)])
    pipe_mock = MagicMock()
    pipe_mock.execute = AsyncMock()
    pipe_mock.delete = MagicMock()
    pipe_mock.rpush = MagicMock()
    redis_mock.redis.pipeline = MagicMock(return_value=pipe_mock)
    
    exm_mock = MagicMock()
    exm_mock.fetch_order_book_redundant = AsyncMock(return_value={
        "bids": [[102_000, 1.0]], "asks": [[102_100, 1.0]]
    })
    
    db_factory_mock = MagicMock()
    session_mock = AsyncMock()
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=None)
    db_factory_mock.return_value = session_mock
    
    evaluator = PhantomEvaluator(redis_mock, db_factory_mock, exm_mock)
    count = await evaluator.evaluate_pending()
    
    assert count == 1
    # Outcome: long, +2% → win
    session_mock.execute.assert_called_once()
