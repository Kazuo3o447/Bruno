# KI- & Agenten-Verzeichnis

> **Das "Gehirn" des Trading-Bots**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Lokale LLM-Infrastruktur

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

### Warum "Hidden Champions"?
- **Effizienz**: 14B-Modelle laufen flüssig auf RX 7900 XT
- **Latenz**: Unter 500ms für Standard-Inferenz
- **Qualität**: Vergleichbar mit großen Cloud-LLMs für Trading-Tasks
- **Kosten**: Keine API-Gebühren, volle Datenkontrolle

---

## Die 5 Kern-Agenten

### 1. Ingestion Agent
| Eigenschaft | Beschreibung |
|-------------|--------------|
| **Typ** | WebSocket-Sammler |
| **Input** | Binance WebSocket, CryptoPanic API |
| **Output** | Redis Streams (Raw Data) |
| **Technologie** | CCXT, WebSocket-Client, AsyncIO |
| **Aufgabe** | Echtzeit-Marktdaten sammeln, normalisieren, weiterleiten |

### 2. Quant Agent
| Eigenschaft | Beschreibung |
|-------------|--------------|
| **Typ** | Technischer/Mathematischer Analytiker |
| **Input** | Redis Streams, TimescaleDB (historisch) |
| **Output** | Trading-Signals (BUY/SELL/HOLD) + Confidence |
| **Technologie** | Pandas, NumPy, TA-Lib, Prophet |
| **Aufgabe** | Momentum, Volatilität, technische Indikatoren berechnen |

### 3. Sentiment Agent
| Eigenschaft | Beschreibung |
|-------------|--------------|
| **Typ** | News-Analyst |
| **Input** | RSS-Feeds, CryptoPanic, Reddit, LLM-Embeddings |
| **Output** | Sentiment-Score (-1 bis +1) |
| **Technologie** | Ollama-API, pgvector, NLP |
| **Aufgabe** | Marktstimmung analysieren, Fear/Greed quantifizieren |

### 4. Risk & Consensus Agent
| Eigenschaft | Beschreibung |
|-------------|--------------|
| **Typ** | Veto- und Konfluenz-Instanz |
| **Input** | Alle Agent-Signals, Position-Data, Risk-Metriken |
| **Output** | Final Approval + Position-Size |
| **Technologie** | Regelbasiert + ML-Klassifikator |
| **Aufgabe** | Konfliktauflösung, Risk-Management, Final-Check |
| **Regeln** | Stop-Loss, Take-Profit, Max-Position-Size |

### 5. Execution Agent
| Eigenschaft | Beschreibung |
|-------------|--------------|
| **Typ** | Order-Router |
| **Input** | Risk-Approved Signals |
| **Output** | Binance API Orders |
| **Technologie** | CCXT, AsyncIO, Retry-Logic |
| **Aufgabe** | Order-Platzierung, Status-Tracking, Fehlerbehandlung |
| **Modi** | Paper-Trading, Live-Trading (geschaltet) |

---

## Agenten-Kommunikationsprotokoll

### Nachrichten-Schema (Redis)
```json
{
  "agent_id": "quant_01",
  "timestamp": 1712345678,
  "signal": "BUY",
  "symbol": "BTC/USDT",
  "confidence": 0.85,
  "metadata": {
    "indicators": ["RSI", "MACD"],
    "timeframe": "1m"
  }
}
```

### Kanäle
| Kanal | Zweck |
|-------|-------|
| `raw:data` | Ingestion → Alle |
| `signals:quant` | Quant → Risk |
| `signals:sentiment` | Sentiment → Risk |
| `consensus:final` | Risk → Execution |
| `executed:orders` | Execution → Alle (Feedback) |

---

## LLM-Prompting-Strategien

### Sentiment-Analyse Prompt
```
Analysiere folgende Crypto-News auf Bullish/Bearish-Sentiment:
{news_text}

Gib zurück:
- Sentiment-Score (-1.0 bis +1.0)
- Confidence (0.0 bis 1.0)
- Kurze Begründung (max 50 Wörter)
```

### Strategische Analyse (DeepSeek-R1)
```
Gegeben: BTC-Preisaktion, Orderbook-Daten, Sentiment-Score.
Task: Identifiziere Hochwahrscheinlichkeit-Setups für Scalping.
Denke Schritt-für-Schritt:
1. Marktstruktur analysieren
2. Key Levels identifizieren
3. Entry/Exit-Logik ableiten
4. Risk/Ratio berechnen
```

---

## Backend Integration

### LLM Client Wrapper
Der `OllamaClient` in `backend/app/core/llm_client.py` implementiert:

| Methode | Zweck | Beispiel |
|---------|-------|----------|
| `generate_response()` | Single-Prompt | Sentiment-Analyse |
| `generate_chat()` | Konversations-Format | Multi-Turn Dialog |
| `analyze_sentiment()` | JSON-Output | `{"sentiment": 0.8, "confidence": 0.9}` |
| `trading_analysis()` | DeepSeek-R1 | Strategische Planung |

### Agenten-Kommunikation
| Channel | Format | Beispiel |
|---------|--------|---------|
| `signals:quant` | Redis Stream | `{"symbol": "BTC", "signal": "BUY", "confidence": 0.85}` |
| `signals:sentiment` | Redis Pub/Sub | `{"sentiment": 0.7, "source": "news"}` |
| `consensus:final` | WebSocket | `{"action": "EXECUTE", "size": 0.1}` |

### Prompt-Templates
```python
# Sentiment-Analyse
SENTIMENT_PROMPT = """
Analysiere folgenden Text auf Bullish/Bearish-Sentiment:
"{text}"

Gib zurück als JSON:
{
    "sentiment": -1.0 bis 1.0,
    "confidence": 0.0 bis 1.0,
    "reasoning": "kurze Begründung"
}
"""

# Trading-Analyse
TRADING_PROMPT = """
Gegeben:
- Markt-Daten: {market_data}
- Sentiment-Score: {sentiment_score}

Als Trading-Experte analysiere diese Situation und gib eine klare Empfehlung:
1. MARKT-AUSLAGE
2. ENTRY/EXIT-LOGIK
3. RISK/REWARD
4. FINALE ENTSCHEIDUNG: BUY/SELL/HOLD
"""
```

---

## Performance-Ziele

| Metrik | Ziel |
|--------|------|
| End-to-End Latenz | < 2 Sekunden (Signal → Order) |
| LLM-Inferenz | < 500ms (14B-Modelle) |
| Daten-Aktualität | < 100ms (WebSocket) |
| Agenten-Durchsatz | > 1000 Nachrichten/Sekunde |

---

## Implementierungs-Status

### ✅ Phase 2 & 3 Abgeschlossen - System Produktivbereit

| Komponente | Status | Implementierung |
|------------|--------|-----------------|
| **OllamaClient** | ✅ Implementiert | httpx async, qwen2.5/deepseek-r1 |
| **Redis Streams** | ✅ Implementiert | Singleton Pattern, Connection Pool |
| **Prompt Templates** | ✅ Implementiert | Sentiment, Trading-Analyse |
| **Agenten-Kommunikation** | ✅ Implementiert | Pub/Sub, WebSocket Channels |
| **Frontend Dashboard** | ✅ Implementiert | Next.js, Lightweight Charts, WebSocket Client |
| **Agenten-Monitor** | ✅ Implementiert | Echtzeit-Status aller Agenten |
| **Quant Agent** | ✅ Implementiert | RSI(14), NumPy, Warmup, Threading, Redis Pub/Sub |

## 🎯 Phase 4 Abgeschlossen - Vollständige Agenten-Implementierung

### ✅ Alle 5 Agenten Live & Trading (Paper)

| Agent | Status | Technologie | Live-Output |
|-------|--------|------------|-------------|
| **📡 Ingestion** | ✅ RUNNING | Binance WebSocket, Exponential Backoff | 42,451+ Live-Ticks |
| **📊 Quant** | ✅ RUNNING | NumPy RSI(14), AsyncIO Threading | BUY Signal (RSI: 18.85) |
| **🧠 Sentiment** | ✅ RUNNING | Ollama LLM, Fallback Logic | Neutral (Fallback) |
| **⚖️ Risk** | ✅ RUNNING | Konfluenz-Check, Redis Pub/Sub | Bereit für Validation |
| **💰 Execution** | ✅ RUNNING | AsyncSessionLocal, Paper-Trading | Bereit für Orders |

### 🔄 Live Trading Flow
```
Binance WebSocket → 42,451 Ticks → Quant Agent (RSI: 18.85) → BUY Signal → Risk Agent → Execution Agent → PostgreSQL
```

### 📊 System Performance (2026-03-26)
- **BTC/USDT Preis:** 68,912 USD
- **Quant Signal:** BUY (RSI: 18.85, Confidence: 0.37)
- **Sentiment:** Neutral (Fallback-Modus)
- **Ingestion:** 42,451+ Ticks verarbeitet
- **Datenbank:** 9 Tabellen aktiv
- **Redis:** Pub/Sub + Streams aktiv

### 🔧 Technische Implementierungen

#### **Ingestion Agent**
- **WebSocket:** `wss://fstream.binance.com/ws/btcusdt@aggTrade`
- **Backoff:** Exponential 1-60s bei Verbindungsproblemen
- **Stream:** Redis `market:ticks:BTC/USDT`
- **Volume:** 42,451+ Ticks empfangen

#### **Quant Agent (Neu)**
- **RSI Berechnung:** Manuell mit NumPy (statt pandas-ta)
- **Signal-Logik:** RSI < 30 → BUY, RSI > 70 → SELL
- **Threading:** `asyncio.to_thread()` für non-blocking
- **Output:** Redis `signals:quant` + Cache `status:agent:quant`

#### **Sentiment Agent**
- **LLM:** Ollama qwen2.5 (mit Fallback)
- **News-Quelle:** CryptoPanic API (Demo)
- **Output:** Redis `signals:sentiment`
- **Fallback:** Neutral bei LLM-Problemen

#### **Risk Agent**
- **Input:** Quant + Sentiment Signale
- **Konfluenz:** Threshold-basierte Validierung
- **Output:** Redis `execution:orders`

#### **Execution Agent**
- **DB:** AsyncSessionLocal für Background Tasks
- **Logging:** PostgreSQL `trade_audit_logs`
- **Mode:** Paper-Trading (audit only)

### 🌐 Frontend Integration
- **Agenten Dashboard:** http://localhost:3000/agenten
- **Live-Status:** 5/5 Agenten aktiv
- **Auto-Refresh:** Alle 30 Sekunden
- **Agent-Typen:** 📡 Data, 📊 Analysis, ⚖️ Risk, 💰 Execution

---

*Letzte Aktualisierung: 2026-03-26 - Phase 4 Vollständig Implementiert - 5 Agenten Live Trading*
