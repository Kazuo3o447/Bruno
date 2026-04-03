"""
Systemtest Scheduler Service

Nativer Scheduler für regelmäßige Systemtests.
Verwaltet automatische Tests alle 30 Minuten mit Start/Stop/Pause Funktionalität.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum
import json
import logging
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

class SchedulerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"

class SchedulerConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 30
    status: SchedulerStatus = SchedulerStatus.STOPPED
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    created_at: str = datetime.now(timezone.utc).isoformat()

class SystemtestScheduler:
    """
    Nativer Scheduler für automatische Systemtests.
    """
    
    _instance = None
    SCHEDULER_KEY = "bruno:scheduler:systemtest"
    SCHEDULER_STATE_KEY = "bruno:scheduler:state"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemtestScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._paused = False
    
    async def initialize(self):
        """Initialisiert den Scheduler aus Redis oder mit Defaults."""
        try:
            await redis_client.connect()
            config_data = await redis_client.redis.get(self.SCHEDULER_KEY)
            
            if config_data:
                config = SchedulerConfig.parse_raw(config_data)
                logger.info(f"Scheduler Config geladen: {config.status}")
                
                if config.status == SchedulerStatus.RUNNING:
                    await self.start()
            else:
                # Default Config speichern
                config = SchedulerConfig()
                await self._save_config(config)
                logger.info("Scheduler mit Default-Config initialisiert")
                
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren des Schedulers: {e}")
    
    async def _save_config(self, config: SchedulerConfig):
        """Speichert Scheduler-Konfiguration in Redis."""
        await redis_client.redis.set(self.SCHEDULER_KEY, config.json())
    
    async def _get_config(self) -> SchedulerConfig:
        """Holt Scheduler-Konfiguration aus Redis."""
        config_data = await redis_client.redis.get(self.SCHEDULER_KEY)
        if config_data:
            return SchedulerConfig.parse_raw(config_data)
        return SchedulerConfig()
    
    async def start(self) -> Dict[str, Any]:
        """
        Startet den Scheduler.
        """
        try:
            if self._running and not self._paused:
                return {"status": "error", "message": "Scheduler läuft bereits"}
            
            if self._paused:
                self._paused = False
                config = await self._get_config()
                config.status = SchedulerStatus.RUNNING
                await self._save_config(config)
                logger.info("Scheduler fortgesetzt")
                return {"status": "success", "message": "Scheduler fortgesetzt"}
            
            # Config aktualisieren
            config = await self._get_config()
            config.enabled = True
            config.status = SchedulerStatus.RUNNING
            await self._save_config(config)
            
            # Scheduler Task starten
            self._running = True
            self._paused = False
            self._task = asyncio.create_task(self._run_scheduler())
            
            logger.info(f"Scheduler gestartet (Intervall: {config.interval_minutes} Minuten)")
            return {
                "status": "success", 
                "message": f"Scheduler gestartet (alle {config.interval_minutes} Minuten)",
                "next_run": config.next_run
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Schedulers: {e}")
            return {"status": "error", "message": str(e)}
    
    async def stop(self) -> Dict[str, Any]:
        """
        Stoppt den Scheduler komplett.
        """
        try:
            if not self._running:
                return {"status": "error", "message": "Scheduler läuft nicht"}
            
            self._running = False
            self._paused = False
            
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
            
            # Config aktualisieren
            config = await self._get_config()
            config.status = SchedulerStatus.STOPPED
            config.next_run = None
            await self._save_config(config)
            
            logger.info("Scheduler gestoppt")
            return {"status": "success", "message": "Scheduler gestoppt"}
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Schedulers: {e}")
            return {"status": "error", "message": str(e)}
    
    async def pause(self) -> Dict[str, Any]:
        """
        Pausiert den Scheduler (kann fortgesetzt werden).
        """
        try:
            if not self._running:
                return {"status": "error", "message": "Scheduler läuft nicht"}
            
            if self._paused:
                return {"status": "error", "message": "Scheduler ist bereits pausiert"}
            
            self._paused = True
            
            # Config aktualisieren
            config = await self._get_config()
            config.status = SchedulerStatus.PAUSED
            await self._save_config(config)
            
            logger.info("Scheduler pausiert")
            return {"status": "success", "message": "Scheduler pausiert"}
            
        except Exception as e:
            logger.error(f"Fehler beim Pausieren des Schedulers: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Gibt aktuellen Scheduler-Status zurück.
        """
        try:
            config = await self._get_config()
            
            return {
                "status": config.status,
                "enabled": config.enabled,
                "interval_minutes": config.interval_minutes,
                "last_run": config.last_run,
                "next_run": config.next_run,
                "run_count": config.run_count,
                "is_running": self._running and not self._paused,
                "is_paused": self._paused
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Scheduler-Status: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_interval(self, interval_minutes: int) -> Dict[str, Any]:
        """
        Aktualisiert das Zeitintervall.
        """
        try:
            if interval_minutes < 1:
                return {"status": "error", "message": "Intervall muss mindestens 1 Minute sein"}
            
            config = await self._get_config()
            config.interval_minutes = interval_minutes
            await self._save_config(config)
            
            logger.info(f"Scheduler-Intervall aktualisiert: {interval_minutes} Minuten")
            return {
                "status": "success", 
                "message": f"Intervall auf {interval_minutes} Minuten gesetzt"
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Intervalls: {e}")
            return {"status": "error", "message": str(e)}

    async def _evaluate_phantom_trades(self):
        """
        Wertet abgelaufene Phantom-Trades aus.
        Holt den aktuellen Preis und berechnet den hypothetischen P&L.
        Schreibt Ergebnis in trade_debriefs mit trade_mode='phantom'.
        """
        try:
            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            pending_raw = await redis_client.redis.lrange("bruno:phantom_trades:pending", 0, -1)
            completed_key = "bruno:phantom_trades:completed_ids"

            remaining = []
            evaluated_count = 0

            for item_raw in pending_raw:
                phantom = json.loads(item_raw)
                phantom_id = phantom["phantom_id"]

                if await redis_client.redis.sismember(completed_key, phantom_id):
                    continue

                lock_key = f"bruno:phantom_trades:lock:{phantom_id}"
                acquired = await redis_client.redis.set(lock_key, now.isoformat(), nx=True, ex=86400)
                if not acquired:
                    remaining.append(item_raw)
                    continue

                should_keep = False
                evaluate_at = datetime.fromisoformat(phantom["evaluate_at"])

                try:
                    if now < evaluate_at:
                        should_keep = True
                        continue

                    ticker = await redis_client.get_cache("market:ticker:BTCUSDT") or {}
                    current_price = float(ticker.get("last_price", 0))
                    entry_price = float(phantom.get("entry_price", 0))

                    if current_price <= 0 or entry_price <= 0:
                        should_keep = True
                        continue

                    phantom_long_pct = (current_price - entry_price) / entry_price
                    phantom_short_pct = (entry_price - current_price) / entry_price

                    phantom["exit_price"] = current_price
                    phantom["phantom_long_pct"] = round(phantom_long_pct, 4)
                    phantom["phantom_short_pct"] = round(phantom_short_pct, 4)
                    phantom["status"] = "evaluated"
                    phantom["evaluated_at"] = now.isoformat()

                    async with AsyncSessionLocal() as session:
                        await session.execute(
                            text("""
                                INSERT INTO trade_debriefs (
                                    id, trade_id, timestamp, decision_quality,
                                    key_signal, improvement, pattern, regime_assessment,
                                    trade_mode, raw_llm_response
                                ) VALUES (
                                    :id, :trade_id, :timestamp, :decision_quality,
                                    :key_signal, :improvement, :pattern, :regime_assessment,
                                    :trade_mode, :raw_llm_response
                                )
                                ON CONFLICT (id) DO NOTHING
                            """),
                            {
                                "id": phantom_id,
                                "trade_id": phantom_id,
                                "timestamp": now,
                                "decision_quality": "PHANTOM",
                                "key_signal": f"phantom_long_pct={phantom['phantom_long_pct']}, phantom_short_pct={phantom['phantom_short_pct']}",
                                "improvement": "N/A",
                                "pattern": phantom.get("aborted_at", "hold_cycle"),
                                "regime_assessment": phantom.get("regime", "unknown"),
                                "trade_mode": "phantom",
                                "raw_llm_response": json.dumps(phantom),
                            },
                        )
                        await session.commit()

                    await redis_client.redis.sadd(completed_key, phantom_id)
                    await redis_client.redis.lpush(
                        "bruno:phantom_trades:evaluated", json.dumps(phantom)
                    )
                    await redis_client.redis.ltrim("bruno:phantom_trades:evaluated", 0, 999)
                    evaluated_count += 1

                except Exception as e:
                    should_keep = True
                    logger.error(f"Phantom Trade {phantom_id} Evaluation Fehler: {e}")
                finally:
                    await redis_client.redis.delete(lock_key)

                if should_keep:
                    remaining.append(item_raw)

            if pending_raw:
                await redis_client.redis.delete("bruno:phantom_trades:pending")
                for item in remaining:
                    await redis_client.redis.rpush("bruno:phantom_trades:pending", item)
                if evaluated_count > 0:
                    logger.info(f"Phantom Trades ausgewertet: {evaluated_count}")

        except Exception as e:
            logger.error(f"Phantom Trade Evaluation Fehler: {e}")
    
    async def _run_scheduler(self):
        """
        Haupt-Scheduler-Loop.
        """
        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue
                
                config = await self._get_config()
                interval_seconds = config.interval_minutes * 60
                
                # Nächste Laufzeit berechnen
                next_run = datetime.now(timezone.utc).isoformat()
                config.next_run = next_run
                await self._save_config(config)
                
                logger.info(f"Systemtest gestartet ( automatischer Lauf #{config.run_count + 1} )")
                
                # Systemtest durchführen
                try:
                    # Import hier um circular import zu vermeiden
                    from app.routers.systemtest import run_systemtest
                    result = await run_systemtest()
                    logger.info(f"Automatischer Systemtest abgeschlossen: {result.overall_status}")
                except Exception as test_error:
                    logger.error(f"Fehler beim automatischen Systemtest: {test_error}")

                try:
                    await self._evaluate_phantom_trades()
                except Exception as phantom_error:
                    logger.error(f"Fehler bei der Phantom-Trade-Auswertung: {phantom_error}")
                
                # Last run aktualisieren
                config.last_run = datetime.now(timezone.utc).isoformat()
                config.run_count += 1
                await self._save_config(config)
                
                # Warten bis zum nächsten Lauf
                logger.info(f"Warte {config.interval_minutes} Minuten bis zum nächsten Lauf...")
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Scheduler Task wurde abgebrochen")
                break
            except Exception as e:
                logger.error(f"Fehler im Scheduler Loop: {e}")
                await asyncio.sleep(60)  # Bei Fehler 1 Minute warten

# Singleton-Instanz
scheduler = SystemtestScheduler()
