"""
Post-Trade Debrief Service (Phase F)

Analysiert abgeschlossene Trades mit Ollama LLM (deepseek-r1:14b).
Speichert Ergebnisse in trade_debriefs Tabelle.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.config import Settings


class DebriefService:
    """
    Post-Trade Debrief Service
    
    - Nutzt Ollama LLM für Trade-Analyse
    - Speichert strukturierte Debriefs
    - Fehlertolerant bei LLM-Ausfällen
    """
    
    def __init__(self):
        self.config = Settings()
        self.ollama_host = self.config.OLLAMA_HOST
        self.model = "deepseek-r1:14b"
        
    async def analyze_trade(self, trade_id: str, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Führt Post-Trade Debrief durch
        
        Args:
            trade_id: UUID der Position
            position_data: Vollständige Positionsdaten
            
        Returns:
            Dict mit Debrief-Ergebnissen oder None bei Fehler
        """
        try:
            # LLM Prompt erstellen
            prompt = self._create_debrief_prompt(position_data)
            
            # LLM Aufruf
            llm_response = await self._call_ollama(prompt)
            if not llm_response:
                return None
                
            # Response parsen
            debrief = self._parse_llm_response(llm_response)
            
            # In DB speichern
            await self._save_debrief(trade_id, debrief, llm_response)
            
            return debrief
            
        except Exception as e:
            print(f"Debrief Service Error: {e}")
            return None
    
    def _create_debrief_prompt(self, position: Dict[str, Any]) -> str:
        """
        Erstellt strukturierten Prompt für LLM Analyse
        """
        prompt = f"""
Du bist ein erfahrener Krypto-Trading-Analyst. Analysiere diesen abgeschlossenen Trade objektiv.

TRADE-DATEN:
===========
Symbol: {position.get('symbol', 'Unknown')}
Seite: {position.get('side', 'Unknown')}
Entry Price: ${position.get('entry_price', 0):.2f}
Exit Price: ${position.get('exit_price', 0):.2f}
Menge: {position.get('quantity', 0)}
PnL: ${position.get('pnl_eur', 0):.2f} ({position.get('pnl_pct', 0):.1f}%)
Haltezeit: {position.get('hold_duration_minutes', 0)} Min
Entry Time: {position.get('entry_time', 'Unknown')}
Exit Time: {position.get('exit_time', 'Unknown')}
Exit Reason: {position.get('exit_reason', 'Unknown')}

KONTEXT ZUM ENTRY:
==================
GRSS bei Entry: {position.get('grss_at_entry', 0):.1f}
Regime: {position.get('regime', 'Unknown')}
Layer 1 Output: {json.dumps(position.get('layer1_output', {}), indent=2)}
Layer 2 Output: {json.dumps(position.get('layer2_output', {}), indent=2)}
Layer 3 Output: {json.dumps(position.get('layer3_output', {}), indent=2)}

ANALYSE-AUFGABE:
================
Analysiere diesen Trade und gib strukturiertes Feedback in JSON-Format:

{{
  "decision_quality": "EXCELLENT|GOOD|ACCEPTABLE|POOR|TERRIBLE",
  "key_signal": "Welches Signal war entscheidend für den Entry? (1 Satz)",
  "improvement": "Was hätte man besser machen können? (1-2 Sätze)",
  "pattern": "Erkanntes Muster oder Fehler (1 Satz)",
  "regime_assessment": "Passte der Entry zum aktuellen Regime? (1 Satz)"
}}

Fokus auf:
1. Entscheidungsqualität basierend auf vorliegenden Daten
2. Risikomanagement (Stop Loss, Take Profit)
3. Timing und Markteintritt
4. Lernpunkte für zukünftige Trades

Sei präzise und objektiv. Keine Ausreden, keine Emotionen.
"""
        return prompt
    
    async def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Ruft Ollama LLM auf
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Konsistentere Antworten
                            "top_p": 0.9,
                            "max_tokens": 500
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")
                else:
                    print(f"Ollama Error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Ollama Exception: {e}")
            return None
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parst LLM Response und extrahiert JSON
        """
        try:
            # JSON aus Response extrahieren
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                # Fallback: Manuelle Erstellung
                return {
                    "decision_quality": "ACCEPTABLE",
                    "key_signal": "LLM Response konnte nicht geparst werden",
                    "improvement": "Prompt-Optimierung erforderlich",
                    "pattern": "Parsing-Fehler",
                    "regime_assessment": "Unklar"
                }
            
            # JSON parsen
            parsed = json.loads(json_str)
            
            # Validierung und Defaults
            result = {
                "decision_quality": parsed.get("decision_quality", "ACCEPTABLE"),
                "key_signal": parsed.get("key_signal", "Kein Signal erkannt"),
                "improvement": parsed.get("improvement", "Keine Verbesserung identifiziert"),
                "pattern": parsed.get("pattern", "Kein Muster erkannt"),
                "regime_assessment": parsed.get("regime_assessment", "Regime unklar")
            }
            
            return result
            
        except Exception as e:
            print(f"JSON Parsing Error: {e}")
            return {
                "decision_quality": "ACCEPTABLE",
                "key_signal": f"Parsing Error: {str(e)}",
                "improvement": "JSON-Format verbessern",
                "pattern": "Parse-Fehler",
                "regime_assessment": "Unklar"
            }
    
    async def _save_debrief(self, trade_id: str, debrief: Dict[str, Any], raw_response: str) -> None:
        """
        Speichert Debrief in Datenbank
        """
        try:
            async with AsyncSessionLocal() as session:
                # Debrief Record erstellen
                debrief_record = {
                    "id": str(uuid.uuid4()),
                    "trade_id": trade_id,
                    "timestamp": datetime.now(timezone.utc),
                    "decision_quality": debrief["decision_quality"],
                    "key_signal": debrief["key_signal"],
                    "improvement": debrief["improvement"],
                    "pattern": debrief["pattern"],
                    "regime_assessment": debrief["regime_assessment"],
                    "raw_llm_response": raw_response
                }
                
                # SQL Insert
                await session.execute(
                    """
                    INSERT INTO trade_debriefs (
                        id, trade_id, timestamp, decision_quality, 
                        key_signal, improvement, pattern, regime_assessment, 
                        raw_llm_response
                    ) VALUES (
                        :id, :trade_id, :timestamp, :decision_quality,
                        :key_signal, :improvement, :pattern, :regime_assessment,
                        :raw_llm_response
                    )
                    """,
                    debrief_record
                )
                
                await session.commit()
                print(f"Debrief saved for trade {trade_id}")
                
        except Exception as e:
            print(f"Database Error saving debrief: {e}")
    
    async def get_debrief(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Holt vorhandenen Debrief für Trade
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    """
                    SELECT * FROM trade_debriefs 
                    WHERE trade_id = :trade_id 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                    """,
                    {"trade_id": trade_id}
                )
                
                row = result.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "trade_id": row[1],
                        "timestamp": row[2],
                        "decision_quality": row[3],
                        "key_signal": row[4],
                        "improvement": row[5],
                        "pattern": row[6],
                        "regime_assessment": row[7],
                        "raw_llm_response": row[8]
                    }
                return None
                
        except Exception as e:
            print(f"Error getting debrief: {e}")
            return None


# Singleton Instance
debrief_service = DebriefService()
