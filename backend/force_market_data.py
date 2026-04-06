#!/usr/bin/env python3
"""
Force Market Data Collection Test
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def force_market_data():
    print('=== ERZWINGE MARKT DATEN SAMMLUNG ===')
    print()
    
    try:
        from app.core.market_data_collector import MarketDataCollector
        from app.core.redis_client import RedisClient
        
        redis = RedisClient()
        await redis.connect()
        
        collector = MarketDataCollector(redis)
        
        print('1. Bybit V5 Daten sammeln...')
        try:
            await collector.collect_all_data('BTCUSDT')
            print('   ✅ ERFOLG')
        except Exception as e:
            print(f'   ❌ FEHLER: {e}')
        
        print()
        print('2. Redis Check nach Sammlung:')
        
        # Ticker
        ticker = await redis.get_cache('market:ticker:BTCUSDT') or {}
        if ticker:
            price = ticker.get('last_price', 'N/A')
            print(f'   Ticker: {price} USDT')
        else:
            print('   Ticker: ❌')
        
        # Orderbook
        ob = await redis.get_cache('market:orderbook:BTCUSDT') or {}
        if ob:
            bid = ob.get('best_bid', 'N/A')
            ask = ob.get('best_ask', 'N/A')
            print(f'   Orderbook: {bid}/{ask}')
        else:
            print('   Orderbook: ❌')
        
        # CVD
        cvd = await redis.get_cache('market:cvd:BTCUSDT') or {}
        if cvd:
            delta = cvd.get('cumulative_delta', 'N/A')
            print(f'   CVD: {delta}')
        else:
            print('   CVD: ❌')
        
        await redis.disconnect()
        print()
        print('=== TEST ABGESCHLOSSEN ===')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(force_market_data())
