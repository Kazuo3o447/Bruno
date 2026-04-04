# ═══════════════════════════════════════════════════════════
# 🚀 Bruno Trading Bot — Production Deployment (Windows)
# ═══════════════════════════════════════════════════════════

# PowerShell Deployment Script für Windows
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("deploy", "check", "build", "health", "status", "stop", "restart", "logs")]
    [string]$Action = "deploy"
)

# Logging functions
function Log-Info {
    param([string]$Message)
    Write-Host "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] $Message" -ForegroundColor Blue
}

function Log-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Log-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Log-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# Check prerequisites
function Test-Prerequisites {
    Log-Info "Checking prerequisites..."
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Log-Error "Docker is not installed or not in PATH"
    }
    
    # Check Docker Compose
    if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        Log-Error "Docker Compose is not installed or not in PATH"
    }
    
    # Check .env.production
    if (-not (Test-Path ".env.production")) {
        Log-Error ".env.production file not found. Please create it first."
    }
    
    # Check for default passwords
    $envContent = Get-Content ".env.production" -Raw
    if ($envContent -match "CHANGE_ME") {
        Log-Error "Please replace all 'CHANGE_ME' placeholders in .env.production"
    }
    
    Log-Success "Prerequisites check passed"
}

# Security checks
function Test-Security {
    Log-Info "Performing security checks..."
    
    $envContent = Get-Content ".env.production" -Raw
    
    # Check for paper trading mode
    if ($envContent -notmatch "PAPER_TRADING_ONLY=true") {
        Log-Error "PAPER_TRADING_ONLY must be set to true for production"
    }
    
    # Check for dry run mode
    if ($envContent -notmatch "DRY_RUN=true") {
        Log-Error "DRY_RUN must be set to true for production"
    }
    
    # Check for live trading approval
    if ($envContent -match "LIVE_TRADING_APPROVED=true") {
        Log-Error "LIVE_TRADING_APPROVED must be false for initial deployment"
    }
    
    Log-Success "Security checks passed"
}

# Build production images
function Build-Images {
    Log-Info "Building production images..."
    
    # Set environment
    $env:COMPOSE_FILE = "docker-compose.production.yml"
    $env:COMPOSE_PROJECT_NAME = "bruno-prod"
    
    # Load environment variables
    $envLines = Get-Content ".env.production"
    foreach ($line in $envLines) {
        if ($line -and $line -notmatch "^#" -and $line -match "=") {
            $key, $value = $line -split "=", 2
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    
    # Build images
    docker-compose -f docker-compose.production.yml build --no-cache
    
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Docker build failed"
    }
    
    Log-Success "Production images built successfully"
}

# Deploy services
function Deploy-Services {
    Log-Info "Deploying Bruno services..."
    
    # Start database and redis first
    Log-Info "Starting database and Redis..."
    docker-compose -f docker-compose.production.yml up -d postgres redis
    
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Failed to start database services"
    }
    
    # Wait for database to be ready
    Log-Info "Waiting for database to be ready..."
    Start-Sleep -Seconds 30
    
    # Run database migrations
    Log-Info "Running database migrations..."
    docker-compose -f docker-compose.production.yml run --rm api-backend alembic upgrade head
    
    if ($LASTEXITCODE -ne 0) {
        Log-Warning "Database migration failed (may need manual intervention)"
    }
    
    # Start all services
    Log-Info "Starting all services..."
    docker-compose -f docker-compose.production.yml up -d
    
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Failed to start services"
    }
    
    Log-Success "All services deployed successfully"
}

# Health checks
function Test-Health {
    Log-Info "Performing health checks..."
    
    # Wait for services to start
    Start-Sleep -Seconds 30
    
    # Check API health
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Log-Success "API health check passed"
        } else {
            Log-Warning "API health check returned status $($response.StatusCode)"
        }
    } catch {
        Log-Warning "API health check failed: $($_.Exception.Message)"
    }
    
    # Check frontend
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Log-Success "Frontend health check passed"
        } else {
            Log-Warning "Frontend health check returned status $($response.StatusCode)"
        }
    } catch {
        Log-Warning "Frontend health check failed: $($_.Exception.Message)"
    }
    
    # Check API sources
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/systemtest/health/sources" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Log-Success "API sources health check passed"
        } else {
            Log-Warning "API sources health check returned status $($response.StatusCode)"
        }
    } catch {
        Log-Warning "API sources health check failed: $($_.Exception.Message)"
    }
    
    Log-Success "Health checks completed"
}

# Show status
function Show-Status {
    Log-Info "Deployment status:"
    Write-Host ""
    docker-compose -f docker-compose.production.yml ps
    Write-Host ""
    Log-Info "Access URLs:"
    Write-Host "  🌐 Frontend: http://localhost:3000"
    Write-Host "  🔌 API: http://localhost:8000"
    Write-Host "  📊 Metrics: http://localhost:9090"
    Write-Host "  ❤️  Health: http://localhost:8080"
    Write-Host ""
    Log-Info "Useful commands:"
    Write-Host "  📋 View logs: docker-compose -f docker-compose.production.yml logs -f"
    Write-Host "  🔄 Restart: docker-compose -f docker-compose.production.yml restart"
    Write-Host "  🛑 Stop: docker-compose -f docker-compose.production.yml down"
    Write-Host ""
}

# Main deployment function
function Deploy-Bruno {
    Log-Info "Starting Bruno Trading Bot production deployment..."
    Write-Host ""
    
    Test-Prerequisites
    Test-Security
    Build-Images
    Deploy-Services
    Test-Health
    Show-Status
    
    Log-Success "🎉 Bruno Trading Bot deployed successfully!"
    Log-Warning "Remember to:"
    Log-Warning "  1. Monitor the system regularly"
    Log-Warning "  2. Set up backups"
    Log-Warning "  3. Configure monitoring alerts"
    Log-Warning "  4. Keep security updated"
}

# Execute based on action
switch ($Action) {
    "deploy" {
        Deploy-Bruno
    }
    "check" {
        Test-Prerequisites
        Test-Security
    }
    "build" {
        Build-Images
    }
    "health" {
        Test-Health
    }
    "status" {
        Show-Status
    }
    "stop" {
        Log-Info "Stopping Bruno services..."
        docker-compose -f docker-compose.production.yml down
        Log-Success "Services stopped"
    }
    "restart" {
        Log-Info "Restarting Bruno services..."
        docker-compose -f docker-compose.production.yml restart
        Log-Success "Services restarted"
    }
    "logs" {
        docker-compose -f docker-compose.production.yml logs -f
    }
    default {
        Write-Host "Usage: .\deploy.ps1 -Action {deploy|check|build|health|status|stop|restart|logs}"
        exit 1
    }
}
