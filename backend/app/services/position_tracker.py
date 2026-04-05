"""
PositionTracker — Phase D Core Service

Einzige Quelle der Wahrheit für den aktuellen Positions-State.
Trennt sauber: Redis (Live-State, 0ms Check) vs. DB (Audit-Trail, async).

Regeln:
- Immer genau 0 oder 1 offene Position pro Symbol
- MAE/MFE werden lückenlos getrackt (Grundlage für Post-Trade Debrief)
- Phase-C-Felder (llm_reasoning, grss_at_entry etc.) sind forward-kompatibel
  und optional — beim Start ohne LLM-Cascade werden sie leer gelassen
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)

REDIS_KEY = "bruno:position:{symbol}"


class PositionTracker:
    """
    Verwaltet offene Positionen über Redis (Live) + DB (Audit).

    Alle Methoden sind idempotent und crash-safe.
    """

    def __init__(self, redis: RedisClient, db_session_factory):
        self.redis = redis
        self.db_session_factory = db_session_factory

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    async def has_open_position(self, symbol: str) -> bool:
        """RAM-schneller Check — vor jedem neuen Trade aufrufen."""
        pos = await self.redis.get_cache(REDIS_KEY.format(symbol=symbol))
        return pos is not None and pos.get("status") == "open"

    async def get_open_position(self, symbol: str) -> Optional[dict]:
        """Gibt die offene Position zurück oder None."""
        pos = await self.redis.get_cache(REDIS_KEY.format(symbol=symbol))
        if pos and pos.get("status") == "open":
            return pos
        return None

    async def list_open_positions(self) -> list[dict]:
        """Gibt alle offenen Positionen aus Redis zurück."""
        if not getattr(self.redis, "redis", None):
            return []

        positions: list[dict] = []
        async for key in self.redis.redis.scan_iter(match="bruno:position:*"):
            pos = await self.redis.get_cache(key)
            if pos and pos.get("status") == "open":
                positions.append(pos)

        positions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return positions

    async def open_position(
        self,
        symbol: str,
        side: str,                   # "long" | "short"
        entry_price: float,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float,
        entry_trade_id: str,
        take_profit_1_price: float = 0.0,
        take_profit_2_price: float = 0.0,
        tp1_size_pct: float = 0.50,
        tp2_size_pct: float = 0.50,
        breakeven_trigger_pct: float = 0.0,
        # NEU: Scaling-Out Felder
        take_profit_1_pct: float = 0.012,
        take_profit_2_pct: float = 0.025,
        tp1_hit: bool = False,
        atr_trailing_enabled: bool = False,
        max_favorable_price: float = 0.0,
        min_favorable_price: float = 0.0,
        # Phase-C Felder — optional, werden nach LLM-Cascade befüllt
        grss_at_entry: float = 0.0,
        layer1_output: Optional[dict] = None,
        layer2_output: Optional[dict] = None,
        layer3_output: Optional[dict] = None,
        regime: str = "unknown",
        order_type: str = "market",
        slippage_bps: float = 0.0,
        market_conditions: Optional[dict] = None,
        **kwargs  # Alle zusätzlichen Felder durchreichen
    ) -> str:
        """
        Eröffnet eine neue Position.
        Wirft ValueError wenn bereits eine offene Position existiert.
        Gibt die Position-ID zurück.
        """
        if await self.has_open_position(symbol):
            raise ValueError(
                f"Position für {symbol} bereits offen — "
                "kein zweiter Entry erlaubt (PositionTracker Guard)"
            )

        position_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        position = {
            "id": position_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "entry_time": now,
            "entry_trade_id": entry_trade_id,
            "initial_quantity": quantity,
            "quantity": quantity,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_2_price or take_profit_price,
            "take_profit_1_price": take_profit_1_price or take_profit_price,
            "take_profit_2_price": take_profit_2_price or take_profit_price,
            "tp1_size_pct": tp1_size_pct,
            "tp2_size_pct": tp2_size_pct,
            "breakeven_trigger_pct": breakeven_trigger_pct,
            # NEU: Scaling-Out Felder
            "take_profit_1_pct": take_profit_1_pct,
            "take_profit_2_pct": take_profit_2_pct,
            "tp1_hit": tp1_hit,
            "atr_trailing_enabled": atr_trailing_enabled,
            "max_favorable_price": max_favorable_price or entry_price,
            "min_favorable_price": min_favorable_price or entry_price,
            # LLM Context (Phase C)
            "grss_at_entry": grss_at_entry,
            "layer1_output": layer1_output or {},
            "layer2_output": layer2_output or {},
            "layer3_output": layer3_output or {},
            "regime": regime,
            "order_type": order_type,
            "slippage_bps": slippage_bps,
            "market_conditions": market_conditions or {},
            # Excursion Tracking
            "mae_pct": 0.0,   # Max Adverse Excursion (negativ = schlecht)
            "mfe_pct": 0.0,   # Max Favorable Excursion (positiv = gut)
            "current_pnl_pct": 0.0,
            "realized_pnl_pct": 0.0,
            "realized_pnl_eur": 0.0,
            "breakeven_active": False,
            # Status
            "status": "open",
            "created_at": now,
            **kwargs  # Alle zusätzlichen Felder durchreichen
        }

        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), position)

        logger.info(
            f"Position ERÖFFNET: {side.upper()} {quantity:.4f} {symbol} "
            f"@ {entry_price:,.0f} | SL={stop_loss_price:,.0f} | TP1={position['take_profit_1_price']:,.0f} | TP2={position['take_profit_2_price']:,.0f} "
            f"| GRSS={grss_at_entry:.1f} | ID={position_id[:8]}"
        )

        # Async in DB schreiben (nicht-blockierend)
        await self._persist_open_to_db(position)

        return position_id

    async def update_position(self, symbol: str, updates: dict) -> Optional[dict]:
        """Aktualisiert die offene Position in Redis und spiegelt Kernfelder in der DB wider."""
        pos = await self.get_open_position(symbol)
        if not pos:
            return None

        pos.update(updates)
        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), pos)

        try:
            from sqlalchemy import text
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        UPDATE positions SET
                            quantity = :quantity,
                            stop_loss_price = :stop_loss_price,
                            take_profit_price = :take_profit_price
                        WHERE id = :id
                    """),
                    {
                        "id": pos["id"],
                        "quantity": pos.get("quantity", 0.0),
                        "stop_loss_price": pos.get("stop_loss_price", 0.0),
                        "take_profit_price": pos.get("take_profit_2_price", pos.get("take_profit_price", 0.0)),
                    }
                )
                await session.commit()
        except Exception as e:
            logger.error(f"PositionTracker DB-Update Fehler: {e}")

        return pos

    async def scale_out_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
        fraction: float = 0.50,
        move_stop_to_breakeven: bool = True,
        exit_trade_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Schließt einen Teil der Position und zieht optional den Stop auf Breakeven."""
        pos = await self.get_open_position(symbol)
        if not pos:
            return None

        if pos.get("tp1_hit"):
            return pos

        side = pos["side"]
        entry_price = float(pos["entry_price"])
        initial_quantity = float(pos.get("initial_quantity", pos.get("quantity", 0.0)))
        remaining_quantity = float(pos.get("quantity", initial_quantity))
        qty_to_close = min(remaining_quantity, max(0.0, initial_quantity * fraction))
        if qty_to_close <= 0:
            return pos

        if side == "long":
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - exit_price) / entry_price

        fee_estimate = (qty_to_close * exit_price) * 0.0001
        realized_pnl_eur = pnl_pct * entry_price * qty_to_close - fee_estimate

        pos["quantity"] = round(max(0.0, remaining_quantity - qty_to_close), 8)
        pos["realized_pnl_eur"] = round(float(pos.get("realized_pnl_eur", 0.0)) + realized_pnl_eur, 4)
        pos["realized_pnl_pct"] = round(float(pos.get("realized_pnl_pct", 0.0)) + (pnl_pct * (qty_to_close / initial_quantity if initial_quantity > 0 else 0.0)), 6)
        pos["tp1_hit"] = True
        pos["tp1_exit_price"] = exit_price
        pos["tp1_exit_trade_id"] = exit_trade_id or ""
        pos["breakeven_active"] = bool(move_stop_to_breakeven)
        pos["atr_trailing_enabled"] = bool(move_stop_to_breakeven)
        pos["tp1_hit_reason"] = reason

        if move_stop_to_breakeven:
            if side == "long":
                pos["stop_loss_price"] = round(entry_price * 1.001, 2)
            else:
                pos["stop_loss_price"] = round(entry_price * 0.999, 2)

        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), pos)

        try:
            from sqlalchemy import text
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        UPDATE positions SET
                            quantity = :quantity,
                            stop_loss_price = :stop_loss_price,
                            take_profit_price = :take_profit_price
                        WHERE id = :id
                    """),
                    {
                        "id": pos["id"],
                        "quantity": pos["quantity"],
                        "stop_loss_price": pos["stop_loss_price"],
                        "take_profit_price": pos.get("take_profit_2_price", pos.get("take_profit_price", 0.0)),
                    }
                )
                await session.commit()
        except Exception as e:
            logger.error(f"PositionTracker DB-ScaleOut Fehler: {e}")

        logger.info(
            f"Position SCALE-OUT: {symbol} | reason={reason} | exit={exit_price:,.0f} | "
            f"qty_closed={qty_to_close:.4f} | remaining={pos['quantity']:.4f} | breakeven={move_stop_to_breakeven}"
        )

        return pos

    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str,   # "stop_loss" | "take_profit" | "breakeven_stop" | "trailing_stop" | "tp1_scaling" | "manual_close" | "daily_drawdown" | "regime_change"
        exit_trade_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Schließt die offene Position.
        Berechnet P&L, Haltezeit, MAE/MFE final.
        Gibt das geschlossene Position-Dict zurück (für Post-Trade Debrief).
        """
        pos = await self.get_open_position(symbol)
        if not pos:
            logger.warning(f"close_position: Keine offene Position für {symbol}")
            return None

        now = datetime.now(timezone.utc)
        entry_time = datetime.fromisoformat(pos["entry_time"])
        hold_minutes = int((now - entry_time).total_seconds() / 60)

        side = pos["side"]
        entry_price = pos["entry_price"]
        quantity = float(pos.get("quantity", pos.get("initial_quantity", 0.0)))
        realized_pnl_eur = float(pos.get("realized_pnl_eur", 0.0))

        # P&L Berechnung
        if side == "long":
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - exit_price) / entry_price

        pnl_eur = pnl_pct * entry_price * quantity
        fee_estimate = (quantity * exit_price) * 0.0004   # 0.04% Taker
        total_pnl_eur = realized_pnl_eur + pnl_eur - fee_estimate
        total_quantity = float(pos.get("initial_quantity", quantity))
        total_pnl_pct = (total_pnl_eur / (entry_price * total_quantity)) if entry_price > 0 and total_quantity > 0 else pnl_pct

        # Position finalisieren
        pos.update({
            "status": "closed",
            "exit_price": exit_price,
            "exit_time": now.isoformat(),
            "exit_reason": reason,
            "exit_trade_id": exit_trade_id or "",
            "pnl_pct": round(total_pnl_pct, 6),
            "pnl_eur": round(total_pnl_eur, 4),
            "hold_duration_minutes": hold_minutes,
        })

        # Redis aktualisieren (Status auf closed — Watcher beendet sich)
        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), pos)

        # Kurz danach Key löschen (neue Position kann kommen)
        # Wir lassen den Key 60s stehen damit das Dashboard ihn noch lesen kann
        await self.redis.redis.expire(REDIS_KEY.format(symbol=symbol), 60)

        log_emoji = "✅" if total_pnl_pct > 0 else "❌"
        logger.info(
            f"Position GESCHLOSSEN {log_emoji}: {reason.upper()} | {side.upper()} "
            f"{symbol} @ {exit_price:,.0f} | "
            f"P&L={total_pnl_pct:+.2%} ({total_pnl_eur:.2f} EUR) | "
            f"Haltezeit={hold_minutes}min | MAE={pos['mae_pct']:.2%} | MFE={pos['mfe_pct']:.2%}"
        )

        # Async in DB schreiben
        await self._persist_close_to_db(pos)

        return pos

    async def update_excursions(self, symbol: str, current_price: float) -> None:
        """
        Aktualisiert MAE und MFE laufend.
        Wird vom Monitor-Loop aufgerufen (alle 30s).
        """
        pos = await self.get_open_position(symbol)
        if not pos:
            return

        side = pos["side"]
        entry_price = pos["entry_price"]

        if side == "long":
            excursion_pct = (current_price - entry_price) / entry_price
        else:
            excursion_pct = (entry_price - current_price) / entry_price

        changed = False

        # MAE: schlechteste Bewegung gegen uns
        if excursion_pct < pos.get("mae_pct", 0.0):
            pos["mae_pct"] = round(excursion_pct, 6)
            changed = True

        # MFE: beste Bewegung für uns
        if excursion_pct > pos.get("mfe_pct", 0.0):
            pos["mfe_pct"] = round(excursion_pct, 6)
            changed = True

        pos["current_pnl_pct"] = round(excursion_pct, 6)

        if changed:
            await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), pos)

    # ──────────────────────────────────────────────────────────────────
    # DB Persistence (async, nicht-blockierend für den Trading-Pfad)
    # ──────────────────────────────────────────────────────────────────

    async def _persist_open_to_db(self, position: dict) -> None:
        """Schreibt neu eröffnete Position in die DB."""
        try:
            from sqlalchemy import text
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        INSERT INTO positions (
                            id, symbol, side, entry_price, entry_time,
                            entry_trade_id, quantity, stop_loss_price, take_profit_price,
                            grss_at_entry, layer1_output, layer2_output, layer3_output,
                            regime, status, created_at
                        ) VALUES (
                            :id, :symbol, :side, :entry_price, :entry_time,
                            :entry_trade_id, :quantity, :stop_loss_price, :take_profit_price,
                            :grss_at_entry, :layer1_output::jsonb, :layer2_output::jsonb,
                            :layer3_output::jsonb, :regime, 'open', :created_at
                        )
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": position["id"],
                        "symbol": position["symbol"],
                        "side": position["side"],
                        "entry_price": position["entry_price"],
                        "entry_time": position["entry_time"],
                        "entry_trade_id": position["entry_trade_id"],
                        "quantity": position["quantity"],
                        "stop_loss_price": position["stop_loss_price"],
                        "take_profit_price": position["take_profit_price"],
                        "grss_at_entry": position["grss_at_entry"],
                        "layer1_output": json.dumps(position["layer1_output"] or {}),
                        "layer2_output": json.dumps(position["layer2_output"] or {}),
                        "layer3_output": json.dumps(position["layer3_output"] or {}),
                        "regime": position["regime"],
                        "created_at": position["created_at"],
                    }
                )
                await session.commit()
        except Exception as e:
            logger.error(f"PositionTracker DB-Write (open) Fehler: {e}")

    async def _persist_close_to_db(self, position: dict) -> None:
        """Aktualisiert geschlossene Position in der DB."""
        try:
            from sqlalchemy import text
            async with self.db_session_factory() as session:
                await session.execute(
                    text("""
                        UPDATE positions SET
                            status          = 'closed',
                            exit_price      = :exit_price,
                            exit_time       = :exit_time,
                            exit_reason     = :exit_reason,
                            exit_trade_id   = :exit_trade_id,
                            pnl_eur         = :pnl_eur,
                            pnl_pct         = :pnl_pct,
                            hold_duration_minutes = :hold_minutes,
                            mae_pct         = :mae_pct,
                            mfe_pct         = :mfe_pct
                        WHERE id = :id
                    """),
                    {
                        "id": position["id"],
                        "exit_price": position["exit_price"],
                        "exit_time": position["exit_time"],
                        "exit_reason": position["exit_reason"],
                        "exit_trade_id": position.get("exit_trade_id", ""),
                        "pnl_eur": position["pnl_eur"],
                        "pnl_pct": position["pnl_pct"],
                        "hold_minutes": position["hold_duration_minutes"],
                        "mae_pct": position["mae_pct"],
                        "mfe_pct": position["mfe_pct"],
                    }
                )
                await session.commit()
        except Exception as e:
            logger.error(f"PositionTracker DB-Write (close) Fehler: {e}")
