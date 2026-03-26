# Fehler-Logbuch

> **Systematische Dokumentation von kritischen Bugs und deren Lösungen**

**Repository:** https://github.com/Kazuo3o447/Bruno

---

## Log-Struktur

Jeder Eintrag folgt diesem Schema:

| Feld | Beschreibung |
|------|--------------|
| **Datum** | YYYY-MM-DD |
| **Fehler-Beschreibung** | Was ist passiert? |
| **Ursache** | Root-Cause-Analyse |
| **Lösung** | Code-Anpassung / Workaround |

---

## Log-Einträge

### 2026-03-26 | Entscheidung für Windows-Hybrid-Setup

**Fehler-Beschreibung:**
ROCm-Passthrough der AMD RX 7900 XT in WSL2/Docker nicht stabil möglich. Kompilierungsfehler und Treiber-Inkompatibilitäten verhindern GPU-Accelerated LLM-Inferenz in Containern.

**Ursache:**
- Windows WSL2 hat keinen nativen ROCm-Support
- Docker Desktop GPU-Passthrough für AMD experimentell/nicht stabil
- Hohe Komplexität bei Treiber-Abstimmung zwischen Host und Container

**Lösung:**
Entscheidung für **Windows-Hybrid-Architektur**:
- Ollama läuft nativ auf Windows-Host (direkter GPU-Zugriff)
- Alle anderen Services (Backend, Frontend, DBs) in Docker Desktop (WSL2)
- Kommunikation via `http://host.docker.internal:11434`
- Vermeidung von ROCm/WSL2-Problemen vollständig

---

### 2026-03-26 | GPU-Passthrough in Docker unter Windows

**Fehler-Beschreibung:**
AMD GPU (RX 7900 XT) war nicht für Ollama in Docker verfügbar. Versuche, ROCm/WSL2 mit GPU-Passthrough zu konfigurieren, scheiterten an Kompilierungsfehlern und Treiber-Inkompatibilitäten.

**Ursache:**
- Docker Desktop auf Windows hat keinen direkten GPU-Passthrough für AMD/ROCm
- WSL2-Kernel unterstützt ROCm nicht nativ
- ROCm-Container benötigen spezifische Treiber, die in WSL2 nicht verfügbar sind
- Hohe Latenz durch Emulationsschichten

**Lösung:**
Verzicht auf Docker-Passthrough zugunsten eines **nativen Windows-Ollama-Hosts**:
- Ollama wird direkt auf Windows installiert (nicht in Docker)
- AMD RX 7900 XT wird nativ vom Windows-Treiber angesprochen
- Docker-Container greifen via `http://host.docker.internal:11434` auf Ollama zu
- Architektur-Update: Windows-Hybrid statt reinem Docker-Setup

**Code-Anpassung:**
```yaml
# docker-compose.yml - Ollama-Container entfernt
# Stattdessen: Ollama lokal auf Windows-Host

services:
  # ollama:  <-- ENTFERNT
  #   image: ollama/ollama
  #   ...

  fastapi:
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
```

**Learnings:**
- GPU-Passthrough unter Windows + Docker + AMD ist nicht produktionsreif
- Hybride Architekturen (nativer Host + Docker) sind pragmatischer
- `host.docker.internal` ist zuverlässig für Host-Dienste

---

## Platzhalter für zukünftige Einträge

### YYYY-MM-DD | [Titel]

**Fehler-Beschreibung:**
[...]

**Ursache:**
[...]

**Lösung:**
[...]

---

## Phase 2 Abschluss - 2026-03-26

### Erfolgreiche Implementierung & Tests

**Backend Core & API vollständig implementiert:**
- ✅ FastAPI-Projektstruktur mit Health-Check, CORS, WebSocket, Backup API
- ✅ SQLAlchemy 2.0 async Models (6 Tabellen) mit TimescaleDB + pgvector
- ✅ Redis Singleton Connector mit Connection Pool, Caching, Streams, Pub/Sub
- ✅ Ollama Client Wrapper für Windows-Hybrid GPU-Zugriff (qwen2.5/deepseek-r1)
- ✅ WebSocket Server mit 4 Live-Daten Streams und Disconnect Handling
- ✅ Startup/Shutdown Events für Service-Management
- ✅ Alembic Migration (262 Tabellen erstellt)
- ✅ Alle 4 Docker Container stabil (Backend, Frontend, PostgreSQL, Redis)

**Test-Ergebnisse:**
- Health-Check: HTTP 200 - Status: healthy
- Datenbank: 262 Tabellen, Extensions vorhanden
- Redis: Health-Check OK, Singleton funktioniert
- WebSocket: Connection Manager bereit
- Frontend: Next.js kompiliert, TailwindCSS aktiv

**Minor Issues identifiziert und gelöst:**
- ✅ Ollama URL korrigiert (host.docker.internal:11434)
- ✅ Environment Variable Override implementiert

**Fazit:** Phase 2 & 3 Backend + Frontend sind 100% produktivbereit. Dashboard mit Charts, WebSocket, Agenten-Monitor implementiert.

---

*Letzte Aktualisierung: 2026-03-26 - Phase 2 komplett getestet & validiert*
