"""
Scaled Entry Engine — Pyramiding für den Trend-Slot.

Statt einer All-In Entry bei einem Preis:
- Tranche 1 (40%): Initial-Signal → sofortige Entry
- Tranche 2 (30%): Preis bestätigt Richtung (+0.5%) → Add
- Tranche 3 (30%): Breakout über Key-Level → Add

Jede Tranche hat ihren eigenen Breakeven-Stop.
Wenn der Trade sofort gegen dich läuft, verlierst du nur 40% statt 100%.

Redis State: bruno:scaled_entry:BTCUSDT:{slot}
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

class ScaledEntryEngine:
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger("scaled_entry")
    
    async def initiate_entry(self, symbol: str, slot_name: str, direction: str,
                              entry_price: float, total_size_btc: float,
                              slot_config) -> dict:
        """
        Startet einen Scaled Entry.
        Gibt die ERSTE Tranche zurück die sofort ausgeführt werden soll.
        """
        if not slot_config.scaled_entry_enabled:
            # Kein Scaling → Einmal-Entry mit voller Größe
            return {
                "tranche_number": 1,
                "tranche_size_btc": total_size_btc,
                "is_final": True,
                "total_planned_btc": total_size_btc,
            }
        
        tranches = []
        for i, pct in enumerate(slot_config.tranche_sizes):
            size = round(total_size_btc * pct, 5)
            if i == 0:
                trigger_price = entry_price  # Sofort
            else:
                # Bestätigungspreis: Entry + (i × confirmation_pct)
                if direction == "long":
                    trigger_price = entry_price * (1 + slot_config.tranche_confirmation_pct * i)
                else:
                    trigger_price = entry_price * (1 - slot_config.tranche_confirmation_pct * i)
            
            tranches.append({
                "number": i + 1,
                "size_btc": size,
                "size_pct": pct,
                "trigger_price": round(trigger_price, 2),
                "status": "pending" if i > 0 else "executing",
                "executed_at": None,
                "executed_price": None,
            })
        
        state = {
            "symbol": symbol,
            "slot": slot_name,
            "direction": direction,
            "initial_price": entry_price,
            "total_planned_btc": total_size_btc,
            "total_executed_btc": 0.0,
            "tranches": tranches,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        
        await self.redis.set_cache(
            f"bruno:scaled_entry:{symbol}:{slot_name}", state, ttl=86400
        )
        
        return {
            "tranche_number": 1,
            "tranche_size_btc": tranches[0]["size_btc"],
            "is_final": len(tranches) == 1,
            "total_planned_btc": total_size_btc,
            "next_trigger_price": tranches[1]["trigger_price"] if len(tranches) > 1 else None,
        }
    
    async def check_pending_tranches(self, symbol: str, slot_name: str,
                                      current_price: float) -> Optional[dict]:
        """
        Prüft ob die nächste Tranche getriggert werden soll.
        Aufgerufen vom Position Monitor alle 10 Sekunden.
        """
        state = await self.redis.get_cache(f"bruno:scaled_entry:{symbol}:{slot_name}")
        if not state or state.get("status") != "active":
            return None
        
        direction = state["direction"]
        
        for tranche in state["tranches"]:
            if tranche["status"] != "pending":
                continue
            
            trigger = tranche["trigger_price"]
            triggered = False
            
            if direction == "long" and current_price >= trigger:
                triggered = True
            elif direction == "short" and current_price <= trigger:
                triggered = True
            
            if triggered:
                tranche["status"] = "executing"
                tranche["executed_at"] = datetime.now(timezone.utc).isoformat()
                tranche["executed_price"] = current_price
                state["total_executed_btc"] += tranche["size_btc"]
                
                # Prüfe ob letzte Tranche
                remaining = [t for t in state["tranches"] if t["status"] == "pending"]
                if not remaining:
                    state["status"] = "complete"
                
                await self.redis.set_cache(
                    f"bruno:scaled_entry:{symbol}:{slot_name}", state, ttl=86400
                )
                
                self.logger.info(
                    f"Tranche {tranche['number']} triggered: "
                    f"+{tranche['size_btc']:.4f} BTC @ {current_price:,.0f} "
                    f"(Total: {state['total_executed_btc']:.4f}/{state['total_planned_btc']:.4f} BTC)"
                )
                
                return {
                    "tranche_number": tranche["number"],
                    "tranche_size_btc": tranche["size_btc"],
                    "is_final": state["status"] == "complete",
                    "total_executed_btc": state["total_executed_btc"],
                    "total_planned_btc": state["total_planned_btc"],
                }
        
        return None
    
    async def cancel_remaining(self, symbol: str, slot_name: str, reason: str):
        """Cancelt verbleibende Tranchen (z.B. bei SL-Hit)."""
        state = await self.redis.get_cache(f"bruno:scaled_entry:{symbol}:{slot_name}")
        if not state:
            return
        
        for tranche in state["tranches"]:
            if tranche["status"] == "pending":
                tranche["status"] = f"cancelled: {reason}"
        
        state["status"] = "cancelled"
        await self.redis.set_cache(
            f"bruno:scaled_entry:{symbol}:{slot_name}", state, ttl=86400
        )
        self.logger.info(f"Scaled Entry cancelled: {slot_name} — {reason}")
