from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.agents.sentiment import SentimentAgentV2
from app.agents.deps import AgentDependencies
from app.core.redis_client import redis_client
from app.core.config import settings
from app.core.log_manager import log_manager
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.database import SessionLocal
from app.core.llm_client import ollama_client
import logging

router = APIRouter(prefix="/systemtest/sentiment", tags=["systemtest"])

async def get_deps():
    return AgentDependencies(
        redis=redis_client,
        config=settings,
        db_session_factory=SessionLocal,
        ollama=ollama_client,
        log_manager=log_manager
    )

@router.get("/news_health")
async def get_news_health():
    """
    Gibt den Gesundheitsstatus aller News-Feeds zurück.
    Liest Daten aus Redis, die vom SentimentAgent aktualisiert werden.
    """
    detailed = await redis_client.get_cache("sentiment:feeds:health") or {}
    summary = await redis_client.get_cache("sentiment:health:summary") or {}
    return {
        "summary": summary,
        "feeds": detailed
    }

@router.get("/fetch")
async def test_sentiment_fetch(deps: AgentDependencies = Depends(get_deps)):
    """
    Triggert manuell das Abrufen und Kategorisieren der News-Feeds.
    Dient zur Verifizierung der FinBERT/CryptoBERT-Pipeline.
    """
    agent = SentimentAgentV2(deps)
    
    # Feeds abrufen (ohne Deduplizierung für den Test)
    macro_news = await agent._fetch_categorized_news(agent.macro_feeds, "MACRO")
    crypto_news = await agent._fetch_categorized_news(agent.crypto_feeds, "CRYPTO")
    
    return {
        "status": "success",
        "counts": {
            "macro": len(macro_news),
            "crypto": len(crypto_news)
        },
        "samples": {
            "macro": macro_news[:3],
            "crypto": crypto_news[:3]
        }
    }
