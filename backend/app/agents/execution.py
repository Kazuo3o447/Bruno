from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.exchange_manager import AuthenticatedExchangeClient
from app.schemas.models import TradeAuditLog
from datetime import datetime, timezone
import json
import asyncio
import time
from typing import Dict

class ExecutionAgentV3(StreamingAgent):
    """
    Phase 7: Zero-Latency Execution Engine.
    Hält Veto-Entscheidungen im RAM.
    Trennt Order-Firing (0ms Latenz) von Audit/Logging.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("execution", deps)
        self.exm = AuthenticatedExchangeClient(redis=deps.redis)
        self._local_veto_active = True # Default safe State
        self._last_veto_reason = "Initialisierung..."

    async def setup(self) -> None:
        self.logger.info("ExecutionAgentV3 (Zero-Latency) gestartet.")
        # Startzustand aus Redis laden
        veto_raw = await self.deps.redis.redis.get("bruno:veto:state")
        if veto_raw:
            data = json.loads(veto_raw)
            self._local_veto_active = data.get("Veto_Active", True)
            self._last_veto_reason = data.get("Reason", "Redis Cache")

    async def _listen_to_risk_veto(self):
        """Hintergrund-Task: Aktualisiert den lokalen RAM-State (0ms Check)."""
        pubsub = await self.deps.redis.subscribe_channel("bruno:pubsub:veto")
        self.logger.info("Veto-Listener aktiv.")
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    data = json.loads(msg['data'])
                    self._local_veto_active = data.get("Veto_Active", True)
                    self._last_veto_reason = data.get("Reason", "PubSub Update")
                    if self._local_veto_active:
                        self.logger.warning(f"LOCAL VETO AKTIV: {self._last_veto_reason}")
            except Exception as e:
                self.logger.error(f"Veto-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def _execute_trade(self, signal: Dict):
        """Der kritische Pfad. 0ms RAM-Check und sofortiges Firing."""
        start_exec = time.perf_counter()
        
        # 1. RAM-CHECK (0ms Latenz)
        if self._local_veto_active:
            self.logger.info(f"Signal blockiert durch Veto: {self._last_veto_reason}")
            return

        # ── Preis-Validierung ─────────────────────────────────────────
        # Verhindert Orders mit price=0 (QuantAgent-Bug war: kein Preis im Signal)
        signal_price = signal.get("price", 0.0)
        if signal_price <= 0:
            self.logger.error(
                f"ABBRUCH: Signal ohne validen Preis empfangen. "
                f"Signal: {signal}. "
                f"Prüfe ob QuantAgent 'price' im Signal-Dict hat."
            )
            return

        symbol = signal.get("symbol")
        side = signal.get("side")
        amount = signal.get("amount", 0.01)

        if not symbol or not isinstance(symbol, str):
            self.logger.error(f"ABBRUCH: Ungültiges oder fehlendes Symbol im Signal: {signal}")
            return

        if side not in {"buy", "sell"}:
            self.logger.error(f"ABBRUCH: Ungültige Signal-Seite empfangen: {signal}")
            return

        if amount <= 0:
            self.logger.error(f"ABBRUCH: Ungültige Signal-Menge empfangen: {signal}")
            return

        # 2. IMMEDIATE ORDER FIRING (OR SHADOW SIMULATION)
        try:
            if self.deps.config.DRY_RUN:
                # ABSOLUTER DRY-RUN BLOCK (Phase 7.5 Audit)
                exec_latency = (time.perf_counter() - start_exec) * 1000
                simulated_fee = (amount * signal_price) * 0.0004 # 0.04% Taker-Fee
                
                # Simulation der Netzwerklatenz-Slippage (Random Noise für Audit)
                simulated_fill_price = signal_price * 1.0001 if side == "buy" else signal_price * 0.9999
                
                self.logger.info(f"🚧 SIMULIERTER TRADE (DRY_RUN): {side.upper()} {amount} {symbol} @ {simulated_fill_price:.2f}")
                
                # Mock-Order Objekt für Audit-Logging
                order = {
                    "id": f"sim_{int(datetime.now().timestamp())}",
                    "price": simulated_fill_price,
                    "amount": amount,
                    "cost": amount * simulated_fill_price,
                    "fee": simulated_fee,
                    "status": "simulated"
                }
                
                asyncio.create_task(self._audit_trade(signal, order, exec_latency))
                return

            # ECHTE ORDER AUSFÜHRUNG (Nur wenn DRY_RUN=False)
            order = await self.exm.create_order(symbol, side, amount)
            exec_latency = (time.perf_counter() - start_exec) * 1000
            self.logger.info(f"✅ ECHTE ORDER GEFEUERT: {side.upper()} {amount} {symbol} in {exec_latency:.2f}ms")
            
            # 3. ASYNCHRONOUS AUDIT & LOGGING (Nicht-blockierend)
            asyncio.create_task(self._audit_trade(signal, order, exec_latency))

        except Exception as e:
            self.logger.error(f"KRITISCHER FEHLER BEI ORDER-AUSFÜHRUNG: {e}")

    async def _audit_trade(self, signal: Dict, order: Dict, latency: float):
        """Speichert den Audit-Trail in der DB (nachdem die Order raus ist)."""
        try:
            async with self.deps.db_session_factory() as session:
                log = TradeAuditLog(
                    id=order.get('id', str(datetime.now().timestamp())),
                    timestamp=datetime.now(timezone.utc),
                    symbol=signal.get('symbol'),
                    action=signal.get('side'),
                    price=order.get('price', 0.0), # Actual / Simulated price
                    quantity=order.get('amount', 0.0),
                    total=order.get('cost', 0.0),
                    status=order.get('status', 'filled'),
                    
                    # Enhanced Telemetry (Phase 7.5 Audit)
                    latency_exec_ms=latency,
                    signal_price=signal.get('price', 0.0),
                    simulated_fill_price=order.get('price', 0.0),
                    slippage_bps=((order.get('price', 0.0) / signal.get('price', 1.0)) - 1) * 10000,
                    simulated_fee_usdt=order.get('fee', 0.0), # 0.04% for simulated, or real fee
                    latency_ms=latency # Total processing latency
                )
                session.add(log)
                await session.commit()
                
            await self.log_manager.info(
                category="TRADE",
                source=self.agent_id,
                message=f"Audit completed for order {order.get('id')}",
                details={"latency_ms": latency}
            )
        except Exception as e:
            self.logger.error(f"Audit-Log Fehler: {e}")

    async def _listen_to_signals(self):
        """Hintergrund-Task: Empfängt Trading-Signale."""
        pubsub = await self.deps.redis.subscribe_channel("bruno:pubsub:signals")
        self.logger.info("Signal-Listener aktiv.")
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    signal = json.loads(msg['data'])
                    await self._execute_trade(signal)
            except Exception as e:
                self.logger.error(f"Signal-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def run_stream(self) -> None:
        """Parallele Ausführung der Listener."""
        await asyncio.gather(
            self._listen_to_risk_veto(),
            self._listen_to_signals()
        )

