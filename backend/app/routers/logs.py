"""
Log API Router - Endpoints für das Log-System
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from typing import Optional, List
import json
import asyncio

from app.core.log_manager import log_manager, LogEntry
from app.core.redis_client import redis_client

router = APIRouter()


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=1000, description="Maximale Anzahl Logs"),
    level: Optional[str] = Query(default=None, description="Filter nach Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    category: Optional[str] = Query(default=None, description="Filter nach Kategorie"),
    source: Optional[str] = Query(default=None, description="Filter nach Quelle"),
    search: Optional[str] = Query(default=None, description="Text-Suche in Nachrichten"),
    since: Optional[str] = Query(default=None, description="Logs seit Zeitstempel (ISO format)")
):
    """
    Holt Logs mit verschiedenen Filtern
    """
    logs = await log_manager.get_logs(
        limit=limit,
        level=level,
        category=category,
        source=source,
        search=search,
        since=since
    )
    
    return {
        "status": "success",
        "count": len(logs),
        "logs": [log.to_dict() for log in logs]
    }


@router.get("/logs/stats")
async def get_log_stats():
    """
    Holt Log-Statistiken (Anzahl nach Level, Kategorien, Quellen)
    """
    stats = await log_manager.get_stats()
    return {
        "status": "success",
        "stats": stats
    }


@router.post("/logs/clear")
async def clear_logs():
    """
    Löscht alle Logs
    """
    success = await log_manager.clear_logs()
    if success:
        return {"status": "success", "message": "Alle Logs gelöscht"}
    else:
        return {"status": "error", "message": "Fehler beim Löschen der Logs"}


@router.get("/logs/categories")
async def get_categories():
    """
    Holt alle verfügbaren Log-Kategorien
    """
    stats = await log_manager.get_stats()
    return {
        "status": "success",
        "categories": stats.get("categories", [])
    }


@router.get("/logs/sources")
async def get_sources():
    """
    Holt alle verfügbaren Log-Quellen
    """
    stats = await log_manager.get_stats()
    return {
        "status": "success",
        "sources": stats.get("sources", [])
    }


@router.websocket("/logs/ws")
async def logs_websocket(websocket: WebSocket):
    """
    WebSocket für Live-Log-Updates
    """
    await websocket.accept()
    
    try:
        # Letzte 100 Logs senden
        logs = await log_manager.get_logs(limit=100)
        await websocket.send_json({
            "type": "history",
            "logs": [log.to_dict() for log in logs]
        })
        
        # Auf neue Logs warten
        async def log_listener(message):
            try:
                log_data = json.loads(message)
                await websocket.send_json({
                    "type": "new_log",
                    "log": log_data
                })
            except Exception as e:
                print(f"Fehler beim Senden von Log: {e}")
        
        # Subscriben
        pubsub = await redis_client.client.pubsub()
        await pubsub.subscribe("logs:live")
        
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                await log_listener(message["data"])
            
            # Auf Client-Nachrichten prüfen (für Filter-Updates etc.)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                if data.get("action") == "filter":
                    # Filter anwenden und gefilterte Logs senden
                    logs = await log_manager.get_logs(
                        limit=data.get("limit", 1000),
                        level=data.get("level"),
                        category=data.get("category"),
                        source=data.get("source"),
                        search=data.get("search")
                    )
                    await websocket.send_json({
                        "type": "filtered",
                        "logs": [log.to_dict() for log in logs]
                    })
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"WebSocket Fehler: {e}")
                break
                
    except WebSocketDisconnect:
        print("Log WebSocket disconnected")
    except Exception as e:
        print(f"Log WebSocket Error: {e}")
    finally:
        try:
            await pubsub.unsubscribe("logs:live")
        except:
            pass
