#!/usr/bin/env python3
"""
Generate publication-quality diagrams for K3s Deployment, GPU/CPU Sharding,
Workflow, AI Pipeline, and Auto-Start recovery.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch

OUTPUT_DIR = "/home/user/k3s/Suraksha-deployment/docs_assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# DIAGRAM 1: K3s Cluster & Network Architecture
# -----------------------------------------------------------------------------
def generate_k3s_architecture_diagram():
    fig, ax = plt.subplots(figsize=(16, 9.5), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9.5)
    ax.axis("off")

    # Title
    ax.text(8, 9.1, "Suraksha CrowdVision: Production K3s Edge Cluster Architecture",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A")
    ax.text(8, 8.7, "Single-Node GPU Workstation (HP Z6 G4) | Namespace: 'crowdvision' | Dual RTX A4000 GPUs",
            ha="center", va="center", fontsize=11, color="#475569")

    def box(x, y, w, h, t1, t2="", bg="#FFFFFF", border="#0F172A", fontsize=9.5):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12,rounding_size=0.15",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        if t2:
            ax.text(x + w/2, y + h/2 + 0.18, t1, ha="center", va="center",
                    fontsize=fontsize, fontweight="bold", color="#0F172A")
            ax.text(x + w/2, y + h/2 - 0.22, t2, ha="center", va="center",
                    fontsize=fontsize-2, color="#334155")
        else:
            ax.text(x + w/2, y + h/2, t1, ha="center", va="center",
                    fontsize=fontsize, fontweight="bold", color="#0F172A")

    def arrow(x1, y1, x2, y2, label="", color="#334155"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx, my + 0.12, label, ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Outer Node Box
    node_box = FancyBboxPatch((0.4, 0.4), 15.2, 7.9, boxstyle="round,pad=0.2,rounding_size=0.25",
                              facecolor="#F8FAFC", edgecolor="#64748B", linewidth=2.0, linestyle="--")
    ax.add_patch(node_box)
    ax.text(0.8, 8.0, "Physical Host Node: surakshaai (Ubuntu 24.04 LTS | Intel Xeon 48 vCPUs | 128 GB RAM | 2x RTX A4000)",
            fontsize=10.5, fontweight="bold", color="#1E293B")

    # Ingress Layer
    box(0.8, 4.5, 2.2, 2.6, "Traefik Ingress\nController", "Host Port 80 / 443\nIP: 10.54.23.55\nmDNS: .local", "#DCFCE7", "#16A34A", 10)

    # Clients (outside)
    box(0.8, 1.2, 2.2, 2.0, "Client Access", "Browser / Dashboard\nHTTP 10.54.23.55\nhttp://crowdvision-\ndashboard.local", "#E0E7FF", "#4338CA", 9.5)
    arrow(1.9, 3.2, 1.9, 4.5, "User Requests", "#4338CA")

    # Routing Paths from Ingress
    arrow(3.0, 6.2, 4.2, 6.2, "Path: /", "#16A34A")
    arrow(3.0, 5.0, 4.2, 4.5, "Path: /api, /docs", "#D97706")

    # Workload Pods
    # Frontend Pod
    box(4.2, 5.5, 3.2, 1.8, "Frontend Pod (Deployment)", "crowdvision-frontend\nNginx Server | Port 80\nReact + Vite Single Page App\nLimits: 2 CPU, 1Gi RAM", "#E0E7FF", "#4338CA", 10)

    # Backend StatefulSet Pods
    box(4.2, 2.8, 4.5, 2.0, "Backend Shard 0 (StatefulSet)\ncrowdvision-backend-0", "Dedicated GPU 0 (RTX A4000 - 16GB)\nNVIDIA_VISIBLE_DEVICES=0\nHandles Cameras 1-14 (14 Streams)\nReq: 8 CPU, 8GiB | Lim: 17 CPU, 24GiB", "#FEF3C7", "#D97706", 9.5)
    box(4.2, 0.6, 4.5, 2.0, "Backend Shard 1 (StatefulSet)\ncrowdvision-backend-1", "Dedicated GPU 1 (RTX A4000 - 16GB)\nNVIDIA_VISIBLE_DEVICES=1\nHandles Cameras 15-28 (14 Streams)\nReq: 8 CPU, 8GiB | Lim: 17 CPU, 24GiB", "#FEF3C7", "#D97706", 9.5)

    # Headless Service & ClusterIP
    box(9.2, 2.8, 2.6, 2.0, "Backend Headless Service", "crowdvision-backend-headless\nPort 8000 (TCP)\nDirect Pod-to-Pod DNS\nPod State Synchronization", "#F1F5F9", "#475569", 9.5)
    arrow(8.7, 3.8, 9.2, 3.8, "Peer Sync")

    # MediaMTX Streaming Pod
    box(9.2, 5.5, 2.6, 1.8, "MediaMTX Pod\n(Deployment)", "RTSP / WebRTC Stream Relay\nPorts: 8554 (RTSP), 8889 (WebRTC)\nProxy for 28 IP CCTV Cameras\nLim: 4 CPU, 2Gi RAM", "#E0F2FE", "#0284C7", 9.5)
    arrow(9.2, 6.4, 7.4, 6.4, "HLS/WebRTC", "#0284C7")
    arrow(10.5, 5.5, 7.5, 4.2, "RTSP Relay", "#0284C7")

    # External Physical Cameras
    box(12.4, 5.5, 2.8, 1.8, "28 Physical CCTV Cameras", "Station FOBs, Platforms, Waiting Halls\nRTSP Streams over Station LAN\nSubnet: 10.54.x.x / 192.168.x.x", "#FEE2E2", "#DC2626", 9.5)
    arrow(12.4, 6.4, 11.8, 6.4, "28 RTSP Feeds", "#DC2626")

    # Persistent Volume
    box(9.2, 0.6, 2.6, 1.8, "Persistent Volume (PVC)", "crowdvision-data (Local Storage)\n/app/data/weights (YOLO, Re-ID)\n/app/data/zones (Polygons, Masks)\nMounted in Shard 0 & 1", "#F1F5F9", "#475569", 9.5)
    arrow(8.7, 1.5, 9.2, 1.5, "Read Weights")

    # External MongoDB
    box(12.4, 1.5, 2.8, 2.5, "External Database\nMongoDB (Production)", "telematics-mongo0.evrides.in:12021\nDatabase: crowdvision_prod\nCollections:\n- cameras (28 active records)\n- zones (PF-10 Waiting Hall, etc.)\n- crowd_analytics (TimeSeries)", "#DCFCE7", "#16A34A", 9.5)
    arrow(8.7, 3.2, 12.4, 2.7, "Analytics & Count Sync", "#16A34A")

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "diagram_k3s_cluster_architecture.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated: {out}")


# -----------------------------------------------------------------------------
# DIAGRAM 2: Dual GPU & CPU Resource Utilization Configurations
# -----------------------------------------------------------------------------
def generate_gpu_cpu_sharding_diagram():
    fig, ax = plt.subplots(figsize=(16, 9.5), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9.5)
    ax.axis("off")

    ax.text(8, 9.1, "Dual NVIDIA RTX A4000 GPU & CPU Resource Utilization Architecture",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A")
    ax.text(8, 8.7, "Workload Partitioning: 28 Cameras Sharded Across Dual Hardware GPUs with Isolated VRAM & Compute",
            ha="center", va="center", fontsize=11, color="#475569")

    def box(x, y, w, h, t1, t2="", bg="#FFFFFF", border="#0F172A", fontsize=9.5):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        if t2:
            ax.text(x + w/2, y + h/2 + 0.18, t1, ha="center", va="center",
                    fontsize=fontsize, fontweight="bold", color="#0F172A")
            ax.text(x + w/2, y + h/2 - 0.22, t2, ha="center", va="center",
                    fontsize=fontsize-2, color="#334155")
        else:
            ax.text(x + w/2, y + h/2, t1, ha="center", va="center",
                    fontsize=fontsize, fontweight="bold", color="#0F172A")

    def arrow(x1, y1, x2, y2, label="", color="#334155"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx, my + 0.12, label, ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color=color,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Host Hardware Layer Box
    host_box = FancyBboxPatch((0.5, 6.2), 15.0, 2.2, boxstyle="round,pad=0.15,rounding_size=0.2",
                             facecolor="#F1F5F9", edgecolor="#475569", linewidth=2.0)
    ax.add_patch(host_box)
    ax.text(8, 8.1, "HOST HARDWARE ENGINE: Intel Xeon 48-Core CPU (125 GB RAM) + Dual RTX A4000 GPUs",
            ha="center", va="center", fontsize=12, fontweight="bold", color="#0F172A")

    box(1.0, 6.4, 4.3, 1.4, "Host CPU & RAM Pool", "Intel Xeon Platinum 8260 (48 vCPUs)\n125 GiB DDR4 ECC System Memory\nLinux Kernel 6.8 + K3s containerd", "#E0F2FE", "#0284C7", 10)
    box(5.8, 6.4, 4.4, 1.4, "NVIDIA GPU 0 (PCIe 21:00.0)", "RTX A4000 | 16 GB GDDR6 ECC VRAM\n6,144 CUDA Cores | 192 Tensor Cores\nActive Temp: ~92°C | Power: ~85W", "#FEF3C7", "#D97706", 10)
    box(10.7, 6.4, 4.4, 1.4, "NVIDIA GPU 1 (PCIe 2D:00.0)", "RTX A4000 | 16 GB GDDR6 ECC VRAM\n6,144 CUDA Cores | 192 Tensor Cores\nActive Temp: ~87°C | Power: ~129W", "#FEF3C7", "#D97706", 10)

    # Container Runtime Integration
    box(4.5, 4.9, 7.0, 0.9, "NVIDIA Container Runtime (K3s Integration)",
        "runtimeClassName: nvidia | CDI / NVIDIA Container Toolkit | GPU Isolation", "#DCFCE7", "#16A34A", 10.5)

    arrow(7.5, 6.4, 7.5, 5.8)
    arrow(12.5, 6.4, 8.5, 5.8)

    # Shard 0 Column
    box(0.5, 0.5, 7.2, 4.1, "", "", "#FFFBEB", "#D97706")
    ax.text(4.1, 4.3, "POD: crowdvision-backend-0 (SHARD 0)", ha="center", fontsize=11, fontweight="bold", color="#B45309")

    box(0.8, 3.1, 6.6, 1.0, "GPU Binding: NVIDIA_VISIBLE_DEVICES=0",
        "Assigned to Hardware GPU 0 | Dedicated 16 GB VRAM\nActual VRAM Usage: 13.6 GiB (Stable)", "#FEF3C7", "#D97706", 9)
    box(0.8, 2.0, 6.6, 0.9, "K3s Pod Resource Quota",
        "CPU Request: 8 vCPUs | CPU Limit: 17 vCPUs\nMemory Request: 8 GiB | Memory Limit: 24 GiB", "#F8FAFC", "#64748B", 9)
    box(0.8, 0.7, 6.6, 1.1, "Assigned Camera Fleet (14 Active Streams)",
        "cam_middle_fob_4_5, cam_pf1_fob_hyb_end, cam_kzj_pf1_fob_kzj,\n"
        "cam_mid_fob_pf1, cam_hyb_pf1, cam_hyb_pf2, cam_hyb_pf4,\n"
        "cam_hyb_booking, cam_hyb_booking_gate4a, cam_hyb_booking_gate6...", "#DCFCE7", "#16A34A", 8.5)

    # Shard 1 Column
    box(8.3, 0.5, 7.2, 4.1, "", "", "#EFF6FF", "#2563EB")
    ax.text(11.9, 4.3, "POD: crowdvision-backend-1 (SHARD 1)", ha="center", fontsize=11, fontweight="bold", color="#1D4ED8")

    box(8.6, 3.1, 6.6, 1.0, "GPU Binding: NVIDIA_VISIBLE_DEVICES=1",
        "Assigned to Hardware GPU 1 | Dedicated 16 GB VRAM\nActual VRAM Usage: 15.7 GiB (Stable)", "#DBEAFE", "#2563EB", 9)
    box(8.6, 2.0, 6.6, 0.9, "K3s Pod Resource Quota",
        "CPU Request: 8 vCPUs | CPU Limit: 17 vCPUs\nMemory Request: 8 GiB | Memory Limit: 24 GiB", "#F8FAFC", "#64748B", 9)
    box(8.6, 0.7, 6.6, 1.1, "Assigned Camera Fleet (14 Active Streams)",
        "cam_kzj_fob_mid_4_5, cam_kzj_fob_mid_8_9, cam_pf8_mid_fc_kzj,\n"
        "cam_gate2_wh, cam_hyd_booking_gate2a, cam_near_gate_2a_fc,\n"
        "cam_gate2_fc_ac_wh, cam_gate2a_fc_parking, cam_pf10_waiting_hall...", "#DCFCE7", "#16A34A", 8.5)

    arrow(6.5, 4.9, 4.1, 4.5, "Routes to GPU 0")
    arrow(9.5, 4.9, 11.9, 4.5, "Routes to GPU 1")

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "diagram_gpu_cpu_sharding.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated: {out}")


# -----------------------------------------------------------------------------
# DIAGRAM 3: Deployment & Rollout Workflow
# -----------------------------------------------------------------------------
def generate_deployment_workflow_diagram():
    fig, ax = plt.subplots(figsize=(16, 8.5), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(8, 8.1, "End-to-End K3s Application Deployment & Zero-Downtime Rollout Workflow",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A")
    ax.text(8, 7.7, "Step-by-Step CI/CD and Container Orchestration Pipeline for Edge Workstation",
            ha="center", va="center", fontsize=11, color="#475569")

    def step_box(x, y, w, h, step_num, title, cmd, color_bg, color_b):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                           facecolor=color_bg, edgecolor=color_b, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + 0.35, y + h - 0.3, f"STEP {step_num}", fontsize=8.5, fontweight="bold", color=color_b)
        ax.text(x + w/2, y + h - 0.65, title, ha="center", fontsize=10, fontweight="bold", color="#0F172A")
        ax.text(x + w/2, y + 0.45, cmd, ha="center", fontsize=8, color="#334155",
                fontfamily="monospace", bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="#CBD5E1"))

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=2.0, shrinkA=5, shrinkB=5))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx, my + 0.12, label, ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color="#1E293B")

    # Step 1: Code Sync
    step_box(0.5, 4.6, 3.4, 2.4, "1", "Code Sync & Branches",
             "git checkout videotest (backend)\n"
             "git checkout master (frontend)",
             "#E0F2FE", "#0284C7")

    # Step 2: Build Images
    step_box(4.4, 4.6, 3.4, 2.4, "2", "Docker Image Build",
             "docker build -t\n"
             "  crowdvision-backend:local\n"
             "docker build -t\n"
             "  crowdvision-frontend:local",
             "#FEF3C7", "#D97706")

    # Step 3: Import into K3s
    step_box(8.3, 4.6, 3.4, 2.4, "3", "Import into containerd",
             "docker save crowdvision-*\n"
             " | k3s ctr -n k8s.io\n"
             "   images import -",
             "#DCFCE7", "#16A34A")

    # Step 4: Secrets & Config
    step_box(12.2, 4.6, 3.3, 2.4, "4", "Apply Secrets & Config",
             "kubectl apply -f\n"
             "  namespace.yaml\n"
             "kubectl create secret\n"
             "  generic crowdvision-secrets",
             "#F3E8FF", "#7E22CE")

    # Arrows for Top Row
    arrow(3.9, 5.8, 4.4, 5.8)
    arrow(7.8, 5.8, 8.3, 5.8)
    arrow(11.7, 5.8, 12.2, 5.8)

    # Connector down
    arrow(13.8, 4.6, 13.8, 3.6)

    # Step 5: StatefulSet & Deployment
    step_box(12.2, 1.2, 3.3, 2.4, "5", "Deploy Workloads",
             "kubectl apply -f\n"
             "  pvc.yaml mediamtx.yaml\n"
             "  frontend.yaml\n"
             "  backend-statefulset.yaml",
             "#FEE2E2", "#DC2626")

    # Step 6: Ingress & Networking
    step_box(8.3, 1.2, 3.4, 2.4, "6", "Configure Ingress",
             "kubectl apply -f ingress.yaml\n"
             "Traefik maps routes:\n"
             "  / -> frontend\n"
             "  /api, /docs -> backend",
             "#DCFCE7", "#16A34A")

    # Step 7: Rollout & Restart
    step_box(4.4, 1.2, 3.4, 2.4, "7", "Zero-Downtime Rollout",
             "kubectl rollout restart\n"
             "  statefulset crowdvision-backend\n"
             "kubectl rollout restart\n"
             "  deployment crowdvision-frontend",
             "#FEF3C7", "#D97706")

    # Step 8: Health Verification
    step_box(0.5, 1.2, 3.4, 2.4, "8", "Verify Health & Probes",
             "kubectl get pods -n crowdvision\n"
             "curl -s http://10.54.23.55/\n"
             "  api/health/simple\n"
             "Status: 200 OK | All Cams Alive",
             "#E0F2FE", "#0284C7")

    # Arrows for Bottom Row
    arrow(12.2, 2.4, 11.7, 2.4)
    arrow(8.3, 2.4, 7.8, 2.4)
    arrow(4.4, 2.4, 3.9, 2.4)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "diagram_k3s_deployment_workflow.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated: {out}")


# -----------------------------------------------------------------------------
# DIAGRAM 4: Video Processing & Inference Pipeline
# -----------------------------------------------------------------------------
def generate_video_ai_pipeline_diagram():
    fig, ax = plt.subplots(figsize=(16, 8.5), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(8, 8.1, "Suraksha AI Video Analytics & Computer Vision Inference Pipeline",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A")
    ax.text(8, 7.7, "Decoupled RTSP Acquisition, YOLOv8 GPU Forward Pass, Zone Homography & Real-Time Aggregation",
            ha="center", va="center", fontsize=11, color="#475569")

    def pbox(x, y, w, h, t1, t2="", bg="#FFFFFF", border="#0F172A"):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2 + 0.18, t1, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#0F172A")
        ax.text(x + w/2, y + h/2 - 0.22, t2, ha="center", va="center",
                fontsize=8, color="#334155")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color="#1E293B",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Stage 1: Cameras & MediaMTX
    pbox(0.5, 4.8, 2.5, 1.4, "28 IP CCTV Cameras", "Station FOBs, Stairs, Halls\nRTSP Streams (1080p / 720p)", "#FEE2E2", "#DC2626")
    pbox(0.5, 2.2, 2.5, 1.4, "MediaMTX In-Cluster", "RTSP / WebRTC Restreamer\nLocal Low-Latency Cache", "#E0F2FE", "#0284C7")
    arrow(1.75, 4.8, 1.75, 3.6, "RTSP Feed")

    # Stage 2: Ingestion Loop
    pbox(3.6, 2.2, 2.6, 2.6, "Decoupled RTSP Workers", "OpenCV VideoCapture Threads\nZero-Lag Circular Ring Buffer\nAuto Reconnection Watchdog\nDrop Stale Frames (Keep Newest)", "#FEF3C7", "#D97706")
    arrow(3.0, 2.9, 3.6, 2.9, "Stream Decode")

    # Stage 3: Deep Learning Inference
    pbox(6.8, 4.6, 2.8, 1.8, "YOLOv8 Head/Person Model", "Dual RTX A4000 GPU\nBatch Inference (Batch=8/16)\nTensorRT / FP16 Accelerated\nBBoxes & Confidence Scores", "#F3E8FF", "#7E22CE")
    pbox(6.8, 1.6, 2.8, 1.8, "Multi-Camera ByteTrack / ReID", "Feature Extraction Vectors\nTemporal Cross-Camera Tracking\nEliminate Double-Counting", "#F3E8FF", "#7E22CE")

    arrow(6.2, 4.0, 6.8, 5.2, "Sampled Frames")
    arrow(6.2, 3.0, 6.8, 2.5, "Tracklets")

    # Stage 4: Homography & Zone Mapping
    pbox(10.2, 2.2, 2.6, 2.6, "Zone Aggregator & Fusion", "Perspective Homography Matrix\nStation Polygon Masks:\n- PF-10 Waiting Hall Area\n- Middle FOB, KZJ FOB\n- Platform Footfall Counts\nRegime Calibration Scaling", "#DCFCE7", "#16A34A")
    arrow(9.6, 5.2, 10.2, 4.2, "Bounding Boxes")
    arrow(9.6, 2.5, 10.2, 3.2, "Track Trajectories")

    # Stage 5: Outputs
    pbox(13.3, 4.8, 2.3, 1.6, "FastAPI WebSockets", "Real-time Push to Dashboard\nLatency: <250ms\nLive Count Badges (45-52 pax)", "#E0E7FF", "#4338CA")
    pbox(13.3, 2.6, 2.3, 1.6, "MongoDB Storage", "TimeSeries Collections\nZone History & Alerts\nTTL Auto-Cleanup", "#DCFCE7", "#16A34A")
    pbox(13.3, 0.4, 2.3, 1.6, "Station Operations UI", "React Dashboard\nFOB Spatial Heatmaps\nRPF Emergency Alerts", "#E0E7FF", "#4338CA")

    arrow(12.8, 4.2, 13.3, 5.4, "Live Stream")
    arrow(12.8, 3.5, 13.3, 3.4, "Store Metrics")
    arrow(12.8, 2.8, 13.3, 1.4, "UI Update")

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "diagram_video_ai_pipeline.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated: {out}")


# -----------------------------------------------------------------------------
# DIAGRAM 5: Auto-Start & Power-Loss Recovery Chain
# -----------------------------------------------------------------------------
def generate_autostart_power_recovery_diagram():
    fig, ax = plt.subplots(figsize=(16, 7.5), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    ax.text(8, 7.1, "Hardware Auto-Boot & High-Availability Service Recovery Chain",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#0F172A")
    ax.text(8, 6.7, "Automated Unattended Startup Following System Restart or Unexpected Electrical Power Cut",
            ha="center", va="center", fontsize=11, color="#475569")

    def abox(x, y, w, h, num, t1, t2="", bg="#FFFFFF", border="#0F172A"):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + 0.35, y + h - 0.28, f"STAGE {num}", fontsize=8.5, fontweight="bold", color=border)
        ax.text(x + w/2, y + h/2 + 0.12, t1, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#0F172A")
        ax.text(x + w/2, y + 0.45, t2, ha="center", va="center",
                fontsize=8, color="#334155")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=2.0, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color="#1E293B")

    abox(0.4, 2.0, 2.7, 3.8, "1", "BIOS Power Loss\nRecovery",
         "HP Z6 G4 Workstation\n"
         "Setting: Advanced ->\n"
         "  Power Management ->\n"
         "  After Power Loss ->\n"
         "  [POWER ON]\n"
         "Hardware boots instantly\n"
         "when AC electricity returns.",
         "#FEF3C7", "#D97706")

    abox(3.5, 2.0, 2.7, 3.8, "2", "Operating System\n& systemd Init",
         "Ubuntu 24.04 LTS\n"
         "multi-user.target activates\n"
         "systemd starts core units:\n"
         "• mongod.service (Enabled)\n"
         "• network.target (Online)\n"
         "• NVIDIA Driver 580 init\n"
         "• user-linger enabled",
         "#E0F2FE", "#0284C7")

    abox(6.6, 2.0, 2.7, 3.8, "3", "K3s Orchestration\nEngine Launch",
         "systemctl enable k3s.service\n"
         "• containerd daemon starts\n"
         "• Flannel CNI overlay\n"
         "• Traefik Ingress activates\n"
         "• NVIDIA Container Runtime\n"
         "  mounts GPUs 0 & 1",
         "#DCFCE7", "#16A34A")

    abox(9.7, 2.0, 2.7, 3.8, "4", "Pod Auto-Restore\n(Zero-Pull Boot)",
         "restartPolicy: Always\n"
         "imagePullPolicy: Never\n"
         "Instant boot from local cache:\n"
         "• backend-0 (GPU 0)\n"
         "• backend-1 (GPU 1)\n"
         "• frontend (Nginx)\n"
         "• mediamtx (RTSP relay)",
         "#F3E8FF", "#7E22CE")

    abox(12.8, 2.0, 2.8, 3.8, "5", "Networking & Monitor\nDaemon Broadcasters",
         "Auto-Networking:\n"
         "• crowdvision-mdns.service\n"
         "  broadcasts .local domain\n"
         "• crowdvision-monitor.service\n"
         "  (Overnight 3-hr reporter\n"
         "  with 30-min plots)\n"
         "Full System Online!",
         "#DCFCE7", "#16A34A")

    arrow(3.1, 3.9, 3.5, 3.9)
    arrow(6.2, 3.9, 6.6, 3.9)
    arrow(9.3, 3.9, 9.7, 3.9)
    arrow(12.4, 3.9, 12.8, 3.9)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "diagram_autostart_power_recovery.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated: {out}")


if __name__ == "__main__":
    generate_k3s_architecture_diagram()
    generate_gpu_cpu_sharding_diagram()
    generate_deployment_workflow_diagram()
    generate_video_ai_pipeline_diagram()
    generate_autostart_power_recovery_diagram()
    print("All 5 diagrams generated successfully!")
