import asyncio
import signal
import sys
import logging
from app.core.redis_client import RedisClient
from app.core.database import AsyncSessionLocal, init_db
from app.core.log_manager import log_manager
from app.core.config import settings
from app.agents.deps import AgentDependencies
from app.agents.orchestrator import AgentOrchestrator

from app.agents.ingestion import IngestionAgentV2
from app.agents.quant_v4 import QuantAgentV4
from app.agents.technical import TechnicalAnalysisAgent
from app.agents.context import ContextAgent
from app.agents.sentiment import SentimentAgent
from app.agents.risk import RiskAgent
from app.agents.execution_v4 import ExecutionAgentV4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("worker")

async def wait_for_redis(redis: RedisClient, max_attempts: int = 30) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            await redis.connect()
            logger.info("Redis verbunden")
            return
        except Exception as e:
            logger.warning(f"Redis nicht bereit (Versuch {attempt}/{max_attempts}): {e}")
            await asyncio.sleep(5)
    logger.critical("Redis nicht erreichbar. Worker beendet.")
    sys.exit(1)

async def wait_for_db(max_attempts: int = 30) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            await init_db()
            logger.info("Datenbank verbunden")
            return
        except Exception as e:
            logger.warning(f"DB nicht bereit (Versuch {attempt}/{max_attempts}): {e}")
            await asyncio.sleep(5)
    logger.critical("Datenbank nicht erreichbar. Worker beendet.")
    sys.exit(1)

async def main():
    logger.info("=" * 60)
    logger.info("Bruno Worker Entrypoint Startet...")
    logger.info("=" * 60)

    # 1. Infrastruktur Init
    redis = RedisClient()

    await wait_for_redis(redis)
    await wait_for_db()
    await log_manager.initialize()
    
    # Telegram Bot initialisieren
    from app.core.telegram_bot import init_telegram_bot, get_telegram_bot

    telegram = init_telegram_bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
        redis_client=redis
    )

    # Emergency Stop Callback
    async def emergency_stop():
        logger.warning("EMERGENCY STOP via Telegram ausgelöst!")
        await orchestrator.stop_all()
        await telegram.send_critical_alert(
            "Emergency Stop ausgeführt. Alle Agenten gestoppt."
        )

    # Pause Callback
    async def pause_bot(hours: int = 4):
        if hours == 0:
            await redis.set_cache("bruno:system:paused", {"paused": False})
            await telegram.send_critical_alert("Bot fortgesetzt.")
        else:
            from datetime import datetime, timezone, timedelta
            resume_at = (
                datetime.now(timezone.utc) + timedelta(hours=hours)
            ).isoformat()
            await redis.set_cache(
                "bruno:system:paused",
                {"paused": True, "resume_at": resume_at},
                ttl=hours * 3600
            )
            await telegram.send_critical_alert(
                f"Bot für {hours}h pausiert. Resume: {resume_at}"
            )

    telegram.set_callbacks(
        emergency_stop=emergency_stop,
        pause=pause_bot
    )

    telegram_started = await telegram.start()
    if not telegram_started:
        logger.warning("Telegram nicht aktiv — Keys fehlen in .env")
    
    # Bybit V5 WebSocket Health Check
    from app.core.market_data_collector import MarketDataCollector
    market_collector = MarketDataCollector(redis)
    bybit_ok = await market_collector.health_check()
    logger.info(f"Bybit V5 WebSocket Status: {'✅ Connected' if bybit_ok else '⚠️ Disconnected'}")
    
    # News Ingestion Service
    from app.services.news_ingestion import news_ingestion_service
    news_ingestion_service.set_redis_client(redis)
    logger.info("News Ingestion Service initialisiert")

    # 2. Dependency Injection
    deps = AgentDependencies(
        redis=redis,
        config=settings,
        db_session_factory=AsyncSessionLocal,
        log_manager=log_manager,
        logger=logger
    )

    # 3. Agenten Registrierung
    orchestrator = AgentOrchestrator(deps)
    orchestrator.register("ingestion", IngestionAgentV2(deps))
    orchestrator.register("technical", TechnicalAnalysisAgent(deps))
    orchestrator.register("quant", QuantAgentV4(deps, symbol="BTCUSDT"))
    orchestrator.register("context", ContextAgent(deps))
    orchestrator.register("sentiment", SentimentAgent(deps))
    orchestrator.register("risk", RiskAgent(deps))
    orchestrator.register("execution", ExecutionAgentV4(deps))

    # 4. Agenten Starten
    await orchestrator.start_all()
    cmd_task = asyncio.create_task(orchestrator.listen_for_commands())
    
    # Market Data Collection Task (Bybit V5 WebSocket)
    async def market_data_loop():
        while True:
            try:
                await market_collector.collect_all_data("BTCUSDT")
                await asyncio.sleep(30)  # Alle 30 Sekunden aktualisieren
            except Exception as e:
                logger.error(f"Market data collection error: {e}")
                await asyncio.sleep(60)  # Bei Fehler länger warten
    
    # News Ingestion Task
    async def news_ingestion_loop():
        while True:
            try:
                await news_ingestion_service.start_ingestion_loop()
                await asyncio.sleep(1)  # Service hat eigene Timing-Logik
            except Exception as e:
                logger.error(f"News ingestion error: {e}")
                await asyncio.sleep(10)  # Bei Fehler kurz warten
    
    market_task = asyncio.create_task(market_data_loop())
    news_task = asyncio.create_task(news_ingestion_loop())
    logger.info("Market Data Collection & News Ingestion gestartet")

    # 5. Shutdown Handling (signal für Windows nicht 100% kompatibel, daher try/except)
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(orchestrator.stop_all()))
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(orchestrator.stop_all()))
    except NotImplementedError:
        pass # Windows

    await orchestrator.wait_for_shutdown()

    # 6. Cleanup
    cmd_task.cancel()
    market_task.cancel()
    news_task.cancel()
    await market_collector.close()
    await news_ingestion_service.shutdown()
    await redis.disconnect()
    
    # Telegram Bot stoppen
    telegram_bot = get_telegram_bot()
    if telegram_bot:
        await telegram_bot.stop()
    
    logger.info("Worker sauber beendet.")

if __name__ == "__main__":
    asyncio.run(main())
