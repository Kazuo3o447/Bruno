import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.core.redis_client import get_redis_client
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt aktuelle Ticker-Daten für ein Symbol zurück."""
    try:
        ticker_data = await redis.get_cache(f"market:ticker:{symbol}")
        if not ticker_data:
            raise HTTPException(status_code=404, detail=f"No ticker data found for {symbol}")
        
        return {
            "symbol": symbol,
            "data": ticker_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ticker for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt aktuelle Orderbook-Daten für ein Symbol zurück."""
    try:
        orderbook_data = await redis.get_cache(f"market:orderbook:{symbol}")
        if not orderbook_data:
            raise HTTPException(status_code=404, detail=f"No orderbook data found for {symbol}")
        
        return {
            "symbol": symbol,
            "data": orderbook_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching orderbook for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/price/{symbol}")
async def get_price(symbol: str, redis=Depends(get_redis_client)) -> Dict[str, Any]:
    """Gibt nur den aktuellen Preis für ein Symbol zurück."""
    try:
        ticker_data = await redis.get_cache(f"market:ticker:{symbol}")
        if not ticker_data:
            raise HTTPException(status_code=404, detail=f"No price data found for {symbol}")
        
        price = ticker_data.get("last_price") or ticker_data.get("price")
        if price is None:
            raise HTTPException(status_code=404, detail=f"No price found in ticker data")
        
        return {
            "symbol": symbol,
            "price": float(price),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/grss-full")
async def get_grss_full(redis=Depends(get_redis_client)):
    """Vollständiger GRSS-State mit allen Inputs für Dashboard."""
    try:
        grss_data = await redis.get_cache("bruno:context:grss") or {}
        return {
            "score": grss_data.get("GRSS_Score"),
            "score_raw": grss_data.get("GRSS_Score_Raw"),
            "ema": grss_data.get("GRSS_Score"),
            "velocity_30min": grss_data.get("GRSS_Velocity_30min"),
            "veto_active": grss_data.get("Veto_Active"),
            "reason": grss_data.get("Reason"),
            "macro": {
                "ndx_status": grss_data.get("Macro_Status"),
                "vix": grss_data.get("VIX"),
                "yields_10y": grss_data.get("Yields_10Y"),
                "dxy_change_pct": grss_data.get("DXY_Change_Pct"),
                "m2_yoy_pct": grss_data.get("M2_YoY_Pct"),
            },
            "derivatives": {
                "funding_rate": grss_data.get("Funding_Rate"),
                "funding_divergence": grss_data.get("Funding_Divergence"),
                "put_call_ratio": grss_data.get("Put_Call_Ratio"),
                "dvol": grss_data.get("DVOL"),
                "oi_delta_pct": grss_data.get("OI_Delta_Pct"),
                "perp_basis_pct": grss_data.get("Perp_Basis_Pct"),
                "long_short_ratio": grss_data.get("Long_Short_Ratio"),
            },
            "sentiment": {
                "fear_greed": grss_data.get("Fear_Greed"),
                "llm_news_sentiment": grss_data.get("LLM_News_Sentiment"),
                "stablecoin_delta_bn": grss_data.get("Stablecoin_Delta_Bn"),
                "retail_score": grss_data.get("Retail_Score"),
                "retail_fomo_warning": grss_data.get("Retail_FOMO_Warning"),
            },
            "data_quality": {
                "fresh_source_count": grss_data.get("Fresh_Source_Count"),
                "data_freshness_ok": grss_data.get("Data_Freshness_Active"),
                "news_silence_seconds": grss_data.get("News_Silence_Seconds"),
                "funding_settlement_window": grss_data.get("Funding_Settlement_Window"),
                "last_update": grss_data.get("last_update"),
            },
            "btc": {
                "change_24h_pct": grss_data.get("BTC_Change_24h_Pct"),
                "change_1h_pct": grss_data.get("BTC_Change_1h_Pct"),
            }
        }
    except Exception as e:
        logger.error(f"Error fetching GRSS full: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
