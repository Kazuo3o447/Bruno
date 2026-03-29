"""
LLM Provider — Phase C

Abstrakte Provider-Architektur: lokal (Ollama) oder Cloud (DeepSeek/Groq)
über einen Config-Flag austauschbar — kein Code-Umbau nötig.

Das JSON-Problem (kaum brauchbare Outputs): gelöst durch
  1. Ollama format:"json" Parameter — erzwingt JSON-Grammatik auf Token-Ebene
  2. Explizite JSON-Schema-Beispiele im Prompt
  3. Retry mit Re-Prompt bei Parse-Fehler (max 1 Retry)
  4. Deterministischere Temperatures je Layer (0.1 / 0.3 / 0.5)
  5. HOLD als Fallback wenn beide Versuche scheitern — nie ein Crash

Wechsel zu Cloud-LLMs nach Paper-Trading: LLM_PROVIDER=cloud in .env setzen.
"""

import httpx
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Temperature-Presets je Cascade-Layer ──────────────────────────────────
LAYER_TEMPERATURES = {
    "layer1_regime":    0.1,   # Klassifikation → fast deterministisch
    "layer2_reasoning": 0.3,   # Strategisches Denken → etwas Varianz OK
    "layer3_devil":     0.5,   # Advocatus Diaboli → braucht Kreativität
    "sentiment":        0.2,
    "debrief":          0.4,
}

HOLD_FALLBACKS = {
    "layer1": {
        "regime": "unknown",
        "confidence": 0.0,
        "key_signals": ["JSON_PARSE_ERROR — HOLD erzwungen"],
        "_parse_error": True,
    },
    "layer2": {
        "decision": "HOLD",
        "confidence": 0.0,
        "entry_reasoning": "JSON_PARSE_ERROR — HOLD erzwungen",
        "risk_factors": ["LLM Output nicht parsebar"],
        "suggested_sl_pct": 0.010,
        "suggested_tp_pct": 0.020,
        "_parse_error": True,
    },
    "layer3": {
        "blocker": True,
        "blocking_reasons": ["JSON_PARSE_ERROR — Sicherheits-Blocker aktiv"],
        "risk_override": False,
        "_parse_error": True,
    },
}


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        layer_name: str,
        system_prompt: Optional[str] = None,
        use_reasoning_model: bool = False,
    ) -> dict:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class OllamaProvider(BaseLLMProvider):
    PRIMARY_MODEL   = "qwen2.5:14b"
    REASONING_MODEL = "deepseek-r1:14b"

    def __init__(self, base_url: str = "http://host.docker.internal:11434"):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
                limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            r = await client.get(f"{self.base_url}/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def generate_json(
        self,
        prompt: str,
        layer_name: str,
        system_prompt: Optional[str] = None,
        use_reasoning_model: bool = False,
    ) -> dict:
        model = self.REASONING_MODEL if use_reasoning_model else self.PRIMARY_MODEL
        temperature = LAYER_TEMPERATURES.get(layer_name, 0.3)

        for attempt in range(2):
            raw = await self._call_ollama(
                model=model,
                prompt=prompt if attempt == 0 else self._repair_prompt(prompt),
                system_prompt=system_prompt,
                temperature=temperature,
                force_json=True,
            )
            if raw is None:
                break

            parsed = self._parse_json(raw)
            if parsed is not None:
                return parsed

            logger.warning(
                f"[{layer_name}] JSON-Parse Fehler (Versuch {attempt + 1}/2). "
                f"Raw: {raw[:200]}"
            )

        logger.error(f"[{layer_name}] Beide Versuche gescheitert — HOLD Fallback.")
        layer_key = layer_name.split("_")[0]
        return HOLD_FALLBACKS.get(layer_key, {"error": "parse_failed", "_parse_error": True})

    async def _call_ollama(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        force_json: bool,
    ) -> Optional[str]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 1024},
        }
        if system_prompt:
            payload["system"] = system_prompt
        if force_json:
            payload["format"] = "json"

        try:
            client = await self._get_client()
            r = await client.post(f"{self.base_url}/api/generate", json=payload)
            r.raise_for_status()
            return r.json().get("response", "")
        except httpx.TimeoutException:
            logger.error(f"Ollama Timeout ({model})")
        except httpx.RequestError as e:
            logger.error(f"Ollama Verbindungsfehler ({model}): {e}")
        except Exception as e:
            logger.error(f"Ollama Fehler ({model}): {e}")
        return None

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw or not raw.strip():
            return None
        clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _repair_prompt(original_prompt: str) -> str:
        return (
            "WICHTIG: Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt.\n"
            "Kein Text davor oder danach. Kein Markdown. Nur { ... }.\n\n"
            + original_prompt
        )


class CloudProvider(BaseLLMProvider):
    """
    Stub für Cloud-LLMs nach Paper-Trading.
    Layer 1+3: Groq llama-3.1-8b-instant
    Layer 2:   DeepSeek deepseek-reasoner
    Aktivierung: LLM_PROVIDER=cloud in .env
    """
    def __init__(self, deepseek_api_key: str = "", groq_api_key: str = ""):
        self.deepseek_api_key = deepseek_api_key
        self.groq_api_key = groq_api_key

    async def generate_json(self, prompt, layer_name, system_prompt=None,
                             use_reasoning_model=False) -> dict:
        raise NotImplementedError("CloudProvider nach Paper-Trading implementieren.")

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass


def create_llm_provider(provider: str = "ollama", **kwargs) -> BaseLLMProvider:
    if provider == "cloud":
        return CloudProvider(
            deepseek_api_key=kwargs.get("deepseek_api_key", ""),
            groq_api_key=kwargs.get("groq_api_key", ""),
        )
    return OllamaProvider(base_url=kwargs.get("ollama_host", "http://host.docker.internal:11434"))


from app.core.config import settings as _settings

llm_provider: BaseLLMProvider = create_llm_provider(
    provider=getattr(_settings, "LLM_PROVIDER", "ollama"),
    ollama_host=_settings.OLLAMA_HOST,
    deepseek_api_key=getattr(_settings, "DEEPSEEK_API_KEY", ""),
    groq_api_key=getattr(_settings, "GROQ_API_KEY", ""),
)

# Legacy-Kompatibilität für SentimentAgent
class _LegacyOllamaClient:
    async def generate_response(self, prompt: str, use_reasoning: bool = False,
                                 system_prompt=None, temperature: float = 0.7,
                                 max_tokens=None) -> str:
        result = await llm_provider.generate_json(
            prompt=prompt,
            layer_name="sentiment",
            system_prompt=system_prompt,
            use_reasoning_model=use_reasoning,
        )
        if isinstance(result, dict) and "_parse_error" not in result:
            return json.dumps(result)
        return json.dumps({"sentiment": 0.0, "confidence": 0.5, "reasoning": "fallback"})

    async def health_check(self) -> bool:
        return await llm_provider.health_check()

    async def close(self):
        await llm_provider.close()


ollama_client = _LegacyOllamaClient()
