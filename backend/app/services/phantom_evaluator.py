"""
Phantom Trade Evaluator (BRUNO-FIX-09).
Wertet pending Phantom-Trades aus und schreibt sie in trade_debriefs.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text


class PhantomEvaluator:
    """Evaluiert fällige Phantom-Trades und persistiert Outcomes."""
    
    def __init__(self, redis_client, db_session_factory, exchange_client):
        self.redis = redis_client
        self.db = db_session_factory
        self.exm = exchange_client
        self.logger = logging.getLogger("phantom_evaluator")
    
    async def evaluate_pending(self) -> int:
        """
        Hauptlauf: Durchläuft alle pending Phantoms, wertet fällige aus.
        Returns: Anzahl ausgewerteter Phantoms.
        """
        try:
            raw_list = await self.redis.redis.lrange("bruno:phantom_trades:pending", 0, -1)
            if not raw_list:
                return 0
            
            now = datetime.now(timezone.utc)
            evaluated_count = 0
            still_pending = []
            
            for raw in raw_list:
                try:
                    phantom = json.loads(raw)
                    evaluate_at = datetime.fromisoformat(phantom["evaluate_at"])
                    
                    if evaluate_at > now:
                        # Noch nicht fällig
                        still_pending.append(raw)
                        continue
                    
                    # Fällig — Outcome berechnen
                    outcome = await self._compute_outcome(phantom)
                    if outcome is None:
                        # Konnte Preis nicht laden — zurück in pending
                        still_pending.append(raw)
                        continue
                    
                    await self._persist_phantom_debrief(phantom, outcome)
                    evaluated_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Phantom eval error: {e}")
                    still_pending.append(raw)  # Defensiv: nicht verwerfen
            
            # Pending-Liste neu schreiben (atomar)
            pipe = self.redis.redis.pipeline()
            pipe.delete("bruno:phantom_trades:pending")
            if still_pending:
                pipe.rpush("bruno:phantom_trades:pending", *still_pending)
            await pipe.execute()
            
            if evaluated_count > 0:
                self.logger.info(
                    f"Phantom Evaluator: {evaluated_count} ausgewertet, "
                    f"{len(still_pending)} noch pending"
                )
            
            return evaluated_count
            
        except Exception as e:
            self.logger.error(f"PhantomEvaluator Fehler: {e}", exc_info=True)
            return 0
    
    async def _compute_outcome(self, phantom: dict) -> Optional[dict]:
        """Berechnet Phantom-Outcome anhand aktuellem Preis."""
        try:
            ob = await self.exm.fetch_order_book_redundant("BTCUSDT", limit=5)
            if not ob or not ob.get("bids"):
                return None
            
            current_price = float(ob["bids"][0][0])
            entry_price = float(phantom["entry_price"])
            direction = phantom["direction"]
            
            if direction == "long":
                pnl_pct = (current_price - entry_price) / entry_price
            elif direction == "short":
                pnl_pct = (entry_price - current_price) / entry_price
            else:
                return None
            
            # Hypothetische Outcome-Klassifikation
            if pnl_pct > 0.015:
                outcome_class = "win"
            elif pnl_pct < -0.010:
                outcome_class = "loss"
            else:
                outcome_class = "neutral"
            
            return {
                "exit_price": current_price,
                "pnl_pct": round(pnl_pct, 5),
                "outcome_class": outcome_class,
            }
        except Exception as e:
            self.logger.warning(f"Outcome compute error: {e}")
            return None
    
    async def _persist_phantom_debrief(self, phantom: dict, outcome: dict) -> None:
        """Schreibt Phantom-Outcome nach trade_debriefs oder Redis Fallback."""
        try:
            # Versuch DB-Insert
            async with self.db() as session:
                await session.execute(
                    text("""
                        INSERT INTO trade_debriefs (
                            phantom_id, trade_mode, ts, evaluated_at,
                            entry_price, exit_price, direction, pnl_pct,
                            outcome_class, composite_score, regime,
                            ta_score, liq_score, flow_score, macro_score,
                            mtf_aligned, sweep_confirmed, signals_active
                        ) VALUES (
                            :pid, 'phantom', :ts, :eval_at,
                            :ep, :xp, :dir, :pnl,
                            :oc, :cs, :reg,
                            :ta, :liq, :flow, :macro,
                            :mtf, :sweep, :signals
                        )
                        ON CONFLICT (phantom_id) DO NOTHING
                    """),
                    {
                        "pid": phantom["phantom_id"],
                        "ts": phantom["ts"],
                        "eval_at": datetime.now(timezone.utc).isoformat(),
                        "ep": phantom["entry_price"],
                        "xp": outcome["exit_price"],
                        "dir": phantom["direction"],
                        "pnl": outcome["pnl_pct"],
                        "oc": outcome["outcome_class"],
                        "cs": phantom["composite_score"],
                        "reg": phantom["regime"],
                        "ta": phantom["ta_score"],
                        "liq": phantom["liq_score"],
                        "flow": phantom["flow_score"],
                        "macro": phantom["macro_score"],
                        "mtf": phantom["mtf_aligned"],
                        "sweep": phantom["sweep_confirmed"],
                        "signals": json.dumps(phantom.get("signals_active", [])),
                    }
                )
                await session.commit()
        except Exception as e:
            # Fallback: Redis
            self.logger.warning(f"DB insert failed, using Redis fallback: {e}")
            try:
                evaluated_entry = {
                    "phantom_id": phantom["phantom_id"],
                    "ts": phantom["ts"],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "entry_price": phantom["entry_price"],
                    "exit_price": outcome["exit_price"],
                    "direction": phantom["direction"],
                    "pnl_pct": outcome["pnl_pct"],
                    "outcome_class": outcome["outcome_class"],
                    "composite_score": phantom["composite_score"],
                    "regime": phantom["regime"],
                }
                await self.redis.redis.lpush(
                    "bruno:phantom_trades:evaluated",
                    json.dumps(evaluated_entry)
                )
                await self.redis.redis.ltrim("bruno:phantom_trades:evaluated", 0, 999)
            except Exception as e2:
                self.logger.error(f"Redis fallback also failed: {e2}")
