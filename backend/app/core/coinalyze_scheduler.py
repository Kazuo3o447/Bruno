"""
Coinalyze Reference Data Scheduler.

Täglicher automatischer Import von Coinalyze-Daten um 03:00 UTC.
Unabhängig vom Systemtest-Scheduler.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging
from app.core.redis_client import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class CoinalyzeScheduler:
    """
    Scheduler für tägliche Coinalyze Daten-Updates.
    Läuft um 03:00 UTC (nach Daily Close).
    """
    
    _instance = None
    SCHEDULER_KEY = "bruno:scheduler:coinalyze"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CoinalyzeScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.db_pool = None
    
    async def initialize(self):
        """Initialisiert den Scheduler und startet wenn API-Key vorhanden."""
        try:
            await redis_client.connect()
            
            # Check if COINALYZE_API_KEY is configured
            if not settings.COINALYZE_API_KEY:
                logger.info("Coinalyze Scheduler: COINALYZE_API_KEY not set, skipping initialization")
                return
            
            # Initialize database pool
            from app.core.database import async_engine
            from sqlalchemy.ext.asyncio import AsyncSession
            import asyncpg
            
            # Create asyncpg pool directly for the importer
            db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            self.db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
            
            # Start the scheduler
            await self.start()
            logger.info("Coinalyze Scheduler initialized")
            
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren des Coinalyze Schedulers: {e}")
    
    async def start(self) -> Dict[str, Any]:
        """Startet den Coinalyze Scheduler."""
        try:
            if self._running:
                return {"status": "error", "message": "Coinalyze Scheduler läuft bereits"}
            
            self._running = True
            self._task = asyncio.create_task(self._run_scheduler())
            
            logger.info("Coinalyze Scheduler gestartet (täglich um 20:00 UTC)")
            return {
                "status": "success",
                "message": "Coinalyze Scheduler gestartet (täglich um 20:00 UTC)"
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Coinalyze Schedulers: {e}")
            return {"status": "error", "message": str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """Stoppt den Coinalyze Scheduler."""
        try:
            if not self._running:
                return {"status": "error", "message": "Coinalyze Scheduler läuft nicht"}
            
            self._running = False
            
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
            
            if self.db_pool:
                await self.db_pool.close()
                self.db_pool = None
            
            logger.info("Coinalyze Scheduler gestoppt")
            return {"status": "success", "message": "Coinalyze Scheduler gestoppt"}
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Coinalyze Schedulers: {e}")
            return {"status": "error", "message": str(e)}
    
    def _seconds_until_20h_utc(self) -> float:
        """Berechnet Sekunden bis zum nächsten 20:00 UTC."""
        now = datetime.now(timezone.utc)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        
        if now >= target:
            # Wenn es schon nach 20:00 ist, auf morgen 20:00 warten
            target = target + timedelta(days=1)
        
        return (target - now).total_seconds()
    
    async def _run_import(self):
        """Führt den tatsächlichen Import durch."""
        try:
            from app.services.coinalyze_importer import CoinalyzeImporter
            
            importer = CoinalyzeImporter(self.db_pool)
            stats = await importer.run_incremental_update()
            
            total = sum(stats.values())
            logger.info(f"Coinalyze täglicher Import abgeschlossen: {total} neue Zeilen")
            
            # Store last run info in Redis
            await redis_client.redis.hset(
                self.SCHEDULER_KEY,
                mapping={
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "rows_imported": str(total),
                    "status": "success"
                }
            )
            
        except Exception as e:
            logger.error(f"Coinalyze Import Fehler: {e}")
            await redis_client.redis.hset(
                self.SCHEDULER_KEY,
                mapping={
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "status": "error",
                    "error": str(e)
                }
            )
    
    async def _run_scheduler(self):
        """Haupt-Scheduler-Loop."""
        while self._running:
            try:
                # Warte bis 20:00 UTC
                wait_seconds = self._seconds_until_20h_utc()
                next_run = datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)
                
                logger.info(f"Coinalyze Scheduler: Nächster Lauf um {next_run.isoformat()} (in {wait_seconds/3600:.1f} Stunden)")
                
                await redis_client.redis.hset(
                    self.SCHEDULER_KEY,
                    mapping={
                        "next_run": next_run.isoformat(),
                        "status": "waiting"
                    }
                )
                
                await asyncio.sleep(wait_seconds)
                
                if not self._running:
                    break
                
                # Führe Import durch
                logger.info("Coinalyze Scheduler: Starte täglichen Import...")
                await self._run_import()
                
                # Warte 1 Minute nach dem Import um doppelte Ausführung zu vermeiden
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Coinalyze Scheduler Task wurde abgebrochen")
                break
            except Exception as e:
                logger.error(f"Fehler im Coinalyze Scheduler Loop: {e}")
                await asyncio.sleep(3600)  # Bei Fehler 1 Stunde warten
    
    async def get_status(self) -> Dict[str, Any]:
        """Gibt aktuellen Scheduler-Status zurück."""
        try:
            status_data = await redis_client.redis.hgetall(self.SCHEDULER_KEY)
            
            return {
                "is_running": self._running,
                "last_run": status_data.get("last_run"),
                "next_run": status_data.get("next_run"),
                "status": status_data.get("status", "unknown"),
                "rows_imported_last_run": status_data.get("rows_imported"),
                "error": status_data.get("error")
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Coinalyze Scheduler-Status: {e}")
            return {"status": "error", "message": str(e)}
    
    async def run_now(self) -> Dict[str, Any]:
        """Manueller Trigger für sofortigen Import."""
        try:
            if not self.db_pool:
                return {"status": "error", "message": "Scheduler nicht initialisiert"}
            
            logger.info("Coinalyze Scheduler: Manueller Import gestartet...")
            await self._run_import()
            return {"status": "success", "message": "Import abgeschlossen"}
            
        except Exception as e:
            logger.error(f"Fehler beim manuellen Coinalyze Import: {e}")
            return {"status": "error", "message": str(e)}


# Singleton-Instanz
coinalyze_scheduler = CoinalyzeScheduler()
