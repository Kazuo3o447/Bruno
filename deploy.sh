#!/bin/bash

# ═══════════════════════════════════════════════════════════
# 🚀 Bruno Trading Bot — Production Deployment Script
# ═══════════════════════════════════════════════════════════

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    # Check .env.production
    if [ ! -f ".env.production" ]; then
        error ".env.production file not found. Please create it first."
    fi
    
    # Check for default passwords
    if grep -q "CHANGE_ME" .env.production; then
        error "Please replace all 'CHANGE_ME' placeholders in .env.production"
    fi
    
    success "Prerequisites check passed"
}

# Security checks
security_check() {
    log "Performing security checks..."
    
    # Check file permissions
    if [ "$(stat -c %a .env.production)" != "600" ]; then
        warning "Setting secure permissions on .env.production"
        chmod 600 .env.production
    fi
    
    # Check for paper trading mode
    if ! grep -q "PAPER_TRADING_ONLY=true" .env.production; then
        error "PAPER_TRADING_ONLY must be set to true for production"
    fi
    
    # Check for dry run mode
    if ! grep -q "DRY_RUN=true" .env.production; then
        error "DRY_RUN must be set to true for production"
    fi
    
    # Check for live trading approval
    if grep -q "LIVE_TRADING_APPROVED=true" .env.production; then
        error "LIVE_TRADING_APPROVED must be false for initial deployment"
    fi
    
    success "Security checks passed"
}

# Build production images
build_images() {
    log "Building production images..."
    
    # Set environment
    export COMPOSE_FILE=docker-compose.production.yml
    export COMPOSE_PROJECT_NAME=bruno-prod
    
    # Load environment variables
    set -a
    source .env.production
    set +a
    
    # Build images
    docker-compose -f docker-compose.production.yml build --no-cache
    
    success "Production images built successfully"
}

# Deploy services
deploy_services() {
    log "Deploying Bruno services..."
    
    # Start database and redis first
    log "Starting database and Redis..."
    docker-compose -f docker-compose.production.yml up -d postgres redis
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    sleep 30
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose -f docker-compose.production.yml run --rm api-backend alembic upgrade head
    
    # Start all services
    log "Starting all services..."
    docker-compose -f docker-compose.production.yml up -d
    
    success "All services deployed successfully"
}

# Health checks
health_check() {
    log "Performing health checks..."
    
    # Wait for services to start
    sleep 30
    
    # Check API health
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        success "API health check passed"
    else
        error "API health check failed"
    fi
    
    # Check frontend
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        success "Frontend health check passed"
    else
        error "Frontend health check failed"
    fi
    
    # Check API sources
    if curl -f http://localhost:8000/api/v1/systemtest/health/sources > /dev/null 2>&1; then
        success "API sources health check passed"
    else
        warning "API sources health check failed (may need more time)"
    fi
    
    success "Health checks completed"
}

# Show status
show_status() {
    log "Deployment status:"
    echo ""
    docker-compose -f docker-compose.production.yml ps
    echo ""
    log "Access URLs:"
    echo "  🌐 Frontend: http://localhost:3000"
    echo "  🔌 API: http://localhost:8000"
    echo "  📊 Metrics: http://localhost:9090"
    echo "  ❤️  Health: http://localhost:8080"
    echo ""
    log "Useful commands:"
    echo "  📋 View logs: docker-compose -f docker-compose.production.yml logs -f"
    echo "  🔄 Restart: docker-compose -f docker-compose.production.yml restart"
    echo "  🛑 Stop: docker-compose -f docker-compose.production.yml down"
    echo ""
}

# Main deployment function
deploy() {
    log "Starting Bruno Trading Bot production deployment..."
    echo ""
    
    check_prerequisites
    security_check
    build_images
    deploy_services
    health_check
    show_status
    
    success "🎉 Bruno Trading Bot deployed successfully!"
    warning "Remember to:"
    warning "  1. Monitor the system regularly"
    warning "  2. Set up backups"
    warning "  3. Configure monitoring alerts"
    warning "  4. Keep security updated"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "check")
        check_prerequisites
        security_check
        ;;
    "build")
        build_images
        ;;
    "health")
        health_check
        ;;
    "status")
        show_status
        ;;
    "stop")
        log "Stopping Bruno services..."
        docker-compose -f docker-compose.production.yml down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting Bruno services..."
        docker-compose -f docker-compose.production.yml restart
        success "Services restarted"
        ;;
    "logs")
        docker-compose -f docker-compose.production.yml logs -f
        ;;
    *)
        echo "Usage: $0 {deploy|check|build|health|status|stop|restart|logs}"
        exit 1
        ;;
esac
