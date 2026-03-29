import redis.asyncio as redis
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis Client mit Connection Pool für Caching, Streams und Pub/Sub."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance.redis = None
        return cls._instance

    async def connect(self):
        """Stellt Verbindung zu Redis her."""
        if not self.redis:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                max_connections=100,
                retry_on_timeout=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            try:
                await self.redis.ping()
                logger.info(f"Verbunden mit Redis auf {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.error(f"Redis Verbindung fehlgeschlagen: {e}")
                raise

    async def disconnect(self):
        """Schließt die Redis Verbindung."""
        if self.redis:
            await self.redis.aclose()
            logger.info("Redis Verbindung geschlossen.")

    async def set_cache(self, key: str, value: Dict[str, Any], ttl: int = 300):
        """Setzt einen Cache-Eintrag mit TTL."""
        if self.redis:
            await self.redis.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cache gesetzt: {key} (TTL: {ttl}s)")

    async def get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Holt einen Cache-Eintrag."""
        if self.redis:
            data = await self.redis.get(key)
            if data:
                logger.debug(f"Cache hit: {key}")
                return json.loads(data)
            logger.debug(f"Cache miss: {key}")
        return None

    async def delete_cache(self, key: str):
        """Löscht einen Cache-Eintrag."""
        if self.redis:
            await self.redis.delete(key)
            logger.debug(f"Cache gelöscht: {key}")

    async def publish_stream(self, stream_name: str, data: Dict[str, Any]):
        """Publiziert Daten in einen Redis Stream."""
        if self.redis:
            await self.redis.xadd(stream_name, data)
            logger.debug(f"Stream published: {stream_name}")

    async def read_stream(self, stream_name: str, count: int = 10, block: int = 1000) -> list:
        """Liest Daten aus einem Redis Stream."""
        if self.redis:
            try:
                result = await self.redis.xread({stream_name: '$'}, count=count, block=block)
                return result
            except redis.ResponseError:
                return []
        return []

    async def publish_message(self, channel: str, message: str):
        """Publiziert eine Nachricht in einen Pub/Sub Channel."""
        if self.redis:
            await self.redis.publish(channel, message)
            logger.debug(f"Message published: {channel}")

    async def subscribe_channel(self, channel: str):
        """Erstellt einen Pub/Sub Subscriber."""
        if self.redis:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        return None

    async def health_check(self) -> bool:
        """Prüft die Redis-Verbindung."""
        if self.redis:
            try:
                await self.redis.ping()
                return True
            except Exception:
                return False
        return False

    def get_current_time(self) -> str:
        """Gibt aktuelle Zeit als ISO-String zurück."""
        return datetime.now(timezone.utc).isoformat()

    async def delete_cache(self, key: str) -> bool:
        """Löscht einen Cache-Eintrag."""
        if self.redis:
            try:
                await self.redis.delete(key)
                logger.debug(f"Cache gelöscht: {key}")
                return True
            except Exception as e:
                logger.error(f"Fehler beim Löschen von Cache {key}: {e}")
                return False
        return False


# Singleton-Instanz
redis_client = RedisClient()
