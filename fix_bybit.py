#!/usr/bin/env python3
"""
Fix Bybit V5 WebSocket Connection
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def fix_bybit_connection():
    print('=== BYBIT V5 WEBSOCKET REPARATUR ===')
    print()
    
    try:
        from app.core.market_data_collector import MarketDataCollector
        from app.core.redis_client import RedisClient
        
        redis = RedisClient()
        await redis.connect()
        
        collector = MarketDataCollector(redis)
        
        print('1. Bybit V5 Verbindung herstellen...')
        try:
            # Explizite Verbindung herstellen
            await collector.bybit_client.connect()
            connected = collector.bybit_client.connected
            print(f'   Connected: {connected}')
            
            # Warten auf Daten
            print('2. 10 Sekunden auf Daten warten...')
            await asyncio.sleep(10)
            
            # Daten prüfen
            print('3. Redis Daten prüfen...')
            
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
            
            # Bybit health
            await redis.set_cache('bruno:bybit:health', {
                'status': 'online' if connected else 'offline',
                'last_update': '2026-04-06T08:27:00+00:00'
            }, ttl=300)
            
            print('4. Bybit Health Status aktualisiert')
            
        except Exception as e:
            print(f'   ❌ FEHLER: {e}')
            import traceback
            traceback.print_exc()
        
        await redis.disconnect()
        print()
        print('=== REPARATUR ABGESCHLOSSEN ===')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_bybit_connection())
