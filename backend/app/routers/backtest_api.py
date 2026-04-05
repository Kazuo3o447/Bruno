from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from app.services.backtester import PipelineBacktester
from app.core.database import get_db_session_factory
import logging

router = APIRouter(prefix="/backtest", tags=["backtest"])
logger = logging.getLogger("backtest_api")

class BacktestRequest(BaseModel):
    start: str  # Format: "YYYY-MM-DD"
    end: str    # Format: "YYYY-MM-DD"
    initial_capital: float = 10000.0

@router.post("/run")
async def run_pipeline_backtest(
    req: BacktestRequest,
    db_factory = Depends(get_db_session_factory)
):
    """
    Triggers a Walk-Forward Pipeline Backtest.
    """
    try:
        start_dt = datetime.strptime(req.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(req.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        if start_dt >= end_dt:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        backtester = PipelineBacktester(db_factory)
        result = await backtester.run(start_dt, end_dt, req.initial_capital)
        
        return result

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {ve}")
    except Exception as e:
        logger.error(f"Backtest API Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
