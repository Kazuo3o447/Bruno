import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.contracts import RiskDecision, SignalDirection, QuantSignalV2, SentimentSignalV2

class RiskAgentV2(StreamingAgent):
    """
    Phase 3 Architektur: The Consensus & Risk Master.
    Baut das MarketContext JSON fürs DeepSeek-R1 LLM und wickelt das Money Management ab.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("risk", deps)
        self.latest_quant: Optional[QuantSignalV2] = None
        self.latest_sentiment: Optional[SentimentSignalV2] = None
        
        self.max_daily_loss_pct = 5.0
        self.portfolio_value_usd = 1000.0  # Test Capital
        self.symbol = "BTCUSDT"
        
    async def setup(self) -> None:
        self.logger.info("RiskAgent setup abgeschlossen.")
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message="Risk Agent initialisiert. Konsens-Modus aktiv."
        )
        
    async def _fetch_context(self, symbol: str) -> Dict[str, Any]:
        """Sammelt alle fehlenden Puzzleteile für den Market Context (Liquidations, Funding Rates)."""
        # 1. Macro F&G
        fg_data = await self.deps.redis.get_cache("macro:fear_and_greed")
        fg_index = fg_data.get("value", 50) if fg_data else 50
        
        # 2. Funding Rate
        fund_data = await self.deps.redis.get_cache(f"market:funding:{symbol}")
        funding_rate = fund_data.get("rate", 0.0) if fund_data else 0.0
        
        # 3. Orderbook (wurde z.T. vom Quant genutzt, aber hier fürs LLM)
        ob_data = await self.deps.redis.get_cache(f"market:orderbook:{symbol}")
        ob_imbalance = ob_data.get("imbalance_ratio", 1.0) if ob_data else 1.0
        
        # Optional: Liquidations der letzten Stunde aggregieren (für Phase 3 Mock: Dummy aus Redis stream oder fixed)
        liquidations = "Keine Anomalien."
        
        return {
            "macro_context": {
                "fear_and_greed_index": fg_index
            },
            "derivatives_pressure": {
                "funding_rate_pct": round(funding_rate * 100, 4),
                "orderbook_imbalance": round(ob_imbalance, 2),
                "liquidations_info": liquidations
            }
        }
        
    async def _evaluate_risk(self) -> None:
        if not self.latest_quant or not self.latest_sentiment:
            return
            
        quant = self.latest_quant
        sentiment = self.latest_sentiment
        symbol = quant.symbol
        
        # Kontext anreichern
        extra_ctx = await self._fetch_context(symbol)
        
        market_context = {
            "asset": symbol,
            "macro_context": extra_ctx["macro_context"],
            "price_action": {
                "current_price": quant.indicators.get("price", 0.0),
                "trend": quant.market_state.get("trend", "neutral"),
                "rsi_1h": round(quant.indicators.get("rsi_1h", 50.0), 2)
            },
            "derivatives_pressure": extra_ctx["derivatives_pressure"],
            "news_sentiment": {
                "score": round(sentiment.score, 2),
                "insight": sentiment.reasoning
            },
            "quant_recommendation": {
                "direction": quant.direction,
                "confidence": round(quant.confidence, 2),
                "reasoning": quant.reasoning
            }
        }
        
        # LLM Prompt (Reasoning Model - z.B. DeepSeek-R1)
        self.logger.info("Frage Reasoning Model (Risk Analysis)...")
        prompt = f"""
Du bist ein profitabler, kaltschnäuziger Quant-Trader. 
Gegeben ist folgender reeller Market Context für {symbol}:
{json.dumps(market_context, indent=2)}

Analysiere diesen Kontext strikt und professionell. Ignoriere Emotionen.
Ist ein Trade gerechtfertigt? 
(Tipp: Ist der Quant auf SELL, aber Sentiment extrem bullish und Imbalance stark Bids = VETO/HOLD.
Sind Quant, Sentiment und Derivate aligniert = APPROVED).

Antworte exakt als valides JSON mit diesem Schema (KEIN ANDERER TEXT, NUR JSON):
{{
  "action": "BUY" oder "SELL" oder "HOLD",
  "approved": true/false (true = order ausführen, false = veto),
  "reasoning": "Warum? Max 3 Sätze.",
  "risk_reward_ratio": Zahl (mindestens 1.5, bei HOLD 0.0)
}}
"""
        # Health Check für Reasoning Model
        ollama_ok = await self.deps.ollama.health_check()
        if not ollama_ok:
            self.state.health = "degraded"
            await self.log_manager.warning(
                category="AGENT",
                source=self.agent_id,
                message="DeepSeek-R1 Reasoning nicht verfügbar. Nutze Risiko-Heuristiken."
            )
        else:
            self.state.health = "healthy"

        response_text = await self.deps.ollama.generate_response(
            prompt, 
            use_reasoning=True, 
            temperature=0.1 # Very deterministic
        )
        
        # Fallback if Ollama fails (e.g. Model not found 404)
        if response_text.startswith("Error:"):
            self.logger.warning(f"Ollama Reasoning fehlgeschlagen: {response_text}. Nutze regelbasierten Fallback.")
            # Einfacher Fallback: Wenn Quant und Sentiment gleichgerichtet sind, approven
            if quant.direction == sentiment.direction and quant.direction != SignalDirection.HOLD:
                llm_response = {
                    "action": quant.direction.value,
                    "approved": True,
                    "reasoning": f"Fallback: Quant({quant.direction.value}) und Sentiment({sentiment.direction.value}) aligniert.",
                    "risk_reward_ratio": 2.0
                }
            else:
                llm_response = {
                    "action": "HOLD",
                    "approved": False,
                    "reasoning": "Fallback: Keine eindeutige Konfluenz ohne LLM Analyse.",
                    "risk_reward_ratio": 0.0
                }
        else:
            # Parse JSON from actual LLM response
            try:
                # Versuch DeepSeek's <think> block zu ignorieren: Wir suchen nach { ... }
                json_str = response_text
                match = re.search(r'(\{.*\})', response_text.replace('\n', ' '), re.MULTILINE | re.DOTALL)
                if match:
                    json_str = match.group(1)
                
                llm_response = json.loads(json_str)
            except Exception as e:
                self.logger.error(f"Konnte LLM JSON nicht verarbeiten: {e}\nResponse: {response_text[:200]}")
                llm_response = {"action": "HOLD", "approved": False, "reasoning": "Parsing Error", "risk_reward_ratio": 0.0}
                
        action_str = llm_response.get("action", "HOLD").upper()
        action = SignalDirection(action_str)
        approved = bool(llm_response.get("approved", False))
        reasoning = llm_response.get("reasoning", "LLM Reasoning missing.")
        rr_ratio = float(llm_response.get("risk_reward_ratio", 0.0))

        if action == SignalDirection.HOLD:
            approved = False

        # Math SL/TP
        price = quant.indicators.get("price", 0.0)
        atr = quant.indicators.get("atr_1h", price * 0.01) # fallback 1%
        if atr <= 0:
            atr = price * 0.01
            
        if action == SignalDirection.BUY:
            sl = price - (atr * 1.5)
            tp = price + (atr * 1.5 * max(rr_ratio, 1.5))
        else:
            sl = price + (atr * 1.5)
            tp = price - (atr * 1.5 * max(rr_ratio, 1.5))
            
        # Fixed fractional 2% of PTF
        risk_amt = self.portfolio_value_usd * 0.02
        # Position Size in Base (BTC) = Risk_USD / Risk_Per_Unit
        distance_to_sl = abs(price - sl)
        pos_size_btc = (risk_amt / distance_to_sl) if distance_to_sl > 0 else 0.0
        pos_size_usd = pos_size_btc * price
        
        # Sanity Check
        if pos_size_usd > (self.portfolio_value_usd * 0.5):
            pos_size_usd = self.portfolio_value_usd * 0.5 # Max 50% leverage
        
        dec = RiskDecision(
            agent_id=self.agent_id,
            symbol=symbol,
            action=action,
            approved=approved,
            position_size_usd=round(pos_size_usd, 2),
            stop_loss_price=round(sl, 2),
            take_profit_price=round(tp, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            market_context=market_context,
            reasoning=f"LLM: {reasoning}",
            quant_signal=quant,
            sentiment_signal=sentiment
        )
        
        
        await self.deps.redis.publish_message("risk:decisions", dec.model_dump_json())
        
        await self.log_manager.info(
            category="AGENT",
            source=self.agent_id,
            message=f"Risk Entscheidung: {action.value} (Approved: {approved})",
            details={"pos_size_usd": round(pos_size_usd, 2), "rr_ratio": round(rr_ratio, 2)}
        )
        self.logger.info(f"Risk Entscheidung: {action} (Approved: {approved}) | Size: ${pos_size_usd:.2f}")
        
        # Set state back so we wait for new fresh signals
        self.latest_quant = None
        self.latest_sentiment = None

    async def run_stream(self) -> None:
        pubsub = await self.deps.redis.subscribe_channel("signals:quant")
        if not pubsub:
            return
            
        await pubsub.subscribe("signals:sentiment")
        self.logger.info("RiskAgent lauscht auf quant und sentiment.")
        
        while self.state.running:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    channel = msg['channel']
                    payload = json.loads(msg['data'])
                    
                    if channel == "signals:quant":
                        self.latest_quant = QuantSignalV2(**payload)
                        self.logger.debug("RiskAgent hat Quant Signal empfangen.")
                    elif channel == "signals:sentiment":
                        self.latest_sentiment = SentimentSignalV2(**payload)
                        self.logger.debug("RiskAgent hat Sentiment Signal empfangen.")
                        
                    # Evaluate if we have both signals!
                    if self.latest_quant and self.latest_sentiment:
                        await self._evaluate_risk()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Fehler im Risk-Stream: {e}")
                await asyncio.sleep(1)
