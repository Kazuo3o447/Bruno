import asyncio
import json
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

        # ── Binance REST Cache ──────────────────────────────────
        self.open_interest: float = 0.0
        self.oi_prev: float = 0.0           # Vorheriger OI für Delta
        self.long_short_ratio: float = 1.0
        self.perp_basis_pct: float = 0.0
        self.btc_change_24h: float = 0.0

        # ── Deribit Public Cache ────────────────────────────────
        self.put_call_ratio: float = 0.60   # Neutral-Default
        self.dvol: float = 55.0             # Neutral-Default

        # ── GRSS Velocity Tracking ──────────────────────────────
        # Liste von {"ts": float, "grss": float} — letzte 6 Einträge
        self.grss_history: list = []

        # ── Fetch-Intervall-Kontrolle ───────────────────────────
        self._last_binance_rest_fetch: float = 0.0
        self._last_deribit_fetch: float = 0.0
        # Binance REST: bei jedem Agent-Cycle (300s)
        # Deribit: alle 900s (15 Min)
        self._deribit_interval: float = 900.0

    def get_interval(self) -> float:
        """
        5-Minuten-Intervall für Medium-Frequency Trading.
        Schnell genug für echte OI/Funding-Veränderungen.
        Langsam genug für Rate-Limit-sichere API-Calls.
        """
        return 300.0

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
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("FRED_Yields", "offline", latency)
            return self.yields_10y
            
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                latency = (time.perf_counter() - start) * 1000
                if resp.status_code == 200:
                    data = resp.json()
                    val = data['observations'][0]['value']
                    yield_val = float(val) if val != "." else self.yields_10y
                    await self._report_health("FRED_Yields", "online", latency)
                else:
                    yield_val = self.yields_10y
                    await self._report_health("FRED_Yields", "offline", latency)
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
                    latency = (time.perf_counter() - start) * 1000
                    await self._report_health("yFinance_NDX", "offline", latency)
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
            await self._report_health("yFinance_NDX", "offline", latency)
            return self.ndx_status

    async def _fetch_vix_and_dxy(self) -> Dict[str, float]:
        """Holt VIX und DXY von Yahoo Finance."""
        start = time.perf_counter()
        results = {"VIX": self.vix, "DXY_Change": self.dxy_change}
        headers = {"User-Agent": self._user_agent}
        success_parts = 0
        
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                # VIX
                vix_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/^VIX?range=1d&interval=1m")
                if vix_resp.status_code != 429:
                    vix_data = vix_resp.json()
                    results["VIX"] = float(vix_data['chart']['result'][0]['meta']['regularMarketPrice'])
                    success_parts += 1
                else:
                    self.logger.warning("yFinance VIX Rate Limit (429). Nutze Cache.")
                    # Stooq-Fallback wenn yFinance Rate-Limit
                    if vix_resp.status_code == 429:
                        try:
                            import pandas_datareader as pdr
                            from datetime import date
                            vix_df = pdr.get_data_stooq(
                                "^VIX.US",
                                start=date.today() - timedelta(days=5),
                                end=date.today()
                            )
                            if not vix_df.empty:
                                results["VIX"] = float(vix_df["Close"].iloc[-1])
                                success_parts += 1
                                self.logger.info(
                                    f"VIX via Stooq-Fallback: {results['VIX']:.1f}"
                                )
                        except Exception as stooq_err:
                            self.logger.warning(
                                f"Stooq VIX Fallback fehlgeschlagen: {stooq_err}"
                            )

                await asyncio.sleep(2)   # 429-Schutz zwischen Yahoo-Calls

                # DXY 24h Change
                dxy_resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=2d&interval=1d")
                if dxy_resp.status_code != 429:
                    dxy_data = dxy_resp.json()
                    dxy_closes = [c for c in dxy_data['chart']['result'][0]['indicators']['quote'][0]['close'] if c is not None]
                    if len(dxy_closes) >= 2:
                        results["DXY_Change"] = (dxy_closes[-1] - dxy_closes[-2]) / dxy_closes[-2]
                        success_parts += 1
                else:
                    self.logger.warning("yFinance DXY Rate Limit (429). Nutze Cache.")
                
                latency = (time.perf_counter() - start) * 1000
                if success_parts == 2:
                    status = "online"
                elif success_parts == 1:
                    status = "degraded"
                else:
                    status = "offline"
                await self._report_health("yFinance_Macro", status, latency)
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.logger.warning(f"yFinance Macro Fehler: {e}. Nutze Cache.")
            await self._report_health("yFinance_Macro", "offline", latency)
            
        return results

    async def _fetch_binance_rest_data(self) -> None:
        """
        Holt Open Interest, Long/Short Ratio, Perp Basis und 24h Change von Binance.
        Kostenlos — kein API-Key nötig für öffentliche Futures-Endpunkte.
        Wird bei jedem Agent-Cycle aufgerufen (ca. alle 300 Sekunden).
        """
        start = time.perf_counter()
        headers = {"User-Agent": self._user_agent}
        success_parts = 0

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:

                # ── 1. Open Interest (Binance Futures) ──────────
                try:
                    resp = await client.get(
                        "https://fapi.binance.com/fapi/v1/openInterest",
                        params={"symbol": "BTCUSDT"}
                    )
                    if resp.status_code == 200:
                        oi_data = resp.json()
                        new_oi = float(oi_data.get("openInterest", 0))
                        # Vorherigen Wert nur überschreiben wenn valider neuer Wert
                        if new_oi > 0:
                            self.oi_prev = self.open_interest if self.open_interest > 0 else new_oi
                            self.open_interest = new_oi
                            success_parts += 1
                    else:
                        self.logger.debug(f"Binance OI HTTP {resp.status_code}")
                except Exception as e:
                    self.logger.warning(f"Binance OI Fehler: {e}")

                await asyncio.sleep(0.2)  # Rate-Limit-Schutz zwischen Calls

                # ── 2. Top Trader Long/Short Ratio ──────────────
                try:
                    resp = await client.get(
                        "https://fapi.binance.com/futures/data/topLongShortAccountRatio",
                        params={"symbol": "BTCUSDT", "period": "5m", "limit": 1}
                    )
                    if resp.status_code == 200:
                        ls_data = resp.json()
                        if ls_data and isinstance(ls_data, list):
                            self.long_short_ratio = float(
                                ls_data[0].get("longShortRatio", 1.0)
                            )
                            success_parts += 1
                    else:
                        self.logger.debug(f"Binance L/S HTTP {resp.status_code}")
                except Exception as e:
                    self.logger.warning(f"Binance L/S Ratio Fehler: {e}")

                await asyncio.sleep(0.2)

                # ── 3. 24h Ticker + Perp Basis ───────────────────
                try:
                    # Spot-Preis für Perp-Basis-Berechnung
                    resp_spot = await client.get(
                        "https://api.binance.com/api/v3/ticker/24hr",
                        params={"symbol": "BTCUSDT"}
                    )
                    await asyncio.sleep(0.1)
                    # Futures-Preis für Perp-Basis
                    resp_futures = await client.get(
                        "https://fapi.binance.com/fapi/v1/ticker/price",
                        params={"symbol": "BTCUSDT"}
                    )

                    if resp_spot.status_code == 200:
                        ticker = resp_spot.json()
                        change_pct = float(ticker.get("priceChangePercent", 0))
                        self.btc_change_24h = change_pct / 100.0  # → Dezimal

                        spot_price = float(ticker.get("lastPrice", 0))
                        if resp_futures.status_code == 200 and spot_price > 0:
                            futures_price = float(resp_futures.json().get("price", 0))
                            self.perp_basis_pct = (
                                (futures_price - spot_price) / spot_price * 100
                            )
                        success_parts += 1
                    else:
                        self.logger.debug(f"Binance 24hr HTTP {resp_spot.status_code}")

                except Exception as e:
                    self.logger.warning(f"Binance 24hr/Basis Fehler: {e}")

            latency = (time.perf_counter() - start) * 1000
            if success_parts == 3:
                status = "online"
            elif success_parts > 0:
                status = "degraded"
            else:
                status = "offline"
            await self._report_health("Binance_REST", status, latency)
            self.logger.debug(
                f"Binance REST: OI={self.open_interest:,.0f} | "
                f"L/S={self.long_short_ratio:.2f} | "
                f"Basis={self.perp_basis_pct:.3f}% | "
                f"BTC_24h={self.btc_change_24h:.2%}"
            )

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("Binance_REST", "offline", latency)
            self.logger.warning(
                f"Binance REST gesamt Fehler: {e} — nutze Cache-Werte"
            )

    async def _fetch_deribit_data(self) -> None:
        """
        Holt Put/Call Ratio und DVOL von Deribit Public API.
        Kein API-Key erforderlich — alle /public/ Endpunkte sind frei zugänglich.
        Intervall: alle 15 Minuten (self._deribit_interval).

        PCR < 0.40 → stark bullish (Call-Dominanz)
        PCR 0.40–0.70 → neutral
        PCR > 0.80 → Hedge-Druck (bearish)
        DVOL > 80 → erhöhte Vola → konservativeres Sizing
        """
        now = time.time()
        if now - self._last_deribit_fetch < self._deribit_interval:
            return   # Noch nicht fällig
        self._last_deribit_fetch = now

        start = time.perf_counter()
        success_parts = 0
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:

                # ── 1. Put/Call Ratio ────────────────────────────
                try:
                    resp = await client.get(
                        "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
                        params={"currency": "BTC", "kind": "option"}
                    )
                    if resp.status_code == 200:
                        instruments = resp.json().get("result", [])
                        puts_oi = sum(
                            float(i.get("open_interest", 0))
                            for i in instruments
                            if "-P" in i.get("instrument_name", "")
                        )
                        calls_oi = sum(
                            float(i.get("open_interest", 0))
                            for i in instruments
                            if "-C" in i.get("instrument_name", "")
                        )
                        if calls_oi > 0:
                            self.put_call_ratio = puts_oi / calls_oi
                            success_parts += 1
                    else:
                        self.logger.debug(f"Deribit PCR HTTP {resp.status_code}")
                except Exception as e:
                    self.logger.warning(f"Deribit PCR Fehler: {e}")

                await asyncio.sleep(0.5)

                # ── 2. DVOL (BTC Implied Volatility Index) ───────
                try:
                    end_ts = int(time.time() * 1000)
                    start_ts = end_ts - (3600 * 1000)   # Letzte Stunde
                    resp = await client.get(
                        "https://www.deribit.com/api/v2/public/get_volatility_index_data",
                        params={
                            "currency": "BTC",
                            "start_timestamp": start_ts,
                            "end_timestamp": end_ts,
                            "resolution": "3600"
                        }
                    )
                    if resp.status_code == 200:
                        result = resp.json().get("result", {})
                        data_points = result.get("data", [])
                        if data_points:
                            # Format: [timestamp, open, high, low, close]
                            self.dvol = float(data_points[-1][4])
                            success_parts += 1
                    else:
                        self.logger.debug(f"Deribit DVOL HTTP {resp.status_code}")
                except Exception as e:
                    self.logger.warning(f"Deribit DVOL Fehler: {e}")

            latency = (time.perf_counter() - start) * 1000
            if success_parts == 2:
                status = "online"
            elif success_parts > 0:
                status = "degraded"
            else:
                status = "offline"
            await self._report_health("Deribit_Public", status, latency)
            self.logger.info(
                f"Deribit Update: PCR={self.put_call_ratio:.3f} | "
                f"DVOL={self.dvol:.1f}"
            )

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            await self._report_health("Deribit_Public", "offline", latency)
            self.logger.warning(
                f"Deribit gesamt Fehler: {e} — nutze Cache-Werte "
                f"(PCR={self.put_call_ratio:.3f}, DVOL={self.dvol:.1f})"
            )

    def calculate_grss(self, data: dict) -> float:
        """
        Global Risk Sentiment Score — 0 bis 100.

        EISERNE REGEL: Kein random.uniform(). Kein random.random(). Niemals.
        Jeder Input muss aus einer echten Datenquelle stammen.

        Unter 40: Veto aktiv → kein Trading.
        Über 65:  Signal-Qualität gut.

        Gewichtung: Makro 30% | Derivatives 40% | Sentiment 30%
        """
        score = 50.0  # Neutral-Basis

        fresh_source_count = int(data.get("fresh_source_count", 0) or 0)
        data_freshness_ok = bool(data.get("data_freshness_ok", fresh_source_count > 0))
        if not data_freshness_ok or fresh_source_count <= 0:
            return 0.0

        # ═══════════════════════════════════════════════════
        # MAKRO LAYER (~30 Punkte)
        # ═══════════════════════════════════════════════════

        ndx = data.get("ndx_status", "BULLISH")
        yields = data.get("yields_10y", 4.3)
        vix = data.get("vix", 20.0)
        dxy_change = data.get("dxy_change_pct", 0.0)   # Bereits in Prozent
        btc_change_24h = data.get("btc_change_24h", 0.0)  # Dezimal (0.02 = +2%)

        # Nasdaq SMA200: asymmetrisch — Bear bestraft stärker als Bull belohnt
        if ndx == "BULLISH":
            score += 15.0
        elif ndx == "BEARISH":
            score -= 20.0

        # 10Y Yields
        if yields < 4.0:    score += 8.0
        elif yields > 4.5:  score -= 10.0

        # VIX
        if vix < 15:        score += 7.0
        elif vix > 25:      score -= 15.0
        elif vix > 20:      score -= 7.0

        # DXY Decoupling: BTC steigt trotz starkem Dollar
        # = institutionelles Kaufinteresse unabhängig vom Makro
        if dxy_change > 0.5 and btc_change_24h > 0:
            score += 10.0

        # ═══════════════════════════════════════════════════
        # DERIVATIVES LAYER (~40 Punkte)
        # ═══════════════════════════════════════════════════

        funding = data.get("funding_rate", 0.01)
        oi_delta_pct = data.get("oi_delta_pct", 0.0)
        btc_change_1h = data.get("btc_change_1h", 0.0)
        pcr = data.get("put_call_ratio", 0.6)
        basis = data.get("perp_basis_pct", 0.03)

        # Funding Rate (Binance Perpetual)
        if -0.010 <= funding <= 0.030:  score += 10.0   # Gesundes Niveau
        elif funding > 0.050:           score -= 15.0   # Longs überhitzt → Squeeze-Risiko
        elif funding < -0.010:          score += 5.0    # Short-Dominanz → Reversal-Potenzial

        # OI-Delta: Steigt OI bei steigendem Preis = echte Akkumulation
        if oi_delta_pct > 0 and btc_change_1h > 0:     score += 10.0
        elif oi_delta_pct > 0 and btc_change_1h < 0:   score -= 8.0    # Shorts bauen auf

        # Put/Call Ratio (Deribit Options)
        if pcr < 0.40:      score += 12.0   # Call-Dominanz = institutionell bullish
        elif pcr > 0.80:    score -= 10.0   # Hedge-Druck

        # Perp Basis (Futures Premium über Spot)
        if 0.01 <= basis <= 0.05:   score += 5.0    # Gesundes Premium
        elif basis > 0.10:          score -= 10.0   # Überhitztes Premium

        # ═══════════════════════════════════════════════════
        # SENTIMENT LAYER (~30 Punkte)
        # ═══════════════════════════════════════════════════

        fear_greed = data.get("fear_greed", 50)
        etf_flows = data.get("etf_flows_3d_m", 0.0)   # 0.0 = neutral (bis CoinGlass)
        llm_sentiment = data.get("llm_news_sentiment", 0.0)  # -1.0 bis +1.0

        # Fear & Greed Index (0–100)
        fng_norm = (fear_greed - 50) / 50.0   # → -1.0 bis +1.0
        score += fng_norm * 15.0

        # ETF Flows (Platzhalter 0.0 bis Phase B CoinGlass)
        if etf_flows > 500:     score += 10.0
        elif etf_flows < -500:  score -= 15.0

        # LLM News Sentiment (aus SentimentAgent, echte CryptoPanic-Daten)
        score += llm_sentiment * 10.0

        # ═══════════════════════════════════════════════════
        # HARD VETOES — überschreiben alles
        # ═══════════════════════════════════════════════════

        news_silence = data.get("news_silence_seconds", 0)
        if news_silence > 3600:
            return 0.0   # Kein Datenstrom = kein Trading

        if vix > 35:
            return 10.0  # Markt-Crash-Modus

        if ndx == "BEARISH" and funding > 0.05:
            return 5.0   # Bärenmarkt + überhitzte Longs = maximales Risiko

        # ═══════════════════════════════════════════════════
        # VELOCITY CHECK — schneller GRSS-Fall warnt früher
        # ═══════════════════════════════════════════════════

        grss_30min_ago = data.get("grss_30min_ago", score)
        velocity = score - grss_30min_ago
        if velocity < -20:
            # Markt kippt schnell → präventiv unter Veto-Schwelle
            score = min(score, 38.0)

        return max(0.0, min(100.0, round(score, 1)))

    async def process(self) -> None:
        """
        Hauptzyklus des ContextAgent.
        Läuft alle 300 Sekunden (5 Minuten).
        Berechnet den GRSS aus echten Datenquellen.

        EISERNE REGEL: Kein random. Kein Mock. Kein Dummy.
        """
        try:
            # ── 1. Makro-Daten (15-Min-Cache intern) ─────────────
            now_t = time.time()
            if now_t - self._last_macro_fetch > self._macro_interval:
                self.logger.info("Makro-Update gestartet...")
                self.yields_10y = await self._fetch_fred_yields()
                macro_data = await self._fetch_vix_and_dxy()
                self.vix = macro_data.get("VIX", self.vix)
                self.dxy_change = macro_data.get("DXY_Change", self.dxy_change)
                self.ndx_status = await self._fetch_nasdaq_status()
                self._last_macro_fetch = now_t
                self.logger.info(
                    f"Makro: NDX={self.ndx_status} | "
                    f"VIX={self.vix:.1f} | "
                    f"Yields={self.yields_10y:.2f}%"
                )

            # ── 2. Binance REST (bei jedem Cycle) ────────────────
            await self._fetch_binance_rest_data()

            # ── 3. Deribit Public (15-Min-Cache intern) ──────────
            await self._fetch_deribit_data()

            # ── 4. BTC 1h Change aus Redis-Ticker ────────────────
            btc_ticker = await self.deps.redis.get_cache("market:ticker:BTCUSDT") or {}
            btc_price_now = float(btc_ticker.get("last_price", 0))

            btc_1h_cache = await self.deps.redis.get_cache("bruno:ctx:btc_1h_ago") or {}
            btc_price_1h_ago = float(btc_1h_cache.get("price", btc_price_now))
            btc_change_1h = (
                (btc_price_now - btc_price_1h_ago) / btc_price_1h_ago
                if btc_price_1h_ago > 0 else 0.0
            )
            # Aktuellen Preis für nächsten 1h-Vergleich speichern
            if btc_price_now > 0:
                await self.deps.redis.set_cache(
                    "bruno:ctx:btc_1h_ago",
                    {
                        "price": btc_price_now,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    ttl=3900   # 65 Min TTL
                )

            # ── 5. OI-Delta berechnen ─────────────────────────────
            oi_delta_pct = 0.0
            if self.oi_prev > 0 and self.open_interest > 0:
                oi_delta_pct = (self.open_interest - self.oi_prev) / self.oi_prev * 100

            # ── 6. Funding Rate aus Redis ─────────────────────────
            funding_data = await self.deps.redis.get_cache(
                "market:funding:BTCUSDT"
            ) or {}
            funding_rate = float(funding_data.get("rate", 0.010))

            # ── 7. Fear & Greed aus Redis ─────────────────────────
            fng_data = await self.deps.redis.get_cache("macro:fear_and_greed") or {}
            fear_greed = int(fng_data.get("value", 50))

            # ── 8. LLM News Sentiment aus SentimentAgent ─────────
            sentiment_data = await self.deps.redis.get_cache(
                "bruno:sentiment:aggregate"
            ) or {}
            llm_news_sentiment = float(sentiment_data.get("average_score", 0.0))

            # ── 8b. Daten-Freshness aus Health-Telemetrie ────────
            health_sources = await self.deps.redis.get_cache("bruno:health:sources") or {}
            fresh_source_count = 0
            freshness_cutoff_seconds = 1800
            for source_name in ("Binance_REST", "Deribit_Public", "yFinance_Macro", "FRED_Yields", "CryptoPanic"):
                source_health = health_sources.get(source_name) or {}
                status = source_health.get("status")
                last_update_str = source_health.get("last_update")
                if status not in {"online", "degraded"} or not last_update_str:
                    continue

                try:
                    last_update = datetime.fromisoformat(last_update_str)
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()
                    if age_seconds <= freshness_cutoff_seconds:
                        fresh_source_count += 1
                except Exception:
                    continue

            data_freshness_ok = fresh_source_count > 0

            # ── 9. News-Watchdog ──────────────────────────────────
            ingestion_status = await self.deps.redis.get_cache(
                "bruno:ingestion:last_message"
            )
            if ingestion_status:
                last_ts_str = ingestion_status.get(
                    "timestamp",
                    datetime.now(timezone.utc).isoformat()
                )
                last_ts = datetime.fromisoformat(last_ts_str)
                # Stelle sicher dass last_ts timezone-aware ist
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                news_silence_seconds = (
                    datetime.now(timezone.utc) - last_ts
                ).total_seconds()
            else:
                news_silence_seconds = 0  # Beim Start: kein Silence

            # ── 10. GRSS Velocity aus History ────────────────────
            grss_30min_ago = 50.0
            if self.grss_history:
                cutoff_ts = datetime.now(timezone.utc).timestamp() - 1800
                old = [e for e in self.grss_history if e["ts"] < cutoff_ts]
                if old:
                    grss_30min_ago = old[-1]["grss"]

            # ── 11. GRSS berechnen ────────────────────────────────
            grss_input = {
                "ndx_status": self.ndx_status,
                "yields_10y": self.yields_10y,
                "vix": self.vix,
                "dxy_change_pct": self.dxy_change * 100,   # Dezimal → Prozent
                "btc_change_24h": self.btc_change_24h,
                "btc_change_1h": btc_change_1h,
                "funding_rate": funding_rate,
                "oi_delta_pct": oi_delta_pct,
                "put_call_ratio": self.put_call_ratio,
                "perp_basis_pct": self.perp_basis_pct,
                "fear_greed": fear_greed,
                "etf_flows_3d_m": 0.0,           # Neutral-Platzhalter bis Phase B
                "llm_news_sentiment": llm_news_sentiment,
                "news_silence_seconds": news_silence_seconds,
                "grss_30min_ago": grss_30min_ago,
                "fresh_source_count": fresh_source_count,
                "data_freshness_ok": data_freshness_ok,
            }

            grss = self.calculate_grss(grss_input)

            # ── 12. GRSS-History für Velocity-Tracking ───────────
            self.grss_history.append({
                "ts": datetime.now(timezone.utc).timestamp(),
                "grss": grss
            })
            self.grss_history = self.grss_history[-6:]   # Max 6 Einträge

            # ── 13. Stress Score (Abwärts-Kompatibilität) ────────
            stress_score = 0.0
            if self.vix > 20:           stress_score += (self.vix - 20) * 3.0
            if self.yields_10y > 4.5:   stress_score += 20.0
            if self.ndx_status == "BEARISH":    stress_score += 30.0
            if news_silence_seconds > 3600:     stress_score = 100.0
            if not data_freshness_ok:           stress_score = 100.0
            stress_score = max(0.0, min(100.0, stress_score))

            # ── 14. Payload publizieren ───────────────────────────
            # WICHTIG: Bestehende Keys beibehalten (RiskAgent ist abhängig davon)
            payload = {
                # ── Keys die RiskAgent erwartet (NICHT umbenennen) ──
                "GRSS_Score": grss,
                "Stress_Score": round(stress_score, 1),
                "Macro_Status": self.ndx_status,
                "Yields_10Y": round(self.yields_10y, 2),
                "VIX": round(self.vix, 2),
                "Veto_Active": grss < 40 or news_silence_seconds > 3600 or not data_freshness_ok,
                "Reason": (
                    f"GRSS={grss:.1f} | NDX={self.ndx_status} | "
                    f"VIX={self.vix:.1f} | PCR={self.put_call_ratio:.2f}"
                    + (f" | DATA_FRESHNESS=STALE({fresh_source_count})" if not data_freshness_ok else "")
                ),
                "last_update": datetime.now(timezone.utc).isoformat(),

                # ── Neue Keys für Dashboard und LLM-Kaskade ──────
                "DVOL": round(self.dvol, 1),
                "Put_Call_Ratio": round(self.put_call_ratio, 3),
                "OI_Delta_Pct": round(oi_delta_pct, 2),
                "Perp_Basis_Pct": round(self.perp_basis_pct, 3),
                "Long_Short_Ratio": round(self.long_short_ratio, 2),
                "BTC_Change_24h_Pct": round(self.btc_change_24h * 100, 2),
                "BTC_Change_1h_Pct": round(btc_change_1h * 100, 2),
                "Fear_Greed": fear_greed,
                "LLM_News_Sentiment": round(llm_news_sentiment, 3),
                "Funding_Rate": round(funding_rate, 6),
                "DXY_Change_Pct": round(self.dxy_change * 100, 2),
                "ETF_Flows_3d_M": 0.0,   # Neutral bis CoinGlass Phase B
                "News_Silence_Seconds": int(news_silence_seconds),
                "GRSS_Velocity_30min": round(grss - grss_30min_ago, 1),
                "Data_Freshness_Active": data_freshness_ok,
                "Fresh_Source_Count": fresh_source_count,
            }

            await self.deps.redis.set_cache(
                "bruno:context:grss", payload, ttl=3600
            )
            await self.deps.redis.publish_message(
                "bruno:context:grss", json.dumps(payload)
            )

            # ── 15. Logging ───────────────────────────────────────
            if grss < 40:
                self.logger.warning(
                    f"⛔ VETO AKTIV | GRSS={grss:.1f} | {payload['Reason']}"
                )
            else:
                self.logger.info(
                    f"✅ GRSS={grss:.1f} | NDX={self.ndx_status} | "
                    f"VIX={self.vix:.1f} | PCR={self.put_call_ratio:.2f} | "
                    f"DVOL={self.dvol:.0f} | Funding={funding_rate:.4%}"
                )

        except Exception as e:
            self.logger.error(f"ContextAgent process() Fehler: {e}", exc_info=True)
