import asyncio
import logging
from typing import Any, Dict, List, Optional
import json
from app.agents.base import BaseAgent
from app.agents.deps import AgentDependencies
from app.core.log_manager import LogCategory

logger = logging.getLogger("orchestrator")

class AgentOrchestrator:
    """
    Verwaltet den Startup, Shutdown und Restart der Agenten (Supervision Tree).
    
    PROMPT 9: Strict Pipeline für Order-Execution
    =================================================
    Der kritische Order-Pfad ist von losem Pub/Sub zu einer synchronen Pipeline umgebaut:
    
    1. QuantAgent generiert Signal
    2. Orchestrator wartet synchron auf RiskAgent.validate_and_size_order(signal)
    3. RiskAgent holt FRISCHEN Portfolio-State und berechnet Sizes
    4. NUR bei Freigabe: Orchestrator ruft ExecutionAgent.execute_order(order_payload)
    
    Dies eliminiert Race Conditions zwischen Signalgenerierung und Portfolio-Validierung.
    """

    # Definierte Start-Reihenfolge zur Einhaltung der Daten-Pipeline Topologie
    # Ingestion liefert Daten -> Quant/Context/Sentiment berechnen daraus Indikatoren -> Risk prüft -> Execution führt aus
    STARTUP_STAGES: List[List[str]] = [
        ["ingestion"],
        ["technical", "context", "sentiment"],
        ["quant"],
        ["risk"],
        ["execution"],
    ]

    def __init__(self, deps: AgentDependencies):
        self.deps = deps
        self._agents: Dict[str, BaseAgent] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        
        # PROMPT 9: Strict Pipeline Queue
        # Signale werden hier von QuantAgent eingereiht und sequentiell verarbeitet
        self._signal_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._pipeline_task: Optional[asyncio.Task] = None
        self._pipeline_metrics = {
            "signals_processed": 0,
            "signals_approved": 0,
            "signals_rejected": 0,
            "last_processing_time_ms": 0
        }

    async def _emit_lifecycle_log(
        self,
        level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Schreibt Orchestrator-Lifecycle-Ereignisse in den zentralen LogManager."""
        try:
            log_method = getattr(self.deps.log_manager, level, None)
            if callable(log_method):
                await log_method(LogCategory.SYSTEM, "orchestrator", message, details=details)
        except Exception as e:
            logger.debug(f"Lifecycle-Log konnte nicht geschrieben werden: {e}")

    def register(self, agent_id: str, agent: BaseAgent) -> None:
        self._agents[agent_id] = agent
        logger.info(f"Agent {agent_id} registriert.")

    async def start_all(self) -> None:
        logger.info("Starte Agent-Pipeline...")
        await self._emit_lifecycle_log("info", "Starte Agent-Pipeline...")
        for i, stage in enumerate(self.STARTUP_STAGES):
            await self._start_stage(i+1, stage)
        
        # PROMPT 9: Strict Pipeline Task starten
        logger.info("PROMPT 9: Starte Strict Pipeline Task...")
        await self._emit_lifecycle_log("info", "PROMPT 9: Strict Pipeline wird gestartet")
        self._pipeline_task = asyncio.create_task(
            self._run_strict_pipeline(),
            name="strict-pipeline"
        )
        
        logger.info("Agent-Pipeline vollständig gestartet (mit Strict Pipeline).")
        await self._emit_lifecycle_log("info", "Agent-Pipeline vollständig gestartet")

    async def _start_stage(self, stage_num: int, stage_agents: List[str]) -> None:
        active = [aid for aid in stage_agents if aid in self._agents]
        if not active:
            return

        logger.info(f"=== Starte Stufe {stage_num}: {active} ===")
        await self._emit_lifecycle_log("info", f"Starte Stufe {stage_num}: {active}")
        for agent_id in active:
            agent = self._agents[agent_id]
            try:
                # Setup MUSS erfolgreich sein
                await asyncio.wait_for(agent.setup(), timeout=60.0)
                logger.info(f"  ✅ {agent_id}: Setup erfolgreich")
                await self._emit_lifecycle_log("info", f"{agent_id}: Setup erfolgreich")
                
                # Als supervised task starten
                task = asyncio.create_task(self._supervised_run(agent_id, agent), name=f"agent-{agent_id}")
                self._tasks[agent_id] = task
            except asyncio.TimeoutError:
                logger.error(f"  ❌ {agent_id}: Setup Timeout (60s) - Agent wird übersprungen")
                await self._emit_lifecycle_log("error", f"{agent_id}: Setup Timeout (60s) - Agent wird übersprungen")
            except Exception as e:
                logger.error(f"  ❌ {agent_id}: Setup Fehler - {e}")
                await self._emit_lifecycle_log("error", f"{agent_id}: Setup Fehler - {e}")
        
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
        await self._emit_lifecycle_log("info", "Stoppe alle Agenten...")
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
        await self._emit_lifecycle_log("info", "Alle Agenten beendet.")

    async def restart_agent(self, agent_id: str) -> bool:
        """Einzelnen Agenten neu starten (wird via Redis angesteuert)."""
        if agent_id not in self._agents:
            return False
            
        agent = self._agents[agent_id]
        logger.info(f"Manueller Restart von {agent_id}...")
        await self._emit_lifecycle_log("info", f"Manueller Restart von {agent_id}...")
        
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
            await self._emit_lifecycle_log("info", f"Manueller Restart von {agent_id} erfolgreich.")
            return True
        except Exception as e:
            logger.error(f"Manueller Restart {agent_id} fehlgeschlagen: {e}")
            await self._emit_lifecycle_log("error", f"Manueller Restart {agent_id} fehlgeschlagen: {e}")
            return False

    async def start_agent(self, agent_id: str) -> bool:
        """Einzelnen Agenten starten (wird via Redis angesteuert)."""
        if agent_id not in self._agents:
            return False
            
        agent = self._agents[agent_id]
        existing_task = self._tasks.get(agent_id)
        if agent.state.running or (existing_task is not None and not existing_task.done()):
            logger.info(f"Agent {agent_id} läuft bereits.")
            await self._emit_lifecycle_log("info", f"Agent {agent_id} läuft bereits.")
            return True
            
        logger.info(f"Manueller Start von {agent_id}...")
        await self._emit_lifecycle_log("info", f"Manueller Start von {agent_id}...")
        try:
            await agent.setup()
            task = asyncio.create_task(self._supervised_run(agent_id, agent), name=f"agent-{agent_id}")
            self._tasks[agent_id] = task
            logger.info(f"Manueller Start von {agent_id} erfolgreich.")
            await self._emit_lifecycle_log("info", f"Manueller Start von {agent_id} erfolgreich.")
            return True
        except Exception as e:
            logger.error(f"Manueller Start {agent_id} fehlgeschlagen: {e}")
            await self._emit_lifecycle_log("error", f"Manueller Start {agent_id} fehlgeschlagen: {e}")
            return False

    # =========================================================================
    # PROMPT 9: STRICT PIPELINE METHODS
    # =========================================================================
    
    async def submit_signal_for_validation(self, signal: Dict[str, Any]) -> bool:
        """
        PROMPT 9: Einreichen eines Signals in die strikte Validierungs-Pipeline.
        
        Wird vom QuantAgent aufgerufen anstatt direkt Pub/Sub zu verwenden.
        Das Signal wird in die Queue eingereiht und sequentiell verarbeitet.
        
        Args:
            signal: Das Trading-Signal mit allen Metadaten
            
        Returns:
            True wenn Signal in Queue eingereiht, False wenn Queue voll
        """
        try:
            self._signal_queue.put_nowait(signal)
            logger.info(f"PROMPT 9 PIPELINE: Signal eingereiht [{signal.get('strategy_slot', 'unknown')}] "
                       f"Direction={signal.get('direction', 'unknown').upper()}")
            return True
        except asyncio.QueueFull:
            logger.error("PROMPT 9 PIPELINE: Signal Queue voll - Signal verworfen!")
            return False
    
    async def _run_strict_pipeline(self) -> None:
        """
        PROMPT 9: Hauptpipeline - Sequential Await Path
        
        1. Hole Signal aus Queue
        2. Rufe RiskAgent.validate_and_size_order(signal) - SYNCHRONER AWAIT
        3. Bei Freigabe: Rufe ExecutionAgent.execute_order(order_payload) - SYNCHRONER AWAIT
        
        Diese Methode läuft als eigener Task und garantiert:
        - Keine Race Conditions zwischen Signalgenerierung und Portfolio-Validierung
        - Frischer Portfolio-State bei jeder Validierung
        - Atomare Order-Ausführung
        """
        logger.info("PROMPT 9: Strict Pipeline gestartet - Warte auf Signale...")
        
        while not self._shutdown_event.is_set():
            try:
                # Timeout damit wir regelmäßig das shutdown_event prüfen können
                signal = await asyncio.wait_for(
                    self._signal_queue.get(), 
                    timeout=1.0
                )
                
                start_time = asyncio.get_event_loop().time()
                self._pipeline_metrics["signals_processed"] += 1
                
                logger.info(
                    f"PROMPT 9 PIPELINE: Verarbeite Signal [{signal.get('strategy_slot', 'unknown')}] "
                    f"Queue-Depth={self._signal_queue.qsize()}"
                )
                
                # === SCHRITT 2: RiskAgent synchron aufrufen ===
                risk_agent = self._agents.get("risk")
                execution_agent = self._agents.get("execution")
                
                if not risk_agent or not execution_agent:
                    logger.error("PROMPT 9 PIPELINE: RiskAgent oder ExecutionAgent nicht verfügbar!")
                    self._signal_queue.task_done()
                    continue
                
                # SYNCHRONER AWAIT: RiskAgent holt frischen Portfolio-State
                order_payload = await risk_agent.validate_and_size_order(signal)
                
                if order_payload is None:
                    # Signal wurde von RiskAgent abgelehnt
                    self._pipeline_metrics["signals_rejected"] += 1
                    logger.info(
                        f"PROMPT 9 PIPELINE: Signal ABGELEHNT [{signal.get('strategy_slot', 'unknown')}] "
                        f"- Risk-Veto oder ungenügende Daten"
                    )
                else:
                    # === SCHRITT 3: ExecutionAgent synchron aufrufen ===
                    self._pipeline_metrics["signals_approved"] += 1
                    logger.info(
                        f"PROMPT 9 PIPELINE: Signal FREIGEGEBEN [{order_payload.get('strategy_slot', 'unknown')}] "
                        f"Size={order_payload.get('sizing', {}).get('position_size_usdt', 0):.2f} USDT"
                    )
                    
                    # SYNCHRONER AWAIT: Order wird atomar ausgeführt
                    await execution_agent.execute_order(order_payload)
                
                # Metrics
                processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
                self._pipeline_metrics["last_processing_time_ms"] = processing_time
                
                logger.info(
                    f"PROMPT 9 PIPELINE: Signal-Verarbeitung abgeschlossen in {processing_time:.1f}ms "
                    f"[Total: {self._pipeline_metrics['signals_processed']}, "
                    f"Approved: {self._pipeline_metrics['signals_approved']}, "
                    f"Rejected: {self._pipeline_metrics['signals_rejected']}]"
                )
                
                self._signal_queue.task_done()
                
            except asyncio.TimeoutError:
                # Normales Timeout für shutdown_check, nichts tun
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PROMPT 9 PIPELINE FEHLER: {e}", exc_info=True)
                # Queue nicht blockieren
                try:
                    self._signal_queue.task_done()
                except:
                    pass
    
    async def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Gibt aktuelle Pipeline-Metriken zurück."""
        return {
            **self._pipeline_metrics,
            "queue_depth": self._signal_queue.qsize(),
            "queue_maxsize": self._signal_queue.maxsize,
            "pipeline_active": self._pipeline_task is not None and not self._pipeline_task.done()
        }
    
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
                    # PROMPT 9: Pipeline Metrics Command
                    elif action == "pipeline_metrics":
                        metrics = await self.get_pipeline_metrics()
                        await self.deps.redis.set_cache("bruno:pipeline:metrics", metrics, ttl=60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Command listener error: {e}")
                await asyncio.sleep(1)

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
