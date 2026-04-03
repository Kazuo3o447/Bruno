# KI- & Agenten-Architektur

> **Referenz: WINDSURF_MANIFEST.md v2.0 — Dieses Dokument ist implementierungsorientiert**
>
> **Manifest hat Vorrang.** Bei Widerspruch zwischen diesem Dokument und dem Manifest gilt das Manifest.
>
> ✅ **Primäre Umgebung:** Windows mit **Ryzen 7 7800X3D + RX 7900 XT** (native Ollama)

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Aktueller Fokus (Manifest v2.0)

> 🔧 **Wir bauen auf Windows:** Docker Desktop (WSL2) + Native Ollama auf RX 7900 XT

### Phase C ✅ COMPLETED (2026-03-30)
- [x] LLM Cascade (3 Layer) implementiert & verifiziert
- [x] **Bruno Pulse**: Echtzeit-Transparency (Sub-States & LLM Pulse)
- [x] **Background Heartbeat Loop**: Unabhängige Vitalzeichen-Übermittlung (15s)
- [x] Regime Manager mit 2-Bestätigungs-Logik + Transition Buffer
- [x] PositionTracker/PositionMonitor im Worker verdrahtet
- [x] CoinGlass Graceful Degradation ohne API-Key
- [x] Telegram Notifications mit Chat-ID-Auth
- [x] Erweiterte Daten-Quellen (Funding Rates, Liquidations)
- [x] Profit-Factor-Tracking aus realisierter P&L-Historie

### Phase A — Fundament ✅ COMPLETED (2026-03-29)

**Ziel erreicht:** Den Bot ehrlich machen. Keine Zufallsdaten mehr.

**Erledigt:**
- [x] `ContextAgent`: Alle `random.uniform()` entfernt
- [x] BTC 24h Change aus Redis berechnet
- [x] **Binance REST**: Open Interest, OI-Delta, L/S-Ratio, Perp-Basis
- [x] **Deribit Public**: Put/Call Ratio, DVOL (kostenlos)
- [x] **GRSS-Funktion**: echte Daten (Manifest Abschnitt 5)
- [x] **Polling-Intervalle**: Quant 5s→300s, Context 60s→900s
- [x] **CVD State**: in Redis persistiert
- [x] **Data-Freshness Fail-Safe**: GRSS bricht bei stale data auf 0.0 ab
- [x] **Live-Trading Guard**: `LIVE_TRADING_APPROVED` Flag implementiert
- [x] **CryptoPanic Health**: Health-Telemetrie mit Latenz-Tracking

**Eiserne Regel:** GRSS muss 100% echte Daten verwenden. Keine Mocks. Keine `random.uniform()`. ✅ ERLEDIGT

---

## Schnell-Referenz: Die 6 Agenten (Manifest v2.0)

| Agent | Typ | Datenquellen | Output |
|-------|-----|--------------|--------|
| **Ingestion** | Streaming | Binance WS (5 Streams) | Redis Streams (OHLCV, OFI, Liqs, Funding) |
| **Context** | Polling | FRED, Deribit, RSS, Makro | Redis `bruno:context:grss` (GRSS Score 0–100) |
| **Sentiment** | Polling | 8× RSS, CryptoPanic, LLM | Redis `bruno:sentiment` |
| **Quant** | Polling | Redis, Orderbook | Redis `bruno:signals` (OFI, CVD) |
| **Risk** | Streaming | Alle Redis Channels | RAM-Veto (GRSS < 40 = Block) |
| **Execution** | Streaming | Risk + Signals | **Bybit API** (Limit/PostOnly Orders) |

**Börsen-Architektur:**
- **Binance** = Daten (WebSocket + REST, kostenlos)
- **Bybit** = **Execution** (Futures, max 1.0× Leverage, Unified Account)
- **Deribit** = Options-Daten (PCR, DVOL, kostenlos)

---

## Legacy-Inhalt (zu referenzieren, nicht als aktueller Stand)

*Der folgende Inhalt beschreibt die technische Implementierung. Die aktuellen Prioritäten sind in Manifest v2.0 Phase A definiert.*

---

## Inhaltsverzeichnis

1. [Lokale LLM-Infrastruktur](#lokale-llm-infrastruktur)
2. [Ehrlicher Ist-Stand der Agenten](#ehrlicher-ist-stand-der-agenten)
3. [Architektur-Entscheidungen](#architektur-entscheidungen)
4. [Zwei Agent-Basisklassen](#zwei-agent-basisklassen)
5. [Dependency Injection](#dependency-injection)
6. [Startup-Sequenz & Orchestrator](#startup-sequenz--orchestrator)
7. [Worker-Entrypoint](#worker-entrypoint)
8. [Message Contracts](#message-contracts)
9. [Redis Channel-Architektur](#redis-channel-architektur)
10. [Agent-Spezifikationen (Ist → Soll)](#agent-spezifikationen-ist--soll)
11. [Status-Monitoring & Heartbeat](#status-monitoring--heartbeat)
12. [Dateisystem-Übersicht (Zielzustand)](#dateisystem-übersicht-zielzustand)
13. [Implementierungsreihenfolge](#implementierungsreihenfolge)
14. [Verifizierung](#verifizierung)

---

## 1. Lokale LLM-Infrastruktur

### Primärmodell: Qwen 2.5 (14B)

| Attribut | Spezifikation |
|----------|---------------|
| **Modell** | `qwen2.5:14b` |
| **Einsatzzweck** | Schnelles Sentiment-Reasoning |
| **Stärken** | Code-Verständnis, logisches Schließen, geringe Latenz |
| **Kontext** | 128K Token |

### Analysemodell: DeepSeek-R1 (14B)

| Attribut | Spezifikation |
|----------|---------------|
| **Modell** | `deepseek-r1:14b` |
| **Einsatzzweck** | Tiefe Chain-of-Thought-Analysen |
| **Stärken** | Komplexes Reasoning, strategische Planung, Marktanalyse |
| **Besonderheit** | Denkprozess explizit sichtbar |

### Warum lokal?
- **Hardware:** Ryzen 7 7800X3D + AMD RX 7900 XT GPU, nativ auf Windows
- **Latenz:** Unter 500ms für Standard-Inferenz
- **Kosten:** Keine API-Gebühren, volle Datenkontrolle
- **Zugang aus Docker:** `http://host.docker.internal:11434`

### LLM Client (bestehend)

Der `OllamaClient` in `backend/app/core/llm_client.py` bleibt unverändert:

| Methode | Zweck |
|---------|-------|
| `generate_response()` | Single-Prompt Inferenz |
| `generate_chat()` | Multi-Turn Konversation |
| `analyze_sentiment()` | JSON-formatierte Sentiment-Analyse |
| `trading_analysis()` | Strategische Analyse mit DeepSeek-R1 |
| `health_check()` | Prüft ob Ollama erreichbar ist |

---

## Learning Mode (DRY_RUN only)

### Zweck
Das System sammelt im Paper-Trading-Modus Trainingsdaten für LLM-Kalibrierung und
Regime-Erkennung. Ohne Learning Mode: ~2 Trades/Tag = 3–8 Monate bis belastbare Daten.
Mit Learning Mode: 8–15 Trades/Tag + Phantom-Datenpunkte = deutlich schnellere Kalibrierung.

### Schwellen im Learning Mode
| Parameter | Produktion | Learning Mode |
|-----------|-----------|---------------|
| GRSS_Threshold (RiskAgent) | 40 | 25 |
| Layer 1 Confidence | 0.60 | 0.50 |
| Layer 2 Confidence | 0.65 | 0.55 |

### Aktivierung
`backend/config.json`: `"LEARNING_MODE_ENABLED": true` — nur wirksam wenn `DRY_RUN=True`.

### Trade Mode Flag
Jeder Trade wird in `trade_audit_logs.trade_mode` markiert:
- `production` — Produktions-Schwellen, DRY_RUN=False oder Learning Mode aus
- `learning` — Learning-Schwellen, DRY_RUN=True und Learning Mode aktiv
- `phantom` — HOLD-Zyklus nur für Auswertung, kein echter Trade

### Phantom Trades
Für jeden HOLD-Zyklus wird ein hypothetischer Trade gespeichert.
Nach `PHANTOM_HOLD_DURATION_MINUTES` (Standard: 240) wird der Outcome mit dem echten Preispfad berechnet.
Phantom Trades fließen **nie** in Portfolio, Kapital oder Live-Performance ein.

### Getrennte Auswertung
```sql
-- Nur Produktions-Trades
SELECT *
FROM trade_audit_logs
WHERE trade_mode = 'production';

-- Nur Learning-Mode-Trades
SELECT *
FROM trade_audit_logs
WHERE trade_mode = 'learning';

-- Phantom-Outcomes für HOLD-Qualität
SELECT *
FROM trade_debriefs
WHERE trade_mode = 'phantom';
```

---

## 2. Aktueller Status (Phase 7.5 - MLOps & Audit)

> **Das System verfügt über institutional-grade Monitoring und exakte Shadow-Trading Analytik.**

### ✅ Gelöste Probleme (Audit März 2026)

- **Execution Latenz:** Der `ExecutionAgentV3` nutzt einen lokalen RAM-Check (0ms Latenz) für Vetos.
- **Schatten-Handel (Audit):** Implementierung einer exakten **0.04% Taker-Fee** Simulation und BPS-Slippage Tracking.
- **Monitoring Hub:** Natives Monitoring für Telemetrie, Veto-Distribution und MLOps-Parameter.
- **Strict MLOps Security:** Das Dashboard ist **Read-Only**; Parameter-Updates erfolgen ausschließlich offline.
- **Offline Optimizer:** Erzwingt die Realität (PnL inkl. Gebühren & PF > 1.5).
- **Phase B Hardening:** CoinGlass läuft graceful ohne API-Key, Telegram ist chat-authentifiziert und der Profit Factor basiert auf realisierter P&L-Historie.
- **WebSocket Stabilität:** Robuste Retry-Logic mit Exponential Backoff und erweiterten Ping-Timeouts (30s) zur Vermeidung von Keepalive-Timeouts.
- **Frontend Routing:** Browser-kompatible WebSocket-URLs statt Docker-interner Hosts für Live-Daten und Logs.

- **Einheitliches Interface:** Alle Agenten erben von `BaseAgent` / `PollingAgent` / `StreamingAgent`.
- **HFT-Performance:** Der `ExecutionAgentV3` nutzt einen lokalen RAM-Check (0ms Latenz) für Vetos.
- **Sicherheits-Isolation:** `PublicExchangeClient` vs `AuthenticatedExchangeClient` Trennung.
- **Fehler-Handling:** Supervised Neustarts durch den `AgentOrchestrator` im Worker-Container.
- **Standardisierung:** Alle Pub/Sub Kanäle folgen dem `bruno:pubsub:*` Schema.

---

## 3. Architektur-Entscheidungen

> **Fundamental-Entscheidungen, die alles Weitere bestimmen.**

### Entscheidung 1: Zwei Container statt einem

```
bruno-api:    FastAPI (API + WebSocket) — KEINE Agenten
bruno-worker: Agent Orchestrator       — KEINE API
```

**Begründung:** Ein Agent-Crash (z.B. durch ccxt-Exception oder WebSocket-Timeout) darf nie den Health-Check oder die Backup-API umwerfen. Gleiche Codebase, verschiedene Entrypoints.

### Entscheidung 2: Zwei Agent-Basisklassen statt einer

Die 5 Agenten folgen **zwei fundamental verschiedenen Laufzeit-Mustern**:

| Muster | Agenten | Verhalten |
|--------|---------|-----------|
| **Polling** | Quant, Sentiment | Intervall-basiert: alle N Sekunden `process()` aufrufen |
| **Streaming** | Ingestion, Risk, Execution | Event-basiert: dauerhaft auf WebSocket/Pub/Sub lauschen |

Ein einzelnes `BaseAgent` mit `get_interval() -> 0` als Hack für Streaming-Agenten ist unehrlich. Der Ingestion Agent blockt in seinem WebSocket-Consumer — er hat kein Intervall. Der Risk Agent reagiert auf Pub/Sub Messages — er pollt nicht.

### Entscheidung 3: Dependency Injection statt globale Singletons

Jeder Agent bekommt seine Dependencies **explizit beim Erstellen** über ein `AgentDependencies`-Objekt. Kein Agent importiert `redis_client` oder `ollama_client` direkt als Modul-Singleton.

**Begründung:**
- Tests können Mock-Dependencies injizieren
- Verschiedene Agenten können verschiedene Konfigurationen nutzen
- Der Worker-Container steuert zentral, welche Infrastruktur wann initialisiert wird

### Entscheidung 4: setup() ist Pflicht, nicht optional

`setup()` wird **vom Orchestrator aufgerufen**, nicht vom Agent selbst. So weiß der Orchestrator, ob die Initialisierung erfolgreich war, bevor er den Agent in die Run-Schleife schickt.

### Entscheidung 5: Gestufter Startup statt alles gleichzeitig

Die Pipeline hat eine natürliche Topologie. Die Startreihenfolge bildet diese ab:

```
Stufe 1: [Ingestion]                 ← Daten-Feed muss zuerst stehen
Stufe 2: [Quant, Sentiment]          ← Analyse braucht Daten (parallel)
Stufe 3: [Risk]                      ← Entscheidung braucht Signale
Stufe 4: [Execution]                 ← Ausführung braucht Freigabe
```

---

## 4. Zwei Agent-Basisklassen

### Gemeinsame Basis: `BaseAgent`

```python
# backend/app/agents/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import asyncio
import logging
import traceback
import json

if TYPE_CHECKING:
    from app.agents.deps import AgentDependencies


class AgentState:
    """Interner Zustand eines Agenten — wird vom Orchestrator gelesen."""
    def __init__(self):
        self.running: bool = False
        self.error_count: int = 0
        self.consecutive_errors: int = 0
        self.processed_count: int = 0
        self.start_time: Optional[datetime] = None
        self.last_process_time: Optional[datetime] = None
        self.last_error: Optional[str] = None


class BaseAgent(ABC):
    """
    Gemeinsame Basis für alle Bruno-Agenten.
    
    Definiert Lifecycle (setup/teardown), State-Tracking und Heartbeat.
    Die run()-Logik wird von den Subklassen PollingAgent/StreamingAgent implementiert.
    """
    
    def __init__(self, agent_id: str, deps: "AgentDependencies"):
        self.agent_id = agent_id
        self.deps = deps
        self.state = AgentState()
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self._max_consecutive_errors = 10

    # --- Lifecycle (vom Orchestrator aufgerufen) ---

    @abstractmethod
    async def setup(self) -> None:
        """
        PFLICHT. Einmalige Initialisierung.
        
        Hier passiert alles was ein Agent braucht bevor er arbeiten kann:
        - Exchange-Verbindung aufbauen
        - Historische Daten laden (Warmup)
        - Pub/Sub Channels subscriben
        - API-Keys validieren
        
        Wird VOR run() vom Orchestrator aufgerufen.
        Wenn setup() eine Exception wirft, wird der Agent NICHT gestartet.
        """
        ...

    async def teardown(self) -> None:
        """
        Cleanup beim Stoppen. Optional überschreibbar.
        
        Hier: Exchange schließen, Connections aufräumen, etc.
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """
        Hauptschleife. Implementierung in PollingAgent/StreamingAgent.
        Kehrt erst zurück wenn der Agent gestoppt wird oder fatal crasht.
        """
        ...

    async def stop(self) -> None:
        """Signalisiert dem Agent, dass er sich beenden soll."""
        self.state.running = False
        self.logger.info(f"Stop-Signal gesendet an {self.agent_id}")

    # --- Heartbeat ---

    async def _send_heartbeat(self) -> None:
        """
        Meldet Agent-Status an Redis (TTL 60s).
        Wenn 60s kein Heartbeat kommt, gilt der Agent als tot.
        """
        try:
            heartbeat = {
                "agent_id": self.agent_id,
                "status": "running" if self.state.running else "stopped",
                "uptime_seconds": (
                    (datetime.now(timezone.utc) - self.state.start_time).total_seconds()
                    if self.state.start_time else 0
                ),
                "processed_count": self.state.processed_count,
                "error_count": self.state.error_count,
                "consecutive_errors": self.state.consecutive_errors,
                "last_error": self.state.last_error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.deps.redis.set_cache(
                f"heartbeat:{self.agent_id}",
                heartbeat,
                ttl=60
            )
        except Exception as e:
            # Heartbeat-Fehler darf NIEMALS den Agent crashen
            self.logger.debug(f"Heartbeat-Fehler (nicht kritisch): {e}")

    # --- Error Reporting ---

    async def _report_error(self, error: Exception) -> None:
        """Publiziert Fehler auf Redis für Monitoring/Telegram."""
        try:
            await self.deps.redis.publish_message(
                "alerts:agent_error",
                json.dumps({
                    "agent_id": self.agent_id,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "consecutive": self.state.consecutive_errors
                })
            )
        except Exception:
            pass  # Error-Reporting darf den Agent nie crashen
```

### PollingAgent — für periodische Arbeit

```python
# backend/app/agents/base.py (Fortsetzung)

class PollingAgent(BaseAgent):
    """
    Agent der periodisch arbeitet.
    
    Verwendung: Quant Agent (alle 30s), Sentiment Agent (alle 5min).
    
    Implementiere:
      - setup():        Initialisiering (Exchange, Warmup, etc.)
      - process():      Ein einzelner Verarbeitungszyklus
      - get_interval(): Pause zwischen zwei process()-Aufrufen in Sekunden
    """

    @abstractmethod
    async def process(self) -> None:
        """
        Ein einzelner Verarbeitungszyklus.
        Wird alle get_interval() Sekunden aufgerufen.
        
        Beispiel Quant: Candles laden → RSI berechnen → Signal publizieren
        Beispiel Sentiment: News holen → LLM analysieren → Score publizieren
        """
        ...

    @abstractmethod
    def get_interval(self) -> float:
        """Pause zwischen process()-Aufrufen in Sekunden."""
        ...

    async def run(self) -> None:
        """Polling-Loop: process() → sleep → process() → sleep → ..."""
        self.state.running = True
        self.state.start_time = datetime.now(timezone.utc)

        while self.state.running:
            try:
                await self._send_heartbeat()
                await self.process()
                self.state.processed_count += 1
                self.state.last_process_time = datetime.now(timezone.utc)
                self.state.consecutive_errors = 0  # Reset bei Erfolg
            except Exception as e:
                self.state.error_count += 1
                self.state.consecutive_errors += 1
                self.state.last_error = str(e)
                self.logger.error(f"process() Fehler: {e}")
                await self._report_error(e)

                if self.state.consecutive_errors >= self._max_consecutive_errors:
                    self.logger.critical(
                        f"{self.agent_id}: {self._max_consecutive_errors} Fehler "
                        f"in Folge — 5 Minuten Pause"
                    )
                    await asyncio.sleep(300)
                    self.state.consecutive_errors = 0

            await asyncio.sleep(self.get_interval())

        self.logger.info(f"{self.agent_id} run-loop beendet")
```

### StreamingAgent — für Event-basierte Arbeit

```python
# backend/app/agents/base.py (Fortsetzung)

class StreamingAgent(BaseAgent):
    """
    Agent der dauerhaft auf einen Event-Stream lauscht.
    
    Verwendung: Ingestion (WebSocket), Risk (Pub/Sub), Execution (Pub/Sub).
    
    Implementiere:
      - setup():      Initialisiering (WebSocket aufbauen, Channel subscriben)
      - run_stream(): Blockierende Stream-Verarbeitung
    """

    @abstractmethod
    async def run_stream(self) -> None:
        """
        Blockierender Stream-Consumer.
        
        Diese Methode läuft bis der Agent gestoppt wird.
        Sie enthält die eigene Event-Loop (WebSocket-Receive, Pub/Sub-Listen, etc.)
        
        Der Agent ist selbst dafür verantwortlich, self.state.running zu prüfen
        und bei False sauber zu beenden.
        
        Beispiel Ingestion: async for message in websocket: ...
        Beispiel Risk: while running: await pubsub.get_message(...)
        """
        ...

    async def run(self) -> None:
        """
        Wrapper um run_stream() mit Reconnect-Logik.
        
        Wenn run_stream() eine Exception wirft (z.B. WebSocket-Disconnect),
        wird automatisch mit Exponential Backoff reconnected.
        """
        self.state.running = True
        self.state.start_time = datetime.now(timezone.utc)
        backoff = 1

        while self.state.running:
            try:
                await self._send_heartbeat()
                await self.run_stream()
                break  # Normales Ende (stop() wurde aufgerufen)
            except Exception as e:
                self.state.error_count += 1
                self.state.consecutive_errors += 1
                self.state.last_error = str(e)
                self.logger.error(f"Stream-Fehler: {e}")
                await self._report_error(e)

                if self.state.consecutive_errors >= self._max_consecutive_errors:
                    self.logger.critical(
                        f"{self.agent_id}: {self._max_consecutive_errors} "
                        f"Stream-Fehler in Folge — 5 Minuten Pause"
                    )
                    await asyncio.sleep(300)
                    self.state.consecutive_errors = 0
                    backoff = 1
                else:
                    wait_time = min(backoff, 60)
                    self.logger.info(f"Reconnect in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    backoff = min(backoff * 2, 60)

        self.logger.info(f"{self.agent_id} run-loop beendet")
```

### Warum zwei Klassen statt einer?

```
PollingAgent:                    StreamingAgent:
┌──────────────┐                ┌──────────────────────┐
│ loop:        │                │ loop:                │
│   process()  │                │   run_stream()       │
│   sleep(30)  │                │     ↳ blockiert auf  │
│   process()  │                │       WebSocket/     │
│   sleep(30)  │                │       Pub/Sub        │
│   ...        │                │   ↳ bei Fehler:      │
└──────────────┘                │     reconnect mit    │
                                │     exp. backoff     │
                                └──────────────────────┘

Der Quant Agent pollt.          Der Ingestion Agent streamt.
Er hat eine Pause.              Er hat KEINE Pause.
Er ruft process() auf.          Er lebt IN run_stream().
```

Ein `get_interval() -> 0` verwischt diesen Unterschied. Der Code sieht gleich aus, aber das Verhalten ist fundamental anders. Zwei Klassen machen die Absicht klar.

---

## 5. Dependency Injection

### Das AgentDependencies-Objekt

```python
# backend/app/agents/deps.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.redis_client import RedisClient
    from app.core.llm_client import OllamaClient
    from app.core.config import Settings
    from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass
class AgentDependencies:
    """
    Alles was ein Agent zum Arbeiten braucht.
    
    Wird einmal im Worker-Entrypoint erstellt und an alle Agenten übergeben.
    Kein Agent importiert jemals redis_client oder ollama_client direkt.
    
    Vorteile:
    - Tests: Mock-Dependencies injizieren, kein Monkey-Patching
    - Kontrolle: Worker entscheidet wann Redis/DB verbunden wird
    - Flexibilität: Verschiedene Agenten können verschiedene Configs nutzen
    """
    redis: "RedisClient"
    config: "Settings"
    db_session_factory: "async_sessionmaker"  # Für DB-Zugriff (Execution Agent)
    ollama: "OllamaClient"                    # Für LLM-Zugriff (Sentiment Agent)
```

### Wie ein Agent Dependencies nutzt

```python
# Vorher (globaler Import — schlecht):
from app.core.redis_client import redis_client

class QuantAgent:
    async def start(self):
        await redis_client.publish_message(...)  # Woher kommt das? Ist es connected?

# Nachher (Dependency Injection — gut):
class QuantAgentV2(PollingAgent):
    def __init__(self, deps: AgentDependencies, symbol: str = "BTC/USDT"):
        super().__init__(agent_id="quant", deps=deps)
        self.symbol = symbol
    
    async def process(self):
        await self.deps.redis.publish_message(...)  # Explizit, testbar
```

### Was das für Tests bedeutet

```python
# test_quant_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_deps():
    deps = MagicMock(spec=AgentDependencies)
    deps.redis = AsyncMock()
    deps.redis.publish_message = AsyncMock()
    deps.redis.set_cache = AsyncMock()
    deps.config = Settings()
    return deps

async def test_quant_publishes_signal(mock_deps):
    agent = QuantAgentV2(deps=mock_deps, symbol="BTC/USDT")
    agent.prices = [100.0] * 50  # Genug für RSI
    
    await agent.process()
    
    mock_deps.redis.publish_message.assert_called_once()
    call_args = mock_deps.redis.publish_message.call_args
    assert call_args[0][0] == "signals:quant"  # Richtiger Channel
```

So werden Tests möglich, **ohne** Docker, Redis oder Binance laufen zu haben.

---

## 6. Startup-Sequenz & Orchestrator

### AgentOrchestrator

```python
# backend/app/agents/orchestrator.py

import asyncio
import logging
from typing import Dict, List
from app.agents.base import BaseAgent
from app.agents.deps import AgentDependencies

logger = logging.getLogger("orchestrator")


class AgentOrchestrator:
    """
    Verwaltet den kompletten Lifecycle aller Agenten.
    
    Verantwortlichkeiten:
    1. Gestufte Startup-Reihenfolge (Pipeline-Topologie)
    2. setup() für jeden Agent aufrufen und Fehler abfangen
    3. Supervised run() — crashed Agents neu starten
    4. Graceful Shutdown mit Timeout
    5. Redis-Kommandos empfangen (restart/stop von API aus)
    """

    # Die Startup-Reihenfolge bildet die Daten-Pipeline ab:
    # Ingestion → [Quant, Sentiment] → Risk → Execution
    STARTUP_STAGES: List[List[str]] = [
        ["ingestion"],              # Stufe 1: Daten-Feed
        ["quant", "sentiment"],     # Stufe 2: Analyse (parallel)
        ["risk"],                   # Stufe 3: Entscheidung
        ["execution"],              # Stufe 4: Ausführung
    ]

    def __init__(self, deps: AgentDependencies):
        self.deps = deps
        self._agents: Dict[str, BaseAgent] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    def register(self, agent_id: str, agent: BaseAgent) -> None:
        """Registriert einen Agent. Muss VOR start_all() passieren."""
        self._agents[agent_id] = agent
        logger.info(f"Agent registriert: {agent_id}")

    async def start_all(self) -> None:
        """
        Startet alle Agenten in der definierten Reihenfolge.
        
        Für jede Stufe:
        1. setup() aufrufen (kann fehlschlagen → Agent wird übersprungen)
        2. run() als supervised Task starten
        3. Kurze Grace-Period, dann nächste Stufe
        """
        for stage_index, stage in enumerate(self.STARTUP_STAGES):
            agent_ids_in_stage = [aid for aid in stage if aid in self._agents]
            
            if not agent_ids_in_stage:
                continue

            logger.info(f"=== Starte Stufe {stage_index + 1}: {agent_ids_in_stage} ===")

            for agent_id in agent_ids_in_stage:
                agent = self._agents[agent_id]
                
                # --- setup() aufrufen ---
                try:
                    await asyncio.wait_for(agent.setup(), timeout=30.0)
                    logger.info(f"  ✅ {agent_id}: setup() erfolgreich")
                except asyncio.TimeoutError:
                    logger.error(f"  ❌ {agent_id}: setup() Timeout (30s)")
                    continue  # Agent wird NICHT gestartet
                except Exception as e:
                    logger.error(f"  ❌ {agent_id}: setup() fehlgeschlagen: {e}")
                    continue  # Agent wird NICHT gestartet

                # --- Supervised run() starten ---
                task = asyncio.create_task(
                    self._supervised_run(agent_id, agent),
                    name=f"agent-{agent_id}"
                )
                self._tasks[agent_id] = task

            # Grace-Period zwischen Stufen (z.B. damit der Ingestion Agent
            # erste Ticks liefern kann bevor der Quant Agent startet)
            if stage_index < len(self.STARTUP_STAGES) - 1:
                await asyncio.sleep(3)

        running = [aid for aid, t in self._tasks.items() if not t.done()]
        logger.info(f"=== Alle Stufen abgeschlossen. {len(running)} Agenten laufen. ===")

    async def _supervised_run(
        self, agent_id: str, agent: BaseAgent, max_restarts: int = 5
    ) -> None:
        """
        Wrapper der einen Agent überwacht.
        
        Bei Crash:
        1. Fehler loggen
        2. teardown() aufrufen (Cleanup)
        3. Warten (exponentieller Backoff)
        4. setup() erneut aufrufen
        5. run() erneut starten
        
        Nach max_restarts aufgeben und Agent deaktivieren.
        """
        restart_count = 0

        while restart_count < max_restarts:
            try:
                await agent.run()
                # Normales Ende (stop() wurde aufgerufen)
                logger.info(f"{agent_id}: Sauber beendet")
                break
            except Exception as e:
                restart_count += 1
                logger.error(
                    f"{agent_id}: Unbehandelte Exception ({restart_count}/{max_restarts}): {e}"
                )
                await agent._report_error(e)

                # Cleanup
                try:
                    await agent.teardown()
                except Exception as teardown_err:
                    logger.warning(f"{agent_id}: teardown() Fehler: {teardown_err}")

                # Backoff
                wait_time = min(30 * restart_count, 300)
                logger.info(f"{agent_id}: Neustart in {wait_time}s...")
                await asyncio.sleep(wait_time)

                # Re-Setup
                try:
                    await asyncio.wait_for(agent.setup(), timeout=30.0)
                    logger.info(f"{agent_id}: Re-Setup erfolgreich, starte neu")
                except Exception as setup_err:
                    logger.error(f"{agent_id}: Re-Setup fehlgeschlagen: {setup_err}")
                    # Zählt als weiterer Fehler, nächster Loop-Durchlauf

        if restart_count >= max_restarts:
            logger.critical(
                f"💀 {agent_id}: {max_restarts} Neustarts erschöpft. Agent DEAKTIVIERT."
            )

    async def stop_all(self, timeout: float = 15.0) -> None:
        """Stoppt alle Agenten graceful mit Timeout."""
        logger.info("Stoppe alle Agenten...")

        # 1. Stop-Signal an alle senden
        for agent_id, agent in self._agents.items():
            await agent.stop()

        # 2. Auf Beendigung warten (mit Timeout)
        if self._tasks:
            done, pending = await asyncio.wait(
                self._tasks.values(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )

            # 3. Hartnäckige Tasks canceln
            for task in pending:
                task.cancel()

        # 4. teardown() für alle aufrufen
        for agent_id, agent in self._agents.items():
            try:
                await agent.teardown()
            except Exception as e:
                logger.warning(f"{agent_id}: teardown() Fehler: {e}")

        logger.info("Alle Agenten gestoppt.")
        self._shutdown_event.set()

    async def restart_agent(self, agent_id: str) -> bool:
        """
        Startet einen einzelnen Agent neu.
        Wird vom API-Container via Redis-Kommando ausgelöst.
        """
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]
        
        # Alten Task stoppen
        await agent.stop()
        if agent_id in self._tasks:
            task = self._tasks[agent_id]
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()

        # Cleanup
        try:
            await agent.teardown()
        except Exception:
            pass

        # Re-Setup + Neustart
        try:
            await agent.setup()
            new_task = asyncio.create_task(
                self._supervised_run(agent_id, agent),
                name=f"agent-{agent_id}"
            )
            self._tasks[agent_id] = new_task
            logger.info(f"{agent_id}: Neustart erfolgreich")
            return True
        except Exception as e:
            logger.error(f"{agent_id}: Neustart fehlgeschlagen: {e}")
            return False

    async def listen_for_commands(self) -> None:
        """
        Lauscht auf Redis-Channel 'worker:commands' für Befehle vom API-Container.
        
        Unterstützte Kommandos:
        - {"command": "restart", "agent_id": "quant"}
        - {"command": "stop", "agent_id": "risk"}
        - {"command": "shutdown"}
        """
        import json
        
        pubsub = await self.deps.redis.subscribe_channel("worker:commands")
        if not pubsub:
            logger.warning("Konnte worker:commands nicht subscriben")
            return

        while not self._shutdown_event.is_set():
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message['type'] == 'message':
                    cmd = json.loads(message['data'])
                    command = cmd.get("command")
                    agent_id = cmd.get("agent_id")

                    if command == "restart" and agent_id:
                        await self.restart_agent(agent_id)
                    elif command == "stop" and agent_id:
                        agent = self._agents.get(agent_id)
                        if agent:
                            await agent.stop()
                    elif command == "shutdown":
                        await self.stop_all()
            except Exception as e:
                logger.error(f"Command-Listener Fehler: {e}")
                await asyncio.sleep(1)

    async def wait_for_shutdown(self) -> None:
        """Blockt bis ein Shutdown-Signal kommt."""
        await self._shutdown_event.wait()
```

### Warum der Orchestrator setup() aufruft (und nicht der Agent selbst)

Im alten Plan war `setup()` optional und wurde intern in `run()` aufgerufen:

```python
# ALT (Status.md Plan):
async def run(self):
    try:
        await self.setup()  # ← Agent ruft sich selbst auf
    except Exception:
        return  # ← Und verschwindet still

# NEU:
# Orchestrator ruft setup() auf → weiß ob es geklappt hat → startet run() nur bei Erfolg
await asyncio.wait_for(agent.setup(), timeout=30.0)  # ← Mit Timeout!
task = asyncio.create_task(agent.run())
```

Der Unterschied: Der Orchestrator **weiß**, ob ein Agent bereit ist. Er kann entscheiden: "Ingestion Agent hat kein Setup geschafft — stoppe den kompletten Worker" vs. "Sentiment Agent konnte Ollama nicht erreichen — starte trotzdem den Rest".

---

## 7. Worker-Entrypoint

```python
# backend/app/worker.py
"""
Bruno Agent Worker — Separater Container für alle Trading-Agenten.

Gestartet via: python -m app.worker
Docker Command: python -m app.worker

Dieser Prozess:
1. Wartet auf Infrastruktur (Redis, DB)
2. Erstellt AgentDependencies
3. Registriert alle Agenten
4. Startet Agenten in Pipeline-Reihenfolge
5. Lauscht auf Kommandos vom API-Container
"""

import asyncio
import signal
import sys
import logging
from app.core.redis_client import RedisClient
from app.core.database import AsyncSessionLocal, init_db
from app.core.llm_client import OllamaClient
from app.core.config import settings
from app.agents.deps import AgentDependencies
from app.agents.orchestrator import AgentOrchestrator

# Agent-Importe
from app.agents.ingestion import IngestionAgentV2
from app.agents.quant import QuantAgentV2
from app.agents.sentiment import SentimentAgentV2
from app.agents.risk import RiskAgentV2
from app.agents.execution_v3 import ExecutionAgentV3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("worker")


async def wait_for_redis(redis: RedisClient, max_attempts: int = 30) -> None:
    """Wartet bis Redis erreichbar ist (max 5 Minuten)."""
    for attempt in range(1, max_attempts + 1):
        try:
            await redis.connect()
            logger.info(f"Redis verbunden (Versuch {attempt})")
            return
        except Exception as e:
            logger.warning(f"Redis nicht bereit (Versuch {attempt}/{max_attempts}): {e}")
            await asyncio.sleep(10)
    
    logger.critical("Redis nicht erreichbar nach 5 Minuten. Worker beendet.")
    sys.exit(1)


async def wait_for_db(max_attempts: int = 30) -> None:
    """Wartet bis PostgreSQL erreichbar ist."""
    for attempt in range(1, max_attempts + 1):
        try:
            await init_db()
            logger.info(f"Datenbank verbunden (Versuch {attempt})")
            return
        except Exception as e:
            logger.warning(f"DB nicht bereit (Versuch {attempt}/{max_attempts}): {e}")
            await asyncio.sleep(10)
    
    logger.critical("Datenbank nicht erreichbar nach 5 Minuten. Worker beendet.")
    sys.exit(1)


async def main():
    logger.info("=" * 60)
    logger.info("Bruno Worker startet...")
    logger.info("=" * 60)

    # ===== 1. Infrastruktur prüfen =====
    redis = RedisClient()
    ollama = OllamaClient()

    await wait_for_redis(redis)
    await wait_for_db()
    
    # Ollama ist OPTIONAL (Sentiment Agent hat Fallback)
    ollama_ok = await ollama.health_check()
    logger.info(f"Ollama: {'✅ erreichbar' if ollama_ok else '⚠️ nicht erreichbar (Fallback aktiv)'}")

    # ===== 2. Dependencies zusammenbauen =====
    deps = AgentDependencies(
        redis=redis,
        config=settings,
        db_session_factory=AsyncSessionLocal,
        ollama=ollama
    )

    # ===== 3. Orchestrator aufsetzen =====
    orchestrator = AgentOrchestrator(deps)

    # ===== 4. Agenten registrieren =====
    orchestrator.register("ingestion", IngestionAgentV2(deps))
    orchestrator.register("quant", QuantAgentV2(deps, symbol="BTC/USDT"))
    orchestrator.register("sentiment", SentimentAgentV2(deps))
    orchestrator.register("risk", RiskAgentV2(deps))
    orchestrator.register("execution", ExecutionAgentV3(deps))

    # ===== 5. Starten in Pipeline-Reihenfolge =====
    await orchestrator.start_all()

    # ===== 6. Command-Listener starten =====
    cmd_task = asyncio.create_task(orchestrator.listen_for_commands())

    # ===== 7. Auf Shutdown warten =====
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.stop_all()))
        except NotImplementedError:
            pass  # Windows hat kein add_signal_handler

    await orchestrator.wait_for_shutdown()

    # ===== 8. Cleanup =====
    cmd_task.cancel()
    await ollama.close()
    await redis.disconnect()
    logger.info("Worker beendet.")


if __name__ == "__main__":
    asyncio.run(main())
```

### Docker-Compose Erweiterung

```yaml
# docker-compose.yml — Neuer Service:
  bruno-worker:
    build:
      context: ./backend
      dockerfile: ../docker/Dockerfile.backend
    container_name: bruno-worker
    command: python -m app.worker
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DB_HOST=${DB_HOST:-postgres}
      - DB_PORT=${DB_PORT:-5432}
      - DB_USER=${DB_USER:-bruno}
      - DB_PASS=${DB_PASS:-bruno_secret}
      - DB_NAME=${DB_NAME:-bruno_trading}
      - REDIS_HOST=${REDIS_HOST:-redis}
      - REDIS_PORT=${REDIS_PORT:-6379}
    volumes:
      - ./backend:/app
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"
```

**Gleichzeitig** muss aus `bruno-api` (das bestehende `api-backend`) die gesamte Agent-Logik entfernt werden. `main.py` wird zum reinen API-Server reduziert:

```python
# main.py — NACH Refactoring:
# KEINE agent-imports mehr
# KEIN agent_instances dict
# KEIN asyncio.create_task(agent.start())
# Nur: FastAPI, Routers, Health-Check
```

---

## 8. Message Contracts

> **Alle Inter-Agent-Kommunikation folgt strikten Pydantic-Schemas.**
> Keine losen JSON-Strings, keine `dict`-Typen ohne Schema.

```python
# backend/app/core/contracts.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
import uuid


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalEnvelope(BaseModel):
    """Standard-Hülle für JEDES Signal im System."""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    version: str = "2.0"
    timestamp: datetime
    symbol: str


class QuantSignalV2(SignalEnvelope):
    """Quant Agent → Risk Agent"""
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    indicators: Dict[str, float]  # {"rsi_1m": 28.5, "macd_hist": 0.003, ...}
    timeframe: str = "1m"
    reasoning: str  # "RSI oversold + MACD bullish cross"


class SentimentSignalV2(SignalEnvelope):
    """Sentiment Agent → Risk Agent"""
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=-1.0, le=1.0)
    sources: List[str]  # ["CryptoPanic", "RSS:coindesk"]
    reasoning: str
    article_count: int


class RiskDecision(SignalEnvelope):
    """Risk Agent → Execution Agent"""
    action: SignalDirection
    approved: bool
    position_size_usd: float
    stop_loss_price: float
    take_profit_price: float
    risk_reward_ratio: float
    reasoning: str
    # Eingangssignale (für Transparenz)
    quant_signal: Optional[QuantSignalV2] = None
    sentiment_signal: Optional[SentimentSignalV2] = None


class TradeExecution(SignalEnvelope):
    """Execution Agent → Dashboard/Telegram"""
    action: str  # "BUY" / "SELL"
    entry_price: float
    quantity: float
    position_size_usd: float
    stop_loss: float
    take_profit: float
    risk_decision: RiskDecision
    execution_status: str  # "FILLED" / "FAILED" / "PAPER"
    order_id: Optional[str] = None
```

### Migration der alten Schemas

| Alt (`schemas/agents.py`) | Neu (`core/contracts.py`) | Änderungen |
|---|---|---|
| `QuantSignal.signal: int` | `QuantSignalV2.direction: SignalDirection` | Enum statt int |
| `QuantSignal.timestamp: str` | `QuantSignalV2.timestamp: datetime` | Richtiger Typ |
| — | `QuantSignalV2.correlation_id` | **NEU** — Tracing |
| — | `QuantSignalV2.reasoning` | **NEU** — Transparenz |
| `SentimentSignal.reasoning: str` | `SentimentSignalV2.reasoning: str` | Beibehalten |
| `ExecutionOrder` | `RiskDecision` + `TradeExecution` | **Aufgespalten** |

---

## 9. Redis Channel-Architektur (Standardisiert)

| Channel | Publisher | Subscriber | Payload | Typ |
|---|---|---|---|---|
| `bruno:pubsub:signals` | Quant | Execution | `TradeSignal` | Pub/Sub |
| `bruno:pubsub:veto` | Risk | Execution | `VetoState` | Pub/Sub |
| `bruno:context:grss` | Context | Risk | `MacroContext` | Pub/Sub |
| `bruno:quant:micro` | Quant | Risk | `HFTMetrics` | Pub/Sub |
| `bruno:veto:state` | Risk | - | Veto RAM-Cache | Cache |
| `heartbeat:{agent_id}` | Alle Agenten | Dashboard, API | Heartbeat JSON | Cache (TTL 60s) |
| `alerts:agent_error` | BaseAgent | Dashboard, Telegram | Error Details | Pub/Sub |
| `worker:commands` | API | Worker | Restart/Stop/Shutdown | Pub/Sub |
| `logs:live` | LogManager | Dashboard | Log Entries | Pub/Sub |

### Wichtig: Pub/Sub vs. Stream

- **Pub/Sub** für Signale, Entscheidungen, Alerts: Wird nur in Echtzeit konsumiert, keine Historie nötig.
- **Stream (XADD)** für Ticks: Kann mit `XRANGE` abgefragt werden, hat ID-basierte Consumer-Groups für spätere Erweiterung.
- **Cache (SET mit TTL)** für Heartbeats: Einfachster Mechanismus — wenn der Key expired, ist der Agent tot.

---

## 10. Agent-Spezifikationen (Phase C/D - Zero Latency)

### Ingestion Agent
- **Basisklasse:** `StreamingAgent`
- **Ziel:** Stabile Echtzeit-Datenversorgung (Multi-Stream).
- **Daten-Target:** Redis Stream + TimescaleDB Hypertables.

### Quant Agent (HFT Engine)
- **Basisklasse:** `PollingAgent` (Interval: 300s)
- **Ziel:** Mikro-Struktur-Signale basierend auf OFI, VAMP und CVD.
- **Security:** Nutzt `PublicExchangeClient` (keine Keys erforderlich).
- **LLM:** Ruft die Phase-C-LLM-Kaskade auf und publiziert nur actionable Signale.
- **Output:** Publiziert an `bruno:pubsub:signals`.

### Sentiment Agent
- **Basisklasse:** `PollingAgent` (Interval: 300s)
- **Ziel:** Makro-Bias & News-Sentiment Analysis via Ollama.
- **Output:** Publiziert an `bruno:context:grss`.

### Risk AgentV2 (Veto Guard)
- **Basisklasse:** `PollingAgent` (Interval: 2.0s)
- **Ziel:** Hard-Veto Matrix & Konsolidierung aller Signale.
- **Latenz:** Direkte Redis-Calls (`set`, `publish`) für minimale Verzögerung.
- **Output:** Publiziert an `bruno:pubsub:veto`.

### Execution AgentV3 (Zero-Latency Core)
- **Basisklasse:** `StreamingAgent`
- **RAM-Cache:** Spiegelt den Veto-State im lokalen RAM (0ms Latenz).
- **Latency-Check:** Bei Signal-Eingang erfolgt ein sofortiger RAM-Check.
- **Security:** Einziger Agent mit `AuthenticatedExchangeClient` (API-Keys).
- **Execution:** 0ms RAM-Check → Order Fire → `PositionTracker.open_position()` → Async Audit.
- **Phase D:** Schließt Positionen über `PositionTracker.close_position()` und überwacht SL/TP im Monitor-Loop.


---

## 11. Status-Monitoring & Heartbeat

### Wie das Frontend Agent-Status abfragt

**Aktuell**: Heartbeats werden von `BaseAgent._send_heartbeat()` in Redis geschrieben (`heartbeat:<agent_id>`). Das Runtime-Tracking läuft über Worker + Orchestrator, nicht über `app.main`.

**Frontend/Status-API**: Der Status-Endpoint liest die Heartbeat-Keys direkt aus Redis und zeigt damit den realen Worker-Zustand an:

```python
# routers/agents_status.py — heartbeat-basiert

@router.get("/status")
async def get_agents_status():
    """Liest Heartbeat-Keys aus Redis. TTL-basiert: Kein Heartbeat = tot."""
    agent_ids = ["ingestion", "quant", "sentiment", "risk", "execution"]
    agents = []
    
    for agent_id in agent_ids:
        heartbeat = await redis_client.get_cache(f"heartbeat:{agent_id}")
        if heartbeat:
            agents.append({
                **heartbeat,
                "status": heartbeat.get("status", "unknown")
            })
        else:
            # Key expired → Agent ist tot oder nie gestartet
            agents.append({
                "agent_id": agent_id,
                "status": "dead",
                "uptime_seconds": 0,
                "processed_count": 0,
                "error_count": 0
            })
    
    running = [a for a in agents if a["status"] == "running"]
    return {
        "agents": agents,
        "total_agents": len(agents),
        "running_agents": len(running),
        "last_check": datetime.now(timezone.utc).isoformat()
    }
```

**Vorteil:** Kein `from app.main import` Hack. Der API-Container muss nichts über den Worker-Container wissen außer die Redis-Keys. Funktioniert auch über Container-Grenzen hinweg.

### Agent-Restart via API

```python
@router.post("/restart/{agent_id}")
async def restart_agent(agent_id: str):
    """Sendet Restart-Kommando an Worker via Redis."""
    await redis_client.publish_message(
        "worker:commands",
        json.dumps({"command": "restart", "agent_id": agent_id})
    )
    return {"status": "sent", "message": f"Restart-Kommando für {agent_id} gesendet"}
```

Kein `TODO` mehr — das funktioniert über Redis Pub/Sub zum Worker-Container.

---

## 12. Dateisystem-Übersicht (Aktueller Stand)

```
backend/
├── app/
│   ├── main.py                 # FastAPI API + Router inkl. Phase C/D Monitoring
│   ├── worker.py               # Agent Orchestrator Entrypoint
│   │
│   ├── agents/
│   │   ├── base.py             # BaseAgent, PollingAgent, StreamingAgent
│   │   ├── deps.py             # AgentDependencies
│   │   ├── orchestrator.py     # AgentOrchestrator
│   │   ├── quant.py            # QuantAgent mit LLM Cascade
│   │   ├── execution_v3.py     # ExecutionAgentV3 mit PositionTracker
│   │   ├── risk.py             # Veto / Guard Agent
│   │   └── ...
│   │
│   ├── llm/
│   │   └── llm_cascade.py      # 3-Layer Cascade + Provider-Abstraktion
│   │
│   ├── services/
│   │   ├── regime_config_v2.py # RegimeManager + Transition Buffer
│   │   ├── position_tracker.py # Redis Live-State + DB Audit Trail
│   │   └── position_monitor.py # SL/TP Monitoring
│   │
│   ├── routers/
│   │   ├── llm_cascade.py      # Monitoring / Debugging
│   │   ├── positions.py        # Positions API
│   │   └── ...                 # Rest unverändert
│   │
│   └── schemas/
│       └── models.py           # DB-Models
│
├── docker-compose.yml          # api + worker + db + redis
└── docker/
    └── Dockerfile.backend      # Gleiche Codebase, anderer Command
```

---

## 13. Implementierungsreihenfolge

> **Die Reihenfolge ist entscheidend.** Jeder Schritt baut auf dem vorherigen auf.

### Aktueller Betriebsstand
- [x] `worker.py` startet die Agenten im Orchestrator
- [x] `quant.py` publiziert LLM-angereicherte Signale
- [x] `execution_v3.py` schließt/opened Positionen über `PositionTracker`
- [x] `positions.py` bietet Monitoring / Status / History
- [x] `llm_cascade.py` ist in die Runtime eingebunden
- [ ] SL/TP End-to-End live validieren
- [ ] Dashboard-Ansichten für Positions- und Cascade-Metriken finalisieren

---

## 14. Verifizierung

### Automatische Tests

```bash
# Unit-Tests (ohne Docker)
pytest tests/agents/test_base.py          # BaseAgent, PollingAgent, StreamingAgent
pytest tests/agents/test_orchestrator.py  # Startup-Sequenz, Crash-Recovery
pytest tests/agents/test_quant.py         # RSI-Berechnung, Signal-Erzeugung

# Integration-Tests (mit Docker)
docker compose up -d postgres redis
pytest tests/integration/test_agent_pipeline.py  # Signal von Quant → Risk → Execution
```

### Manuelle Verifizierung

```
1. docker compose up -d
2. Logs prüfen:
   docker logs bruno-worker -f
   → Erwartete Ausgabe:
   === Starte Stufe 1: ['ingestion'] ===
     ✅ ingestion: setup() erfolgreich
   === Starte Stufe 2: ['quant', 'sentiment'] ===
     ✅ quant: setup() erfolgreich
     ✅ sentiment: setup() erfolgreich
   === Starte Stufe 3: ['risk'] ===
     ✅ risk: setup() erfolgreich
   === Starte Stufe 4: ['execution'] ===
     ✅ execution: setup() erfolgreich
   === Alle Stufen abgeschlossen. 5 Agenten laufen. ===

3. Heartbeats prüfen:
   docker exec bruno-redis redis-cli GET heartbeat:quant
   → JSON mit status, uptime, processed_count

4. Agent-Restart testen:
   Invoke-RestMethod -Method POST http://localhost:8000/api/v1/agents/restart/quant
   → Worker-Logs zeigen Restart

5. Crash-Recovery testen:
   docker exec bruno-worker kill -USR1 <agent-pid>  # Simuliert Crash
   → Worker-Logs zeigen Neustart nach Backoff
```

---

## Performance-Ziele

### 🎯 Phase 4.2 Live Performance (2026-03-26)

| Metrik | Wert | Status |
|--------|------|--------|
| **BTC/USDT Live Preis** | 68,975 USD | ✅ AKTIV |
| **Dashboard Refresh** | 5 Sekunden | ✅ AKTIV |
| **RSS News Feed** | Cointelegraph + Coindesk | ✅ AKTIV |
| **Sentiment Analyse** | Keyword-basiert | ✅ AKTIV |
| **Agenten Pipeline** | 5/5 Running | ✅ AKTIV |
| **Redis Ticker** | market:ticker:BTCUSDT | ✅ AKTIV |
| **WebSocket Stream** | Orderbook + Ticker | ✅ AKTIV |

### 📊 Live Daten Flow
```
Binance WebSocket → Ingestion Agent → Redis Ticker → Frontend Dashboard
RSS Feeds → Sentiment Agent → Keyword Analyse → Redis Signals → Risk Agent
PostgreSQL ← MarketCandle ← Ingestion Agent ← Binance K-Lines
```

### 🚀 System Status
- **Frontend:** Dashboard mit Live-Preis und Charts
- **Backend:** API mit WebSocket Streaming
- **Worker:** Multi-Agenten-Pipeline aktiv
- **Datenbank:** PostgreSQL + Redis mit Live-Daten
- **News:** Echte RSS-Feeds (keine Mocks)

---

*Letzte Aktualisierung: 2026-03-26 - Phase 4.2 Vollständig Implementiert - Live Marktdaten & RSS News Integration*

