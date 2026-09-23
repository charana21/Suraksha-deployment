#!/bin/bash
# CrowdVision Emergency Reset Script
# Usage: ./emergency_reset.sh
# Use this when the system is unresponsive or in a bad state

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "    CROWDVISION EMERGENCY RESET"
echo "============================================"
echo ""
echo "WARNING: This will forcefully stop all processes"
echo "         and clear temporary data."
echo ""
read -p "Continue? (y/N): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "[1/6] Stopping service..."
if systemctl is-active --quiet crowdvision 2>/dev/null; then
    sudo systemctl stop crowdvision || true
fi

# Force kill any remaining processes
pkill -9 -f "uvicorn api.main:app" 2>/dev/null || true
pkill -9 -f "python.*crowdvision" 2>/dev/null || true
sleep 2

echo "[2/6] Clearing GPU memory..."
if command -v nvidia-smi &> /dev/null; then
    # Kill any stuck GPU processes
    nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | while read pid; do
        if [ -n "$pid" ]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    echo "       GPU processes cleared."
else
    echo "       nvidia-smi not available, skipping."
fi

echo "[3/6] Clearing temporary files..."
rm -rf "$APP_DIR/data/heatmaps/"* 2>/dev/null || true
rm -rf /tmp/crowdvision_* 2>/dev/null || true
rm -rf /tmp/torch_* 2>/dev/null || true
echo "       Temporary files cleared."

echo "[4/6] Checking MongoDB..."
if systemctl is-active --quiet mongod 2>/dev/null; then
    echo "       MongoDB is running."
else
    echo "       MongoDB is stopped. Starting..."
    sudo systemctl start mongod || true
    sleep 3
fi

echo "[5/6] Starting CrowdVision..."
if [ -f /etc/systemd/system/crowdvision.service ]; then
    sudo systemctl start crowdvision
    sleep 5
else
    echo "       No systemd service found."
    echo "       Start manually with: ./start.sh"
fi

echo "[6/6] Verifying health..."
sleep 5
"$SCRIPT_DIR/health_check.sh" || true

echo ""
echo "============================================"
echo "    EMERGENCY RESET COMPLETE"
echo "============================================"
echo ""
echo "Run ./status.sh to check system status."
