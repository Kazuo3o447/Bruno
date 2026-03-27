# Architektur-Manifest

> **Windows-Hybrid-Plattform für asynchronen Multi-Agenten Trading**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Infrastruktur-Stack

### Docker Desktop (WSL2)
Alle Container-Services laufen in Docker Desktop mit WSL2-Backend:

| Service | Technologie | Zweck |
|---------|-------------|-------|
| **PostgreSQL** | TimescaleDB + pgvector | Zeitserien-Daten, Vektor-Embeddings |
| **Redis** | Redis Stack | Caching, Pub/Sub, Message Queue |
| **FastAPI** | Python ASGI | Backend API, Agenten-Endpoints |
| **Frontend** | Next.js + React | "Bruno" - Trading Dashboard |

---

## Die LLM-Brücke

### Native Windows-Ollama
- **Ollama läuft NATIV auf dem Windows-Host**
- Direkter Zugriff auf **AMD RX 7900 XT GPU**
- Keine Docker-Passthrough-Komplexität
- Keine WSL2-Kompilierungsprobleme

### Docker-Kommunikation
Container greifen auf Ollama zu via:
```
http://host.docker.internal:11434
```

**Vorteile dieser Architektur:**
- Minimale Latenz durch nativen GPU-Zugriff
- Keine ROCm/WSL2-Kompatibilitätsprobleme
- Einfache Skalierung der Container unabhängig vom LLM

---

## Datenfluss-Architektur

### 1. Echtzeit-Datenstrom
```
Binance/CryptoPanic WebSocket (ccxt)
            ↓
      Redis Pub/Sub
            ↓
    Agenten (Python)
            ↓
   TimescaleDB (Aggregation)
```

### 2. Kommunikations-Pfade
- **Redis Streams**: High-Frequency Trading-Daten
- **Redis Pub/Sub**: Agenten-Kommunikation
- **PostgreSQL**: Persistente Marktdaten, Trades, Logs
- **FastAPI WebSocket**: Frontend-Updates

| Agent | Input | Output | Zweck |
|-------|-------|--------|-------|
| **Ingestion** | WebSocket & RSS APIs | Redis Streams | Rohdaten-Aggregation & Normalisierung |
| **Context** | 8 RSS Feeds + GDELT + Makro | Redis `bruno:context:grss` | **Makro-Bias**: GRSS Score, Geopolitik & Sentiment |
| **Quant** | Redis + PublicExchange | Redis `bruno:pubsub:signals` | **HFT-Signale**: OFI/CVD Mikro-Struktur Signale |
| **Risk** | Alle Agent-Signals | Redis `bruno:pubsub:veto` | **0ms Veto-Matrix**: Hard-Veto RAM-State |
| **Execution** | Risk (RAM) + Signals | Exchange APIs | **Zero-Latency Core**: Direkte Order-Ausführung |

---

## Die Multi-Agenten-Kaskade (Phase 7.5 - Shadow Trading & MLOps)

Das System nutzt eine dreistufige Entscheidungs-Kaskade zur Absicherung institutioneller Qualität:

1. **ContextAgent (Strategischer Bias)**: Analysiert das "Warum". Berechnet den **Global Risk Sentiment Score (GRSS)**.
2. **QuantAgent (Taktisches Signal)**: Analysiert die "Wahrheit". Generiert HFT-Signale basierend auf Mikro-Struktur (OFI/CVD).
3. **ExecutionAgent (Ausführer)**: Reagiert in Millisekunden. Nutzt einen **0ms RAM-Veto-Check**. Bei aktivem `DRY_RUN` wird ein Shadow-Trade mit exakter Gebühren-Simulation (0.04% Taker-Fee) durchgeführt.

---

## MLOps & Telemetry Monitoring

### 1. Das Cockpit (Next.js)
Ein dediziertes Monitoring-Dashboard bietet native Visualisierungen ohne iFrames:
- **Live-Telemetrie**: Execution-Latenz und Risk-Veto Status in Echtzeit.
- **Slippage-Analyse**: Scatter-Plots vergleichen Signal-Preis mit Fill-Preis.
- **Veto-Distribution**: Analyse der Blockade-Gründe des Risk-Agents.

### 2. Parameter Hub (Strict MLOps)
Vergleich von produktiven (`config.json`) und optimierten (`optimized_params.json`) Parametern. 
- **Eiserne Regel**: Das Dashboard ist **Read-Only**. Parameter-Updates erfolgen ausschließlich offline über Code-Commits/Neustarts zum Schutz vor Manipulation.

---

## Sicherheits-Isolation (Trading Keys)

Um die Sicherheit der Plattform zu gewährleisten, sind die Trading-Keys (BINANCE_SECRET) strikt isoliert:

- **PublicExchangeClient**: Wird von Quant- und Context-Agenten genutzt. Erfordert keine API-Keys.
- **AuthenticatedExchangeClient**: Exklusiv für den ExecutionAgent. Nur dieser Client lädt die API-Keys.
- **DRY_RUN Protection**: Ein hardware-naher Software-Block in der Execution-Engine verhindert physische Orders, wenn die Simulation aktiv ist.

---

## Technische Spezifikationen

### Datenbank-Schema (Phase 7.5 Audit)
| Tabelle | Feld | Zweck |
|---------|------|-------|
| `trade_audit_logs` | `simulated_fee_usdt` | Exakte Simulation der 0.04% Taker-Fee |
| `trade_audit_logs` | `slippage_bps` | Slippage-Erfassung in Basis-Punkten |
| `trade_audit_logs` | `latency_ms` | Zeit vom Signal bis zum Fill |

---

## System-Status

### ✅ Phase 7.5 Abgeschlossen - MLOps & Shadow Trading
| Komponente | Status | Details |
|------------|--------|---------|
| **Execution Engine** | ✅ High-Perf | Lokaler RAM-Check, 0ms Veto-Latenz, Shadow-Modus |
| **Slippage Audit** | ✅ Exakt | 0.04% Fee-Simulation & BPS-Tracking |
| **Monitoring Hub** | ✅ Dashboard | Native Recharts-Integration, Read-Only MLOps |
| **Offline Optimizer**| ✅ PF > 1.5 | Strenges Profit-Factor-Enforcement |

---

*Letzte Aktualisierung: 2026-03-27 - Phase 7.5 MLOps & Telemetry Integration abgeschlossen*
