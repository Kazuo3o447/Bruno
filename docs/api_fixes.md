# API Fixes & Troubleshooting

> **Dokumentation der API-Verbindung, Fehlerbehebung und Container-Konfiguration**
> 
> ✅ **Stand:** 2. April 2026 - Critical Fixes & Config-Hot-Reload

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## 🎯 API-Verbindungs-Status

### ✅ Aktive API-Endpunkte
```
✅ /api/v1/telemetry/live      - System-Status & Agenten-Health
✅ /api/v1/market/grss-full    - GRSS-Score & Marktdaten
✅ /api/v1/decisions/feed      - Decision-Feed (letzte 20)
✅ /api/v1/positions/open      - Offene Positionen
✅ /api/v1/performance/metrics - Performance-Kennzahlen
✅ /api/v1/config              - Konfiguration & Status
✅ /api/v1/export/snapshot     - Vollständiger Bot-Snapshot
```

### 🔗 Frontend → Backend Verbindung
```
✅ Next.js Proxy: /api/:path* → http://api-backend:8000/api/:path*
✅ WebSocket Proxy: /ws/:path* → http://api-backend:8000/ws/:path*
✅ Docker-Netzwerk: bruno_default (alle Container verbunden)
✅ Container-Abhängigkeiten: bruno-frontend depends_on api-backend
✅ Port-Mapping: Backend 8000, Frontend 3000
✅ Environment: DB_HOST=postgres, REDIS_HOST=redis
✅ Config-Hot-Reload: Live-Konfigurationsänderungen ohne Neustart
```

---

## 🚨 Kritische API-Probleme & Lösungen (2. April 2026)

### **Problem 1: Doppeltes /api/v1 Prefix → 404 Errors**
**Symptome:**
- `/api/v1/config`, `/api/v1/export/snapshot`, `/api/v1/decisions/feed` geben 404 Not Found
- Dashboard kann Konfiguration nicht laden

**Ursache:**
```python
# Router definierten Prefix bereits intern
router = APIRouter(prefix="/api/v1", tags=["config"])
# main.py fügte erneut Prefix hinzu
app.include_router(config_api.router, prefix="/api/v1")  # → /api/v1/api/v1/config
```

**Lösung:**
```python
# In export.py, config_api.py, decisions.py:
router = APIRouter(tags=["export"])  # Prefix entfernt
# In main.py bleibt:
app.include_router(export.router, prefix="/api/v1")
```

**Behobene Dateien:**
- ✅ `backend/app/routers/export.py`
- ✅ `backend/app/routers/config_api.py` 
- ✅ `backend/app/routers/decisions.py`

### **Problem 2: Fresh-Source-Gate blockiert GRSS**
**Symptome:**
- GRSS Score immer 0.0 → dauerhafter Veto-Modus
- "fresh_source_count" ist 0 beim Start

**Ursache:**
```python
# Nur 2 von 5 Quellen reported Health
if int(data.get("fresh_source_count", 0)) <= 0: return 0.0
# Binance_REST, Deribit_Public, yFinance_Macro fehlten
```

**Lösung:**
```python
# Health-Reporting für alle Quellen:
await self._report_health("Binance_REST", "online", latency)
await self._report_health("Deribit_Public", "online", latency) 
await self._report_health("yFinance_Macro", "online", latency)
# Gate-Schwelle gesenkt:
if int(data.get("fresh_source_count", 0)) < 2: return 0.0
# Startup Warm-Up:
await self._fetch_binance_rest_data()
await self._fetch_deribit_data()
```

### **Problem 3: Config-Änderungen wirken nicht**
**Symptome:**
- Änderungen in Einstellungen haben keinen Effekt auf Agenten
- Hardcoded Werte in QuantAgent und RiskAgent

**Lösung:**
```python
# Config-Hot-Reload implementiert:
def _load_config_value(self, key: str, default: float) -> float:
    config_path = os.path.join(BASE_DIR, "config.json")
    with open(config_path, "r") as f:
        return float(json.load(f).get(key, default))

# In jedem process() Zyklus:
self.ofi_threshold = self._load_config_value("OFI_Threshold", 50.0)
self._grss_threshold = self._load_config_value("GRSS_Threshold", 40.0)
```

### **Problem 4: OFI Schema falsch im Frontend**
**Symptome:**
- OFI Slider zeigt 0 obwohl Wert 50
- Min=200, Max=1000, aber tatsächlicher Wert ist 50

**Lösung:**
```typescript
// Frontend Schema korrigiert:
OFI_Threshold: {
  label: "OFI Schwellenwert (Full-Depth)", 
  min: 10, max: 300, step: 5,  // Statt min: 200, max: 1000
  description: "Full-Depth OFI über 20 Levels. Typische Werte: 20–150. Start: 50."
}
// Backend Schema ebenfalls angepasst
```

### **Problem 5: Preset-System fehlt**
**Lösung:**
```typescript
// 3 Presets implementiert:
- Standard: GRSS=40, OFI=50, StopLoss=1.2%
- Konservativ: GRSS=50, OFI=80, StopLoss=1.0%  
- Aggressiv: GRSS=35, OFI=30, StopLoss=1.5%
// Visuelle Preset-Buttons mit Konfigurations-Erklärungs-Block
```

---

## 🚨 Kritische Port-Probleme & Lösungen (31. März 2026)

### **Problem 1: Frontend hartcodiert auf localhost:8001**
**Symptome:**
- Dashboard zeigt keine Daten an
- API-Aufrufe geben Connection Refused
- WebSocket-Verbindungen schlagen fehl

**Ursache:**
```javascript
// Falsch (war in 10+ Dateien vorhanden)
fetch("http://localhost:8001/api/v1/health")
new WebSocket("ws://localhost:8001/ws/agents")
```

**Lösung:**
```javascript
// Korrekt
fetch("/api/v1/health")  // Über Next.js Proxy
new WebSocket("ws://localhost:3000/ws/agents")  // Über WebSocket Proxy
```

**Behobene Dateien:**
- ✅ `frontend/src/components/SystemMatrix.tsx`
- ✅ `frontend/src/components/PriceLineChart.tsx`
- ✅ `frontend/src/components/LightweightChart.tsx`
- ✅ `frontend/src/components/ChartWidget.tsx`
- ✅ `frontend/src/components/ActivePositions.tsx`
- ✅ `frontend/src/app/websocket-test/page.tsx`
- ✅ `frontend/src/app/logtest/page.tsx`
- ✅ `frontend/src/app/backup/page.tsx`
- ✅ `frontend/src/app/components/LogViewer.tsx`
- ✅ `frontend/src/app/components/AgentStatusMonitor.tsx`

### **Problem 2: Environment-Datei mit localhost Konfiguration**
**Symptome:**
- Backend kann nicht mit Redis/Datenbank verbinden
- `Error 111 connecting to localhost:6379. Connection refused`
- Container-Start schlägt fehl

**Ursache:**
```bash
# Falsch (.env Datei)
DB_HOST=localhost
REDIS_HOST=localhost
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Lösung:**
```bash
# Korrekt (Docker-konfiguriert)
DB_HOST=postgres
REDIS_HOST=redis
NEXT_PUBLIC_API_URL=http://api-backend:8000
```

### **Problem 3: WebSocket "Cannot call send once close message has been sent"**
**Symptome:**
- Massenweise WebSocket-Fehler im Backend-Log
- Verbindungen werden ständig getrennt
- System überflutet mit Fehlermeldungen

**Ursache:**
```python
# WebSocket-Loops laufen weiter, auch wenn Verbindung geschlossen
while True:
    # ... Daten senden ohne Verbindungsprüfung
    await websocket.send_json(data)  # Fehler wenn Verbindung geschlossen
```

**Lösung:**
```python
# backend/app/routers/ws.py Fixes:
- Verbindungsprüfung vor dem Senden
- isDisposed Flags und Race Condition Protection
- Automatische Bereinigung geschlossener Verbindungen

if websocket.client_state.name == "CONNECTED":
    await websocket.send_json(message)
else:
    self.disconnect(websocket)  # Verbindung entfernen
```

### **Problem 4: WebSocket Proxy fehlt**
**Symptome:**
- WebSocket-Verbindungen geben Connection Refused
- Browser kann keine ws:// Verbindungen aufbauen

**Lösung:**
```javascript
// frontend/next.config.js
async rewrites() {
  return [
    { source: '/api/:path*', destination: 'http://api-backend:8000/api/:path*' },
    { source: '/ws/:path*', destination: 'http://api-backend:8000/ws/:path*' }, // ← WebSocket Proxy
  ];
}
```

### 1. "Object is disposed" Fehler in lightweight-charts
**Problem:** Chart-Komponente stürzt ab beim Unmounting
```javascript
// Fehler: get node_modules/fancy-canvas/canvas-element-bitmap-size.mjs
Error: Object is disposed
```

**Lösung:** Robuste Fehlerbehandlung in TradingChart.tsx
```javascript
// Fixes implementiert:
- isDisposed Flag für Race Conditions
- try-catch Blöcke um alle Chart-Operationen
- setTimeout(100ms) beim Cleanup
- isConnected Prüfung für DOM-Elemente
- generateDemoData() für Fallback-Daten
```

### 2. API-Aufrufe funktionieren nicht (404/Connection Errors)
**Problem:** Frontend kann nicht auf Backend zugreifen
```
Failed to proxy http://host.docker.internal:8000/api/v1/telemetry/live
Error: socket hang up
```

**Lösung:** Docker-Netzwerk-Konfiguration korrigiert
```yaml
# docker-compose.yml Änderungen:
bruno-frontend:
  depends_on:
    - api-backend                    # ← Neu: Abhängigkeit hinzugefügt
  environment:
    - NEXT_PUBLIC_API_URL=http://api-backend:8000  # ← Geändert

# next.config.js Änderungen:
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://api-backend:8000/api/:path*',  # ← Geändert
    },
  ];
}
```

### 3. RiskAgent vol_multiplier Bug
**Problem:** Variable nicht in allen Code-Pfaden definiert
```
RiskAgent Fehler: cannot access local variable 'vol_multiplier'
```

**Lösung:** Variable am Anfang der Funktion initialisiert
```python
# backend/app/agents/risk.py Fixes:
- vol_multiplier = 1.0 am Anfang von else-Block
- Berechnung in allen Code-Pfaden (auch bei Veto)
- Keine "unbound local variable" Fehler mehr
```

### 4. Fehlende API-Endpunkte
**Problem:** /performance/metrics gibt 404 Not Found

**Lösung:** Endpunkt in monitoring.py implementiert
```python
@router.get("/performance/metrics")
async def get_performance_metrics():
    # Gibt Performance-Kennzahlen zurück
    return {
        "daily_return": sim_data.get("daily_return_pct"),
        "weekly_return": sim_data.get("weekly_return_pct"),
        # ... weitere Metriken
    }
```

### 5. API-Routing Prefix fehlt
**Problem:** decisions und config Router ohne /api/v1 Prefix

**Lösung:** main.py Router-Konfiguration korrigiert
```python
# backend/app/main.py Fixes:
app.include_router(decisions.router, prefix="/api/v1")      # ← Prefix hinzugefügt
app.include_router(config_api.router, prefix="/api/v1")    # ← Prefix hinzugefügt
app.include_router(export.router, prefix="/api/v1")        # ← Prefix hinzugefügt
```

---

## 🚨 Alte Probleme (März 2026) - Rate Limits

### API-Rate-Limit-Probleme (behoben)
| API | Problem | Lösung |
|-----|---------|--------|
| Yahoo Finance | 429 Rate Limit | CBOE CSV Fallback |
| Reddit | 429 Rate Limit | OAuth + Anonym Fallback |
| StockTwits | 403 Forbidden | Graceful Skip |
| HuggingFace | Langsame Downloads | Token-Integration |

**Ergebnis:** Alle 6 Agenten laufen stabil.

---

## ✅ Lösung (30.03.2026)

### 1. VIX: CBOE Offizielle Quelle
```python
# CBOE CSV als primäre Quelle (offiziell, kein Rate Limit)
cboe_resp = await client.get(
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    timeout=10.0
)
if cboe_resp.status_code == 200:
    lines = cboe_resp.text.strip().split("\n")
    last = lines[-1].split(",")
    vix = float(last[4])  # CLOSE-Spalte
    # Ergebnis: VIX 31.05 (echte Marktdaten)
```

### 2. Fallback-Hierarchie VIX
```
1. CBOE CSV (primär) - Offizielle Quelle, keine Rate Limits
2. Yahoo Finance (fallback) - Real-time aber 429-anfällig  
3. Alpha Vantage (final) - TIME_SERIES_DAILY
```

### 3. Reddit OAuth + Anonym Fallback
```python
# OAuth (60 req/min) oder anonym
if token:
    url = "https://oauth.reddit.com/r/Bitcoin/hot.json"
    headers = {"Authorization": f"Bearer {token}"}
else:
    url = "https://www.reddit.com/r/Bitcoin/hot.json"
    headers = {"User-Agent": "BrunoBot/1.0"}
```

### 3. StockTwits Graceful Skip
```python
# Kein Request ohne API Key
if not api_key:
    logger.debug("StockTwits: kein API Key — übersprungen")
    return None  # Graceful skip
```

### 4. Alpha Vantage NDX Fallback
```python
# QQQ als NDX-Proxy (25 req/day kostenlos)
av_url = (
    "https://www.alphavantage.co/query"
    f"?function=TIME_SERIES_DAILY_ADJUSTED&symbol=QQQ"
    f"&apikey={av_key}"
)
```

### 5. HuggingFace Token Optimierung
```python
# Schnellere Downloads mit Token
_hf_token = os.getenv("HF_TOKEN")
if _hf_token:
    from huggingface_hub import login
    login(token=_hf_token, add_to_git_credential=False)
```

---

## 🔧 Konfiguration

### Neue API Keys
```env
# Alpha Vantage (NDX Fallback)
ALPHA_VANTAGE_API_KEY=A32W701M76K5OVEW

# Reddit OAuth (optional)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# StockTwits (optional)
STOCKTWITS_API_KEY=

# HuggingFace (optional)
HF_TOKEN=
```

### Dependencies
```txt
huggingface_hub  # Für HF Token Login
```

---

## 📊 Ergebnis

### Vorher (API-Probleme)
```
❌ ingestion: running (5 Streams)
❌ quant: running (orderbook)
❌ context: stopped (VIX 429)
❌ sentiment: stopped (Reddit 429)
❌ risk: running (vetos)
❌ execution: running

Total: 2/6 running, 4 blocked
```

### Nachher (Stabil)
```
✅ ingestion: running (streaming)
✅ quant: running (fetching orderbook)
✅ context: running (fetching macro data)
✅ sentiment: running (fetching news)
✅ risk: running (idle, 60s wait)
✅ execution: running (streaming)

Total: 6/6 running, 0 errors
```

---

## 🎯 API-Health

| API | Status | Lösung |
|-----|--------|---------|
| VIX | ✅ 200 | CBOE CSV (offiziell) - VIX 31.05 |
| Reddit | ✅ 200 | OAuth + Anonym |
| StockTwits | ✅ Skip | Graceful Skip |
| Alpha Vantage | ✅ 200 | NDX Fallback aktiv |
| HuggingFace | ⚠️ Optional | Token bereit |

---

## 🚀 Deployment

### Git Commit
```
919a925 - API Fixes: Implement rate limit solutions and fallback mechanisms
```

### Docker Container
```bash
docker compose build    # Mit huggingface_hub
docker compose up -d     # Alle Container neu starten
```

### Validierung
```bash
curl http://localhost:8000/api/v1/agents/status
# {"total_agents": 6, "running_agents": 6, "error_agents": 0}
```

---

## 📋 Technische Details

### Fallback-Hierarchie
```
VIX: CBOE CSV → Yahoo Finance → Alpha Vantage → Redis-Cache → Default
NDX: Yahoo Finance → Alpha Vantage → Redis-Cache → Default
Reddit: OAuth → Anonym → None
StockTwits: API-Key → Graceful Skip
```

### Rate-Limits
- **CBOE**: Kein Limit (offizielle CSV)
- **Reddit OAuth**: 60 req/min
- **Alpha Vantage**: 25 req/day (kostenlos)
- **StockTwits**: Übersprungen ohne Key

---

## 🎉 Fazit

**Mission accomplished!** 🎯

- ✅ **6/6 Agenten laufen stabil**
- ✅ **Keine API-Blockaden mehr**
- ✅ **Maximale Redundanz**
- ✅ **Produktionsbereit**

Das Bruno Trading Bot System hat jetzt robuste API-Verbindungen mit mehreren Fallback-Optionen für maximale Stabilität.
