import asyncio
from app.core.log_manager import LogManager, LogLevel, LogCategory

async def test_log_manager():
    log_manager = LogManager()
    await log_manager.initialize()
    
    # Test log entry
    await log_manager.add_log(
        level=LogLevel.INFO,
        category=LogCategory.SYSTEM,
        source='manual_test',
        message='Test log from LogManager',
        details={'test': True}
    )
    
    print('Log sent via LogManager')
    
    # Check recent logs
    logs = await log_manager.get_recent_logs(limit=5)
    print(f'Recent logs count: {len(logs)}')
    for log in logs:
        print(f'  - {log["level"]} {log["source"]}: {log["message"]}')

if __name__ == "__main__":
    asyncio.run(test_log_manager())
