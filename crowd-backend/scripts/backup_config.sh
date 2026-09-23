#!/bin/bash
# CrowdVision Config Backup Script
# Usage: ./backup_config.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "============================================"
echo "       CROWDVISION CONFIG BACKUP"
echo "============================================"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup .env file
if [ -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env" "$BACKUP_DIR/.env.$TIMESTAMP"
    echo "Backed up: .env -> .env.$TIMESTAMP"
fi

# Backup production.env if exists
if [ -f "$APP_DIR/config/production.env" ]; then
    cp "$APP_DIR/config/production.env" "$BACKUP_DIR/production.env.$TIMESTAMP"
    echo "Backed up: production.env -> production.env.$TIMESTAMP"
fi

# Backup cameras.json if exists
if [ -f "$APP_DIR/config/cameras.json" ]; then
    cp "$APP_DIR/config/cameras.json" "$BACKUP_DIR/cameras.json.$TIMESTAMP"
    echo "Backed up: cameras.json -> cameras.json.$TIMESTAMP"
fi

echo ""

# Clean up old backups (keep last 10 of each type)
for pattern in ".env" "production.env" "cameras.json"; do
    count=$(ls -1 "$BACKUP_DIR/$pattern."* 2>/dev/null | wc -l)
    if [ "$count" -gt 10 ]; then
        echo "Cleaning old $pattern backups (keeping last 10)..."
        ls -t "$BACKUP_DIR/$pattern."* | tail -n +11 | xargs -r rm
    fi
done

echo ""
echo "Backups stored in: $BACKUP_DIR"
echo ""

# List current backups
echo "Current backups:"
ls -lt "$BACKUP_DIR" | head -20
