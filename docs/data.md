# Daten-Architektur & Market Context

> **Das LLM ist das Gehirn, die Daten sind die Sinne.**
> Ein Modell wie DeepSeek-R1 (14B Parameter) verhungert, wenn man ihm nur "Der RSI ist 30" als Kontext gibt. Dieses Dokument definiert,## 🏁 Phase 5: Institutional Macro/Micro Context & Risk System (März 2026)
**Status: ✅ COMPLETED**

- [x] **ContextAgent**: Integration von 8 RSS-Feeds & Makro-Metriken (VIX, Yields).
- [x] **HFT-Quant**: Implementierung von OFI, VAMP und CVD-Trend.
- [x] **HuggingFace Pipeline**: BERT-Integration (FinBERT/CryptoBERT) mit non-blocking Threads.
- [x] **Zero-Shot Filtering**: BART-MNLI Modell zur Trennung von "Opinion" und "Facts".
- [x] **Risk Veto Matrix**: Implementierung von Hard-Vetos (News Silence, Divergenz, Geopolitik).
- [x] **Dashboard V2**: Visualisierung von GRSS, Bias und HFT-Metriken in Echtzeit.

---

## 🚀 Phase 6: Live-Execution & Linux-Stabilitäts-Härtung (Next)
**Ziele:**
1. Migration der Worker auf dedizierte Linux-Hosts (Native Performance).
2. Implementierung von Order-Execution-Sicherungen (Fat-Finger-Schutz).
3. Live-Backtesting gegen historische Slippage-Daten.
wie wir aus **100% kostenlosen (Free-Tier)** APIs das absolute Maximum an Daten-Masse und Daten-Qualität extrahieren, um dem Bot einen unfairen Vorteil zu verschaffen.

**Jede Implementierung in Phase 2 und 3 MUSS sich zwingend an diesen Vorgaben orientieren.**

---

## 1. Das Problem: Die reine Preis-Illusion

Retail-Trader schauen nur auf den Preis (Candlesticks) und einfache Indikatoren (RSI, MACD). Das reicht für Algorithmus-Trading nicht aus. Wale und Institutionen bewegen den Markt über das **Orderbuch** und lösen **Kaskaden an Liquidationen** aus. 

Um erfolgreich zu sein, muss unser Bot den Krypto-Markt dreidimensional sehen:
1. **Preis-Aktion** (Candles & Makro-Trend)
2. **Markt-Mikrostruktur** (Orderbuch-Tiefe & Limit-Orders)
3. **Derivate-Dynamik** (Funding Rates & Liquidations)
4. **Markt-Psychologie** (Fear & Greed, News-Sentiment)

---

## 2. Der "Free-Tier Maximum" Stack

Wir nutzen extrem hochauflösende Echtzeit-Daten, ohne einen Cent für APIs zu bezahlen.

### 2.1 Echtzeit-Marktdaten (Binance Futures WebSocket)
Binance bietet über den Futures WebSocket (WSS) öffentlichen, kostenlosen Zugang zu professionellen Marktdaten. Unser Ingestion Agent muss 5 Streams gleichzeitig abonnieren:

| Stream (z.B. `btcusdt@...`) | Daten-Art | Alpha-Wert (Warum brauchen wir das?) |
|-----------------------------|-----------|-------------------------------------|
| `kline_1m` | 1-Minuten Kerzen | Perfekte OHLCV-Daten direkt von der Börse. Ersetzt das mühsame manuelle Berechnen aus Ticks. |
| `depth20@100ms` | Orderbuch | Zeigt die 20 tiefsten Bids/Asks. Erlaubt uns massive Kauf/Verkaufs-Wände (Support/Resistance) der Wale zu erkennen. |
| `forceOrder` | Liquidations | **Das stärkste Signal!** Wenn massenhaft Short-Trader zwangsliquidiert werden, treibt das den Preis hoch (Short-Squeeze). Perfekt für Counter-Trades. |
| `markPrice@1s` | Funding Rate | Zahlen Longs die Shorts (positiv) oder umgekehrt? Offenbart überhitzte Märkte, wenn alle in die gleiche Richtung wetten. |
| `btcdomusdt@kline_1m` | BTC Dominanz | Zeigt an, ob Geld gerade in Bitcoin fließt oder in Altcoins abfließt (Makro-Kontext). |

### 2.2 Makro & Sentiment (Free REST APIs)
Neben den Rohdaten der Börse brauchen wir den menschlichen Faktor:

| Quelle | Intervall | Daten |
|--------|-----------|-------|
| `alternative.me` | Täglich | **Fear & Greed Index** (0-100). Erlaubt dem Quant, Strategien an extreme Panik oder Gier anzupassen. (Kein API-Key nötig). |
| `CryptoPanic API` | 5 Minuten | Breaking News Aggregator. (Free-Tier: 5 Requests/Minute, reicht völlig aus). |

### 2.3 Spezialisierte News Feeds & BERT Modelle (Phase 5)
Um den "menschlichen Faktor" noch tiefer zu analysieren, integrieren wir spezialisierte News-Feeds und NLP-Modelle.

| Kategorie | Quelle | Zweck | Status |
|-----------|---------|-------|--------|
| **Makro (FinBERT)** | federalreserve.gov/feeds/press_all.xml | Zinspolitik & FOMC | ✅ Aktiv |
| **Makro (FinBERT)** | reuters.com/business/feed | Globale Wirtschaftsnachrichten | ✅ Aktiv |
| **Makro (FinBERT)** | investing.com/rss/news.rss | Markt-Metriken & Analysen | ✅ Aktiv |
| **Makro (FinBERT)** | marketwatch.com/rss/marketupdate | Intraday Markt-Trends | ✅ Aktiv |
| **Krypto (CryptoBERT)** | coindesk.com/arc/outboundfeeds/rss | Primäre Krypto-News | ✅ Aktiv |
| **Krypto (CryptoBERT)** | decrypt.co/feed | Web3 & Tech Fokus | ✅ Aktiv |
| **Krypto (CryptoBERT)** | cryptoslate.com/feed | Markt-Daten & On-Chain News | ✅ Aktiv |
| **Krypto (CryptoBERT)** | cointelegraph.com/rss | Globale Krypto-Trends | ✅ Aktiv |

---

## 3. NLP-Modelle & Sentiment-Analytik (Phase 5)

Das System nutzt eine dreistufige NLP-Pipeline zur Klassifizierung und Bewertung von Markt-Nachrichten:

| Modell | Zweck | Details |
|--------|-------|---------|
| **BART-Large-MNLI** | Noise-Filter | Zero-Shot Klassifizierung in Regulatory, Macro, Infrastructure oder Opinion. |
| **FinBERT (ProsusAI)** | Finanz-Sentiment | Spezialisiert auf die Tonalität von Wirtschaftsnachrichten (Macro-Flow). |
| **CryptoBERT (ElKulako)**| Krypto-Sentiment | Optimiert für die spezifische Sprache der Krypto-Märkte (Crypto-Pulse). |
| **DeepSeek-R1 / Qwen** | Strategisches Reasoning| Letzte Instanz im Risk-Agent zur Konsolidierung aller Faktoren. |

**Logik-Regel:** Nachrichten mit dem Label `Opinion and Rumor` werden verworfen, wenn der absolute Sentiment-Score < 0.75 ist. Dies eliminiert Rauschen und fokussiert das System auf harte Marktfakten.

---

## 4. Datenbank-Struktur (TimescaleDB)

Die einfache `market_candles` Tabelle reicht für diese Informationsflut nicht. Wir strukturieren unsere PostgreSQL/TimescaleDB komplett neu:

### Hypertables (Rohdaten)
1. `candles_1m` (Zeit, Symbol, O, H, L, C, V)
2. `orderbook_snapshots` (Zeit, Symbol, Bids_Volume, Asks_Volume, Imbalance_Ratio)
3. `liquidations` (Zeit, Symbol, Direction, Quantity, Price)
4. `funding_rates` (Zeit, Symbol, Rate)

### Continuous Aggregates (Automatische Zeitfenster)
TimescaleDB errechnet live im Hintergrund die höheren Timeframes aus den 1m-Daten:
- `candles_5m`, `candles_15m`, `candles_1h`, `candles_4h`
- Aggregierte Liquidations-Summen (z.B. "Wie viele Millionen wurden in der letzten Stunde liquidiert?")

---

## 4. Der "Rich Market Context" (Das LLM Prompt)

All diese Daten bringen nichts, wenn wir sie dem DeepSeek-R1 Modell (oder dem Regelwerk des Risk Agents) nicht strukturiert übergeben.

In **Phase 3** aggregiert der Risk/Consensus Agent alle Daten zu einem massiven `MarketContext` JSON. Dieses JSON ist der alleinige "Blick auf die Welt" für unseren Trading-Bot.

### Beispiel eines perfekten Context-Prompts an DeepSeek-R1:

```json
{
  "asset": "BTC/USDT",
  "macro_context": {
    "trend_4H": "bullish_struktur",
    "fear_and_greed_index": 76,
    "btc_dominance_trend": "steigend"
  },
  "price_action": {
    "current_price": 68912.50,
    "momentum_15m": "stark_oversold (RSI: 22)",
    "distance_to_vwap": "-2.4%"
  },
  "market_microstructure": {
    "orderbook_imbalance": "+2.8x Bids",
    "insight": "Massive Buy-Wall bei 68500.00 detektiert"
  },
  "derivatives_pressure": {
    "funding_rate": "0.015% (Longs extrem überhitzt)",
    "liquidations_last_1h": "12.5M USD Shorts liquidiert (Warnung vor Top)"
  },
  "news_sentiment": {
    "score_1h": 0.82,
    "insight": "ETF Inflow News dominieren die Krypto-Medien"
  }
}
```

### Die Magie der Reasoning Engine
Wenn wir DeepSeek-R1 mit **genau diesem** strukturierten Datensatz füttern (zusammen mit der Anweisung `Denke Schritt-für-Schritt wie ein institutioneller Quant-Trader`), entfesseln wir seine volle Kraft.

Es kann dann Korrelationen herstellen wie:
> *"Der 15m RSI ist im überverkauften Bereich, was technisch bullisch wirkt. ABER: Die Funding Rates sind massiv überhitzt und in der letzten Stunde wurden 12.5 Millionen Dollar an Shorts liquidiert. Gleichzeitig drückt eine Buy-Wall von unten. Dies deutet auf einen künstlichen Squeeze hin, die Liquidität oben ist abgefischt. Ein Long hier ist extrem gefährlich. Entscheidung: ABWARTEN oder VORSICHTIGER SHORT-SCALP bis zur Buy-Wall."*

---

## 5. Agenten-Verantwortlichkeiten (Phase 7.5 - Shadow Trading)

Damit dieser Datenfluss funktioniert, haben die Agenten klare, entkoppelte Aufgaben:

- **📡 Ingestion Agent:** Handhabt 5-10 WebSocket-Streams. Sammelt Rohdaten und flusht sie in TimescaleDB-Hypertables sowie Redis-Ticker-Caches.
- **📊 Quant Agent:** Nutzt den `PublicExchangeClient`. Berechnet HFT-Metriken (OFI, CVD, VAMP) und publiziert Signale an `bruno:pubsub:signals`.
- **🧠 Sentiment Agent:** Aggregiert News (8 Feeds) und generiert via Ollama (FinBERT/DeepSeek) einen Bias-Score.
- **🛡️ Risk Agent:** Der Wächter. Konsolidiert alle Signale und Makro-Daten. Publiziert den aktuellen Sicherheitsstatus (Veto-State) an `bruno:pubsub:veto`.
- **⚡ Execution Agent:** Das Herzstück. Hält den Veto-Status im RAM (0ms Latenz) und führt Signale von `bruno:pubsub:signals` über den `AuthenticatedExchangeClient` sofort aus. Bei aktivem `DRY_RUN` erfolgt ein Shadow-Trade mit exakter 0.04% Fee-Simulation und Slippage-Logging in `trade_audit_logs`.

---

## 6. Audit-Trail & Telemetrie (Phase 7.5)

Das System erfasst für jeden (simulierten) Trade einen hochpräzisen Datensatz für das MLOps Dashboard:

| Datenpunkt | Feldname | Zweck |
|------------|----------|-------|
| **Signal-Preis** | `signal_price` | Preis exakt im Moment der Signalgenerierung. |
| **Fill-Preis** | `simulated_fill_price` | Tatsächlicher/Simulierter Preis inkl. Latenz-Nachbildung. |
| **Slippage** | `slippage_bps` | Differenz in Basis-Punkten (Audit-Metrik). |
| **Gebühren** | `simulated_fee_usdt` | Exakte 0.04% Taker-Fee Simulation (Lead Architect Rule). |
| **Latenz** | `latency_ms` | Zeit vom Signal-Empfang bis zum Abschluss der Simulation. |

---

> [!CAUTION]
> **Performance-Vorgabe:** In Phase 7.5 ist die Simulation der Gebühren (0.04%) zwingend einzuhalten. Shadow-Trades ohne Fees gelten als ungültig und verzerren die MLOps-Optimierung.

