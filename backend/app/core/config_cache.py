import json
import time
from typing import Any, Optional

class ConfigCache:
    """
    Cached config.json reader. Lädt nur 1× beim Startup.
    Laufzeit-Änderungen erfolgen über das Objekt im RAM.
    Stoppt die ständigen Disk-Reads.
    """
    _instance = None
    _config: dict = {}
    _last_load: float = 0
    _path: str = ""
    _loaded_once = False  # NEU: Flag für einmaliges Laden beim Startup

    @classmethod
    def init(cls, path: str) -> None:
        """Initialisiert den Cache mit dem Pfad zur config.json (lädt nur einmal)."""
        cls._path = path
        cls._reload()
        cls._loaded_once = True

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Gibt einen Konfigurationswert zurück.
        Lädt die Datei NICHT neu - nur beim Startup.
        """
        return cls._config.get(key, default)

    @classmethod
    def _reload(cls) -> None:
        """Lädt die config.json Datei neu (nur beim Startup)."""
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
        return cls._config.copy()

    @classmethod
    def force_reload(cls) -> None:
        """Erzwingt ein sofortiges Neuladen der Konfiguration (für manuelle Updates)."""
        cls._reload()

