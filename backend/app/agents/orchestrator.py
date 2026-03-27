import asyncio
import logging
from typing import Dict, List
import json
from app.agents.base import BaseAgent
from app.agents.deps import AgentDependencies

logger = logging.getLogger("orchestrator")

class AgentOrchestrator:
    """Verwaltet den Startup, Shutdown und Restart der Agenten (Supervision Tree)."""

    # Definierte Start-Reihenfolge zur Einhaltung der Daten-Pipeline Topologie
    # Ingestion liefert Daten -> Quant berechnet daraus Indikatoren ...
    STARTUP_STAGES: List[List[str]] = [
        ["ingestion"],
        ["quant", "context"],
        ["risk"],
        ["execution"],
    ]

    def __init__(self, deps: AgentDependencies):
        self.deps = deps
        self._agents: Dict[str, BaseAgent] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    def register(self, agent_id: str, agent: BaseAgent) -> None:
        self._agents[agent_id] = agent
        logger.info(f"Agent {agent_id} registriert.")

    async def start_all(self) -> None:
        logger.info("Starte Agent-Pipeline...")
        for i, stage in enumerate(self.STARTUP_STAGES):
            await self._start_stage(i+1, stage)
        logger.info("Agent-Pipeline vollständig gestartet.")

    async def _start_stage(self, stage_num: int, stage_agents: List[str]) -> None:
        active = [aid for aid in stage_agents if aid in self._agents]
        if not active:
            return

        logger.info(f"=== Starte Stufe {stage_num}: {active} ===")
        for agent_id in active:
            agent = self._agents[agent_id]
            try:
                # Setup MUSS erfolgreich sein
                await asyncio.wait_for(agent.setup(), timeout=60.0)
                logger.info(f"  ✅ {agent_id}: Setup erfolgreich")
                
                # Als supervised task starten
                task = asyncio.create_task(self._supervised_run(agent_id, agent), name=f"agent-{agent_id}")
                self._tasks[agent_id] = task
            except asyncio.TimeoutError:
                logger.error(f"  ❌ {agent_id}: Setup Timeout (60s) - Agent wird übersprungen")
            except Exception as e:
                logger.error(f"  ❌ {agent_id}: Setup Fehler - {e}")
        
        # Kleine Grace-Period zwischen den Stufen
        await asyncio.sleep(2)

    async def _supervised_run(self, agent_id: str, agent: BaseAgent, max_restarts: int = 5) -> None:
        """Restart-Logic, falls ein Agent unerwartet stirbt."""
        restart_count = 0
        while restart_count <= max_restarts and not self._shutdown_event.is_set():
            try:
                await agent.run()
                break  # Sauber über agent.stop() beendet
            except asyncio.CancelledError:
                break
            except Exception as e:
                restart_count += 1
                logger.error(f"Agent {agent_id} abgestürzt ({restart_count}/{max_restarts}): {e}")
                try:
                    await agent.teardown()
                except Exception as cleanup_err:
                    logger.warning(f"Cleanup von {agent_id} nach Crash fehlgeschlagen: {cleanup_err}")
                
                if restart_count > max_restarts:
                    logger.critical(f"Agent {agent_id} final deaktiviert (Max Restarts).")
                    break

                wait_secs = min(30 * restart_count, 300)
                logger.info(f"Restart {agent_id} in {wait_secs}s...")
                await asyncio.sleep(wait_secs)
                
                try:
                    await asyncio.wait_for(agent.setup(), timeout=30.0)
                except Exception as e:
                    logger.error(f"Re-Setup {agent_id} fehlgeschlagen: {e}")

    async def stop_all(self, timeout: float = 15.0) -> None:
        """Gibt allen Agenten das Signal zum Stoppen."""
        logger.info("Stoppe alle Agenten...")
        self._shutdown_event.set()
        
        for agent in self._agents.values():
            await agent.stop()
        
        if self._tasks:
            done, pending = await asyncio.wait(
                self._tasks.values(), timeout=timeout, return_when=asyncio.ALL_COMPLETED
            )
            for t in pending:
                t.cancel()

        for agent in self._agents.values():
            try:
                await agent.teardown()
            except Exception:
                pass
        
        logger.info("Alle Agenten beendet.")

    async def restart_agent(self, agent_id: str) -> bool:
        """Einzelnen Agenten neu starten (wird via Redis angesteuert)."""
        if agent_id not in self._agents:
            return False
            
        agent = self._agents[agent_id]
        logger.info(f"Manueller Restart von {agent_id}...")
        
        await agent.stop()
        if agent_id in self._tasks:
            try:
                await asyncio.wait_for(asyncio.shield(self._tasks[agent_id]), timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._tasks[agent_id].cancel()
        
        try:
            await agent.teardown()
        except:
            pass

        try:
            await agent.setup()
            task = asyncio.create_task(self._supervised_run(agent_id, agent), name=f"agent-{agent_id}")
            self._tasks[agent_id] = task
            logger.info(f"Manueller Restart von {agent_id} erfolgreich.")
            return True
        except Exception as e:
            logger.error(f"Manueller Restart {agent_id} fehlgeschlagen: {e}")
            return False

    async def start_agent(self, agent_id: str) -> bool:
        """Einzelnen Agenten starten (wird via Redis angesteuert)."""
        if agent_id not in self._agents:
            return False
            
        agent = self._agents[agent_id]
        if agent._running:
            logger.info(f"Agent {agent_id} läuft bereits.")
            return True
            
        logger.info(f"Manueller Start von {agent_id}...")
        try:
            await agent.setup()
            task = asyncio.create_task(self._supervised_run(agent_id, agent), name=f"agent-{agent_id}")
            self._tasks[agent_id] = task
            logger.info(f"Manueller Start von {agent_id} erfolgreich.")
            return True
        except Exception as e:
            logger.error(f"Manueller Start {agent_id} fehlgeschlagen: {e}")
            return False

    async def listen_for_commands(self) -> None:
        """Lauscht auf API-Anweisungen (wie restart/stop)."""
        pubsub = await self.deps.redis.subscribe_channel("worker:commands")
        if not pubsub:
            return

        while not self._shutdown_event.is_set():
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    cmd = json.loads(msg['data'])
                    action = cmd.get("command")
                    a_id = cmd.get("agent_id")
                    
                    if action == "restart" and a_id:
                        await self.restart_agent(a_id)
                    elif action == "start" and a_id:
                        await self.start_agent(a_id)
                    elif action == "stop" and a_id:
                        if a_id in self._agents:
                            await self._agents[a_id].stop()
                    elif action == "shutdown":
                        await self.stop_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Command listener error: {e}")
                await asyncio.sleep(1)

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
