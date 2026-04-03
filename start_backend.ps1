# Robustes Backend-Startskript mit Portkonflikt-Behandlung
# Autor: Bruno Trading Bot System
# Version: 1.0

Write-Host "=== Bruno Backend Server Startup ===" -ForegroundColor Green
Write-Host "Datum: $(Get-Date)" -ForegroundColor Yellow

# Konfiguration
$DEFAULT_PORT = 8000
$MAX_RETRIES = 5
$PORT_RANGE_START = 8000
$PORT_RANGE_END = 8010

# Funktion zum Überprüfen der Portverfügbarkeit
function Test-PortAvailability {
    param($Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]$Port
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

# Funktion zum Finden eines verfügbaren Ports
function Find-AvailablePort {
    for ($port = $PORT_RANGE_START; $port -le $PORT_RANGE_END; $port++) {
        if (Test-PortAvailability $port) {
            return $port
        }
    }
    return $null
}

# Funktion zum Beenden von Prozessen auf einem Port
function Stop-PortProcesses {
    param($Port)
    try {
        $processes = netstat -ano | findstr ":$Port" | ForEach-Object {
            $_.Trim() -split '\s+' | Select-Object -Last 1
        } | Get-Unique
        
        foreach ($pid in $processes) {
            if ($pid -match '\d+') {
                Write-Host "Beende Prozess PID $pid auf Port $Port" -ForegroundColor Red
                taskkill /PID $pid /F 2>$null
                Start-Sleep -Milliseconds 200
            }
        }
    } catch {
        Write-Host "Warnung: Konnte Prozesse auf Port $Port nicht beenden: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Hauptlogik
Write-Host ""
Write-Host "1. Überprüfe Portverfügbarkeit..." -ForegroundColor Cyan

# Versuche zuerst den Standardport
if (Test-PortAvailability $DEFAULT_PORT) {
    $selected_port = $DEFAULT_PORT
    Write-Host "✅ Port $DEFAULT_PORT ist verfügbar" -ForegroundColor Green
} else {
    Write-Host "⚠️  Port $DEFAULT_PORT ist belegt, suche alternativen Port..." -ForegroundColor Yellow
    Stop-PortProcesses $DEFAULT_PORT
    
    # Warte kurz und versuche es erneut
    Start-Sleep -Seconds 1
    
    if (Test-PortAvailability $DEFAULT_PORT) {
        $selected_port = $DEFAULT_PORT
        Write-Host "✅ Port $DEFAULT_PORT nach Bereinigung verfügbar" -ForegroundColor Green
    } else {
        # Suche alternativen Port
        $selected_port = Find-AvailablePort
        if ($selected_port) {
            Write-Host "✅ Alternativer Port gefunden: $selected_port" -ForegroundColor Green
        } else {
            Write-Host "❌ Kein verfügbarer Port im Bereich $PORT_RANGE_START-$PORT_RANGE_END gefunden" -ForegroundColor Red
            exit 1
        }
    }
}

# Aktualisiere Umgebungsvariable temporär
$env:NEXT_PUBLIC_API_URL = "http://localhost:$selected_port"
Write-Host "Umgebungsvariable gesetzt: NEXT_PUBLIC_API_URL=$env:NEXT_PUBLIC_API_URL" -ForegroundColor Magenta

Write-Host ""
Write-Host "2. Starte Backend-Server auf Port $selected_port..." -ForegroundColor Cyan

# Wechsle ins Backend-Verzeichnis
Set-Location "$PSScriptRoot\backend"

# Starte den Server
Write-Host "Starte: python -m uvicorn app.main:app --host 0.0.0.0 --port $selected_port" -ForegroundColor White
Write-Host "Server läuft auf: http://localhost:$selected_port" -ForegroundColor Green
Write-Host "API Endpoint: http://localhost:$selected_port/api/v1/health" -ForegroundColor Green
Write-Host "WebSocket: ws://localhost:$selected_port/ws/agents" -ForegroundColor Green
Write-Host ""
Write-Host "Drücke Ctrl+C zum Beenden" -ForegroundColor Yellow
Write-Host "=" * 50 -ForegroundColor Green

# Starte den Server
python -m uvicorn app.main:app --host 0.0.0.0 --port $selected_port