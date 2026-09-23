#!/bin/bash
# CrowdVision Stop Script
# Usage: ./stop.sh

set -e

echo "============================================"
echo "       STOPPING CROWDVISION"
echo "============================================"

# Check if running as systemd service
if systemctl is-active --quiet crowdvision 2>/dev/null; then
    echo "Stopping via systemctl..."
    sudo systemctl stop crowdvision
    echo "CrowdVision stopped."
else
    echo "Looking for running CrowdVision processes..."

    # Find and kill uvicorn processes running our app
    PIDS=$(pgrep -f "uvicorn api.main:app" 2>/dev/null || true)

    if [ -n "$PIDS" ]; then
        echo "Found processes: $PIDS"
        echo "Sending SIGTERM for graceful shutdown..."
        kill -TERM $PIDS 2>/dev/null || true

        # Wait up to 30 seconds for graceful shutdown
        for i in {1..30}; do
            if ! pgrep -f "uvicorn api.main:app" > /dev/null 2>&1; then
                echo "CrowdVision stopped gracefully."
                exit 0
            fi
            sleep 1
        done

        # Force kill if still running
        echo "Graceful shutdown timed out, forcing..."
        kill -9 $PIDS 2>/dev/null || true
        echo "CrowdVision force stopped."
    else
        echo "No CrowdVision processes found."
    fi
fi
