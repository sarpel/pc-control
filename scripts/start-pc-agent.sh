#!/bin/bash

# PC Voice Controller - PC Agent Startup Script
# This script starts the PC backend service with proper configuration

set -e  # Exit on any error

# Configuration
PYTHON_MIN_VERSION="3.10"
SERVICE_NAME="pc-agent"
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8765"
CONFIG_DIR="$HOME/.pc-voice-control"
CERT_DIR="$CONFIG_DIR/certificates"
LOG_DIR="$CONFIG_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
check_python() {
    log_info "Checking Python version..."

    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python is not installed. Please install Python $PYTHON_MIN_VERSION or later."
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    if [ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]; then
        log_error "Python $PYTHON_MIN_VERSION or later is required. Found version $PYTHON_VERSION"
        exit 1
    fi

    log_success "Python $PYTHON_VERSION detected"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p "$CERT_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$CONFIG_DIR/backups"

    log_success "Directories created"
}

# Install dependencies
install_dependencies() {
    log_info "Checking dependencies..."

    # Check if we're in a virtual environment
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        log_warning "No virtual environment detected. Creating one..."
        $PYTHON_CMD -m venv "$CONFIG_DIR/venv"
        source "$CONFIG_DIR/venv/bin/activate"
    fi

    # Upgrade pip
    pip install --upgrade pip

    # Install requirements if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        log_info "Installing Python dependencies..."
        pip install -r requirements.txt
    else
        log_warning "requirements.txt not found. Installing basic dependencies..."
        pip install fastapi uvicorn python-multipart websockets python-jose[cryptography] passlib[bcrypt] sqlite3
    fi

    log_success "Dependencies installed"
}

# Generate certificates if they don't exist
check_certificates() {
    log_info "Checking SSL certificates..."

    if [ ! -f "$CERT_DIR/server.crt" ] || [ ! -f "$CERT_DIR/server.key" ]; then
        log_warning "SSL certificates not found. Generating new certificates..."

        # Create certificate generation script
        cat > "$CERT_DIR/generate_certs.py" << 'EOF'
#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from utils.certificate_generator import CertificateGenerator

if __name__ == "__main__":
    generator = CertificateGenerator()
    generator.cert_dir = os.path.dirname(__file__)
    generator.generate_all_certificates()
    print("Certificates generated successfully!")
EOF

        $PYTHON_CMD "$CERT_DIR/generate_certs.py"
        log_success "SSL certificates generated"
    else
        log_success "SSL certificates found"
    fi
}

# Start the service
start_service() {
    log_info "Starting PC Voice Controller service..."

    # Get command line arguments
    HOST=${1:-$DEFAULT_HOST}
    PORT=${2:-$DEFAULT_PORT}

    # Change to the src directory
    cd "src"

    # Set environment variables
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."
    export PC_VOICE_HOST="$HOST"
    export PC_VOICE_PORT="$PORT"
    export PC_VOICE_CONFIG_DIR="$CONFIG_DIR"
    export PC_VOICE_CERT_DIR="$CERT_DIR"

    # Start the service
    log_info "Starting server on $HOST:$PORT"
    log_info "Logs directory: $LOG_DIR"
    log_info "Press Ctrl+C to stop the service"

    exec uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --ssl-keyfile "$CERT_DIR/server.key" \
        --ssl-certfile "$CERT_DIR/server.crt" \
        --log-level info \
        --access-log "$LOG_DIR/access.log" \
        --log-file "$LOG_DIR/server.log"
}

# Main execution
main() {
    echo "PC Voice Controller - PC Agent Startup Script"
    echo "=============================================="

    check_python
    create_directories
    install_dependencies
    check_certificates
    start_service "$@"
}

# Handle signals gracefully
trap 'log_info "Shutting down service..."; exit 0' INT TERM

# Run main function
main "$@"