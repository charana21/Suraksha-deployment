# Suraksha CrowdVision: Complete Project Architecture, Deployment Runbook & Automated Operations Guide

**Document Version:** 3.0 (Production Verified — Dual GPU Sharded & Zero-Touch Self-Healing)  
**Classification:** Internal Engineering, Management & Operations Handbook  
**Target Audience:** Executive Leadership, Project Managers, Operations Engineers, Junior Developers & Newcomers  
**Hardware Platform:** HP Z6 G4 Workstation (Intel Xeon Platinum 8260, 128 GB RAM, Dual NVIDIA RTX A4000)  
**Software Platform:** Ubuntu 24.04 LTS, K3s Lightweight Kubernetes, containerd, Traefik, FastAPI, PyTorch/YOLO  

---

## Table of Contents
1. [Executive Summary & Management Overview (Non-IT Friendly)](#1-executive-summary--management-overview-non-it-friendly)
   - 1.1 [What is Suraksha CrowdVision?](#11-what-is-suraksha-crowdvision)
   - 1.2 [Business & Public Safety Value](#12-business--public-safety-value)
   - 1.3 [High-Level Architecture (Visual)](#13-high-level-architecture-visual)
   - 1.4 [Availability & Outage Summary (Past 72-Hour Audit)](#14-availability--outage-summary-past-72-hour-audit)
2. [Workstation Hardware Profile & Infrastructure](#2-workstation-hardware-profile--infrastructure)
   - 2.1 [Hardware Specifications](#21-hardware-specifications)
   - 2.2 [Dual GPU Sharding Architecture (Visual)](#22-dual-gpu-sharding-architecture-visual)
3. [Kubernetes (K3s) & Container Architecture](#3-kubernetes-k3s--container-architecture)
   - 3.1 [K3s Cluster Topology](#31-k3s-cluster-topology)
   - 3.2 [Namespace & Workload Structure](#32-namespace--workload-structure)
   - 3.3 [Ingress Routing & Networking (Visual)](#33-ingress-routing--networking-visual)
4. [Monitoring, Systemd Daemons & In-Memory Analytics](#4-monitoring-systemd-daemons--in-memory-analytics)
   - 4.1 [Overnight Monitoring Daemon (`crowdvision-monitor.service`)](#41-overnight-monitoring-daemon-crowdvision-monitorservice)
   - 4.2 [Zero Local File Logging Policy](#42-zero-local-file-logging-policy)
   - 4.3 [Automated 3-Hour Email Reports & 30-Minute Plots](#43-automated-3-hour-email-reports--30-minute-plots)
   - 4.4 [Downtime & Outage History Tracker](#44-downtime--outage-history-tracker)
   - 4.5 [Camera Freeze & Stream Stall Tracker](#45-camera-freeze--stream-stall-tracker)
   - 4.6 [Monitoring Sequence Diagram](#46-monitoring-sequence-diagram)
5. [Autonomous Freeze Recovery & Zero-Touch Self-Healing Blueprint](#5-autonomous-freeze-recovery--zero-touch-self-healing-blueprint)
   - 5.1 [The Unattended Operation Challenge](#51-the-unattended-operation-challenge)
   - 5.2 [Tier 1: Application & Container Self-Healing](#52-tier-1-application--container-self-healing)
   - 5.3 [Tier 2: Operating System Automatic Panic & Reboot](#53-tier-2-operating-system-automatic-panic--reboot)
   - 5.4 [Tier 3: HP Hardware Power Recovery & Intel AMT Remote Reset](#54-tier-3-hp-hardware-power-recovery--intel-amt-remote-reset)
   - 5.5 [Self-Healing State Diagram](#55-self-healing-state-diagram)
6. [Step-by-Step Operations Guide for Juniors & Newcomers](#6-step-by-step-operations-guide-for-juniors--newcomers)
   - 6.1 [Daily System Health Verification (5-Minute Routine)](#61-daily-system-health-verification-5-minute-routine)
   - 6.2 [How to Deploy Backend Code Changes](#62-how-to-deploy-backend-code-changes)
   - 6.3 [How to Deploy Frontend Code Changes](#63-how-to-deploy-frontend-code-changes)
   - 6.4 [How to Update Configuration & Secrets](#64-how-to-update-configuration--secrets)
   - 6.5 [How to Safely Restart Services](#65-how-to-safely-restart-services)
7. [Troubleshooting Playbooks & Emergency Runbook](#7-troubleshooting-playbooks--emergency-runbook)
   - 7.1 [Playbook A: Camera Stream Frozen / Stalling](#71-playbook-a-camera-stream-frozen--stalling)
   - 7.2 [Playbook B: GPU Overheating & Thermal Throttling (98°C)](#72-playbook-b-gpu-overheating--thermal-throttling-98c)
   - 7.3 [Playbook C: Kubernetes Pod in CrashLoopBackOff](#73-playbook-c-kubernetes-pod-in-crashloopbackoff)
   - 7.4 [Playbook D: System Recovery After Extended Facility Power Cut](#74-playbook-d-system-recovery-after-extended-facility-power-cut)
   - 7.5 [Playbook E: Hardware MCE Memory Error (RAM Repair)](#75-playbook-e-hardware-mce-memory-error-ram-repair)
8. [Quick Reference Cheatsheet](#8-quick-reference-cheatsheet)

---

## 1. Executive Summary & Management Overview (Non-IT Friendly)

### 1.1 What is Suraksha CrowdVision?
**Suraksha CrowdVision** is an enterprise-grade Edge AI safety and crowd density analytics platform designed for major Indian Railway stations (currently operational at Hyderabad and Kazipet stations). 

The platform continuously digests **28 live high-definition CCTV RTSP camera streams** placed along Foot-Over-Bridges (FOBs), concourses, ticket booking offices, platform waiting halls, and staircases. Using state-of-the-art computer vision models (YOLOv8 + PET Density Estimator), it transforms raw video footage into actionable crowd intelligence, density heatmaps, and automated stampede warning alerts.

```mermaid
flowchart LR
    A["28 CCTV Cameras<br/>(Railway Station RTSP)"] --> B["HP Z6 G4 Workstation<br/>(Dual NVIDIA GPUs)"]
    B --> C["Suraksha AI Engine<br/>(YOLOv8 + PET Fusion)"]
    C --> D["Station Control Dashboard<br/>(Live Heatmaps & Counts)"]
    C --> E["Automated Alerts<br/>(Audio & Visual Warnings)"]
    C --> F["3-Hour Executive Email Reports<br/>(Availability & Health)"]
```

### 1.2 Business & Public Safety Value
* **Stampede Prevention:** Identifies dangerous crowd buildup on narrow foot-over-bridges and stairwells before critical mass is reached.
* **Autonomous Operations:** Eliminates the need for 24/7 manual CCTV monitor viewing. The AI triggers alarms when safety thresholds are breached.
* **Evidence & Analytics:** Aggregates footfall trends, peak-hour bottlenecks, and station occupancy curves for railway management planning.
* **Edge Resilience:** Runs entirely on-premise on local station hardware without relying on cloud internet connectivity for core safety processing.

### 1.3 High-Level Architecture (Visual)
The following diagram illustrates how video streams, hardware resources, microservices, and user interfaces connect together:

```mermaid
flowchart TD
    subgraph Station_Field ["Railway Station Field Ingestion"]
        CAMS_S0["14 Cameras: Group A<br/>(Platform 1, FOB, Booking Gate)"]
        CAMS_S1["14 Cameras: Group B<br/>(Platform 2-10, Center FOB, Parking)"]
    end

    subgraph Hardware_Edge ["HP Z6 G4 Edge Workstation (Ubuntu 24.04)"]
        subgraph GPU_Pool ["NVIDIA Hardware Compute"]
            GPU0["NVIDIA RTX A4000 (GPU 0)<br/>16 GB GDDR6 ECC"]
            GPU1["NVIDIA RTX A4000 (GPU 1)<br/>16 GB GDDR6 ECC"]
        end

        subgraph K3s_Workloads ["K3s Kubernetes Cluster"]
            TRAEFIK["Traefik Ingress Gateway<br/>(Port 80 / 443)"]
            BACKEND0["crowdvision-backend-0<br/>(Shard 0: 14 Streams)"]
            BACKEND1["crowdvision-backend-1<br/>(Shard 1: 14 Streams)"]
            FRONTEND["crowdvision-frontend<br/>(React Web Dashboard)"]
            MEDIAMTX["MediaMTX Gateway<br/>(WebRTC / HLS Streamer)"]
        end

        subgraph Background_Daemons ["Host OS Daemons"]
            MONITOR["crowdvision-monitor.service<br/>(In-Memory Reporter & Outage Tracker)"]
        end
    end

    subgraph Management_Clients ["Station Operations & Management"]
        WEB_USER["Railway Station Master / RPF<br/>(Web Browser Interface)"]
        EXEC_MAIL["Executive Leadership & Tech Team<br/>(Automated 3-Hour Email Reports)"]
    end

    CAMS_S0 --> BACKEND0
    CAMS_S1 --> BACKEND1
    BACKEND0 --> GPU0
    BACKEND1 --> GPU1
    TRAEFIK --> FRONTEND
    TRAEFIK --> BACKEND0
    TRAEFIK --> BACKEND1
    TRAEFIK --> MEDIAMTX
    WEB_USER --> TRAEFIK
    MONITOR --> EXEC_MAIL
```

### 1.4 Availability & Outage Summary (Past 72-Hour Audit)
An exhaustive forensic analysis of the host operating system, Kubernetes workloads, and systemd journals across the past 72 hours revealed the following system uptime and downtime metrics:

| Metric | Duration | Percentage | Management Note |
| :--- | :--- | :--- | :--- |
| **Total Reporting Window** | **72 hours (259,200 s)** | **100.0%** | Audit window: 09 Oct 10:02 to 12 Oct 10:02 |
| **System Running (Uptime)** | **47 hours 43 mins** | **66.28%** | Total time the AI was actively computing |
| **System Offline (Downtime)** | **24 hours 17 mins** | **33.72%** | Lost across 5 ungraceful power loss incidents |
| **Power Cuts / Sudden Drops** | **5 Occurrences** | N/A | None were manual shutdowns; all were abrupt cuts |

#### Breakdown of the 5 Outage Incidents:
1. **Incident #1 (Friday Afternoon):** Fri 09 Oct, 14:45 &rarr; 17:29 (**Down: 2h 45m**).
2. **Incident #2 (Friday Overnight):** Fri 09 Oct, 21:58 &rarr; Sat 10 Oct, 08:07 (**Down: 10h 08m** — station power cut overnight).
3. **Incident #3 (Sunday Morning):** Sun 11 Oct, 07:25 &rarr; 10:40 (**Down: 3h 14m**).
4. **Incident #4 (Sunday Afternoon):** Sun 11 Oct, 11:38 &rarr; 19:36 (**Down: 7h 58m** — extended weekend power outage).
5. **Incident #5 (Monday Morning):** Mon 12 Oct, 09:42 &rarr; 09:53 (**Down: 11m** — system hard freeze & reboot).

---

## 2. Workstation Hardware Profile & Infrastructure

### 2.1 Hardware Specifications
The workstation deployed at the edge station is an enterprise **HP Z6 G4 Workstation** designed for continuous heavy compute:

* **Host Machine:** HP Z6 G4 Workstation (Chassis: Tower/Desktop, Firmware: P60 v02.96).
* **CPU:** Intel(R) Xeon(R) Platinum 8260 CPU @ 2.40 GHz (24 Physical Cores / 48 vCPUs, 35.75 MB Cache).
* **System RAM:** 128 GB DDR4 2933 MHz ECC (125 GiB usable).
* **Primary Storage:** 1 TB NVMe SSD (`/dev/sda2`, 264 GB used, 570 GB free / 32% used).
* **Network Interfaces:** Dual Intel Gigabit Ethernet NICs (Local IP: `10.54.23.55`).
* **GPU 0:** NVIDIA RTX A4000 (16 GB GDDR6 ECC, Bus ID: `0000:21:00.0`, Driver 580.178.04, CUDA 13.0).
* **GPU 1:** NVIDIA RTX A4000 (16 GB GDDR6 ECC, Bus ID: `0000:2D:00.0`, Driver 580.178.04, CUDA 13.0).

### 2.2 Dual GPU Sharding Architecture (Visual)
Processing 28 simultaneous HD video feeds on a single GPU would exceed PCIe bandwidth and VRAM limits. The workload is partitioned symmetrically into **two shards**:

```mermaid
flowchart TD
    subgraph Stream_Ingestion ["28 Ingested RTSP Video Streams"]
        S0_CAMS["Shard 0 Fleet (14 Cameras)<br/>cam_middle_fob_4_5, cam_pf1_fob_hyb_end, cam_kzj_pf1_fob_kzj,<br/>cam_kzj_pf1_fob_pf10, cam_hyb_pf1_a, cam_hyb_booking, etc."]
        S1_CAMS["Shard 1 Fleet (14 Cameras)<br/>cam_mid_fob_pf1, cam_mid_fob_center, cam_hyb_pf1, cam_hyb_pf2,<br/>cam_hyb_pf4, cam_hyb_pf10, cam_pf2_fc_hyd_side, etc."]
    end

    subgraph K3s_Pod_Binding ["K8s StatefulSet Sharding"]
        POD0["crowdvision-backend-0<br/>Index: 0 | CPU Limit: 17 Cores | RAM Limit: 24 GiB"]
        POD1["crowdvision-backend-1<br/>Index: 1 | CPU Limit: 17 Cores | RAM Limit: 24 GiB"]
    end

    subgraph GPU_Hardware ["Dedicated GPU Acceleration"]
        GPU0["GPU 0: NVIDIA RTX A4000<br/>VRAM Used: ~13.6 GiB / 16 GiB"]
        GPU1["GPU 1: NVIDIA RTX A4000<br/>VRAM Used: ~12.8 GiB / 16 GiB"]
    end

    S0_CAMS --> POD0
    S1_CAMS --> POD1
    POD0 -->|NVIDIA Container Runtime| GPU0
    POD1 -->|NVIDIA Container Runtime| GPU1
```

---

## 3. Kubernetes (K3s) & Container Architecture

### 3.1 K3s Cluster Topology
The workstation runs **K3s (v1.36.4+k3s1)**, an ultra-lightweight, production-grade Kubernetes distribution optimized for edge environments.
* **Master/Node:** Single-node control-plane and worker (`surakshaai`).
* **Container Runtime:** `containerd` with `nvidia-container-runtime` integration (`RuntimeClass: nvidia`).
* **Network CNI:** Flannel (Pod CIDR: `10.42.0.0/16`, Service CIDR: `10.43.0.0/16`).
* **Ingress Controller:** Traefik Ingress Controller built-in.

### 3.2 Namespace & Workload Structure
All Suraksha services reside within the `crowdvision` namespace:

| Workload Name | Type | Replicas | GPU Assigned | Role |
| :--- | :--- | :--- | :--- | :--- |
| **`crowdvision-backend`** | `StatefulSet` | 2 (`backend-0`, `backend-1`) | 1 GPU each | Video stream ingestion, YOLOv8/PET AI inference, MongoDB sync |
| **`crowdvision-frontend`** | `Deployment` | 1 | None | Nginx serving React/Vite dashboard, live camera grid, heatmap views |
| **`mediamtx`** | `Deployment` | 1 | None | Low-latency RTSP-to-WebRTC/HLS video streaming proxy |
| **`crowdvision-data`** | `PVC` | 1 (HostPath) | N/A | Persistent storage for model weights (`yolov8m.pt`), homography JSONs |

### 3.3 Ingress Routing & Networking (Visual)
All external HTTP/WebSocket requests on port 80/443 enter through the Traefik Ingress controller and route internally:

```mermaid
flowchart LR
    CLIENT["Browser Client / Station Staff<br/>http://10.54.23.55"] --> TRAEFIK["Traefik Ingress Controller<br/>(Port 80)"]

    TRAEFIK -->|"Path: /api/*"| SVC_BACKEND["crowdvision-backend (Service: Port 8000)"]
    TRAEFIK -->|"Path: /docs or /openapi.json"| SVC_BACKEND
    TRAEFIK -->|"Path: /"| SVC_FRONTEND["crowdvision-frontend (Service: Port 80)"]
    TRAEFIK -->|"Path: /live/*"| SVC_MEDIAMTX["mediamtx (Service: Port 8554 / 8889)"]

    SVC_BACKEND --> POD0["crowdvision-backend-0"]
    SVC_BACKEND --> POD1["crowdvision-backend-1"]
```

---

## 4. Monitoring, Systemd Daemons & In-Memory Analytics

### 4.1 Overnight Monitoring Daemon (`crowdvision-monitor.service`)
To ensure reliable 24/7 visibility into system health, a dedicated systemd service runs continuously:
* **Service Name:** `crowdvision-monitor.service`
* **Source Script:** `/home/user/Downloads/overnight_monitor.py`
* **Systemd Configuration:** `/etc/systemd/system/crowdvision-monitor.service`
* **Restart Policy:** `Restart=always`, `RestartSec=10`

### 4.2 Zero Local File Logging Policy
Edge machines with NVMe/SSD storage are prone to disk exhaustion when running continuous high-frequency video analytics. The monitoring daemon enforces a strict **Zero Local File Logging Policy**:
1. It does **not** append logs to text files, CSVs, or local disk tables.
2. All metrics, reconnect events, GPU readings, and camera statuses are kept in RAM using **fixed-length rolling ring buffers** (`collections.deque(maxlen=MAX_SAMPLES)`).
3. Graphs and visual charts are generated strictly in RAM using `io.BytesIO()` and transmitted via email.

### 4.3 Automated 3-Hour Email Reports & 30-Minute Plots
Every **3 hours** (and after a 30-second initial boot verification), the daemon compiles and dispatches a comprehensive HTML email report to management and engineering (`saicharananandapu@tridemobility.com`):
* **30-Minute Interval Charts:** 4-panel graph visualizing CPU/RAM usage, dual GPU temperatures, GPU compute engine utilization, and active stream stability.
* **30-Minute Interval Table:** Summarizes average and peak CPU, RAM, GPU temperatures, active streams, and stream freeze duration.
* **Offline / Attention Cameras Table:** Highlights cameras experiencing connection drops.

### 4.4 Downtime & Outage History Tracker
The monitoring daemon inspects persistent systemd boot records (`journalctl --list-boots`) and calculates:
* **Host Machine Boot Uptime:** Exact time elapsed since the server powered on.
* **Last Power Outage / Down Time:** Duration and timestamps of the most recent power cut.
* **72-Hour System Availability:** Percentage of uptime vs. downtime and complete audit table of all power drops.

### 4.5 Camera Freeze & Stream Stall Tracker
In [`rtsp_worker.py`](file:///home/user/k3s/Suraksha-deployment/crowd-backend/services/rtsp_worker.py#L1010-L1025), when no video frames arrive for 15 seconds, a stream stall event is triggered:
* The monitor starts an active stall timer for that camera.
* When frames resume, the stall duration is calculated and added to the camera's cumulative freeze total.
* The email report ranks cameras by freeze duration, displaying total frozen hours/minutes and active stall status.

### 4.6 Monitoring Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    participant K8S as K3s Backend Pods
    participant MON as Overnight Monitor Daemon
    participant SYS as Linux Kernel & journalctl
    participant GPU as NVIDIA SMI Driver
    participant SMTP as Google SMTP Gateway
    participant MGT as Management Mailbox

    loop Every 15 Seconds
        MON->>GPU: Query Temperature, Util, VRAM
        MON->>K8S: Parse in-memory logs (RTSP Frame count & Disconnects)
        MON->>MON: Update RAM Ring Buffer & Active Freeze Timers
    end

    loop Every 30 Seconds
        MON->>K8S: Poll Pod Readiness & Restart Counts
    end

    loop Every 3 Hours
        MON->>SYS: Query journalctl --list-boots (Outages & Downtimes)
        MON->>MON: Aggregate 30-minute metric buckets
        MON->>MON: Render 4-Panel PNG Plot in Memory (BytesIO)
        MON->>MON: Compose HTML Email (Outage Table + Freeze Breakdown + Graphs)
        MON->>SMTP: Dispatch Report over TLS (Port 587)
        SMTP->>MGT: Deliver Report to saicharananandapu@tridemobility.com
    end
```

---

## 5. Autonomous Freeze Recovery & Zero-Touch Self-Healing Blueprint

### 5.1 The Unattended Operation Challenge
Because the workstation is deployed remotely in a railway server room without dedicated local IT personnel:
* **Physical restarts are impossible** during night hours or weekends.
* The system must detect its own freezes and automatically restore operations without human intervention.

### 5.2 Tier 1: Application & Container Self-Healing
When individual camera pipelines or Python processes freeze while the host OS remains alive:
1. **Liveness Probe Stalled Detection:** Kubernetes continuously probes `/api/health`. If frame processing stalls for >90 seconds, K3s marks the pod unready, terminates the container, and starts a clean instance.
2. **OpenCV Socket Timeout:** FFmpeg environment variable `OPENCV_FFMPEG_CAPTURE_OPTIONS="stimeout=5000000"` ensures network reads abort after 5 seconds of silence, preventing C++ thread deadlocks.
3. **In-Process Worker Watchdog:** Worker heartbeat timestamps are checked; if any thread hangs, it is terminated and respawned dynamically.

### 5.3 Tier 2: Operating System Automatic Panic & Reboot
If a GPU driver locks up or the kernel experiences a hard freeze:
* Configure `/etc/sysctl.d/99-auto-reboot.conf`:
  ```ini
  kernel.panic = 10
  kernel.hung_task_panic = 1
  kernel.hung_task_timeout_secs = 120
  kernel.panic_on_oops = 1
  ```
* **Effect:** If any kernel task is frozen for more than 120 seconds, the kernel triggers a panic and **reboots the machine automatically after 10 seconds**.
* **Hardware Watchdog:** Systemd hardware watchdog (`RuntimeWatchdogSec=30` in `/etc/systemd/system.conf`) forces a motherboard power reset if the OS stops responding for 30 seconds.

### 5.4 Tier 3: HP Hardware Power Recovery & Intel AMT Remote Reset
When facility power cuts occur:
1. **BIOS "After Power Loss: Power On":**
   * In HP BIOS Setup (`F10` at boot) &rarr; **Advanced** &rarr; **Power-On Options** &rarr; **After Power Loss** &rarr; set to **`Power On`**.
   * **Result:** The moment station electricity returns, the machine powers on immediately without requiring anyone to press the physical power button.
2. **Intel AMT / vPro (Out-Of-Band Remote Reset):**
   * The HP Z6 G4 motherboard includes Intel AMT on its primary Ethernet port.
   * Remote engineers can access `https://10.54.23.55:16993` to execute a cold hardware reboot or view the BIOS console over the network, even if the OS is completely non-functional.
3. **Smart Ping Watchdog PDU:**
   * An optional network-managed smart plug continuously pings the workstation IP. If pings fail for 5 consecutive minutes, the PDU cycles outlet power automatically.

### 5.5 Self-Healing State Diagram
```mermaid
stateDiagram-v2
    [*] --> Normal_Operation: System Boot & Pods Running

    state Normal_Operation {
        [*] --> Ingesting_Streams
        Ingesting_Streams --> AI_Inference: Frames Arriving
        AI_Inference --> Ingesting_Streams: Heatmaps Published
    }

    Normal_Operation --> Camera_Stall: Camera Silent >15s
    state Camera_Stall {
        [*] --> Increment_Stall_Timer
        Increment_Stall_Timer --> Attempt_RTSP_Reconnect: Exponential Backoff
        Attempt_RTSP_Reconnect --> [*]: Connection Restored
    }
    Camera_Stall --> Normal_Operation: Video Restored

    Normal_Operation --> Container_Freeze: Python Event Loop Deadlocked
    state Container_Freeze {
        [*] --> Liveness_Probe_Fails
        Liveness_Probe_Fails --> K8s_Kills_Pod: 5 Failures (150s)
        K8s_Kills_Pod --> K8s_Restarts_Pod: Container Restarted
    }
    Container_Freeze --> Normal_Operation: Pod Returns Ready (HTTP 200)

    Normal_Operation --> OS_Hard_Freeze: GPU / RAM Hardware Lockup
    state OS_Hard_Freeze {
        [*] --> Kernel_Hung_Task_Timer: >120s Freeze
        Kernel_Hung_Task_Timer --> Kernel_Panic_Reboot: sysctl panic=10
        Kernel_Panic_Reboot --> [*]: Motherboard Power Cycles
    }
    OS_Hard_Freeze --> Normal_Operation: System Reboots (K3s Autostarts)

    Normal_Operation --> Station_Power_Cut: Facility Mains Power Fails
    state Station_Power_Cut {
        [*] --> System_Unpowered
        System_Unpowered --> Power_Restored: Mains Returns
        Power_Restored --> HP_BIOS_Auto_Boot: BIOS 'After Power Loss: Power On'
    }
    Station_Power_Cut --> Normal_Operation: Automatic Boot Complete (<60s)
```

---

## 6. Step-by-Step Operations Guide for Juniors & Newcomers

> [!NOTE]
> This section is written specifically so that any newcomer or junior engineer can maintain, update, and deploy changes to the system without requiring senior developer supervision.

### 6.1 Daily System Health Verification (5-Minute Routine)
Run these commands in terminal from `/home/user/k3s/Suraksha-deployment`:

```bash
# 1. Check K3s Node Status (Must show Ready)
kubectl get nodes

# 2. Check All Running Pods (All crowdvision pods must be 1/1 Running)
kubectl get pods -n crowdvision

# 3. Check Dual GPU Status & Temperatures (GPU 0 and GPU 1 must be visible)
nvidia-smi

# 4. Check Overnight Monitor Daemon Status
systemctl status crowdvision-monitor.service --no-pager

# 5. Check Recent System Outages & Downtimes
python3 -c "import sys; sys.path.insert(0, '/home/user/Downloads'); import overnight_monitor as om; print(om.get_system_downtime_summary(24)['total_downtime_str'])"
```

---

### 6.2 How to Deploy Backend Code Changes
When you make changes to backend Python files in `/home/user/k3s/Suraksha-deployment/crowd-backend`:

#### Step 1: Verify Code & Environment
```bash
cd /home/user/k3s/Suraksha-deployment/crowd-backend

# Check git status to ensure you know what files were modified
git status
```

#### Step 2: Build the New Docker Image
```bash
# Build the local backend image
docker build -t crowdvision-backend:local .
```

#### Step 3: Import Image into K3s containerd
Because K3s uses containerd (not Docker) as its internal container runtime, you must import the newly built Docker image:
```bash
docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -
```

#### Step 4: Restart the Backend StatefulSet
```bash
# Trigger rolling restart of both backend-0 and backend-1
kubectl rollout restart statefulset/crowdvision-backend -n crowdvision

# Monitor the rollout status until complete
kubectl rollout status statefulset/crowdvision-backend -n crowdvision
```

#### Step 5: Verify Backend Logs
```bash
# Tail logs from backend-0 to ensure cameras and YOLO models initialized cleanly
kubectl logs crowdvision-backend-0 -n crowdvision -f --tail=50
```

---

### 6.3 How to Deploy Frontend Code Changes
When you make changes to UI, React, or CSS files in `/home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend`:

#### Step 1: Build the New Frontend Image
```bash
cd /home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend

docker build \
  --build-arg "VITE_API_URL=/api" \
  -t crowdvision-frontend:local .
```

#### Step 2: Import into K3s containerd
```bash
docker save crowdvision-frontend:local | sudo k3s ctr -n k8s.io images import -
```

#### Step 3: Restart the Frontend Deployment
```bash
kubectl rollout restart deployment/crowdvision-frontend -n crowdvision
kubectl rollout status deployment/crowdvision-frontend -n crowdvision
```

#### Step 4: Verify in Browser
Open `http://10.54.23.55` in your browser. Perform a hard refresh (`Ctrl + Shift + R`) to clear browser cache and verify UI updates.

---

### 6.4 How to Update Configuration & Secrets

#### To update configuration settings (FPS, thresholds, model paths):
1. Open [`k3s/configmap.yaml`](file:///home/user/k3s/Suraksha-deployment/k3s/configmap.yaml):
   ```bash
   nano /home/user/k3s/Suraksha-deployment/k3s/configmap.yaml
   ```
2. Apply the updated ConfigMap:
   ```bash
   kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/configmap.yaml
   ```
3. Restart the backend to apply changes:
   ```bash
   kubectl rollout restart statefulset/crowdvision-backend -n crowdvision
   ```

#### To update database passwords or camera RTSP credentials:
1. Update `.env` in `crowd-backend/.env`.
2. Re-create the Kubernetes Secret:
   ```bash
   kubectl -n crowdvision create secret generic crowdvision-secrets \
     --from-env-file=/home/user/k3s/Suraksha-deployment/crowd-backend/.env \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
3. Restart the backend pods to consume the new secret.

---

### 6.5 How to Safely Restart Services

| Objective | Command | Downtime |
| :--- | :--- | :--- |
| **Restart Backend Only** | `kubectl rollout restart statefulset/crowdvision-backend -n crowdvision` | ~15 seconds (Rolling) |
| **Restart Frontend Only** | `kubectl rollout restart deployment/crowdvision-frontend -n crowdvision` | ~5 seconds |
| **Restart Video Proxy (MediaMTX)** | `kubectl rollout restart deployment/mediamtx -n crowdvision` | ~5 seconds |
| **Restart Monitoring Daemon** | `pkill -f overnight_monitor.py` *(systemd auto-restarts within 10s)* | 0s (Pods unaffected) |
| **Restart Entire K3s Engine** | `sudo systemctl restart k3s.service` | ~30 seconds |
| **Reboot Host Workstation** | `sudo reboot` | ~90 seconds |

---

## 7. Troubleshooting Playbooks & Emergency Runbook

### 7.1 Playbook A: Camera Stream Frozen / Stalling
**Symptom:** Monitor email reports *Stream Stall (>15s frame starvation)* or camera shows frozen picture in UI.
1. Check the offending camera ID in monitor email (e.g., `cam_hyb_pf1_a`).
2. Test RTSP connectivity from terminal using FFmpeg:
   ```bash
   ffprobe -v error -show_entries stream=width,height,avg_frame_rate "rtsp://username:password@camera-ip:554/stream"
   ```
3. If `ffprobe` hangs or times out: The camera or station network switch port is offline. Contact station electrical/CCTV maintenance to check camera power.
4. If `ffprobe` works cleanly: Restart the specific backend pod managing that camera:
   ```bash
   # If camera is on Shard 0:
   kubectl delete pod crowdvision-backend-0 -n crowdvision
   # If camera is on Shard 1:
   kubectl delete pod crowdvision-backend-1 -n crowdvision
   ```
   *StatefulSet will automatically recreate the pod within 10 seconds.*

---

### 7.2 Playbook B: GPU Overheating & Thermal Throttling (98°C)
**Symptom:** Monitor report warns *GPU 0 Critical Overheat (98°C)*; system experiences slowdowns or sudden hard resets.
1. Inspect live temperature and fan speeds:
   ```bash
   nvidia-smi -q -d TEMPERATURE,FAN,PERFORMANCE
   ```
2. **Immediate Action (Physical Maintenance):**
   * Inspect the front air intake dust filter of the HP Z6 G4 Workstation. Clean all accumulated dust.
   * Verify that the internal blower fan on GPU 0 (PCIe Slot 1) is spinning freely and not blocked by power cables.
   * Ensure the server room air conditioning is operational (ambient room temp should be 20°C–24°C).
3. **Software Throttle Mitigation:** If physical access is delayed, reduce inference load temporarily:
   * Edit [`k3s/configmap.yaml`](file:///home/user/k3s/Suraksha-deployment/k3s/configmap.yaml): change `PET_INFERENCE_INTERVAL` from `"3"` to `"6"`.
   * Apply changes: `kubectl apply -f k3s/configmap.yaml && kubectl rollout restart statefulset/crowdvision-backend -n crowdvision`.

---

### 7.3 Playbook C: Kubernetes Pod in CrashLoopBackOff
**Symptom:** `kubectl get pods -n crowdvision` shows `CrashLoopBackOff` or `Error`.
1. Inspect the pod's failure logs:
   ```bash
   kubectl logs <pod-name> -n crowdvision --previous --tail=100
   ```
2. Inspect pod Kubernetes events:
   ```bash
   kubectl describe pod <pod-name> -n crowdvision | tail -n 30
   ```
3. **Common Causes:**
   * **Missing weights:** Ensure `/app/data/weights/yolov8m.pt` exists on the host disk.
   * **GPU Allocation Error (`Insufficient nvidia.com/gpu`):** NVIDIA Device Plugin may have restarted. Run:
     ```bash
     kubectl rollout restart daemonset/nvidia-device-plugin-daemonset -n kube-system
     ```

---

### 7.4 Playbook D: System Recovery After Extended Facility Power Cut
**Symptom:** Workstation was powered off during an extended station blackout and just rebooted.
1. Verify K3s network routes initialized:
   ```bash
   kubectl get nodes
   ```
   *(If node shows `NotReady`, wait 60s for DHCP and Flannel CNI network binding).*
2. Confirm both backend pods acquired their GPU devices:
   ```bash
   kubectl get pods -n crowdvision
   ```
3. Check overnight monitor has resumed tracking:
   ```bash
   systemctl status crowdvision-monitor.service
   ```
4. Check the latest email in management inbox to confirm the startup verification email arrived.

---

### 7.5 Playbook E: Hardware MCE Memory Error (RAM Repair)
**Symptom:** Kernel logs show `EDAC skx MC0: CPU 0: Machine Check Event: ADDR 0x46e6fb800` and `RAS: Soft-offlining pfn: 0x46e6fb`.
1. View the exact memory bank logging errors:
   ```bash
   journalctl -k -b 0 | grep -iE "(mce|hardware error|edac skx)"
   ```
2. **Diagnosis:** Socket 0 / Memory Controller 0 (IMC#0) Channel 0 has a physical memory cell defect at address `0x46e6fb800`.
3. **Action:** Schedule a hardware maintenance window. Power down the workstation, open the HP Z6 G4 side panel, and reseat or replace the RAM DIMM module installed in **DIMM Slot CPU0-DIMM1**.

---

## 8. Quick Reference Cheatsheet

### Important File Paths
* **Project Root:** `/home/user/k3s/Suraksha-deployment`
* **Backend Source Code:** `/home/user/k3s/Suraksha-deployment/crowd-backend`
* **Frontend Source Code:** `/home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend`
* **K3s Kubernetes Manifests:** `/home/user/k3s/Suraksha-deployment/k3s`
* **Overnight Monitor Script:** `/home/user/Downloads/overnight_monitor.py`
* **Systemd Service Unit:** `/etc/systemd/system/crowdvision-monitor.service`
* **Model Weights & Calibration:** `/home/user/k3s/Suraksha-deployment/data/weights`

### Key URLs & Ports
* **Live Web Dashboard:** `http://10.54.23.55/`
* **Interactive API Documentation (Swagger):** `http://10.54.23.55/docs`
* **Simple Health Check:** `http://10.54.23.55/api/health/simple`
* **Detailed System Health Check:** `http://10.54.23.55/api/health`
* **Intel AMT Remote Management:** `https://10.54.23.55:16993`
