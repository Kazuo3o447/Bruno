#!/usr/bin/env python3
"""
Test News Ingestion Integration
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_integration():
    print('Testing News Ingestion Integration...')
    print('=' * 50)
    
    try:
        # Import services
        from app.services.news_ingestion import news_ingestion_service
        from app.core.redis_client import RedisClient
        
        # Redis Client
        redis = RedisClient()
        await redis.connect()
        
        # Set Redis client in news ingestion
        news_ingestion_service.set_redis_client(redis)
        
        # Test Tier-3 client
        from app.services.news_providers.free_crypto_news import free_crypto_news_client
        
        news = await free_crypto_news_client.fetch_news()
        print(f'✅ Tier-3 Client: {len(news)} items')
        
        # Simulate processing
        if news:
            sample = news[0]
            processed = await news_ingestion_service.process_news_item(
                title=sample['title'],
                content=sample['text'],
                timestamp=sample['timestamp'],
                url=sample.get('url'),
                metadata=sample.get('metadata', {})
            )
            
            if processed:
                print(f'✅ Processed: {processed["title"][:30]}...')
                print(f'   Sentiment: {processed["sentiment"]} ({processed["sentiment_score"]:.3f})')
            else:
                print('⚠️ Processing returned None')
        
        # Check Redis storage
        stored_items = await redis.get_cache('bruno:news:processed_items') or []
        print(f'✅ Redis Storage: {len(stored_items)} items stored')
        
        await redis.disconnect()
        print('🎉 Integration test completed')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integration())
