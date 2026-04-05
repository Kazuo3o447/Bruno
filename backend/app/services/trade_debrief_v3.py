import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from app.core.deepseek_client import get_deepseek_client
from app.core.database import AsyncSessionLocal

class TradeDebriefV3:
    """Post-Trade-Analyse via DeepSeek Reasoner."""
    
    def __init__(self, redis_client, db_session_factory=None):
        self.logger = logging.getLogger("trade_debrief_v3")
        self.redis = redis_client
        self.db = db_session_factory or AsyncSessionLocal
        self.llm = get_deepseek_client()
    
    async def debrief_trade(self, trade_data: dict, trade_mode: str = "production") -> Optional[dict]:
        """
        Analysiert einen abgeschlossenen Trade und speichert Learnings.
        
        Input: trade_data mit entry_price, exit_price, side, pnl_pct,
               composite_score, ta_score, liq_score, flow_score, macro_score,
               regime, signals_active, hold_duration_minutes
        """
        try:
            prompt = f"""Analysiere diesen BTC Perpetual Futures Trade:

Entry: {trade_data.get('entry_price')} ({trade_data.get('side')})
Exit: {trade_data.get('exit_price')}
P&L: {trade_data.get('pnl_pct', 0) * 100:.2f}%
Hold Time: {trade_data.get('hold_duration_minutes')} Minuten
Regime: {trade_data.get('regime')}

Scores bei Entry:
- Composite: {trade_data.get('composite_score')}
- TA: {trade_data.get('ta_score')}
- Liquidity: {trade_data.get('liq_score')}
- Flow: {trade_data.get('flow_score')}
- Macro: {trade_data.get('macro_score')}

Aktive Signale: {', '.join(trade_data.get('signals_active', []))}

Antworte NUR als JSON:
{{
  "was_correct": bool,
  "primary_error": "string oder null",
  "signal_accuracy": {{
    "ta_accurate": bool,
    "flow_accurate": bool,
    "liq_accurate": bool,
    "macro_accurate": bool
  }},
  "recommendation": "string (1 Satz, konkret)"
}}"""

            # DeepSeek Reasoner nutzen für tiefere Analyse
            response = await self.llm.generate_json(prompt, model="deepseek-chat") # Use deepseek-chat as proxy for reasoner if needed or reasoning model if available
            
            if not response or "error" in response:
                self.logger.warning(f"Debrief LLM Fehler: {response.get('message') if response else 'No response'}")
                return None

            # Speichern in DB
            await self._save_to_db(trade_data.get("id"), response, trade_mode)
            
            # In Redis History pushen
            history_entry = {
                "trade_id": trade_data.get("id"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pnl_pct": trade_data.get("pnl_pct"),
                "rating": response.get("was_correct"),
                "recommendation": response.get("recommendation")
            }
            await self.redis.redis.lpush("bruno:debriefs:history", json.dumps(history_entry))
            await self.redis.redis.ltrim("bruno:debriefs:history", 0, 99)
            
            return response

        except Exception as e:
            self.logger.error(f"Trade Debrief Fehler: {e}", exc_info=True)
            return None

    async def _save_to_db(self, trade_id: str, debrief: dict, trade_mode: str):
        try:
            async with self.db() as session:
                await session.execute(
                    text("""
                        INSERT INTO trade_debriefs (
                            id, trade_id, timestamp, decision_quality, 
                            key_signal, improvement, pattern, regime_assessment,
                            trade_mode, raw_llm_response
                        ) VALUES (
                            :id, :trade_id, :timestamp, :decision_quality,
                            :key_signal, :improvement, :pattern, :regime_assessment,
                            :trade_mode, :raw_llm_response
                        ) ON CONFLICT (id) DO UPDATE SET
                            raw_llm_response = EXCLUDED.raw_llm_response
                    """),
                    {
                        "id": f"dbf_{trade_id}",
                        "trade_id": trade_id,
                        "timestamp": datetime.now(timezone.utc),
                        "decision_quality": "CORRECT" if debrief.get("was_correct") else "INCORRECT",
                        "key_signal": debrief.get("recommendation", "N/A"),
                        "improvement": debrief.get("primary_error", "N/A"),
                        "pattern": json.dumps(debrief.get("signal_accuracy", {})),
                        "regime_assessment": trade_data.get("regime", "unknown"),
                        "trade_mode": trade_mode,
                        "raw_llm_response": json.dumps(debrief)
                    }
                )
                await session.commit()
        except Exception as e:
            self.logger.error(f"Debrief DB Save Fehler: {e}")
