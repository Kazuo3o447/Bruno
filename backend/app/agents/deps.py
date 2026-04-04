from dataclasses import dataclass
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.core.redis_client import RedisClient
    from app.core.config import Settings
    from app.core.log_manager import LogManager
    from sqlalchemy.ext.asyncio import async_sessionmaker

@dataclass
class AgentDependencies:
    """
    Alle Abhängigkeiten, die ein Agent zum Arbeiten braucht.
    Dies ersetzt direkte globale Imports (z.B. von redis_client) und macht
    die Agenten testbar und unabhängig vom API-Container.
    """
    redis: "RedisClient"
    config: "Settings"
    db_session_factory: "async_sessionmaker"
    log_manager: "LogManager"
    logger: logging.Logger = logging.getLogger("worker")
