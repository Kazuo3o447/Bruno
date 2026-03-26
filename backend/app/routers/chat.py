import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")


class ChatRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    model: str


@router.post("/chat/ask", response_model=ChatResponse)
async def ask_ollama(request: ChatRequest):
    """Proxy requests to Ollama LLM running on Windows host"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": request.model,
                    "prompt": request.prompt,
                    "stream": request.stream
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return ChatResponse(
                response=data.get("response", ""),
                model=data.get("model", request.model)
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_HOST}. Ensure Ollama is running on Windows host."
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Ollama request timed out"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/models")
async def list_models():
    """List available Ollama models"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_HOST}/api/tags",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_HOST}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
