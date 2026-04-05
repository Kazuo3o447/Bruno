"""
Log Manager - Zentrales Logging-System für Bruno Trading Bot
Speichert Logs in Redis mit Pub/Sub für Live-Updates
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict

from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    TRADING = "TRADING"
    API = "API"
    DATABASE = "DATABASE"
    REDIS = "REDIS"
    WEBSOCKET = "WEBSOCKET"
    BINANCE = "BINANCE"
    LLM = "LLM"
    BACKUP = "BACKUP"


@dataclass
class LogEntry:
    timestamp: str
    level: str
    category: str
    source: str
    message: str
    details: Optional[Dict] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "LogEntry":
        return cls(**data)


class LogManager:
    """
    Zentraler Log-Manager mit Redis-Speicher und Pub/Sub
    """
    
    def __init__(self, max_logs: int = 10000):
        self.redis = RedisClient()
        self.max_logs = max_logs
        self.log_key = "logs:all"
        self.channel = "logs:live"
        self.subscribers: List[Callable] = []
        self._initialized = False
        
        # Cache für häufige Log-Abfragen (5 Sekunden TTL)
        self._stats_cache = None
        self._stats_cache_time = 0
        self._cache_ttl = 5  # Sekunden
        
    async def initialize(self):
        """Initialisiert den Log-Manager"""
        if not self._initialized:
            try:
                # Sicherstellen dass Redis verbunden ist
                if not self.redis.redis:
                    await self.redis.connect()
                # Nochmal prüfen ob Verbindung funktioniert
                if not self.redis.redis:
                    raise Exception("Redis Verbindung fehlgeschlagen")
                self._initialized = True
                await self.info(LogCategory.SYSTEM, "LogManager", "Log-System initialisiert")
            except Exception as e:
                logger.error(f"LogManager Init Fehler: {e}")
                raise
    
    async def _cleanup_old_logs(self):
        """Löscht Logs, die älter als 24 Stunden sind."""
        try:
            # Wir prüfen das älteste Element (am Ende der Liste)
            # Da wir LPUSH machen, ist das Element am Index -1 das älteste
            oldest_json = await self.redis.redis.lindex(self.log_key, -1)
            if not oldest_json:
                return

            oldest_dict = json.loads(oldest_json)
            oldest_ts = datetime.fromisoformat(oldest_dict["timestamp"])
            
            # Wenn älter als 24h
            if (datetime.now(timezone.utc) - oldest_ts).total_seconds() > 86400:
                # Wir löschen solange, bis das älteste Element wieder aktuell ist
                # Da eine Liste groß sein kann, machen wir das schrittweise
                deleted = 0
                while deleted < 100: # Max 100 pro Durchgang um Blockade zu vermeiden
                    last_json = await self.redis.redis.lindex(self.log_key, -1)
                    if not last_json: break
                    
                    last_dict = json.loads(last_json)
                    last_ts = datetime.fromisoformat(last_dict["timestamp"])
                    
                    if (datetime.now(timezone.utc) - last_ts).total_seconds() > 86400:
                        await self.redis.redis.rpop(self.log_key)
                        deleted += 1
                    else:
                        break
        except Exception as e:
            logger.error(f"Fehler bei Log-Cleanup: {e}")

    async def add_log(
        self, 
        level: LogLevel, 
        category: LogCategory, 
        source: str, 
        message: str,
        details: Optional[Dict] = None,
        stack_trace: Optional[str] = None
    ) -> LogEntry:
        """
        Fügt einen Log-Eintrag hinzu
        
        Args:
            level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: Log-Kategorie (SYSTEM, AGENT, TRADING, etc.)
            source: Quelle des Logs (z.B. "QuantAgent", "BinanceAPI")
            message: Log-Nachricht
            details: Optionale Details als Dictionary
            stack_trace: Stack-Trace bei Fehlern
        """
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.value,
            category=category.value if hasattr(category, 'value') else category,
            source=source,
            message=message,
            details=details,
            stack_trace=stack_trace
        )
        
        # In Redis speichern (LPUSH für neueste zuerst)
        log_json = json.dumps(entry.to_dict())
        await self.redis.redis.lpush(self.log_key, log_json)
        
        # 24h Cleanup triggern (nicht bei jedem Log, um Performance zu sparen, z.B. bei jedem 10.)
        import random
        if random.random() < 0.1: 
            asyncio.create_task(self._cleanup_old_logs())
        
        # Harte Obergrenze trotzdem beibehalten
        await self.redis.redis.ltrim(self.log_key, 0, self.max_logs - 1)
        
        # Pub/Sub für Live-Updates
        await self.redis.publish_message(self.channel, log_json)
        
        # Auch in Python-Logging ausgeben
        log_method = getattr(logger, level.value.lower())
        log_method(f"[{category.value if hasattr(category, 'value') else category}] {source}: {message}")
        
        return entry
    
    # Convenience-Methoden für verschiedene Log-Levels
    async def debug(self, category: LogCategory, source: str, message: str, details: Optional[Dict] = None):
        return await self.add_log(LogLevel.DEBUG, category, source, message, details)
    
    async def info(self, category: LogCategory, source: str, message: str, details: Optional[Dict] = None):
        return await self.add_log(LogLevel.INFO, category, source, message, details)
    
    async def warning(self, category: LogCategory, source: str, message: str, details: Optional[Dict] = None):
        return await self.add_log(LogLevel.WARNING, category, source, message, details)
    
    async def error(self, category: LogCategory, source: str, message: str, details: Optional[Dict] = None, stack_trace: Optional[str] = None):
        return await self.add_log(LogLevel.ERROR, category, source, message, details, stack_trace)
    
    async def critical(self, category: LogCategory, source: str, message: str, details: Optional[Dict] = None, stack_trace: Optional[str] = None):
        return await self.add_log(LogLevel.CRITICAL, category, source, message, details, stack_trace)
    
    async def get_logs(
        self, 
        limit: int = 1000,
        level: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        since: Optional[str] = None
    ) -> List[LogEntry]:
        """
        Holt Logs mit Filtern - Hochoptimierte Version
        
        Args:
            limit: Maximale Anzahl Logs
            level: Filter nach Log-Level
            category: Filter nach Kategorie
            source: Filter nach Quelle
            search: Text-Suche in Nachricht
            since: Zeitstempel für Logs seit diesem Zeitpunkt
        """
        logs = []
        count = 0
        
        # Redis LRANGE mit Pagination für bessere Performance
        total_logs = await self.redis.redis.llen(self.log_key)
        if total_logs == 0:
            return []
        
        # Von hinten nach vorne iterieren (neueste Logs zuerst)
        # Wir holen nur die benötigte Anzahl + Buffer für Filter
        batch_size = min(limit * 3, 5000)  # Maximal 5000 Logs scannen
        start_idx = max(0, total_logs - batch_size)
        
        log_jsons = await self.redis.redis.lrange(self.log_key, start_idx, -1)
        
        for log_json in reversed(log_jsons):  # Neueste zuerst verarbeiten
            if count >= limit:
                break
                
            try:
                log_dict = json.loads(log_json)
                log = LogEntry.from_dict(log_dict)
                
                # Filter anwenden
                if level and log.level != level:
                    continue
                if category and log.category != category:
                    continue
                if source and log.source != source:
                    continue
                if search and search.lower() not in log.message.lower():
                    continue
                if since and log.timestamp < since:
                    continue
                    
                logs.append(log)
                count += 1
            except Exception as e:
                logger.error(f"Fehler beim Parsen von Log: {e}")
                continue
        
        return logs
    
    async def clear_logs(self) -> bool:
        """Löscht alle Logs"""
        try:
            await self.redis.redis.delete(self.log_key)
            await self.info("SYSTEM", "LogManager", "Alle Logs gelöscht")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Logs: {e}")
            return False
    
    async def get_stats(self) -> Dict:
        """Holt Log-Statistiken - Optimierte Version mit Caching"""
        
        # Cache prüfen
        import time
        current_time = time.time()
        if self._stats_cache and (current_time - self._stats_cache_time) < self._cache_ttl:
            return self._stats_cache
        
        try:
            total = await self.redis.redis.llen(self.log_key)
            if total == 0:
                result = {"total": 0, "levels": {}, "categories_count": 0, "sources_count": 0, "categories": [], "sources": []}
                self._stats_cache = result
                self._stats_cache_time = current_time
                return result
            
            # Nur die letzten 1000 Logs für Statistiken analysieren (ausreichend für repräsentative Stats)
            sample_size = min(total, 1000)
            log_jsons = await self.redis.redis.lrange(self.log_key, -sample_size, -1)
            
            levels = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
            categories = set()
            sources = set()
            
            for log_json in log_jsons:
                try:
                    log_dict = json.loads(log_json)
                    level = log_dict.get("level", "INFO")
                    if level in levels:
                        levels[level] += 1
                    
                    category = log_dict.get("category")
                    if category:
                        categories.add(category)
                        
                    source = log_dict.get("source")
                    if source:
                        sources.add(source)
                        
                except Exception:
                    continue
            
            result = {
                "total": total,
                "levels": levels,
                "categories_count": len(categories),
                "sources_count": len(sources),
                "categories": list(categories),
                "sources": list(sources)
            }
            
            # Cache aktualisieren
            self._stats_cache = result
            self._stats_cache_time = current_time
            
            return result
        except Exception as e:
            logger.error(f"Fehler beim Holen der Log-Statistiken: {e}")
            return {"total": 0, "levels": {}, "categories_count": 0, "sources_count": 0, "categories": [], "sources": []}


# Singleton-Instanz
log_manager = LogManager()
