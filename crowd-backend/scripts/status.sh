#!/bin/bash
# CrowdVision Status Script
# Usage: ./status.sh

echo "============================================"
echo "       CROWDVISION SYSTEM STATUS"
echo "============================================"
echo ""

# Service status
echo "SERVICE STATUS:"
echo "---------------"

if systemctl is-active --quiet crowdvision 2>/dev/null; then
    echo "  [OK] CrowdVision: RUNNING (systemd)"
    uptime_info=$(systemctl show crowdvision --property=ActiveEnterTimestamp 2>/dev/null | cut -d= -f2)
    echo "       Started: $uptime_info"
elif pgrep -f "uvicorn api.main:app" > /dev/null 2>&1; then
    echo "  [OK] CrowdVision: RUNNING (standalone)"
else
    echo "  [!!] CrowdVision: STOPPED"
fi

if systemctl is-active --quiet mongod 2>/dev/null; then
    echo "  [OK] MongoDB: RUNNING"
else
    echo "  [!!] MongoDB: STOPPED"
fi

echo ""

# Health check
echo "HEALTH CHECK:"
echo "-------------"
response=$(curl -s --max-time 5 http://localhost:8000/api/health 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$response" ]; then
    status=$(echo "$response" | jq -r '.status // "unknown"' 2>/dev/null)

    if [ "$status" = "healthy" ]; then
        echo "  [OK] API Status: $status"
    elif [ "$status" = "degraded" ]; then
        echo "  [!!] API Status: $status"
        issues=$(echo "$response" | jq -r '.issues // [] | join(", ")' 2>/dev/null)
        echo "       Issues: $issues"
    else
        echo "  [!!] API Status: $status"
    fi

    # Database
    db_connected=$(echo "$response" | jq -r '.database.connected // "unknown"' 2>/dev/null)
    if [ "$db_connected" = "true" ]; then
        echo "  [OK] Database: Connected"
    else
        echo "  [!!] Database: Disconnected"
    fi

    # GPU
    gpu_available=$(echo "$response" | jq -r '.gpu.available // "unknown"' 2>/dev/null)
    if [ "$gpu_available" = "true" ]; then
        gpu_mem=$(echo "$response" | jq -r '.gpu.devices[0].memory_percent // "N/A"' 2>/dev/null)
        echo "  [OK] GPU: Available (${gpu_mem}% memory used)"
    else
        echo "  [!!] GPU: Not available"
    fi

    # Streams
    active_streams=$(echo "$response" | jq -r '.streams.active // 0' 2>/dev/null)
    total_streams=$(echo "$response" | jq -r '.streams.total // 0' 2>/dev/null)
    echo "  [--] Streams: $active_streams active / $total_streams total"
else
    echo "  [!!] API: Not responding"
fi

echo ""

# Resource usage
echo "RESOURCE USAGE:"
echo "---------------"
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' 2>/dev/null || echo "N/A")
mem_info=$(free -h | awk '/^Mem:/ {print $3 "/" $2}' 2>/dev/null || echo "N/A")
echo "  CPU: ${cpu_usage}%"
echo "  Memory: $mem_info"

# GPU memory (if nvidia-smi available)
if command -v nvidia-smi &> /dev/null; then
    gpu_mem=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "N/A")
    echo "  GPU Memory: $gpu_mem"
fi

# Disk usage
disk_usage=$(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}' 2>/dev/null || echo "N/A")
echo "  Disk: $disk_usage"

echo ""

# Recent logs
echo "RECENT LOG ENTRIES:"
echo "-------------------"
if [ -f "/var/log/crowdvision/app.log" ]; then
    tail -5 /var/log/crowdvision/app.log 2>/dev/null || echo "  (unable to read logs)"
elif systemctl is-active --quiet crowdvision 2>/dev/null; then
    journalctl -u crowdvision -n 5 --no-pager 2>/dev/null || echo "  (unable to read logs)"
else
    echo "  (no log file configured)"
fi

echo ""
echo "============================================"
