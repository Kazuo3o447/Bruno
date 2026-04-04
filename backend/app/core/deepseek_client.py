"""
Deepseek Reasoning API Client

Ersetzt OllamaProvider für Post-Trade Analyse und Learning.
Nutzt Deepseek API für strukturierte JSON-Antworten.
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("deepseek_client")

class DeepseekReasoningClient:
    """
    Deepseek Reasoning API Client für Post-Trade Analyse.
    
    Features:
    - JSON-Mode für strukturierte Antworten
    - Reasoning Model für tiefgehende Analyse
    - Timeout und Retry Logic
    - Error Handling und Fallback
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = 30.0
        self.max_retries = 3
        
        # Model Konfiguration
        self.reasoning_model = "deepseek-chat"
        self.chat_model = "deepseek-chat"
        
        # Headers
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_json(self, prompt: str, model: str = None, 
                           temperature: float = 0.3, max_tokens: int = 4000) -> Dict[str, Any]:
        """
        Generiert strukturierte JSON-Antwort von Deepseek API.
        
        Args:
            prompt: Der Prompt für die Analyse
            model: Zu verwendendes Model (default: deepseek-reasoning)
            temperature: Kreativität (0.0-1.0)
            max_tokens: Maximale Token
            
        Returns:
            Dict mit der strukturierten Antwort
        """
        if model is None:
            model = self.reasoning_model
            
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Du bist ein erfahrener Krypto-Trading-Analyst. Antworte immer im gültigen JSON-Format."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}
        }
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=self.headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        # JSON parsen
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            logger.warning(f"Deepseek JSON Parse Error: {content}")
                            # Fallback: Manuelles JSON extrahieren
                            return self._extract_json_fallback(content)
                    
                    elif response.status_code == 429:
                        logger.warning(f"Deepseek Rate Limit (Attempt {attempt + 1})")
                        await asyncio.sleep(2 ** attempt)  # Exponential Backoff
                        continue
                    
                    else:
                        logger.error(f"Deepseek API Error: {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"Deepseek Request Error (Attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
        
        # Fallback bei allen Fehlern
        return self._get_fallback_response()
    
    def _extract_json_fallback(self, content: str) -> Dict[str, Any]:
        """Extrahiert JSON aus Response wenn direktes Parsen fehlschlägt."""
        try:
            # Suche nach JSON im Text
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except Exception:
            pass
        
        logger.error("JSON Fallback failed")
        return self._get_fallback_response()
    
    def _get_fallback_response(self) -> Dict[str, Any]:
        """Sichere Fallback-Antwort bei API-Fehlern."""
        return {
            "error": "API_ERROR",
            "message": "Deepseek API nicht verfügbar",
            "trade_rating": 5,
            "success_factors": ["API Fallback"],
            "failure_factors": ["API nicht erreichbar"],
            "improvements": ["API-Verbindung prüfen"],
            "learning_recommendations": ["System-Stabilität verbessern"]
        }
    
    async def generate_text(self, prompt: str, model: str = None,
                          temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        Generiert Text-Antwort von Deepseek API.
        
        Args:
            prompt: Der Prompt für die Analyse
            model: Zu verwendendes Model
            temperature: Kreativität
            max_tokens: Maximale Token
            
        Returns:
            String mit der Antwort
        """
        if model is None:
            model = self.chat_model
            
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Du bist ein erfahrener Krypto-Trading-Analyst."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Deepseek Text API Error: {response.status_code}")
                    return "API Error - konnte keine Antwort generieren"
                    
        except Exception as e:
            logger.error(f"Deepseek Text Request Error: {e}")
            return "Request Error - konnte keine Antwort generieren"
    
    async def health_check(self) -> Dict[str, Any]:
        """Prüft die Verfügbarkeit der Deepseek API."""
        try:
            test_prompt = "Antworte mit JSON: {'status': 'ok', 'message': 'test'}"
            result = await self.generate_json(test_prompt, max_tokens=100)
            
            return {
                "status": "online" if result.get("status") == "ok" else "error",
                "message": result.get("message", "API erreichbar"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health Check failed: {e}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Singleton Instance
_deepseek_client = None

def get_deepseek_client() -> DeepseekReasoningClient:
    """Gibt die Deepseek Client Instance zurück."""
    global _deepseek_client
    if _deepseek_client is None:
        api_key = "sk-2f93b3854d8b4d1f8a42e2fc00d55da3"
        _deepseek_client = DeepseekReasoningClient(api_key)
    return _deepseek_client
