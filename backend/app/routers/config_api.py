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

router = APIRouter(tags=["config"])

# Config-Pfad relativ zum Backend-Root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups", "config_history")

CONFIG_SCHEMA = {
    "GRSS_Threshold": {"min": 30, "max": 70, "type": "int", "label": "GRSS Mindestschwelle"},
    "OFI_Threshold": {"min": 10, "max": 300, "type": "int", "label": "OFI Schwellenwert"},
    "Max_Leverage": {"min": 0.1, "max": 1.0, "type": "float", "label": "Max. Leverage"},
    "Stop_Loss_Pct": {"min": 0.003, "max": 0.03, "type": "float", "label": "Stop-Loss %"},
    "Liq_Distance": {"min": 0.002, "max": 0.02, "type": "float", "label": "Min. Liq-Wall Abstand"},
    "LEARNING_MODE_ENABLED": {"type": "bool", "label": "Learning Mode"},
    "LEARNING_GRSS_Threshold": {"min": 0, "max": 100, "type": "int", "label": "Learning GRSS Threshold"},
    "LEARNING_Layer1_Confidence": {"min": 0.0, "max": 1.0, "type": "float", "label": "Learning Layer 1 Confidence"},
    "LEARNING_Layer2_Confidence": {"min": 0.0, "max": 1.0, "type": "float", "label": "Learning Layer 2 Confidence"},
    "LEARNING_Layer1_Confidence_PROD": {"min": 0.0, "max": 1.0, "type": "float", "label": "Prod Layer 1 Confidence"},
    "LEARNING_Layer2_Confidence_PROD": {"min": 0.0, "max": 1.0, "type": "float", "label": "Prod Layer 2 Confidence"},
    "PHANTOM_HOLD_DURATION_MINUTES": {"min": 0, "max": 1440, "type": "int", "label": "Phantom Hold Duration (Minuten)"},
    "_comment_v2": {"type": "str", "label": "Kommentar"},
    "COMPOSITE_THRESHOLD_LEARNING": {"min": 0, "max": 100, "type": "int", "label": "Composite Threshold Learning"},
    "COMPOSITE_THRESHOLD_PROD": {"min": 0, "max": 100, "type": "int", "label": "Composite Threshold Prod"},
    "COMPOSITE_W_TA": {"min": 0.0, "max": 1.0, "type": "float", "label": "Composite Weight TA"},
    "COMPOSITE_W_LIQ": {"min": 0.0, "max": 1.0, "type": "float", "label": "Composite Weight LIQ"},
    "COMPOSITE_W_FLOW": {"min": 0.0, "max": 1.0, "type": "float", "label": "Composite Weight FLOW"},
    "COMPOSITE_W_MACRO": {"min": 0.0, "max": 1.0, "type": "float", "label": "Composite Weight MACRO"},
    "COMPOSITE_SIGNAL_THRESHOLD": {"min": 0, "max": 100, "type": "int", "label": "Composite Signal Threshold"},
    "TRADE_COOLDOWN_SECONDS": {"min": 0, "max": 86400, "type": "int", "label": "Trade Cooldown (Sekunden)"},
    "DAILY_MAX_LOSS_PCT": {"min": 0.0, "max": 100.0, "type": "float", "label": "Daily Max Loss %"},
    "MAX_CONSECUTIVE_LOSSES": {"min": 0, "max": 100, "type": "int", "label": "Max Consecutive Losses"},
    "BREAKEVEN_TRIGGER_PCT": {"min": 0.0, "max": 1.0, "type": "float", "label": "Breakeven Trigger %"},
    "ATR_TRAILING_MULTIPLIER": {"min": 0.5, "max": 5.0, "type": "float", "label": "ATR Trailing Multiplier"},
    "TP1_SIZE_PCT": {"min": 0.0, "max": 1.0, "type": "float", "label": "TP1 Position Size %"},
    "TP2_SIZE_PCT": {"min": 0.0, "max": 1.0, "type": "float", "label": "TP2 Position Size %"},
    "ENABLE_ATR_TRAILING": {"type": "bool", "label": "ATR Trailing aktiv"},
    "ENABLE_VOLUME_PROFILE": {"type": "bool", "label": "Volume Profile aktiv"},
    "ENABLE_DELTA_ABSORPTION": {"type": "bool", "label": "Delta Absorption aktiv"},
    "ENABLE_LLM_CASCADE_V4": {"type": "bool", "label": "Enable LLM Cascade V4"},
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

        allowed_keys = set(current.keys()) | set(CONFIG_SCHEMA.keys())

        # Validierung
        errors = []
        for key, value in updates.items():
            if key not in allowed_keys:
                errors.append(f"Unbekannter Parameter: {key}")
                continue

            schema = CONFIG_SCHEMA.get(key)
            if not schema:
                continue

            expected_type = schema.get("type")
            if expected_type == "int":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(f"{key}: erwarteter Typ int")
                    continue
            elif expected_type == "float":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"{key}: erwarteter Typ float")
                    continue
                value = float(value)
            elif expected_type == "bool":
                if not isinstance(value, bool):
                    errors.append(f"{key}: erwarteter Typ bool")
                    continue
            elif expected_type == "str":
                if not isinstance(value, str):
                    errors.append(f"{key}: erwarteter Typ str")
                    continue

            if "min" in schema and "max" in schema:
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
