"""
Config API Router - Read/Write Bot Configuration.

GET /api/v1/config - Aktuelle Konfiguration mit Schema
PUT /api/v1/config - Konfiguration aktualisieren (mit Validierung)
"""
import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1", tags=["config"])

# Config-Pfad relativ zum Backend-Root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups", "config_history")

CONFIG_SCHEMA = {
    "GRSS_Threshold": {"min": 30, "max": 70, "type": "int", "label": "GRSS Mindestschwelle"},
    "OFI_Threshold": {"min": 200, "max": 1000, "type": "int", "label": "OFI Schwellenwert"},
    "Max_Leverage": {"min": 0.1, "max": 1.0, "type": "float", "label": "Max. Leverage"},
    "Stop_Loss_Pct": {"min": 0.003, "max": 0.03, "type": "float", "label": "Stop-Loss %"},
    "Liq_Distance": {"min": 0.002, "max": 0.02, "type": "float", "label": "Min. Liq-Wall Abstand"},
}


class ConfigUpdate(BaseModel):
    updates: Dict[str, Any]


@router.get("/config")
async def get_config():
    """Aktuelle Konfiguration mit Schema-Informationen."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        return {"config": config, "schema": CONFIG_SCHEMA}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="config.json nicht gefunden")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(payload: ConfigUpdate):
    """
    Aktualisiert config.json.
    Validiert gegen Schema — kein Wert außerhalb der erlaubten Range.
    Schreibt config_history Backup vor jeder Änderung.
    """
    updates = payload.updates
    try:
        with open(CONFIG_PATH, "r") as f:
            current = json.load(f)

        # Validierung
        errors = []
        for key, value in updates.items():
            if key not in CONFIG_SCHEMA:
                errors.append(f"Unbekannter Parameter: {key}")
                continue
            schema = CONFIG_SCHEMA[key]
            if value < schema["min"] or value > schema["max"]:
                errors.append(
                    f"{key}: {value} außerhalb erlaubtem Bereich "
                    f"[{schema['min']}, {schema['max']}]"
                )
        if errors:
            raise HTTPException(status_code=422, detail=errors)

        # Backup
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = os.path.join(BACKUP_DIR, f"config_{ts}.json")
        with open(backup_path, "w") as f:
            json.dump(
                {
                    "timestamp": ts,
                    "previous": current,
                    "new": {**current, **updates},
                    "changed_by": "dashboard_ui",
                },
                f,
                indent=2,
            )

        # Schreiben
        current.update(updates)
        with open(CONFIG_PATH, "w") as f:
            json.dump(current, f, indent=4)

        return {"success": True, "config": current, "backup": backup_path}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/history")
async def get_config_history(limit: int = 10):
    """Letzte Konfigurationsänderungen aus Backup-Verzeichnis."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return {"history": []}

        files = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("config_") and f.endswith(".json")],
            reverse=True,
        )[:limit]

        history = []
        for fname in files:
            fpath = os.path.join(BACKUP_DIR, fname)
            try:
                with open(fpath) as f:
                    data = json.load(f)
                    history.append(
                        {
                            "timestamp": data.get("timestamp"),
                            "changed_by": data.get("changed_by"),
                            "file": fname,
                        }
                    )
            except Exception:
                pass

        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
