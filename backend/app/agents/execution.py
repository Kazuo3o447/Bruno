import asyncio
import json
from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import RiskDecision, TradeExecution, SignalDirection
from app.schemas.models import TradeAuditLog
from datetime import datetime, timezone

class ExecutionAgentV2(StreamingAgent):
    """
    Phase 3: Execution Agent
    Führt Trades basierend auf RiskDecision durch (Paper-Mode).
    Speichert den vollen Audit Trail in der PostgreSQL Datenbank.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("execution", deps)

    async def setup(self) -> None:
        self.logger.info("ExecutionAgent setup abgeschlossen.")
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message="Execution Agent bereit für Paper Trading."
        )

    async def _execute_paper_trade(self, decision: RiskDecision) -> None:
        if not decision.approved or decision.action == SignalDirection.HOLD:
            self.logger.info(f"Ignoriere abgelehnte/HOLD Entscheidung für {decision.symbol}")
            return

        # Letzten Preis abrufen (Fallback auf RiskDecision Preis)
        price = decision.quant_signal.indicators.get("price", 0.0) if decision.quant_signal else 0.0
        
        # Menge berechnen
        quantity = decision.position_size_usd / price if price > 0 else 0.0
        if quantity <= 0.0:
            self.logger.warning("Trade Position ist <= 0, breche ab.")
            return

        trade_status = "filled" # In Paper immer filled
        
        # Audit Log in DB
        async with self.deps.db_session_factory() as session:
            try:
                # Quant und Sentiment scores extrahieren
                q_score = decision.quant_signal.confidence if decision.quant_signal else 0.0
                s_score = decision.sentiment_signal.score if decision.sentiment_signal else 0.0
                r_score = decision.risk_reward_ratio

                log = TradeAuditLog(
                    id=decision.correlation_id,
                    timestamp=datetime.now(timezone.utc),
                    symbol=decision.symbol,
                    action=decision.action.value.lower(),
                    price=price,
                    quantity=quantity,
                    total=decision.position_size_usd,
                    quant_score=q_score,
                    sentiment_score=s_score,
                    risk_score=r_score,
                    llm_reasoning=decision.reasoning,
                    llm_model=self.deps.ollama.reasoning_model,
                    status=trade_status,
                    filled_at=datetime.now(timezone.utc)
                )
                
                session.add(log)
                await session.commit()
                
                self.state.health = "healthy"
                await self.log_manager.info(
                    category="TRADE",
                    source=self.agent_id,
                    message=f"PAPER TRADE FILLED: {log.action.upper()} {log.quantity:.4f} {log.symbol} @ ${log.price:.2f}",
                    details={"order_id": str(log.id), "total_usd": log.total}
                )
                self.logger.info(f"✅ PAPER TRADE FILLED: {log.action.upper()} {log.quantity:.4f} {log.symbol} @ ${log.price:.2f}")

                # Trade Event veröffentlichen (z.B. für Frontend/Notifications)
                execution_event = TradeExecution(
                    correlation_id=decision.correlation_id,
                    agent_id=self.agent_id,
                    symbol=decision.symbol,
                    action=log.action.upper(),
                    entry_price=log.price,
                    quantity=log.quantity,
                    position_size_usd=log.total,
                    stop_loss=decision.stop_loss_price,
                    take_profit=decision.take_profit_price,
                    risk_decision=decision,
                    execution_status="PAPER",
                    order_id=log.id
                )
                
                await self.deps.redis.publish_message("trades:executions", execution_event.model_dump_json())

            except Exception as e:
                self.state.health = "error"
                await self.log_manager.error(
                    category="DATABASE",
                    source=self.agent_id,
                    message=f"Fehler bei Paper Trade Ausführung: {e}",
                    stack_trace=str(e)
                )
                self.logger.error(f"Fehler bei Paper Trade Ausführung: {e}")
                await session.rollback()

    async def run_stream(self) -> None:
        pubsub = await self.deps.redis.subscribe_channel("risk:decisions")
        if not pubsub:
            return
            
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    payload = json.loads(msg['data'])
                    decision = RiskDecision(**payload)
                    await self._execute_paper_trade(decision)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Fehler im Execution-Stream: {e}")
                await asyncio.sleep(1)
