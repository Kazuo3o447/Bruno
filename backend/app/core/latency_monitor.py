"""
Latenz-Monitor — Bruno Trading Bot

Überwacht aktiv:
- Binance WebSocket Verbindungsqualität
- Ollama Inferenz-Zeiten
- Generelle Netzwerk-Erreichbarkeit

Ubuntu-ready: Kein WSL2-spezifischer Code.
Auf Ubuntu mit nativem Docker sind Latenzen deutlich niedriger als auf WSL2.
"""

import asyncio
import time
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("latency_monitor")


class LatencyMonitor:

    # Schwellenwerte
    BINANCE_WS_LATENCY_VETO_MS = 500       # Trade-Veto bei >500ms
    OLLAMA_INFERENCE_WARN_MS = 8000        # Nur Warning bei >8s
    OLLAMA_INFERENCE_FALLBACK_MS = 30000   # Fallback-Modus bei >30s

    REDIS_KEY = "bruno:telemetry:latency"

    def __init__(self, redis_client, ollama_host: str):
        self.redis = redis_client
        self.ollama_host = ollama_host
        self._binance_latency_ms: float = 0.0
        self._ollama_latency_ms: float = 0.0
        self._veto_active: bool = False

    async def check_binance_latency(self) -> float:
        """Ping-Test gegen Binance REST (leichtgewichtig, kein WS nötig)."""
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    "https://fapi.binance.com/fapi/v1/ping"
                )
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    self._binance_latency_ms = latency
                    return latency
        except Exception:
            pass
        latency = (time.perf_counter() - start) * 1000
        self._binance_latency_ms = latency
        return latency

    async def check_ollama_latency(self) -> float:
        """Minimal-Inference-Test gegen Ollama."""
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.get(f"{self.ollama_host}/api/tags")
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    self._ollama_latency_ms = latency
                    return latency
        except Exception:
            pass
        latency = (time.perf_counter() - start) * 1000
        self._ollama_latency_ms = latency
        return latency

    async def run_checks(self) -> dict:
        """
        Führt alle Latenz-Checks aus.
        Wird alle 5 Minuten vom ContextAgent aufgerufen.
        """
        binance_ms, ollama_ms = await asyncio.gather(
            self.check_binance_latency(),
            self.check_ollama_latency(),
            return_exceptions=True
        )

        if isinstance(binance_ms, Exception):
            binance_ms = 9999.0
        if isinstance(ollama_ms, Exception):
            ollama_ms = 9999.0

        # Trade-Veto nur bei Binance-Latenz
        veto = binance_ms > self.BINANCE_WS_LATENCY_VETO_MS
        self._veto_active = veto

        # Ollama-Status
        ollama_status = (
            "ok" if ollama_ms < self.OLLAMA_INFERENCE_WARN_MS
            else "degraded" if ollama_ms < self.OLLAMA_INFERENCE_FALLBACK_MS
            else "fallback_required"
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "binance_latency_ms": round(binance_ms, 1),
            "ollama_latency_ms": round(ollama_ms, 1),
            "trade_veto_active": veto,
            "ollama_status": ollama_status,
            "overall_health": (
                "degraded" if veto or ollama_status != "ok" else "ok"
            )
        }

        await self.redis.set_cache(
            self.REDIS_KEY, result, ttl=600
        )

        if veto:
            logger.warning(
                f"⛔ LATENZ-VETO: Binance {binance_ms:.0f}ms > "
                f"{self.BINANCE_WS_LATENCY_VETO_MS}ms"
            )
        if ollama_status != "ok":
            logger.warning(
                f"⚠️ Ollama langsam: {ollama_ms:.0f}ms "
                f"({ollama_status})"
            )

        return result

    def is_veto_active(self) -> bool:
        return self._veto_active
