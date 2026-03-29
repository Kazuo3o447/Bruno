# BRUNO_REVIEW.md
# Bruno Trading Bot — Review, Reporting & State

> **Pflichtlektüre für alle Agenten und LLMs.**
> Dieses Dokument definiert: wie Bruno über sich selbst berichtet,
> wie sein Zustand maschinenlesbar dokumentiert wird,
> und wie Backups + Recovery funktionieren.
>
> Erstellt: 2026-03-27 | Architekt: Ruben | Review: Claude (Anthropic)

---

## 0. DESIGN-PRINZIP: LLM-FIRST REPORTING

Jeder Report den Bruno erzeugt muss folgende Anforderung erfüllen:

**Ein LLM der das Projekt nie gesehen hat, muss nach dem Lesen von
`WINDSURF_MANIFEST.md` + dem aktuellen State-Snapshot sofort wissen:**
- Was der Bot gerade macht
- Ob er funktioniert
- Was die letzten 3 Entscheidungen waren und warum
- Wo die kritischen Probleme liegen

Das bedeutet: **strukturiertes JSON + kurze prose Zusammenfassung.**
Kein freier Text ohne Struktur. Keine Tabellen ohne Kontext.

---

## 1. DER LIVE STATE SNAPSHOT

**Datei:** `bruno_state.json` (im Redis gespeichert, alle 15 Minuten aktualisiert)
**Zweck:** Sofortige Lagebeschreibung für jeden Agent/LLM der eingreift

```json
{
  "snapshot_time": "2026-03-27T14:30:00Z",
  "version": "0.4.0",
  "system": {
    "status": "running",
    "dry_run": true,
    "uptime_hours": 72.5,
    "agents": {
      "ingestion": "healthy",
      "quant": "healthy",
      "context": "healthy",
      "risk": "healthy",
      "execution": "healthy"
    },
    "data_sources": {
      "binance_ws": {"status": "live", "latency_ms": 45, "last_message_ago_s": 2},
      "fred_yields": {"status": "ok", "value": 4.31, "age_minutes": 8},
      "deribit_pcr": {"status": "ok", "value": 0.52, "age_minutes": 4},
      "fear_greed": {"status": "ok", "value": 61, "age_hours": 2},
      "cryptopanic": {"status": "ok", "age_minutes": 5},
      "yfinance_vix": {"status": "degraded", "value": 19.2, "note": "Fallback aktiv"}
    }
  },
  "market": {
    "btc_price": 84523.50,
    "regime": "ranging",
    "grss": 58.5,
    "grss_components": {
      "macro": 14.0,
      "derivatives": 22.5,
      "sentiment": 12.0,
      "velocity_modifier": -5.0,
      "hard_vetoes_active": false
    },
    "funding_rate": 0.0087,
    "pcr": 0.52,
    "dvol": 54.3,
    "oi_delta_pct": 1.2,
    "perp_basis_pct": 0.031,
    "correlation_btc_ndx_20d": 0.71
  },
  "position": {
    "status": "none",
    "symbol": null,
    "side": null,
    "entry_price": null,
    "unrealized_pnl_pct": null,
    "stop_loss": null,
    "take_profit": null
  },
  "last_3_decisions": [
    {
      "time": "2026-03-27T12:15:00Z",
      "decision": "HOLD",
      "layer1_regime": "ranging",
      "layer1_confidence": 0.71,
      "layer2_result": "HOLD — Confidence 0.61 unter Schwelle",
      "grss_at_decision": 55.2
    },
    {
      "time": "2026-03-27T10:00:00Z",
      "decision": "BUY_BLOCKED",
      "layer1_regime": "trending_bull",
      "layer1_confidence": 0.78,
      "layer2_result": "BUY mit 0.72 Confidence",
      "layer3_result": "BLOCKED — Liquidation Wall bei $83.900 (0.3% Distanz)",
      "grss_at_decision": 67.5
    },
    {
      "time": "2026-03-27T07:45:00Z",
      "decision": "EXECUTED_LONG",
      "layer1_regime": "trending_bull",
      "layer1_confidence": 0.82,
      "layer2_result": "BUY mit 0.74 Confidence",
      "layer3_result": "Kein Blocker",
      "executed_price": 83200.0,
      "exit_price": 84100.0,
      "exit_reason": "TAKE_PROFIT",
      "pnl_pct": 1.08,
      "grss_at_decision": 69.1
    }
  ],
  "daily_performance": {
    "date": "2026-03-27",
    "trades": 1,
    "pnl_eur": 3.42,
    "pnl_pct": 0.68,
    "fees_eur": 0.08,
    "max_drawdown_pct": 0.17,
    "daily_limit_remaining_eur": 6.58
  },
  "learning": {
    "total_trades_logged": 47,
    "debriefs_completed": 47,
    "patterns_identified": 5,
    "current_profit_factor_rolling": 1.73,
    "grss_accuracy_last_20": 0.72,
    "open_failure_watches": 2
  },
  "alerts": [],
  "next_calibration": "2026-03-29T03:00:00Z"
}
```

**Redis Key:** `bruno:state:snapshot` 
**TTL:** 900 Sekunden (15 Minuten)
**Generator:** ContextAgent nach jedem Zyklus

---

## 1.1 PHASE-A HARDENING UPDATE — 2026-03-29

Die folgenden Audit-Fixes wurden umgesetzt und live bzw. im Codepfad abgesichert:

- **Data-Freshness Fail-Safe**
  - `ContextAgent` bricht die GRSS-Berechnung jetzt auf `0.0` ab, wenn keine frische externe Datenquelle verfügbar ist.
  - Das verhindert Fail-Open-Verhalten bei vollständigem API-Ausfall.

- **CryptoPanic Health-Telemetrie**
  - `SentimentAgent` meldet jetzt `online` / `degraded` / `offline` inklusive Latenz an `bruno:health:sources`.

- **DVOL-Reason-Persistenz**
  - `RiskAgent` behält DVOL-Leverage-Reduktionshinweise im finalen `Reason`, auch wenn später ein anderes Veto greift.

- **Live-Trading Approval Guard**
  - `AuthenticatedExchangeClient` blockiert `BYBIT_MODE="live"`, solange `LIVE_TRADING_APPROVED=False` bleibt.
  - Der neue Schalter ist in `.env.example` dokumentiert.

---

## 2. REPORT-TYPEN UND FORMATE

### 2.1 Trade Report (nach jedem Trade, sofort)

**Zweck:** Vollständige Dokumentation einer einzelnen Handelsentscheidung.
**Empfänger:** Telegram (kompakt) + DB (vollständig) + Review-Log (täglich aggregiert)

**Telegram-Format (kompakt, für Ruben):**
```
🟢 LONG BTCUSDT ausgeführt
Entry: $84.500 | Qty: 0.001 BTC | Leverage: 1.5×
SL: $83.745 | TP: $85.270
GRSS: 67.5 | Regime: trending_bull | L2 Conf: 74%
Reasoning: "OI steigt, Funding neutral, PCR 0.41"
```

**DB-Format (vollständig, für LLM-Analyse):**
```json
{
  "trade_id": "uuid",
  "timestamp": "2026-03-27T14:30:00Z",
  "type": "entry",
  "symbol": "BTCUSDT",
  "side": "long",
  "entry_price": 84500.0,
  "quantity": 0.001,
  "leverage": 1.5,
  "stop_loss_price": 83745.0,
  "take_profit_price": 85270.0,
  "position_value_eur": 84.50,
  "market_context": {
    "grss": 67.5,
    "grss_breakdown": {"macro": 18.0, "derivatives": 24.0, "sentiment": 15.0},
    "regime": "trending_bull",
    "funding_rate": 0.012,
    "pcr": 0.41,
    "oi_delta_pct": 2.3,
    "perp_basis_pct": 0.031,
    "dvol": 52.0,
    "vix": 17.2,
    "ndx_status": "BULLISH",
    "fear_greed": 71,
    "correlation_btc_ndx": 0.71,
    "atr_ratio": 1.1,
    "active_patterns": ["institutional_accumulation"]
  },
  "llm_cascade": {
    "layer1": {
      "regime": "trending_bull",
      "confidence": 0.82,
      "key_signals": ["OI steigt", "Funding neutral", "PCR bullish"]
    },
    "layer2": {
      "decision": "BUY",
      "confidence": 0.74,
      "reasoning": "OI steigt bei Preis-Anstieg — echte Akkumulation. Funding noch nicht überhitzt. Institutional PCR von 0.41 signalisiert Call-Dominanz. ETF-Flows positiv letzte 3 Tage.",
      "risk_factors": ["Funding könnte in 2-4h überhitzen", "NDX-Korrelation hoch"],
      "suggested_sl": 0.009,
      "suggested_tp": 0.020
    },
    "layer3": {
      "blocker": false,
      "checked_against": ["Liquidation Wall: 0.31 BTC bei $83.100 (1.7% Abstand — OK)", "CVD: leicht positiv"]
    },
    "risk_gate": {
      "grss_check": "pass",
      "liq_wall_check": "pass",
      "cvd_divergence": "none",
      "daily_limit_check": "pass"
    }
  },
  "failure_watches_checked": [
    {"pattern": "fomo_long_squeeze", "active": false},
    {"pattern": "funding_extreme", "active": false}
  ],
  "execution": {
    "order_type": "limit",
    "post_only": true,
    "fill_price": 84502.0,
    "slippage_bps": 0.24,
    "latency_ms": 48
  }
}
```

### 2.2 Exit Report (nach Positionsschließung)

**Telegram (kompakt):**
```
✅ TAKE_PROFIT — LONG BTCUSDT
Exit: $85.270 | Held: 47 Min
P&L: +€0.84 (+1.02%) | Fees: -€0.008
MAE: -0.12% | MFE: +1.08%
→ Debrief läuft...
```

Oder bei Stop-Loss:
```
🔴 STOP_LOSS — LONG BTCUSDT
Exit: $83.745 | Held: 23 Min
P&L: -€0.76 (-0.89%) | Fees: -€0.008
MAE: -0.89% | MFE: +0.21%
→ Debrief läuft... Pattern-Analyse in 5 Min
```

### 2.3 Daily Review Report (täglich 23:55 UTC)

**Format:** Markdown-Datei + Telegram-Zusammenfassung

```markdown
# Bruno Daily Review — 2026-03-27

## Performance
- Trades: 3 (2 Long, 1 Short)
- Gewonnen: 2 | Verloren: 1 | Win Rate: 67%
- Brutto P&L: +€4.10 | Fees: -€0.25 | Netto: +€3.85
- Max Drawdown: -€0.76 (-0.15%)
- Daily Limit genutzt: 7.6% von 2%

## Signalqualität
- GRSS Durchschnitt: 64.2 (Bereich 55–71)
- Regime: ranging (ganztägig)
- Vetos ausgelöst: 4 (3× GRSS<40, 1× Liq-Wall)
- L2 Confidence Durchschnitt: 0.71

## Datenlage
- Alle Quellen: OK außer yFinance VIX (Fallback aktiv)
- Datenlücken: keine

## Lern-Updates
- 3 Debriefs abgeschlossen
- 1 neues Muster erkannt: "ranging_false_breakout"
- Failure Watches aktiv: 2

## Morgen beachten
- FOMC-Protokoll um 19:00 UTC → GRSS-Cap aktiv ab 17:00
- Deribit Options Expiry: kein Freitag diese Woche
```

### 2.4 Weekly Calibration Report (Sonntag 03:00 UTC)

**Zweck:** Semi-automatisches Lernprotokoll. Ruben genehmigt/lehnt ab.

```markdown
# Bruno Weekly Calibration — KW 13/2026

## Performance der Woche
- 23 Trades | PF: 1.73 | Sharpe: 1.12
- Beste Regime: trending_bull (81% WR, 12 Trades)
- Schlechteste Regime: ranging (48% WR, 8 Trades)

## GRSS-Kalibrierung
| GRSS-Range | Trades | Win Rate | Erwartung | Abweichung |
|---|---|---|---|---|
| 40–50 | 4 | 25% | 45% | -20% ⚠️ |
| 50–60 | 8 | 50% | 52% | -2% ✅ |
| 60–70 | 7 | 71% | 65% | +6% ✅ |
| 70–80 | 4 | 75% | 72% | +3% ✅ |

Problem: GRSS 40-50 underperformt deutlich.
→ Vorschlag: GRSS-Minimum-Threshold von 40 auf 48 erhöhen.

## Erkannte Muster diese Woche
1. "ranging_false_breakout" (2 Verluste) — neu erkannt
   → Beschreibung: OFI kurz positiv, dann sofort Reversal
   → Vorschlag: In ranging-Regime OFI-Threshold auf 650 erhöhen

## Parameter-Vorschläge (warten auf Genehmigung)
1. GRSS_Threshold: 40 → 48 (betrifft: ranging, high_vola Regime)
2. ranging.OFI_Threshold: 600 → 650
3. ranging.size_multiplier: 0.5 → 0.4

[Diese Vorschläge werden im Dashboard angezeigt]
[Ruben: GENEHMIGEN | ABLEHNEN | MANUELL ANPASSEN]
```

---

## 3. BACKUP-STRATEGIE

### 3.1 Was gesichert wird (Vollständigkeit)

| Komponente | Inhalt | Kritikalität |
|---|---|---|
| PostgreSQL DB | Alle Trades, Debriefs, Positionen, Candles, Lernhistorie | 🔴 Kritisch |
| Redis Snapshot | Aktueller State, GRSS-Cache, Veto-State | 🟠 Hoch |
| `config.json` | Aktive Parameter | 🔴 Kritisch |
| `optimized_params.json` | Letzte Kalibrierungsergebnisse | 🟠 Hoch |
| `failure_watches.json` | Aktive Failure-Watch-Liste | 🟠 Hoch |
| `pattern_library.json` | Gelernte Psychologie-Muster | 🟠 Hoch |
| `.env` | API-Keys (nur lokal, niemals cloud) | 🔴 Kritisch |
| Ollama Modelle | qwen2.5:14b, deepseek-r1:14b | 🟡 Mittel |

### 3.2 Backup-Zeitplan

```python
BACKUP_SCHEDULE = {
    "postgres_full": {
        "frequency": "täglich 02:00 UTC",
        "command": "pg_dump -Fc -Z9 bruno_trading > /backups/pg_{date}.dump",
        "retention": "14 Tage lokal, 90 Tage extern",
        "trigger": "n8n Scheduler oder cron"
    },
    "postgres_wal": {
        "frequency": "alle 6 Stunden",
        "retention": "48 Stunden",
        "note": "Für Point-in-Time Recovery bei offener Position"
    },
    "redis_snapshot": {
        "frequency": "stündlich",
        "command": "BGSAVE + cp dump.rdb /backups/redis_{timestamp}.rdb",
        "retention": "24 Stunden"
    },
    "config_versioning": {
        "frequency": "bei jeder Änderung",
        "storage": "/backups/config_history/config_{timestamp}.json",
        "note": "Vollständige History jeder Parameter-Änderung mit Zeitstempel und Begründung"
    },
    "learning_export": {
        "frequency": "wöchentlich Sonntag 02:00 UTC",
        "includes": ["pattern_library", "debrief_summaries", "calibration_history"],
        "format": "JSON + Markdown",
        "note": "Menschenlesbar UND maschinenlesbar"
    }
}
```

### 3.3 Redis Persistenz-Konfiguration (kritisch, oft vergessen)

Redis ist standardmäßig nur In-Memory. Bei Crash: alles weg.
**Pflicht-Konfiguration in `redis.conf`:**

```conf
# AOF (Append Only File) — jede Write-Operation wird geloggt
appendonly yes
appendfsync everysec        # Kompromiss: 1 Sekunde max Datenverlust
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB Snapshot zusätzlich
save 900 1                  # Nach 900s wenn mind. 1 Key geändert
save 300 10                 # Nach 300s wenn mind. 10 Keys geändert
save 60 10000               # Nach 60s wenn mind. 10000 Keys geändert

# Datei-Pfade (Docker Volume!)
dir /data
dbfilename dump.rdb
appendfilename "appendonly.aof"
```

**In `docker-compose.yml` sicherstellen:**
```yaml
redis:
  image: redis/redis-stack
  volumes:
    - redis_data:/data      # ← Dieser Volume muss existieren!
    - ./redis.conf:/redis-stack.conf
  command: redis-server /redis-stack.conf
```

### 3.4 Recovery-Verfahren — 3 Szenarien

**Szenario A: Neustart bei KEINER offenen Position (normal)**
```
1. Docker Compose up -d
2. PostgreSQL startet → Daten vollständig
3. Redis startet → lädt AOF/RDB → State rekonstruiert
4. Agenten starten → lesen State aus Redis
5. ContextAgent: nächster Zyklus in max. 15 Minuten
→ Kein manueller Eingriff nötig
```

**Szenario B: Crash bei OFFENER Position (kritisch)**
```
1. Sofort: Telegram-Alert "BRUNO CRASHED — POSITION OFFEN"
2. Ruben: Bybit manuell öffnen → Position prüfen
3. Entscheidung: Manuell schließen ODER warten auf Recovery
4. Docker Compose up -d
5. ExecutionAgent: liest Position aus Redis (AOF) ODER aus DB
6. Stop-Loss Watcher: startet sofort, schützt offene Position
7. Wenn Redis-State verloren: DB ist Fallback
   → positions Tabelle enthält status='open' → Recovery möglich
→ REGEL: Im Zweifel manuell schließen. Kapitalschutz vor Automatik.
```

**Szenario C: Datenbankkorruption (selten, aber vorbereiten)**
```
1. Letztes pg_dump laden
2. pg_restore -d bruno_trading /backups/pg_{latest}.dump
3. Lernhistorie: aus learning_export Sonntag JSON wiederherstellen
4. Pattern Library: aus /backups/pattern_library_{latest}.json
5. Config: aus config_history/ letzten genehmigten Stand laden
→ Datenverlust: max. 24 Stunden (akzeptabel für Lernhistorie)
→ Trade-History: max. 6 Stunden (WAL-Backup)
```

---

## 4. TECHNISCHE RESILIENCE — FAILSAFE-MATRIX

### 4.1 Was passiert wenn einzelne Komponenten ausfallen?

```python
FAILSAFE_MATRIX = {
    "binance_ws_down": {
        "detection": "Keine Nachricht > 30 Sekunden",
        "action": "Reconnect mit Exponential Backoff (bereits implementiert)",
        "fallback": "Binance REST polling alle 60s für Ticker-Daten",
        "trading_allowed": False,  # Kein Trading ohne Live-Daten
        "grss_override": 0,        # Hard-Stop
        "alert": "Telegram sofort"
    },
    "bybit_api_down": {
        "detection": "HTTP 5xx oder Timeout > 5s",
        "action": "3 Retry-Versuche mit je 2s Pause",
        "fallback": "Signal wird gespeichert, nicht ausgeführt",
        "trading_allowed": False,
        "alert": "Telegram + offene Positionen manuell prüfen"
    },
    "ollama_down": {
        "detection": "health_check schlägt fehl",
        "action": "LLM-Kaskade deaktivieren",
        "fallback": {
            "description": "Regel-basierter Fallback-Modus",
            "logic": "Nur Layer 4 (RiskAgent) aktiv. GRSS > 65 + OFI > Threshold → kleines Signal. Confidence = 0.50 (Minimum).",
            "position_size_multiplier": 0.3,  # Sehr kleine Positionen ohne LLM
            "note": "Bot handelt weiter, aber nur auf Basis von Regeln, nicht Reasoning"
        },
        "trading_allowed": True,   # Ja, aber sehr konservativ
        "alert": "Telegram: 'LLM OFFLINE — Fallback-Modus aktiv'"
    },
    "redis_down": {
        "detection": "Connection Error",
        "action": "Bot pausiert sofort",
        "fallback": "Kein Fallback — Redis ist der Kommunikationsbus",
        "trading_allowed": False,
        "alert": "Telegram kritisch"
    },
    "postgres_down": {
        "detection": "DB Connection Error beim Flush",
        "action": "Buffer hält Daten in Memory (max. 5 Min)",
        "fallback": "Agenten laufen weiter, nur kein DB-Write",
        "trading_allowed": True,   # Ja — Trade-Execution braucht keine DB
        "alert": "Telegram: 'DB OFFLINE — Memory-Buffer aktiv'"
    },
    "yfinance_429": {
        "detection": "HTTP 429 von Yahoo Finance",
        "action": "Sofort auf Stooq-Fallback wechseln",
        "fallback": "pdr.get_data_stooq('^VIX') und pdr.get_data_stooq('^NDX')",
        "trading_allowed": True,
        "alert": "Logging, kein Telegram (nicht kritisch)"
    }
}
```

### 4.2 NTP-Synchronisation (kritisch für Orders)

Bybit erfordert Timestamp innerhalb 5 Sekunden des Serverzeit.
Windows-Uhren können driften. Pflicht:

```python
class NTPWatchdog:
    """
    Überwacht lokale Uhrzeit-Drift gegen NTP-Server.
    Bei Drift > 3 Sekunden: Bot pausiert.
    """
    NTP_SERVER = "pool.ntp.org"
    MAX_DRIFT_SECONDS = 3.0

    async def check_time_drift(self) -> float:
        import ntplib
        c = ntplib.NTPClient()
        response = c.request(self.NTP_SERVER, version=3)
        drift = abs(response.offset)
        if drift > self.MAX_DRIFT_SECONDS:
            # Bot kann keine validen Orders mehr platzieren
            await self._emergency_pause(f"NTP Drift: {drift:.1f}s > {self.MAX_DRIFT_SECONDS}s")
        return drift
```

**Windows-Einstellung:** NTP-Synchronisation alle 5 Minuten erzwingen:
```batch
w32tm /config /manualpeerlist:"pool.ntp.org" /syncfromflags:manual /reliable:YES /update
```

### 4.3 Windows-Neustart-Handling

```yaml
# docker-compose.yml: restart policy für alle Services
services:
  bruno-api:
    restart: unless-stopped    # Startet nach Windows-Neustart automatisch
  bruno-worker:
    restart: unless-stopped
  postgres:
    restart: unless-stopped
  redis:
    restart: unless-stopped
```

**Windows Task Scheduler: Docker Desktop automatisch starten:**
```
Trigger: Bei Anmeldung
Aktion: "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

### 4.4 Ollama Fallback-Modus (genau definiert)

Wenn Ollama nicht erreichbar ist, MUSS der Bot eine klare Entscheidung treffen.

```python
class RuleBasedFallback:
    """
    Aktiviert wenn Ollama down ist.
    Kein LLM. Nur Regeln. Sehr konservativ.
    """

    def evaluate(self, data: dict) -> dict:
        grss = data['grss']
        ofi = data['ofi']
        funding = data['funding_rate']
        regime_config = REGIME_CONFIGS[data['regime']]

        # Strenge Kriterien ohne LLM
        if (grss >= 65 and
            abs(ofi) >= regime_config['OFI_Threshold'] * 1.2 and  # 20% höherer Threshold
            abs(funding) < 0.03 and
            data['oi_delta_pct'] > 0):

            side = "buy" if ofi > 0 else "sell"
            return {
                "decision": side.upper(),
                "confidence": 0.50,   # Minimum-Confidence
                "reasoning": f"Fallback-Modus: GRSS={grss}, OFI={ofi:.0f}, Funding={funding:.3%}",
                "source": "rule_based_fallback",
                "size_override": 0.3  # Nur 30% normale Größe
            }

        return {"decision": "HOLD", "reasoning": "Fallback-Modus: Kriterien nicht erfüllt"}
```

---

## 5. CONFIG-VERSIONING (Parameter-Transparenz)

Jede Parameter-Änderung wird versioniert und begründet:

```json
// /backups/config_history/config_2026-03-27T08:00:00Z.json
{
  "timestamp": "2026-03-27T08:00:00Z",
  "changed_by": "ruben_manual",
  "previous_config": {
    "GRSS_Threshold": 40,
    "ranging.OFI_Threshold": 600
  },
  "new_config": {
    "GRSS_Threshold": 48,
    "ranging.OFI_Threshold": 650
  },
  "reason": "Wöchentliche Kalibrierung KW13 — GRSS 40-50 underperformt (25% WR)",
  "calibration_report_ref": "calibration_2026-03-23.md",
  "approved_by": "ruben",
  "profit_factor_before": 1.73,
  "trades_basis": 23
}
```

---

## 6. MONITORING-ENDPOINTS

FastAPI stellt folgende Endpoints bereit (bereits im Code, erweitern):

```python
GET  /api/state/snapshot        # Aktueller JSON State Snapshot
GET  /api/state/health          # Alle Services: healthy/degraded/down
GET  /api/review/daily/{date}   # Daily Review als JSON
GET  /api/review/weekly/{week}  # Weekly Calibration Report
GET  /api/backup/status         # Letztes erfolgreiches Backup
POST /api/backup/trigger        # Manuelles Backup auslösen
GET  /api/config/history        # Alle Parameter-Änderungen
POST /api/config/approve        # Kalibrierungsvorschlag genehmigen
GET  /api/learning/patterns     # Aktuelle Pattern Library
GET  /api/learning/failure-watches  # Aktive Failure Watches
```

---

## 7. ALERT-HIERARCHIE

Nicht jedes Ereignis verdient dieselbe Aufmerksamkeit:

```python
ALERT_LEVELS = {
    "KRITISCH": {
        "channel": "Telegram sofort",
        "events": [
            "Bot crashed mit offener Position",
            "Redis down",
            "Daily Loss Limit erreicht",
            "Flash Crash erkannt",
            "NTP Drift > 3s",
            "Black Swan News erkannt"
        ]
    },
    "HOCH": {
        "channel": "Telegram sofort",
        "events": [
            "Bybit API down",
            "Binance WS disconnect > 2 Min",
            "Ollama offline → Fallback aktiv",
            "3 Verluste in Folge",
            "Neues Psychologie-Muster erkannt"
        ]
    },
    "MITTEL": {
        "channel": "Telegram gebündelt (1x/Stunde)",
        "events": [
            "Trade ausgeführt",
            "Position geschlossen",
            "Veto ausgelöst (mit Grund)",
            "Datenquelle degraded"
        ]
    },
    "INFO": {
        "channel": "Dashboard Log + Daily Report",
        "events": [
            "GRSS-Update",
            "Regime-Wechsel",
            "Debrief abgeschlossen",
            "Backup erfolgreich"
        ]
    }
}
```

---

*Dieses Dokument ist unveränderlich in seiner Review-Funktion.
Der Config-History-Teil wächst automatisch mit jeder Parameteränderung.*

*Repository: https://github.com/Kazuo3o447/Bruno*
