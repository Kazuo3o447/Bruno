# ═══════════════════════════════════════════════════════════
# 🚀 Bruno Trading Bot — PRODUCTION DEPLOYMENT GUIDE
# ═══════════════════════════════════════════════════════════

## 📋 VORAUSSETZUNGEN

### 🔧 System-Anforderungen
- **RAM:** Minimum 8GB, Empfohlen 16GB+
- **CPU:** 4+ Cores, Empfohlen 8+ Cores
- **Storage:** 100GB+ SSD
- **OS:** Linux (Ubuntu 20.04+) oder Docker-fähiges System
- **Docker:** Version 20.10+ mit Docker Compose v2.0+

### 🌐 Netzwerk
- **Ports:** 80, 443, 3000, 8000, 9090, 8080
- **Firewall:** Ports 80/443 offen, Rest intern
- **Domain:** Optional für SSL-Zertifikat

---

## 🛡️ SICHERHEITS-CHECKLISTE

### ✅ Vor Deployment
- [ ] **API Keys:** Alle echten Keys in `.env.production` ersetzen
- [ ] **Passwörter:** Starke Passwörter (32+ chars) für DB/Redis
- [ ] **Paper Trading:** `PAPER_TRADING_ONLY=true` belassen
- [ ] **Dry Run:** `DRY_RUN=true` belassen
- [ ] **Live Trading:** `LIVE_TRADING_APPROVED=false`
- [ ] **Git:** Keine `.env` Dateien im Repository
- [ ] **SSL:** Zertifikat für HTTPS (optional)
- [ ] **Backup:** Backup-Verzeichnis konfiguriert
- [ ] **Monitoring:** Prometheus/Metrics aktiviert

### 🔒 Production Security
```bash
# 1. Dateiberechtigungen setzen
chmod 600 .env.production
chmod 700 logs/
chmod 700 backups/

# 2. Docker Security Scan (optional)
docker scan bruno-backend:latest
docker scan bruno-frontend:latest

# 3. Netzwerk-Isolation prüfen
docker network ls | grep bruno-prod
```

---

## 🚀 DEPLOYMENT SCHÜRZE

### 1️⃣ Environment Setup
```bash
# Production Environment aktivieren
export COMPOSE_FILE=docker-compose.production.yml
export COMPOSE_PROJECT_NAME=bruno-prod

# Environment Variables laden
set -a
source .env.production
set +a
```

### 2️⃣ Production Build
```bash
# Production Images bauen
docker-compose -f docker-compose.production.yml build --no-cache

# Health-Checks prüfen
docker-compose -f docker-compose.production.yml config
```

### 3️⃣ Database Migration
```bash
# PostgreSQL starten
docker-compose -f docker-compose.production.yml up -d postgres redis

# Migration durchführen
docker-compose -f docker-compose.production.yml run --rm api-backend alembic upgrade head

# Daten prüfen
docker-compose -f docker-compose.production.yml exec postgres psql -U $DB_USER -d $DB_NAME -c "SELECT version();"
```

### 4️⃣ Full Deployment
```bash
# Alle Services starten
docker-compose -f docker-compose.production.yml up -d

# Status prüfen
docker-compose -f docker-compose.production.yml ps

# Logs prüfen
docker-compose -f docker-compose.production.yml logs -f api-backend
```

---

## 📊 HEALTH CHECKS

### 🔍 System-Status
```bash
# API Health Check
curl http://localhost:8000/api/v1/health

# Frontend Health Check  
curl http://localhost:3000

# Nginx Health Check
curl http://localhost/nginx-health

# API Sources Status
curl http://localhost:8000/api/v1/systemtest/health/sources
```

### 📈 Monitoring
```bash
# Prometheus Metrics
curl http://localhost:9090/metrics

# Container-Ressourcen
docker stats --no-stream

# Log-Aggregation
docker-compose -f docker-compose.production.yml logs --tail=100
```

---

## 🔄 MAINTENANCE

### 📅 Tägliche Tasks
```bash
# 1. Backup erstellen
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U $DB_USER $DB_NAME > backups/backup_$(date +%Y%m%d).sql

# 2. Logs rotieren
docker-compose -f docker-compose.production.yml exec api-backend find /app/logs -name "*.log" -mtime +7 -delete

# 3. System-Update prüfen
docker-compose -f docker-compose.production.yml pull
```

### 🚨 Fehlerbehebung
```bash
# Service neu starten
docker-compose -f docker-compose.production.yml restart api-backend

# Logs analysieren
docker-compose -f docker-compose.production.yml logs --tail=500 worker-backend

# Health-Check erzwingen
curl -X POST http://localhost:8000/api/v1/health/force-check
```

---

## 📝 CONFIGURATION

### 🌍 Environment Variables
```bash
# Production spezifisch
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true

# Backup Schedule
BACKUP_SCHEDULE=daily
METRICS_PORT=9090
HEALTH_CHECK_PORT=8080
```

### 🔧 Performance Tuning
```yaml
# docker-compose.production.yml Anpassungen
deploy:
  resources:
    limits:
      memory: 2G      # Nach Bedarf erhöhen
      cpus: '1.0'     # CPU-Limits
    reservations:
      memory: 1G
      cpus: '0.5'
```

---

## 🚨 CRITICAL WARNINGS

### ⚠️ NIEMALS in Production:
- `DRY_RUN=false` ohne Backtest
- `PAPER_TRADING_ONLY=false` ohne Genehmigung
- `LIVE_TRADING_APPROVED=true` ohne Validierung
- Echte API Keys in Git committen
- Default-Passwörter verwenden

### 🛡️ IMMER aktivieren:
- HTTPS mit SSL-Zertifikat
- Firewall mit Rate Limiting
- Regular Backups
- Monitoring & Alerting
- Log-Aggregation
- Security Updates

---

## 📞 SUPPORT

### 🆘 Emergency Commands
```bash
# Sofort-Stop (Notfall)
docker-compose -f docker-compose.production.yml down

# Vollständiger Reset
docker-compose -f docker-compose.production.yml down -v
docker system prune -f

# Recovery von Backup
docker-compose -f docker-compose.production.yml exec postgres psql -U $DB_USER -d $DB_NAME < backup_20240404.sql
```

### 📧 Monitoring Alerts
- **CPU > 80%:** System überlastet
- **Memory > 90%:** RAM knapp
- **API Latency > 5s:** Netzwerkprobleme
- **Disk > 85%:** Storage voll

---

## ✅ DEPLOYMENT COMPLETE

Nach erfolgreichem Deployment:
1. **Dashboard prüfen:** http://localhost:3000
2. **API-Status:** Alle 13 APIs online
3. **Health-Checks:** Alle Services grün
4. **Monitoring:** Prometheus erreichbar
5. **Backup:** Automatisiert konfiguriert

**🎉 Bruno v2 Production Ready!**
