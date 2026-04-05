import asyncio
from app.core.redis_client import RedisClient

async def test_log_pubsub():
    redis = RedisClient()
    await redis.connect()
    
    # Test publish to logs:live
    test_msg = '{"test": "message"}'
    await redis.redis.publish('logs:live', test_msg)
    print('Published test message to logs:live')
    
    # Check if log_manager is working
    logs = await redis.get_cache('bruno:logs:recent')
    print('Recent logs available:', logs is not None)
    if logs:
        print('Log count:', len(logs))
    
    await redis.disconnect()

if __name__ == "__main__":
    asyncio.run(test_log_pubsub())
