# Frontend-Startskript mit automatischer Konfigurationsanpassung
# Autor: Bruno Trading Bot System
# Version: 1.0

Write-Host "=== Bruno Frontend Startup ===" -ForegroundColor Green
Write-Host "Datum: $(Get-Date)" -ForegroundColor Yellow

# Standardkonfiguration
$DEFAULT_BACKEND_PORT = 8000
$CONFIG_FILE = "$PSScriptRoot\.env"
$FRONTEND_PORT = 3000

# Funktion zum Extrahieren des aktuellen Backend-Ports
function Get-CurrentBackendPort {
    try {
        if (Test-Path $CONFIG_FILE) {
            $content = Get-Content $CONFIG_FILE -Raw
            if ($content -match "NEXT_PUBLIC_API_URL=http://localhost:(\d+)") {
                return $matches[1]
            }
        }
    } catch {
        Write-Host "Warnung: Konnte Konfiguration nicht lesen: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    return $DEFAULT_BACKEND_PORT
}

# Funktion zum Testen der Backend-Verfügbarkeit
function Test-BackendAvailability {
    param($Port)
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/v1/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Hauptlogik
Write-Host ""
Write-Host "1. Überprüfe Backend-Verfügbarkeit..." -ForegroundColor Cyan

$current_port = Get-CurrentBackendPort
Write-Host "Aktuell konfigurierter Backend-Port: $current_port" -ForegroundColor Magenta

if (Test-BackendAvailability $current_port) {
    Write-Host "✅ Backend auf Port $current_port ist erreichbar" -ForegroundColor Green
} else {
    Write-Host "❌ Backend auf Port $current_port nicht erreichbar" -ForegroundColor Red
    Write-Host "ℹ️  Stelle sicher, dass der Backend-Server läuft" -ForegroundColor Yellow
    Write-Host "   Führe zuerst: .\start_backend.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "2. Starte Frontend-Entwicklungsserver..." -ForegroundColor Cyan

# Wechsle ins Frontend-Verzeichnis
Set-Location "$PSScriptRoot\frontend"

Write-Host "Frontend läuft auf: http://localhost:$FRONTEND_PORT" -ForegroundColor Green
Write-Host "Backend API: http://localhost:$current_port" -ForegroundColor Magenta
Write-Host "WebSocket: ws://localhost:$current_port/ws/agents" -ForegroundColor Magenta
Write-Host ""
Write-Host "Drücke Ctrl+C zum Beenden" -ForegroundColor Yellow
Write-Host "=" * 50 -ForegroundColor Green

# Starte den Frontend-Server
npm run dev