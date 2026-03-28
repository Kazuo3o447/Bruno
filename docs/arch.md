# Architektur-Manifest

> **Referenz: WINDSURF_MANIFEST.md v2.0**
> 
> ⚠️ **Aktuell:** Entwicklung auf **Windows** (Windsurf/SWE-1.5)
> 🐧 **Ziel:** Produktion auf **Linux NUC** (ZimaOS) nach Stabilisierung

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Infrastruktur-Stack

### Umgebungen

| Umgebung | Hardware | Zweck |
|----------|----------|-------|
| **Entwicklung** | Windows + Ryzen 7 7800X3D + RX 7900 XT | Agenten-Entwicklung, LLM-Inferenz |
| **Produktion** | Linux NUC + ZimaOS | Live-Trading (nach Stabilisierung) |

### Docker Services (WSL2 / Linux)

> 🔧 **Während des Bauens:** Docker Desktop auf Windows (WSL2-Backend)
> 🐧 **Produktion:** Docker auf Linux NUC (ZimaOS)

| Service | Technologie | Zweck |
|---------|-------------|-------|
| **PostgreSQL** | TimescaleDB + pgvector | Zeitserien-Daten, Positionen, Trades |
| **Redis** | Redis Stack | Caching, Pub/Sub, State-Management |
| **FastAPI** | Python ASGI | Backend API, Agenten-Orchestration |
| **Frontend** | Next.js + React | Trading Cockpit |

---

## Die LLM-Brücke

### Native Windows-Ollama (Dev)
- **Ollama läuft NATIV auf dem Windows-Host** (Ryzen 7 7800X3D + RX 7900 XT)
- Direkter Zugriff auf **AMD RX 7900 XT GPU**
- Keine Docker-Passthrough-Komplexität
- Keine WSL2-Kompilierungsprobleme

**Modelle:**
- **qwen2.5:14b** - Primary (Klassifizierung, Gate-Checks)
- **deepseek-r1:14b** - Reasoning (Strategische Analyse)

### Docker-Kommunikation
Container greifen auf Ollama zu via:
```
http://host.docker.internal:11434
```

---

## Börsen-Architektur (Manifest v2.0)

```
Binance WS/REST  ──► IngestionAgent + ContextAgent ──► Redis
                                                           │
                                                      alle Agenten
                                                           │
Bybit REST  ◄── ExecutionAgent ◄── RiskAgent (RAM-Veto) ◄─┘
```

| Börse | Nutzung | Daten |
|-------|---------|-------|
| **Binance** | Daten & Analyse | WebSocket (5 Streams), REST (OI, Funding, Perp-Basis) |
| **Bybit** | **Execution** | Unified Account Futures (max 1.5× Leverage) |
| **Deribit** | Options-Daten | Put/Call Ratio, DVOL (kostenlos, kein Key) |

**Bybit Order-Format:**
```python
{
    "category": "linear",
    "symbol": "BTCUSDT",
    "side": "Buy",
    "orderType": "Limit",
    "qty": "0.001",          # Minimum
    "price": "84500",
    "timeInForce": "PostOnly"  # Maker-Fee 0.01%
}
```

---

## Die 6-Agenten-Kaskade

| Agent | Input | Output | Zweck |
|-------|-------|--------|-------|
| **Ingestion** | Binance WebSocket (5 Streams) | Redis Streams | OHLCV, OFI, Liquidations, Funding |
| **Context** | Makro-Daten (FRED, Deribit, RSS) | Redis `bruno:context:grss` | **GRSS Score** (0–100) |
| **Sentiment** | RSS Feeds + CryptoPanic | Redis `bruno:sentiment` | LLM-basierte News-Analyse |
| **Quant** | Redis + Orderbook | Redis `bruno:signals` | OFI, CVD, technische Signale |
| **Risk** | Alle Signals (RAM-Check) | Redis `bruno:veto` | **0ms Veto** (GRSS < 40 = Block) |
| **Execution** | Risk + Signals | **Bybit API** | **Limit/PostOnly Orders** |

---

## Sicherheits-Isolation

### API-Key Isolation
- **PublicExchangeClient** (Quant/Context): Keine Keys nötig (Binance Public)
- **AuthenticatedExchangeClient** (Execution): Nur Bybit API-Keys

### DRY_RUN Protection
- Hardware-naher Block in ExecutionAgent
- Bei `DRY_RUN=True`: Keine echten Orders möglich
- Shadow-Trading mit Fee-Simulation (0.01% Maker)

---

## Datenbank-Schema (Neue Migrationen)

### Migration 005: Positions
```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY, symbol VARCHAR(20), side VARCHAR(10),
    entry_price FLOAT, quantity FLOAT, stop_loss_price FLOAT,
    take_profit_price FLOAT, exit_price FLOAT, exit_reason VARCHAR(50),
    pnl_pct FLOAT, status VARCHAR(10)
);
```

### Migration 006: LLM Reasoning Trail
```sql
ALTER TABLE trade_audit_logs
ADD COLUMN llm_reasoning JSONB,
ADD COLUMN regime VARCHAR(20),
ADD COLUMN layer1_output JSONB,
ADD COLUMN layer2_output JSONB,
ADD COLUMN layer3_output JSONB;
```

---

## System-Status

### Phase A — Fundament (Woche 1–2) — AKTIV
- [ ] ContextAgent: `random.uniform()` entfernen
- [ ] Binance REST: OI, OI-Delta, L/S-Ratio, Perp-Basis
- [ ] Deribit Public: Put/Call Ratio, DVOL
- [ ] GRSS-Funktion: echte Daten (Manifest Abschnitt 5)

### Geplant: Phasen B–H
Siehe WINDSURF_MANIFEST.md Abschnitt 13

---

*Referenz: WINDSURF_MANIFEST.md v2.0 — Einzige Quelle der Wahrheit*
