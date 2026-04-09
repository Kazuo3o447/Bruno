"""
Scaled Entry Engine — Pyramiding für den Trend-Slot.

PROMPT 6: ATR-basierte Scaled Entries mit Break-Even Trailing.

Statt einer All-In Entry bei einem Preis:
- Tranche 1 (40%): Initial-Signal → sofortige Entry
- Tranche 2 (30%): Preis mindestens 1.0× ATR in Profit → Add
- Tranche 3 (30%): Preis mindestens 2.0× ATR in Profit + Break-Even Trail → Add

Break-Even Protection:
BEVOR Tranche 3 gefeuert wird, MUSS der Stop-Loss für Tranche 1+2 
auf Break-Even (Entry + 0.1% Fee-Puffer) nachgezogen sein.

Redis State: bruno:scaled_entry:BTCUSDT:{slot}
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Callable

class ScaledEntryEngine:
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger("scaled_entry")
    
    async def initiate_entry(self, symbol: str, slot_name: str, direction: str,
                              entry_price: float, total_size_btc: float,
                              slot_config, atr: float = 0.0) -> dict:
        """
        Startet einen Scaled Entry.
        Gibt die ERSTE Tranche zurück die sofort ausgeführt werden soll.
        
        PROMPT 6: ATR-basierte Trigger-Levels statt fixer Prozente.
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
            
            # PROMPT 6: ATR-basierte Steps
            if i == 0:
                trigger_price = entry_price  # Sofort
                trigger_atr_mult = 0.0
            elif i == 1:
                # Tranche 2: 1.0× ATR in Profit
                trigger_atr_mult = 1.0
                if direction == "long":
                    trigger_price = entry_price * (1 + (atr / entry_price) * trigger_atr_mult)
                else:
                    trigger_price = entry_price * (1 - (atr / entry_price) * trigger_atr_mult)
            else:
                # Tranche 3: 2.0× ATR in Profit
                trigger_atr_mult = 2.0
                if direction == "long":
                    trigger_price = entry_price * (1 + (atr / entry_price) * trigger_atr_mult)
                else:
                    trigger_price = entry_price * (1 - (atr / entry_price) * trigger_atr_mult)
            
            tranches.append({
                "number": i + 1,
                "size_btc": size,
                "size_pct": pct,
                "trigger_price": round(trigger_price, 2),
                "trigger_atr_mult": trigger_atr_mult,
                "status": "pending" if i > 0 else "executing",
                "executed_at": None,
                "executed_price": None,
                "breakeven_required": i == 2,  # Tranche 3 braucht Break-Even
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
                                      current_price: float, 
                                      breakeven_check_func: Optional[Callable] = None) -> Optional[dict]:
        """
        Prüft ob die nächste Tranche getriggert werden soll.
        Aufgerufen vom Position Monitor alle 10 Sekunden.
        
        PROMPT 6: ATR-basierte Steps + Break-Even Check für Tranche 3.
        """
        state = await self.redis.get_cache(f"bruno:scaled_entry:{symbol}:{slot_name}")
        if not state or state.get("status") != "active":
            return None
        
        direction = state["direction"]
        entry_price = state["initial_price"]
        
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
                # PROMPT 6: Break-Even Check für Tranche 3
                if tranche.get("breakeven_required", False):
                    if breakeven_check_func is None:
                        self.logger.warning(
                            f"Tranche {tranche['number']} BLOCKED: No breakeven check function provided"
                        )
                        return None
                    
                    # Prüfe ob Break-Even für Tranche 1+2 gesetzt ist
                    be_result = await breakeven_check_func(symbol, slot_name)
                    if not be_result.get("breakeven_set", False):
                        self.logger.warning(
                            f"Tranche {tranche['number']} BLOCKED: Break-even not set for previous tranches. "
                            f"P&L={be_result.get('pnl_pct', 0):.2%}, "
                            f"Current SL={be_result.get('current_sl', 0):,.0f}, "
                            f"Entry={entry_price:,.0f}"
                        )
                        return {
                            "tranche_number": tranche["number"],
                            "blocked": True,
                            "reason": "breakeven_not_set",
                            "breakeven_data": be_result
                        }
                    
                    self.logger.info(
                        f"Tranche {tranche['number']} Break-Even validated: "
                        f"SL set at {be_result.get('current_sl', 0):,.0f}"
                    )
                
                tranche["status"] = "executing"
                tranche["executed_at"] = datetime.now(timezone.utc).isoformat()
                tranche["executed_price"] = current_price
                state["total_executed_btc"] += tranche["size_btc"]
                
                # PROMPT 6: Logging mit ATR-Multiplikator
                atr_mult = tranche.get("trigger_atr_mult", 0)
                
                # Prüfe ob letzte Tranche
                remaining = [t for t in state["tranches"] if t["status"] == "pending"]
                if not remaining:
                    state["status"] = "complete"
                
                await self.redis.set_cache(
                    f"bruno:scaled_entry:{symbol}:{slot_name}", state, ttl=86400
                )
                
                self.logger.info(
                    f"Tranche {tranche['number']} triggered ({atr_mult}× ATR): "
                    f"+{tranche['size_btc']:.4f} BTC @ {current_price:,.0f} "
                    f"(Total: {state['total_executed_btc']:.4f}/{state['total_planned_btc']:.4f} BTC)"
                )
                
                return {
                    "tranche_number": tranche["number"],
                    "tranche_size_btc": tranche["size_btc"],
                    "is_final": state["status"] == "complete",
                    "total_executed_btc": state["total_executed_btc"],
                    "total_planned_btc": state["total_planned_btc"],
                    "atr_mult": atr_mult,
                    "trigger_price": trigger,
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
