#!/usr/bin/env python3
import asyncio
import websockets
import json

async def test_binance_ws():
    print("Test Binance WS connectivity...")
    try:
        async with websockets.connect(
            'wss://fstream.binance.com/ws/btcusdt@kline_1m',
            ping_interval=20,
            ping_timeout=20
        ) as ws:
            print("Connected successfully")
            await asyncio.sleep(5)
            print("Still connected after 5s")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_binance_ws())
