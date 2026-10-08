#!/usr/bin/env bash
# Auto-detect current active network IP address
PRIMARY_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')

# Fallback to enx00e04c187718 or 10.54.23.55 if routing check fails
if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP=$(ip -4 -o addr show dev enx00e04c187718 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
fi

if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP="10.54.23.55"
fi

echo "Publishing mDNS: crowdvision-dashboard.local -> ${PRIMARY_IP}"
exec /usr/bin/avahi-publish-address -a crowdvision-dashboard.local "${PRIMARY_IP}" -R -f
