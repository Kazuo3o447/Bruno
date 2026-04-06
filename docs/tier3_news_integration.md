# Tier-3 News Integration Documentation

## Overview

Die Tier-3 News Integration ist eine **fail-safe supplementary layer** für die Bruno Trading Platform, die auf dem Open-Source Projekt [nirholas/free-crypto-news](https://github.com/nirholas/free-crypto-news) basiert.

## Architektur-Prinzip: Zero Trust

Die Integration folgt einem **Zero Trust Architecture** Ansatz:

- **Never Trust**: Open-Source-APIs können jederzeit offline gehen, Latenzen aufbauen oder Datenstrukturen ändern
- **Always Verify**: Strikte Exception-Handling und Timeout-Kontrollen
- **Fail Gracefully**: Bei Ausfällen sofort `[]` Rückgabe, keine Blockierung des Haupt-Threads

## Technische Spezifikation

### FreeCryptoNewsClient

**Datei**: `backend/app/services/news_providers/free_crypto_news.py`

#### Defensive HTTP-Polling (Zero Trust)

```python
# Timeout: 5.0 Sekunden hartes Limit
self._http_client = httpx.AsyncClient(timeout=5.0)

# Exception Handling - Strikte try...except Exception Blöcke
try:
    response = await self._http_client.get(url)
    response.raise_for_status()
    data = response.json()
    # ... Verarbeitung
except httpx.TimeoutException:
    self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
    return []
except httpx.HTTPStatusError as e:
    if e.response.status_code >= 500:
        self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
    else:
        self.logger.warning(f"FreeCryptoNews API returned {e.response.status_code}. Skipping.")
    return []
except Exception:
    self.logger.warning("FreeCryptoNews API offline/timeout. Skipping.")
    return []
```

#### Daten-Normalisierung & Filterung

```python
# BTC Pre-Filter - Nur Bitcoin-spezifische Inhalte
combined_text = (title + " " + description).lower()
if "btc" not in combined_text and "bitcoin" not in combined_text:
    continue

# Standardisiertes Output-Format
normalized_item = {
    "title": title,
    "text": description,
    "source": "free-crypto-news",
    "timestamp": item.get("pubDate", datetime.now(timezone.utc).isoformat()),
    "url": item.get("link", ""),
    "metadata": {
        "source_feed": item.get("source", "unknown"),
        "time_ago": item.get("timeAgo", ""),
        "api_fetched_at": data.get("fetchedAt", "")
    }
}
```

#### Dual Endpoints

1. **General News**: `/api/news` - Allgemeine Crypto News
2. **Bitcoin Specific**: `/api/bitcoin` - BTC-spezifische News (höhere Dichte)

### Integration in News Ingestion Service

**Datei**: `backend/app/services/news_ingestion.py`

#### Redis Storage

```python
async def _store_processed_news(self, processed_news: Dict[str, Any]):
    """Speichere verarbeitete News in Redis für SentimentAgent."""
    if not self._redis_client:
        return
        
    # Speichere einzelne News-Items
    await self._redis_client.set_cache(
        f"bruno:news:item:{processed_news['title'][:50]}",
        processed_news,
        ttl=3600  # 1 Stunde
    )
    
    # Speichere Aggregat für schnellen Zugriff
    existing_items = await self._redis_client.get_cache("bruno:news:processed_items") or []
    existing_items.append({
        "title": processed_news["title"],
        "sentiment": processed_news["sentiment"],
        "sentiment_score": processed_news["sentiment_score"],
        "source": processed_news["source"],
        "timestamp": processed_news["timestamp"]
    })
    
    # Nur die letzten 50 Items behalten
    if len(existing_items) > 50:
        existing_items = existing_items[-50:]
    
    await self._redis_client.set_cache(
        "bruno:news:processed_items",
        existing_items,
        ttl=1800  # 30 Minuten
    )
```

#### Polling Frequenz

- **RSS Feeds**: 30 Sekunden
- **CryptoPanic**: 60 Sekunden
- **Tier-3 FreeCryptoNews**: 60 Sekunden (supplementary)

### SentimentAgent Integration

**Datei**: `backend/app/agents/sentiment.py`

#### Vor-analysierte Daten Nutzung

```python
# Prüfe ob vor-analysierte Daten vorliegen (News Ingestion)
if "pre_analyzed_sentiment" in item:
    # Nutze vor-analysierte Sentiment-Daten
    sentiment_scores.append({
        "score": item["pre_analyzed_sentiment"],
        "confidence": 0.8,  # Hohe Konfidenz bei vor-analysierten Daten
        "classification": item.get("pre_analyzed_label", "neutral"),
        "source": source
    })
    self.logger.debug(f"Vor-analysiert: {headline[:30]}... -> {item['pre_analyzed_sentiment']:.3f}")
else:
    # Fallback auf NLP-Analyse
    mode = "macro" if source == "coindesk" or any(cat in {"regulation", "exchange"} for cat in categories) else "crypto"
    result = await self.analyzer.analyze_with_filter(headline, mode=mode)
```

## Datenfluss

```
Tier-3 FreeCryptoNews ──► FreeCryptoNewsClient ──► NewsIngestionService
                                                            │
                                                            ▼
                                                    SentimentAnalyzer
                                                            │
                                                            ▼
                                                      Redis Storage
                                                            │
                                                            ▼
                                                   SentimentAgent
                                                            │
                                                            ▼
                                                   ContextAgent
                                                            │
                                                            ▼
                                                   GRSS Score
```

## Betrieb in Produktion

### Health Check

Der Client meldet sich health-check-fähig:

```python
# Logs im Worker
[news_ingestion] INFO: Tier-3 FreeCryptoNews: 0 items processed
[news_ingestion] INFO: Tier-3 FreeCryptoNews: Processed 0 items
```

### Performance

- **Timeout**: 5 Sekunden (hart)
- **Polling**: 60 Sekunden
- **Memory**: SHA256 Hash Queue (maxlen=3000)
- **Storage**: Redis Cache (TTL 30-60 Minuten)

### Fehlerbehandlung

1. **API Offline**: Warning Log + `[]` Rückgabe
2. **Timeout**: Warning Log + `[]` Rückgabe  
3. **5xx Errors**: Warning Log + `[]` Rückgabe
4. **JSON Decode Errors**: Warning Log + `[]` Rückgabe
5. **No BTC Content**: Silent Skip (kein Log)

## Monitoring

### Redis Keys

- `bruno:news:processed_items` - Aggregierte News-Liste
- `bruno:news:item:{title_hash}` - Einzelne News-Items

### Log Patterns

```
[news_ingestion] INFO: Tier-3 FreeCryptoNews: {count} items processed
[news_ingestion] WARNING: FreeCryptoNews API offline/timeout. Skipping.
[sentiment] DEBUG: Vor-analysiert: {title}... -> {score:.3f}
```

### Health Status

Der Client wird im ContextAgent als Health Source erfasst:

- **online**: API erreichbar und Daten verfügbar
- **degraded**: API erreichbar aber keine Daten
- **offline**: API nicht erreichbar

## Sicherheit

### Zero Trust Prinzipien

1. **Keine Vertrauenswürdigkeit**: API kann jederzeit ausfallen
2. **Defensive Programmierung**: Jeder Aufruf ist exception-geschützt
3. **Graceful Degradation**: System funktioniert auch bei Ausfall
4. **No Blocking**: Haupt-Thread wird nie blockiert

### Datenprivacy

- **Keine persönlichen Daten**: Nur öffentliche News-Header
- **SHA256 Hashing**: Für Deduplizierung, keine Klartext-Speicherung
- **TTL-basiert**: Daten werden automatisch gelöscht

## Zukunft

### Erweiterungsmöglichkeiten

1. **Zusätzliche Endpoints**: `/api/search?q=bitcoin`, `/api/trending`
2. **Kategorie-Filter**: `/api/news?category=institutional`
3. **International**: `/api/news/international`
4. **AI-Powered**: `/api/ask?q=bitcoin+analysis`

### Optimierungen

1. **Batch Processing**: Mehrere Items in einem Request
2. **Caching**: Lokale Cache für häufige Anfragen
3. **Rate Limiting**: Eigene Rate-Limit-Logik
4. **Fallback Chains**: Multiple Open-Source APIs

---

**Status**: ✅ Production Ready (Zero-Trust Defensive Architecture)  
**Letzte Aktualisierung**: 2026-04-06  
**Version**: v1.0 (Tier-3 Integration)
