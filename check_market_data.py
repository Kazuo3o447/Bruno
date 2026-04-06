#!/usr/bin/env python3
"""
Market Data Task Status Check
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def check_market_data_task():
    print('=== MARKET DATA TASK STATUS ===')
    print()
    
    try:
        from app.core.redis_client import RedisClient
        
        redis = RedisClient()
        await redis.connect()
        
        # Check if data is being collected
        print('1. Aktuelle Marktdaten:')
        
        # Ticker
        ticker = await redis.get_cache('market:ticker:BTCUSDT') or {}
        if ticker:
            price = ticker.get('last_price', 'N/A')
            timestamp = ticker.get('timestamp', 'N/A')
            print(f'   Ticker: {price} USDT')
            print(f'   Timestamp: {timestamp}')
        else:
            print('   Ticker: ❌ KEINE DATEN')
        
        # Orderbook
        ob = await redis.get_cache('market:orderbook:BTCUSDT') or {}
        if ob:
            bid = ob.get('best_bid', 'N/A')
            ask = ob.get('best_ask', 'N/A')
            timestamp = ob.get('timestamp', 'N/A')
            print(f'   Orderbook: {bid}/{ask}')
            print(f'   OB Timestamp: {timestamp}')
        else:
            print('   Orderbook: ❌ KEINE DATEN')
        
        # CVD
        cvd = await redis.get_cache('market:cvd:BTCUSDT') or {}
        if cvd:
            delta = cvd.get('cumulative_delta', 'N/A')
            timestamp = cvd.get('timestamp', 'N/A')
            print(f'   CVD Delta: {delta}')
            print(f'   CVD Timestamp: {timestamp}')
        else:
            print('   CVD: ❌ KEINE DATEN')
        
        # Check task status
        print()
        print('2. Task Status:')
        task_status = await redis.get_cache('bruno:market_data:task_status') or {}
        if task_status:
            last_run = task_status.get('last_run', 'N/A')
            status = task_status.get('status', 'N/A')
            error_count = task_status.get('error_count', 0)
            print(f'   Last Run: {last_run}')
            print(f'   Status: {status}')
            print(f'   Error Count: {error_count}')
        else:
            print('   Kein Task Status gefunden')
        
        # Check Bybit health
        print()
        print('3. Bybit V5 Health:')
        bybit_health = await redis.get_cache('bruno:bybit:health') or {}
        if bybit_health:
            health_status = bybit_health.get('status', 'unknown')
            last_update = bybit_health.get('last_update', 'N/A')
            print(f'   Status: {health_status}')
            print(f'   Last Update: {last_update}')
        else:
            print('   Kein Health Status gefunden')
        
        await redis.disconnect()
        print()
        print('=== CHECK ABGESCHLOSSEN ===')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_market_data_task())
