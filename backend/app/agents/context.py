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
        await self.coinglass.setup()

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
        patterns = []
        oi_7d = data.get("oi_7d_change_pct", 0)
        etf_3d = data.get("etf_flow_3d_m", 0)
        funding = data.get("funding_rate", 0.01)
        if oi_7d > 5 and etf_3d > 100 and funding < 0.02:
            patterns.append({"name": "Coiled Spring", "bias": "bullish", "strength": 0.8})
        stable_delta = data.get("stablecoin_delta_bn", 0)
        if etf_3d > 500 or (stable_delta > 1.0 and data.get("btc_change_24h", 0) >= 0):
            patterns.append({"name": "Institutional Accumulation", "bias": "bullish", "strength": 0.9})
        if not patterns: return {"active_patterns": [], "composite_bias": "neutral", "pattern_score": 0}
        score = sum(p["strength"] * (15 if p["bias"] == "bullish" else -20) for p in patterns)
        return {"active_patterns": patterns, "composite_bias": patterns[0]["bias"], "pattern_score": round(max(-25, min(20, score)), 1)}

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
        # Simplifizierte Yahoo Finance Scraper Logik für VIX
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/^VIX", headers={"User-Agent": self._user_agent})
                if r.status_code == 200:
                    price = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    return {"VIX": float(price), "DXY_Change": 0.0}
        except: pass
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
        # Simulierter Wert bis Etherscan/DeFiLlama Integration
        return 0.5

    async def _fetch_binance_rest_data(self) -> None:
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
        except: pass

    async def _fetch_deribit_data(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency", params={"currency": "BTC", "kind": "option"})
                if r.status_code == 200:
                    res = r.json().get("result", [])
                    put_v = sum(i.get("open_interest", 0) for i in res if "_P" in i.get("instrument_name", ""))
                    call_v = sum(i.get("open_interest", 0) for i in res if "_C" in i.get("instrument_name", ""))
                    if call_v > 0: self.put_call_ratio = put_v / call_v
        except: pass

    async def _fetch_coinglass_data(self) -> None:
        if self.coinglass.is_active:
            await self.coinglass.update()
            self._etf_flows_3d = self.coinglass.etf_flows_3d
            self._funding_divergence = self.coinglass.funding_divergence

    async def _fetch_cross_exchange_funding(self) -> float: return 0.0
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
        score = 50.0
        if int(data.get("fresh_source_count", 0)) <= 0: return 0.0
        
        # 1. DERIVATIVES (40%)
        f = data.get("funding_rate", 0.01)
        if -0.01 <= f <= 0.03: score += 10
        elif f > 0.05: score -= 15
        if data.get("oi_delta_pct", 0) > 0 and data.get("btc_change_1h", 0) > 0: score += 10
        pcr = data.get("put_call_ratio", 0.6)
        if pcr < 0.45: score += 10
        elif pcr > 0.85: score -= 10
        
        # 2. INSTITUTIONAL (20%)
        etf = data.get("etf_flow_3d_m", 0)
        if etf > 300: score += 10
        elif etf < -300: score -= 15
        if data.get("oi_7d_change_pct", 0) > 5: score += 5
        if data.get("stablecoin_delta_bn", 0) > 1.0: score += 5
        
        # 3. SENTIMENT (20%)
        score += ((data.get("fear_greed", 50) - 50) / 50.0) * 10
        score += data.get("llm_news_sentiment", 0.0) * 10
        
        # 4. MACRO (20%)
        vix = data.get("vix", 20)
        if vix < 15: score += 5
        elif vix > 30: score -= 10
        if data.get("ndx_status") == "BULLISH": score += 5
        
        score += data.get("pattern_score", 0)
        if vix > 45: return 5.0
        if data.get("news_silence_seconds", 0) > 3600: return 0.0
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
                "funding_rate": funding_rate,
                "stablecoin_delta_bn": self.stablecoin_delta_bn,
                "btc_change_24h": self.btc_change_24h,
                "btc_change_1h": 0.0 # TODO: Implement delta
            }
            self.pattern_result = self._detect_market_patterns(pattern_data)

            grss_input = {
                **pattern_data,
                "vix": self.vix, "ndx_status": self.ndx_status,
                "fear_greed": int((await self.deps.redis.get_cache("macro:fear_and_greed") or {}).get("value", 50)),
                "llm_news_sentiment": float(sentiment_data.get("average_score", 0)),
                "fresh_source_count": fresh_count,
                "pattern_score": self.pattern_result["pattern_score"],
                "put_call_ratio": self.put_call_ratio,
                "news_silence_seconds": news_silence_seconds,
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
