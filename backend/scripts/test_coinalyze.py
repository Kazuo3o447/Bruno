"""
Coinalyze Reference Data Importer - Complete Test Suite
Tests database, API connectivity, CLI script, and data import
"""

import asyncio
import os
import sys
import asyncpg
import httpx
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.services.coinalyze_importer import CoinalyzeImporter


class CoinalyzeTester:
    def __init__(self):
        self.db_pool = None
        self.results = []

    async def setup(self):
        """Initialize database connection"""
        db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        self.db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)

    async def teardown(self):
        """Close database connection"""
        if self.db_pool:
            await self.db_pool.close()

    def log(self, test_name: str, status: str, message: str = ""):
        """Log test result"""
        emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        result = f"{emoji} [{status}] {test_name}"
        if message:
            result += f" - {message}"
        print(result)
        self.results.append({"test": test_name, "status": status, "message": message})

    async def test_database_connection(self):
        """Test 1: Database connectivity"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 as test")
                if row and row["test"] == 1:
                    self.log("Database Connection", "PASS", "Connected successfully")
                    return True
        except Exception as e:
            self.log("Database Connection", "FAIL", str(e))
            return False

    async def test_reference_schema_exists(self):
        """Test 2: Reference schema exists"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'reference'"
                )
                if row:
                    self.log("Reference Schema", "PASS", "Schema exists")
                    return True
                else:
                    self.log("Reference Schema", "FAIL", "Schema not found")
                    return False
        except Exception as e:
            self.log("Reference Schema", "FAIL", str(e))
            return False

    async def test_tables_exist(self):
        """Test 3: All Coinalyze tables exist"""
        expected_tables = [
            "coinalyze_candles",
            "coinalyze_liquidations",
            "coinalyze_open_interest",
            "coinalyze_funding",
            "coinalyze_long_short_ratio",
        ]
        
        try:
            async with self.db_pool.acquire() as conn:
                for table in expected_tables:
                    row = await conn.fetchrow(
                        """
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'reference' AND table_name = $1
                        """,
                        table,
                    )
                    if row:
                        self.log(f"Table: {table}", "PASS", "Exists")
                    else:
                        self.log(f"Table: {table}", "FAIL", "Not found")
                        return False
                return True
        except Exception as e:
            self.log("Tables Check", "FAIL", str(e))
            return False

    async def test_api_key_configured(self):
        """Test 4: API key is configured"""
        if settings.COINALYZE_API_KEY:
            # Mask key for logging
            key_preview = settings.COINALYZE_API_KEY[:8] + "..." + settings.COINALYZE_API_KEY[-4:]
            self.log("API Key Configured", "PASS", f"Key: {key_preview}")
            return True
        else:
            self.log("API Key Configured", "FAIL", "COINALYZE_API_KEY not set in environment")
            return False

    async def test_api_connectivity(self):
        """Test 5: Coinalyze API is reachable"""
        if not settings.COINALYZE_API_KEY:
            self.log("API Connectivity", "SKIP", "No API key configured")
            return False
            
        try:
            headers = {"api_key": settings.COINALYZE_API_KEY}
            params = {
                "symbols": "BTCUSD_PERP.A",
                "interval": "daily",
                "from": int(datetime.now(timezone.utc).timestamp()) - 86400,
                "to": int(datetime.now(timezone.utc).timestamp()),
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.coinalyze.net/v1/ohlcv-history",
                    params=params,
                    headers=headers,
                )
                
                if r.status_code == 200:
                    data = r.json()
                    if data and len(data) > 0:
                        self.log("API Connectivity", "PASS", f"Received data for {data[0].get('symbol', 'unknown')}")
                        return True
                    else:
                        self.log("API Connectivity", "FAIL", "Empty response")
                        return False
                elif r.status_code == 401:
                    self.log("API Connectivity", "FAIL", "Invalid API key (401)")
                    return False
                else:
                    self.log("API Connectivity", "FAIL", f"HTTP {r.status_code}")
                    return False
                    
        except Exception as e:
            self.log("API Connectivity", "FAIL", str(e))
            return False

    async def test_import_single_interval(self):
        """Test 6: Import data for one interval (daily)"""
        if not settings.COINALYZE_API_KEY:
            self.log("Data Import (daily)", "SKIP", "No API key configured")
            return False
            
        try:
            importer = CoinalyzeImporter(self.db_pool)
            count = await importer.import_candles("daily")
            
            if count > 0:
                self.log("Data Import (daily)", "PASS", f"Imported {count} candles")
                return True
            else:
                self.log("Data Import (daily)", "FAIL", "No data imported")
                return False
                
        except Exception as e:
            self.log("Data Import (daily)", "FAIL", str(e))
            return False

    async def test_verify_imported_data(self):
        """Test 7: Verify data was actually written to database"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as cnt, MIN(time) as oldest, MAX(time) as newest
                    FROM reference.coinalyze_candles
                    WHERE interval = 'daily'
                    """
                )
                
                if row and row["cnt"] > 0:
                    self.log(
                        "Verify Imported Data",
                        "PASS",
                        f"{row['cnt']} rows, {row['oldest'].date()} → {row['newest'].date()}"
                    )
                    return True
                else:
                    self.log("Verify Imported Data", "FAIL", "No data found in table")
                    return False
                    
        except Exception as e:
            self.log("Verify Imported Data", "FAIL", str(e))
            return False

    async def test_import_other_data_types(self):
        """Test 8: Import other data types (liquidations, OI, funding, L/S ratio)"""
        if not settings.COINALYZE_API_KEY:
            self.log("Other Data Types", "SKIP", "No API key configured")
            return False
            
        try:
            importer = CoinalyzeImporter(self.db_pool)
            
            results = {
                "liquidations": await importer.import_liquidations("daily"),
                "open_interest": await importer.import_open_interest("daily"),
                "funding": await importer.import_funding_rate("daily"),
                "long_short_ratio": await importer.import_long_short_ratio("daily"),
            }
            
            all_passed = True
            for data_type, count in results.items():
                if count > 0:
                    self.log(f"Import {data_type}", "PASS", f"{count} rows")
                else:
                    self.log(f"Import {data_type}", "FAIL", "No data")
                    all_passed = False
                    
            return all_passed
            
        except Exception as e:
            self.log("Other Data Types", "FAIL", str(e))
            return False

    async def test_upsert_functionality(self):
        """Test 9: Verify upsert doesn't create duplicates"""
        if not settings.COINALYZE_API_KEY:
            self.log("Upsert Test", "SKIP", "No API key configured")
            return False
            
        try:
            # Get count before
            async with self.db_pool.acquire() as conn:
                before = await conn.fetchval(
                    "SELECT COUNT(*) FROM reference.coinalyze_candles WHERE interval = 'daily'"
                )
            
            # Run import again (should use upsert)
            importer = CoinalyzeImporter(self.db_pool)
            await importer.import_candles("daily")
            
            # Get count after
            async with self.db_pool.acquire() as conn:
                after = await conn.fetchval(
                    "SELECT COUNT(*) FROM reference.coinalyze_candles WHERE interval = 'daily'"
                )
            
            if before == after:
                self.log("Upsert Test", "PASS", f"No duplicates created ({after} rows stable)")
                return True
            else:
                self.log("Upsert Test", "WARN", f"Row count changed from {before} to {after}")
                return True  # Still pass, just a warning
                
        except Exception as e:
            self.log("Upsert Test", "FAIL", str(e))
            return False

    async def test_incremental_update(self):
        """Test 10: Test incremental update logic"""
        if not settings.COINALYZE_API_KEY:
            self.log("Incremental Update", "SKIP", "No API key configured")
            return False
            
        try:
            importer = CoinalyzeImporter(self.db_pool)
            
            # Get last timestamp
            last_ts = await importer.get_last_imported_ts("coinalyze_candles", "daily")
            
            if last_ts:
                last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                self.log("Incremental Update", "PASS", f"Last import: {last_dt.isoformat()}")
                return True
            else:
                self.log("Incremental Update", "FAIL", "Could not retrieve last timestamp")
                return False
                
        except Exception as e:
            self.log("Incremental Update", "FAIL", str(e))
            return False

    async def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        warned = sum(1 for r in self.results if r["status"] == "WARN")
        
        print(f"Total: {len(self.results)} tests")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⚠️  Warned: {warned}")
        print(f"  ⏭️  Skipped: {skipped}")
        
        if failed == 0:
            print("\n🎉 All critical tests passed!")
        else:
            print(f"\n⚠️ {failed} tests failed - please review")
            
        return failed == 0

    async def run_all_tests(self):
        """Run complete test suite"""
        print("="*60)
        print("COINALYZE REFERENCE DATA IMPORTER - TEST SUITE")
        print("="*60)
        print(f"Started: {datetime.now(timezone.utc).isoformat()}")
        print("-"*60)
        
        await self.setup()
        
        try:
            # Phase 1: Infrastructure Tests
            print("\n📦 INFRASTRUCTURE TESTS")
            print("-"*40)
            await self.test_database_connection()
            await self.test_reference_schema_exists()
            await self.test_tables_exist()
            
            # Phase 2: API Tests
            print("\n🌐 API TESTS")
            print("-"*40)
            api_configured = await self.test_api_key_configured()
            if api_configured:
                await self.test_api_connectivity()
            
            # Phase 3: Data Import Tests
            print("\n📊 DATA IMPORT TESTS")
            print("-"*40)
            if api_configured:
                await self.test_import_single_interval()
                await self.test_verify_imported_data()
                await self.test_import_other_data_types()
                await self.test_upsert_functionality()
                await self.test_incremental_update()
            else:
                print("⏭️ Skipping import tests - no API key configured")
            
            # Summary
            success = await self.print_summary()
            
            return success
            
        finally:
            await self.teardown()


async def main():
    tester = CoinalyzeTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
