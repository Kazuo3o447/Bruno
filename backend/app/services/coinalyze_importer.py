"""
Coinalyze Reference Data Importer.

Unabhängige externe Datenquelle für Backtests. Diese Daten sind NICHT Teil
der Live-Trading-Pipeline. Sie dienen ausschließlich der Validierung und
dem Backtest-Harness.

API Docs: https://api.coinalyze.net/v1/doc/
API Key: aus Environment Variable COINALYZE_API_KEY
"""

import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Literal, Any

Interval = Literal["15min", "1hour", "4hour", "daily"]


class CoinalyzeImporter:
    BASE_URL = "https://api.coinalyze.net/v1"
    SYMBOL = "BTCUSD_PERP.A"  # Aggregated BTC Perpetual
    INTERVALS: list[Interval] = ["15min", "1hour", "4hour", "daily"]

    def __init__(self, db_pool, api_key: str | None = None):
        self.db = db_pool
        self.api_key = api_key or os.environ.get("COINALYZE_API_KEY")
        if not self.api_key:
            raise ValueError("COINALYZE_API_KEY not set")
        self.logger = logging.getLogger("coinalyze_importer")

    async def _fetch(self, endpoint: str, params: dict) -> list[Any]:
        """Generic API fetch with error handling."""
        headers = {"api_key": self.api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()

    async def import_candles(self, interval: Interval, from_ts: int | None = None) -> int:
        """
        Import OHLCV candles for given interval.

        If from_ts is None: fetch everything available (initial load).
        If from_ts is set: fetch only newer data (daily update).
        
        Response: [{"symbol": "...", "history": [{"t": 0, "o": 0, "h": 0, "l": 0, "c": 0, "v": 0, "bv": 0, "tx": 0, "btx": 0}]}]
        """
        params = {
            "symbols": self.SYMBOL,
            "interval": interval,
            "from": from_ts or 0,
            "to": int(datetime.now(timezone.utc).timestamp()),
        }
        data = await self._fetch("ohlcv-history", params)

        if not data or not data[0].get("history"):
            self.logger.warning(f"No data returned for candles {interval}")
            return 0

        rows = []
        for point in data[0]["history"]:
            rows.append(
                (
                    datetime.fromtimestamp(point["t"], tz=timezone.utc),
                    self.SYMBOL,
                    interval,
                    point["o"],  # open
                    point["h"],  # high
                    point["l"],  # low
                    point["c"],  # close
                    point.get("v", 0),  # volume
                    point.get("bv", 0),  # buy_volume
                )
            )

        # Upsert (ON CONFLICT DO UPDATE)
        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO reference.coinalyze_candles
                    (time, symbol, interval, open, high, low, close, volume, buy_volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (time, symbol, interval) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    buy_volume = EXCLUDED.buy_volume
            """,
                rows,
            )

        self.logger.info(f"Imported {len(rows)} candles ({interval})")
        return len(rows)

    async def import_liquidations(self, interval: Interval, from_ts: int | None = None) -> int:
        """
        Import liquidation history.
        
        Response: [{"symbol": "...", "history": [{"t": 0, "l": 0, "s": 0}]}]
        - t = timestamp
        - l = long_liquidations_usd
        - s = short_liquidations_usd
        """
        params = {
            "symbols": self.SYMBOL,
            "interval": interval,
            "from": from_ts or 0,
            "to": int(datetime.now(timezone.utc).timestamp()),
        }
        data = await self._fetch("liquidation-history", params)

        if not data or not data[0].get("history"):
            self.logger.warning(f"No data returned for liquidations {interval}")
            return 0

        rows = []
        for point in data[0]["history"]:
            rows.append(
                (
                    datetime.fromtimestamp(point["t"], tz=timezone.utc),
                    self.SYMBOL,
                    interval,
                    point.get("l", 0),  # long_liquidations_usd
                    point.get("s", 0),  # short_liquidations_usd
                )
            )

        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO reference.coinalyze_liquidations
                    (time, symbol, interval, long_liquidations_usd, short_liquidations_usd)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (time, symbol, interval) DO UPDATE SET
                    long_liquidations_usd = EXCLUDED.long_liquidations_usd,
                    short_liquidations_usd = EXCLUDED.short_liquidations_usd
            """,
                rows,
            )

        self.logger.info(f"Imported {len(rows)} liquidation records ({interval})")
        return len(rows)

    async def import_open_interest(self, interval: Interval, from_ts: int | None = None) -> int:
        """
        Import open interest history.
        
        Response: [{"symbol": "...", "history": [{"t": 0, "o": 0, "h": 0, "l": 0, "c": 0}]}]
        - t = timestamp
        - o, h, l, c = OI OHLC (we store all 4)
        """
        params = {
            "symbols": self.SYMBOL,
            "interval": interval,
            "from": from_ts or 0,
            "to": int(datetime.now(timezone.utc).timestamp()),
        }
        data = await self._fetch("open-interest-history", params)

        if not data or not data[0].get("history"):
            self.logger.warning(f"No data returned for open interest {interval}")
            return 0

        rows = []
        for point in data[0]["history"]:
            rows.append(
                (
                    datetime.fromtimestamp(point["t"], tz=timezone.utc),
                    self.SYMBOL,
                    interval,
                    point.get("o"),  # open_interest_open
                    point.get("h"),  # open_interest_high
                    point.get("l"),  # open_interest_low
                    point.get("c"),  # open_interest_close
                )
            )

        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO reference.coinalyze_open_interest
                    (time, symbol, interval, open_interest_open, open_interest_high, 
                     open_interest_low, open_interest_close)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, symbol, interval) DO UPDATE SET
                    open_interest_open = EXCLUDED.open_interest_open,
                    open_interest_high = EXCLUDED.open_interest_high,
                    open_interest_low = EXCLUDED.open_interest_low,
                    open_interest_close = EXCLUDED.open_interest_close
            """,
                rows,
            )

        self.logger.info(f"Imported {len(rows)} OI records ({interval})")
        return len(rows)

    async def import_funding_rate(self, interval: Interval, from_ts: int | None = None) -> int:
        """
        Import funding rate history.
        
        Response: [{"symbol": "...", "history": [{"t": 0, "o": 0, "h": 0, "l": 0, "c": 0}]}]
        - t = timestamp
        - o, h, l, c = funding rate OHLC (we store all 4)
        """
        params = {
            "symbols": self.SYMBOL,
            "interval": interval,
            "from": from_ts or 0,
            "to": int(datetime.now(timezone.utc).timestamp()),
        }
        data = await self._fetch("funding-rate-history", params)

        if not data or not data[0].get("history"):
            self.logger.warning(f"No data returned for funding rate {interval}")
            return 0

        rows = []
        for point in data[0]["history"]:
            rows.append(
                (
                    datetime.fromtimestamp(point["t"], tz=timezone.utc),
                    self.SYMBOL,
                    interval,
                    point.get("o"),  # funding_open
                    point.get("h"),  # funding_high
                    point.get("l"),  # funding_low
                    point.get("c"),  # funding_close
                )
            )

        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO reference.coinalyze_funding
                    (time, symbol, interval, funding_open, funding_high, funding_low, funding_close)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, symbol, interval) DO UPDATE SET
                    funding_open = EXCLUDED.funding_open,
                    funding_high = EXCLUDED.funding_high,
                    funding_low = EXCLUDED.funding_low,
                    funding_close = EXCLUDED.funding_close
            """,
                rows,
            )

        self.logger.info(f"Imported {len(rows)} funding records ({interval})")
        return len(rows)

    async def import_long_short_ratio(self, interval: Interval, from_ts: int | None = None) -> int:
        """
        Import long/short account ratio history.
        
        Response: [{"symbol": "...", "history": [{"t": 0, "r": 0, "l": 0, "s": 0}]}]
        - t = timestamp
        - r = long_short_ratio
        - l = longs percentage
        - s = shorts percentage
        """
        params = {
            "symbols": self.SYMBOL,
            "interval": interval,
            "from": from_ts or 0,
            "to": int(datetime.now(timezone.utc).timestamp()),
        }
        data = await self._fetch("long-short-ratio-history", params)

        if not data or not data[0].get("history"):
            self.logger.warning(f"No data returned for L/S ratio {interval}")
            return 0

        rows = []
        for point in data[0]["history"]:
            rows.append(
                (
                    datetime.fromtimestamp(point["t"], tz=timezone.utc),
                    self.SYMBOL,
                    interval,
                    point.get("r"),  # long_short_ratio
                    point.get("l"),  # longs
                    point.get("s"),  # shorts
                )
            )

        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO reference.coinalyze_long_short_ratio
                    (time, symbol, interval, long_short_ratio, longs, shorts)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (time, symbol, interval) DO UPDATE SET
                    long_short_ratio = EXCLUDED.long_short_ratio,
                    longs = EXCLUDED.longs,
                    shorts = EXCLUDED.shorts
            """,
                rows,
            )

        self.logger.info(f"Imported {len(rows)} L/S ratio records ({interval})")
        return len(rows)

    async def get_last_imported_ts(self, table: str, interval: Interval) -> int | None:
        """
        Returns timestamp (unix seconds) of newest row in given table for daily updates.
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT EXTRACT(EPOCH FROM MAX(time))::bigint AS max_ts
                FROM reference.{table}
                WHERE symbol = $1 AND interval = $2
            """,
                self.SYMBOL,
                interval,
            )
            return row["max_ts"] if row and row["max_ts"] else None

    async def run_initial_import(self) -> dict:
        """
        Run once. Fetches maximum available history for all intervals and data types.
        """
        self.logger.info("Starting initial Coinalyze import...")
        stats = {}
        
        for interval in self.INTERVALS:
            self.logger.info(f"Importing {interval}...")
            stats[f"candles_{interval}"] = await self.import_candles(interval)
            stats[f"liquidations_{interval}"] = await self.import_liquidations(interval)
            stats[f"open_interest_{interval}"] = await self.import_open_interest(interval)
            stats[f"funding_{interval}"] = await self.import_funding_rate(interval)
            stats[f"long_short_ratio_{interval}"] = await self.import_long_short_ratio(interval)
        
        total = sum(stats.values())
        self.logger.info(f"Initial import complete. Total rows: {total}")
        return stats

    async def run_incremental_update(self) -> dict:
        """
        Run daily. Fetches only new data since last imported timestamp per table/interval.
        """
        self.logger.info("Starting incremental Coinalyze update...")
        stats = {}

        for interval in self.INTERVALS:
            # Candles
            last_ts = await self.get_last_imported_ts("coinalyze_candles", interval)
            stats[f"candles_{interval}"] = await self.import_candles(interval, from_ts=last_ts)

            # Liquidations
            last_ts = await self.get_last_imported_ts("coinalyze_liquidations", interval)
            stats[f"liquidations_{interval}"] = await self.import_liquidations(interval, from_ts=last_ts)

            # Open Interest
            last_ts = await self.get_last_imported_ts("coinalyze_open_interest", interval)
            stats[f"open_interest_{interval}"] = await self.import_open_interest(interval, from_ts=last_ts)

            # Funding
            last_ts = await self.get_last_imported_ts("coinalyze_funding", interval)
            stats[f"funding_{interval}"] = await self.import_funding_rate(interval, from_ts=last_ts)

            # L/S Ratio
            last_ts = await self.get_last_imported_ts("coinalyze_long_short_ratio", interval)
            stats[f"long_short_ratio_{interval}"] = await self.import_long_short_ratio(interval, from_ts=last_ts)

        total = sum(stats.values())
        self.logger.info(f"Incremental update complete. New rows: {total}")
        return stats
