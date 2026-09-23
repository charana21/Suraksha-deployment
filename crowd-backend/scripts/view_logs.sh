#!/bin/bash
# CrowdVision Log Viewer
# Usage: ./view_logs.sh [lines]
# Example: ./view_logs.sh 100

LINES=${1:-50}
LOG_FILE="/var/log/crowdvision/app.log"

echo "============================================"
echo "       CROWDVISION LOG VIEWER"
echo "============================================"
echo ""
echo "Press Ctrl+C to exit"
echo ""

# Try different log sources
if [ -f "$LOG_FILE" ]; then
    echo "Showing last $LINES lines from $LOG_FILE, then following..."
    echo ""
    tail -n "$LINES" -f "$LOG_FILE"
elif systemctl is-active --quiet crowdvision 2>/dev/null; then
    echo "Showing last $LINES lines from journald, then following..."
    echo ""
    journalctl -u crowdvision -n "$LINES" -f
else
    echo "No log file found at $LOG_FILE"
    echo "CrowdVision service is not running under systemd."
    echo ""
    echo "If running in standalone mode, logs appear in the terminal."
    echo ""
    echo "To enable file logging, set LOG_FILE in your .env file:"
    echo "  LOG_FILE=/var/log/crowdvision/app.log"
fi
