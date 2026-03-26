"""
WebSocket Router für Live-Daten zum Bruno-Frontend

Streaming von Marktdaten, Agenten-Status und System-Metriken.
Zwingend mit WebSocketDisconnect Handling für stabile Verbindungen.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio
import json
import logging
from typing import Dict, Set, Optional
from datetime import datetime

from app.core.redis_client import redis_client
from app.core.database import get_db, AsyncSession
from app.schemas.models import AgentStatus, SystemMetrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSockets"])

# Verfolger für aktive WebSocket-Verbindungen
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "market": set(),
            "agents": set(),
            "system": set(),
            "alerts": set()
        }
        self.connection_metadata: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, connection_type: str, metadata: Optional[Dict] = None):
        """Verbindet einen neuen WebSocket."""
        await websocket.accept()
        
        if connection_type not in self.active_connections:
            self.active_connections[connection_type] = set()
            
        self.active_connections[connection_type].add(websocket)
        self.connection_metadata[websocket] = {
            "type": connection_type,
            "connected_at": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        logger.info(f"WebSocket verbunden: {connection_type} (Total: {len(self.active_connections[connection_type])})")

    def disconnect(self, websocket: WebSocket):
        """Trennt einen WebSocket."""
        connection_type = self.connection_metadata.get(websocket, {}).get("type", "unknown")
        
        if connection_type in self.active_connections:
            self.active_connections[connection_type].discard(websocket)
        
        self.connection_metadata.pop(websocket, None)
        logger.info(f"WebSocket getrennt: {connection_type}")

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Sendet eine Nachricht an einen spezifischen WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Fehler beim Senden an WebSocket: {e}")
            self.disconnect(websocket)

    async def broadcast(self, connection_type: str, message: dict):
        """Broadcastet eine Nachricht an alle Verbindungen eines Typs."""
        if connection_type not in self.active_connections:
            return
            
        disconnected = set()
        for connection in self.active_connections[connection_type]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast Fehler: {e}")
                disconnected.add(connection)
        
        # Tote Verbindungen entfernen
        for connection in disconnected:
            self.disconnect(connection)

    def get_connection_count(self, connection_type: str) -> int:
        """Gibt die Anzahl aktiver Verbindungen zurück."""
        return len(self.active_connections.get(connection_type, set()))


manager = ConnectionManager()


@router.websocket("/market/{symbol}")
async def websocket_market_data(websocket: WebSocket, symbol: str):
    """Streamt Live-Marktdaten an Bruno-Frontend."""
    await manager.connect(websocket, "market", {"symbol": symbol})
    
    try:
        while True:
            # Lade neueste Marktdaten aus Redis
            if redis_client.redis:
                # Versuche Orderbook-Daten
                orderbook_data = await redis_client.get_cache(f"market:orderbook:{symbol}")
                if orderbook_data:
                    await manager.send_personal_message(websocket, {
                        "type": "orderbook",
                        "symbol": symbol,
                        "data": orderbook_data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                # Versuche Ticker-Daten
                ticker_data = await redis_client.get_cache(f"market:ticker:{symbol}")
                if ticker_data:
                    await manager.send_personal_message(websocket, {
                        "type": "ticker",
                        "symbol": symbol,
                        "data": ticker_data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                # Versuche Candle-Daten
                candle_data = await redis_client.get_cache(f"market:candle:{symbol}")
                if candle_data:
                    await manager.send_personal_message(websocket, {
                        "type": "candle",
                        "symbol": symbol,
                        "data": candle_data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            await asyncio.sleep(1.0)  # 1 Sekunde Update-Intervall
            
    except WebSocketDisconnect:
        logger.info(f"Market WebSocket getrennt für {symbol}")
    except Exception as e:
        logger.error(f"Market WebSocket Error für {symbol}: {e}")
    finally:
        manager.disconnect(websocket)


@router.websocket("/agents")
async def websocket_agent_status(websocket: WebSocket):
    """Streamt Agenten-Status an Bruno-Frontend."""
    await manager.connect(websocket, "agents")
    
    try:
        while True:
            # Lade Agenten-Status aus Redis oder DB
            agents_data = await redis_client.get_cache("agents:status")
            
            if agents_data:
                await manager.send_personal_message(websocket, {
                    "type": "agents_status",
                    "data": agents_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            await asyncio.sleep(2.0)  # 2 Sekunden Update-Intervall
            
    except WebSocketDisconnect:
        logger.info("Agents WebSocket getrennt")
    except Exception as e:
        logger.error(f"Agents WebSocket Error: {e}")
    finally:
        manager.disconnect(websocket)


@router.websocket("/system")
async def websocket_system_metrics(websocket: WebSocket):
    """Streamt System-Metriken an Bruno-Frontend."""
    await manager.connect(websocket, "system")
    
    try:
        while True:
            # Lade System-Metriken aus Redis
            system_data = await redis_client.get_cache("system:metrics")
            
            if system_data:
                await manager.send_personal_message(websocket, {
                    "type": "system_metrics",
                    "data": system_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Sende WebSocket-Verbindungsstatistik
            await manager.send_personal_message(websocket, {
                "type": "websocket_stats",
                "data": {
                    "total_connections": sum(len(conns) for conns in manager.active_connections.values()),
                    "connections_by_type": {
                        conn_type: len(conns) 
                        for conn_type, conns in manager.active_connections.items()
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await asyncio.sleep(5.0)  # 5 Sekunden Update-Intervall
            
    except WebSocketDisconnect:
        logger.info("System WebSocket getrennt")
    except Exception as e:
        logger.error(f"System WebSocket Error: {e}")
    finally:
        manager.disconnect(websocket)


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Streamt Alerts und Benachrichtigungen an Bruno-Frontend."""
    await manager.connect(websocket, "alerts")
    
    try:
        while True:
            # Lade ungelesene Alerts aus Redis
            alerts_data = await redis_client.get_cache("alerts:unread")
            
            if alerts_data:
                await manager.send_personal_message(websocket, {
                    "type": "alerts",
                    "data": alerts_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            await asyncio.sleep(3.0)  # 3 Sekunden Update-Intervall
            
    except WebSocketDisconnect:
        logger.info("Alerts WebSocket getrennt")
    except Exception as e:
        logger.error(f"Alerts WebSocket Error: {e}")
    finally:
        manager.disconnect(websocket)


# Helper-Funktionen für andere Teile der Anwendung
async def broadcast_market_update(symbol: str, data: dict):
    """Broadcastet Marktdaten-Update."""
    await manager.broadcast("market", {
        "type": "market_update",
        "symbol": symbol,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })


async def broadcast_agent_status(agent_id: str, status: dict):
    """Broadcastet Agenten-Status-Update."""
    await manager.broadcast("agents", {
        "type": "agent_update",
        "agent_id": agent_id,
        "data": status,
        "timestamp": datetime.utcnow().isoformat()
    })


async def broadcast_alert(alert: dict):
    """Broadcastet eine Alert-Nachricht."""
    await manager.broadcast("alerts", {
        "type": "new_alert",
        "data": alert,
        "timestamp": datetime.utcnow().isoformat()
    })


async def get_websocket_stats() -> dict:
    """Gibt WebSocket-Statistiken zurück."""
    return {
        "total_connections": sum(len(conns) for conns in manager.active_connections.values()),
        "connections_by_type": {
            conn_type: len(conns) 
            for conn_type, conns in manager.active_connections.items()
        }
    }
