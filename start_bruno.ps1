# Bruno Trading Bot - Hauptstartskript
# Orchestriert Backend und Frontend mit automatischer Portkonflikt-Behandlung
# Autor: Bruno Trading Bot System  
# Version: 1.0

Write-Host ""
Write-Host "██████╗ ██████╗ ██╗   ██╗███╗   ██╗ ██████╗ " -ForegroundColor Cyan
Write-Host "██╔══██╗██╔══██╗██║   ██║████╗  ██║██╔═══██╗" -ForegroundColor Cyan
Write-Host "██████╔╝██████╔╝██║   ██║██╔██╗ ██║██║   ██║" -ForegroundColor Cyan
Write-Host "██╔══██╗██╔══██╗██║   ██║██║╚██╗██║██║   ██║" -ForegroundColor Cyan
Write-Host "██████╔╝██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝" -ForegroundColor Cyan
Write-Host "╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ " -ForegroundColor Cyan
Write-Host ""
Write-Host "Trading Bot System Startup" -ForegroundColor Green
Write-Host "Datum: $(Get-Date)" -ForegroundColor Yellow
Write-Host ""

# Konfiguration
$BACKEND_SCRIPT = "$PSScriptRoot\start_backend.ps1"
$FRONTEND_SCRIPT = "$PSScriptRoot\start_frontend.ps1"

# Prüfe ob PowerShell Skripte vorhanden sind
if (-not (Test-Path $BACKEND_SCRIPT)) {
    Write-Host "❌ Backend-Startskript nicht gefunden: $BACKEND_SCRIPT" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $FRONTEND_SCRIPT)) {
    Write-Host "❌ Frontend-Startskript nicht gefunden: $FRONTEND_SCRIPT" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Alle Startskripte gefunden" -ForegroundColor Green
Write-Host ""

# Starte Backend
Write-Host "1. Starte Backend-Server..." -ForegroundColor Cyan
Write-Host "   Führe: $BACKEND_SCRIPT" -ForegroundColor White

$backendProcess = Start-Process -FilePath "powershell" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$BACKEND_SCRIPT`"" -PassThru -WindowStyle Normal

Write-Host "   Backend gestartet (PID: $($backendProcess.Id))" -ForegroundColor Green
Write-Host "   Warte 5 Sekunden für Initialisierung..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Starte Frontend
Write-Host ""
Write-Host "2. Starte Frontend-Development-Server..." -ForegroundColor Cyan
Write-Host "   Führe: $FRONTEND_SCRIPT" -ForegroundColor White

$frontendProcess = Start-Process -FilePath "powershell" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$FRONTEND_SCRIPT`"" -PassThru -WindowStyle Normal

Write-Host "   Frontend gestartet (PID: $($frontendProcess.Id))" -ForegroundColor Green
Write-Host ""

# Statusübersicht
Write-Host "=" * 60 -ForegroundColor Green
Write-Host "BRUNO TRADING BOT GESTARTET" -ForegroundColor Green -BackgroundColor DarkBlue
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "📍 Frontend Dashboard:" -ForegroundColor Cyan
Write-Host "   http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "📍 Backend API:" -ForegroundColor Cyan  
Write-Host "   http://localhost:8000" -ForegroundColor White
Write-Host "   Health Check: http://localhost:8000/api/v1/health" -ForegroundColor Gray
Write-Host ""
Write-Host "📍 WebSocket Connections:" -ForegroundColor Cyan
Write-Host "   Agent Status: ws://localhost:8000/ws/agents" -ForegroundColor Gray
Write-Host "   Market Data: ws://localhost:8000/ws/market/{symbol}" -ForegroundColor Gray
Write-Host "   Logs: ws://localhost:8000/api/v1/logs/ws" -ForegroundColor Gray
Write-Host ""
Write-Host "📍 System Status:" -ForegroundColor Cyan
Write-Host "   Backend PID: $($backendProcess.Id)" -ForegroundColor White
Write-Host "   Frontend PID: $($frontendProcess.Id)" -ForegroundColor White
Write-Host ""
Write-Host "ℹ️  Beende beide Prozesse mit Ctrl+C in den jeweiligen Fenstern" -ForegroundColor Yellow
Write-Host ""
Write-Host "✅ System erfolgreich gestartet!" -ForegroundColor Green
Write-Host ""

# Warte auf Benutzer-Input
Read-Host "Drücke Enter um zur Hauptkonsole zurückzukehren"