import json
import time
from typing import Any, Optional

class ConfigCache:
    """
    Cached config.json reader. Lädt max 1× pro Minute.
    Vermeidet wiederholtes File I/O in Agent-Loops.
    """
    _instance = None
    _config: dict = {}
    _last_load: float = 0
    _path: str = ""
    TTL = 60.0  # Sekunden

    @classmethod
    def init(cls, path: str) -> None:
        """Initialisiert den Cache mit dem Pfad zur config.json."""
        cls._path = path
        cls._reload()

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Gibt einen Konfigurationswert zurück.
        Lädt die Datei neu, wenn TTL abgelaufen ist.
        """
        if time.time() - cls._last_load > cls.TTL:
            cls._reload()
        return cls._config.get(key, default)

    @classmethod
    def _reload(cls) -> None:
        """Lädt die config.json Datei neu."""
        try:
            with open(cls._path, 'r', encoding='utf-8') as f:
                cls._config = json.load(f)
            cls._last_load = time.time()
        except FileNotFoundError:
            cls._config = {}
            cls._last_load = 0
        except json.JSONDecodeError as e:
            # Bei fehlerhaftem JSON leeren Cache verwenden
            cls._config = {}
            cls._last_load = 0
        except Exception as e:
            cls._config = {}
            cls._last_load = 0

    @classmethod
    def get_all(cls) -> dict:
        """Gibt die gesamte Konfiguration zurück."""
        if time.time() - cls._last_load > cls.TTL:
            cls._reload()
        return cls._config.copy()

    @classmethod
    def force_reload(cls) -> None:
        """Erzwingt ein sofortiges Neuladen der Konfiguration."""
        cls._reload()
