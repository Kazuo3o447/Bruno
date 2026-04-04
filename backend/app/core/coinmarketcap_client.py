"""
CoinMarketCap API Client für Bitcoin-zentrierte News- und Marktdaten.
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class CoinMarketCapClient:
    """Client für die CoinMarketCap API."""

    BASE_URL = "https://pro-api.coinmarketcap.com"
    BTC_SYMBOL = "BTC"
    BTC_ID = 1

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        """Erstellt eine aioHTTP Session."""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "X-CMC_PRO_API_KEY": self.api_key,
                    "Accept": "application/json",
                    "Accept-Encoding": "deflate, gzip",
                }
            )

    async def close(self):
        """Schließt die aioHTTP Session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _with_auth(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged = dict(params or {})
        return merged

    async def _request_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        await self.connect()
        if not self.session:
            return None

        try:
            async with self.session.get(
                f"{self.BASE_URL}{path}",
                params=self._with_auth(params),
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning("CoinMarketCap HTTP %s for %s: %s", response.status, path, body[:240])
                    return None
                return await response.json()
        except asyncio.TimeoutError:
            logger.warning("CoinMarketCap request timeout for %s", path)
        except Exception as e:
            logger.error("CoinMarketCap request error for %s: %s", path, e)
        return None

    @staticmethod
    def _contains_bitcoin_text(value: Any) -> bool:
        if value is None:
            return False
        text = str(value).lower()
        return "bitcoin" in text or "btc" in text

    @staticmethod
    def _normalize_ohlcv_row(row: Dict[str, Any], convert: str) -> Dict[str, Any]:
        quote = row.get("quote") or row.get(convert.upper()) or row.get(convert.lower()) or {}
        if isinstance(quote, dict) and convert.upper() in quote:
            quote = quote.get(convert.upper()) or {}
        if not isinstance(quote, dict):
            quote = {}

        return {
            "time": row.get("time_open") or row.get("timestamp") or row.get("time_close"),
            "open": row.get("open") or quote.get("open"),
            "high": row.get("high") or quote.get("high"),
            "low": row.get("low") or quote.get("low"),
            "close": row.get("close") or quote.get("close"),
            "volume": row.get("volume") or quote.get("volume"),
            "market_cap": quote.get("market_cap"),
            "timestamp": row.get("timestamp") or row.get("time_open"),
        }

    @staticmethod
    def _extract_items(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("items", "data", "Data", "news", "content", "trends"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    async def get_btc_quote(self, convert: str = "USD") -> Optional[Dict[str, Any]]:
        """Holt den aktuellen Bitcoin-Quote."""
        data = await self._request_json(
            "/v1/cryptocurrency/quotes/latest",
            params={"symbol": self.BTC_SYMBOL, "convert": convert.upper()},
            timeout_seconds=8.0,
        )
        if not data:
            return None

        btc_data = (data.get("data") or {}).get(self.BTC_SYMBOL) or {}
        quote = (btc_data.get("quote") or {}).get(convert.upper()) or {}
        if not quote:
            return None

        return {
            "symbol": self.BTC_SYMBOL,
            "name": btc_data.get("name") or "Bitcoin",
            "slug": btc_data.get("slug") or "bitcoin",
            "price": quote.get("price"),
            "market_cap": quote.get("market_cap"),
            "volume_24h": quote.get("volume_24h"),
            "volume_change_24h": quote.get("volume_change_24h"),
            "percent_change_1h": quote.get("percent_change_1h"),
            "percent_change_24h": quote.get("percent_change_24h"),
            "percent_change_7d": quote.get("percent_change_7d"),
            "percent_change_30d": quote.get("percent_change_30d"),
            "last_updated": quote.get("last_updated") or btc_data.get("last_updated"),
            "circulating_supply": btc_data.get("circulating_supply"),
            "total_supply": btc_data.get("total_supply"),
            "max_supply": btc_data.get("max_supply"),
        }

    async def get_global_metrics(self) -> Dict[str, Any]:
        """Holt globale Marktmetriken inklusive Bitcoin-Dominanz."""
        data = await self._request_json(
            "/v1/global-metrics/quotes/latest",
            params={},
            timeout_seconds=8.0,
        )
        if not data:
            return {}

        payload = data.get("data") or {}
        quote = (payload.get("quote") or {}).get("USD") or payload.get("quote") or {}
        return {
            "btc_dominance": payload.get("btc_dominance"),
            "eth_dominance": payload.get("eth_dominance"),
            "active_cryptocurrencies": payload.get("active_cryptocurrencies"),
            "active_exchanges": payload.get("active_exchanges"),
            "active_market_pairs": payload.get("active_market_pairs"),
            "total_market_cap": quote.get("total_market_cap"),
            "total_volume_24h": quote.get("total_volume_24h"),
            "altcoin_market_cap": quote.get("altcoin_market_cap"),
            "stablecoin_volume_24h": quote.get("stablecoin_volume_24h"),
            "stablecoin_market_cap": quote.get("stablecoin_market_cap"),
            "last_updated": payload.get("last_updated") or quote.get("last_updated"),
        }

    async def get_btc_listings_latest(self, convert: str = "USD", limit: int = 100) -> Optional[Dict[str, Any]]:
        """Holt die BTC-Zeile aus den Listings und nutzt nur den freien, unterstützten Endpoint."""
        data = await self._request_json(
            "/v1/cryptocurrency/listings/latest",
            params={"start": 1, "limit": max(1, min(limit, 100)), "convert": convert.upper()},
            timeout_seconds=10.0,
        )
        if not data:
            return None

        rows = data.get("data") or []
        btc_row = None
        for row in rows:
            if isinstance(row, dict) and str(row.get("symbol", "")).upper() == self.BTC_SYMBOL:
                btc_row = row
                break

        if not btc_row:
            return None

        quote = (btc_row.get("quote") or {}).get(convert.upper()) or {}
        return {
            "symbol": btc_row.get("symbol") or self.BTC_SYMBOL,
            "name": btc_row.get("name") or "Bitcoin",
            "slug": btc_row.get("slug") or "bitcoin",
            "rank": btc_row.get("cmc_rank"),
            "price": quote.get("price"),
            "market_cap": quote.get("market_cap"),
            "volume_24h": quote.get("volume_24h"),
            "volume_change_24h": quote.get("volume_change_24h"),
            "percent_change_1h": quote.get("percent_change_1h"),
            "percent_change_24h": quote.get("percent_change_24h"),
            "percent_change_7d": quote.get("percent_change_7d"),
            "last_updated": quote.get("last_updated") or btc_row.get("last_updated"),
            "circulating_supply": btc_row.get("circulating_supply"),
            "total_supply": btc_row.get("total_supply"),
            "max_supply": btc_row.get("max_supply"),
        }

    async def get_btc_info(self) -> Dict[str, Any]:
        """Holt Metadaten zu Bitcoin."""
        data = await self._request_json(
            "/v1/cryptocurrency/info",
            params={"symbol": self.BTC_SYMBOL},
            timeout_seconds=8.0,
        )
        if not data:
            return {}

        payload = (data.get("data") or {}).get(self.BTC_SYMBOL) or {}
        return {
            "symbol": self.BTC_SYMBOL,
            "name": payload.get("name") or "Bitcoin",
            "slug": payload.get("slug") or "bitcoin",
            "logo": payload.get("logo"),
            "date_added": payload.get("date_added"),
            "description": payload.get("description"),
            "urls": payload.get("urls") or {},
            "platform": payload.get("platform"),
            "tags": payload.get("tags") or [],
        }

    async def get_btc_historical(
        self,
        convert: str = "USD",
        timeframe: str = "daily",
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Holt historische OHLCV-Daten für Bitcoin."""
        now = datetime.now(timezone.utc)
        timeframe = timeframe.lower()
        if timeframe in {"minute", "minutes", "1m"}:
            time_start = now - timedelta(days=7)
            interval = "5m"
        elif timeframe in {"hour", "hourly", "1h"}:
            time_start = now - timedelta(days=max(limit, 24))
            interval = "hourly"
        else:
            time_start = now - timedelta(days=max(limit, 30))
            interval = "daily"

        data = await self._request_json(
            "/v1/cryptocurrency/ohlcv/historical",
            params={
                "symbol": self.BTC_SYMBOL,
                "convert": convert.upper(),
                "time_start": time_start.isoformat(),
                "time_end": now.isoformat(),
                "interval": interval,
            },
            timeout_seconds=12.0,
        )
        if not data:
            return []

        payload = data.get("data") or {}
        rows = payload.get("quotes") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            rows = self._extract_items(payload)

        normalized: List[Dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            normalized.append(self._normalize_ohlcv_row(row, convert))

        return normalized[:limit] if limit else normalized

    async def get_btc_market_pairs(self, convert: str = "USD", limit: int = 10) -> List[Dict[str, Any]]:
        """Holt Marktpaare für Bitcoin, gefiltert auf BTC."""
        data = await self._request_json(
            "/v1/cryptocurrency/market-pairs/latest",
            params={"symbol": self.BTC_SYMBOL, "convert": convert.upper(), "limit": limit},
            timeout_seconds=12.0,
        )
        if not data:
            return []

        payload = data.get("data") or {}
        market_pairs = payload.get("market_pairs") if isinstance(payload, dict) else None
        pairs = market_pairs if isinstance(market_pairs, list) else self._extract_items(payload)

        result: List[Dict[str, Any]] = []
        for item in pairs or []:
            if not isinstance(item, dict):
                continue
            quote = item.get("quote") or {}
            convert_quote = quote.get(convert.upper()) if isinstance(quote, dict) else {}
            result.append({
                "exchange": (item.get("exchange") or {}).get("name") if isinstance(item.get("exchange"), dict) else item.get("exchange_name") or item.get("exchange"),
                "market_pair": item.get("market_pair") or item.get("pair") or item.get("market_pair_base"),
                "price": (convert_quote or {}).get("price"),
                "volume_24h": (convert_quote or {}).get("volume_24h"),
                "effective_liquidity": item.get("effective_liquidity"),
                "last_updated": item.get("last_updated"),
            })

        return result[:limit]

    async def get_content_latest(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Holt CoinMarketCap Content und filtert explizit auf Bitcoin."""
        data = await self._request_json(
            "/v1/content/latest",
            params={"symbol": self.BTC_SYMBOL, "limit": limit},
            timeout_seconds=12.0,
        )
        if not data:
            return []

        items = self._extract_items(data.get("data") or data)
        filtered: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            title = item.get("title") or item.get("headline") or ""
            body = item.get("description") or item.get("content") or item.get("summary") or ""
            tags = item.get("tags") or []
            symbol = item.get("symbol") or item.get("coin_symbol") or item.get("slug") or ""
            combined = " ".join([str(title), str(body), str(tags), str(symbol)])
            if not self._contains_bitcoin_text(combined):
                continue

            filtered.append({
                "id": item.get("id"),
                "title": title,
                "body": body,
                "url": item.get("url") or item.get("link"),
                "source": item.get("source_name") or item.get("source") or "CoinMarketCap",
                "source_url": item.get("url") or item.get("link"),
                "image_url": item.get("thumbnail") or item.get("image") or item.get("image_url"),
                "published_at": item.get("published_at") or item.get("published_on") or item.get("created_at"),
                "categories": ["Bitcoin"],
                "tags": tags if isinstance(tags, list) else [str(tags)] if tags else [],
                "language": item.get("language") or "EN",
                "symbol": self.BTC_SYMBOL,
            })

        return filtered[:limit]

    async def get_community_trends(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Holt Community-/Trend-Daten mit Bitcoin-Filter."""
        data = await self._request_json(
            "/v1/community/trends/latest",
            params={"symbol": self.BTC_SYMBOL, "limit": limit},
            timeout_seconds=12.0,
        )
        if not data:
            return []

        items = self._extract_items(data.get("data") or data)
        filtered: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not self._contains_bitcoin_text(item.get("symbol") or item.get("title") or item.get("name") or item):
                continue
            filtered.append({
                "symbol": self.BTC_SYMBOL,
                "title": item.get("title") or item.get("name") or item.get("topic") or "Bitcoin Trend",
                "score": item.get("score") or item.get("trend_score") or item.get("sentiment"),
                "type": item.get("type") or item.get("category"),
                "published_at": item.get("published_at") or item.get("created_at") or item.get("date"),
                "raw": item,
            })

        return filtered[:limit]

    async def get_btc_bundle(self, convert: str = "USD") -> Dict[str, Any]:
        """Baut ein Bitcoin-zentriertes Daten-Bundle für Dashboard und Agenten."""
        quote, listings_latest, btc_info, global_metrics = await asyncio.gather(
            self.get_btc_quote(convert=convert),
            self.get_btc_listings_latest(convert=convert, limit=100),
            self.get_btc_info(),
            self.get_global_metrics(),
            return_exceptions=True,
        )

        def _safe(value: Any, default: Any) -> Any:
            return default if isinstance(value, Exception) else value

        quote = _safe(quote, None)
        listings_latest = _safe(listings_latest, None)
        btc_info = _safe(btc_info, {})
        global_metrics = _safe(global_metrics, {})

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": self.BTC_SYMBOL,
            "bitcoin_filter": True,
            "convert": convert.upper(),
            "quote": quote,
            "listings_latest": listings_latest,
            "btc_info": btc_info,
            "global_metrics": global_metrics,
        }

    async def health_check(self) -> bool:
        """Führt einen Health Check der API durch."""
        if not self.api_key:
            return False

        data = await self._request_json(
            "/v1/cryptocurrency/quotes/latest",
            params={"symbol": self.BTC_SYMBOL, "convert": "USD"},
            timeout_seconds=5.0,
        )
        return bool(data and (data.get("data") or {}).get(self.BTC_SYMBOL))


_coinmarketcap_client: Optional[CoinMarketCapClient] = None


def get_coinmarketcap_client(api_key: Optional[str] = None) -> CoinMarketCapClient:
    """Gibt die globale CoinMarketCap Client Instanz zurück."""
    global _coinmarketcap_client

    if _coinmarketcap_client is None:
        if not api_key:
            from app.core.config import settings
            api_key = settings.COINMARKETCAP_API_KEY

        _coinmarketcap_client = CoinMarketCapClient(api_key)

    return _coinmarketcap_client
