#!/bin/bash
# CrowdVision Restart Script
# Usage: ./restart.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "       RESTARTING CROWDVISION"
echo "============================================"

# Check if running as systemd service
if systemctl is-active --quiet crowdvision 2>/dev/null; then
    echo "Restarting via systemctl..."
    sudo systemctl restart crowdvision
    sleep 3
    sudo systemctl status crowdvision --no-pager
else
    echo "Restarting in standalone mode..."
    "$SCRIPT_DIR/stop.sh"
    sleep 2
    "$SCRIPT_DIR/start.sh"
fi
