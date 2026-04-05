from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.redis_client import redis_client
import json
import logging
from typing import Dict, Any, List

router = APIRouter(prefix="/debriefs", tags=["debriefs"])
logger = logging.getLogger("debrief_api")

@router.get("/summary")
async def get_debrief_summary(db: AsyncSession = Depends(get_db)):
    """
    Aggregates trade debrief insights from the database.
    - Win-Rate by Regime
    - Signal Accuracy Ranking
    - Top 3 Errors
    """
    try:
        # 1. Win-Rate by Regime
        regime_query = text("""
            SELECT regime_assessment, 
                   COUNT(*) as total,
                   SUM(CASE WHEN decision_quality = 'CORRECT' THEN 1 ELSE 0 END) as correct
            FROM trade_debriefs
            GROUP BY regime_assessment
        """)
        regime_result = await db.execute(regime_query)
        regimes = {}
        for row in regime_result:
            name = row[0]
            total = row[1]
            correct = row[2]
            regimes[name] = {
                "total": total,
                "win_rate": round(correct / total, 2) if total > 0 else 0
            }

        # 2. Top 3 Errors (Improvement field)
        error_query = text("""
            SELECT improvement, COUNT(*) as count
            FROM trade_debriefs
            WHERE decision_quality = 'INCORRECT' AND improvement != 'N/A'
            GROUP BY improvement
            ORDER BY count DESC
            LIMIT 3
        """)
        error_result = await db.execute(error_query)
        top_errors = [{"error": row[0], "count": row[1]} for row in error_result]

        # 3. Signal Accuracy Ranking
        # We need to parse the 'pattern' JSONB which contains signal_accuracy
        accuracy_query = text("""
            SELECT 
                AVG((pattern->>'ta_accurate')::int) as ta_acc,
                AVG((pattern->>'flow_accurate')::int) as flow_acc,
                AVG((pattern->>'liq_accurate')::int) as liq_acc,
                AVG((pattern->>'macro_accurate')::int) as macro_acc
            FROM trade_debriefs
            WHERE pattern != '{}'
        """)
        acc_result = await db.execute(accuracy_query)
        acc_row = acc_result.fetchone()
        accuracy_ranking = {
            "technical": round(acc_row[0] or 0, 2),
            "flow": round(acc_row[1] or 0, 2),
            "liquidity": round(acc_row[2] or 0, 2),
            "macro": round(acc_row[3] or 0, 2)
        }

        # 4. Latest History from Redis
        history_raw = await redis_client.redis.lrange("bruno:debriefs:history", 0, 9)
        history = [json.loads(h) for h in history_raw]

        return {
            "regime_performance": regimes,
            "top_errors": top_errors,
            "accuracy_ranking": accuracy_ranking,
            "recent_history": history
        }

    except Exception as e:
        logger.error(f"Debrief Summary Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_debrief_history():
    """Returns the last 100 debriefs from Redis history."""
    history_raw = await redis_client.redis.lrange("bruno:debriefs:history", 0, 99)
    return [json.loads(h) for h in history_raw]
