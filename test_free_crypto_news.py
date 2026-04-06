#!/usr/bin/env python3
"""
Quick test for FreeCryptoNewsClient integration
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.news_providers.free_crypto_news import free_crypto_news_client

async def test_client():
    print('Testing FreeCryptoNewsClient...')
    print('=' * 50)
    
    try:
        # Test general news endpoint
        print("Testing general news endpoint...")
        news = await free_crypto_news_client.fetch_news()
        print(f'✅ General: {len(news)} items fetched')
        
        if news:
            sample = news[0]
            print(f'📰 Sample title: {sample.get("title", "N/A")}')
            print(f'📝 Sample text: {sample.get("text", "N/A")[:100]}...')
            print(f'🕐 Timestamp: {sample.get("timestamp", "N/A")}')
        
        print()
        
        # Test Bitcoin-specific endpoint
        print("Testing Bitcoin endpoint...")
        bitcoin_news = await free_crypto_news_client.fetch_bitcoin_news()
        print(f'✅ Bitcoin: {len(bitcoin_news)} items fetched')
        
        if bitcoin_news:
            sample = bitcoin_news[0]
            print(f'📰 Sample title: {sample.get("title", "N/A")}')
            print(f'📝 Sample text: {sample.get("text", "N/A")[:100]}...')
        
        print()
        print('🎉 All tests completed successfully')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    
    finally:
        await free_crypto_news_client.shutdown()
        print('🔚 Client shutdown complete')

if __name__ == "__main__":
    asyncio.run(test_client())
