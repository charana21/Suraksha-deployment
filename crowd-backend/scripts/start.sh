#!/bin/bash
# CrowdVision Start Script
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "       STARTING CROWDVISION"
echo "============================================"

# Kill any existing crowdvision processes to prevent GPU memory zombies
echo "Cleaning up any existing processes..."
pkill -9 -f "crowd-backend/venv/bin/python" 2>/dev/null || true
sleep 2

# Check if running as systemd service or standalone
if systemctl is-active --quiet crowdvision 2>/dev/null; then
    echo "CrowdVision is managed by systemd."
    echo "Starting via systemctl..."
    sudo systemctl start crowdvision
    sleep 3
    sudo systemctl status crowdvision --no-pager
else
    echo "Starting CrowdVision in standalone mode..."
    cd "$APP_DIR"

    # Activate virtual environment if exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Load environment variables
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi

    # Optimize PyTorch memory allocation
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

    # Start the server
    python -m uvicorn api.main:app --host 0.0.0.0 --port ${API_PORT:-8000}
fi
