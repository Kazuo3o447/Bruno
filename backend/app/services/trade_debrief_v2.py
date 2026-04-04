import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from app.core.deepseek_client import get_deepseek_client
from app.core.database import AsyncSessionLocal

class TradeDebriefServiceV2:
    """
    Bruno v2 Post-Trade LLM Debrief Service.
    
    Analysiert abgeschlossene Trades mit LLM-Reasoning und speichert
    die Ergebnisse in der Datenbank für kontinuierliche Verbesserung.
    """
    
    def __init__(self, redis=None, db_session_factory=None):
        self.logger = logging.getLogger("trade_debrief_v2")
        self.redis = redis
        self.db_session_factory = db_session_factory or AsyncSessionLocal
        
        # Deepseek Reasoning Client für Debrief-Analyse
        self.deepseek_client = get_deepseek_client()
        
        # Debrief-Konfiguration
        self.debrief_prompt_template = """
        ANALYSE DIESEN ABGESCHLOSSENEN TRADE:

        **TRADE DATEN:**
        - Symbol: {symbol}
        - Seite: {side} ({side_de})
        - Entry Preis: {entry_price:,.2f} USDT
        - Exit Preis: {exit_price:,.2f} USDT
        - Menge: {quantity:.6f} BTC
        - P&L: {pnl_eur:.2f} EUR ({pnl_pct:+.2%})
        - Haltezeit: {hold_duration_minutes} Minuten
        - Exit Grund: {exit_reason}

        **MARKT KONTEXT BEIM ENTRY:**
        - GRSS Score: {grss_at_entry:.1f}
        - Regime: {regime}
        - Session: {session}
        - VIX: {vix:.1f}
        - OFI Buy Pressure: {ofi_buy_pressure:.2f}

        **TECHNISCHE ANALYSE:**
        - MTF Alignment: {mtf_alignment}
        - Wick Signal: {wick_signal}
        - Orderbook Walls: {orderbook_walls}
        - TA Confidence: {ta_confidence:.2f}

        **LIQUIDITÄTS ANALYSE:**
        - OI Delta: {oi_delta_pct:+.2f}%
        - Sweep Detection: {sweep_detection}
        - Entry Confirmation: {entry_confirmation}
        - Liquidity Score: {liquidity_score:.2f}

        **LLM CASCADE OUTPUTS:**
        - Layer 1: {layer1_output}
        - Layer 2: {layer2_output}
        - Layer 3: {layer3_output}

        **AUFGABE:**
        1. Bewerte die Trade-Entscheidung (1-10)
        2. Identifiziere die Hauptfaktoren für Erfolg/Misserfolg
        3. Schlage spezifische Verbesserungen vor
        4. Bewerte jedes Layer der LLM Cascade
        5. Gib Lern-Empfehlungen für zukünftige Trades

        **FORMAT:**
        ```json
        {{
            "trade_rating": 1-10,
            "success_factors": ["faktor1", "faktor2"],
            "failure_factors": ["faktor1", "faktor2"],
            "layer_evaluations": {{
                "layer1": {{"rating": 1-10, "feedback": "feedback"}},
                "layer2": {{"rating": 1-10, "feedback": "feedback"}},
                "layer3": {{"rating": 1-10, "feedback": "feedback"}}
            }},
            "improvements": ["verbesserung1", "verbesserung2"],
            "learning_recommendations": ["empfehlung1", "empfehlung2"],
            "market_assessment": "beschreibung",
            "risk_assessment": "beschreibung"
        }}
        ```
        """

    async def analyze_trade(self, trade_id: str, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Führt eine vollständige Post-Trade Analyse durch.
        """
        try:
            start_time = time.perf_counter()
            
            # 1. Zusätzliche Kontext-Daten sammeln
            context_data = await self._collect_context_data(position_data)
            
            # 2. LLM Debrief Prompt vorbereiten
            prompt = self._prepare_debrief_prompt(position_data, context_data)
            
            # 3. Deepseek Analyse durchführen
            llm_response = await self.deepseek_client.generate_json(
                prompt=prompt,
                model="deepseek-chat",  # Chat Model für Analyse
                temperature=0.3
            )
            
            # 4. Ergebnisse validieren und speichern
            debrief_result = self._validate_and_enhance_results(
                llm_response, position_data, context_data
            )
            
            # 5. In Datenbank speichern
            await self._save_debrief_results(trade_id, debrief_result)
            
            # 6. Lern-Update durchführen
            await self._update_learning_system(debrief_result)
            
            latency = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                f"Trade Debrief completed for {trade_id} | "
                f"Rating: {debrief_result.get('trade_rating', 'N/A')}/10 | "
                f"Latency: {latency:.1f}ms"
            )
            
            return debrief_result
            
        except Exception as e:
            self.logger.error(f"Trade Debrief Fehler für {trade_id}: {e}", exc_info=True)
            return None

    async def _collect_context_data(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sammelt zusätzliche Kontext-Daten für die Debrief-Analyse.
        """
        context = {}
        
        try:
            # 1. GRSS Daten zum Entry-Zeitpunkt
            entry_time = position_data.get("entry_time")
            if entry_time:
                # Hier könnten historische GRSS-Daten geladen werden
                # Für jetzt verwenden wir aktuelle Daten als Approximation
                grss_data = await self.redis.get_cache("bruno:context:grss") or {}
                context.update({
                    "vix": grss_data.get("VIX", 0),
                    "ofi_buy_pressure": grss_data.get("OFI_Buy_Pressure", 0.5),
                })
            
            # 2. TA Engine Daten
            ta_data = await self.redis.get_cache("bruno:ta:analysis") or {}
            context.update({
                "mtf_alignment": ta_data.get("mtf_alignment", {}).get("aligned", False),
                "wick_signal": ta_data.get("wick_signals", {}).get("has_wick", False),
                "orderbook_walls": len(ta_data.get("orderbook_walls", {}).get("bid_walls", [])),
                "ta_confidence": ta_data.get("confidence", 0.0),
            })
            
            # 3. Liquidity Engine Daten
            liquidity_data = await self.redis.get_cache("bruno:liquidity:analysis") or {}
            context.update({
                "oi_delta_pct": liquidity_data.get("oi_analysis", {}).get("delta_pct", 0),
                "sweep_detection": liquidity_data.get("sweep_detection", {}).get("detected", False),
                "entry_confirmation": liquidity_data.get("entry_confirmation", {}).get("confirmed", False),
                "liquidity_score": liquidity_data.get("entry_confirmation", {}).get("confidence", 0.0),
            })
            
            # 4. Session Information
            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00')) if entry_time else datetime.now(timezone.utc)
            hour = entry_dt.hour
            if 12 <= hour < 16:
                context["session"] = "london_ny_overlap"
            elif 7 <= hour < 9:
                context["session"] = "asia_london_overlap"
            elif hour < 7:
                context["session"] = "asia"
            elif hour < 12:
                context["session"] = "london"
            else:
                context["session"] = "ny"
            
        except Exception as e:
            self.logger.warning(f"Context Data Collection Fehler: {e}")
        
        return context

    def _prepare_debrief_prompt(self, position_data: Dict[str, Any], context_data: Dict[str, Any]) -> str:
        """
        Bereitet den Debrief-Prompt mit allen Trade-Daten vor.
        """
        # Layer Outputs für bessere Lesbarkeit formatieren
        layer1_output = position_data.get("layer1_output", {})
        layer2_output = position_data.get("layer2_output", {})
        layer3_output = position_data.get("layer3_output", {})
        
        prompt = self.debrief_prompt_template.format(
            symbol=position_data.get("symbol", "BTCUSDT"),
            side=position_data.get("side", "unknown"),
            side_de="Long" if position_data.get("side") == "long" else "Short",
            entry_price=position_data.get("entry_price", 0),
            exit_price=position_data.get("exit_price", 0),
            quantity=position_data.get("quantity", 0),
            pnl_eur=position_data.get("pnl_eur", 0),
            pnl_pct=position_data.get("pnl_pct", 0),
            hold_duration_minutes=position_data.get("hold_duration_minutes", 0),
            exit_reason=position_data.get("exit_reason", "unknown"),
            grss_at_entry=position_data.get("grss_at_entry", 0),
            regime=position_data.get("regime", "unknown"),
            session=context_data.get("session", "unknown"),
            vix=context_data.get("vix", 0),
            ofi_buy_pressure=context_data.get("ofi_buy_pressure", 0.5),
            mtf_alignment=context_data.get("mtf_alignment", False),
            wick_signal=context_data.get("wick_signal", False),
            orderbook_walls=context_data.get("orderbook_walls", 0),
            ta_confidence=context_data.get("ta_confidence", 0),
            oi_delta_pct=context_data.get("oi_delta_pct", 0),
            sweep_detection=context_data.get("sweep_detection", False),
            entry_confirmation=context_data.get("entry_confirmation", False),
            liquidity_score=context_data.get("liquidity_score", 0),
            layer1_output=json.dumps(layer1_output) if layer1_output else "{}",
            layer2_output=json.dumps(layer2_output) if layer2_output else "{}",
            layer3_output=json.dumps(layer3_output) if layer3_output else "{}",
        )
        
        return prompt

    def _validate_and_enhance_results(self, llm_response: Dict[str, Any], 
                                   position_data: Dict[str, Any], 
                                   context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validiert und erweitert die LLM-Ergebnisse.
        """
        # Basis-Struktur sicherstellen
        enhanced_result = {
            "trade_id": position_data.get("id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": position_data.get("symbol", "BTCUSDT"),
            "side": position_data.get("side", "unknown"),
            "entry_price": position_data.get("entry_price", 0),
            "exit_price": position_data.get("exit_price", 0),
            "pnl_eur": position_data.get("pnl_eur", 0),
            "pnl_pct": position_data.get("pnl_pct", 0),
            "hold_duration_minutes": position_data.get("hold_duration_minutes", 0),
            "exit_reason": position_data.get("exit_reason", "unknown"),
            "trade_rating": llm_response.get("trade_rating", 5),
            "success_factors": llm_response.get("success_factors", []),
            "failure_factors": llm_response.get("failure_factors", []),
            "layer_evaluations": llm_response.get("layer_evaluations", {}),
            "improvements": llm_response.get("improvements", []),
            "learning_recommendations": llm_response.get("learning_recommendations", []),
            "market_assessment": llm_response.get("market_assessment", ""),
            "risk_assessment": llm_response.get("risk_assessment", ""),
            "context_data": context_data,
            "position_data": position_data,
        }
        
        # Trade Rating basierend auf P&L anpassen
        pnl_pct = position_data.get("pnl_pct", 0)
        if pnl_pct > 0.02:  # >2% Gewinn
            enhanced_result["trade_rating"] = min(enhanced_result["trade_rating"] + 2, 10)
        elif pnl_pct < -0.02:  # >2% Verlust
            enhanced_result["trade_rating"] = max(enhanced_result["trade_rating"] - 2, 1)
        
        # Erfolgsfaktoren aus P&L ableiten
        if pnl_pct > 0:
            if "profitable move" not in enhanced_result["success_factors"]:
                enhanced_result["success_factors"].append("profitable move")
        else:
            if "loss incurred" not in enhanced_result["failure_factors"]:
                enhanced_result["failure_factors"].append("loss incurred")
        
        return enhanced_result

    async def _save_debrief_results(self, trade_id: str, debrief_result: Dict[str, Any]) -> None:
        """
        Speichert die Debrief-Ergebnisse in der Datenbank.
        """
        try:
            async with self.db_session_factory() as session:
                # Check ob Tabelle existiert, sonst erstellen
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS trade_debriefs (
                        id VARCHAR(100) PRIMARY KEY,
                        timestamp TIMESTAMPTZ,
                        symbol VARCHAR(20),
                        side VARCHAR(10),
                        entry_price FLOAT,
                        exit_price FLOAT,
                        pnl_eur FLOAT,
                        pnl_pct FLOAT,
                        hold_duration_minutes INTEGER,
                        exit_reason VARCHAR(50),
                        trade_rating INTEGER,
                        success_factors JSONB,
                        failure_factors JSONB,
                        layer_evaluations JSONB,
                        improvements JSONB,
                        learning_recommendations JSONB,
                        market_assessment TEXT,
                        risk_assessment TEXT,
                        context_data JSONB,
                        position_data JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
                
                # Insert oder Update
                await session.execute(text("""
                    INSERT INTO trade_debriefs (
                        id, timestamp, symbol, side, entry_price, exit_price,
                        pnl_eur, pnl_pct, hold_duration_minutes, exit_reason,
                        trade_rating, success_factors, failure_factors,
                        layer_evaluations, improvements, learning_recommendations,
                        market_assessment, risk_assessment, context_data, position_data
                    ) VALUES (
                        :id, :timestamp, :symbol, :side, :entry_price, :exit_price,
                        :pnl_eur, :pnl_pct, :hold_duration_minutes, :exit_reason,
                        :trade_rating, :success_factors, :failure_factors,
                        :layer_evaluations, :improvements, :learning_recommendations,
                        :market_assessment, :risk_assessment, :context_data, :position_data
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        timestamp = EXCLUDED.timestamp,
                        trade_rating = EXCLUDED.trade_rating,
                        success_factors = EXCLUDED.success_factors,
                        failure_factors = EXCLUDED.failure_factors,
                        layer_evaluations = EXCLUDED.layer_evaluations,
                        improvements = EXCLUDED.improvements,
                        learning_recommendations = EXCLUDED.learning_recommendations,
                        market_assessment = EXCLUDED.market_assessment,
                        risk_assessment = EXCLUDED.risk_assessment,
                        context_data = EXCLUDED.context_data,
                        position_data = EXCLUDED.position_data
                """), {
                    "id": trade_id,
                    "timestamp": debrief_result["timestamp"],
                    "symbol": debrief_result["symbol"],
                    "side": debrief_result["side"],
                    "entry_price": debrief_result["entry_price"],
                    "exit_price": debrief_result["exit_price"],
                    "pnl_eur": debrief_result["pnl_eur"],
                    "pnl_pct": debrief_result["pnl_pct"],
                    "hold_duration_minutes": debrief_result["hold_duration_minutes"],
                    "exit_reason": debrief_result["exit_reason"],
                    "trade_rating": debrief_result["trade_rating"],
                    "success_factors": json.dumps(debrief_result["success_factors"]),
                    "failure_factors": json.dumps(debrief_result["failure_factors"]),
                    "layer_evaluations": json.dumps(debrief_result["layer_evaluations"]),
                    "improvements": json.dumps(debrief_result["improvements"]),
                    "learning_recommendations": json.dumps(debrief_result["learning_recommendations"]),
                    "market_assessment": debrief_result["market_assessment"],
                    "risk_assessment": debrief_result["risk_assessment"],
                    "context_data": json.dumps(debrief_result["context_data"]),
                    "position_data": json.dumps(debrief_result["position_data"]),
                })
                
                await session.commit()
                self.logger.debug(f"Debrief results saved for trade {trade_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to save debrief results: {e}")

    async def _update_learning_system(self, debrief_result: Dict[str, Any]) -> None:
        """
        Aktualisiert das Lernsystem basierend auf den Debrief-Ergebnissen.
        """
        try:
            # 1. Lern-Metriken in Redis speichern
            learning_metrics = {
                "last_debrief": debrief_result["timestamp"],
                "avg_rating": await self._calculate_average_rating(),
                "common_failure_factors": await self._get_common_failure_factors(),
                "improvement_priority": debrief_result.get("improvements", [])[:3],
            }
            
            await self.redis.set_cache("bruno:learning:metrics", learning_metrics, ttl=86400)
            
            # 2. Layer-Performance aktualisieren
            layer_evals = debrief_result.get("layer_evaluations", {})
            for layer, evaluation in layer_evals.items():
                layer_key = f"bruno:learning:layer_{layer}"
                current_metrics = await self.redis.get_cache(layer_key) or {"ratings": [], "count": 0}
                
                current_metrics["ratings"].append(evaluation.get("rating", 5))
                current_metrics["count"] += 1
                
                # Nur letzte 50 Ratings behalten
                if len(current_metrics["ratings"]) > 50:
                    current_metrics["ratings"] = current_metrics["ratings"][-50:]
                
                await self.redis.set_cache(layer_key, current_metrics, ttl=86400)
            
            self.logger.debug("Learning system updated with debrief results")
            
        except Exception as e:
            self.logger.warning(f"Learning system update failed: {e}")

    async def _calculate_average_rating(self) -> float:
        """
        Berechnet die durchschnittliche Trade-Bewertung der letzten 50 Trades.
        """
        try:
            async with self.db_session_factory() as session:
                result = await session.execute(text("""
                    SELECT AVG(trade_rating) as avg_rating
                    FROM trade_debriefs
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    ORDER BY timestamp DESC
                    LIMIT 50
                """))
                avg_rating = result.scalar()
                return avg_rating or 5.0
        except Exception:
            return 5.0

    async def _get_common_failure_factors(self) -> List[str]:
        """
        Ermittelt die häufigsten Misserfolgsfaktoren der letzten 50 Trades.
        """
        try:
            async with self.db_session_factory() as session:
                result = await session.execute(text("""
                    SELECT jsonb_array_elements_text(failure_factors) as factor, COUNT(*) as count
                    FROM trade_debriefs
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    AND jsonb_array_length(failure_factors) > 0
                    GROUP BY factor
                    ORDER BY count DESC
                    LIMIT 10
                """))
                
                factors = [row[0] for row in result.fetchall()]
                return factors
        except Exception:
            return []

    async def get_learning_insights(self) -> Dict[str, Any]:
        """
        Gibt aktuelle Lern-Erkenntnisse zurück.
        """
        try:
            # 1. Basis-Metriken
            metrics = await self.redis.get_cache("bruno:learning:metrics") or {}
            
            # 2. Layer-Performance
            layer_performance = {}
            for layer in ["layer1", "layer2", "layer3"]:
                layer_key = f"bruno:learning:layer_{layer}"
                layer_data = await self.redis.get_cache(layer_key) or {"ratings": [], "count": 0}
                
                if layer_data["ratings"]:
                    layer_performance[layer] = {
                        "avg_rating": sum(layer_data["ratings"]) / len(layer_data["ratings"]),
                        "count": layer_data["count"],
                        "trend": "improving" if len(layer_data["ratings"]) >= 2 and 
                                layer_data["ratings"][-1] > layer_data["ratings"][-2] else "stable"
                    }
                else:
                    layer_performance[layer] = {"avg_rating": 5.0, "count": 0, "trend": "no_data"}
            
            # 3. Kürzeste Debriefs
            async with self.db_session_factory() as session:
                result = await session.execute(text("""
                    SELECT trade_rating, exit_reason, market_assessment
                    FROM trade_debriefs
                    ORDER BY timestamp DESC
                    LIMIT 5
                """))
                recent_debriefs = [
                    {
                        "rating": row[0],
                        "exit_reason": row[1],
                        "assessment": row[2]
                    }
                    for row in result.fetchall()
                ]
            
            return {
                "metrics": metrics,
                "layer_performance": layer_performance,
                "recent_debriefs": recent_debriefs,
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Learning insights retrieval failed: {e}")
            return {}

# Global Service Instance
debrief_service_v2 = TradeDebriefServiceV2()
