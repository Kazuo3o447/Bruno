from app.services.event_calendar import EventCalendar
import asyncio
import json
import logging
import time
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from app.agents.base import StreamingAgent
from app.agents.deps import AgentDependencies
from app.core.config_cache import ConfigCache

class ContextAgent(StreamingAgent):
    """
    Der ContextAgent aggregiert Makro-Daten, Derivate-Metriken und Sentiment.
    Berechnet den GRSS v2 (Global Risk Sentiment Score).
    """

    def __init__(self, deps: AgentDependencies):
        super().__init__("context", deps)
        self.state.sub_state = "initializing"
        
        # Initialize ConfigCache
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "config.json"
        )
        ConfigCache.init(config_path)
        
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
        self.pattern_result: dict = {}
        self._last_etf_fetch: float = 0.0

        # ── Bestehende Datenquellen ─────────────────────────────
        self.funding_divergence: float = 0.0
        self.open_interest: float = 0.0
        self.oi_prev: float = 0.0
        self.long_short_ratio: float = None  # None = API-Required, Risk-Veto bei None
        self.perp_basis_pct: float = 0.0
        self.btc_change_24h: float = 0.0
        self.put_call_ratio: float = 0.60
        self.dvol: float = None  # None = API-Required, Risk-Veto bei None
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
        self.onchain_data: Dict = {}
        self._deribit_options_chain: List[Dict] = []
        self._last_grss_breakdown: Dict[str, Any] = {
            "deriv": 0.0,
            "inst": 0.0,
            "sent": 0.0,
            "macro": 0.0,
            "regime_hint": "ranging",
            "max_pain": None,
            "max_pain_distance_pct": None,
        }

        # Latenz & CoinGlass & Retail
        from app.core.latency_monitor import LatencyMonitor
        from app.services.coinglass_client import CoinGlassClient
        from app.services.retail_sentiment import RetailSentimentService
        from app.services.sentiment_analyzer import analyzer as nlp_analyzer
        from app.services.onchain_client import OnChainClient
        from app.services.cryptopanic_client import CryptoPanicClient

        self.latency_monitor = LatencyMonitor(redis_client=deps.redis)
        self.coinglass = CoinGlassClient(api_key=deps.config.COINGLASS_API_KEY, redis_client=deps.redis)
        self.retail_sentiment_service = RetailSentimentService(redis_client=deps.redis, sentiment_analyzer=nlp_analyzer, config=deps.config)
        self.onchain_client = OnChainClient(redis_client=deps.redis, glassnode_api_key=getattr(deps.config, 'GLASSNODE_API_KEY', None))
        self.cryptopanic = CryptoPanicClient(api_key=deps.config.CRYPTOPANIC_API_KEY, redis_client=deps.redis)

        self.macro_feeds = ["https://feeds.bloomberg.com/markets/news.rss"]
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
            sources_to_check = [
                "Binance_REST",
                "Binance_Analytics",
                "Deribit_Public",
                "yFinance_Macro",
                "Binance_OI_Trend",
                "CryptoCompare_News",
                "CryptoCompare_Market",
                "CoinMarketCap_BTC",
                "CoinMarketCap_Global",
                "Blockchain_OnChain",
                "TA_Engine",
                "Liquidation_Cluster_SQL",
            ]
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
                "pattern_score": 0, "put_call_ratio": 0.6, "dvol": None, "long_short_ratio": None,
                "yields_10y": self.yields_10y, "m2_yoy_pct": 0,
            }
            minimal_grss = self.calculate_grss(minimal_grss_input)
            missing_critical_liquidity = self.dvol is None or self.long_short_ratio is None

            veto_threshold = 30.0 if self._is_learning_mode() else 40.0
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
                "Veto_Active": missing_critical_liquidity or minimal_grss < veto_threshold,
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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
                r = await client.get("https://farside.co.uk/btc/")
                if r.status_code != 200:
                    self.logger.warning(f"ETF Flows HTTP {r.status_code}")
                    return self._etf_flows_fallback()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if not table:
                    self.logger.warning("ETF Flows: Keine Tabelle gefunden")
                    return self._etf_flows_fallback()
                rows = table.find_all("tr")
                daily_flows = []
                for row in rows[-15:]:
                    cells = row.find_all("td")
                    if not cells: continue
                    val = cells[-1].get_text(strip=True).replace(",", "").replace("$", "").replace(" ", "")
                    if not val or val == "-": continue
                    try: daily_flows.append(float(val))
                    except: continue
                if not daily_flows:
                    self.logger.warning("ETF Flows: Keine gültigen Flow-Werte")
                    return self._etf_flows_fallback()
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
        """Binance Futures API für L/S Ratio - institutionell korrekt."""
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Global Long/Short Ratio
                r = await client.get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                                   params={"symbol": "BTCUSDT", "period": "5m", "limit": 1})
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        self.long_short_ratio = float(data[-1]["longShortRatio"])
                    else:
                        self.long_short_ratio = None
                    latency = (time.perf_counter() - start_t) * 1000
                    await self._report_health("Binance_REST", "online", latency)
                else:
                    self.long_short_ratio = None
                    await self._report_health("Binance_REST", "offline", 0.0)
        except Exception as e:
            self.logger.warning(f"Binance L/S Ratio API Fehler: {e}")
            self.long_short_ratio = None
            await self._report_health("Binance_REST", "error", 0.0)

    async def _fetch_deribit_data(self) -> None:
        """Deribit API für DVOL, PCR und Options-Chain - institutionell korrekt."""
        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                now_ms = int(time.time() * 1000)
                dvol_req = client.get(
                    "https://www.deribit.com/api/v2/public/get_volatility_index_data",
                    params={
                        "currency": "BTC",
                        "start_timestamp": now_ms - 86_400_000,
                        "end_timestamp": now_ms,
                        "resolution": "1d",
                    },
                )
                options_req = client.get(
                    "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
                    params={"currency": "BTC", "kind": "option"},
                )
                dvol_r, options_r = await asyncio.gather(dvol_req, options_req)

                # DVOL (Deribit Implied Volatility Index)
                if dvol_r.status_code == 200:
                    data = dvol_r.json().get("result", {}).get("data", []) or []
                    if data:
                        last_row = data[-1]
                        if isinstance(last_row, list) and len(last_row) >= 5:
                            self.dvol = float(last_row[4])
                        else:
                            self.dvol = None
                    else:
                        self.dvol = None
                else:
                    self.dvol = None

                # Options-Chain für PCR (Max Pain entfernt)
                call_oi = 0.0
                put_oi = 0.0
                options_chain: List[Dict] = []
                if options_r.status_code == 200:
                    raw_options = options_r.json().get("result", []) or []
                    for opt in raw_options:
                        instrument_name = opt.get("instrument_name", "")
                        parts = instrument_name.split("-")
                        if len(parts) < 4:
                            continue
                        try:
                            strike = float(parts[2])
                            option_type = parts[3].upper()
                            open_interest = float(opt.get("open_interest", 0.0) or 0.0)
                            contract_size = float(opt.get("contract_size", 1.0) or 1.0)
                        except (TypeError, ValueError):
                            continue

                        weighted_oi = open_interest * contract_size
                        options_chain.append({
                            "instrument_name": instrument_name,
                            "strike": strike,
                            "type": option_type,
                            "open_interest": weighted_oi,
                        })

                        if option_type == "C":
                            call_oi += weighted_oi
                        elif option_type == "P":
                            put_oi += weighted_oi

                if options_chain:
                    self._deribit_options_chain = options_chain
                    await self.deps.redis.set_cache(
                        "bruno:macro:deribit_options_chain",
                        {"timestamp": datetime.now(timezone.utc).isoformat(), "options": options_chain},
                        ttl=900,
                    )

                if call_oi > 0:
                    self.put_call_ratio = round(put_oi / call_oi, 4)

            latency = (time.perf_counter() - start_t) * 1000
            await self._report_health(
                "Deribit_Public",
                "online" if self.dvol is not None or self._deribit_options_chain else "offline",
                latency,
            )
            
        except Exception as e:
            self.logger.warning(f"Deribit DVOL API Fehler: {e}")
            self.dvol = None
            self._deribit_options_chain = []
            await self._report_health("Deribit_Public", "error", 0.0)
            self.logger.warning(f"Deribit Public Fehler: {e}")

    async def _fetch_coinglass_data(self) -> None:
        if self.coinglass.is_active:
            await self.coinglass.update()
            self._etf_flows_3d = self.coinglass.etf_flows_3d
            self._funding_divergence = self.coinglass.funding_divergence

    async def _fetch_long_short_ratio(self) -> Optional[float]:
        """
        Binance Global Long/Short Account Ratio.
        Kostenlos, kein API-Key nötig.
        """
        CACHE_KEY = "bruno:macro:long_short_ratio"
        cached = await self.deps.redis.get_cache(CACHE_KEY)
        if cached is not None:
            return float(cached)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                    params={"symbol": "BTCUSDT", "period": "1h", "limit": 1}
                )
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        ratio = float(data[-1]["longShortRatio"])
                        await self.deps.redis.set_cache(CACHE_KEY, ratio, ttl=900)
                        return ratio
        except Exception as e:
            self.logger.warning(f"Long/Short Ratio Fehler: {e}")
        return None

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

    @staticmethod
    def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _normalize_max_pain_effect(self, price: float, max_pain: Optional[float]) -> float:
        # DEAKTIVIERT - Max Pain Logik entfernt
        return 0.0

    def _calc_deriv_subscore(self, data: dict) -> float:
        price = float(data.get("current_price", 0.0) or 0.0)
        max_pain = data.get("max_pain")

        funding_rate = float(data.get("funding_rate", 0.0) or 0.0)
        if funding_rate < -0.01:
            funding_norm = 1.0
        elif funding_rate <= 0.03:
            funding_norm = 0.5
        elif funding_rate <= 0.05:
            funding_norm = 0.0
        else:
            funding_norm = -1.0

        oi_delta = float(data.get("oi_delta_pct", 0.0) or 0.0)
        if oi_delta > 15:
            oi_norm = -1.0
        elif oi_delta > 5:
            oi_norm = 0.4
        elif oi_delta < -15:
            oi_norm = 0.2
        elif oi_delta < -5:
            oi_norm = 0.6
        else:
            oi_norm = 0.0

        pcr = float(data.get("put_call_ratio", 0.6) or 0.6)
        if pcr < 0.45:
            pcr_norm = 1.0
        elif pcr < 0.75:
            pcr_norm = 0.3
        elif pcr < 0.9:
            pcr_norm = -0.4
        else:
            pcr_norm = -1.0

        dvol = data.get("dvol")
        if dvol is None:
            dvol_norm = 0.0
        else:
            dvol = float(dvol)
            if dvol < 40:
                dvol_norm = 1.0
            elif dvol < 65:
                dvol_norm = 0.3
            elif dvol < 80:
                dvol_norm = -0.4
            else:
                dvol_norm = -1.0

        ls = data.get("long_short_ratio")
        if ls is None:
            ls_norm = 0.0
        else:
            ls = float(ls)
            if ls < 0.9:
                ls_norm = 0.8
            elif ls < 1.2:
                ls_norm = 0.2
            elif ls < 1.5:
                ls_norm = -0.4
            else:
                ls_norm = -0.9

        max_pain_norm = self._normalize_max_pain_effect(price, max_pain)

        weighted = (
            funding_norm * 0.25 +
            oi_norm * 0.20 +
            pcr_norm * 0.15 +
            dvol_norm * 0.12 +
            ls_norm * 0.13 +
            max_pain_norm * 0.15  # Erhöht von 5% auf 15% für Retail
        )
        return round(self._clamp(weighted * 25.0, -25.0, 25.0), 1)

    def _calc_retail_subscore(self, data: dict) -> float:
        etf_flow_3d_m = float(data.get("etf_flow_3d_m", 0.0) or 0.0)
        if etf_flow_3d_m > 500:
            etf_norm = 1.0
        elif etf_flow_3d_m > 200:
            etf_norm = 0.6
        elif etf_flow_3d_m > 0:
            etf_norm = 0.2
        elif etf_flow_3d_m < -500:
            etf_norm = -1.0
        elif etf_flow_3d_m < -200:
            etf_norm = -0.6
        else:
            etf_norm = 0.0

        oi_7d_change_pct = float(data.get("oi_7d_change_pct", 0.0) or 0.0)
        if oi_7d_change_pct > 15:
            oi_norm = -0.7
        elif oi_7d_change_pct > 3:
            oi_norm = 0.7
        elif oi_7d_change_pct < -15:
            oi_norm = 0.4
        elif oi_7d_change_pct < -5:
            oi_norm = 0.6
        else:
            oi_norm = 0.0

        stablecoin_delta_bn = float(data.get("stablecoin_delta_bn", 0.0) or 0.0)
        if stablecoin_delta_bn > 2.0:
            stable_norm = 1.0
        elif stablecoin_delta_bn > 0.5:
            stable_norm = 0.4
        elif stablecoin_delta_bn < -2.0:
            stable_norm = -1.0
        elif stablecoin_delta_bn < -0.5:
            stable_norm = -0.4
        else:
            stable_norm = 0.0

        pattern_score = float(data.get("pattern_score", 0.0) or 0.0)
        if pattern_score > 10:
            pattern_norm = 1.0
        elif pattern_score > 3:
            pattern_norm = 0.5
        elif pattern_score < -10:
            pattern_norm = -1.0
        elif pattern_score < -3:
            pattern_norm = -0.5
        else:
            pattern_norm = 0.0

        weighted = (
            etf_norm * 0.35 +
            oi_norm * 0.25 +
            stable_norm * 0.25 +
            pattern_norm * 0.15
        )
        return round(self._clamp(weighted * 25.0, -25.0, 25.0), 1)

    def _calc_sentiment_subscore(self, data: dict) -> float:
        fear_greed = float(data.get("fear_greed", 50.0) or 50.0)
        if fear_greed < 20:
            fg_norm = 1.0
        elif fear_greed < 35:
            fg_norm = 0.4
        elif fear_greed <= 65:
            fg_norm = 0.0
        elif fear_greed <= 80:
            fg_norm = -0.4
        else:
            fg_norm = -1.0

        llm_news_sentiment = float(data.get("llm_news_sentiment", 0.0) or 0.0)
        if llm_news_sentiment > 0.5:
            news_norm = 1.0
        elif llm_news_sentiment > 0.1:
            news_norm = 0.4
        elif llm_news_sentiment < -0.5:
            news_norm = -1.0
        elif llm_news_sentiment < -0.1:
            news_norm = -0.4
        else:
            news_norm = 0.0

        retail_score = float(data.get("retail_score", 0.0) or 0.0)
        retail_fomo_warning = bool(data.get("retail_fomo_warning", False))
        if retail_fomo_warning or retail_score > 0.7:
            retail_norm = -1.0
        elif retail_score > 0.4:
            retail_norm = -0.4
        elif retail_score < -0.4:
            retail_norm = 0.4
        else:
            retail_norm = 0.0

        onchain = data.get("onchain", {}) or {}
        exchange_outflow = bool(onchain.get("exchange_outflow"))
        exchange_balance_change_btc = float(onchain.get("exchange_balance_change_btc", 0.0) or 0.0)
        if exchange_outflow:
            onchain_norm = 1.0
        elif exchange_balance_change_btc > 5000:
            onchain_norm = -1.0
        elif exchange_balance_change_btc > 1000:
            onchain_norm = -0.4
        elif exchange_balance_change_btc < -5000:
            onchain_norm = 1.0
        elif exchange_balance_change_btc < -1000:
            onchain_norm = 0.4
        else:
            onchain_norm = 0.0

        weighted = (
            fg_norm * 0.30 +
            news_norm * 0.30 +
            retail_norm * 0.20 +
            onchain_norm * 0.20
        )
        return round(self._clamp(weighted * 25.0, -25.0, 25.0), 1)

    def _calc_macro_subscore(self, data: dict) -> float:
        vix = float(data.get("vix", 20.0) or 20.0)
        if vix < 15:
            vix_norm = 1.0
        elif vix < 20:
            vix_norm = 0.5
        elif vix < 25:
            vix_norm = 0.0
        elif vix < 35:
            vix_norm = -0.5
        else:
            vix_norm = -1.0

        ndx_status = str(data.get("ndx_status", "") or "").upper()
        if ndx_status == "BULLISH":
            ndx_norm = 1.0
        elif ndx_status == "BEARISH":
            ndx_norm = -1.0
        else:
            ndx_norm = 0.0

        yields_10y = float(data.get("yields_10y", 4.2) or 4.2)
        if yields_10y < 4.0:
            yields_norm = 1.0
        elif yields_10y < 4.5:
            yields_norm = 0.3
        elif yields_10y < 5.0:
            yields_norm = -0.5
        else:
            yields_norm = -1.0

        m2_yoy_pct = float(data.get("m2_yoy_pct", 0.0) or 0.0)
        if m2_yoy_pct > 5:
            m2_norm = 1.0
        elif m2_yoy_pct > 2:
            m2_norm = 0.4
        elif m2_yoy_pct < 0:
            m2_norm = -1.0
        else:
            m2_norm = 0.0

        weighted = (
            vix_norm * 0.35 +
            ndx_norm * 0.25 +
            yields_norm * 0.20 +
            m2_norm * 0.20
        )
        return round(self._clamp(weighted * 25.0, -25.0, 25.0), 1)

    def _calc_max_pain(self) -> dict:
        """
        DEAKTIVIERT - Max Pain Berechnung entfernt.
        """
        return {"max_pain": None, "distance_pct": None}

    def _determine_regime_hint(self, data: dict, grss: float) -> str:
        vix = float(data.get("vix", 20.0) or 20.0)
        ndx_status = str(data.get("ndx_status", "") or "").upper()

        if vix > 35:
            return "high_vola"
        if ndx_status == "BULLISH" and grss >= 55:
            return "trending_bull"
        if ndx_status == "BEARISH" and grss <= 45:
            return "bear"
        return "ranging"

    # ── GRSS Logic ──────────────────────────────────────────────────────────

    def calculate_grss(self, data: dict) -> float:
        """
        GRSS v3 — 4 gewichtete Sub-Komplexe statt 25 additive Terme.
        """
        deriv_score = self._calc_deriv_subscore(data)
        retail_score = self._calc_retail_subscore(data)
        sent_score = self._calc_sentiment_subscore(data)
        macro_score = self._calc_macro_subscore(data)

        score = 50.0 + deriv_score + retail_score + sent_score + macro_score

        fresh_count = int(data.get("fresh_source_count", 0))
        if fresh_count == 0:
            score = max(score * 0.5, 10.0)
        elif fresh_count < 3:
            score *= 0.85

        vix = float(data.get("vix", 20.0) or 20.0)
        regime_hint = self._determine_regime_hint(data, score)
        self._last_grss_breakdown = {
            "deriv": deriv_score,
            "retail": retail_score,
            "sent": sent_score,
            "macro": macro_score,
            "regime_hint": regime_hint,
            "max_pain": data.get("max_pain"),
            "max_pain_distance_pct": data.get("max_pain_distance_pct"),
        }

        if vix > 45:
            return 10.0
        if data.get("ndx_status") == "BEARISH" and float(data.get("funding_rate", 0.0) or 0.0) > 0.08:
            return 5.0

        return max(0.0, min(100.0, round(score, 1)))

    def _is_learning_mode(self) -> bool:
        """Prüft ob Learning Mode aktiv ist."""
        return ConfigCache.get("LEARNING_MODE_ENABLED", False)

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

            self.oi_trend = await self._fetch_oi_trend()
            self.etf_flows = await self._fetch_etf_flows()

            await self._fetch_binance_rest_data()
            await self._fetch_coinglass_data()
        
            # NEU: CryptoPanic News (Phase 1 - Ersatz für Browser-Scraping)
            if self.cryptopanic.is_active():
                await self.cryptopanic.update()
        
            # Binance Analytics REMOVED (Phase 3 Purge)
            # Bybit V5 is now the Single Source of Truth

            onchain_start = time.perf_counter()
            self.onchain_data = await self.onchain_client.update()
            await self._report_health(
                "Blockchain_OnChain",
                "online" if self.onchain_data else "offline",
                (time.perf_counter() - onchain_start) * 1000,
            )
        
            if not self.coinglass.is_active:
                self._funding_divergence = await self._fetch_cross_exchange_funding()
            await self.retail_sentiment_service.update()
        
            btc_t = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            price = float(btc_t.get("last_price", 0))
            max_pain_result = self._calc_max_pain()
            max_pain = max_pain_result.get("max_pain")
            max_pain_distance_pct = None
            if max_pain is not None and price > 0:
                max_pain_distance_pct = round(((float(max_pain) - price) / price) * 100.0, 2)
        
            sources = [
                "Binance_REST",
                "Binance_Analytics",
                "Deribit_Public",
                "yFinance_Macro",
                "Binance_OI_Trend",
                "CryptoCompare_News",
                "CryptoCompare_Market",
                "CoinMarketCap_BTC",
                "CoinMarketCap_Global",
                "Blockchain_OnChain",
                "TA_Engine",
                "Liquidation_Cluster_SQL",
            ]
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
            cryptocompare_bundle = await self.deps.redis.get_cache("bruno:cryptocompare:bundle") or {}
            coinmarketcap_bundle = await self.deps.redis.get_cache("bruno:coinmarketcap:bundle") or {}
            retail_data = await self.deps.redis.get_cache("bruno:retail:sentiment") or {}
            ingestion_data = await self.deps.redis.get_cache("bruno:ingestion:last_message") or {}

            # NEU: HuggingFace Verfügbarkeit prüfen - Sentiment-Einfluss auf 0 wenn nicht verfügbar
            sentiment_avg_score = float(sentiment_data.get("average_score", 0))
            try:
                from app.services.sentiment_analyzer import analyzer as nlp_analyzer
                if not nlp_analyzer.hf_available:
                    sentiment_avg_score = 0.0
                    self.logger.warning("HuggingFace nicht verfügbar - Sentiment-Score-Einfluss auf 0 gesetzt")
            except ImportError:
                sentiment_avg_score = 0.0
                self.logger.warning("Sentiment Analyzer nicht verfügbar - Sentiment-Score-Einfluss auf 0 gesetzt")

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
                "llm_news_sentiment": sentiment_avg_score,  
                "fresh_source_count": fresh_count,
                "retail_score": retail_score,
                "retail_fomo_warning": retail_fomo_warning,
                "pattern_score": self.pattern_result["pattern_score"],
                "put_call_ratio": self.put_call_ratio,
                "news_silence_seconds": news_silence_seconds,
                "dvol": self.dvol,
                "long_short_ratio": self.long_short_ratio,
                "yields_10y": self.yields_10y,
                "m2_yoy_pct": self.m2_yoy_pct,
                "onchain": self.onchain_data,
                "taker_buy_sell_ratio": 1.0,  # BinanceAnalyticsService entfernt - Default Wert
                "current_price": price,
                "max_pain": max_pain,
                "max_pain_distance_pct": max_pain_distance_pct,
            }
        
            grss = self.calculate_grss(grss_input)
            
            # Active Event Check
            active_event = EventCalendar.get_active_event()
            
            current_ts = datetime.now(timezone.utc)
            self.grss_history.append({"timestamp": current_ts, "score": grss})
            self.grss_history = [
                entry for entry in self.grss_history
                if (current_ts - entry["timestamp"]).total_seconds() <= 1800
            ]
            grss_velocity_30min = round(grss - self.grss_history[0]["score"], 1) if self.grss_history else 0.0
            self._grss_ema = self._grss_ema_alpha * grss + (1 - self._grss_ema_alpha) * self._grss_ema
        
            veto_threshold = 30.0 if self._is_learning_mode() else 40.0
            missing_critical_liquidity = self.dvol is None or self.long_short_ratio is None
            payload = {
                "GRSS_Score_Raw": round(grss, 1),
                "GRSS_Score": round(self._grss_ema, 1),
                "GRSS_Velocity_30min": grss_velocity_30min,
                "GRSS_Deriv_Sub": self._last_grss_breakdown.get("deriv", 0.0),
                "GRSS_Inst_Sub": self._last_grss_breakdown.get("inst", 0.0),
                "GRSS_Sent_Sub": self._last_grss_breakdown.get("sent", 0.0),
                "GRSS_Macro_Sub": self._last_grss_breakdown.get("macro", 0.0),
                "Macro_Status": self.ndx_status,
                "VIX": round(self.vix, 2),
                "Yields_10Y": round(self.yields_10y, 2),
                "DXY_Change_Pct": round(self.dxy_change, 4),
                "M2_YoY_Pct": round(self.m2_yoy_pct, 2),
                "Funding_Rate": round(funding_rate, 4),
                "Funding_Divergence": round(self._funding_divergence, 4),
                "OI_Delta_Pct": round(oi_delta_pct, 2),
                "Perp_Basis_Pct": round(self.perp_basis_pct, 4),
                "Long_Short_Ratio": round(self.long_short_ratio, 4) if self.long_short_ratio is not None else None,
                "Put_Call_Ratio": round(self.put_call_ratio, 4),
                "DVOL": round(self.dvol, 2) if self.dvol is not None else None,
                "Stablecoin_Delta_Bn": round(self.stablecoin_delta_bn, 2),
                "Retail_Score": round(retail_score, 3),
                "Retail_FOMO_Warning": retail_fomo_warning,
                "LLM_News_Sentiment": round(sentiment_avg_score, 3),  # NEU: uses checked value
                "Fresh_Source_Count": fresh_count,
                "Data_Freshness_Active": fresh_count > 0,
                "News_Silence_Seconds": round(news_silence_seconds, 1),
                "Funding_Settlement_Window": self._is_funding_settlement_window(),
                "CoinGlass_Active": self.coinglass.is_active,
                "BTC_Change_24h_Pct": round(self.btc_change_24h, 4),
                "BTC_Change_1h_Pct": 0.0,
                "Max_Pain": max_pain,
                "Max_Pain_Distance_Pct": max_pain_distance_pct,
                "Active_Event": active_event,
                "_regime_hint": self._last_grss_breakdown.get("regime_hint", "ranging"),
                "pattern_score": self.pattern_result["pattern_score"],
                "Active_Patterns": self.pattern_result["active_patterns"],
                "OI_Trend": self.oi_trend,
                "ETF_Flows": self.etf_flows,
                "CryptoCompare": {
                    "timestamp": cryptocompare_bundle.get("timestamp"),
                    "symbols": cryptocompare_bundle.get("symbols", []),
                    "tsym": cryptocompare_bundle.get("tsym", "USD"),
                    "price_snapshot": cryptocompare_bundle.get("price_snapshot", {}),
                    "top_coins": cryptocompare_bundle.get("top_coins", []),
                    "top_exchanges": cryptocompare_bundle.get("top_exchanges", []),
                    "historical_summary": cryptocompare_bundle.get("historical_summary", {}),
                    "social_stats_raw": cryptocompare_bundle.get("social_stats_raw", {}),
                    "blockchain_stats_raw": cryptocompare_bundle.get("blockchain_stats_raw", {}),
                },
                "CoinMarketCap": {
                    "timestamp": coinmarketcap_bundle.get("timestamp"),
                    "symbol": coinmarketcap_bundle.get("symbol", "BTC"),
                    "convert": coinmarketcap_bundle.get("convert", "USD"),
                    "quote": coinmarketcap_bundle.get("quote", {}),
                    "listings_latest": coinmarketcap_bundle.get("listings_latest", {}),
                    "btc_info": coinmarketcap_bundle.get("btc_info", {}),
                    "global_metrics": coinmarketcap_bundle.get("global_metrics", {}),
                },
                "Veto_Active": missing_critical_liquidity or self._grss_ema < veto_threshold,
                "Data_Source_Status": self._get_data_source_summary(health, sources),
                "timestamp": current_ts.isoformat()
            }
            await self.deps.redis.set_cache("bruno:context:grss", payload)
            await self.deps.redis.publish_message("bruno:context:grss", json.dumps(payload))
            self.logger.info(f"Context Update: GRSS={payload['GRSS_Score']} | Patterns={len(payload['Active_Patterns'])}")

        except Exception as e:
            self.logger.error(f"ContextAgent process() Fehler: {e}", exc_info=True)

    async def _fetch_rss(self, url: str) -> bool:
        """Fetch RSS feed for systemtest compatibility."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False

    def _get_data_source_summary(self, health: dict, sources: list) -> dict:
        """Erzeugt eine detaillierte Zusammenfassung des Datenquellen-Status."""
        if not health:
            return {
                "total_sources": len(sources),
                "online_count": 0,
                "offline_count": len(sources),
                "error_count": 0,
                "status_percentage": 0.0,
                "status_emoji": "🔴",
                "status_text": "Keine Daten verfügbar",
                "critical_issues": [],
                "healthy_sources": [],
                "problematic_sources": sources.copy(),
                "last_update": None
            }
        
        online_count = 0
        offline_count = 0
        error_count = 0
        healthy_sources = []
        problematic_sources = []
        critical_issues = []
        
        for source in sources:
            status_info = health.get(source, {})
            status = status_info.get("status", "unknown")
            latency = status_info.get("latency_ms", 0)
            last_update = status_info.get("last_update")
            
            if status == "online":
                online_count += 1
                healthy_sources.append({
                    "name": source,
                    "status": status,
                    "latency_ms": latency,
                    "last_update": last_update
                })
            elif status == "error":
                error_count += 1
                problematic_sources.append({
                    "name": source,
                    "status": status,
                    "latency_ms": latency,
                    "last_update": last_update,
                    "issue": "Fehler bei der Datenabfrage"
                })
                if source in ["TA_Engine", "Binance_OB", "Binance_OI_Trend"]:
                    critical_issues.append(f"{source}: Technischer Fehler")
            else:  # offline, warning, etc.
                offline_count += 1
                problematic_sources.append({
                    "name": source,
                    "status": status,
                    "latency_ms": latency,
                    "last_update": last_update,
                    "issue": "Keine Verbindung"
                })
                if source in ["CoinMarketCap_BTC", "CoinMarketCap_Global", "CryptoCompare_News", "CryptoCompare_Market"]:
                    critical_issues.append(f"{source}: API Key Problem")
        
        total = len(sources)
        status_percentage = (online_count / total) * 100 if total > 0 else 0.0
        
        # Status-Emoji und Text basierend auf Verfügbarkeit
        if status_percentage >= 80:
            status_emoji = "🟢"
            status_text = "Optimal"
        elif status_percentage >= 60:
            status_emoji = "🟡"
            status_text = "Akzeptabel"
        elif status_percentage >= 40:
            status_emoji = "🟠"
            status_text = "Eingeschränkt"
        else:
            status_emoji = "🔴"
            status_text = "Kritisch"
        
        # Letzte Aktualisierung finden
        latest_update = None
        for source_info in health.values():
            if source_info.get("last_update"):
                if not latest_update or source_info["last_update"] > latest_update:
                    latest_update = source_info["last_update"]
        
        return {
            "total_sources": total,
            "online_count": online_count,
            "offline_count": offline_count,
            "error_count": error_count,
            "status_percentage": round(status_percentage, 1),
            "status_emoji": status_emoji,
            "status_text": status_text,
            "critical_issues": critical_issues,
            "healthy_sources": healthy_sources,
            "problematic_sources": problematic_sources,
            "last_update": latest_update,
            "recommendation": self._get_data_source_recommendation(status_percentage, critical_issues)
        }
    
    def _get_data_source_recommendation(self, status_percentage: float, critical_issues: list) -> str:
        """Gibt eine Empfehlung basierend auf dem Datenquellen-Status."""
        if status_percentage >= 80:
            return "Alle Systeme optimal. Trading kann ohne Einschränkungen fortgesetzt werden."
        elif status_percentage >= 60:
            return "Die meisten Datenquellen verfügbar. Trading möglich, aber einige Indikatoren fehlen."
        elif status_percentage >= 40:
            return "Wichtige Datenquellen fehlen. Empfohlen: Trading mit Vorsicht oder manuelle Überprüfung."
        else:
            if "API Key Problem" in str(critical_issues):
                return "Kritisch: API Keys fehlen oder sind ungültig. Bitte überprüfen Sie die Konfiguration."
            else:
                return "Kritisch: Viele Datenquellen nicht verfügbar. Trading nicht empfohlen."
