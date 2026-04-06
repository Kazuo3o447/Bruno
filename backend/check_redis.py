#!/usr/bin/env python3
"""
Check Redis Integration
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def check_redis():
    print('Checking Redis Integration...')
    print('=' * 50)
    
    try:
        from app.core.redis_client import RedisClient
        
        redis = RedisClient()
        await redis.connect()
        
        # Check processed news items
        items = await redis.get_cache('bruno:news:processed_items') or []
        print(f'Processed news items in Redis: {len(items)}')
        
        if items:
            for i, item in enumerate(items[-3:]):  # Last 3 items
                title = item.get("title", "N/A")
                sentiment = item.get("sentiment", "unknown")
                score = item.get("sentiment_score", 0)
                source = item.get("source", "unknown")
                print(f'  {i+1}. {title[:40]}... -> {sentiment} ({score:.3f}) [{source}]')
        
        # Check sentiment aggregate
        sentiment = await redis.get_cache('bruno:sentiment:aggregate') or {}
        avg_score = sentiment.get('average_score', 0)
        samples = sentiment.get('samples_analyzed', 0)
        headlines = sentiment.get('headlines_collected', 0)
        
        print(f'Sentiment aggregate: {avg_score:.3f} from {samples} samples, {headlines} headlines')
        
        await redis.disconnect()
        print('🎉 Redis check completed')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_redis())
