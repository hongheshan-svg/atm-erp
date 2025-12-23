#!/bin/bash
#
# ERP System Docker Management Script
# Usage: ./scripts/docker-manage.sh [command]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE} ERP System Docker Manager${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

# Determine docker compose command
get_compose_cmd() {
    if command -v docker compose &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

COMPOSE_CMD=$(get_compose_cmd)

# Setup environment
setup_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from template..."
        cp .env.docker .env
        print_success "Created .env file. Please edit it with your settings."
        echo -e "${YELLOW}Edit the .env file before running 'start' command.${NC}"
    else
        print_success ".env file exists."
    fi
}

# Build images
build() {
    print_header
    echo "Building Docker images..."
    $COMPOSE_CMD build --no-cache
    print_success "Docker images built successfully!"
}

# Start all services
start() {
    print_header
    check_docker
    setup_env
    
    echo "Starting ERP services..."
    $COMPOSE_CMD up -d
    
    echo ""
    print_success "ERP services started successfully!"
    echo ""
    echo -e "${GREEN}Access the application:${NC}"
    echo -e "  Frontend:  http://localhost"
    echo -e "  API:       http://localhost/api/"
    echo -e "  Admin:     http://localhost/admin/"
    echo ""
    echo -e "${YELLOW}Default credentials:${NC}"
    echo -e "  Username:  admin"
    echo -e "  Password:  admin123"
    echo ""
    echo -e "${YELLOW}View logs:${NC} ./scripts/docker-manage.sh logs"
}

# Stop all services
stop() {
    print_header
    echo "Stopping ERP services..."
    $COMPOSE_CMD down
    print_success "ERP services stopped!"
}

# Restart all services
restart() {
    stop
    start
}

# View logs
logs() {
    if [ -z "$2" ]; then
        $COMPOSE_CMD logs -f
    else
        $COMPOSE_CMD logs -f "$2"
    fi
}

# Show service status
status() {
    print_header
    echo "Service Status:"
    echo ""
    $COMPOSE_CMD ps
}

# Execute command in backend container
exec_backend() {
    $COMPOSE_CMD exec backend "$@"
}

# Django management commands
manage() {
    shift
    $COMPOSE_CMD exec backend python manage.py "$@"
}

# Create database backup
backup() {
    print_header
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    echo "Creating database backup: $BACKUP_FILE"
    $COMPOSE_CMD exec postgres pg_dump -U ${DB_USER:-erp_user} ${DB_NAME:-erp_db} > "$BACKUP_FILE"
    print_success "Backup created: $BACKUP_FILE"
}

# Restore database from backup
restore() {
    if [ -z "$2" ]; then
        print_error "Please provide backup file path"
        echo "Usage: ./scripts/docker-manage.sh restore <backup_file.sql>"
        exit 1
    fi
    print_header
    echo "Restoring database from: $2"
    cat "$2" | $COMPOSE_CMD exec -T postgres psql -U ${DB_USER:-erp_user} ${DB_NAME:-erp_db}
    print_success "Database restored!"
}

# Clean up (remove volumes)
clean() {
    print_header
    print_warning "This will remove all containers, networks, and volumes!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $COMPOSE_CMD down -v --rmi local
        print_success "Cleanup complete!"
    else
        echo "Cancelled."
    fi
}

# Show help
show_help() {
    print_header
    echo "Usage: ./scripts/docker-manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start all ERP services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  build       - Build Docker images"
    echo "  status      - Show service status"
    echo "  logs [svc]  - View logs (optionally for specific service)"
    echo "  manage      - Run Django management commands"
    echo "  backup      - Create database backup"
    echo "  restore     - Restore database from backup"
    echo "  clean       - Remove all containers and volumes"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/docker-manage.sh start"
    echo "  ./scripts/docker-manage.sh logs backend"
    echo "  ./scripts/docker-manage.sh manage createsuperuser"
    echo "  ./scripts/docker-manage.sh backup"
}

# Main script
case "${1:-help}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    build)
        build
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    manage)
        manage "$@"
        ;;
    backup)
        backup
        ;;
    restore)
        restore "$@"
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

