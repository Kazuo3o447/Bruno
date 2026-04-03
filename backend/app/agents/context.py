import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies

class ContextAgent(StreamingAgent):
    """
    Der ContextAgent aggregiert Makro-Daten, Derivate-Metriken und Sentiment.
    Berechnet den GRSS v2 (Global Risk Sentiment Score).
    """

    def __init__(self, deps: AgentDependencies):
        super().__init__("context", deps)
        self.state.sub_state = "initializing"
        
        # Makro-Werte (Cache)
        self.vix: float = 20.0
        self.dxy_change: float = 0.0
        self.yields_10y: float = 4.30
        self.ndx_status: str = "BULLISH"
        self.m2_yoy_pct: float = 0.0
        self.stablecoin_delta_bn: float = 0.0
        
        self._last_macro_fetch: float = 0.0
        self._macro_interval = 900 # 15 Minuten
        self._user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # ── Neue Makro-Signale (v2) ─────────────────────────────
        self.oi_trend: dict = self._oi_trend_fallback()
        self.etf_flows: dict = self._etf_flows_fallback()
        self.max_pain: dict = {
            "max_pain_price": 0.0, "distance_pct": 0.0,
            "direction": "neutral", "gravitational_bias": "neutral",
            "strikes_analyzed": 0
        }
        self.pattern_result: dict = {}
        self._last_etf_fetch: float = 0.0

        # ── Bestehende Datenquellen ─────────────────────────────
        self.funding_divergence: float = 0.0
        self.open_interest: float = 0.0
        self.oi_prev: float = 0.0
        self.long_short_ratio: float = 1.0
        self.perp_basis_pct: float = 0.0
        self.btc_change_24h: float = 0.0
        self.put_call_ratio: float = 0.60
        self.dvol: float = 55.0
        self.grss_history: list = []
        self._grss_ema: float = 50.0
        self._grss_ema_alpha: float = 0.4
        self._last_binance_rest_fetch: float = 0.0
        self._last_deribit_fetch: float = 0.0
        self._deribit_interval: float = 900.0
        self._last_latency_check: float = 0.0
        self._latency_check_interval: float = 300.0
        self._last_coinglass_fetch: float = 0.0
        self._coinglass_interval: float = 900.0
        self._etf_flows_3d: float = 0.0
        self._funding_divergence: float = 0.0
        self._retail_sentiment_weight: float = 0.0
        self._retail_score: float = 0.0
        self._retail_fomo_warning: bool = False

        # Latenz & CoinGlass & Retail
        from app.core.latency_monitor import LatencyMonitor
        from app.services.coinglass_client import CoinGlassClient
        from app.services.retail_sentiment import RetailSentimentService
        from app.services.sentiment_analyzer import analyzer as nlp_analyzer

        self.latency_monitor = LatencyMonitor(redis_client=deps.redis, ollama_host=deps.config.OLLAMA_HOST)
        self.coinglass = CoinGlassClient(api_key=deps.config.COINGLASS_API_KEY, redis_client=deps.redis)
        self.retail_sentiment_service = RetailSentimentService(redis_client=deps.redis, sentiment_analyzer=nlp_analyzer, config=deps.config)

        self.macro_feeds = ["https://feeds.finance.yahoo.com/rss/2.0/headline"]
        self.crypto_feeds = ["https://cointelegraph.com/rss"]

    async def setup(self) -> None:
        self.logger.info("ContextAgent v2 (Institutional) gestartet.")
        
        # Sofortiger erster Fetch damit fresh_count beim ersten Zyklus > 0 ist
        try:
            await self._fetch_binance_rest_data()
            await self._fetch_deribit_data()
            macro = await self._fetch_vix_and_dxy()
            self.vix = macro.get("VIX", self.vix)
            self.logger.info("ContextAgent Warm-Up: Erstfetch abgeschlossen")
        except Exception as e:
            self.logger.warning(f"Warm-Up Fehler (nicht kritisch): {e}")

        # NEU: Minimal-GRSS sofort schreiben damit RiskAgent nicht mit context={} startet
        # Dieser Platzhalter-Payload verhindert den DATA GAP Veto beim ersten RiskAgent-Zyklus
        try:
            from datetime import datetime, timezone
            health = await self.deps.redis.get_cache("bruno:health:sources") or {}
            sources_to_check = ["Binance_REST", "Deribit_Public", "yFinance_Macro", "Binance_OI_Trend", "ETF_Flows_Farside"]
            fresh_count = sum(
                1 for s in sources_to_check
                if self._is_fresh_health_status(health.get(s, {}).get("status"))
                or self._is_warning_health_status(health.get(s, {}).get("status"))
            )

            # Minimal GRSS berechnen aus den bereits geholten Daten
            minimal_grss_input = {
                "vix": self.vix,
                "ndx_status": self.ndx_status,
                "fresh_source_count": fresh_count,
                "funding_rate": 0.01,  # neutral default
                "news_silence_seconds": 0,
                # alle anderen Felder auf 0/neutral
                "oi_7d_change_pct": 0, "etf_flow_3d_m": 0, "etf_consecutive_inflow_days": 0,
                "etf_consecutive_outflow_days": 0, "funding_divergence": 0, "stablecoin_delta_bn": 0,
                "btc_change_24h": 0, "btc_change_1h": 0, "fear_greed": 50, "deleveraging_complete": False,
                "liq_bias": "balanced", "liq_squeeze_potential": False, "llm_news_sentiment": 0,
                "pattern_score": 0, "put_call_ratio": 0.6, "dvol": 55, "long_short_ratio": 1.0,
                "yields_10y": self.yields_10y, "m2_yoy_pct": 0,
            }
            minimal_grss = self.calculate_grss(minimal_grss_input)

            warmup_payload = {
                "GRSS_Score_Raw": round(minimal_grss, 1),
                "GRSS_Score": round(minimal_grss, 1),
                "GRSS_Velocity_30min": 0.0,
                "Macro_Status": self.ndx_status,
                "VIX": round(self.vix, 2),
                "Yields_10Y": round(self.yields_10y, 2),
                "Fresh_Source_Count": fresh_count,
                "Data_Freshness_Active": fresh_count > 0,
                "News_Silence_Seconds": 0.0,
                "Veto_Active": minimal_grss < 40,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "_warmup": True,  # Flag dass dies ein Warm-Up-Payload ist
            }
            await self.deps.redis.set_cache("bruno:context:grss", warmup_payload)
            self.logger.info(
                f"ContextAgent Warm-Up GRSS Payload gesetzt: GRSS={minimal_grss:.1f} | "
                f"Fresh Sources={fresh_count} | Data_Freshness_Active={fresh_count > 0}"
            )
        except Exception as e:
            self.logger.warning(f"Warm-Up GRSS Payload Fehler: {e}")

    async def run_stream(self) -> None:
        """Implementierung der abstrakten Methode für StreamingAgent."""
        while self.state.running:
            try:
                await self.process()
                # ContextAgent läuft alle 30 Sekunden
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"ContextAgent run_stream Fehler: {e}", exc_info=True)
                await asyncio.sleep(30)

    # ── Institutional Signal Fetchers ──────────────────────────────────────────

    async def _fetch_oi_trend(self) -> dict:
        CACHE_KEY = "bruno:macro:oi_trend"
        cached = await self.deps.redis.get_cache(CACHE_KEY)
        if cached: return cached
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://fapi.binance.com/futures/data/openInterestHist", 
                                   params={"symbol": "BTCUSDT", "period": "1d", "limit": 8})
                if r.status_code != 200: return self._oi_trend_fallback()
                data = r.json()
                if len(data) < 2: return self._oi_trend_fallback()
                oi_values = [float(d["sumOpenInterestValue"]) for d in data]
                oi_curr, oi_24h, oi_7d = oi_values[-1], oi_values[-2], oi_values[0]
                oi_24h_pct = (oi_curr - oi_24h) / oi_24h * 100
                oi_7d_pct = (oi_curr - oi_7d) / oi_7d * 100
                trend = "building" if oi_7d_pct > 5 else "declining" if oi_7d_pct < -5 else "stable"
                delev_complete = (oi_7d_pct < -5 and abs(oi_24h_pct) < 2)
                result = {
                    "oi_current": round(oi_curr / 1e9, 2), "oi_24h_change_pct": round(oi_24h_pct, 2),
                    "oi_7d_change_pct": round(oi_7d_pct, 2), "oi_trend": trend, "deleveraging_complete": delev_complete
                }
                await self.deps.redis.set_cache(CACHE_KEY, result, ttl=3600)
                await self._report_health("Binance_OI_Trend", "online", (time.perf_counter() - start_t)*1000)
                return result
        except Exception as e:
            self.logger.warning(f"OI Trend Fehler: {e}")
            return self._oi_trend_fallback()

    def _oi_trend_fallback(self) -> dict:
        return {"oi_current": 0.0, "oi_24h_change_pct": 0.0, "oi_7d_change_pct": 0.0, "oi_trend": "unknown", "deleveraging_complete": False}

    async def _fetch_etf_flows(self) -> dict:
        CACHE_KEY = "bruno:macro:etf_flows"
        cached = await self.deps.redis.get_cache(CACHE_KEY)
        if cached: return cached
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": self._user_agent}) as client:
                r = await client.get("https://farside.co.uk/btc/")
                if r.status_code != 200: return self._etf_flows_fallback()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if not table: return self._etf_flows_fallback()
                rows = table.find_all("tr")
                daily_flows = []
                for row in rows[-15:]:
                    cells = row.find_all("td")
                    if not cells: continue
                    val = cells[-1].get_text(strip=True).replace(",", "").replace("$", "").replace(" ", "")
                    if not val or val == "-": continue
                    try: daily_flows.append(float(val))
                    except: continue
                if not daily_flows: return self._etf_flows_fallback()
                flow_today = daily_flows[-1]
                flow_3d = sum(daily_flows[-3:]) if len(daily_flows) >= 3 else sum(daily_flows)
                consecutive_in, consecutive_out = 0, 0
                for f in reversed(daily_flows):
                    if f > 0:
                        if consecutive_out > 0: break
                        consecutive_in += 1
                    elif f < 0:
                        if consecutive_in > 0: break
                        consecutive_out += 1
                result = {
                    "flow_today_m": round(flow_today, 1), "flow_3d_m": round(flow_3d, 1),
                    "consecutive_inflow_days": consecutive_in, "consecutive_outflow_days": consecutive_out,
                    "trend": "inflow" if consecutive_in >= 2 else "outflow" if consecutive_out >= 2 else "mixed",
                    "source": "farside.co.uk"
                }
                await self.deps.redis.set_cache(CACHE_KEY, result, ttl=21600)
                await self._report_health("ETF_Flows_Farside", "online", (time.perf_counter() - start_t)*1000)
                return result
        except Exception as e:
            self.logger.warning(f"ETF Flow Fehler: {e}")
            return self._etf_flows_fallback()

    def _etf_flows_fallback(self) -> dict:
        return {"flow_today_m": 0.0, "flow_3d_m": 0.0, "consecutive_inflow_days": 0, "consecutive_outflow_days": 0, "trend": "unknown", "source": "fallback"}

    async def _calculate_max_pain(self) -> dict:
        try:
            btc_ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            price = float(btc_ticker.get("last_price", 60000))
            if self.put_call_ratio < 0.45: max_pain_strike = price * 0.96
            elif self.put_call_ratio > 0.85: max_pain_strike = price * 1.04
            else: max_pain_strike = price
            dist = (max_pain_strike - price) / price * 100
            return {
                "max_pain_price": round(max_pain_strike, 0), "distance_pct": round(dist, 2),
                "gravitational_bias": "bullish" if dist > 2 else "bearish" if dist < -2 else "neutral"
            }
        except: return {"max_pain_price": 0, "distance_pct": 0, "gravitational_bias": "neutral"}

    def _detect_market_patterns(self, data: dict) -> dict:
        """
        Erkennt zusammengesetzte Marktmuster.
        Mindestens 3 Bedingungen pro Muster müssen erfüllt sein.

        Coiled Spring: Deleveraging abgeschlossen + Funding neutral + Shorts überwiegen
        Institutional Accumulation: ETF Inflows + OI stabil/steigend + positives Basis
        FOMO Top: Funding überhitzt + OI stark gestiegen + Extreme Gier
        Smart Money Exit: ETF Outflows mehrere Tage + Funding noch positiv
        """
        patterns = []

        oi_7d = data.get("oi_7d_change_pct", 0)
        etf_3d = data.get("etf_flow_3d_m", 0)
        etf_in_days = data.get("etf_consecutive_inflow_days", 0)
        etf_out_days = data.get("etf_consecutive_outflow_days", 0)
        funding = data.get("funding_rate", 0.01)
        stable_delta = data.get("stablecoin_delta_bn", 0)
        btc_change_24h = data.get("btc_change_24h", 0)
        fear_greed = data.get("fear_greed", 50)
        delev_complete = data.get("deleveraging_complete", False)
        liq_bias = data.get("liq_bias", "balanced")
        liq_squeeze = data.get("liq_squeeze_potential", False)

        coiled_conditions = [
            oi_7d < -5 or delev_complete,
            abs(funding) < 0.02,
            liq_bias == "upside" or liq_squeeze,
            btc_change_24h < 0,
            fear_greed < 55,
        ]
        if sum(coiled_conditions) >= 3:
            patterns.append({
                "name": "Coiled Spring",
                "bias": "bullish",
                "strength": 0.85,
                "conditions_met": sum(coiled_conditions),
            })

        accum_conditions = [
            etf_3d > 200 or etf_in_days >= 2,
            oi_7d >= -3,
            0 < funding < 0.04,
            stable_delta > 0 or etf_3d > 100,
            btc_change_24h >= 0,
        ]
        if sum(accum_conditions) >= 3:
            patterns.append({
                "name": "Institutional Accumulation",
                "bias": "bullish",
                "strength": 0.9,
                "conditions_met": sum(accum_conditions),
            })

        fomo_conditions = [
            funding > 0.05,
            oi_7d > 10,
            fear_greed > 70,
            etf_3d < 0,
        ]
        if sum(fomo_conditions) >= 3:
            patterns.append({
                "name": "FOMO Top",
                "bias": "bearish",
                "strength": 0.85,
                "conditions_met": sum(fomo_conditions),
            })

        exit_conditions = [
            etf_out_days >= 3 or etf_3d < -300,
            fear_greed > 50,
            funding > 0.01,
            oi_7d > 0,
        ]
        if sum(exit_conditions) >= 3:
            patterns.append({
                "name": "Smart Money Exit",
                "bias": "bearish",
                "strength": 0.8,
                "conditions_met": sum(exit_conditions),
            })

        if not patterns:
            return {
                "active_patterns": [],
                "composite_bias": "neutral",
                "pattern_score": 0,
            }

        score = 0.0
        for p in patterns:
            if p["bias"] == "bullish":
                score += p["strength"] * 15
            else:
                score -= p["strength"] * 20

        return {
            "active_patterns": patterns,
            "composite_bias": patterns[0]["bias"] if patterns else "neutral",
            "pattern_score": round(max(-30, min(20, score)), 1),
        }

    # ── Original Data Fetchers ──────────────────────────────────────────────────

    async def _fetch_fred_yields(self) -> float:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://api.stlouisfed.org/fred/series/observations", params={
                    "series_id": "DGS10", "api_key": self.deps.config.FRED_API_KEY, "file_type": "json", "sort_order": "desc", "limit": 1
                })
                if r.status_code == 200:
                    val = r.json().get("observations", [{}])[0].get("value", "4.3")
                    return float(val) if val != "." else 4.3
        except: pass
        return 4.3

    async def _fetch_vix_and_dxy(self) -> dict:
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/^VIX", headers={"User-Agent": self._user_agent})
                if r.status_code == 200:
                    price = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    latency = (time.perf_counter() - start_t) * 1000
                    await self._report_health("yFinance_Macro", "online", latency)
                    return {"VIX": float(price), "DXY_Change": 0.0}
        except Exception:
            pass
        await self._report_health("yFinance_Macro", "degraded", 0.0)
        return {"VIX": 20.0, "DXY_Change": 0.0}

    async def _fetch_nasdaq_status(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/^IXIC?interval=1d&range=200d", headers={"User-Agent": self._user_agent})
                if r.status_code == 200:
                    prices = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                    prices = [p for p in prices if p is not None]
                    if len(prices) >= 200:
                        sma200 = sum(prices[-200:]) / 200
                        return "BULLISH" if prices[-1] > sma200 else "BEARISH"
        except: pass
        return "BULLISH"

    async def _fetch_m2_supply(self) -> float:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://api.stlouisfed.org/fred/series/observations", params={
                    "series_id": "M2SL", "api_key": self.deps.config.FRED_API_KEY, "file_type": "json", "sort_order": "desc", "limit": 13
                })
                if r.status_code == 200:
                    obs = r.json().get("observations", [])
                    if len(obs) >= 13:
                        current = float(obs[0]["value"])
                        prev_year = float(obs[12]["value"])
                        return (current - prev_year) / prev_year * 100
        except: pass
        return 1.5

    async def _fetch_stablecoin_supply(self) -> float:
        """
        USDT + USDC 7-Tages Supply Delta via CoinGecko (kostenlos, kein Key).
        Rückgabe: Delta in Mrd. USD (positiv = Kapitalzufluss ins Crypto-System)
        Cache: 6 Stunden
        """
        CACHE_KEY = "bruno:macro:stablecoin_delta"
        cached = await self.deps.redis.get_cache(CACHE_KEY)
        if cached is not None:
            return float(cached)

        try:
            async with httpx.AsyncClient(timeout=15.0, headers={"Accept": "application/json"}) as client:
                r = await client.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": "tether,usd-coin",
                        "order": "market_cap_desc",
                        "per_page": 2,
                        "page": 1,
                        "sparkline": False,
                        "price_change_percentage": "7d",
                    },
                )
                if r.status_code == 429:
                    self.logger.debug("CoinGecko rate limited — nutze letzten Cache")
                    return self.stablecoin_delta_bn
                if r.status_code != 200:
                    return 0.0

                coins = r.json()
                total_now = 0.0
                total_7d_ago = 0.0
                for coin in coins:
                    mc = coin.get("market_cap", 0) or 0
                    pct7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
                    total_now += mc
                    mc_7d = mc / (1 + pct7d / 100) if pct7d != -100 else mc
                    total_7d_ago += mc_7d

                delta_bn = (total_now - total_7d_ago) / 1e9
                await self.deps.redis.set_cache(CACHE_KEY, delta_bn, ttl=21600)
                self.logger.info(f"Stablecoin Supply Delta 7d: {delta_bn:+.2f}B USD")
                return round(delta_bn, 2)

        except Exception as e:
            self.logger.warning(f"Stablecoin CoinGecko Fehler: {e}")
            return 0.0

    async def _fetch_binance_rest_data(self) -> None:
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://fapi.binance.com/fapi/v1/openInterest", params={"symbol": "BTCUSDT"})
                if r.status_code == 200:
                    self.oi_prev = self.open_interest
                    self.open_interest = float(r.json().get("openInterest", 0))
                
                r = await client.get("https://fapi.binance.com/fapi/v1/premiumIndex", params={"symbol": "BTCUSDT"})
                if r.status_code == 200:
                    data = r.json()
                    self.perp_basis_pct = (float(data.get("lastFundingRate", 0.01))) * 100
                
                r = await client.get("https://api.binance.com/api/v3/ticker/24hr", params={"symbol": "BTCUSDT"})
                if r.status_code == 200:
                    self.btc_change_24h = float(r.json().get("priceChangePercent", 0)) / 100
            
            # Health melden wenn mindestens OI-Fetch erfolgreich
            latency = (time.perf_counter() - start_t) * 1000
            await self._report_health("Binance_REST", "online", latency)
        except Exception as e:
            await self._report_health("Binance_REST", "offline", 0.0)
            self.logger.warning(f"Binance REST Fehler: {e}")

    async def _fetch_deribit_data(self) -> None:
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency", params={"currency": "BTC", "kind": "option"})
                if r.status_code == 200:
                    res = r.json().get("result", [])
                    put_v = sum(i.get("open_interest", 0) for i in res if "_P" in i.get("instrument_name", ""))
                    call_v = sum(i.get("open_interest", 0) for i in res if "_C" in i.get("instrument_name", ""))
                    if call_v > 0: self.put_call_ratio = put_v / call_v
            
            latency = (time.perf_counter() - start_t) * 1000
            await self._report_health("Deribit_Public", "online", latency)
        except Exception as e:
            await self._report_health("Deribit_Public", "offline", 0.0)
            self.logger.warning(f"Deribit Public Fehler: {e}")

    async def _fetch_coinglass_data(self) -> None:
        if self.coinglass.is_active:
            await self.coinglass.update()
            self._etf_flows_3d = self.coinglass.etf_flows_3d
            self._funding_divergence = self.coinglass.funding_divergence

    async def _fetch_cross_exchange_funding(self) -> float:
        """
        Cross-Exchange Funding Divergenz: Binance vs Bybit vs OKX.
        Alle kostenlos, kein API-Key.
        Rückgabe: max. Divergenz als float.
        Cache: 5 Minuten
        """
        CACHE_KEY = "bruno:macro:funding_divergence"
        cached = await self.deps.redis.get_cache(CACHE_KEY)
        if cached is not None:
            return float(cached)

        binance_f = self.perp_basis_pct / 100.0

        async def _bybit() -> float:
            try:
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r = await c.get("https://api.bybit.com/v5/market/tickers", params={"category": "linear", "symbol": "BTCUSDT"})
                    if r.status_code == 200:
                        lst = r.json().get("result", {}).get("list", [{}])
                        if lst:
                            return float(lst[0].get("fundingRate", binance_f))
            except Exception:
                pass
            return binance_f

        async def _okx() -> float:
            try:
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r = await c.get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": "BTC-SWAP"})
                    if r.status_code == 200:
                        data = r.json().get("data", [{}])
                        if data:
                            return float(data[0].get("fundingRate", binance_f))
            except Exception:
                pass
            return binance_f

        bybit_f, okx_f = await asyncio.gather(_bybit(), _okx())

        divergences = [
            abs(binance_f - bybit_f),
            abs(binance_f - okx_f),
            abs(bybit_f - okx_f),
        ]
        max_div = max(divergences)
        await self.deps.redis.set_cache(CACHE_KEY, max_div, ttl=300)
        self.logger.debug(
            f"Funding: BNC={binance_f:.4%} BYB={bybit_f:.4%} OKX={okx_f:.4%} MaxDiv={max_div:.4%}"
        )
        return round(max_div, 6)
    def _is_funding_settlement_window(self) -> bool: return False

    @staticmethod
    def _normalize_health_status(status: object) -> str:
        return str(status or "").strip().lower()

    @classmethod
    def _is_fresh_health_status(cls, status: object) -> bool:
        return cls._normalize_health_status(status) in {
            "online", "healthy", "connected", "success", "running", "ok",
        }

    @classmethod
    def _is_warning_health_status(cls, status: object) -> bool:
        return cls._normalize_health_status(status) in {
            "degraded", "warning", "fallback", "partial",
        }

    # ── GRSS Logic ──────────────────────────────────────────────────────────

    def calculate_grss(self, data: dict) -> float:
        """
        GRSS v2 — Global Risk & Sentiment Score (0–100)

        Mindestens 2 frische Datenquellen erforderlich.
        VIX > 45 = Hard Veto (systemischer Crash).
        NDX BEARISH = -10 Punkte (kein Block mehr).
        """
        score = 50.0
        fresh_count = int(data.get("fresh_source_count", 0))
        if fresh_count == 0:
            # Kein harter Kollaps — System arbeitet mit veralteten Daten weiter
            # Penalty statt Nullung: -20 Punkte für kompletten Datenverlust
            score -= 20
        elif fresh_count < 2:
            # Teilweise Daten: -8 Punkte pro fehlendem Source
            score -= (2 - fresh_count) * 8
        # Absoluter Minimalwert: 10 (nie 0.0 bei normalen API-Ausfällen)
        # Der news_silence_seconds Veto am Ende der Funktion bleibt erhalten

        # ═══ TIER 1: DERIVATE ═══════════════════════════════════════════════
        f = data.get("funding_rate", 0.01)
        if -0.01 <= f <= 0.03:
            score += 12
        elif f > 0.05:
            score -= 12
        elif f < -0.01:
            score += 6

        oi_delta = data.get("oi_delta_pct", 0)
        btc_1h = data.get("btc_change_1h", 0)
        if oi_delta > 0 and btc_1h > 0:
            score += 8
        elif oi_delta > 0 and btc_1h < 0:
            score -= 6

        pcr = data.get("put_call_ratio", 0.6)
        if pcr < 0.45:
            score += 10
        elif 0.45 <= pcr <= 0.75:
            score += 3
        elif pcr > 0.9:
            score += 6
        elif pcr > 0.75:
            score -= 5

        basis = data.get("perp_basis_pct", 0)
        if 0.0001 <= basis <= 0.05:
            score += 5
        elif basis > 0.1:
            score -= 8
        elif basis < -0.01:
            score -= 4

        div = data.get("funding_divergence", 0)
        if div < 0.01:
            score += 6
        elif div > 0.03:
            score -= 8

        dvol = data.get("dvol", 55)
        if dvol < 40:
            score += 5
        elif dvol > 80:
            score -= 10
        elif dvol > 65:
            score -= 4

        ls = data.get("long_short_ratio", 1.0)
        if ls < 0.9:
            score += 5
        elif ls > 1.5:
            score -= 4

        # ═══ TIER 2: INSTITUTIONELL ═══════════════════════════════════════
        etf = data.get("etf_flow_3d_m", 0)
        if etf > 500:
            score += 12
        elif etf > 200:
            score += 7
        elif etf > 0:
            score += 3
        elif etf < -500:
            score -= 12
        elif etf < -200:
            score -= 7

        oi_7d = data.get("oi_7d_change_pct", 0)
        if -15 <= oi_7d <= -5:
            score += 7
        elif oi_7d < -15:
            score += 3
        elif 3 <= oi_7d <= 12:
            score += 5
        elif oi_7d > 15:
            score -= 8

        stable = data.get("stablecoin_delta_bn", 0)
        if stable > 2.0:
            score += 8
        elif stable > 0.5:
            score += 3
        elif stable < -2.0:
            score -= 8
        elif stable < -0.5:
            score -= 3

        # ═══ TIER 3: SENTIMENT ═════════════════════════════════════════════
        fng = data.get("fear_greed", 50)
        score += ((fng - 50) / 50.0) * 10
        score += data.get("llm_news_sentiment", 0.0) * 8

        # ═══ TIER 4: MAKRO ═════════════════════════════════════════════════
        if data.get("ndx_status") == "BULLISH":
            score += 8
        elif data.get("ndx_status") == "BEARISH":
            score -= 10

        vix = data.get("vix", 20)
        if vix < 15:
            score += 8
        elif vix < 20:
            score += 4
        elif vix < 25:
            score += 0
        elif vix < 35:
            score -= 7
        elif vix < 45:
            score -= 14

        yields = data.get("yields_10y", 4.2)
        if yields < 4.0:
            score += 6
        elif yields < 4.5:
            score += 0
        elif yields < 5.0:
            score -= 6
        else:
            score -= 12

        m2 = data.get("m2_yoy_pct", 1.5)
        if m2 > 5:
            score += 5
        elif m2 > 2:
            score += 2
        elif m2 < 0:
            score -= 7

        score += data.get("pattern_score", 0)

        # Absoluter Minimalwert: 10 (nie 0.0 bei normalen API-Ausfällen)
        score = max(score, 10.0)

        if data.get("news_silence_seconds", 0) > 3600:
            return 0.0
        if vix > 45:
            return 10.0
        if data.get("ndx_status") == "BEARISH" and f > 0.08:
            return 5.0

        return max(0.0, min(100.0, round(score, 1)))

    async def _report_health(self, name: str, status: str, latency: float):
        curr = await self.deps.redis.get_cache("bruno:health:sources") or {}
        curr[name] = {"status": status, "last_update": datetime.now(timezone.utc).isoformat(), "latency_ms": round(latency, 1)}
        await self.deps.redis.set_cache("bruno:health:sources", curr)

    # ── Cycle Logic ──────────────────────────────────────────────────────────

    async def process(self) -> None:
        try:
            self.state.sub_state = "refreshing signals"
            now_t = time.time()
            if now_t - self._last_macro_fetch > self._macro_interval:
                self.yields_10y = await self._fetch_fred_yields()
                macro = await self._fetch_vix_and_dxy()
                self.vix = macro.get("VIX", self.vix)
                self.dxy_change = macro.get("DXY_Change", self.dxy_change)
                self.ndx_status = await self._fetch_nasdaq_status()
                self.m2_yoy_pct = await self._fetch_m2_supply()
                self.stablecoin_delta_bn = await self._fetch_stablecoin_supply()
                self._last_macro_fetch = now_t

            self.oi_trend = await self._fetch_oi_trend()
            self.etf_flows = await self._fetch_etf_flows()
            self.max_pain = await self._calculate_max_pain()
            
            await self._fetch_binance_rest_data()
            await self._fetch_deribit_data()
            await self._fetch_coinglass_data()
            if not self.coinglass.is_active:
                self._funding_divergence = await self._fetch_cross_exchange_funding()
            await self.retail_sentiment_service.update()
            
            btc_t = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            price = float(btc_t.get("last_price", 0))
            
            sources = ["Binance_REST", "Deribit_Public", "yFinance_Macro", "Binance_OI_Trend", "ETF_Flows_Farside"]
            health = await self.deps.redis.get_cache("bruno:health:sources") or {}
            fresh_count = sum(
                1
                for s in sources
                if self._is_fresh_health_status(health.get(s, {}).get("status"))
                or self._is_warning_health_status(health.get(s, {}).get("status"))
            )

            quant_micro = await self.deps.redis.get_cache("bruno:quant:micro") or {}
            liq_asym = quant_micro.get("Liq_Asymmetry", {})

            funding_data = await self.deps.redis.get_cache("market:funding:BTCUSDT") or {}
            sentiment_data = await self.deps.redis.get_cache("bruno:sentiment:aggregate") or {}
            retail_data = await self.deps.redis.get_cache("bruno:retail:sentiment") or {}
            ingestion_data = await self.deps.redis.get_cache("bruno:ingestion:last_message") or {}

            funding_rate = float(funding_data.get("rate", self.perp_basis_pct / 100.0))
            retail_score = float(retail_data.get("retail_score", self._retail_score))
            retail_fomo_warning = bool(retail_data.get("fomo_warning", self._retail_fomo_warning))
            self._retail_score = retail_score
            self._retail_fomo_warning = retail_fomo_warning

            latest_ingestion_ts = ingestion_data.get("timestamp")
            if latest_ingestion_ts:
                try:
                    news_silence_seconds = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(latest_ingestion_ts).replace(tzinfo=timezone.utc)
                    ).total_seconds()
                except Exception:
                    news_silence_seconds = 0.0
            else:
                news_silence_seconds = 0.0

            oi_delta_pct = ((self.open_interest - self.oi_prev) / self.oi_prev * 100.0) if self.oi_prev > 0 else 0.0

            pattern_data = {
                "oi_7d_change_pct": self.oi_trend.get("oi_7d_change_pct", 0),
                "etf_flow_3d_m": self.etf_flows.get("flow_3d_m", 0),
                "etf_consecutive_inflow_days": self.etf_flows.get("consecutive_inflow_days", 0),
                "etf_consecutive_outflow_days": self.etf_flows.get("consecutive_outflow_days", 0),
                "funding_rate": funding_rate,
                "funding_divergence": self._funding_divergence,
                "stablecoin_delta_bn": self.stablecoin_delta_bn,
                "btc_change_24h": self.btc_change_24h,
                "btc_change_1h": 0.0,
                "fear_greed": int((await self.deps.redis.get_cache("macro:fear_and_greed") or {}).get("value", 50)),
                "deleveraging_complete": self.oi_trend.get("deleveraging_complete", False),
                "liq_bias": liq_asym.get("bias", "balanced"),
                "liq_squeeze_potential": liq_asym.get("squeeze_potential", False),
            }
            self.pattern_result = self._detect_market_patterns(pattern_data)

            grss_input = {
                **pattern_data,
                "vix": self.vix, "ndx_status": self.ndx_status,
                "llm_news_sentiment": float(sentiment_data.get("average_score", 0)),
                "fresh_source_count": fresh_count,
                "pattern_score": self.pattern_result["pattern_score"],
                "put_call_ratio": self.put_call_ratio,
                "news_silence_seconds": news_silence_seconds,
                "dvol": self.dvol,
                "long_short_ratio": self.long_short_ratio,
                "yields_10y": self.yields_10y,
                "m2_yoy_pct": self.m2_yoy_pct,
            }
            
            grss = self.calculate_grss(grss_input)
            current_ts = datetime.now(timezone.utc)
            self.grss_history.append({"timestamp": current_ts, "score": grss})
            self.grss_history = [
                entry for entry in self.grss_history
                if (current_ts - entry["timestamp"]).total_seconds() <= 1800
            ]
            grss_velocity_30min = round(grss - self.grss_history[0]["score"], 1) if self.grss_history else 0.0
            self._grss_ema = self._grss_ema_alpha * grss + (1 - self._grss_ema_alpha) * self._grss_ema
            
            payload = {
                "GRSS_Score_Raw": round(grss, 1),
                "GRSS_Score": round(self._grss_ema, 1),
                "GRSS_Velocity_30min": grss_velocity_30min,
                "Macro_Status": self.ndx_status,
                "VIX": round(self.vix, 2),
                "Yields_10Y": round(self.yields_10y, 2),
                "DXY_Change_Pct": round(self.dxy_change, 4),
                "M2_YoY_Pct": round(self.m2_yoy_pct, 2),
                "Funding_Rate": round(funding_rate, 4),
                "Funding_Divergence": round(self._funding_divergence, 4),
                "OI_Delta_Pct": round(oi_delta_pct, 2),
                "Perp_Basis_Pct": round(self.perp_basis_pct, 4),
                "Long_Short_Ratio": round(self.long_short_ratio, 4),
                "Put_Call_Ratio": round(self.put_call_ratio, 4),
                "DVOL": round(self.dvol, 2),
                "Stablecoin_Delta_Bn": round(self.stablecoin_delta_bn, 2),
                "Retail_Score": round(retail_score, 3),
                "Retail_FOMO_Warning": retail_fomo_warning,
                "LLM_News_Sentiment": round(float(sentiment_data.get("average_score", 0)), 3),
                "Fresh_Source_Count": fresh_count,
                "Data_Freshness_Active": fresh_count > 0,
                "News_Silence_Seconds": round(news_silence_seconds, 1),
                "Funding_Settlement_Window": self._is_funding_settlement_window(),
                "CoinGlass_Active": self.coinglass.is_active,
                "BTC_Change_24h_Pct": round(self.btc_change_24h, 4),
                "BTC_Change_1h_Pct": 0.0,
                "pattern_score": self.pattern_result["pattern_score"],
                "Active_Patterns": self.pattern_result["active_patterns"],
                "OI_Trend": self.oi_trend,
                "ETF_Flows": self.etf_flows,
                "Max_Pain": self.max_pain,
                "Veto_Active": self._grss_ema < 40,
                "timestamp": current_ts.isoformat()
            }
            await self.deps.redis.set_cache("bruno:context:grss", payload)
            await self.deps.redis.publish_message("bruno:context:grss", json.dumps(payload))
            self.logger.info(f"Context Update: GRSS={payload['GRSS_Score']} | Patterns={len(payload['Active_Patterns'])}")

        except Exception as e:
            self.logger.error(f"ContextAgent process() Fehler: {e}", exc_info=True)
