# LLM Provider — LEGACY (v1)

> **Status:** 📦 ARCHIVIERT — Diese Architektur wurde in v2.2 entfernt
> 
> **Aktuell:** Nur Deepseek Reasoning API für Post-Trade Analyse
> 
> **Historie:** Lokal (Ollama) oder Cloud (DeepSeek/Groq) über Config-Flag austauschbar

---

## Architektur

### Provider-Abstraktion

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_json(self, prompt, layer_name, system_prompt=None, use_reasoning_model=False) -> dict:
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        ...
    
    @abstractmethod
    async def close(self) -> None:
        ...
```

### Implementierungen

#### 1. **OllamaProvider** (Default)
- **Primary Model:** `qwen2.5:14b`
- **Reasoning Model:** `deepseek-r1:14b`
- **JSON-Format:** `format="json"` Parameter
- **Retry-Logic:** 2 Versuche mit Repair-Prompt

#### 2. **CloudProvider** (Future)
- **Layer 1+3:** Groq `llama-3.1-8b-instant`
- **Layer 2:** DeepSeek `deepseek-reasoner`
- **Activation:** `LLM_PROVIDER=cloud` in .env

---

## JSON-Problem Lösung

### 1. **Ollama format="json"**
```python
payload = {
    "model": model,
    "prompt": prompt,
    "format": "json",  # ← Erzwingt JSON-Grammatik auf Token-Ebene
    "options": {"temperature": temperature}
}
```

### 2. **Layer-spezifische Temperaturen**
```python
LAYER_TEMPERATURES = {
    "layer1_regime":    0.1,   # Klassifikation → fast deterministisch
    "layer2_reasoning": 0.3,   # Strategisches Denken → etwas Varianz
    "layer3_devil":     0.5,   # Advocatus Diaboli → braucht Kreativität
    "sentiment":        0.2,
    "debrief":          0.4,
}
```

### 3. **Retry mit Repair-Prompt**
```python
for attempt in range(2):
    raw = await self._call_ollama(
        prompt=prompt if attempt == 0 else self._repair_prompt(prompt),
        ...
    )
    parsed = self._parse_json(raw)
    if parsed is not None:
        return parsed

# Repair-Prompt bei Parse-Error
def _repair_prompt(original_prompt: str) -> str:
    return (
        "WICHTIG: Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt.\n"
        "Kein Text davor oder danach. Kein Markdown. Nur { ... }.\n\n"
        + original_prompt
    )
```

### 4. **Robust JSON Parsing**
```python
@staticmethod
def _parse_json(raw: str) -> Optional[dict]:
    if not raw or not raw.strip():
        return None
    
    # Markdown entfernen
    clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
    
    # JSON-Block finden
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    
    # Fallback: ganze Antwort parsen
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return None
```

### 5. **HOLD Fallback**
```python
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
        "_parse_error": True,
    },
    "layer3": {
        "blocker": True,
        "blocking_reasons": ["JSON_PARSE_ERROR — Sicherheits-Blocker aktiv"],
        "_parse_error": True,
    },
}
```

---

## Konfiguration

### .env.example
```bash
# LLM Provider (Phase C)
LLM_PROVIDER=ollama
OLLAMA_HOST=http://host.docker.internal:11434
DEEPSEEK_API_KEY=your_deepseek_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### Provider Switch
```python
# Automatische Provider-Auswahl basierend auf Config
llm_provider: BaseLLMProvider = create_llm_provider(
    provider=getattr(settings, "LLM_PROVIDER", "ollama"),
    ollama_host=settings.OLLAMA_HOST,
    deepseek_api_key=getattr(settings, "DEEPSEEK_API_KEY", ""),
    groq_api_key=getattr(settings, "GROQ_API_KEY", ""),
)
```

---

## Usage

### In LLM Cascade
```python
# Layer 1: Regime-Erkennung
l1_raw = await llm_provider.generate_json(
    prompt=_build_layer1_prompt(grss_components, market_snapshot),
    layer_name="layer1_regime",
    use_reasoning_model=False,
)

# Layer 2: Strategisches Reasoning
l2_raw = await llm_provider.generate_json(
    prompt=_build_layer2_prompt(layer1_output, market_context, ...),
    layer_name="layer2_reasoning",
    use_reasoning_model=True,  # deepseek-r1:14b
)

# Layer 3: Advocatus Diaboli
l3_raw = await llm_provider.generate_json(
    prompt=_build_layer3_prompt(layer2_output, market_context),
    layer_name="layer3_devil",
    use_reasoning_model=False,
)
```

### Legacy Kompatibilität
```python
# Für SentimentAgent (keine Breaking Changes)
class _LegacyOllamaClient:
    async def generate_response(self, prompt: str, use_reasoning: bool = False, ...) -> str:
        result = await llm_provider.generate_json(
            prompt=prompt,
            layer_name="sentiment",
            use_reasoning_model=use_reasoning,
        )
        return json.dumps(result) if "_parse_error" not in result else json.dumps({"sentiment": 0.0})

ollama_client = _LegacyOllamaClient()
```

---

## Performance

### Timing-Ziele
- **OllamaProvider:** < 2s pro Layer
- **CloudProvider:** < 1s pro Layer (zukünftig)

### Connection Pooling
```python
self._client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
    limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
)
```

### Health Check
```python
async def health_check(self) -> bool:
    try:
        client = await self._get_client()
        r = await client.get(f"{self.base_url}/api/tags")
        return r.status_code == 200
    except Exception:
        return False
```

---

## Cloud Provider (Future)

### DeepSeek + Groq Kombination
```python
class CloudProvider(BaseLLMProvider):
    async def generate_json(self, prompt, layer_name, ...):
        if layer_name == "layer2_reasoning":
            # DeepSeek für strategisches Denken
            return await self._call_deepseek(prompt, temperature=0.3)
        else:
            # Groq für Klassifikation und Safety
            return await self._call_groq(prompt, temperature=0.1)
```

### Activation
```bash
# Nach Paper-Trading Phase
LLM_PROVIDER=cloud
DEEPSEEK_API_KEY=sk-...
GROQ_API_KEY=gsk_...
```

---

## Error Handling

### Layer-spezifische Fallbacks
- **Layer 1:** `regime: "unknown"`, `confidence: 0.0`
- **Layer 2:** `decision: "HOLD"`, `confidence: 0.0`
- **Layer 3:** `blocker: true`, `blocking_reasons: ["JSON_PARSE_ERROR"]`

### Logging
```python
logger.warning(f"[{layer_name}] JSON-Parse Fehler (Versuch {attempt + 1}/2)")
logger.error(f"[{layer_name}] Beide Versuche gescheitert — HOLD Fallback.")
```

---

## Testing

### Unit Tests
```python
async def test_ollama_provider_parse_json():
    provider = OllamaProvider()
    
    # Valid JSON
    result = provider._parse_json('{"regime": "trending_bull"}')
    assert result == {"regime": "trending_bull"}
    
    # JSON in Markdown
    result = provider._parse_json('```json\n{"regime": "trending_bull"}\n```')
    assert result == {"regime": "trending_bull"}
    
    # Invalid JSON
    result = provider._parse_json('not json')
    assert result is None
```

### Integration Tests
```python
async def test_llm_provider_health():
    assert await llm_provider.health_check() is True
    
    result = await llm_provider.generate_json(
        prompt='{"regime": "test"}',
        layer_name="layer1_regime"
    )
    assert "_parse_error" not in result
```

---

## Migration Path

### Phase C (Current)
- **OllamaProvider** mit lokalen Modellen
- **JSON-Format** und Retry-Logic
- **HOLD Fallbacks** für Stabilität

### Phase D (Future)
- **CloudProvider** mit DeepSeek/Groq
- **Kein Code-Change** nötig
- **Performance-Boost** durch Cloud-LLMs

---

## Benefits

### 1. **Provider-Agnostic**
- Kein Code-Umbau bei Cloud-Wechsel
- Einheitliche API für alle LLM-Aufrufe

### 2. **JSON Reliability**
- `format="json"` erzwingt gültige JSON
- Retry mit Repair-Prompt
- HOLD Fallbacks verhindern Crashes

### 3. **Performance**
- Layer-spezifische Temperaturen
- Connection Pooling
- Health Checks

### 4. **Future-Proof**
- Cloud-Provider vorbereitet
- Legacy-Kompatibilität erhalten
- Einfache Erweiterbarkeit

---

*Der LLM Provider macht Phase C robust und zukunftssicher — von lokalen Modellen zu Cloud-LLMs ohne Breaking Changes.*
