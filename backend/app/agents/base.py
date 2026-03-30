from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import asyncio
import logging
import traceback
import json

if TYPE_CHECKING:
    from app.agents.deps import AgentDependencies

class AgentState:
    """Tracking-Metriken für einen Agenten."""
    def __init__(self):
        self.running: bool = False
        self.error_count: int = 0
        self.consecutive_errors: int = 0
        self.processed_count: int = 0
        self.start_time: Optional[datetime] = None
        self.last_process_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.health: str = "healthy" # healthy, degraded, error
        self.sub_state: str = "initializing" # Status-Details für das Dashboard

class BaseAgent(ABC):
    """
    Abstrakte Basis-Klasse für alle Agenten.
    Übernimmt Heartbeat-Management, Logging und Error-Reporting.
    """
    def __init__(self, agent_id: str, deps: "AgentDependencies"):
        self.agent_id = agent_id
        self.deps = deps
        self.state = AgentState()
        self.logger = logging.getLogger(f"agent.{agent_id}")
        # LogManager Referenz für einfacheren Zugriff
        self.log_manager = deps.log_manager
        self._max_consecutive_errors = 10

    @abstractmethod
    async def setup(self) -> None:
        """
        Einmalige Initialisierung.
        Muss vom Orchestrator VOR run() aufgerufen werden.
        """
        pass

    async def teardown(self) -> None:
        """Optional: Cleanup wenn der Agent gestoppt wird."""
        pass

    @abstractmethod
    async def run(self) -> None:
        """
        Hauptschleife. Implementiert in PollingAgent oder StreamingAgent.
        """
        pass

    async def stop(self) -> None:
        """Signal an run(), sich sauber zu beenden."""
        self.state.running = False
        self.logger.info(f"Stop-Signal erhalten.")

    async def _send_heartbeat(self) -> None:
        """Meldet Agenten-Vitalfunktionen an Redis."""
        try:
            heartbeat = {
                "agent_id": self.agent_id,
                "status": "running" if self.state.running else "stopped",
                "sub_state": self.state.sub_state,
                "uptime_seconds": (datetime.now(timezone.utc) - self.state.start_time).total_seconds() if self.state.start_time else 0,
                "processed_count": self.state.processed_count,
                "error_count": self.state.error_count,
                "consecutive_errors": self.state.consecutive_errors,
                "last_error": self.state.last_error,
                "health": self.state.health,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if hasattr(self.deps, "redis"):
                await self.deps.redis.set_cache(f"heartbeat:{self.agent_id}", heartbeat, ttl=60)
        except Exception as e:
            self.logger.warning(f"Heartbeat-Fehler: {e}")

    async def _heartbeat_loop(self) -> None:
        """Sende Heartbeats im Hintergrund, während der Agent läuft."""
        while self.state.running:
            await self._send_heartbeat()
            # Alle 15 Sekunden ein Lebenszeichen für maximale Transparenz im Dashboard
            await asyncio.sleep(15)

    async def _report_error(self, error: Exception) -> None:
        """Meldet einen Crash an das System."""
        try:
            from app.core.log_manager import LogLevel, LogCategory
            
            error_msg = f"Agent Error: {str(error)}"
            await self.log_manager.error(
                category=LogCategory.AGENT,
                source=self.agent_id,
                message=error_msg,
                stack_trace=traceback.format_exc()
            )
            
            if hasattr(self.deps, "redis"):
                msg = json.dumps({
                    "agent_id": self.agent_id,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "consecutive": self.state.consecutive_errors
                })
                await self.deps.redis.publish_message("alerts:agent_error", msg)
        except Exception as e:
            self.logger.error(f"Error Reporting failed: {e}")

class PollingAgent(BaseAgent):
    """Agent für zyklische Aufgaben (z.B. alle 30s)."""
    
    @abstractmethod
    async def process(self) -> None:
        """Ein einzelner Verarbeitungs-Zyklus."""
        pass

    @abstractmethod
    def get_interval(self) -> float:
        """Pause zwischen den Zyklen in Sekunden."""
        pass

    async def run(self) -> None:
        self.state.running = True
        self.state.start_time = datetime.now(timezone.utc)

        # Starte Heartbeat-Task im Hintergrund (Universal Pulse)
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        while self.state.running:
            try:
                # Heartbeat wird jetzt parallel im _heartbeat_loop gesendet
                await self.process()
                self.state.processed_count += 1
                self.state.last_process_time = datetime.now(timezone.utc)
                self.state.consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state.error_count += 1
                self.state.consecutive_errors += 1
                self.state.last_error = str(e)
                self.logger.error(f"Fehler in process(): {e}")
                await self._report_error(e)

                if self.state.consecutive_errors >= self._max_consecutive_errors:
                    self.logger.critical(f"Agent pausiert für 5m nach {self._max_consecutive_errors} Fehlern.")
                    self.state.sub_state = "error_paused"
                    await asyncio.sleep(300)
                    self.state.consecutive_errors = 0

            if self.state.running:
                interval = self.get_interval()
                self.state.sub_state = f"idle (waiting {int(interval)}s)"
                await asyncio.sleep(interval)

        # Cleanup
        self.state.running = False
        heartbeat_task.cancel()
        self.logger.info("PollingAgent beendet.")

class StreamingAgent(BaseAgent):
    """Agent für dauerhafte Streams (WebSockets, Pub/Sub)."""

    @abstractmethod
    async def run_stream(self) -> None:
        """
        Blockierender Consumer.
        Der Agent ist verantwortlich, bei self.state.running=False sauber abzubrechen.
        """
        pass

    async def _heartbeat_loop(self) -> None:
        """Sende Heartbeats im Hintergrund, während der Stream läuft."""
        while self.state.running:
            await self._send_heartbeat()
            await asyncio.sleep(30)

    async def run(self) -> None:
        self.state.running = True
        self.state.start_time = datetime.now(timezone.utc)
        self.state.sub_state = "streaming"
        backoff = 1

        # Starte Heartbeat-Task im Hintergrund (Universal Pulse)
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        while self.state.running:
            try:
                # Der Stream blockiert hier, daher brauchen wir den Background-Heartbeat
                await self.run_stream()
                break  # Normales Ende
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state.error_count += 1
                self.state.consecutive_errors += 1
                self.state.last_error = str(e)
                self.state.sub_state = "reconnecting"
                self.logger.error(f"Stream-Fehler: {e}")
                await self._report_error(e)

                if self.state.consecutive_errors >= self._max_consecutive_errors:
                    self.logger.critical(f"Agent pausiert für 5m nach {self._max_consecutive_errors} Fehlern.")
                    self.state.sub_state = "error_paused"
                    await asyncio.sleep(300)
                    self.state.consecutive_errors = 0
                    backoff = 1
                else:
                    wait_time = min(backoff, 60)
                    self.logger.info(f"Reconnect in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    backoff = min(backoff * 2, 60)

        # Cleanup
        self.state.running = False
        heartbeat_task.cancel()
        self.logger.info("StreamingAgent beendet.")

