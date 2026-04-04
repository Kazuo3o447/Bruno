"""
CryptoCompare API Client für News- und Marktdaten.
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CryptoCompareClient:
    """Client für die CryptoCompare API."""

    BASE_URL = "https://min-api.cryptocompare.com/data"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "authorization": f"Apikey {self.api_key}",
                    "Accept": "application/json",
                    "Accept-Encoding": "deflate, gzip",
                }
            )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

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
                params=params or {},
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning("CryptoCompare HTTP %s for %s: %s", response.status, path, body[:240])
                    return None
                return await response.json()
        except asyncio.TimeoutError:
            logger.warning("CryptoCompare request timeout for %s", path)
        except Exception as e:
            logger.error("CryptoCompare request error for %s: %s", path, e)
        return None

    async def get_news(self, limit: int = 50, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Holt News von CryptoCompare."""
        if not self.api_key:
            logger.warning("CryptoCompare API Key nicht gesetzt")
            return []

        params: Dict[str, Any] = {
            "lang": "EN",
            "sortOrder": "latest",
            "limit": max(1, min(limit, 100)),
        }
        if categories:
            params["categories"] = ",".join(categories)

        data = await self._request_json("/v2/news/", params=params, timeout_seconds=12.0)
        if not data or data.get("Type") != 100:
            logger.warning("CryptoCompare News API returned no usable data")
            return []

        transformed_news: List[Dict[str, Any]] = []
        for item in data.get("Data", []):
            if not isinstance(item, dict):
                continue
            source_info = item.get("source_info") or {}
            published_on = item.get("published_on")
            transformed_news.append({
                "title": (item.get("title") or "").strip(),
                "body": (item.get("body") or "").strip(),
                "url": item.get("url"),
                "source": source_info.get("name") or item.get("source") or "CryptoCompare",
                "source_url": source_info.get("url") or item.get("url"),
                "image_url": item.get("imageurl") or item.get("imageURL") or source_info.get("img"),
                "published_at": datetime.fromtimestamp(published_on, tz=timezone.utc) if published_on else None,
                "categories": item.get("categories") or [],
                "language": item.get("lang") or "EN",
                "sentiment": self._extract_sentiment(item),
            })

        logger.info("CryptoCompare: %s News-Artikel geladen", len(transformed_news))
        return transformed_news

    def _extract_sentiment(self, news_item: Dict[str, Any]) -> Optional[str]:
        sentiment_info = news_item.get("sentiment", {})
        if isinstance(sentiment_info, dict):
            return sentiment_info.get("sentiment")
        return None

    async def get_price(self, fsym: str = "BTC", tsym: str = "USD") -> Optional[float]:
        data = await self._request_json("/price", params={"fsym": fsym.upper(), "tsyms": tsym.upper()}, timeout_seconds=5.0)
        if not data:
            return None
        return data.get(tsym.upper())

    async def get_multi_price(self, symbols: List[str], tsym: str = "USD") -> Dict[str, Dict[str, Any]]:
        if not symbols:
            return {}

        data = await self._request_json(
            "/pricemultifull",
            params={"fsyms": ",".join(sorted({s.upper() for s in symbols})), "tsyms": tsym.upper()},
            timeout_seconds=8.0,
        )
        if not data:
            return {}

        display = data.get("DISPLAY", {}) or {}
        raw = data.get("RAW", {}) or {}
        result: Dict[str, Dict[str, Any]] = {}
        for symbol in symbols:
            sym = symbol.upper()
            raw_row = (raw.get(sym) or {}).get(tsym.upper(), {})
            display_row = (display.get(sym) or {}).get(tsym.upper(), {})
            result[sym] = {
                "price": raw_row.get("PRICE"),
                "open_24h": raw_row.get("OPEN24HOUR"),
                "high_24h": raw_row.get("HIGH24HOUR"),
                "low_24h": raw_row.get("LOW24HOUR"),
                "volume_24h": raw_row.get("VOLUME24HOUR"),
                "volume_to_24h": raw_row.get("VOLUME24HOURTO"),
                "market_cap": raw_row.get("MKTCAP"),
                "change_pct_24h": raw_row.get("CHANGEPCT24HOUR"),
                "display": display_row,
            }
        return result

    async def get_history(
        self,
        fsym: str = "BTC",
        tsym: str = "USD",
        timeframe: str = "day",
        limit: int = 30,
        aggregate: int = 1,
    ) -> List[Dict[str, Any]]:
        endpoint_map = {
            "minute": "/v2/histominute",
            "hour": "/v2/histohour",
            "day": "/v2/histoday",
        }
        endpoint = endpoint_map.get(timeframe.lower(), "/v2/histoday")
        data = await self._request_json(
            endpoint,
            params={"fsym": fsym.upper(), "tsym": tsym.upper(), "limit": limit, "aggregate": aggregate},
            timeout_seconds=10.0,
        )
        if not data:
            return []

        rows = (data.get("Data") or {}).get("Data") if isinstance(data.get("Data"), dict) else data.get("Data", [])
        if not isinstance(rows, list):
            rows = []

        history: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            history.append({
                "time": row.get("time"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume_from": row.get("volumefrom"),
                "volume_to": row.get("volumeto"),
            })
        return history

    async def get_top_coins(self, limit: int = 10, tsym: str = "USD") -> List[Dict[str, Any]]:
        data = await self._request_json(
            "/top/mktcapfull",
            params={"limit": limit, "tsym": tsym.upper()},
            timeout_seconds=10.0,
        )
        if not data:
            return []

        entries = data.get("Data") or []
        top_coins: List[Dict[str, Any]] = []
        for item in entries[:limit]:
            if not isinstance(item, dict):
                continue
            coin = item.get("CoinInfo", {}) or {}
            raw_row = (item.get("RAW") or {}).get(tsym.upper(), {})
            display_row = (item.get("DISPLAY") or {}).get(tsym.upper(), {})
            top_coins.append({
                "symbol": coin.get("Name"),
                "name": coin.get("FullName"),
                "price": raw_row.get("PRICE"),
                "market_cap": raw_row.get("MKTCAP"),
                "volume_24h": raw_row.get("VOLUME24HOURTO"),
                "change_pct_24h": raw_row.get("CHANGEPCT24HOUR"),
                "display": display_row,
            })
        return top_coins

    async def get_top_exchanges(self, fsym: str = "BTC", tsym: str = "USD", limit: int = 10) -> List[Dict[str, Any]]:
        data = await self._request_json(
            "/top/exchanges/full",
            params={"fsym": fsym.upper(), "tsym": tsym.upper(), "limit": limit},
            timeout_seconds=10.0,
        )
        if not data:
            return []

        entries = data.get("Data") or []
        result: List[Dict[str, Any]] = []
        for item in entries[:limit]:
            if not isinstance(item, dict):
                continue
            exchange = item.get("MARKET") or item.get("Exchange") or item.get("exchange")
            raw_row = (item.get("RAW") or {}).get(tsym.upper(), {})
            display_row = (item.get("DISPLAY") or {}).get(tsym.upper(), {})
            result.append({
                "exchange": exchange,
                "price": raw_row.get("PRICE"),
                "volume_24h": raw_row.get("VOLUME24HOURTO"),
                "volume_from_24h": raw_row.get("VOLUME24HOUR"),
                "spread_pct": raw_row.get("SPREADPCT"),
                "display": display_row,
            })
        return result

    async def get_social_stats(self, coin_name: str) -> Dict[str, Any]:
        data = await self._request_json(
            "/social/coin/latest",
            params={"coinName": coin_name.upper()},
            timeout_seconds=10.0,
        )
        return data.get("Data", {}) if data else {}

    async def get_blockchain_stats(self, symbol: str) -> Dict[str, Any]:
        data = await self._request_json(
            "/blockchain/histo/day",
            params={"fsym": symbol.upper(), "limit": 30},
            timeout_seconds=10.0,
        )
        if not data:
            return {}

        payload = data.get("Data", {})
        rows = payload.get("Data") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            rows = []

        return {
            "symbol": symbol.upper(),
            "rows": rows,
            "latest": rows[-1] if rows else {},
        }

    async def get_market_bundle(self, symbols: Optional[List[str]] = None, tsym: str = "USD") -> Dict[str, Any]:
        symbols = [s.upper() for s in (symbols or ["BTC", "ETH"])]
        primary_symbol = symbols[0]

        price_snapshot, top_coins, top_exchanges, history_btc, social_btc, blockchain_btc = await asyncio.gather(
            self.get_multi_price(symbols, tsym=tsym),
            self.get_top_coins(limit=10, tsym=tsym),
            self.get_top_exchanges(primary_symbol, tsym=tsym, limit=5),
            self.get_history(primary_symbol, tsym=tsym, timeframe="day", limit=7),
            self.get_social_stats(primary_symbol),
            self.get_blockchain_stats(primary_symbol),
            return_exceptions=True,
        )

        def _safe_value(value: Any, default: Any) -> Any:
            return default if isinstance(value, Exception) else value

        price_snapshot = _safe_value(price_snapshot, {})
        top_coins = _safe_value(top_coins, [])
        top_exchanges = _safe_value(top_exchanges, [])
        history_btc = _safe_value(history_btc, [])
        social_btc = _safe_value(social_btc, {})
        blockchain_btc = _safe_value(blockchain_btc, {})

        historical_summary: Dict[str, Any] = {}
        if history_btc:
            first_close = history_btc[0].get("close") or 0
            last_close = history_btc[-1].get("close") or 0
            change_pct = ((last_close - first_close) / first_close * 100.0) if first_close else 0.0
            historical_summary[primary_symbol] = {
                "rows": len(history_btc),
                "first_close": first_close,
                "last_close": last_close,
                "change_pct": round(change_pct, 3),
                "high": max((row.get("high") or 0) for row in history_btc),
                "low": min((row.get("low") or 0) for row in history_btc),
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols": symbols,
            "tsym": tsym.upper(),
            "price_snapshot": price_snapshot,
            "top_coins": top_coins,
            "top_exchanges": top_exchanges,
            "historical_summary": historical_summary,
            "social_stats_raw": {primary_symbol: social_btc},
            "blockchain_stats_raw": {primary_symbol: blockchain_btc},
        }

    async def health_check(self) -> bool:
        if not self.api_key:
            return False

        data = await self._request_json("/v2/news/", params={"lang": "EN", "limit": 1}, timeout_seconds=5.0)
        return bool(data and data.get("Type") == 100)


_cryptocompare_client: Optional[CryptoCompareClient] = None


def get_cryptocompare_client(api_key: Optional[str] = None) -> CryptoCompareClient:
    global _cryptocompare_client

    if _cryptocompare_client is None:
        if not api_key:
            from app.core.config import settings
            api_key = settings.CRYPTOCOMPARE_API_KEY

        _cryptocompare_client = CryptoCompareClient(api_key)

    return _cryptocompare_client