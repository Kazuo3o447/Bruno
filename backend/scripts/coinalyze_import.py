"""
Manual Coinalyze import runner.

Usage:
    python backend/scripts/coinalyze_import.py --initial    # first-time full import
    python backend/scripts/coinalyze_import.py --update     # incremental daily update
    python backend/scripts/coinalyze_import.py --stats      # show row counts per table
"""

import argparse
import asyncio
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from app.services.coinalyze_importer import CoinalyzeImporter


async def main():
    parser = argparse.ArgumentParser(description="Coinalyze Reference Data Import")
    parser.add_argument("--initial", action="store_true", help="First-time full import")
    parser.add_argument("--update", action="store_true", help="Incremental daily update")
    parser.add_argument("--stats", action="store_true", help="Show row counts per table")
    parser.add_argument("--interval", type=str, default=None, help="Import only specific interval (15min, 1hour, 4hour, daily)")
    args = parser.parse_args()

    # Check for API key
    if not os.environ.get("COINALYZE_API_KEY"):
        print("ERROR: COINALYZE_API_KEY environment variable not set")
        print("Get your free API key at: https://coinalyze.net/account/api-access/")
        sys.exit(1)

    # Get database URL
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Construct from individual env vars
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5432")
        db_user = os.environ.get("DB_USER", "bruno")
        db_pass = os.environ.get("DB_PASS", "bruno_secret")
        db_name = os.environ.get("DB_NAME", "bruno_trading")
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    print(f"Connecting to database...")
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
    
    try:
        importer = CoinalyzeImporter(pool)

        if args.stats:
            print("\n=== Coinalyze Reference Data Statistics ===\n")
            async with pool.acquire() as conn:
                for table in [
                    "coinalyze_candles",
                    "coinalyze_liquidations",
                    "coinalyze_open_interest",
                    "coinalyze_funding",
                    "coinalyze_long_short_ratio",
                ]:
                    row = await conn.fetchrow(
                        f"""
                        SELECT 
                            COUNT(*) as cnt,
                            MIN(time) as oldest,
                            MAX(time) as newest,
                            COUNT(DISTINCT interval) as intervals
                        FROM reference.{table}
                    """
                    )
                    print(f"{table}:")
                    print(f"  Rows: {row['cnt']:,}")
                    print(f"  Range: {row['oldest']} → {row['newest']}")
                    print(f"  Intervals: {row['intervals']}")
                    print()

        elif args.initial:
            if args.interval:
                print(f"\n=== Running INITIAL import for {args.interval} only ===\n")
                # Override INTERVALS temporarily
                original_intervals = importer.INTERVALS
                importer.INTERVALS = [args.interval]
                stats = await importer.run_initial_import()
                importer.INTERVALS = original_intervals
            else:
                print("\n=== Running INITIAL import (all intervals) ===\n")
                print("This may take a while...")
                stats = await importer.run_initial_import()
            
            total = sum(stats.values())
            print(f"\n=== Import Complete ===")
            print(f"Total rows imported: {total:,}")
            for key, count in sorted(stats.items()):
                print(f"  {key}: {count:,}")

        elif args.update:
            if args.interval:
                print(f"\n=== Running INCREMENTAL update for {args.interval} only ===\n")
                # Run specific interval update
                stats = {}
                
                last_ts = await importer.get_last_imported_ts("coinalyze_candles", args.interval)
                stats[f"candles_{args.interval}"] = await importer.import_candles(args.interval, from_ts=last_ts)

                last_ts = await importer.get_last_imported_ts("coinalyze_liquidations", args.interval)
                stats[f"liquidations_{args.interval}"] = await importer.import_liquidations(args.interval, from_ts=last_ts)

                last_ts = await importer.get_last_imported_ts("coinalyze_open_interest", args.interval)
                stats[f"open_interest_{args.interval}"] = await importer.import_open_interest(args.interval, from_ts=last_ts)

                last_ts = await importer.get_last_imported_ts("coinalyze_funding", args.interval)
                stats[f"funding_{args.interval}"] = await importer.import_funding_rate(args.interval, from_ts=last_ts)

                last_ts = await importer.get_last_imported_ts("coinalyze_long_short_ratio", args.interval)
                stats[f"long_short_ratio_{args.interval}"] = await importer.import_long_short_ratio(args.interval, from_ts=last_ts)
            else:
                print("\n=== Running INCREMENTAL update (all intervals) ===\n")
                stats = await importer.run_incremental_update()
            
            total = sum(stats.values())
            print(f"\n=== Update Complete ===")
            print(f"Total new rows: {total:,}")
            for key, count in sorted(stats.items()):
                if count > 0:
                    print(f"  {key}: +{count:,}")

        else:
            parser.print_help()
            print("\nUse --initial for first-time import, --update for daily updates, --stats to check data")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
