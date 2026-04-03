# BRUNO_LEARNING.md
# Bruno Trading Bot — Lern-Intelligenz & Psychologie-Architektur

> **PFLICHTLEKTÜRE für alle Agenten.**
> Dieses Dokument definiert wie Bruno lernt, sich anpasst und messbar besser wird.
> Es ist kein Feature — es ist das Fundament.
> Letzte Aktualisierung: 2026-04-02 (Critical Fixes & Config-Hot-Reload)

---

## 🎯 NEUE LERNERFAHRUNGEN (April 2026)

### Critical Fixes Lektionen (2. April 2026)
1. **Doppelte Prefix sind tödlich:** /api/v1/api/v1/ führt zu 404 und macht System unbenutzbar
2. **Fresh-Source-Gate ist entscheidend:** Ohne Health-Reporting für alle Quellen bleibt GRSS bei 0
3. **Config-Hot-Reload ist Game-Changer:** Agenten können live konfiguriert werden ohne Neustart
4. **OFI Schema muss realistisch sein:** min=10 statt 200 verhindert Slider-Probleme
5. **Preset-System verbessert UX:** Visuelle Presets reduzieren Konfigurationsfehler
6. **Startup Warm-Up vermeidet Start-Probleme:** Erste Datenabrufe sofort nach Start

### Port-Architektur Lektionen (31. März 2026)
7. **Hartcodierte Ports sind tödlich:** localhost:8001 im Frontend verursacht kompletten Systemausfall
8. **Environment-Konfiguration ist entscheidend:** DB_HOST=localhost vs DB_HOST=postgres macht den Unterschied zwischen funktionierend und kaputt
9. **WebSocket-Proxy wird oft vergessen:** /ws/* Proxy ist genauso wichtig wie /api/* Proxy
10. **Systematische Port-Korrektur ist notwendig:** 10+ Dateien müssen konsistent korrigiert werden, nicht nur eine

### Dashboard-Integration Lektionen
5. **Container-Netzwerk ist kritisch:** Docker-Netzwerk-Konfiguration kann API-Verbindung komplett verhindern
6. **Frontend-Proxy muss robust sein:** Next.js Rewrites benötigen exakte Service-Namen, nicht host.docker.internal
7. **Chart-Komponenten brauchen Cleanup:** "Object is disposed" Fehler ohne proper React Lifecycle Management
8. **API-Routing muss konsistent sein:** Fehlende Prefixe führen zu 404-Fehlern im Dashboard

### System-Integration Lektionen
9. **Vollständiger Neustart löst hartnäckige Probleme:** Docker-Container mit Volumes neu aufbauen
10. **Race Conditions sind häufig:** setTimeout und isDisposed Flags für Chart-Operationen
11. **WebSocket-Fehler überfluten Logs:** "Cannot call send once close message" braucht Verbindungsprüfung
12. **Health-Checks sind essenziell:** API-Endpunkte müssen auf Fehler reagieren können

---

## 0. WARUM DIESER BOT AB TAG 1 LERNEN MUSS

Der klassische Ansatz: Strategie entwickeln → backtesten → live schalten → fertig.
Das ist falsch. Hier ist warum:

**Der Markt März 2026 — die Realität:**
- BTC fiel von $90.000 auf $60.000 in 8 Tagen (Jan–Feb 2026). 50% Korrektur.
- Put-IV erreichte 95% am 5. Februar — höchster Wert seit 2022.
- Institutionelle (BlackRock IBIT: $263M an einem Tag) kauften genau in dieser Panik.
- BTC korreliert jetzt stärker mit Nasdaq als mit Gold.
- Energiepreise und Geopolitik (Straße von Hormuz) lösen sofortige Selloffs aus.
- Der klassische 4-Jahres-Halving-Zyklus wird durch institutionelle Dauerakkumulation verzerrt.

**Was das bedeutet:** Ein Bot der nur auf historischen Mustern basiert ist
beim Launch bereits veraltet. Märkte lernen auch — gegen den Bot.

**Die Soros-Reflexivität:** Märkte sind nicht neutral. Preis-Bewegungen erzeugen
Narrative, die neue Käufer/Verkäufer anziehen, die den Preis weiter bewegen.
Der Bot muss verstehen, WANN er in einem reflexiven Zyklus ist.

---

## 1. DIE 4 LERNEBENEN — HIERARCHISCH UND SEQUENZIELL

```
EBENE 1: Echtzeit-Kontext-Anpassung     (ab Tag 1, automatisch)
EBENE 2: Post-Trade Debrief + Muster    (ab Trade #1, täglich)
EBENE 3: Wöchentliche Regime-Kalibrierung (ab Woche 1, semi-automatisch)
EBENE 4: LLM Fine-Tuning               (ab Trade #500, manuell)
```

---

## 2. EBENE 1 — ECHTZEIT-KONTEXT-ANPASSUNG (automatisch, keine Freigabe)

Diese Ebene läuft vollautomatisch innerhalb unveränderlicher Grenzen.
Kein menschlicher Eingriff nötig. Keine Freigabe. Immer aktiv.

### 2.1 Volatility-Adjusted Position Sizing

Nicht jeder Tag hat dasselbe Risiko. Der Bot skaliert automatisch:

```python
class VolatilityAdjuster:
    """
    Passt Positionsgröße an aktuelle Marktvolatilität an.
    Basis: ATR (Average True Range) normalisiert über 14 Perioden.
    """

    def calculate_atr_multiplier(self, atr_14: float,
                                  atr_baseline: float) -> float:
        """
        atr_14: Aktueller 14-Perioden ATR (aus Binance Klines)
        atr_baseline: Historischer Durchschnitt ATR (aus DB, rolling 90 Tage)

        Rückgabe: Multiplikator 0.25 – 1.0
        """
        ratio = atr_14 / atr_baseline if atr_baseline > 0 else 1.0

        if ratio < 0.8:     return 1.0    # Ruhiger Markt: volle Größe
        elif ratio < 1.2:   return 0.8    # Normal: leicht reduziert
        elif ratio < 1.8:   return 0.6    # Erhöht: deutlich kleiner
        elif ratio < 2.5:   return 0.4    # Hoch: minimal
        else:               return 0.25   # Extrem (wie Feb 2026): fast nichts

    def calculate_dvol_multiplier(self, dvol: float) -> float:
        """
        dvol: Deribit DVOL Index (BTC Implied Volatility, annualisiert)
        Historische Orientierung: 40-60% normal, 80%+ = Stress
        """
        if dvol < 45:       return 1.0
        elif dvol < 60:     return 0.8
        elif dvol < 75:     return 0.6
        elif dvol < 95:     return 0.35   # Feb 5, 2026: DVOL bei 95% → minimale Größe
        else:               return 0.2
```

**Konsequenz:** In der Feb-2026-Panik (DVOL 95%, ATR 3×) hätte der Bot
automatisch auf 25% × 0.2 = 5% der normalen Positionsgröße skaliert.
Das ist der Unterschied zwischen Überleben und Totalverlust.

### 2.2 Dynamic Stop-Loss Expansion

Normaler Stop-Loss in ruhigem Markt: 0.8%.
Wenn ATR hoch ist, bedeutet 0.8% bei jedem Tick ein Stop-Out.
Der Bot passt automatisch an:

```python
def calculate_dynamic_sl(self, base_sl_pct: float,
                          atr_14: float,
                          atr_baseline: float,
                          current_price: float) -> float:
    """
    Berechnet dynamischen Stop-Loss basierend auf ATR.
    Nie größer als 2× Basis-SL.
    """
    atr_in_pct = atr_14 / current_price
    atr_ratio = atr_14 / atr_baseline if atr_baseline > 0 else 1.0

    dynamic_sl = max(base_sl_pct, atr_in_pct * 1.5)
    max_sl = base_sl_pct * 2.0
    return min(dynamic_sl, max_sl)
```

### 2.3 Correlation Watchdog (NEU — Institutionelles Signal)

BTC korreliert 2026 stark mit Nasdaq. Wenn diese Korrelation plötzlich bricht
(Decoupling) → starkes institutionelles Signal:

```python
class CorrelationWatchdog:
    """
    Überwacht BTC vs NDX Korrelation (Rolling 20 Tage).
    Korrelations-Bruch = Regime-Warnung ODER Alpha-Opportunity.
    """

    async def get_correlation_signal(self) -> dict:
        # Berechnet aus Binance BTC Klines + Yahoo NDX Daten
        correlation_20d = self._calculate_rolling_correlation(
            btc_returns=self.btc_daily_returns[-20:],
            ndx_returns=self.ndx_daily_returns[-20:]
        )

        signal = {
            "correlation": correlation_20d,
            "regime": None,
            "grss_modifier": 0.0
        }

        if correlation_20d > 0.75:
            signal["regime"] = "btc_follows_macro"
            signal["grss_modifier"] = 0.0   # Normal — VIX und NDX gelten
        elif correlation_20d < 0.30:
            signal["regime"] = "btc_decoupling"
            signal["grss_modifier"] = +8.0  # Institutionelles Buying — GRSS erhöhen
        elif correlation_20d < 0:
            signal["regime"] = "btc_inverse_macro"
            signal["grss_modifier"] = +15.0 # Seltenes Regime — BTC als Safe Haven

        return signal
```

**VIX Datenquelle (✅ FIXED 30.03.2026):**
```python
# CBOE CSV als primäre Quelle (offiziell, zuverlässig)
cboe_resp = await client.get(
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    timeout=10.0
)
if cboe_resp.status_code == 200:
    lines = cboe_resp.text.strip().split("\n")
    last = lines[-1].split(",")
    vix = float(last[4])  # CLOSE-Spalte
    # Ergebnis: VIX 31.05 (echte Marktdaten)

# Fallback-Hierarchie:
# 1. CBOE CSV (primär) - Offizielle Quelle, keine Rate Limits
# 2. Yahoo Finance (fallback) - Real-time aber 429-anfällig  
# 3. Alpha Vantage (final) - TIME_SERIES_DAILY
```

---

## 3. EBENE 2 — POST-TRADE DEBRIEF (täglich, automatisch + Dokumentation)

Nach JEDEM geschlossenen Trade. Kein Trade ohne Debrief.

### 3.1 Der vollständige Debrief-Prompt

```python
DEBRIEF_PROMPT = """
Du bist der Lern-Agent des Bruno Trading Systems.
Analysiere diesen Trade vollständig. Sei hart. Sei ehrlich. Keine Beschönigung.

═══ TRADE-DATEN ═══
Symbol: {symbol} | Seite: {side} | Regime: {regime}
Entry: ${entry_price} @ {entry_time}
Exit: ${exit_price} @ {exit_time} ({exit_reason})
P&L: {pnl_pct:.2%} | Haltezeit: {hold_minutes} Min
MAE (Max Adverse Excursion): {mae_pct:.2%}
MFE (Max Favorable Excursion): {mfe_pct:.2%}

═══ SIGNALE BEI ENTRY ═══
GRSS: {grss} | Komponenten: {grss_breakdown}
Layer 1: Regime={l1_regime}, Confidence={l1_confidence}
Layer 2: Decision={l2_decision}, Confidence={l2_confidence}
Layer 2 Reasoning: {l2_reasoning}
Layer 3 Blocker: {l3_blocker} | Gründe: {l3_reasons}
Funding Rate: {funding_rate} | PCR: {pcr} | OI-Delta: {oi_delta}

═══ MARKTKONTEXT ═══
ATR-Ratio: {atr_ratio} | DVOL: {dvol} | VIX: {vix} (✅ CBOE CSV Echtzeit)
Corr BTC/NDX: {btc_ndx_correlation}
Letzte 3 Entscheidungen: {decision_history}

Beantworte folgende Fragen als JSON:
{{
    "decision_quality": "correct|incorrect|timing_error|signal_error|exit_error",
    "primary_failure_point": "entry|exit|sizing|signal|regime|none",
    "was_regime_correct": true/false,
    "was_layer2_reasoning_valid": true/false,
    "key_insight": "Ein Satz. Was war das wichtigste Lern-Signal?",
    "pattern_detected": "Hat dieser Trade ein bekanntes Muster? Welches?",
    "psychological_factor": "Welche Marktpsychologie war dominant?",
    "what_should_change": "Konkret: Was soll der Bot beim nächsten ähnlichen Setup anders machen?",
    "grss_calibration_feedback": {{
        "grss_was_accurate": true/false,
        "grss_should_have_been": "höher|niedriger|korrekt",
        "which_component_failed": "makro|derivatives|sentiment|none"
    }},
    "regime_feedback": {{
        "actual_regime": "trending_bull|ranging|high_vola|bear|unknown",
        "regime_config_was_appropriate": true/false,
        "suggested_sl_pct": null or float,
        "suggested_tp_pct": null or float
    }},
    "confidence_calibration": {{
        "l2_confidence_was_appropriate": true/false,
        "actual_success_probability": "war die confidence von {l2_confidence} realistisch?"
    }}
}}
"""
```

### 3.2 Der "Hinterkopf" — Persistentes Failure Memory

Das ist der wichtigste Mechanismus. Ein Verlust darf nicht in der DB
verschwinden — er muss in JEDE zukünftige Entscheidung einfließen.

```python
class FailureWatchList:
    """
    Aktive Failure Watches werden bei JEDEM Layer-2-Call injiziert.
    Redis (aktiv) + DB (persistent) + failure_watches.json (Backup).
    """
    REDIS_KEY = "bruno:learning:failure_watches"

    async def add_watch(self, pattern: str, context: dict,
                        severity: str, expires_after_trades: int = 20):
        watch = {
            "id": str(uuid4()),
            "pattern": pattern,
            "context_when_detected": context,
            "severity": severity,          # "critical"|"high"|"medium"
            "loss_pct": context.get("pnl_pct"),
            "expires_after_trades": expires_after_trades,
            "trades_since_added": 0,
            "repetitions": 0,
            "active": True,
            "injection_text": self._generate_injection(pattern, context)
        }
        # Verfalls-Logik:
        # Normal: nach 20 Trades inaktiv (wenn nicht wiederholt)
        # Bei Wiederholung: +15 Trades Verlängerung
        # Critical: 50 Trades
        # Permanent (Schwarze Schwäne): 9999 Trades

    def _generate_injection(self, pattern: str, context: dict) -> str:
        return (
            f"WARNUNG AUS VERGANGENEM TRADE: "
            f"Muster '{pattern}' führte zu {context.get('loss_pct', 0):.1%} Verlust "
            f"(Regime: {context.get('regime')}, GRSS: {context.get('grss', 0):.0f}). "
            f"Sei kritisch wenn ähnliche Bedingungen vorliegen."
        )

    async def get_injection_context(self, current_data: dict) -> str:
        """Wird bei JEDEM Layer-2-Aufruf aufgerufen."""
        watches = await self.get_active_watches()
        relevant = [
            w['injection_text'] for w in watches
            if w['active'] and (
                w['context_when_detected'].get('regime') == current_data.get('regime') or
                abs(w['context_when_detected'].get('grss', 50) - current_data.get('grss', 50)) < 15
            )
        ]
        if not relevant:
            return ""
        return "\n\nAKTIVE LERN-WARNUNGEN:\n" + "\n".join(f"• {r}" for r in relevant)
```

**Integration in Layer-2:**
```python
failure_context = await failure_watch_list.get_injection_context(current_data)
layer2_prompt = f"{base_market_context}\n{failure_context}\nEntscheide: BUY/SELL/HOLD?"
```

### 3.3 Die Debrief-Datenbank als Lerngedächtnis

Jeder Debrief wird nicht nur gespeichert — er wird **aktiv genutzt**:

```python
class DebriefMemory:
    """
    Das kumulative Lerngedächtnis des Bots.
    Wird bei Layer 2 als Rolling Context mitgegeben.
    """

    async def get_relevant_debriefs(self,
                                    current_regime: str,
                                    current_setup: dict,
                                    limit: int = 5) -> list:
        """
        Holt die ähnlichsten vergangenen Trades aus der DB.
        Ähnlichkeit nach: Regime + GRSS-Range + Funding-Level.
        """
        query = """
            SELECT
                td.decision_quality,
                td.key_insight,
                td.pattern_detected,
                td.psychological_factor,
                td.what_should_change,
                p.pnl_pct,
                p.grss_at_entry,
                p.regime_at_entry
            FROM trade_debriefs td
            JOIN positions p ON td.position_id = p.id
            WHERE p.regime_at_entry = :regime
            AND ABS(p.grss_at_entry - :grss) < 15
            ORDER BY p.entry_time DESC
            LIMIT :limit
        """
        # Diese Debriefs werden als Kontext an Layer 2 übergeben:
        # "In ähnlichen Situationen hat der Bot folgendes gelernt: ..."
```

### 3.3 Psychologie-Muster-Bibliothek (wächst automatisch)

Jeder Debrief kategorisiert den dominanten psychologischen Faktor.
Nach 50 Trades entsteht eine eigene Musterbibliothek:

```python
PSYCHOLOGICAL_PATTERNS = {
    "fomo_long_squeeze": {
        "description": "Preis steigt stark, Funding explodiert, alle kaufen spät",
        "detection": "funding > 0.05% UND price_change_1h > 2% UND pcr < 0.35",
        "historical_outcome": "80% Chance auf Reversal innerhalb 4h",
        "recommended_action": "KEIN Long. Short-Opportunity oder Warten.",
        "grss_penalty": -20
    },
    "capitulation_bottom": {
        "description": "Panikverkäufe, IV explodiert, ETF-Flows werden positiv",
        "detection": "dvol > 80 UND pcr > 0.90 UND etf_flows_1d > 200M",
        "historical_outcome": "Meist Boden. Reversal in 24-72h",
        "recommended_action": "Vorsichtiger Long. Kleines Sizing. Weiter SL.",
        "grss_bonus": +15,
        "example": "5. Februar 2026 — BTC bei $60k, DVOL 95%, PCR 1.1"
    },
    "institutional_accumulation": {
        "description": "Preis fällt, aber ETF-Inflows massiv positiv",
        "detection": "btc_change_24h < -3% UND etf_flows_1d > 300M",
        "historical_outcome": "Starkes Boden-Signal. 2-5 Tage bis Reversal.",
        "recommended_action": "Long bias. GRSS normal bewerten.",
        "grss_bonus": +10,
        "example": "März 2026 — BTC bei $66k, IBIT +$263M"
    },
    "liquidity_cascade": {
        "description": "Preisfall löst Liquidationskaskade aus, OI bricht ein",
        "detection": "oi_delta_pct < -5% UND price_change_1h < -3%",
        "historical_outcome": "Kurzfristig heftiger, dann oft Reversal",
        "recommended_action": "KEIN Trade während der Kaskade. Warten bis OI stabilisiert.",
        "grss_penalty": -30
    },
    "reflexive_narrative": {
        "description": "Narrativ verstärkt sich selbst: Preis steigt → Narrativ bullisch → mehr Käufer",
        "detection": "llm_sentiment_velocity > 0.3 UND price_change_3d > 8%",
        "historical_outcome": "Kann lange laufen. Aber Ende ist abrupt.",
        "recommended_action": "Mit Trend. Trailing Stop statt festem TP.",
        "grss_modifier": 0  # Neutral — Trend beachten
    },
    "geopolitical_shock": {
        "description": "Geopolitisches Ereignis löst Risiko-Off Bewegung aus",
        "detection": "vix_spike > 20% in 1h UND news_sentiment < -0.7 (✅ VIX via CBOE CSV)",
        "historical_outcome": "Initial panic. Oft Erholung in 12-48h wenn keine Eskalation.",
        "recommended_action": "KEIN Trade in ersten 2h. Dann beobachten.",
        "grss_penalty": -25
    },
    "etf_rotation": {
        "description": "Institutionelle wechseln zwischen BTC-ETF und Risk-Assets",
        "detection": "coinbase_premium < -0.3 UND correlation_btc_ndx > 0.80",
        "historical_outcome": "BTC folgt Nasdaq. Macro-Daten wichtiger als Crypto-Daten.",
        "recommended_action": "VIX und NDX stärker gewichten als Funding-Rate.",
        "grss_modifier": 0  # GRSS-Gewichte adjustieren: Makro +10%
    },
    "halving_fatigue": {
        "description": "Post-Halving Euphorie klingt ab, Institutionelle nehmen Gewinne",
        "detection": "Zyklus-Kontext: >12 Monate nach Halving",
        "historical_outcome": "Historisch: 6-18 Monate nach Halving Topping-Phase",
        "recommended_action": "GRSS-Schwelle erhöhen. Kleinere Positionen.",
        "grss_penalty": -5  # Permanenter Kontext-Abzug
    }
}
```

---

## 4. EBENE 3 — WÖCHENTLICHE REGIME-KALIBRIERUNG

Jeden Sonntag, 03:00 UTC (wenn keine Position offen ist).

### 4.1 Der Kalibrierungs-Algorithmus

```python
class WeeklyCalibration:
    """
    Analysiert die Woche und passt Regime-Configs an.
    OUTPUT: Vorschlag für neue Parameter (keine automatische Übernahme!).
    """

    async def run_calibration(self) -> CalibrationReport:
        # 1. Letzte 7 Tage Trades aus DB
        trades = await self._get_week_trades()

        # 2. Performance pro Regime
        regime_stats = self._calculate_regime_performance(trades)

        # 3. GRSS-Kalibrierung: War GRSS=X wirklich mit positiven Outcomes verbunden?
        grss_calibration = self._calibrate_grss_accuracy(trades)

        # 4. Layer 2 Confidence Kalibrierung
        confidence_calibration = self._calibrate_confidence(trades)

        # 5. Optuna Optimierung (falls genug Daten: > 20 Trades)
        if len(trades) >= 20:
            optimized_params = await self._run_optuna_optimization(trades)
        else:
            optimized_params = None

        return CalibrationReport(
            regime_stats=regime_stats,
            grss_calibration=grss_calibration,
            confidence_calibration=confidence_calibration,
            optimized_params=optimized_params,
            requires_human_review=True  # IMMER Mensch entscheidet
        )

    def _calibrate_grss_accuracy(self, trades: list) -> dict:
        """
        Beantwortet: War GRSS=70 tatsächlich mit guten Trades verbunden?
        Oder: Überschätzt GRSS die Lage systematisch?
        """
        buckets = {
            "40-50": [], "50-60": [], "60-70": [],
            "70-80": [], "80-90": [], "90-100": []
        }

        for trade in trades:
            grss = trade.grss_at_entry
            bucket_key = f"{(grss//10)*10}-{(grss//10)*10+10}"
            if bucket_key in buckets:
                buckets[bucket_key].append(trade.pnl_pct)

        calibration = {}
        for bucket, pnls in buckets.items():
            if len(pnls) >= 3:
                calibration[bucket] = {
                    "trades": len(pnls),
                    "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
                    "avg_pnl": sum(pnls) / len(pnls),
                    "grss_was_accurate": sum(1 for p in pnls if p > 0) / len(pnls) > 0.55
                }

        return calibration
```

### 4.2 Messbarkeit — Die 8 Kern-KPIs

Diese KPIs werden wöchentlich berechnet und im Dashboard angezeigt.
**Trend ist wichtiger als absoluter Wert.**

```python
LEARNING_KPIS = {
    # ═══ PERFORMANCE KPIS ═══
    "profit_factor_trend": {
        "description": "PF rolling 4 Wochen. Muss > 1.5 bleiben.",
        "calculation": "gross_profit / gross_loss (inkl. Fees)",
        "alarm_threshold": 1.2,
        "target": 2.0,
        "measurement": "wöchentlich"
    },
    "sharpe_ratio_trend": {
        "description": "Risiko-adjustierte Rendite. Verbessert sich der Bot?",
        "calculation": "(avg_return - risk_free_rate) / std_return * sqrt(52)",
        "alarm_threshold": 0.8,
        "target": 1.5,
        "measurement": "wöchentlich"
    },
    "max_drawdown_trend": {
        "description": "Sinkt der maximale Drawdown über Zeit?",
        "calculation": "peak_to_trough / peak * 100",
        "alarm_threshold": 15.0,  # % des Kapitals
        "target": 5.0,
        "measurement": "fortlaufend"
    },

    # ═══ SIGNAL-QUALITÄTS KPIS ═══
    "grss_calibration_score": {
        "description": "Wie gut sagt GRSS>65 positive Outcomes voraus?",
        "calculation": "win_rate bei GRSS > 65 / erwartete win_rate",
        "alarm_threshold": 0.7,  # Unter 70% → GRSS-Formel überdenken
        "target": 0.75,
        "measurement": "wöchentlich (nach mind. 10 Trades)"
    },
    "layer2_confidence_calibration": {
        "description": "Ist L2-Confidence=0.8 wirklich in 80% erfolgreich?",
        "calculation": "actual_win_rate bei Confidence > X vs stated X",
        "alarm_threshold": 0.15,  # Abweichung > 15% → Kalibrierungsproblem
        "target": 0.05,           # Abweichung < 5% = gut kalibriert
        "measurement": "wöchentlich"
    },
    "regime_accuracy": {
        "description": "Wie oft war die Regime-Klassifizierung korrekt?",
        "calculation": "regime_was_correct / total_trades (aus Debrief)",
        "alarm_threshold": 0.60,
        "target": 0.80,
        "measurement": "wöchentlich"
    },

    # ═══ LERN-GESCHWINDIGKEIT KPIS ═══
    "debrief_pattern_utilization": {
        "description": "Werden erkannte Muster tatsächlich vermieden?",
        "calculation": "trades mit bekanntem negative pattern / total trades",
        "alarm_threshold": 0.15,  # > 15% Wiederholung = Bot lernt nicht
        "target": 0.05,
        "measurement": "wöchentlich"
    },
    "improvement_velocity": {
        "description": "Verbesserungsrate pro 50 Trades",
        "calculation": "(pf_last_50 - pf_first_50) / pf_first_50",
        "alarm_threshold": -0.10,  # Verschlechterung > 10% = Problem
        "target": 0.15,            # 15% Verbesserung pro 50 Trades
        "measurement": "je 50 Trades"
    }
}
```

---

## 5. DAS AKTUELLE MARKT-REGIME VERSTEHEN (März 2026)

**Was wir aktuell wissen und wie der Bot damit umgehen muss:**

### 5.1 Das fragile Rebound-Regime

BTC hat sich von $60k auf ~$75k erholt, ist aber noch im "High-Risk Regime".
On-Chain: Realized P/L Ratio unter 2 → fragile Liquidität.

```python
CURRENT_REGIME_CONTEXT = {
    "regime": "fragile_rebound",
    "description": "Post-Kapitulation, aber noch nicht klarer Bull-Trend",
    "key_characteristics": [
        "BTC/NDX Korrelation hoch (0.70+) → Makro dominiert",
        "ETF-Inflows positiv (institutionelles Buying) → Support",
        "Funding Rate normalisiert aber noch sensibel",
        "25-Delta Risk Reversal noch negativ → Downside-Angst bleibt",
        "Energiepreise + Geopolitik = externe Schock-Risiken"
    ],
    "bot_implications": {
        "regime_config": "ranging",  # Nicht trending_bull trotz Erholung
        "grss_bias": -5,             # Konservativer als normal
        "preferred_setups": ["institutional_accumulation", "capitulation_bottom"],
        "avoid": ["fomo_long_squeeze", "high_leverage_long"],
        "stop_loss_multiplier": 1.3   # Weiterer SL wegen höherer Vola
    }
}
```

### 5.2 Der institutionelle Rhythmus (2026)

Institutional ETF-Käufer haben einen erkennbaren Rhythmus geschaffen:

```
MUSTER: ETF-Ausflüsse → Preis fällt → Panik → ETF-Zuflüsse explodieren → Erholung
TIMING: Selloff dauert 1-3 Tage. Erholung dauert 3-7 Tage.
SIGNAL: Wenn IBIT-Flows > $200M/Tag während Preisrückgang → Strong Buy Signal

IMPLEMENTATION:
- CoinGlass ETF-Flow API: Täglicher Wert
- Wenn flows_1d > 200M UND btc_change_24h < -3% → Muster erkannt → GRSS +15
```

### 5.3 Geopolitik-Response-Muster

Neu in 2026: Geopolitische Schocks (Energiekrise, Naher Osten) lösen sofortige BTC-Selloffs aus.
Historisch: Erholung in 12-48h wenn keine Eskalation.

```python
class GeopoliticalShockDetector:
    """
    Erkennt geopolitische Schocks aus News-Sentiment + VIX-Spike Kombination.
    VIX-Daten via CBOE CSV (✅ zuverlässig, 31.05 aktuell)
    """

    async def detect_shock(self, data: dict) -> dict:
        news_sentiment = data['llm_news_sentiment']
        vix_change_1h = data['vix_change_1h']
        vix_level = data['vix']  # Echtzeit von CBOE CSV

        # Schock-Kriterien
        sentiment_crash = news_sentiment < -0.65
        vix_spike = vix_change_1h > 15  # 15% VIX-Anstieg in 1h
        vix_elevated = vix_level > 22

        if sentiment_crash and vix_spike and vix_elevated:
            return {
                "shock_detected": True,
                "severity": "high" if vix_change_1h > 25 else "medium",
                "grss_override": 15,    # Hard-Cap: max GRSS=15 für 4h
                "cooling_period_hours": 4,
                "pattern": "geopolitical_shock"
            }
        return {"shock_detected": False}
```

---

## 6. EBENE 4 — LLM FINE-TUNING (ab Trade #500)

### 6.1 Wann beginnt das Fine-Tuning?

- Mindestens 500 abgeschlossene Trades in trade_debriefs
- Davon mindestens 100 pro Regime
- Mindestens 6 Monate Daten
- Aktueller Profit Factor > 1.5 (der Bot muss bereits funktionieren)

### 6.2 Der Datensatz

```python
# Jeder Trade wird als Trainings-Sample aufbereitet:
TRAINING_SAMPLE = {
    "input": {
        "market_context": {
            "grss": 67.5,
            "regime": "trending_bull",
            "funding_rate": 0.012,
            "pcr": 0.41,
            "oi_delta": +2.3,
            "perp_basis": 0.03,
            "dvol": 52,
            "vix": 31.05,  # ✅ Echtzeit von CBOE CSV (Market Stress)
            "ndx_status": "BULLISH",
            "correlation_btc_ndx": 0.72,
            "fear_greed": 71
        },
        "pattern_matches": ["institutional_accumulation"],
        "similar_past_trades": [...]  # Aus DebriefMemory
    },
    "expected_output": {
        "decision": "BUY",
        "confidence": 0.78,
        "reasoning": "OI steigt bei Preis-Anstieg = echte Akkumulation...",
        "sl_pct": 0.009,
        "tp_pct": 0.022
    },
    "actual_outcome": {
        "pnl_pct": +1.48,
        "exit_reason": "TAKE_PROFIT",
        "decision_quality": "correct"
    }
}
```

### 6.3 Hardware-Upgrade-Plan für Fine-Tuning

**Aktuell (Windows, Phase A-G):**
```
qwen2.5:14b  (~9GB VRAM) — Layer 1 + Layer 3
deepseek-r1:14b (~9GB VRAM) — Layer 2
→ Beide im 20GB VRAM: paralleles Vorladen möglich → ~3-5s Kaskade
```

**Nach Linux-Migration (Phase H+):**
```
ROCm auf RX 7900 XT (RDNA3) → volle GPU-Beschleunigung
qwen2.5:32b (~19GB VRAM) — Layer 1: bessere Klassifizierung
deepseek-r1:14b (~9GB VRAM) — Layer 2: bleibt
→ 32b für Layer 1 passt alleine in den VRAM
→ Wechsel Layer 1 → Layer 2: Modell-Swap (~2s) + Inferenz (~4s)
→ Gesamte Kaskade: ~8-10s — auf 15-Min-Zeitebene kein Problem

qwen2.5:32b vs qwen2.5:14b:
→ Regime-Klassifizierung: ~20% besser auf komplexen Marktlagen
→ Psychologie-Muster-Erkennung: deutlich besser
→ Besonders relevant für: fragile_rebound, geopolitical_shock, reflexive_narrative
```

**Fine-Tuning auf Linux:**
```bash
# Ollama Custom Model aus Fine-Tuning-Datensatz
ollama create bruno-quant-v1 -f ./Modelfile

# Modelfile:
FROM qwen2.5:32b
SYSTEM "Du bist Bruno, ein spezialisierter Bitcoin-Trading-Analyst..."
# + alle gelernten Muster als System-Prompt injiziert
```

---

## 7. SCHWARZE SCHWÄNE & AUSNAHME-EVENTS

Der Bot muss Situationen kennen in denen er NICHTS tun soll.

### 7.1 Auto-Pause Triggers (sofort, keine Diskussion)

```python
AUTO_PAUSE_TRIGGERS = [
    {
        "name": "flash_crash_detected",
        "condition": "price_change_5min < -5%",
        "action": "alle offenen Positionen sofort schließen, Bot pausiert 4h",
        "reason": "Liquidationskaskade läuft — kein fairer Preis möglich"
    },
    {
        "name": "exchange_anomaly",
        "condition": "binance_ws_reconnects > 3 in 10min ODER latency > 5000ms",
        "action": "Bot pausiert bis stabile Verbindung 5 Min bestätigt",
        "reason": "Datenqualität nicht garantiert"
    },
    {
        "name": "funding_extreme",
        "condition": "funding_rate > 0.1% ODER funding_rate < -0.05%",
        "action": "Nur Gegenrichtung erlaubt (Long bei extrem negativem Funding)",
        "reason": "Extreme Funding = unmittelbares Reversal-Risiko"
    },
    {
        "name": "daily_loss_limit",
        "condition": "daily_pnl < -2% des Kontos",
        "action": "Bot pausiert bis 00:00 UTC",
        "reason": "Tagesregel — verhindert Revenge Trading"
    },
    {
        "name": "consecutive_losses",
        "condition": "3 Verluste in Folge",
        "action": "Positionsgröße halbieren für nächste 10 Trades",
        "reason": "Muster-Erkennung: Strategie passt nicht zum aktuellen Markt"
    },
    {
        "name": "black_swan_news",
        "condition": "news_sentiment < -0.85 UND vix_change_1h > 30% (✅ VIX via CBOE)",
        "action": "Bot pausiert 8h, Telegram-Alert an Ruben",
        "reason": "Unbekanntes Regime — erst Lage verstehen"
    }
]
```

### 7.2 Bekannte Kalender-Events (GRSS-Override)

```python
CALENDAR_EVENTS = [
    {
        "event": "FOMC_Entscheidung",
        "timing": "2h vor + 2h nach der Ankündigung",
        "grss_max": 35,  # Unter Veto-Schwelle → kein Trading
        "reason": "Unberechenbare Liquiditätssprünge"
    },
    {
        "event": "BTC_Options_Expiry_Deribit",
        "timing": "jeden letzten Freitag im Monat, 8:00 UTC",
        "grss_max": 40,
        "reason": "Max-Pain Magnetismus kann irrational sein"
    },
    {
        "event": "US_CPI_Daten",
        "timing": "30min vor + 1h nach Veröffentlichung",
        "grss_max": 35,
        "reason": "BTC/Makro Korrelation 2026 macht CPI zum Marktmover"
    },
    {
        "event": "Wochenende_Niedrige_Liquidität",
        "timing": "Samstag 22:00 UTC bis Sonntag 22:00 UTC",
        "grss_adjustment": -5,  # Konservativer, aber nicht blockiert
        "reason": "Niedrige Liquidität = höhere Slippage"
    }
]
```

---

## 8. DAS LERN-DASHBOARD (Frontend-Anforderungen)

Ein eigener Tab "Lern-Zentrale" im Frontend:

### 8.1 Pflicht-Widgets

**KPI-Trend-Chart (wöchentlich):**
```
Profit Factor:    ████████░░  1.73 (↑ von 1.41 vor 4 Wochen)
Sharpe Ratio:     ██████░░░░  1.12 (↑ von 0.87)
GRSS Accuracy:    ████████░░  76%  (↑ von 68%)
L2 Calibration:   ███████░░░  8% Abweichung (↓ von 14%)
Regime Accuracy:  ████████░░  78%  (↑ von 65%)
```

**Muster-Bibliothek (wächst automatisch):**
```
Erkannte Muster:        8 / 12 dokumentiert
Häufigstes Muster:      institutional_accumulation (12×)
Erfolgreichstes:        capitulation_bottom (83% WR)
Gefährlichstes:         fomo_long_squeeze (23% WR — wird jetzt vermieden)
```

**GRSS-Kalibrierungs-Heatmap:**
```
GRSS 40-50: 8 Trades, 38% WR  ← unter Erwartung
GRSS 50-60: 12 Trades, 52% WR ← leicht unter
GRSS 60-70: 18 Trades, 64% WR ← gut
GRSS 70-80: 15 Trades, 72% WR ← sehr gut
GRSS 80+:   6 Trades, 75% WR  ← zu wenige Daten
```

**Kalibrierungs-Vorschlag (wöchentlich):**
```
Diese Woche analysiert: 23 Trades
Vorschlag für Review:
  → GRSS-Threshold erhöhen von 40 auf 45 (trending_bull Regime)
  → Layer 2 Confidence Minimum erhöhen von 0.65 auf 0.68
  → Stop-Loss in high_vola Regime: +0.003 Punkte
  [GENEHMIGEN] [ABLEHNEN] [DETAILS]
```

---

## 9. IMPLEMENTIERUNGS-CHECKLISTE (Lernebenen)

### Phase A (sofort aktiv — kein Extra-Aufwand)
- [ ] ATR-Berechnung in QuantAgent hinzufügen (aus Klines bereits vorhanden)
- [ ] VolatilityAdjuster in ExecutionAgent verdrahten
- [ ] Dynamic Stop-Loss in Position Sizing einbauen
- [ ] DVOL aus Deribit API (bereits in Plan) in ATR-Multiplier einbauen

### Phase C (mit LLM-Kaskade)
- [ ] Debrief-Prompt implementieren (Abschnitt 3.1)
- [ ] DebriefMemory Klasse bauen
- [ ] Psychologie-Muster-Bibliothek als Enum/Dict im Code
- [ ] GeopoliticalShockDetector implementieren
- [ ] CorrelationWatchdog implementieren
- [ ] Kalender-Events-Check in ContextAgent
- [ ] Auto-Pause-Triggers in RiskAgent

### Phase D (mit Position Tracker)
- [ ] MFE (Max Favorable Excursion) tracking hinzufügen
- [ ] Consecutive Loss Counter
- [ ] Daily Loss Limit Hardware-Block

### Phase E (Frontend)
- [ ] Lern-Zentrale Tab
- [ ] KPI-Trend-Chart
- [ ] Muster-Bibliothek Widget
- [ ] GRSS-Kalibrierungs-Heatmap
- [ ] Kalibrierungs-Vorschlags-Panel

### Phase F (Lern-System)
- [ ] WeeklyCalibration Klasse bauen
- [ ] Optuna-Integration
- [ ] Kalibrierungsreport als Telegram-Notification
- [ ] Training-Datensatz-Export für späteres Fine-Tuning

### Phase I (nach Trade #500, Linux)
- [ ] Fine-Tuning Datensatz aufbereiten
- [ ] ROCm auf Linux verifizieren
- [ ] qwen2.5:32b für Layer 1 testen
- [ ] Custom Ollama Modell "bruno-quant-v1" trainieren

---

## 10. PARAMETER-ÄNDERUNG — PROTOKOLL (MENSCHLICHE KONTROLLE)

**Niemals vollautomatisch. Immer Ruben entscheidet.**

```
Wöchentlicher Ablauf:
1. Sonntag 03:00 UTC: WeeklyCalibration läuft automatisch
2. Sonntag 08:00 UTC: Telegram-Nachricht mit Kalibrierungsreport
3. Ruben reviewt Dashboard → Lern-Zentrale → Kalibrierungsvorschlag
4. Ruben klickt [GENEHMIGEN] oder [ABLEHNEN] oder passt manuell an
5. Erst dann wird config.json aktualisiert
6. Bot läuft mit neuen Parametern ab Montag 00:00 UTC

Eiserne Regel: Kein Code darf config.json automatisch überschreiben.
Live-Parameter ändern sich NUR durch bewusste menschliche Entscheidung.
```

---

## 11. DAS LERN-ZIEL — MESSBAR

**Nach 3 Monaten Live-Betrieb soll der Bot:**

| KPI | Start | 1 Monat | 3 Monate | 6 Monate |
|---|---|---|---|---|
| Profit Factor | > 1.5 (Backtest) | > 1.5 | > 1.8 | > 2.0 |
| GRSS Accuracy | unbekannt | > 60% | > 70% | > 75% |
| L2 Calibration | unbekannt | < 20% Abw. | < 10% Abw. | < 5% Abw. |
| Regime Accuracy | unbekannt | > 60% | > 75% | > 80% |
| Muster erkannt | 0 | 3–5 | 8–10 | 12+ |
| Drawdown max | unbekannt | < 10% | < 7% | < 5% |

**Der Bot lernt dann wirklich wenn:**
- Er dasselbe Muster nicht zweimal verliert
- GRSS-Accuracy steigt (der Score wird ehrlicher)
- L2-Confidence sich selbst kalibriert
- Die Drawdowns über Zeit kleiner werden

---

*Dieses Dokument wächst mit dem Bot. Nach jedem Monat Live-Betrieb:
neue Muster dokumentieren, Kalibrierungsergebnisse eintragen,
Hardware-Upgrade-Status aktualisieren.*

*Repository: https://github.com/Kazuo3o447/Bruno*
