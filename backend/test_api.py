from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import asyncio
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bruno Test API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3003", "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store WebSocket connections
active_connections = []

@app.websocket("/ws/market/{symbol}")
async def websocket_market(websocket: WebSocket, symbol: str):
    logger.info(f"New WebSocket connection attempt for /ws/market/{symbol}")
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Market WebSocket client connected for {symbol}. Total connections: {len(active_connections)}")
    
    try:
        message_count = 1
        while True:
            # Send mock ticker data every 2 seconds
            ticker_data = {
                "type": "ticker",
                "data": {
                    "symbol": symbol,
                    "last_price": 65000 + random.uniform(-1000, 1000),
                    "price_change_percent": random.uniform(-5, 5),
                    "open_price": 65000,
                    "high_price": 65500,
                    "low_price": 64500,
                    "volume": random.uniform(100, 1000)
                }
            }
            
            message = json.dumps(ticker_data)
            await websocket.send_text(message)
            logger.info(f"Sent ticker data for {symbol} #{message_count}: {len(message)} bytes")
            message_count += 1
            
            await asyncio.sleep(2)
    except WebSocketDisconnect as e:
        logger.info(f"Market WebSocket client disconnected for {symbol}: {e.code}")
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"Error in market WebSocket: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket):
    logger.info("New WebSocket connection attempt for /ws/agents")
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Agent WebSocket client connected. Total connections: {len(active_connections)}")
    
    try:
        # Send initial status immediately
        agents_data = {
            "type": "agents_status",
            "data": {
                "agents": {
                    "sentiment": {
                        "id": "sentiment",
                        "name": "Sentiment Analysis Agent",
                        "status": "running",
                        "last_heartbeat": datetime.now().isoformat(),
                        "healthy": True,
                        "age_seconds": 1
                    },
                    "market": {
                        "id": "market",
                        "name": "Market Data Agent",
                        "status": "running",
                        "last_heartbeat": datetime.now().isoformat(),
                        "healthy": True,
                        "age_seconds": 1
                    },
                    "quant": {
                        "id": "quant",
                        "name": "Quant Agent",
                        "status": "running",
                        "last_heartbeat": datetime.now().isoformat(),
                        "healthy": True,
                        "age_seconds": 1
                    },
                    "risk": {
                        "id": "risk",
                        "name": "Risk Agent",
                        "status": "running",
                        "last_heartbeat": datetime.now().isoformat(),
                        "healthy": True,
                        "age_seconds": 1
                    },
                    "execution": {
                        "id": "execution",
                        "name": "Execution Agent",
                        "status": "running",
                        "last_heartbeat": datetime.now().isoformat(),
                        "healthy": True,
                        "age_seconds": 1
                    }
                }
            }
        }
        
        message = json.dumps(agents_data)
        await websocket.send_text(message)
        logger.info(f"Sent initial agent status: {len(message)} bytes")
        
        # Send periodic updates
        message_count = 1
        while True:
            await asyncio.sleep(3)  # Send every 3 seconds
            
            # Update heartbeat times
            current_time = datetime.now().isoformat()
            updated_agents = {
                "type": "agents_status",
                "data": {
                    "agents": {
                        "sentiment": {
                            "id": "sentiment",
                            "name": "Sentiment Analysis Agent",
                            "status": "running",
                            "last_heartbeat": current_time,
                            "healthy": True,
                            "age_seconds": message_count * 3
                        },
                        "market": {
                            "id": "market",
                            "name": "Market Data Agent",
                            "status": "running",
                            "last_heartbeat": current_time,
                            "healthy": True,
                            "age_seconds": message_count * 3
                        },
                        "quant": {
                            "id": "quant",
                            "name": "Quant Agent",
                            "status": "running",
                            "last_heartbeat": current_time,
                            "healthy": True,
                            "age_seconds": message_count * 3
                        },
                        "risk": {
                            "id": "risk",
                            "name": "Risk Agent",
                            "status": "running",
                            "last_heartbeat": current_time,
                            "healthy": True,
                            "age_seconds": message_count * 3
                        },
                        "execution": {
                            "id": "execution",
                            "name": "Execution Agent",
                            "status": "running",
                            "last_heartbeat": current_time,
                            "healthy": True,
                            "age_seconds": message_count * 3
                        }
                    }
                }
            }
            
            message = json.dumps(updated_agents)
            await websocket.send_text(message)
            logger.info(f"Sent periodic update #{message_count}: {len(message)} bytes")
            message_count += 1
            
    except WebSocketDisconnect as e:
        logger.info(f"Agent WebSocket client disconnected: {e.code}")
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"Error in agent WebSocket: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.websocket("/api/v1/logs/ws")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial log history
        history_data = {
            "type": "history",
            "logs": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "category": "SYSTEM",
                    "source": "API",
                    "message": "Bruno Test API gestartet"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO", 
                    "category": "AGENT",
                    "source": "SENTIMENT",
                    "message": "Sentiment Analysis Agent initialized"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "WARNING",
                    "category": "TRADING",
                    "source": "MARKET",
                    "message": "Market data feed connected"
                }
            ]
        }
        await websocket.send_text(json.dumps(history_data))
        print(f"Sent log history to WebSocket client")
        
        # Send new logs periodically
        log_counter = 1
        while True:
            await asyncio.sleep(8)  # Send every 8 seconds
            
            new_log = {
                "type": "new_log",
                "log": {
                    "timestamp": datetime.now().isoformat(),
                    "level": random.choice(["INFO", "WARNING", "ERROR"]),
                    "category": random.choice(["SYSTEM", "AGENT", "TRADING", "API"]),
                    "source": random.choice(["API", "SENTIMENT", "MARKET", "DATABASE"]),
                    "message": f"Mock Log Entry #{log_counter}: {random.choice(['Connection established', 'Data processed', 'Heartbeat received', 'Cache updated', 'Task completed'])}"
                }
            }
            await websocket.send_text(json.dumps(new_log))
            print(f"Sent new log #{log_counter} to WebSocket client")
            log_counter += 1
            
    except WebSocketDisconnect:
        print("Log WebSocket client disconnected")
        active_connections.remove(websocket)
    except Exception as e:
        print(f"Error in log WebSocket: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "database": "connected",
        "redis": "connected",
        "ollama": "connected"
    }

@app.get("/api/v1/agents/status")
async def agents_status():
    return {
        "agents": {
            "sentiment": {
                "id": "sentiment",
                "name": "Sentiment Analysis Agent",
                "status": "running",
                "last_heartbeat": datetime.now().isoformat(),
                "healthy": True,
                "age_seconds": 5
            },
            "market": {
                "id": "market",
                "name": "Market Data Agent", 
                "status": "running",
                "last_heartbeat": datetime.now().isoformat(),
                "healthy": True,
                "age_seconds": 3
            },
            "trading": {
                "id": "trading",
                "name": "Trading Agent",
                "status": "idle",
                "last_heartbeat": datetime.now().isoformat(),
                "healthy": True,
                "age_seconds": 10
            }
        }
    }

@app.get("/api/v1/telemetry/live")
async def telemetry():
    return {
        "agents": {
            "sentiment": {
                "status": "running",
                "last_heartbeat": datetime.now().isoformat(),
                "healthy": True
            },
            "market": {
                "status": "running", 
                "last_heartbeat": datetime.now().isoformat(),
                "healthy": True
            }
        },
        "live_trading_approved": random.choice([True, False]),
        "system_load": random.uniform(0.1, 0.8),
        "memory_usage": random.uniform(0.2, 0.7)
    }

@app.get("/api/v1/positions/open")
async def positions():
    return {
        "positions": [
            {
                "id": "pos_1",
                "symbol": "BTCUSDT",
                "side": "long",
                "entry_price": 65000,
                "quantity": 0.1,
                "current_price": 65500,
                "current_pnl_pct": 0.77,
                "current_pnl_eur": 50,
                "stop_loss_price": 64000,
                "take_profit_price": 67000,
                "created_at": (datetime.now() - timedelta(hours=2)).isoformat()
            },
            {
                "id": "pos_2", 
                "symbol": "ETHUSDT",
                "side": "short",
                "entry_price": 3500,
                "quantity": 1.0,
                "current_price": 3450,
                "current_pnl_pct": 1.43,
                "current_pnl_eur": 50,
                "stop_loss_price": 3550,
                "take_profit_price": 3400,
                "created_at": (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]
    }

@app.get("/api/v1/market/klines/{symbol}")
async def market_klines(symbol: str):
    # Generate demo candlestick data
    data = []
    base_time = datetime.now() - timedelta(days=1)
    base_price = 65000 if "BTC" in symbol else 3500
    
    for i in range(100):
        time = base_time + timedelta(minutes=i*15)
        price = base_price + random.uniform(-500, 500)
        
        data.append({
            "time": int(time.timestamp()),
            "open": price,
            "high": price * (1 + random.uniform(0, 0.02)),
            "low": price * (1 - random.uniform(0, 0.02)),
            "close": price * (1 + random.uniform(-0.01, 0.01))
        })
    
    return data

@app.get("/api/v1/systemtest/news_health")
async def news_health():
    return {
        "feeds": {
            "coindesk": {"status": "healthy", "last_update": datetime.now().isoformat()},
            "cointelegraph": {"status": "healthy", "last_update": datetime.now().isoformat()},
            "reddit_crypto": {"status": "healthy", "last_update": datetime.now().isoformat()}
        }
    }

@app.post("/api/v1/agents/start/{agent_id}")
async def start_agent(agent_id: str):
    return {"status": "success", "message": f"Agent {agent_id} started"}

@app.post("/api/v1/agents/stop/{agent_id}")
async def stop_agent(agent_id: str):
    return {"status": "success", "message": f"Agent {agent_id} stopped"}

@app.post("/api/v1/agents/restart/{agent_id}")
async def restart_agent(agent_id: str):
    return {"status": "success", "message": f"Agent {agent_id} restarted"}

@app.post("/api/v1/agents/start-all")
async def start_all_agents():
    return {"status": "success", "message": "All agents started"}

@app.post("/api/v1/agents/stop-all")
async def stop_all_agents():
    return {"status": "success", "message": "All agents stopped"}

@app.post("/api/v1/agents/chat/{agent_id}")
async def chat_with_agent(agent_id: str, request: dict):
    user_message = request.get("message", "")
    # Simulate different agent responses
    responses = {
        "sentiment": f"Sentiment Agent: Ich habe deine Nachricht '{user_message}' analysiert. Das aktuelle Marktsentiment ist leicht positiv mit einem Score von 0.65.",
        "market": f"Market Data Agent: Die aktuellen Marktdaten zeigen BTC bei $65,000 mit einem Volumen von $1.2B. Deine Anfrage '{user_message}' wurde verarbeitet.",
        "quant": f"Quant Agent: Basierend auf deiner Nachricht '{user_message}' habe ich die OFI berechnet: aktueller Wert ist +750, was über dem Threshold liegt.",
        "risk": f"Risk Agent: Risikoanalyse für '{user_message}' durchgeführt. Aktuelles Risk Level: MODERATE. Kein Veto notwendig.",
        "execution": f"Execution Agent: Deine Anfrage '{user_message}' wurde erhalten. Keine Trades auszuführen. System im DRY_RUN Modus."
    }
    return {"response": responses.get(agent_id, f"{agent_id} Agent: Nachricht erhalten.")}

@app.get("/api/v1/market/grss-full")
async def grss_full():
    return {
        "macro": {
            "ndx_status": random.choice(["BULLISH", "BEARISH"]),
            "vix": random.uniform(15, 35),
            "yields_10y": random.uniform(3.5, 4.5),
            "m2_yoy_pct": random.uniform(-2, 5)
        },
        "derivatives": {
            "funding_rate": random.uniform(-0.01, 0.01),
            "put_call_ratio": random.uniform(0.3, 1.2),
            "dvol": random.uniform(80, 120),
            "oi_delta_pct": random.uniform(-5, 5)
        },
        "sentiment": {
            "fear_greed": random.choice(["EXTREME FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME GREED"]),
            "llm_news_sentiment": random.uniform(-0.5, 0.5),
            "stablecoin_delta_bn": random.uniform(-10, 10)
        },
        "data_quality": {
            "last_update": datetime.now().isoformat(),
            "news_silence_seconds": random.randint(100, 3600),
            "fresh_source_count": random.randint(3, 5),
            "funding_settlement_window": random.choice([True, False])
        },
        "score": random.uniform(20, 60),
        "score_raw": random.uniform(15, 65),
        "velocity_30min": random.uniform(-10, 10),
        "veto_active": random.choice([True, False]),
        "reason": "High volatility detected" if random.random() > 0.8 else None
    }

@app.get("/api/v1/llm-cascade/status")
async def llm_cascade_status():
    return {
        "ollama_available": True,
        "model_layer1": "qwen2.5:14b",
        "model_layer2": "deepseek-r1:14b",
        "recent_decisions": [
            {
                "timestamp": datetime.now().isoformat(),
                "decision": random.choice(["BUY", "SELL", "HOLD"]),
                "regime": random.choice(["BULLISH", "BEARISH", "SIDEWAYS"]),
                "ofi_met": random.random() > 0.5
            }
            for _ in range(5)
        ]
    }

@app.get("/api/v1/decisions/feed")
async def decisions_feed():
    return {
        "stats": {
            "ofi_below_threshold": random.randint(20, 40),
            "cascade_hold": random.randint(5, 15),
            "signals_generated": random.randint(2, 8)
        },
        "events": [
            {
                "timestamp": datetime.now().isoformat(),
                "decision": random.choice(["BUY", "SELL", "HOLD"]),
                "regime": random.choice(["BULLISH", "BEARISH", "SIDEWAYS"]),
                "ofi_met": random.random() > 0.5
            }
            for _ in range(10)
        ]
    }

@app.get("/api/v1/decisions/veto-history")
async def veto_history():
    return {
        "events": [
            {
                "ts": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat(),
                "change": random.choice(["VETO_ON", "VETO_OFF"]),
                "reason": random.choice([
                    "High volatility detected",
                    "Volume anomaly",
                    "News sentiment shift",
                    "Technical indicator warning"
                ])
            }
            for _ in range(8)
        ]
    }

@app.post("/api/v1/logs/clear")
async def clear_logs():
    return {"status": "success", "message": "Logs cleared"}

@app.get("/api/v1/systemtest/health/sources")
async def sources_health():
    return {
        "news_api": "healthy",
        "price_feeds": "healthy", 
        "sentiment": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
