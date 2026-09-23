#!/bin/bash

# CrowdVision Production Setup Script (Ubuntu 22.04 LTS Optimized)
#
# This script automates the steps detailed in the Deployment Guide.
# It handles:
# 1. System Dependencies & MongoDB 6.0
# 2. User & Directory Setup
# 3. Python Environment & Dependencies
# 4. Model Downloading
# 5. Nginx & Security
# 6. Service Installation

set -e
APP_DIR="/opt/crowdvision"
USER="crowdvision"
GROUP="crowdvision"
CURRENT_DIR=$(pwd)

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}   CrowdVision Production Setup (Ubuntu)       ${NC}"
echo -e "${BLUE}===============================================${NC}"

if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}Error: Please run as root (sudo ./setup_prod.sh)${NC}"
  exit 1
fi

# -----------------------------------------------------------------------------
# 1. System Dependencies & MongoDB
# -----------------------------------------------------------------------------
echo -e "${GREEN}[1/6] Installing System Dependencies & MongoDB...${NC}"

# Update & Install Basic Deps
apt-get update
apt-get install -y python3-venv python3-pip python3-dev build-essential \
    ffmpeg jq curl unzip gnupg nginx apache2-utils

# Install MongoDB 6.0 (As per guide)
if ! systemctl is-active --quiet mongod; then
    echo "SETTING UP MONGODB 6.0..."
    curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
       sudo gpg --dearmor --yes -o /usr/share/keyrings/mongodb-server-6.0.gpg

    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | \
       sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

    apt-get update
    apt-get install -y mongodb-org
    systemctl enable mongod
    systemctl start mongod
else
    echo "MongoDB is already running."
fi

# -----------------------------------------------------------------------------
# 2. User & Director Setup
# -----------------------------------------------------------------------------
echo -e "${GREEN}[2/6] Setting up User & Directories...${NC}"

if ! id "$USER" &>/dev/null; then
    useradd -r -s /bin/false $USER
    usermod -aG video,render $USER
fi

mkdir -p $APP_DIR
# Copy files if we are not already in target
if [ "$CURRENT_DIR" != "$APP_DIR" ] && [ -d "$CURRENT_DIR/api" ]; then
    echo "Copying project files to $APP_DIR..."
    cp -r ./. $APP_DIR/
fi

# Create all necessary subdirs (logs, data)
mkdir -p /var/log/crowdvision
chown -R $USER:$GROUP /var/log/crowdvision

# -----------------------------------------------------------------------------
# 3. Python Environment
# -----------------------------------------------------------------------------
echo -e "${GREEN}[3/6] Setting up Python Environment...${NC}"
cd $APP_DIR

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}Warning: requirements.txt not found!${NC}"
fi

# -----------------------------------------------------------------------------
# 4. Download Models
# -----------------------------------------------------------------------------
echo -e "${GREEN}[4/6] Downloading Models...${NC}"
if [ -f "scripts/download_models.py" ]; then
    python3 scripts/download_models.py
else
    echo "Download script not found, skipping."
fi

# -----------------------------------------------------------------------------
# 5. Configuration & Nginx
# -----------------------------------------------------------------------------
echo -e "${GREEN}[5/6] Configuration & Nginx...${NC}"

# Production Config
if [ ! -f "config/production.env" ]; then
    echo "Creating production.env from template..."
    cp config/production.env.template config/production.env
fi

# Cameras Config
if [ ! -f "config/cameras.json" ]; then
    echo "Creating empty cameras.json (Update this later!)"
    echo '{ "cameras": [] }' > config/cameras.json
fi

# Nginx Setup
echo "Configuring Nginx..."
AUTH_FILE="/etc/nginx/.htpasswd"
if [ ! -f "$AUTH_FILE" ]; then
    echo -e "${BLUE}>> Enter password for 'admin' user (Basic Auth):${NC}"
    htpasswd -c $AUTH_FILE admin
fi

cp nginx/crowdvision.conf /etc/nginx/sites-available/crowdvision
ln -sf /etc/nginx/sites-available/crowdvision /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# -----------------------------------------------------------------------------
# 6. Service Installation
# -----------------------------------------------------------------------------
echo -e "${GREEN}[6/6] Finalizing Service...${NC}"

# Fix Permissions
chown -R $USER:$GROUP $APP_DIR
chmod +x $APP_DIR/scripts/*.sh

# Install Systemd
cp $APP_DIR/scripts/crowdvision.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable crowdvision
systemctl restart crowdvision

echo -e "${GREEN}SUCCESS! Installation Complete.${NC}"
echo "------------------------------------------------"
echo "Web Interface: http://<server-ip>/"
echo "System Status: sudo systemctl status crowdvision"
echo "Logs:          journalctl -u crowdvision -f"
echo "------------------------------------------------"
