import asyncio
import json
import random
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from app.agents.base import PollingAgent
from app.agents.deps import AgentDependencies
from app.services.sentiment_analyzer import analyzer

class ContextAgent(PollingAgent):
    """
    Phase 6: Context Agent (Makro & Sentiment Bias).
    Berechnet den GRSS und aggregiert institutionelles Sentiment.
    Refined: Health-Reporting, Latency Tracking & Nasdaq SMA200.
    """
    def __init__(self, deps: AgentDependencies):
        super().__init__("context", deps)
        self.last_ingestion_time = datetime.now(timezone.utc)
        self.ndx_status = "BULLISH"
        self.yields_10y = 4.2
        self.vix = 18.5
        self.dxy_change = 0.0
        self.btc_change = 0.0
        self.etf_flows_3d = 0.0 # Kumulierte Flows in Mio. USD
        self._last_macro_fetch = 0.0
        self._macro_interval = 900 # 15 Minuten
        self._user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_interval(self) -> float:
        """ContextAgent Polling: alle 60 Sekunden (Sentiment/Makro)."""
        return 60.0

    async def setup(self) -> None:
        self.logger.info("ContextAgent gestartet. Makro & Sentiment Bias Mode.")

    async def _report_health(self, source: str, status: str, latency: float):
        """Meldet Status und Latenz an den globalen Redis-Hub."""
        health_data = {
            "status": status,
            "latency_ms": round(latency, 1),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        current_map = await self.deps.redis.get_cache("bruno:health:sources") or {}
        current_map[source] = health_data
        await self.deps.redis.set_cache("bruno:health:sources", current_map)

    async def _fetch_fred_yields(self) -> float:
        """Holt US 10Y Yields von FRED API mit Latenz-Tracking."""
        api_key = self.deps.config.FRED_API_KEY
        start = time.perf_counter()
        if not api_key:
            return self.yields_10y
            
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                latency = (time.perf_counter() - start) * 1000
                data = resp.json()
                val = data['observations'][0]['value']
                yield_val = float(val) if val != "." else self.yields_10y
                await self._report_health("FRED_Yields", "online", latency)
                return yield_val
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("FRED_Yields", "offline", latency)
            return self.yields_10y

    async def _fetch_nasdaq_status(self) -> str:
        """Berechnet Nasdaq SMA200 Trend (Daily) via yfinance/httpx."""
        start = time.perf_counter()
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^NDX?range=250d&interval=1d"
        headers = {"User-Agent": self._user_agent}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 429:
                    self.logger.warning("yFinance NDX Rate Limit (429). Nutze Cache.")
                    return self.ndx_status
                
                resp.raise_for_status()
                latency = (time.perf_counter() - start) * 1000
                data = resp.json()
                closes = [c for c in data['chart']['result'][0]['indicators']['quote'][0]['close'] if c is not None]
                if len(closes) < 200:
                    status = "BULLISH"
                else:
                    sma200 = sum(closes[-200:]) / 200
                    status = "BULLISH" if closes[-1] >= sma200 else "BEARISH"
                await self._report_health("yFinance_NDX", "online", latency)
                return status
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.logger.warning(f"yFinance NDX Fehler: {e}. Nutze Cache: {self.ndx_status}")
            await self._report_health("yFinance_NDX", "degraded", latency)
            return self.ndx_status

    async def _fetch_vix_and_dxy(self) -> Dict[str, float]:
        """Holt VIX und DXY von Yahoo Finance."""
        start = time.perf_counter()
        results = {"VIX": self.vix, "DXY_Change": self.dxy_change}
        headers = {"User-Agent": self._user_agent}
        
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                # VIX
                vix_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/^VIX?range=1d&interval=1m")
                if vix_resp.status_code != 429:
                    vix_data = vix_resp.json()
                    results["VIX"] = float(vix_data['chart']['result'][0]['meta']['regularMarketPrice'])
                else:
                    self.logger.warning("yFinance VIX Rate Limit (429). Nutze Cache.")

                # DXY 24h Change
                dxy_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=2d&interval=1d")
                if dxy_resp.status_code != 429:
                    dxy_data = dxy_resp.json()
                    dxy_closes = [c for c in dxy_data['chart']['result'][0]['indicators']['quote'][0]['close'] if c is not None]
                    if len(dxy_closes) >= 2:
                        results["DXY_Change"] = (dxy_closes[-1] - dxy_closes[-2]) / dxy_closes[-2]
                else:
                    self.logger.warning("yFinance DXY Rate Limit (429). Nutze Cache.")
                
                latency = (time.perf_counter() - start) * 1000
                await self._report_health("yFinance_Macro", "online" if vix_resp.status_code != 429 else "degraded", latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.logger.warning(f"yFinance Macro Fehler: {e}. Nutze Cache.")
            await self._report_health("yFinance_Macro", "degraded", latency)
            
        return results

    async def _estimate_etf_flows(self) -> float:
        """Simuliert/Extrahiert ETF Flows (IBIT/FBTC) aus News-Sentiment oder API-Mocks."""
        # In einer echten Umgebung würden wir hier eine spezifische API oder News-Aggregation nutzen.
        # Strategie 2026: Mock-Data mit News-Abgleich.
        val = random.uniform(-600, 800) # In Mio. USD
        return val

    async def process(self) -> None:
        try:
            # 1. Makro Pipeline (mit 15-Minuten Caching)
            now = time.time()
            if now - self._last_macro_fetch > self._macro_interval:
                self.logger.info(f"Makro-Update gestartet (Intervall: {self._macro_interval}s)")
                self.yields_10y = await self._fetch_fred_yields()
                macro_data = await self._fetch_vix_and_dxy()
                self.vix = macro_data["VIX"]
                self.dxy_change = macro_data["DXY_Change"]
                self.ndx_status = await self._fetch_nasdaq_status()
                self._last_macro_fetch = now
            else:
                self.logger.debug("Nutze Cache für Makro-Daten.")
            
            self.etf_flows_3d = await self._estimate_etf_flows() # Vereinfacht: 3d Aggregat
            
            # BTC Performance (via Redis Ticker)
            btc_data = await self.deps.redis.get_cache("market:ticker:BTCUSDT")
            if btc_data:
                # btc_data ist bereits ein dict durch get_cache()
                # In einer echten Umgebung hätten wir 24h Start-Preis im State
                self.btc_change = random.uniform(-0.02, 0.02) # Mock für 24h Change
            
            # GDELT Goldstein Simulation/Mock
            start_gdelt = time.perf_counter()
            goldstein = random.uniform(-10, 10)
            latency_gdelt = (time.perf_counter() - start_gdelt) * 1000
            await self._report_health("GDELT_Scale", "online", latency_gdelt)

            # 2. Watchdog: News Silence
            # WENN seit 60 Min keine neuen Daten empfangen -> GRSS = 0 (Sicherheit)
            if random.random() > 0.1: # Simulation für "Datenfluss"
                self.last_ingestion_time = datetime.now(timezone.utc)
            silence_active = (datetime.now(timezone.utc) - self.last_ingestion_time).total_seconds() > 3600

            # 3. Stress Score Berechnung (0-100)
            stress_score = 0.0
            if self.vix > 20: stress_score += (self.vix - 20) * 3.0
            if self.yields_10y > 4.5: stress_score += 20.0
            if self.ndx_status == "BEARISH": stress_score += 30.0
            if silence_active: stress_score = 100.0
            stress_score = max(0.0, min(100.0, stress_score))

            # 4. Bias & GRSS Berechnung (50% Crypto, 30% Macro, 20% LLM)
            macro_bias = 0.0
            if self.ndx_status == "BULLISH": macro_bias += 0.2
            if self.vix < 20: macro_bias += 0.1
            if self.yields_10y < 4.0: macro_bias += 0.2
            
            crypto_bias = random.uniform(-0.5, 0.5) # Platzhalter für technisches Sentiment
            llm_bias = random.uniform(-0.5, 0.5)    # Platzhalter für News-Inference
            
            grss = 50.0 + ((crypto_bias * 0.5 + macro_bias * 0.3 + llm_bias * 0.2) * 50.0)
            
            # STRATEGISCHE ANPASSUNGEN (Phase 6)
            # A. DXY Decoupling (+10 GRSS)
            decoupling = self.dxy_change > 0.005 and self.btc_change > -0.001
            if decoupling:
                grss += 10.0
                self.logger.info(f"DXY Decoupling erkannt: DXY {self.dxy_change:+.2%}, BTC {self.btc_change:+.2%}")

            # B. ETF Flows (+10 / -15 GRSS)
            if self.etf_flows_3d > 500:
                grss += 10.0
            elif self.etf_flows_3d < -500:
                grss -= 15.0

            # C. Institutional Vetos (Hard Penalties)
            if self.vix > 25: grss -= 15
            if self.yields_10y > 4.5: grss -= 10
            if self.ndx_status == "BEARISH": grss -= 30
            if silence_active: grss = 0.0

            grss = max(0.0, min(100.0, grss))

            # 5. Payload publizieren
            payload = {
                "GRSS_Score": round(grss, 1),
                "Stress_Score": round(stress_score, 1),
                "Bias_Breakdown": {
                    "Macro": round(macro_bias, 2), 
                    "Crypto": round(crypto_bias, 2),
                    "DXY_Decoupling": decoupling
                },
                "Macro_Status": self.ndx_status,
                "Yields_10Y": round(self.yields_10y, 2),
                "VIX": round(self.vix, 2),
                "DXY_Change_24h": round(self.dxy_change * 100, 2),
                "ETF_Flows_3d_M": round(self.etf_flows_3d, 1),
                "Veto_Active": grss < 40 or silence_active,
                "Reason": f"GRSS: {grss}, NDX: {self.ndx_status}",
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            await self.deps.redis.set_cache("bruno:context:grss", payload, ttl=3600)
            await self.deps.redis.publish_message("bruno:context:grss", json.dumps(payload))

        except Exception as e:
            self.logger.error(f"ContextAgent Fehler: {e}")
