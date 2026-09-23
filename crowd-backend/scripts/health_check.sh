#!/bin/bash
# CrowdVision Health Check Script
# Usage: ./health_check.sh
# Exit codes: 0 = healthy, 1 = unhealthy
# Designed for use with monitoring systems and cron jobs

HEALTH_URL="http://localhost:8000/api/health"
LOG_FILE="/var/log/crowdvision/health.log"
TIMEOUT=10

# Fetch health status
response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$HEALTH_URL" 2>/dev/null)
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

timestamp=$(date '+%Y-%m-%d %H:%M:%S')

# Check HTTP response
if [ "$http_code" != "200" ]; then
    msg="[$timestamp] UNHEALTHY: HTTP $http_code - API not responding"
    echo "$msg"
    [ -w "$(dirname "$LOG_FILE")" ] && echo "$msg" >> "$LOG_FILE"
    exit 1
fi

# Parse health status
status=$(echo "$body" | jq -r '.status // "unknown"' 2>/dev/null)
db_connected=$(echo "$body" | jq -r '.database.connected // false' 2>/dev/null)
gpu_available=$(echo "$body" | jq -r '.gpu.available // false' 2>/dev/null)
issues=$(echo "$body" | jq -r '.issues // [] | join(", ")' 2>/dev/null)

# Evaluate health
if [ "$status" = "unhealthy" ]; then
    msg="[$timestamp] UNHEALTHY: status=$status, db=$db_connected, gpu=$gpu_available, issues=$issues"
    echo "$msg"
    [ -w "$(dirname "$LOG_FILE")" ] && echo "$msg" >> "$LOG_FILE"
    exit 1
elif [ "$status" = "degraded" ]; then
    msg="[$timestamp] DEGRADED: status=$status, issues=$issues"
    echo "$msg"
    [ -w "$(dirname "$LOG_FILE")" ] && echo "$msg" >> "$LOG_FILE"
    exit 0  # Still considered "up" for monitoring purposes
else
    msg="[$timestamp] HEALTHY"
    echo "$msg"
    [ -w "$(dirname "$LOG_FILE")" ] && echo "$msg" >> "$LOG_FILE"
    exit 0
fi
