# API Datenprobleme - Lokale Entwicklung

## Problem Diagnose (2026-04-05)

### Symptome
- Alle Datenquellen zeigen "offline" im Dashboard
- API-Endpunkte liefern `null` Werte
- Worker kann nicht starten mit Datenbank-Verbindungsfehlern

### Ursache
Die Konfiguration in `backend/app/core/config.py` verwendet Docker-Hostnamen:
```python
DB_HOST: str = "postgres"      # Docker Container Name
REDIS_HOST: str = "redis"     # Docker Container Name
```

Für die lokale Entwicklung müssen diese auf `localhost` zeigen, da PostgreSQL und Redis lokal installiert sind.

### Fehlermeldungen
```
[Errno 11001] getaddrinfo failed
```
Dies bedeutet, dass der Hostname "postgres" nicht aufgelöst werden kann.

### Lösung

#### Option 1: Docker Environment (empfohlen)
Verwende Docker Compose für die volle Infrastruktur:
```bash
docker compose up -d --build
```

#### Option 2: Lokale Services mit Environment Override
Erstelle eine `.env` Datei im Projekt-Root mit lokalen Hostnamen:
```bash
# Lokale Entwicklungsumgebung
DB_HOST=localhost
REDIS_HOST=localhost
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Option 3: Lokale Services starten
Stelle sicher, dass PostgreSQL und Redis lokal laufen:
```bash
# PostgreSQL auf localhost:5432
# Redis auf localhost:6379
```

### Verifizierung
Teste die Verbindungen:
```bash
# Backend Health Check
curl http://localhost:8000/health

# Telemetry API (sollte Daten zeigen)
curl http://localhost:8000/api/v1/telemetry/live
```

### Nächste Schritte
1. Environment konfigurieren
2. Worker neu starten
3. Datenquellen-Status überprüfen
4. Frontend-Daten validieren

## Status
- [x] Problem identifiziert
- [x] Lösung dokumentiert
- [ ] Environment konfigurieren
- [ ] Services neu starten
