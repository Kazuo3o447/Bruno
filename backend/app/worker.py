import asyncio
import signal
import sys
import logging
from app.core.redis_client import RedisClient
from app.core.database import AsyncSessionLocal, init_db
from app.core.llm_client import OllamaClient
from app.core.log_manager import log_manager
from app.core.config import settings
from app.agents.deps import AgentDependencies
from app.agents.orchestrator import AgentOrchestrator

# Wir importieren die Agenten, die wir später auf V2 umstellen.
# Für den Augenblick registrieren wir leere Dummies, bis ihre Dateien refactored sind.
# Die tatsächlichen V2-Agenten werden wir im nächsten Schritt implementieren.
from app.agents.ingestion import IngestionAgentV2
from app.agents.quant import QuantAgent
from app.agents.context import ContextAgent
from app.agents.risk import RiskAgent
from app.agents.execution import ExecutionAgentV3

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
    ollama = OllamaClient()

    await wait_for_redis(redis)
    await wait_for_db()
    await log_manager.initialize()
    
    ollama_ok = await ollama.health_check()
    logger.info(f"Ollama Status: {'✅ Ok' if ollama_ok else '⚠️ Down (Fallback)'}")

    # 2. Dependency Injection
    deps = AgentDependencies(
        redis=redis,
        config=settings,
        db_session_factory=AsyncSessionLocal,
        ollama=ollama,
        log_manager=log_manager,
        logger=logger
    )

    # 3. Agenten Registrierung
    orchestrator = AgentOrchestrator(deps)
    orchestrator.register("ingestion", IngestionAgentV2(deps))
    orchestrator.register("quant", QuantAgent(deps, symbol="BTCUSDT"))
    orchestrator.register("context", ContextAgent(deps))
    orchestrator.register("risk", RiskAgent(deps))
    orchestrator.register("execution", ExecutionAgentV3(deps))
    
    # 4. Agenten Starten
    await orchestrator.start_all()
    cmd_task = asyncio.create_task(orchestrator.listen_for_commands())

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
    await ollama.close()
    await redis.disconnect()
    logger.info("Worker sauber beendet.")

if __name__ == "__main__":
    asyncio.run(main())
