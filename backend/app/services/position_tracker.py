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

    async def open_position(
        self,
        symbol: str,
        side: str,                   # "long" | "short"
        entry_price: float,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float,
        entry_trade_id: str,
        # Phase-C Felder — optional, werden nach LLM-Cascade befüllt
        grss_at_entry: float = 0.0,
        layer1_output: Optional[dict] = None,
        layer2_output: Optional[dict] = None,
        layer3_output: Optional[dict] = None,
        regime: str = "unknown",
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
            "quantity": quantity,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            # LLM Context (Phase C)
            "grss_at_entry": grss_at_entry,
            "layer1_output": layer1_output or {},
            "layer2_output": layer2_output or {},
            "layer3_output": layer3_output or {},
            "regime": regime,
            # Excursion Tracking
            "mae_pct": 0.0,   # Max Adverse Excursion (negativ = schlecht)
            "mfe_pct": 0.0,   # Max Favorable Excursion (positiv = gut)
            "current_pnl_pct": 0.0,
            # Status
            "status": "open",
            "created_at": now,
        }

        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), position)

        logger.info(
            f"Position ERÖFFNET: {side.upper()} {quantity:.4f} {symbol} "
            f"@ {entry_price:,.0f} | SL={stop_loss_price:,.0f} | TP={take_profit_price:,.0f} "
            f"| GRSS={grss_at_entry:.1f} | ID={position_id[:8]}"
        )

        # Async in DB schreiben (nicht-blockierend)
        await self._persist_open_to_db(position)

        return position_id

    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str,   # "stop_loss" | "take_profit" | "signal" | "manual" | "emergency"
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
        quantity = pos["quantity"]

        # P&L Berechnung
        if side == "long":
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - exit_price) / entry_price

        pnl_eur = pnl_pct * entry_price * quantity
        fee_estimate = (quantity * exit_price) * 0.0004   # 0.04% Taker

        # Position finalisieren
        pos.update({
            "status": "closed",
            "exit_price": exit_price,
            "exit_time": now.isoformat(),
            "exit_reason": reason,
            "exit_trade_id": exit_trade_id or "",
            "pnl_pct": round(pnl_pct, 6),
            "pnl_eur": round(pnl_eur - fee_estimate, 4),
            "hold_duration_minutes": hold_minutes,
        })

        # Redis aktualisieren (Status auf closed — Watcher beendet sich)
        await self.redis.set_cache(REDIS_KEY.format(symbol=symbol), pos)

        # Kurz danach Key löschen (neue Position kann kommen)
        # Wir lassen den Key 60s stehen damit das Dashboard ihn noch lesen kann
        await self.redis.redis.expire(REDIS_KEY.format(symbol=symbol), 60)

        log_emoji = "✅" if pnl_pct > 0 else "❌"
        logger.info(
            f"Position GESCHLOSSEN {log_emoji}: {reason.upper()} | {side.upper()} "
            f"{symbol} @ {exit_price:,.0f} | "
            f"P&L={pnl_pct:+.2%} ({pnl_eur:.2f} EUR) | "
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
                        "layer1_output": str(position["layer1_output"]).replace("'", '"'),
                        "layer2_output": str(position["layer2_output"]).replace("'", '"'),
                        "layer3_output": str(position["layer3_output"]).replace("'", '"'),
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
            import json as _json
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
