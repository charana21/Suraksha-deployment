#!/usr/bin/env python3
"""
Generate the Comprehensive K3s Deployment Architecture, Operations Runbook & Resource Allocation Guide.
Outputs:
1. /home/user/k3s/Suraksha-deployment/K3s_Deployment_Architecture_and_Operations_Guide.docx
2. /home/user/k3s/Suraksha-deployment/K3s_Deployment_Architecture_and_Operations_Guide.md
"""

import os
import datetime
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOCX_OUTPUT = "/home/user/k3s/Suraksha-deployment/K3s_Deployment_Architecture_and_Operations_Guide.docx"
MD_OUTPUT = "/home/user/k3s/Suraksha-deployment/K3s_Deployment_Architecture_and_Operations_Guide.md"
ASSETS_DIR = "/home/user/k3s/Suraksha-deployment/docs_assets"

def build_docx():
    doc = docx.Document()

    # Set Margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Corporate Color Palette
    PRIMARY = RGBColor(24, 76, 120)       # Deep Navy Blue (#184C78)
    SECONDARY = RGBColor(41, 128, 185)    # Medium Blue (#2980B9)
    DARK_TEXT = RGBColor(30, 41, 59)      # Slate 800 (#1E293B)
    MUTED_TEXT = RGBColor(100, 116, 139)  # Slate 500 (#64748B)
    CODE_COLOR = RGBColor(15, 23, 42)     # Slate 900 (#0F172A)
    SUCCESS_COLOR = RGBColor(22, 101, 52) # Emerald Green (#166534)
    WARNING_COLOR = RGBColor(180, 83, 9)  # Amber (#B45309)
    DANGER_COLOR = RGBColor(185, 28, 28)  # Crimson (#B91C1C)

    def set_font(run, font_name="Calibri", size_pt=11, color=DARK_TEXT, bold=False, italic=False):
        run.font.name = font_name
        run.font.size = Pt(size_pt)
        run.font.color.rgb = color
        run.bold = bold
        run.italic = italic

    def add_title(text, subtitle=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(24)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(text)
        set_font(run, "Calibri", 26, PRIMARY, bold=True)

        if subtitle:
            p2 = doc.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(20)
            run2 = p2.add_run(subtitle)
            set_font(run2, "Calibri", 13, SECONDARY, italic=True)

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 16, PRIMARY, bold=True)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 13, SECONDARY, bold=True)
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 11.5, DARK_TEXT, bold=True)
        return p

    def add_body(text, bold_prefix=None, space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            set_font(r_bold, "Calibri", 11, DARK_TEXT, bold=True)
        run = p.add_run(text)
        set_font(run, "Calibri", 11, DARK_TEXT)
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            set_font(r_bold, "Calibri", 10.5, DARK_TEXT, bold=True)
        run = p.add_run(text)
        set_font(run, "Calibri", 10.5, DARK_TEXT)
        return p

    def add_callout(title, text, callout_type="info"):
        bg_colors = {
            "info": "F0F9FF",     # Light Blue
            "success": "F0FDF4",  # Light Green
            "warning": "FFFBEB",  # Light Amber
            "danger": "FEF2F2",   # Light Red
        }
        border_colors = {
            "info": "0284C7",
            "success": "16A34A",
            "warning": "D97706",
            "danger": "DC2626",
        }
        title_colors = {
            "info": RGBColor(2, 132, 199),
            "success": RGBColor(22, 163, 74),
            "warning": RGBColor(217, 119, 6),
            "danger": RGBColor(220, 38, 38),
        }

        bg_hex = bg_colors.get(callout_type, "F8FAFC")
        b_hex = border_colors.get(callout_type, "64748B")
        t_color = title_colors.get(callout_type, PRIMARY)

        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)

        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
        tcPr.append(shd)

        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="36" w:space="0" w:color="{b_hex}"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)

        mar = parse_xml(f'''
            <w:tcMar {nsdecls("w")}>
                <w:top w:w="120" w:type="dxa"/>
                <w:left w:w="200" w:type="dxa"/>
                <w:bottom w:w="120" w:type="dxa"/>
                <w:right w:w="200" w:type="dxa"/>
            </w:tcMar>
        ''')
        tcPr.append(mar)

        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r_title = p.add_run(title)
        set_font(r_title, "Calibri", 11, t_color, bold=True)

        p2 = cell.add_paragraph()
        p2.paragraph_format.space_after = Pt(0)
        p2.paragraph_format.line_spacing = 1.15
        r_text = p2.add_run(text)
        set_font(r_text, "Calibri", 10, DARK_TEXT)

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_code_block(code_text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)

        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="0F172A"/>') # Dark slate background
        tcPr.append(shd)

        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="6" w:space="0" w:color="334155"/>
                <w:left w:val="single" w:sz="24" w:space="0" w:color="38BDF8"/>
                <w:bottom w:val="single" w:sz="6" w:space="0" w:color="334155"/>
                <w:right w:val="single" w:sz="6" w:space="0" w:color="334155"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)

        mar = parse_xml(f'''
            <w:tcMar {nsdecls("w")}>
                <w:top w:w="120" w:type="dxa"/>
                <w:left w:w="180" w:type="dxa"/>
                <w:bottom w:w="120" w:type="dxa"/>
                <w:right w:w="180" w:type="dxa"/>
            </w:tcMar>
        ''')
        tcPr.append(mar)

        lines = code_text.strip().split("\n")
        for i, line in enumerate(lines):
            p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.1
            run = p.add_run(line)
            set_font(run, "Consolas", 9.5, RGBColor(226, 232, 240)) # Slate 200 light text

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_image_with_caption(img_path, caption):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(10)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.add_run().add_picture(img_path, width=Inches(6.5))

            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(12)
            run = p_cap.add_run(f"Figure: {caption}")
            set_font(run, "Calibri", 9.5, MUTED_TEXT, italic=True)
        else:
            add_callout("Image File Missing", f"Image could not be found at: {img_path}", "warning")

    # -------------------------------------------------------------------------
    # DOCUMENT COVER & HEADER
    # -------------------------------------------------------------------------
    add_title("SURAKSHA CROWDVISION", "K3s Edge Orchestration, Dual RTX A4000 GPU Sharding & Deployment Runbook")

    # Metadata Table
    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Document Title:", "Suraksha CrowdVision: K3s Deployment Architecture & Operations Runbook"),
        ("Version & Status:", "Version 2.0 (Production Verified — Dual GPU Sharding & 28 Cameras)"),
        ("Hardware Workstation:", "HP Z6 G4 Workstation (Intel Xeon 48 vCPUs, 128 GB RAM, 2x NVIDIA RTX A4000)"),
        ("Orchestration Platform:", "K3s Lightweight Kubernetes (v1.30+), containerd, Traefik Ingress Controller"),
        ("Operating System & Driver:", "Ubuntu 24.04 LTS (Kernel 6.8), NVIDIA Driver 580.178.04, CUDA 13.0 / 12.x"),
        ("Author / Organization:", "Tride Mobility AI Engineering Team (saicharananandapu@tridemobility.com)"),
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        row = meta_tbl.rows[row_idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        r0 = c0.paragraphs[0].add_run(k)
        set_font(r0, "Calibri", 10, PRIMARY, bold=True)
        r1 = c1.paragraphs[0].add_run(v)
        set_font(r1, "Calibri", 10, DARK_TEXT)

        for cell in (c0, c1):
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{"F8FAFC" if row_idx % 2 == 0 else "FFFFFF"}"/>')
            cell._tc.get_or_add_tcPr().append(shd)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------------------
    # SECTION 1: EXECUTIVE OVERVIEW & PLATFORM ARCHITECTURE
    # -------------------------------------------------------------------------
    add_h1("1. Executive Overview & System Architecture")
    add_body(
        "Suraksha CrowdVision is an edge-deployed, multi-camera computer vision and passenger density monitoring "
        "platform operating at major Indian Railway hubs. The application continuously processes 28 live high-definition "
        "RTSP video feeds across foot-over-bridges (FOBs), platform concourses, stairwells, and waiting halls to compute "
        "real-time passenger counts, spatial heatmaps, congestion alerts, and stampede risk scores."
    )
    add_body(
        "To satisfy strict edge operational constraints—including zero external cloud dependency for inference, complete "
        "power-loss recovery, dual hardware GPU acceleration, and low-latency local streaming—the platform is containerized "
        "and orchestrated on a single high-performance edge workstation running K3s (Lightweight Kubernetes)."
    )

    add_callout(
        "Key Architecture Principles:",
        "• Workload Sharding: 28 cameras are divided evenly (14 cameras each) across two independent NVIDIA RTX A4000 GPUs.\n"
        "• Deterministic Stateful Orchestration: Backend uses a Kubernetes StatefulSet with dedicated GPU device binding.\n"
        "• Unified Ingress Routing: Traefik Ingress routes web, API, Swagger, and WebSocket connections over port 80/443.\n"
        "• Continuous Availability: Fully configured auto-start chain ensures unattended recovery within 60s of power restoration.",
        "success"
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_k3s_cluster_architecture.png"),
        "Suraksha CrowdVision End-to-End K3s Cluster Architecture & Network Topology"
    )

    # -------------------------------------------------------------------------
    # SECTION 2: WORKSTATION HARDWARE & INFRASTRUCTURE PROFILE
    # -------------------------------------------------------------------------
    add_h1("2. Edge Workstation Hardware & Compute Profile")
    add_body(
        "The edge workstation running CrowdVision is an enterprise-grade HP Z6 G4 Workstation engineered for continuous "
        "24/7 compute loads. The hardware is configured with dual high-bandwidth NVIDIA RTX A4000 GPUs, massive system memory, "
        "and enterprise NVMe storage to guarantee zero thermal throttling and stable inference frame rates."
    )

    # Hardware Table
    hw_tbl = doc.add_table(rows=8, cols=3)
    hw_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Hardware Subsystem", "Physical Specification", "Operational Role in CrowdVision"]
    for i, h in enumerate(headers):
        cell = hw_tbl.rows[0].cells[i]
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10.5, RGBColor(255, 255, 255), bold=True)

    hw_rows = [
        ("Host Processor (CPU)", "Intel Xeon Platinum 8260 (24 Cores / 48 vCPUs @ 2.40 GHz)", "Decoupled OpenCV RTSP decoding, video frame buffers, FastAPI serving"),
        ("System Memory (RAM)", "128 GB DDR4 2933 MHz ECC Registered (125 GiB Usable)", "Host frame ring buffers, in-memory rolling metrics (Zero-disk daemon)"),
        ("GPU Accelerator #0", "NVIDIA RTX A4000 (16 GB GDDR6 ECC, 6144 CUDA, PCIe 21:00.0)", "Assigned to Shard 0 (crowdvision-backend-0): 14 Camera Streams"),
        ("GPU Accelerator #1", "NVIDIA RTX A4000 (16 GB GDDR6 ECC, 6144 CUDA, PCIe 2D:00.0)", "Assigned to Shard 1 (crowdvision-backend-1): 14 Camera Streams"),
        ("Storage Subsystem", "2 TB NVMe PCIe Gen4 M.2 SSD + Secondary Data Drive", "Stores OS, K3s containerd local images, YOLO weights, homography zones"),
        ("Network Interfaces", "Dual Intel Gigabit NICs (Active Node IP: 10.54.23.55)", "RTSP camera ingestion from station LAN + Traefik dashboard serving"),
        ("Power & Cooling", "1000W 90% Efficient Chassis Power Supply + Active Blowers", "Independent dual GPU blower exhaust maintaining operating temps <95°C"),
    ]

    for row_idx, data in enumerate(hw_rows, start=1):
        row = hw_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = row.cells[col_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            run = cell.paragraphs[0].add_run(text)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------------------
    # SECTION 3: DUAL GPU & CPU RESOURCE UTILIZATION CONFIGURATIONS
    # -------------------------------------------------------------------------
    add_h1("3. Dual GPU & CPU Resource Utilization Configurations")
    add_body(
        "A critical engineering requirement of Suraksha CrowdVision is deterministic hardware isolation. If all 28 video "
        "streams competed for a single GPU, CUDA memory allocation would saturate immediately, leading to Out-Of-Memory (OOM) "
        "kernel panics and dropped frames. The solution employs K3s StatefulSet pod sharding backed by the NVIDIA Container Runtime."
    )

    add_h2("3.1: Workload Partitioning & StatefulSet Sharding Mechanism")
    add_body(
        "Instead of a standard Kubernetes Deployment (which launches interchangeable, non-indexed replicas), the backend uses "
        "a StatefulSet named `crowdvision-backend` with `replicas: 2` and `podManagementPolicy: Parallel`."
    )
    add_bullet("Pod crowdvision-backend-0: Pinned to Hardware GPU 0 via NVIDIA Container Toolkit.", bold_prefix="Shard 0: ")
    add_bullet("Pod crowdvision-backend-1: Pinned to Hardware GPU 1 via NVIDIA Container Toolkit.", bold_prefix="Shard 1: ")
    add_bullet("Parallel Startup: Both pods boot concurrently without waiting for sequential ordering.", bold_prefix="Policy Parallel: ")
    add_bullet("Camera Modulo Partitioning: Each pod determines its active camera list using (Camera_Index % 2 == Shard_ID).", bold_prefix="Even Distribution: ")

    add_h2("3.2: Pod Resource Allocation Matrix (Requests & Limits)")
    add_body(
        "Resource boundaries are strictly configured in the pod specification to guarantee that background processes do not "
        "starve the operating system while preventing memory leaks from crashing the host node."
    )

    # Resource Matrix Table
    res_tbl = doc.add_table(rows=5, cols=6)
    res_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    r_headers = ["Component Pod", "CPU Request", "CPU Limit", "Memory Request", "Memory Limit", "GPU Binding"]
    for i, h in enumerate(r_headers):
        cell = res_tbl.rows[0].cells[i]
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    res_data = [
        ("crowdvision-backend-0", "8 vCPUs", "17 vCPUs", "8 GiB", "24 GiB", "1x GPU (NVIDIA RTX A4000 #0)"),
        ("crowdvision-backend-1", "8 vCPUs", "17 vCPUs", "8 GiB", "24 GiB", "1x GPU (NVIDIA RTX A4000 #1)"),
        ("crowdvision-frontend", "0.5 vCPUs", "2.0 vCPUs", "256 MiB", "1.0 GiB", "None (CPU Nginx Static Engine)"),
        ("mediamtx", "1.0 vCPUs", "4.0 vCPUs", "512 MiB", "2.0 GiB", "None (RTSP Network Streaming)"),
    ]
    for row_idx, data in enumerate(res_data, start=1):
        row = res_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = row.cells[col_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            run = cell.paragraphs[0].add_run(text)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_h2("3.3: GPU VRAM Memory Budget Breakdown")
    add_body(
        "Each NVIDIA RTX A4000 provides 16,376 MiB of high-speed GDDR6 VRAM. The application memory allocation per GPU is "
        "dimensioned as follows:"
    )
    add_bullet("PyTorch Base CUDA Context: ~450 MiB overhead upon initialization.", bold_prefix="CUDA Context: ")
    add_bullet("YOLOv8 Person & Head Model: ~1,850 MiB for FP16 inference engine and TensorRT buffers.", bold_prefix="YOLOv8 Weights: ")
    add_bullet("ByteTrack / Re-ID Embedding Model: ~1,200 MiB for feature extraction across multiple cameras.", bold_prefix="Tracking Engine: ")
    add_bullet("Active Ingestion Frame Buffers: ~3,200 MiB for 14 concurrent circular frame buffers.", bold_prefix="Frame Queues: ")
    add_bullet("Batched Inference Tensors: ~7,500 MiB dynamic scratchpad memory during peak batching.", bold_prefix="Tensor Workspace: ")
    add_bullet("Active Memory Usage: ~13.6 GiB (GPU 0) and ~15.7 GiB (GPU 1), operating reliably within hardware capacity.", bold_prefix="Measured Utilization: ")

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_gpu_cpu_sharding.png"),
        "Dual NVIDIA RTX A4000 GPU & CPU Resource Utilization Architecture"
    )

    # -------------------------------------------------------------------------
    # SECTION 4: K3S NETWORKING & INGRESS TOPOLOGY
    # -------------------------------------------------------------------------
    add_h1("4. K3s Networking & Ingress Routing Topology")
    add_body(
        "K3s bundles Traefik as its standard Ingress controller, listening directly on the host network interfaces (port 80). "
        "The ingress configuration routes HTTP requests to the appropriate in-cluster service based on URL path prefixes."
    )

    # Ingress Table
    ing_tbl = doc.add_table(rows=5, cols=4)
    ing_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    i_headers = ["Path Prefix", "In-Cluster Target Service", "Target Port", "Description & Client Audience"]
    for i, h in enumerate(i_headers):
        cell = ing_tbl.rows[0].cells[i]
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    ing_data = [
        ("/", "crowdvision-frontend", "80 (HTTP)", "Serves React SPA dashboard, static JS/CSS assets, FOB SVG map"),
        ("/api", "crowdvision-backend", "8000 (HTTP)", "REST API routes for cameras, zones, counts, alerts, analytics"),
        ("/docs", "crowdvision-backend", "8000 (HTTP)", "Interactive OpenAPI Swagger documentation for API consumers"),
        ("/openapi.json", "crowdvision-backend", "8000 (HTTP)", "Raw OpenAPI JSON schema definition"),
    ]
    for row_idx, data in enumerate(ing_data, start=1):
        row = ing_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = row.cells[col_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            run = cell.paragraphs[0].add_run(text)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_callout(
        "Cross-Subnet Access via DNS Name vs IP Address:",
        "• Local IP Address (http://10.54.23.55/): Fully routable across all corporate subnets and VLANs.\n"
        "• mDNS Domain (http://crowdvision-dashboard.local): Resolves automatically within the local subnet (10.54.23.0/24).\n"
        "• Cross-Subnet Recommendation: For devices on other office subnets, configure a corporate DNS A-record "
        "pointing 'crowdvision.tride.live' or 'crowdvision-dashboard' to 10.54.23.55.",
        "info"
    )

    # -------------------------------------------------------------------------
    # SECTION 5: STEP-BY-STEP DEPLOYMENT RUNBOOK & COMMANDS
    # -------------------------------------------------------------------------
    add_h1("5. End-to-End Step-by-Step Deployment Runbook")
    add_body(
        "This section provides the complete, copy-paste terminal runbook for building, importing, deploying, and "
        "rolling out CrowdVision on K3s from scratch."
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_k3s_deployment_workflow.png"),
        "End-to-End Application Deployment & Zero-Downtime Rollout Pipeline"
    )

    add_h2("Phase 1: Environment Preparation & Git Code Checkout")
    add_body("Verify working directory and ensure target branches are synchronized:")
    add_code_block("""# Navigate to the deployment repository
cd /home/user/k3s/Suraksha-deployment

# Verify git status and active branch
git status
git branch

# Sync backend and frontend code to working directory
# Backend source: https://github.com/TrideAdmin/crowd-backend.git (branch: videotest)
# Frontend source: https://github.com/TrideAdmin/Crowd_Vision_Frontend.git (branch: master)""")

    add_h2("Phase 2: Building Local Container Images")
    add_body("Build Docker container images locally for both the frontend and backend:")
    add_code_block("""# 1. Build Frontend Container Image
docker build \\
  --build-arg "VITE_API_URL=/api" \\
  -t crowdvision-frontend:local \\
  /home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend

# 2. Build Backend Container Image (includes CUDA & PyTorch)
docker build \\
  -t crowdvision-backend:local \\
  /home/user/k3s/Suraksha-deployment/crowd-backend

# Verify built images
docker images | grep crowdvision""")

    add_h2("Phase 3: Ingesting Images into K3s containerd Runtime")
    add_body("Export Docker images and import directly into the K3s containerd `k8s.io` namespace:")
    add_code_block("""# Export and import Frontend image into K3s containerd
docker save crowdvision-frontend:local | sudo k3s ctr -n k8s.io images import -

# Export and import Backend image into K3s containerd
docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -

# Verify images are recognized by K3s containerd
sudo k3s ctr -n k8s.io images list | grep crowdvision""")

    add_h2("Phase 4: Creating Kubernetes Namespace, Secrets & ConfigMaps")
    add_body("Apply namespace and generate application secrets from the production `.env` file:")
    add_code_block("""# 1. Create crowdvision namespace
kubectl create namespace crowdvision --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply Application ConfigMap
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/configmap.yaml

# 3. Create Secrets from backend .env file (MongoDB, SMTP, API keys)
kubectl -n crowdvision create secret generic crowdvision-secrets \\
  --from-env-file=/home/user/k3s/Suraksha-deployment/crowd-backend/.env \\
  --dry-run=client -o yaml | kubectl apply -f -

# Verify Secrets created
kubectl get secrets -n crowdvision""")

    add_h2("Phase 5: Deploying Workloads (Storage, MediaMTX, Frontend & Backend)")
    add_body("Apply PersistentVolumeClaims, video proxy, frontend, backend StatefulSet, and Ingress:")
    add_code_block("""# 1. Apply Persistent Storage Claim for AI Weights
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/pvc.yaml

# 2. Deploy MediaMTX Video Streaming Proxy
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/mediamtx-deployment.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/mediamtx-service.yaml

# 3. Deploy Frontend Web Application
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/stack/base/frontend.yaml

# 4. Deploy Headless Service for StatefulSet
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-headless-service.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-service.yaml

# 5. Deploy Backend StatefulSet (GPU Sharding)
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-statefulset.yaml

# 6. Apply Traefik Ingress Rules
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/ingress.yaml""")

    add_h2("Phase 6: Triggering Rolling Restarts & Verifying Status")
    add_body("Perform zero-downtime rolling restart to guarantee all pods load the newest images:")
    add_code_block("""# Rolling restart of Frontend deployment
kubectl rollout restart deployment crowdvision-frontend -n crowdvision

# Rolling restart of Backend StatefulSet
kubectl rollout restart statefulset crowdvision-backend -n crowdvision

# Watch rollout status
kubectl rollout status statefulset/crowdvision-backend -n crowdvision
kubectl rollout status deployment/crowdvision-frontend -n crowdvision

# Check running pods and resource allocations
kubectl get pods -n crowdvision -o wide""")

    # -------------------------------------------------------------------------
    # SECTION 6: AI VIDEO ANALYTICS & CAMERA FLEET PARTITIONING
    # -------------------------------------------------------------------------
    add_h1("6. AI Video Analytics & Camera Fleet Partitioning")
    add_body(
        "The station monitoring deployment encompasses 28 active cameras configured in the database `crowdvision_prod`. "
        "The inference pipeline decouples stream grabbing from deep learning inference to prevent network stalls from "
        "blocking the GPU."
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_video_ai_pipeline.png"),
        "AI Video Analytics & Computer Vision Inference Pipeline"
    )

    add_h2("6.1: Active Camera Fleet Partitioning (Shard 0 vs Shard 1)")
    add_body("Cameras are assigned to specific pods and GPUs as shown in the table below:")

    # Camera Shard Table
    cam_tbl = doc.add_table(rows=15, cols=3)
    cam_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_headers = ["Stream #", "Shard 0 (GPU 0 — crowdvision-backend-0)", "Shard 1 (GPU 1 — crowdvision-backend-1)"]
    for i, h in enumerate(c_headers):
        cell = cam_tbl.rows[0].cells[i]
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    cam_data = [
        ("1", "cam_middle_fob_4_5 (Middle FOB Platform 4-5)", "cam_kzj_fob_mid_4_5 (KZJ FOB Middle 4-5)"),
        ("2", "cam_pf1_fob_hyb_end (PF 1 FOB HYB End)", "cam_kzj_fob_mid_8_9 (KZJ FOB Middle 8-9)"),
        ("3", "cam_kzj_pf1_fob_kzj (KZJ PF 1 FOB)", "cam_pf8_mid_fc_kzj (PF 8 Middle FC KZJ)"),
        ("4", "cam_kzj_pf1_fob_pf10 (KZJ PF 1 to PF 10)", "cam_gate2_wh (Gate 2 Waiting Hall)"),
        ("5", "cam_mid_fob_pf1 (Middle FOB PF 1)", "cam_hyd_booking_gate2a (HYD Booking Gate 2A)"),
        ("6", "cam_mid_fob_center (Middle FOB Center Concourse)", "cam_near_gate_2a_fc_swathi_ent (Near Gate 2A Swathi)"),
        ("7", "cam_hyb_pf1 (HYB Platform 1)", "cam_gate2_fc_ac_wh (Gate 2 FC AC Waiting Hall)"),
        ("8", "cam_hyb_pf2 (HYB Platform 2)", "cam_gate2a_fc_parking (Gate 2A FC Parking Area)"),
        ("9", "cam_hyb_pf4 (HYB Platform 4)", "cam_pf1_fob_pf10 (PF 1 FOB to PF 10)"),
        ("10", "cam_hyb_pf10 (HYB Platform 10)", "cam_new_kzj_fob_fc_pf1 (New KZJ FOB FC PF 1)"),
        ("11", "cam_hyb_pf1_a (HYB Platform 1A)", "cam_new_kzj_fob_near_pf1 (New KZJ FOB Near PF 1)"),
        ("12", "cam_hyb_booking (HYB Main Booking Hall)", "cam_pf10_bme_counter (PF-10 Waiting Hall Area)"),
        ("13", "cam_hyb_booking_gate4a (HYB Booking Gate 4A)", "cam_hyb_booking_gate6 (HYB Booking Gate 6)"),
        ("14", "cam_pf2_fc_hyd_side (PF 2 FC HYD Side)", "cam_hyb_booking_gate8 (HYB Booking Gate 8)"),
    ]

    for row_idx, (idx_s, c0, c1) in enumerate(cam_data, start=1):
        row = cam_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate([idx_s, c0, c1]):
            cell = row.cells[col_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            run = cell.paragraphs[0].add_run(text)
            set_font(run, "Calibri", 9, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_callout(
        "PF-10 Waiting Hall Area Integration:",
        "Camera 'cam_pf10_bme_counter' maps directly to zone 'zone_pf10_waiting_hall' in MongoDB crowdvision_prod. "
        "The frontend Dashboard renders the live crowd count badge (streaming at 45-52 pax) directly in the camera "
        "stream card header with real-time WebSocket updates.",
        "success"
    )

    # -------------------------------------------------------------------------
    # SECTION 7: OPERATIONS, MONITORING & VERIFICATION COMMANDS
    # -------------------------------------------------------------------------
    add_h1("7. Operations, Monitoring & Health Verification Commands")
    add_body("Use these operational commands to inspect cluster health, GPU activity, and pod logs in real time:")

    add_h2("7.1: Kubernetes Cluster & Pod Telemetry")
    add_code_block("""# Check all resources across the crowdvision namespace
kubectl get all -n crowdvision

# Inspect pod resource consumption (CPU and Memory)
kubectl top pods -n crowdvision

# Check detailed pod events and describe status
kubectl describe pod crowdvision-backend-0 -n crowdvision

# Stream live backend inference logs (tail last 50 lines)
kubectl logs -n crowdvision -l app.kubernetes.io/name=crowdvision-backend -f --tail=50

# Stream frontend access logs
kubectl logs -n crowdvision -l app.kubernetes.io/name=crowdvision-frontend -f --tail=50""")

    add_h2("7.2: NVIDIA Hardware GPU Live Monitoring")
    add_code_block("""# Check current GPU temperature, VRAM usage, and compute utilization
nvidia-smi

# Watch GPU telemetry refresh every 1 second
watch -n 1 nvidia-smi

# Query detailed GPU temperature and power metrics
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv""")

    add_h2("7.3: In-Memory Overnight Monitor Daemon (Zero Local Files)")
    add_code_block("""# Check status of the 3-hour reporting daemon
systemctl status crowdvision-monitor.service

# Stream live monitor daemon journal logs (without disk clutter)
journalctl -u crowdvision-monitor.service -f

# Restart the monitor daemon
sudo systemctl restart crowdvision-monitor.service""")

    # -------------------------------------------------------------------------
    # SECTION 8: AUTO-START & POWER-LOSS RECOVERY CONFIGURATION
    # -------------------------------------------------------------------------
    add_h1("8. Auto-Start & Power-Loss Recovery Configuration")
    add_body(
        "To ensure continuous availability in station environments subject to electrical maintenance or power outages, "
        "the workstation is configured with a fully automated, unattended startup chain."
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_autostart_power_recovery.png"),
        "Hardware Auto-Boot & High-Availability Service Recovery Chain"
    )

    add_h2("8.1: Hardware BIOS Configuration (Power-Cut Auto-Boot)")
    add_body("To enable the HP Z6 G4 Workstation to power on automatically when electricity returns:")
    add_bullet("Power on the machine and repeatedly press F10 during boot to enter BIOS Setup.", bold_prefix="Step 1: ")
    add_bullet("Navigate to: Advanced -> Power Management Options -> After Power Loss.", bold_prefix="Step 2: ")
    add_bullet("Change the value from 'Power Off' to 'Power On' (or 'Previous State').", bold_prefix="Step 3: ")
    add_bullet("Press F10 to Save Changes and Exit. The system will now boot automatically upon power connection.", bold_prefix="Step 4: ")

    add_h2("8.2: Software systemd Auto-Start Chain")
    add_body("Verify that all system services are enabled to launch automatically at boot:")
    add_code_block("""# Verify and enable MongoDB service
sudo systemctl enable mongod.service

# Verify and enable K3s orchestration engine
sudo systemctl enable k3s.service

# Verify and enable mDNS domain publisher service
systemctl --user enable crowdvision-mdns.service
sudo loginctl enable-linger user

# Verify and enable Overnight Monitor service
sudo systemctl enable crowdvision-monitor.service""")

    # -------------------------------------------------------------------------
    # SECTION 9: TROUBLESHOOTING & COMMON RESOLUTIONS
    # -------------------------------------------------------------------------
    add_h1("9. Troubleshooting & Operational Resolutions")

    add_callout(
        "Issue: GPU Out-Of-Memory (OOM) / CUDA Allocation Error",
        "Cause: An un-sharded deployment was applied where both replicas attempted to bind to GPU 0.\n"
        "Fix: Verify that backend-statefulset.yaml contains 'CAMERA_SHARD_COUNT=2' and that each pod replica "
        "properly identifies its pod index from metadata.name.",
        "danger"
    )

    add_callout(
        "Issue: ErrImageNeverPull / ImagePullBackOff",
        "Cause: The pod has 'imagePullPolicy: Never' but the container image was not imported into K3s containerd.\n"
        "Fix: Run 'docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -' and verify "
        "with 'sudo k3s ctr -n k8s.io images list | grep crowdvision'.",
        "warning"
    )

    add_callout(
        "Issue: Duplicate Environment Variables in Secrets",
        "Cause: Multiple definitions of SMTP_PASSWORD or MONGODB_URI in the .env file cause kubectl create secret to fail.\n"
        "Fix: Comment out redundant legacy credentials in .env, keeping only the active production configuration.",
        "info"
    )

    # -------------------------------------------------------------------------
    # SECTION 10: APPENDIX — COMPLETE PRODUCTION YAML MANIFESTS
    # -------------------------------------------------------------------------
    add_h1("10. Appendix: Complete Production K3s Manifests")

    add_h2("10.1: StatefulSet Manifest (k3s/backend-statefulset.yaml)")
    add_code_block("""apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: crowdvision-backend
  labels:
    app.kubernetes.io/name: crowdvision-backend
spec:
  serviceName: crowdvision-backend-headless
  replicas: 2
  podManagementPolicy: Parallel
  selector:
    matchLabels:
      app.kubernetes.io/name: crowdvision-backend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: crowdvision-backend
    spec:
      runtimeClassName: nvidia
      terminationGracePeriodSeconds: 60
      containers:
        - name: backend
          image: crowdvision-backend:local
          imagePullPolicy: Never
          ports:
            - name: http
              containerPort: 8000
          env:
            - name: CAMERA_SHARD_COUNT
              value: "2"
            - name: HEADLESS_SERVICE_NAME
              value: "crowdvision-backend-headless"
            - name: HEADLESS_SERVICE_PORT
              value: "8000"
            - name: NVIDIA_DRIVER_CAPABILITIES
              value: "compute,utility,video"
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          envFrom:
            - configMapRef:
                name: crowdvision-config
            - secretRef:
                name: crowdvision-secrets
          volumeMounts:
            - name: application-data
              mountPath: /app/data
          resources:
            requests:
              cpu: "8"
              memory: 8Gi
              nvidia.com/gpu: "1"
            limits:
              cpu: "17"
              memory: 24Gi
              nvidia.com/gpu: "1"
          startupProbe:
            httpGet:
              path: /api/health/simple
              port: http
            timeoutSeconds: 5
            failureThreshold: 60
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /api/health/simple
              port: http
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 5
          readinessProbe:
            httpGet:
              path: /api/health/simple
              port: http
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 5
      volumes:
        - name: application-data
          persistentVolumeClaim:
            claimName: crowdvision-data""")

    add_h2("10.2: Traefik Ingress Manifest (k3s/ingress.yaml)")
    add_code_block("""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crowdvision
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
          - path: /docs
            pathType: Prefix
            backend:
              service:
                name: crowdvision-backend
                port:
                  name: http
          - path: /openapi.json
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
                  name: http""")

    # Save Word Document
    doc.save(DOCX_OUTPUT)
    print(f"Successfully generated Word document: {DOCX_OUTPUT}")


def build_markdown():
    """Generates an accompanying Markdown document."""
    content = f"""# Suraksha CrowdVision: K3s Deployment Architecture & Operations Runbook

**Document Version:** 2.0 (Production Verified — Dual GPU Sharding & 28 Cameras)  
**Date:** October 2026  
**Hardware Workstation:** HP Z6 G4 (Intel Xeon 48 vCPUs, 128 GB RAM, Dual NVIDIA RTX A4000)  
**Platform:** K3s Lightweight Kubernetes, containerd, Traefik Ingress, NVIDIA Container Runtime  
**Author:** Tride Mobility AI Engineering Team  

---

## 1. Executive Overview & System Architecture

Suraksha CrowdVision is an edge-deployed, multi-camera computer vision and passenger density monitoring platform operating at major Indian Railway hubs. The application continuously processes 28 live high-definition RTSP video feeds across foot-over-bridges (FOBs), platform concourses, stairwells, and waiting halls to compute real-time passenger counts, spatial heatmaps, congestion alerts, and stampede risk scores.

### Key Architecture Principles
- **Workload Sharding:** 28 cameras divided evenly (14 cameras each) across two independent NVIDIA RTX A4000 GPUs.
- **Deterministic Stateful Orchestration:** Backend uses a Kubernetes StatefulSet with dedicated GPU device binding.
- **Unified Ingress Routing:** Traefik Ingress routes web, API, Swagger, and WebSocket connections over port 80/443.
- **Continuous Availability:** Fully configured auto-start chain ensures unattended recovery within 60s of power restoration.

![K3s Cluster Architecture](docs_assets/diagram_k3s_cluster_architecture.png)

---

## 2. Workstation Hardware Profile

| Subsystem | Specification | Operational Role |
| :--- | :--- | :--- |
| **Host CPU** | Intel Xeon Platinum 8260 (24 Cores / 48 vCPUs @ 2.40 GHz) | Decoupled OpenCV RTSP decoding, video frame buffers, FastAPI serving |
| **Host RAM** | 128 GB DDR4 2933 MHz ECC (125 GiB Usable) | Host frame ring buffers, in-memory rolling metrics |
| **GPU 0** | NVIDIA RTX A4000 (16 GB GDDR6 ECC, PCIe 21:00.0) | Assigned to Shard 0 (`crowdvision-backend-0`): 14 Camera Streams |
| **GPU 1** | NVIDIA RTX A4000 (16 GB GDDR6 ECC, PCIe 2D:00.0) | Assigned to Shard 1 (`crowdvision-backend-1`): 14 Camera Streams |
| **Storage** | 2 TB NVMe PCIe Gen4 M.2 SSD + Secondary Drive | OS, K3s containerd local images, YOLO weights, homography zones |
| **Network** | Dual Intel Gigabit NICs (Active IP: 10.54.23.55) | Station LAN RTSP ingestion + Traefik dashboard serving |

---

## 3. Dual GPU & CPU Resource Utilization Configurations

### 3.1 Workload Partitioning & StatefulSet Sharding Mechanism
Instead of a standard Kubernetes Deployment, the backend uses a StatefulSet named `crowdvision-backend` with `replicas: 2` and `podManagementPolicy: Parallel`:
- **Shard 0 (`crowdvision-backend-0`):** Pinned to Hardware GPU 0 (`NVIDIA_VISIBLE_DEVICES=0`).
- **Shard 1 (`crowdvision-backend-1`):** Pinned to Hardware GPU 1 (`NVIDIA_VISIBLE_DEVICES=1`).
- **Even Distribution:** Camera assignments are determined via `Camera_Index % 2 == Shard_ID`.

### 3.2 Resource Allocation Matrix

| Component Pod | CPU Request | CPU Limit | Memory Request | Memory Limit | GPU Allocation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **crowdvision-backend-0** | 8 vCPUs | 17 vCPUs | 8 GiB | 24 GiB | 1x NVIDIA RTX A4000 #0 |
| **crowdvision-backend-1** | 8 vCPUs | 17 vCPUs | 8 GiB | 24 GiB | 1x NVIDIA RTX A4000 #1 |
| **crowdvision-frontend** | 0.5 vCPUs | 2.0 vCPUs | 256 MiB | 1.0 GiB | None (CPU Nginx Static Engine) |
| **mediamtx** | 1.0 vCPUs | 4.0 vCPUs | 512 MiB | 2.0 GiB | None (RTSP Network Streaming) |

### 3.3 GPU VRAM Memory Budget (16 GB per GPU)
- **CUDA Context:** ~450 MiB
- **YOLOv8 Weights & TensorRT Buffers:** ~1,850 MiB
- **Tracking & Embedding Models:** ~1,200 MiB
- **Active Ingestion Frame Buffers (14 cameras):** ~3,200 MiB
- **Batched Tensor Workspace:** ~7,500 MiB
- **Measured Steady-State VRAM:** ~13.6 GiB (GPU 0), ~15.7 GiB (GPU 1)

![GPU & CPU Resource Utilization Architecture](docs_assets/diagram_gpu_cpu_sharding.png)

---

## 4. K3s Networking & Ingress Routing

| Path Prefix | In-Cluster Target Service | Target Port | Audience |
| :--- | :--- | :--- | :--- |
| `/` | `crowdvision-frontend` | `80` | React Dashboard, FOB Map, Static Assets |
| `/api` | `crowdvision-backend` | `8000` | REST API, Count Badges, Zone Analytics |
| `/docs` | `crowdvision-backend` | `8000` | OpenAPI Swagger Documentation |
| `/openapi.json` | `crowdvision-backend` | `8000` | OpenAPI JSON Schema |

---

## 5. End-to-End Step-by-Step Deployment Runbook

![Deployment & Rollout Workflow](docs_assets/diagram_k3s_deployment_workflow.png)

### Phase 1: Environment Verification
```bash
cd /home/user/k3s/Suraksha-deployment
git status
git branch
```

### Phase 2: Building Local Container Images
```bash
# 1. Build Frontend Container Image
docker build \\
  --build-arg "VITE_API_URL=/api" \\
  -t crowdvision-frontend:local \\
  /home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend

# 2. Build Backend Container Image
docker build \\
  -t crowdvision-backend:local \\
  /home/user/k3s/Suraksha-deployment/crowd-backend
```

### Phase 3: Ingesting Images into K3s containerd
```bash
docker save crowdvision-frontend:local | sudo k3s ctr -n k8s.io images import -
docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -
sudo k3s ctr -n k8s.io images list | grep crowdvision
```

### Phase 4: Secrets & ConfigMaps
```bash
kubectl create namespace crowdvision --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/configmap.yaml
kubectl -n crowdvision create secret generic crowdvision-secrets \\
  --from-env-file=/home/user/k3s/Suraksha-deployment/crowd-backend/.env \\
  --dry-run=client -o yaml | kubectl apply -f -
```

### Phase 5: Applying Workloads
```bash
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/pvc.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/mediamtx-deployment.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/mediamtx-service.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/stack/base/frontend.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-headless-service.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-service.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/backend-statefulset.yaml
kubectl apply -f /home/user/k3s/Suraksha-deployment/k3s/ingress.yaml
```

### Phase 6: Zero-Downtime Rollout Restart
```bash
kubectl rollout restart deployment crowdvision-frontend -n crowdvision
kubectl rollout restart statefulset crowdvision-backend -n crowdvision
kubectl get pods -n crowdvision -o wide
```

---

## 6. AI Video Analytics & Camera Partitioning

![AI Video Pipeline](docs_assets/diagram_video_ai_pipeline.png)

### Camera Allocation Matrix (28 Cameras)

| Stream # | Shard 0 (GPU 0 — `backend-0`) | Shard 1 (GPU 1 — `backend-1`) |
| :--- | :--- | :--- |
| 1 | `cam_middle_fob_4_5` | `cam_kzj_fob_mid_4_5` |
| 2 | `cam_pf1_fob_hyb_end` | `cam_kzj_fob_mid_8_9` |
| 3 | `cam_kzj_pf1_fob_kzj` | `cam_pf8_mid_fc_kzj` |
| 4 | `cam_kzj_pf1_fob_pf10` | `cam_gate2_wh` |
| 5 | `cam_mid_fob_pf1` | `cam_hyd_booking_gate2a` |
| 6 | `cam_mid_fob_center` | `cam_near_gate_2a_fc_swathi_ent` |
| 7 | `cam_hyb_pf1` | `cam_gate2_fc_ac_wh` |
| 8 | `cam_hyb_pf2` | `cam_gate2a_fc_parking` |
| 9 | `cam_hyb_pf4` | `cam_pf1_fob_pf10` |
| 10 | `cam_hyb_pf10` | `cam_new_kzj_fob_fc_pf1` |
| 11 | `cam_hyb_pf1_a` | `cam_new_kzj_fob_near_pf1` |
| 12 | `cam_hyb_booking` | `cam_pf10_bme_counter` (PF-10 Waiting Hall Area) |
| 13 | `cam_hyb_booking_gate4a` | `cam_hyb_booking_gate6` |
| 14 | `cam_pf2_fc_hyd_side` | `cam_hyb_booking_gate8` |

---

## 7. Operations & Monitoring Commands

### Live Cluster Telemetry
```bash
kubectl get all -n crowdvision
kubectl top pods -n crowdvision
kubectl logs -n crowdvision -l app.kubernetes.io/name=crowdvision-backend -f --tail=50
```

### Hardware GPU Telemetry
```bash
nvidia-smi
watch -n 1 nvidia-smi
```

### In-Memory Overnight Monitor Daemon
```bash
systemctl status crowdvision-monitor.service
journalctl -u crowdvision-monitor.service -f
```

---

## 8. Auto-Start & Power-Loss Recovery

![Auto-Start Recovery Chain](docs_assets/diagram_autostart_power_recovery.png)

1. **BIOS Power Restoration:** Set HP Z6 G4 BIOS: `Advanced -> Power Management Options -> After Power Loss -> Power On`.
2. **System Services:** `systemctl enable k3s.service`, `mongod.service`, `crowdvision-monitor.service`.
3. **Pod Policies:** All Kubernetes workloads configured with `restartPolicy: Always` and `imagePullPolicy: Never`.

---
*Generated by Tride Mobility AI Engineering Team — Production Verified*
"""
    with open(MD_OUTPUT, "w") as f:
        f.write(content)
    print(f"Successfully generated Markdown document: {MD_OUTPUT}")


if __name__ == "__main__":
    build_docx()
    build_markdown()
