# Daten-Architektur & Market Context

> **Das LLM ist das Gehirn, die Daten sind die Sinne.**
> Ein Modell wie DeepSeek-R1 (14B Parameter) verhungert, wenn man ihm nur "Der RSI ist 30" als Kontext gibt. Dieses Dokument definiert, wie wir aus **100% kostenlosen (Free-Tier)** APIs das absolute Maximum an Daten-Masse und Daten-Qualität extrahieren, um dem Bot einen unfairen Vorteil zu verschaffen.

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

---

## 3. Datenbank-Struktur (TimescaleDB)

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

## 5. Agenten-Verantwortlichkeiten

Damit dieser Datenfluss funktioniert, haben die Agenten klare Aufgaben (umzusetzen in Phase 2 und 3):

- **📡 Ingestion Agent:** Handhabt die 5 WebSocket-Streams synchron und stabil. Sammelt die Daten und flusht sie minütlich in die TimescaleDB-Hypertables.
- **📊 Quant Agent:** Fragt die TimescaleDB ab. Nutzt die Continuous Aggregates, um nicht nur den 1m-Trend, sondern das Makro-Bild (4H) und Mikrostruktur (Orderbuch-Imbalance) in den "Context" zu gießen. Holt täglich den F&G Index.
- **🧠 Sentiment Agent:** Konzentriert sich rein auf Krypto-News (CryptoPanic) und wandelt sie via Ollama in einen numerischen `news_sentiment` Score um.
- **⚖️ Risk Agent (State Builder):** Dies ist der Chef-Architekt. Er nimmt die Rohdaten vom Quant (Preis, Liquidations, Funding, Orderbuch) und Sentiment (News) und **baut das JSON-Context-Objekt** zusammen. Dieses reicht er an das LLM für die Deep-Reasoning-Analyse weiter, bevor eine Buy/Sell Order an Execution geht.

---

> [!CAUTION]
> **Wer auch immer Code für Phase 2 oder Phase 3 schreibt:** 
> Ein simples Setup, das nur den Preis anschaut, wird rigoros abgelehnt. Der Code MUSS Orderbuch-Tiefe, Liquidations und Funding-Rates berücksichtigen, um dem KI-Gehirn die nötige "Sehkraft" zu geben.
