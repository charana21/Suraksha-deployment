"""
Generate high-resolution architecture and flow diagrams for Suraksha / CrowdVision.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle

def create_e2e_architecture_diagram(output_path):
    fig, ax = plt.subplots(figsize=(16, 10), dpi=300)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Color palette
    c_edge = "#E0F2FE"      # Light Sky Blue
    c_edge_b = "#0284C7"
    c_proc = "#FEF3C7"      # Light Amber
    c_proc_b = "#D97706"
    c_ai = "#F3E8FF"        # Light Purple
    c_ai_b = "#7E22CE"
    c_agg = "#DCFCE7"       # Light Green
    c_agg_b = "#16A34A"
    c_store = "#F1F5F9"     # Slate
    c_store_b = "#475569"
    c_ext = "#FEE2E2"       # Light Rose
    c_ext_b = "#DC2626"
    c_client = "#E0E7FF"    # Light Indigo
    c_client_b = "#4338CA"

    def draw_box(x, y, w, h, title, subtitle="", bg="#FFFFFF", border="#000000", fontsize=10):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.15",
                             facecolor=bg, edgecolor=border, linewidth=2.0)
        ax.add_patch(box)
        if subtitle:
            ax.text(x + w/2, y + h/2 + 0.18, title, ha='center', va='center',
                    fontsize=fontsize, fontweight='bold', color="#0F172A")
            ax.text(x + w/2, y + h/2 - 0.22, subtitle, ha='center', va='center',
                    fontsize=fontsize-2, color="#334155")
        else:
            ax.text(x + w/2, y + h/2, title, ha='center', va='center',
                    fontsize=fontsize, fontweight='bold', color="#0F172A")

    def draw_arrow(x1, y1, x2, y2, label="", color="#334155"):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2.0, shrinkA=5, shrinkB=5,
                                    mutation_scale=15))
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx, my + 0.15, label, ha='center', va='bottom', fontsize=8,
                    fontweight='bold', color=color,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="none", alpha=0.85))

    # Title
    ax.text(8, 9.6, "Suraksha / CrowdVision: End-to-End System Architecture",
            ha='center', va='center', fontsize=18, fontweight='bold', color="#1E293B")
    ax.text(8, 9.25, "Unified High-Throughput Video Pipeline, AI Fusion, Multi-Channel Alerting & Operations Interface",
            ha='center', va='center', fontsize=11, color="#64748B")

    # Column 1: Video Ingestion
    ax.text(1.8, 8.6, "1. INGESTION LAYER", ha='center', fontsize=11, fontweight='bold', color=c_edge_b)
    draw_box(0.5, 7.2, 2.6, 1.1, "IP Cameras / CCTV", "RTSP Streams (H.264/H.265)", c_edge, c_edge_b)
    draw_box(0.5, 5.7, 2.6, 1.1, "MediaMTX Proxy", "Local Stream Aggregator", c_edge, c_edge_b)
    draw_box(0.5, 4.2, 2.6, 1.1, "RTSP Workers", "Decoupled Capture Loop\nCircuit Breaker Reconnect", c_edge, c_edge_b)
    draw_box(0.5, 2.7, 2.6, 1.1, "Frame Enhancement", "CLAHE & Adaptive Denoise", c_edge, c_edge_b)

    draw_arrow(1.8, 7.2, 1.8, 6.8)
    draw_arrow(1.8, 5.7, 1.8, 5.3)
    draw_arrow(1.8, 4.2, 1.8, 3.8)

    # Column 2: Batching & Deep Learning
    ax.text(5.5, 8.6, "2. AI & INFERENCE LAYER", ha='center', fontsize=11, fontweight='bold', color=c_ai_b)
    draw_box(4.2, 7.2, 2.6, 1.1, "Central FrameQueue", "Priority & Per-Camera Limit", c_proc, c_proc_b)
    draw_box(4.2, 5.7, 2.6, 1.1, "Batched GPU Worker", "Dynamic Batching (Batch=16)", c_ai, c_ai_b)
    draw_box(4.2, 4.2, 2.6, 1.1, "YOLOv8m + PET Model", "Head BBox & Density Points", c_ai, c_ai_b)
    draw_box(4.2, 2.7, 2.6, 1.1, "Adaptive Fusion Engine", "Regime Blending + Calibration", c_ai, c_ai_b)
    draw_box(4.2, 1.2, 2.6, 1.1, "Motion / Stampede Engine", "Optical Flow & Compression Div", c_ai, c_ai_b)

    draw_arrow(3.1, 4.7, 4.2, 7.5, "Sampled Frames")
    draw_arrow(5.5, 7.2, 5.5, 6.8)
    draw_arrow(5.5, 5.7, 5.5, 5.3)
    draw_arrow(5.5, 4.2, 5.5, 3.8)
    draw_arrow(5.5, 2.7, 5.5, 2.3)

    # Column 3: Aggregation, Risk & Core API
    ax.text(9.2, 8.6, "3. BUSINESS & ANALYTICS LAYER", ha='center', fontsize=11, fontweight='bold', color=c_agg_b)
    draw_box(7.9, 7.2, 2.6, 1.1, "Zone Analytics Engine", "SUM(Count), MAX(Risk/Density)", c_agg, c_agg_b)
    draw_box(7.9, 5.7, 2.6, 1.1, "Core FastAPI Backend", "REST APIs, Security & RBAC", c_agg, c_agg_b)
    draw_box(7.9, 4.2, 2.6, 1.1, "Island Platform Service", "Footfall Risk & Train Windows", c_agg, c_agg_b)
    draw_box(7.9, 2.7, 2.6, 1.1, "Incident & Alert Engine", "Thresholds (Score 0-100)", c_agg, c_agg_b)
    draw_box(7.9, 1.2, 2.6, 1.1, "Persistence Worker", "Async Batched MongoDB Writes", c_store, c_store_b)

    draw_arrow(6.8, 3.2, 7.9, 7.7, "Metrics")
    draw_arrow(9.2, 7.2, 9.2, 6.8)
    draw_arrow(9.2, 5.7, 9.2, 5.3)
    draw_arrow(9.2, 4.2, 9.2, 3.8)
    draw_arrow(9.2, 2.7, 9.2, 2.3)

    # Column 4: Storage & External Gateways
    ax.text(12.0, 8.6, "4. PERSISTENCE & SERVICES", ha='center', fontsize=11, fontweight='bold', color=c_store_b)
    draw_box(11.0, 7.2, 2.0, 1.1, "WebSocket Gateway", "/api/ws/* Realtime Hub", c_client, c_client_b)
    draw_box(11.0, 5.7, 2.0, 1.1, "MongoDB Database", "Analytics, Alerts, Config", c_store, c_store_b)
    draw_box(11.0, 4.2, 2.0, 1.1, "AWS S3 Bucket", "Audio Files & Snapshots", c_ext, c_ext_b)
    draw_box(11.0, 2.7, 2.0, 1.1, "MSG91 WhatsApp", "Platform & Delay Alerts", c_ext, c_ext_b)
    draw_box(11.0, 1.2, 2.0, 1.1, "Automated TTS", "Multi-lingual PA Audio", c_ext, c_ext_b)

    draw_arrow(9.2, 6.3, 11.0, 7.5, "Broadcast")
    draw_arrow(9.2, 1.8, 11.0, 5.9, "Store")
    draw_arrow(9.2, 3.2, 11.0, 3.2, "WhatsApp")
    draw_arrow(9.2, 4.5, 11.0, 1.8, "TTS PA")

    # Column 5: Presentation / UI
    ax.text(14.6, 8.6, "5. OPERATIONAL CLIENTS", ha='center', fontsize=11, fontweight='bold', color=c_client_b)
    draw_box(13.6, 7.0, 2.1, 1.4, "React Dashboard", "Live Overview & Stats\n1-Hour Rolling Graph", c_client, c_client_b)
    draw_box(13.6, 5.1, 2.1, 1.4, "SVG FOB Map Viewer", "Real-Time Spatial Visuals\nGreen/Amber/Red Zones", c_client, c_client_b)
    draw_box(13.6, 3.2, 2.1, 1.4, "Alerts & Incidents", "Severity Filters & History\nIncident Resolution", c_client, c_client_b)
    draw_box(13.6, 1.3, 2.1, 1.4, "Station Ops Center", "Railway Police & Security\nDisplay Video Walls", c_client, c_client_b)

    draw_arrow(13.0, 7.7, 13.6, 7.7, "WSS Push")
    draw_arrow(13.0, 7.5, 13.6, 5.8)
    draw_arrow(13.0, 7.3, 13.6, 3.9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def create_inference_pipeline_diagram(output_path):
    fig, ax = plt.subplots(figsize=(15, 8), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8)
    ax.axis('off')

    ax.text(7.5, 7.6, "Deep Learning & Computer Vision Inference Pipeline",
            ha='center', va='center', fontsize=17, fontweight='bold', color="#1E293B")
    ax.text(7.5, 7.2, "Decoupled Video Acquisition, Dual-Model GPU Forward Pass & Regime-Adaptive Fusion",
            ha='center', va='center', fontsize=10.5, color="#64748B")

    def box(x, y, w, h, t1, t2, bg, border):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.12",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2 + 0.16, t1, ha='center', va='center', fontsize=9.5, fontweight='bold', color="#0F172A")
        ax.text(x + w/2, y + h/2 - 0.2, t2, ha='center', va='center', fontsize=8, color="#334155")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha='center', va='bottom', fontsize=7.5,
                    fontweight='bold', color="#1E293B",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Stage 1: Frame Acquisition
    box(0.5, 4.8, 2.4, 1.2, "RTSP Camera Feed", "Full FPS Ingestion\nOpenCV Decoupled Loop", "#E0F2FE", "#0284C7")
    box(0.5, 3.0, 2.4, 1.2, "Non-Blocking Buffer", "Zero Backlog Peak\nNewest Frame Only", "#E0F2FE", "#0284C7")
    box(0.5, 1.2, 2.4, 1.2, "Frame Enhancer", "CLAHE Contrast Limit\nConditional Denoise", "#E0F2FE", "#0284C7")
    arrow(1.7, 4.8, 1.7, 4.2)
    arrow(1.7, 3.0, 1.7, 2.4)

    # Stage 2: Queue & Batching
    box(3.5, 3.0, 2.4, 1.4, "Batched Inference Svc", "FrameQueue (Max=100)\nPer-Camera Limit=2\nTimeout=200ms", "#FEF3C7", "#D97706")
    arrow(2.9, 1.8, 3.5, 3.4, "1 FPS AI Sample")

    # Stage 3: Dual ML Models
    box(6.5, 4.6, 2.6, 1.4, "YOLOv8m Model", "Single GPU Forward Pass\nHead Bounding Boxes\nOccupancy Ratio", "#F3E8FF", "#7E22CE")
    box(6.5, 2.2, 2.6, 1.4, "PET Transformer", "Density Point Queries\nGaussian Sigma = 15.0\nRuns Every 3rd Frame", "#F3E8FF", "#7E22CE")
    arrow(5.9, 4.0, 6.5, 5.1, "Batched Frames")
    arrow(5.9, 3.4, 6.5, 2.9, "PET Sampling")

    # Stage 4: Fusion & Calibration
    box(9.8, 3.4, 2.6, 2.2, "Adaptive Fusion Engine", "Regime Classifier:\n- SPARSE (<15)\n- LOW (15-50)\n- MEDIUM (50-120)\n- HIGH (>120)\nDynamic Weighting\nPET Guard (>220 pax)", "#DCFCE7", "#16A34A")
    arrow(9.1, 5.3, 9.8, 4.8, "YOLO Count & Conf")
    arrow(9.1, 2.9, 9.8, 4.0, "PET Count & Map")

    box(9.8, 1.2, 2.6, 1.4, "Count Calibration", "ShanghaiTech Scale Factors:\nBin 1: x1.12 | Bin 2: x1.28\nBin 3: x1.09 | Bin 4: x1.19", "#DCFCE7", "#16A34A")
    arrow(11.1, 3.4, 11.1, 2.6)

    # Stage 5: Output Metrics
    box(13.0, 3.0, 1.8, 3.0, "Output Metrics", "1. Calibrated Count\n2. Density (pax/m²)\n3. Optical Flow (m/s)\n4. Risk Score (0-100)\n5. Risk Level:\n- LOW (<35)\n- MEDIUM (35-55)\n- HIGH (55-80)\n- CRITICAL (>80)", "#F1F5F9", "#475569")
    arrow(12.4, 1.9, 13.0, 3.8, "Final Results")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def create_zone_alert_flow_diagram(output_path):
    fig, ax = plt.subplots(figsize=(15, 8), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8)
    ax.axis('off')

    ax.text(7.5, 7.6, "Zone Aggregation, Risk Scoring & Incident Lifecycle Flow",
            ha='center', va='center', fontsize=17, fontweight='bold', color="#1E293B")
    ax.text(7.5, 7.2, "Multi-Camera Spatial Synthesis, Conservative Risk Logic & Multi-Channel Actioning",
            ha='center', va='center', fontsize=10.5, color="#64748B")

    def box(x, y, w, h, t1, t2, bg, border):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.12",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2 + 0.16, t1, ha='center', va='center', fontsize=9.5, fontweight='bold', color="#0F172A")
        ax.text(x + w/2, y + h/2 - 0.2, t2, ha='center', va='center', fontsize=8, color="#334155")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha='center', va='bottom', fontsize=7.5,
                    fontweight='bold', color="#1E293B",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Cameras
    box(0.5, 5.0, 2.4, 1.2, "Camera 1 (Stairs)", "People Count: 35\nDensity: 1.2 pax/m²", "#E0F2FE", "#0284C7")
    box(0.5, 3.2, 2.4, 1.2, "Camera 2 (Mid-FOB)", "People Count: 85\nDensity: 3.1 pax/m²", "#E0F2FE", "#0284C7")
    box(0.5, 1.4, 2.4, 1.2, "Camera 3 (PF Drop)", "People Count: 42\nDensity: 1.8 pax/m²", "#E0F2FE", "#0284C7")

    # Zone Aggregator
    box(3.6, 2.8, 2.8, 2.6, "Zone Aggregator", "Rule: Conservative Synthesis\n\nPeople Count = SUM(Cameras)\n= 35 + 85 + 42 = 162 pax\n\nDensity = MAX(Cameras) = 3.1\nRisk Score = MAX(Scores) = 84\nRisk Level = CRITICAL", "#DCFCE7", "#16A34A")
    arrow(2.9, 5.6, 3.6, 4.8)
    arrow(2.9, 3.8, 3.6, 4.1)
    arrow(2.9, 2.0, 3.6, 3.4)

    # Decision Engine
    box(7.2, 3.3, 2.6, 1.6, "Incident Assessment", "Persist >= 5 seconds?\nConsecutive frames >= 3?\nCooldown expired (30m)?\nSeverity >= HIGH?", "#FEF3C7", "#D97706")
    arrow(6.4, 4.1, 7.2, 4.1, "Zone State")

    # Outputs
    box(10.6, 5.2, 3.8, 1.4, "Real-Time WebSocket Push", "FOB Crowd > 150 -> Alarm Border Active\nSVG Map Updates: Zone flashes Red\n1-Hour Rolling Graph caches point", "#E0E7FF", "#4338CA")
    box(10.6, 3.2, 3.8, 1.4, "MSG91 WhatsApp Notification", "Automated alert to RPF & Station Master\nIncludes Train/FOB location, footfall count,\nseverity details and emergency link", "#FEE2E2", "#DC2626")
    box(10.6, 1.2, 3.8, 1.4, "Automated Multilingual Voice PA", "Text-to-Speech (gTTS / Sarvam AI)\nMP3 audio uploaded to AWS S3\nStation PA triggers crowd diversion", "#F3E8FF", "#7E22CE")

    arrow(9.8, 4.6, 10.6, 5.8, "Instant UI Feed")
    arrow(9.8, 4.1, 10.6, 3.9, "If Critical Alert")
    arrow(9.8, 3.6, 10.6, 2.0, "If PA Trigger")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def create_k3s_deployment_diagram(output_path):
    fig, ax = plt.subplots(figsize=(15, 8), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8)
    ax.axis('off')

    ax.text(7.5, 7.6, "K3s Production Cluster Architecture & Topology",
            ha='center', va='center', fontsize=17, fontweight='bold', color="#1E293B")
    ax.text(7.5, 7.2, "GPU-Accelerated Edge Workstation Deployment with Traefik Ingress & Container Toolkit",
            ha='center', va='center', fontsize=10.5, color="#64748B")

    def box(x, y, w, h, t1, t2, bg, border):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.12",
                           facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2 + 0.16, t1, ha='center', va='center', fontsize=9.5, fontweight='bold', color="#0F172A")
        ax.text(x + w/2, y + h/2 - 0.2, t2, ha='center', va='center', fontsize=8, color="#334155")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.8, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha='center', va='bottom', fontsize=7.5,
                    fontweight='bold', color="#1E293B",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="none", alpha=0.9))

    # Cluster boundary box
    cluster_box = FancyBboxPatch((2.2, 0.4), 10.6, 6.4, boxstyle="round,pad=0.2,rounding_size=0.2",
                                facecolor="#F8FAFC", edgecolor="#94A3B8", linewidth=2.0, linestyle="--")
    ax.add_patch(cluster_box)
    ax.text(7.5, 6.55, "K3s Single-Node / Edge Workstation Cluster (Namespace: crowdvision)",
            ha='center', va='center', fontsize=11, fontweight='bold', color="#334155")

    # External Client
    box(0.2, 3.6, 1.6, 1.8, "Client Browser", "React SPA\nHTTPS Port 443\nWSS /api/ws/*", "#E0E7FF", "#4338CA")

    # Ingress
    box(2.6, 3.6, 2.0, 1.8, "Traefik Ingress", "Path Routing:\n'/' -> Frontend\n'/api' -> Backend\n'/api/ws' -> WSS", "#DCFCE7", "#16A34A")
    arrow(1.8, 4.5, 2.6, 4.5, "HTTPS / WSS")

    # Pods
    box(5.3, 4.8, 2.4, 1.4, "Frontend Pod", "Nginx Server\nStatic React / Vite Assets\nPort 80", "#E0E7FF", "#4338CA")
    box(5.3, 2.2, 2.4, 2.2, "Backend Pod", "FastAPI Application\nNVIDIA GPU: 1\nCUDA 11.8+ / TensorRT\nPersistence & Schedulers\nPort 8000", "#FEF3C7", "#D97706")
    box(5.3, 0.6, 2.4, 1.2, "MediaMTX Pod", "RTSP Ingestion Relay\nPort 8554 (RTSP)", "#E0F2FE", "#0284C7")

    arrow(4.6, 4.8, 5.3, 5.4, "'/'")
    arrow(4.6, 4.5, 5.3, 3.5, "'/api'")

    # Storage & Models
    box(8.5, 2.5, 2.2, 1.8, "Persistent Volume", "PVC: crowdvision-data\n- /app/data/weights\n  yolov8m.pt\n  SHA_model.pth\n- /app/data/images", "#F1F5F9", "#475569")
    arrow(7.7, 3.4, 8.5, 3.4, "Mounts PVC")

    box(8.5, 0.6, 2.2, 1.4, "External MongoDB", "URI via Kubernetes Secret\nOperational & Analytics\nTime-series & TTL Store", "#DCFCE7", "#16A34A")
    arrow(7.7, 2.5, 8.5, 1.5, "Async PyMongo")

    # Cloud Services
    box(13.2, 4.8, 1.6, 1.4, "MSG91 Cloud", "WhatsApp API\nOTP & Alerts", "#FEE2E2", "#DC2626")
    box(13.2, 3.0, 1.6, 1.4, "AWS S3 Cloud", "Object Storage\nPA Audio Files", "#FEE2E2", "#DC2626")
    box(13.2, 1.2, 1.6, 1.4, "RapidAPI Cloud", "Live Train Status\nArrival/Delay Feeds", "#FEE2E2", "#DC2626")

    arrow(7.7, 4.0, 13.2, 5.4, "HTTPS API")
    arrow(7.7, 3.8, 13.2, 3.7, "Boto3 S3")
    arrow(7.7, 3.6, 13.2, 2.0, "Live Feeds")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    create_e2e_architecture_diagram("/home/user/k3s/Suraksha-deployment/docs_assets/diagram_e2e_architecture.png")
    create_inference_pipeline_diagram("/home/user/k3s/Suraksha-deployment/docs_assets/diagram_inference_pipeline.png")
    create_zone_alert_flow_diagram("/home/user/k3s/Suraksha-deployment/docs_assets/diagram_zone_alert_flow.png")
    create_k3s_deployment_diagram("/home/user/k3s/Suraksha-deployment/docs_assets/diagram_k3s_deployment.png")
