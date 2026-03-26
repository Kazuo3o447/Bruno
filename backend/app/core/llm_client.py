import httpx
import logging
import asyncio
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama Client für Windows-Hybrid-Architektur.
    
    Kommuniziert mit nativem Ollama auf Windows-Host über host.docker.internal.
    Unterstützt unsere Hidden Champions: qwen2.5:14b und deepseek-r1:14b.
    """
    
    def __init__(self):
        # Nutzt host.docker.internal aus der .env für nativen Windows-Zugriff
        self.base_url = settings.OLLAMA_HOST
        self.primary_model = "qwen2.5:14b"
        self.reasoning_model = "deepseek-r1:14b"
        self.timeout = 60.0
        
        # HTTP Client mit Connection Pooling
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Erstellt oder gibt den HTTP Client zurück."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        """Schließt den HTTP Client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate_response(
        self, 
        prompt: str, 
        use_reasoning: bool = False, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generiert eine Antwort vom LLM."""
        model = self.reasoning_model if use_reasoning else self.primary_model
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = data.get("response", "")
            
            logger.debug(f"LLM Response von {model}: {len(result)} Zeichen")
            return result
            
        except httpx.RequestError as e:
            logger.error(f"Ollama Verbindungsfehler ({model}): {e}")
            return f"Error: LLM {model} nicht erreichbar. Prüfe ob Ollama auf Windows-Host läuft."
        except httpx.TimeoutException:
            logger.error(f"Ollama Timeout ({model})")
            return f"Error: LLM {model} Timeout nach {self.timeout}s."
        except Exception as e:
            logger.error(f"Ollama unerwarteter Fehler ({model}): {e}")
            return f"Error: Unerwarteter Fehler bei LLM {model}."

    async def generate_chat(
        self,
        messages: list[Dict[str, str]],
        use_reasoning: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generiert eine Antwort aus Chat-Messages."""
        model = self.reasoning_model if use_reasoning else self.primary_model
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = data.get("message", {}).get("content", "")
            
            logger.debug(f"LLM Chat Response von {model}: {len(result)} Zeichen")
            return result
            
        except httpx.RequestError as e:
            logger.error(f"Ollama Chat Verbindungsfehler ({model}): {e}")
            return f"Error: LLM {model} nicht erreichbar."
        except Exception as e:
            logger.error(f"Ollama Chat unerwarteter Fehler ({model}): {e}")
            return f"Error: Unerwarteter Fehler bei LLM {model}."

    async def list_models(self) -> Optional[Dict[str, Any]]:
        """Listet alle verfügbaren Modelle auf."""
        url = f"{self.base_url}/api/tags"
        
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Verfügbare Ollama Modelle: {len(data.get('models', []))}")
            return data
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Modelle: {e}")
            return None

    async def health_check(self) -> bool:
        """Prüft ob Ollama erreichbar ist."""
        try:
            models = await self.list_models()
            return models is not None and len(models.get('models', [])) > 0
        except Exception:
            return False

    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analysiert Sentiment mit dem Primary Model."""
        prompt = f"""
Analysiere folgenden Text auf Sentiment (Bullish/Bearish):
"{text}"

Gib zurück als JSON:
{{
    "sentiment": -1.0 bis 1.0 (-1 = stark bearish, 0 = neutral, 1 = stark bullish),
    "confidence": 0.0 bis 1.0,
    "reasoning": "kurze Begründung (max 50 Wörter)"
}}
"""
        
        response = await self.generate_response(prompt, use_reasoning=False)
        
        try:
            # Versuche JSON zu parsen
            import json
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: einfache Sentiment-Analyse
            positive_words = ["bullish", "buy", "up", "gain", "profit", "positive"]
            negative_words = ["bearish", "sell", "down", "loss", "negative", "drop"]
            
            text_lower = text.lower()
            pos_count = sum(1 for word in positive_words if word in text_lower)
            neg_count = sum(1 for word in negative_words if word in text_lower)
            
            if pos_count > neg_count:
                sentiment = min(0.8, pos_count * 0.2)
            elif neg_count > pos_count:
                sentiment = max(-0.8, -neg_count * 0.2)
            else:
                sentiment = 0.0
                
            return {
                "sentiment": sentiment,
                "confidence": 0.5,
                "reasoning": "Fallback-Analyse"
            }

    async def trading_analysis(self, market_data: str, sentiment_score: float) -> str:
        """Führt Trading-Analyse mit Reasoning Model durch."""
        prompt = f"""
Gegeben:
- Markt-Daten: {market_data}
- Sentiment-Score: {sentiment_score}

Als Trading-Experte analysiere diese Situation und gib eine klare Empfehlung:
1. MARKT-AUSLAGE (kurz)
2. ENTRY/EXIT-LOGIK
3. RISK/REWARD
4. FINALE ENTSCHEIDUNG: BUY/SELL/HOLD

Antworte präzise und handlungsorientiert.
"""
        
        return await self.generate_response(prompt, use_reasoning=True)


# Singleton-Instanz
ollama_client = OllamaClient()
