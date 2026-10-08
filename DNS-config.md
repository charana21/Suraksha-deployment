# Suraksha CrowdVision — DNS Configuration & Network Setup Guide

**Domain Name:** `crowdvision-dashboard.local` (and `crowdvision-dashboard`)  
**Server IP Address:** `10.54.23.55` (enx00e04c187718) / `192.168.3.199` (eno1)  
**Cluster Ingress:** K3s Kubernetes with Traefik Ingress Controller  
**Status:** Active & Verified 24/7 (via systemd user service)  
**Word Document:** [`DNS-config.docx`](file:///home/user/k3s/Suraksha-deployment/DNS-config.docx)

---

## 1. Executive Summary & Access URLs

To allow team members and stakeholders across the office network to easily access the CrowdVision dashboard without having to memorize or type raw IP addresses, a local network DNS name has been configured.

### Primary Office Access URL (Zero Configuration Required)
> **[http://crowdvision-dashboard.local/](http://crowdvision-dashboard.local/)**  
> *(Also accessible case-insensitively: [http://Crowdvision-dashboard.local/](http://Crowdvision-dashboard.local/))*

* **Compatibility:** Works out of the box across **Windows 10/11**, **macOS**, **Linux**, and **iOS** devices connected to the same office Wi-Fi / Ethernet LAN.
* **Full Stack Support:** Frontend UI, Backend API (`/api`), Swagger Docs (`/docs`), and real-time WebSockets connect automatically under this domain.

---

## 2. How the DNS Was Configured

DNS resolution in a local office network operates differently than public internet domains (`.com`/`.org`). To achieve immediate, frictionless connectivity across team computers without requiring domain purchase or public certificate authorities, we implemented a three-tier architecture:

### Tier 1: Multicast DNS Daemon (Avahi / RFC 6762)
The underlying Ubuntu Linux host runs `avahi-daemon`, which listens on UDP port 5353. Avahi implements mDNS (Zero-Configuration Networking / Bonjour). Any computer on the same local subnet querying for `*.local` domains receives an immediate direct response from Avahi with the host IP.

### Tier 2: Dynamic IP Auto-Detection Wrapper (`publish_mdns.sh`)
Instead of hardcoding a single static IP address that breaks if DHCP reassigns a new IP address upon system reboot, we implemented an automated wrapper script at [`/home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh`](file:///home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh). This script queries the active network routing table (`ip -4 route get 1.1.1.1`) to dynamically detect the server's current IP address and broadcasts it to Avahi.

### Tier 3: Persistent Background Systemd User Service
A systemd service named [`crowdvision-mdns.service`](file:///home/user/.config/systemd/user/crowdvision-mdns.service) was created under `~/.config/systemd/user/`. To guarantee that the broadcast runs 24/7 across server reboots—even when no user is interactively logged in via terminal or desktop—we enabled systemd user lingering (`loginctl enable-linger user`). The service is configured with `Restart=always` to recover automatically from any transient network interruptions.

---

## 3. Exact Commands Used

Below is the complete sequence of commands used to implement, register, and verify the DNS configuration:

### Step 3.1: Created the Dynamic IP Detection Script
**File location:** [`/home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh`](file:///home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh)

```bash
#!/usr/bin/env bash
# Auto-detect current active network IP address
PRIMARY_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')

# Fallback to network adapter if routing check fails
if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP=$(ip -4 -o addr show dev enx00e04c187718 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
fi

if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP="10.54.23.55"
fi

echo "Publishing mDNS: crowdvision-dashboard.local -> ${PRIMARY_IP}"
exec /usr/bin/avahi-publish-address -a crowdvision-dashboard.local "${PRIMARY_IP}" -R -f
```

Made the script executable:
```bash
chmod +x /home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh
```

### Step 3.2: Created the Persistent Systemd User Service
**File location:** [`~/.config/systemd/user/crowdvision-mdns.service`](file:///home/user/.config/systemd/user/crowdvision-mdns.service)

```ini
[Unit]
Description=Avahi mDNS Publisher for crowdvision-dashboard.local (Auto-detects IP)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

### Step 3.3: Enabled Systemd Lingering & Started the Service
```bash
# Enable persistent lingering so background user services run across reboots and logouts
loginctl enable-linger user

# Reload systemd daemon to pick up the new service
systemctl --user daemon-reload

# Enable the service on system startup and start it immediately
systemctl --user enable --now crowdvision-mdns.service

# Verify service status
systemctl --user status crowdvision-mdns.service
```

### Step 3.4: Diagnostic & Verification Commands
```bash
# 1. Resolve host using Name Service Switch (NSS):
getent ahosts crowdvision-dashboard.local
# Output: 10.54.23.55 STREAM crowdvision-dashboard.local

# 2. Ping verification:
ping -c 2 crowdvision-dashboard.local
# Output: 64 bytes from surakshaai (10.54.23.55): icmp_seq=1 ttl=64 time=0.037 ms

# 3. Ingress HTTP verification:
curl -I http://crowdvision-dashboard.local/
# Output: HTTP/1.1 200 OK

# 4. Backend API verification:
curl -s http://crowdvision-dashboard.local/api/health/simple
# Output: {"status":"ok","timestamp":"2026-10-08T..."}
```

---

## 4. Where Was the DNS Name Added in the Code?

> **Architectural Principle:** The DNS name was **deliberately NOT hardcoded** into the application code or frontend JavaScript files.

This design ensures the application remains modular, cloud-native, and production-ready. Here is how each layer automatically handles the new DNS name:

### 1. Kubernetes Traefik Ingress (Catch-All Path Routing)
In [`k3s/stack/base/ingress.yaml`](file:///home/user/k3s/Suraksha-deployment/k3s/stack/base/ingress.yaml) and the deployed cluster Ingress resource, the routing rules do not define a restrictive `host:` property:
```yaml
spec:
  ingressClassName: traefik
  rules:
  - http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: crowdvision-backend
            port:
              name: http
      - path: /
        pathType: Prefix
        backend:
          service:
            name: crowdvision-frontend
            port:
              name: http
```
Because there is no host restriction, Traefik acts as a catch-all router for any incoming `Host` header (`10.54.23.55`, `crowdvision-dashboard.local`, `crowdvision-dashboard`, etc.).

### 2. Frontend API Configuration (Relative Origin Routing)
In [`Crowd_Vision_Frontend/.env`](file:///home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend/.env), the API endpoint is configured as:
```env
VITE_API_URL=/api
```
Because this path is relative (no hardcoded IP or domain prefix), modern web browsers automatically send all API calls to the same origin (`window.location.origin`) that loaded the page. When a user opens `http://crowdvision-dashboard.local/`, the browser automatically routes all API queries to `http://crowdvision-dashboard.local/api/`.

### 3. Dynamic WebSocket Resolution (`websocketService.ts`)
In [`Crowd_Vision_Frontend/src/services/websocketService.ts`](file:///home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend/src/services/websocketService.ts) (lines 17–19):
```typescript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const cleanPath = apiUrl.replace(/\/api$/, '');
return `${protocol}//${window.location.host}${cleanPath}`;
```
The WebSocket service dynamically reads `window.location.host` from the browser runtime. Whether users access via IP, `.local` domain, or custom intranet DNS, WebSockets for live video analytics and crowd counts connect seamlessly without changing code.

---

## 5. If the IP Changes, Will the DNS Be the Same? (YES / NO)

### Direct Answer
1. **DNS Name for Users:** **YES**  
   The URL and DNS name (`http://crowdvision-dashboard.local/`) remains **100% THE SAME** for all colleagues in your office. Users never need to learn a new link.
2. **IP Resolution Under the Hood:** **YES** (Automatically Handled via Script)  
   Because we created the dynamic `publish_mdns.sh` script, when the server restarts or obtains a new IP address via DHCP, the service automatically detects the new IP and broadcasts it under the same DNS name.

### Comparison by Resolution Method

| DNS Method | URL Used | If IP Changes, Same DNS? | Action Required on IP Change |
| :--- | :--- | :--- | :--- |
| **mDNS (Avahi Service)** <br>*(Currently Active)* | `http://crowdvision-dashboard.local/` | **YES** *(Automatic)* | **NONE.** Our dynamic script automatically detects and broadcasts the new IP on startup. |
| **Office Router DNS (A Record)** | `http://crowdvision-dashboard/` | **YES** *(Name stays same)* <br>IP Mapping: Manual | Network Admin updates the A-Record on router OR sets a DHCP Static Reservation. |
| **Client `hosts` file** | `http://crowdvision-dashboard/` | **YES** *(Name stays same)* <br>IP Mapping: Manual | Colleagues must update the IP address line in their local `hosts` file. |

> **Best Practice Recommendation for IT Administration:**  
> Ask your office network administrator to set a **DHCP Static Reservation (MAC Binding)** on the office router for this workstation's MAC address (`00:e0:4c:18:77:18`) to permanently lock IP `10.54.23.55`.

---

## 6. Sharing with Office Colleagues

### Method 1: Instant Access via Browser (No Setup Required)
Send colleagues this link directly in email, Slack, or Teams:
> **`http://crowdvision-dashboard.local/`**

Supported out-of-the-box:
* Windows 10 & Windows 11 (mDNS enabled by default)
* Apple macOS (MacBooks / iMacs via Bonjour)
* Apple iPhones / iPads (Safari & Chrome)
* Linux Desktops (Ubuntu, Fedora, etc. via Avahi)

### Method 2: Using the Short Name (`http://crowdvision-dashboard/`)
If colleagues prefer omitting the `.local` suffix:

#### Option A: Office Router DNS (One-time setup for the entire company)
Your office IT administrator adds an internal DNS entry on the Wi-Fi router / DHCP server:
* **Hostname:** `crowdvision-dashboard`
* **IP Address:** `10.54.23.55`

#### Option B: Individual PC `hosts` File Configuration
For specific computers without router configuration:
1. **Windows:** Open Notepad as Administrator &rarr; Open `C:\Windows\System32\drivers\etc\hosts`  
   Add line: `10.54.23.55    crowdvision-dashboard`
2. **macOS / Linux:** Run `sudo nano /etc/hosts` in Terminal  
   Add line: `10.54.23.55    crowdvision-dashboard`

---

## 7. System Startup & Power-Loss Recovery Configuration

To guarantee that K3s and the CrowdVision application start automatically whenever the workstation powers on or restarts—including recovery after an unexpected power outage—the full startup chain has been configured and verified:

### Auto-Start Status Summary

| Component | Status | How It Starts |
| :--- | :---: | :--- |
| **`k3s.service`** | **`ENABLED`** | Starts automatically on Ubuntu boot (`multi-user.target`) |
| **`mongod.service`** | **`ENABLED`** | Starts automatically on Ubuntu boot |
| **`crowdvision-mdns.service`** | **`ENABLED`** | Starts via systemd user manager with lingering (`Linger=yes`) |
| **K3s Workloads (`crowdvision`)** | **`Running`** | Managed by K8s with `restartPolicy: Always` |
| **Image Pull Policy** | **`Never`** | Instant startup from local cache without needing remote registry |

### Hardware / Power-Cut Recovery (BIOS Setting)
To ensure the HP Z6 G4 Workstation automatically turns back on if electricity is cut and then restored:
1. Turn on the machine and press **F10** during boot to open the HP BIOS Setup.
2. Navigate to: **`Advanced`** &rarr; **`Power Management Options`** &rarr; **`After Power Loss`**.
3. Select: **`Power On`** (or `Previous State`).
4. Press **F10** to Save and Exit.

With this setting enabled, whenever power returns, the computer automatically powers on, boots Ubuntu, starts K3s, and runs the entire application completely unattended.

