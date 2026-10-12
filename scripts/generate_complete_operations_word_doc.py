#!/usr/bin/env python3
"""
Generate the Comprehensive Suraksha CrowdVision Project Architecture,
Deployment Operations Runbook, and Zero-Touch Self-Healing Word Document (.docx).

Outputs:
1. /home/user/k3s/Suraksha-deployment/docs/SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx
2. /home/user/k3s/Suraksha-deployment/scripts/SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx
3. /home/user/k3s/Suraksha-deployment/SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

BASE_DIR = "/home/user/k3s/Suraksha-deployment"
ASSETS_DIR = os.path.join(BASE_DIR, "docs_assets")
OUTPUT_DOCS = os.path.join(BASE_DIR, "docs", "SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx")
OUTPUT_SCRIPTS = os.path.join(BASE_DIR, "scripts", "SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx")
OUTPUT_ROOT = os.path.join(BASE_DIR, "SURAKSHA_PROJECT_DEPLOYMENT_OPERATIONS_AND_SELF_HEALING_GUIDE.docx")

def build_complete_word_doc():
    doc = docx.Document()

    # Configure Margins (1 inch)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Corporate Color Palette
    PRIMARY = RGBColor(24, 76, 120)        # Deep Navy Blue (#184C78)
    SECONDARY = RGBColor(41, 128, 185)     # Medium Ocean Blue (#2980B9)
    DARK_TEXT = RGBColor(30, 41, 59)       # Slate 800 (#1E293B)
    MUTED_TEXT = RGBColor(100, 116, 139)   # Slate 500 (#64748B)
    SUCCESS_COLOR = RGBColor(22, 101, 52)  # Emerald Green (#166534)
    WARNING_COLOR = RGBColor(180, 83, 9)   # Amber (#B45309)
    DANGER_COLOR = RGBColor(185, 28, 28)   # Crimson Red (#B91C1C)

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
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        set_font(run, "Calibri", 24, PRIMARY, bold=True)

        if subtitle:
            p2 = doc.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(18)
            run2 = p2.add_run(subtitle)
            set_font(run2, "Calibri", 12.5, SECONDARY, italic=True)

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 15, PRIMARY, bold=True)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 12.5, SECONDARY, bold=True)
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 11, DARK_TEXT, bold=True)
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
        bg_colors = {"info": "F0F9FF", "success": "F0FDF4", "warning": "FFFBEB", "danger": "FEF2F2"}
        border_colors = {"info": "0284C7", "success": "16A34A", "warning": "D97706", "danger": "DC2626"}
        title_colors = {"info": PRIMARY, "success": SUCCESS_COLOR, "warning": WARNING_COLOR, "danger": DANGER_COLOR}

        bg_hex = bg_colors.get(callout_type, "F8FAFC")
        b_hex = border_colors.get(callout_type, "64748B")
        t_color = title_colors.get(callout_type, PRIMARY)

        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.5)

        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>'))
        tcPr.append(parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="36" w:space="0" w:color="{b_hex}"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        '''))
        tcPr.append(parse_xml(f'''
            <w:tcMar {nsdecls("w")}>
                <w:top w:w="120" w:type="dxa"/><w:left w:w="180" w:type="dxa"/>
                <w:bottom w:w="120" w:type="dxa"/><w:right w:w="180" w:type="dxa"/>
            </w:tcMar>
        '''))

        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r_title = p.add_run(title)
        set_font(r_title, "Calibri", 10.5, t_color, bold=True)

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
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="0F172A"/>'))
        tcPr.append(parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="6" w:space="0" w:color="334155"/>
                <w:left w:val="single" w:sz="24" w:space="0" w:color="38BDF8"/>
                <w:bottom w:val="single" w:sz="6" w:space="0" w:color="334155"/>
                <w:right w:val="single" w:sz="6" w:space="0" w:color="334155"/>
            </w:tcBorders>
        '''))
        tcPr.append(parse_xml(f'''
            <w:tcMar {nsdecls("w")}>
                <w:top w:w="120" w:type="dxa"/><w:left w:w="160" w:type="dxa"/>
                <w:bottom w:w="120" w:type="dxa"/><w:right w:w="160" w:type="dxa"/>
            </w:tcMar>
        '''))

        lines = code_text.strip().split("\n")
        for i, line in enumerate(lines):
            p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.1
            run = p.add_run(line)
            set_font(run, "Consolas", 9, RGBColor(226, 232, 240))

        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_image_with_caption(img_path, caption):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.add_run().add_picture(img_path, width=Inches(6.5))

            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(10)
            run = p_cap.add_run(f"Figure: {caption}")
            set_font(run, "Calibri", 9.5, MUTED_TEXT, italic=True)

    # -------------------------------------------------------------------------
    # DOCUMENT COVER & HEADER METADATA
    # -------------------------------------------------------------------------
    add_title("SURAKSHA CROWDVISION", "Complete Project Architecture, Deployment Operations Runbook & Zero-Touch Self-Healing Guide")

    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Document Title:", "Suraksha CrowdVision: Project Deployment, Operations & Self-Healing Guide"),
        ("Document Version:", "Version 3.0 (Production Verified — Dual GPU Sharded & Zero-Touch Recovery)"),
        ("Target Audience:", "Executive Management, Operations Engineers, Junior Developers & Newcomers"),
        ("Hardware Workstation:", "HP Z6 G4 (Intel Xeon Platinum 48 vCPUs, 128 GB RAM, Dual NVIDIA RTX A4000)"),
        ("Software Platform:", "Ubuntu 24.04 LTS, K3s Kubernetes (v1.36.4), Traefik Ingress, FastAPI, YOLOv8/PET"),
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
    # SECTION 1: EXECUTIVE SUMMARY & MANAGEMENT OVERVIEW
    # -------------------------------------------------------------------------
    add_h1("1. Executive Summary & Management Overview (Non-IT Friendly)")
    add_body(
        "Suraksha CrowdVision is an enterprise-grade Edge AI safety and crowd density analytics platform deployed at major "
        "Indian Railway hubs (including Hyderabad Deccan and Kazipet stations). The platform continuously processes 28 live high-definition "
        "CCTV RTSP video feeds across foot-over-bridges (FOBs), concourses, ticket booking offices, platform waiting halls, and staircases. "
        "Using deep learning vision models (YOLOv8 + PET Density Estimator), it transforms raw video footage into actionable crowd intelligence, "
        "density heatmaps, and automated stampede warning alerts."
    )

    add_callout(
        "Business & Public Safety Value:",
        "• Stampede Prevention: Automatically detects hazardous congestion bottlenecks on pedestrian bridges before stampedes can occur.\n"
        "• Autonomous Monitoring: Replaces 24/7 human CCTV watching with automated, AI-driven audio/visual alarms.\n"
        "• Edge Operational Resilience: Executes 100% of computer vision and alert processing locally on station hardware without cloud latency.\n"
        "• Automated Reporting: Dispatches scheduled 3-hour executive health and streaming reports directly to management inboxes.",
        "success"
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_e2e_architecture.png"),
        "Suraksha CrowdVision End-to-End System Architecture (From Station Cameras to Dashboard)"
    )

    add_h2("1.1: System Availability & Outage Summary (Past 72-Hour Audit)")
    add_body(
        "An exhaustive audit of the host operating system, Kubernetes workloads, and systemd journals across the past 72 hours "
        "(09 October 10:02 to 12 October 10:02 IST) established the following baseline operational availability metrics:"
    )

    # 72-Hour Summary Table
    audit_tbl = doc.add_table(rows=6, cols=5)
    audit_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    a_headers = ["Outage #", "Power Loss / Crash Timestamp", "Power Restored / Reboot", "Total Down Time", "Event Classification"]
    for i, h in enumerate(a_headers):
        cell = audit_tbl.rows[0].cells[i]
        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>'))
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    outages_data = [
        ("Incident #1", "Fri 09 Oct, 14:45:01 IST", "Fri 09 Oct, 17:29:55 IST", "2 hr 44 min 54 sec", "Facility power cut / manual restart"),
        ("Incident #2", "Fri 09 Oct, 21:58:42 IST", "Sat 10 Oct, 08:07:07 IST", "10 hr 08 min 25 sec", "Overnight facility power cut (Off until morning)"),
        ("Incident #3", "Sun 11 Oct, 07:25:58 IST", "Sun 11 Oct, 10:40:27 IST", "3 hr 14 min 29 sec", "Sunday morning facility power trip"),
        ("Incident #4", "Sun 11 Oct, 11:38:18 IST", "Sun 11 Oct, 19:36:03 IST", "7 hr 57 min 45 sec", "Extended weekend power outage"),
        ("Incident #5", "Mon 12 Oct, 09:42:14 IST", "Mon 12 Oct, 09:53:18 IST", "11 min 04 sec", "Operating system hard freeze & reboot"),
    ]
    for row_idx, row_values in enumerate(outages_data, start=1):
        row = audit_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_values):
            cell = row.cells[col_idx]
            cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>'))
            run = cell.paragraphs[0].add_run(val)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0 or col_idx == 3))

    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    add_body(
        "Key Takeaway: The system achieved 47 hours 43 minutes of active compute uptime (66.28%) and experienced 24 hours 17 minutes "
        "of offline downtime (33.72%) entirely due to abrupt station power cuts without graceful shutdown records in the OS.",
        bold_prefix="Audit Finding: "
    )

    # -------------------------------------------------------------------------
    # SECTION 2: WORKSTATION HARDWARE PROFILE & INFRASTRUCTURE
    # -------------------------------------------------------------------------
    add_h1("2. Workstation Hardware Profile & Infrastructure")
    add_body(
        "CrowdVision runs on an enterprise HP Z6 G4 Workstation engineered for high-density GPU computing. The machine is configured "
        "with dual NVIDIA RTX A4000 GPUs, massive ECC system memory, and NVMe solid-state storage to guarantee multi-stream throughput."
    )

    hw_tbl = doc.add_table(rows=8, cols=3)
    hw_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    hw_headers = ["Subsystem", "Physical Specification", "Operational Function in CrowdVision"]
    for i, h in enumerate(hw_headers):
        cell = hw_tbl.rows[0].cells[i]
        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>'))
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    hw_data = [
        ("Host CPU", "Intel Xeon Platinum 8260 (24 Cores / 48 vCPUs @ 2.40 GHz)", "OpenCV multi-threaded RTSP decoding & FastAPI web serving"),
        ("System RAM", "128 GB DDR4 2933 MHz ECC (125 GiB Usable)", "Host frame ring buffers, in-memory rolling metrics buffer"),
        ("GPU 0", "NVIDIA RTX A4000 (16 GB GDDR6 ECC, PCIe 21:00.0)", "Dedicated to Shard 0 (crowdvision-backend-0): 14 Camera Streams"),
        ("GPU 1", "NVIDIA RTX A4000 (16 GB GDDR6 ECC, PCIe 2D:00.0)", "Dedicated to Shard 1 (crowdvision-backend-1): 14 Camera Streams"),
        ("Primary NVMe", "1 TB NVMe PCIe SSD (/dev/sda2, 32% used, 570 GB free)", "Host operating system, K3s images, YOLO weights, homography data"),
        ("Network NIC", "Dual Intel Gigabit Ethernet NICs (Static IP: 10.54.23.55)", "RTSP ingestion from station LAN + Traefik dashboard serving"),
        ("Cooling & PSU", "1000W 90% Efficient Power Supply + Active GPU Blowers", "Independent blower exhaust fans per GPU maintaining thermals"),
    ]
    for row_idx, row_values in enumerate(hw_data, start=1):
        row = hw_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_values):
            cell = row.cells[col_idx]
            cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>'))
            run = cell.paragraphs[0].add_run(val)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_h2("2.1: Dual GPU Sharding Architecture")
    add_body(
        "To prevent CUDA Out-Of-Memory (OOM) crashes and PCIe bus saturation, the 28 station cameras are partitioned symmetrically "
        "across both GPUs using a deterministic StatefulSet sharding architecture:"
    )
    add_bullet("Pod crowdvision-backend-0: Bound to GPU 0. Ingests and processes Shard 0 (14 Cameras: Platform 1, Main FOB, Booking Gate).", bold_prefix="Shard 0: ")
    add_bullet("Pod crowdvision-backend-1: Bound to GPU 1. Ingests and processes Shard 1 (14 Cameras: Platforms 2-10, Center FOB, Parking).", bold_prefix="Shard 1: ")

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_gpu_cpu_sharding.png"),
        "Dual GPU Hardware Sharding & Symmetric Workload Distribution"
    )

    # -------------------------------------------------------------------------
    # SECTION 3: KUBERNETES (K3S) & CONTAINER ARCHITECTURE
    # -------------------------------------------------------------------------
    add_h1("3. Kubernetes (K3s) & Container Architecture")
    add_body(
        "The application is orchestrated by K3s (v1.36.4+k3s1), a lightweight, production-grade Kubernetes engine running directly "
        "on the workstation node surakshaai. Microservices communicate over high-speed local virtual bridges with zero internet dependency."
    )

    # Workloads Table
    workloads_tbl = doc.add_table(rows=5, cols=5)
    workloads_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    w_headers = ["Workload Name", "Kubernetes Kind", "Replicas", "Assigned Compute", "Functional Purpose"]
    for i, h in enumerate(w_headers):
        cell = workloads_tbl.rows[0].cells[i]
        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>'))
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    w_data = [
        ("crowdvision-backend", "StatefulSet", "2 Replicas", "1x GPU each, 8-17 CPU", "Video frame ingestion, YOLO/PET AI inference, MongoDB sync"),
        ("crowdvision-frontend", "Deployment", "1 Replica", "0.2 CPU, 256 MiB RAM", "Nginx serving React/Vite UI, live dashboard & heatmaps"),
        ("mediamtx", "Deployment", "1 Replica", "0.5 CPU, 512 MiB RAM", "Low-latency RTSP-to-WebRTC/HLS video streaming proxy"),
        ("crowdvision-data", "PVC (HostPath)", "1 Volume", "Host NVMe Disk", "Persistent storage for weights (yolov8m.pt) and calibration"),
    ]
    for row_idx, row_values in enumerate(w_data, start=1):
        row = workloads_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_values):
            cell = row.cells[col_idx]
            cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>'))
            run = cell.paragraphs[0].add_run(val)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_k3s_cluster_architecture.png"),
        "K3s Cluster Topology, Pod Lifecycle & Network Routing"
    )

    # -------------------------------------------------------------------------
    # SECTION 4: MONITORING, SYSTEMD & IN-MEMORY ANALYTICS
    # -------------------------------------------------------------------------
    add_h1("4. Monitoring, Systemd Daemons & In-Memory Analytics")
    add_body(
        "To ensure complete visibility into system health without risking solid-state drive exhaustion, an automated in-memory "
        "monitoring daemon runs continuously as a systemd background service:"
    )
    add_bullet("Service Unit: /etc/systemd/system/crowdvision-monitor.service", bold_prefix="Systemd Daemon: ")
    add_bullet("Executable Script: /home/user/Downloads/overnight_monitor.py", bold_prefix="Script Location: ")
    add_bullet("Cadence: Comprehensive HTML email report dispatched every 3 hours (10,800s) to management.", bold_prefix="Reporting: ")

    add_callout(
        "Zero Local File Logging Policy:",
        "Continuous high-speed CCTV inference generates massive log output that would wear out workstation SSDs within months. "
        "The overnight monitor enforces a strict Zero Local File Logging Policy: all metrics, reconnect events, GPU temperatures, "
        "and camera statuses are maintained in RAM using rolling ring buffers (collections.deque). Reports and multi-panel visual graphs "
        "are rendered in-memory and emailed directly without writing files to disk.",
        "info"
    )

    add_h2("4.1: Power Downtime & Camera Freeze Duration Tracking")
    add_body(
        "The monitoring daemon features advanced persistent auditing capabilities:"
    )
    add_bullet("Power Down Time Audit: Automatically reads journalctl --list-boots to calculate exact offline outage times across previous power cuts.", bold_prefix="Downtime Tracker: ")
    add_bullet("Camera Freeze Duration: Whenever an RTSP stream drops for >15 seconds (Stream Stall), an active freeze timer begins. Total freeze duration is accumulated per camera and across the fleet.", bold_prefix="Freeze Tracker: ")
    add_bullet("Hardware Warnings: Detects extreme GPU overheating (>85°C/93°C) and kernel Machine Check Exceptions (MCE RAM errors).", bold_prefix="Thermal Alerts: ")

    # -------------------------------------------------------------------------
    # SECTION 5: AUTONOMOUS FREEZE RECOVERY & ZERO-TOUCH SELF-HEALING
    # -------------------------------------------------------------------------
    add_h1("5. Autonomous Freeze Recovery & Zero-Touch Self-Healing Blueprint")
    add_body(
        "Because the workstation operates in an unmanned station room where physical access is impossible during night hours or weekends, "
        "the architecture implements a multi-tiered autonomous self-healing strategy:"
    )

    add_callout(
        "The Unattended Recovery Challenge:",
        "When an edge system freezes with no person present on-site, it must be capable of autonomous self-detection and self-reboot. "
        "The solution is engineered across three independent fault domains: Container Level, Operating System Level, and Hardware Level.",
        "warning"
    )

    add_h2("5.1: Tier 1 — Container & Application Self-Healing")
    add_bullet("Kubernetes Liveness Probes: K3s continuously tests /api/health. If video processing stalls for >90s, K3s terminates the container and boots a clean instance automatically.", bold_prefix="Pod Auto-Restart: ")
    add_bullet("OpenCV Socket Timeout: Injected environment variable OPENCV_FFMPEG_CAPTURE_OPTIONS='stimeout=5000000' forces network reads to abort after 5s of silence, preventing C++ thread deadlocks.", bold_prefix="Socket Protection: ")

    add_h2("5.2: Tier 2 — Operating System Automatic Panic & Reboot")
    add_body(
        "If a GPU driver locks up or the kernel experiences a hard freeze, Linux kernel sysctl rules force an immediate automated reboot:"
    )
    add_code_block(
        "# /etc/sysctl.d/99-auto-reboot.conf\n"
        "kernel.panic = 10\n"
        "kernel.hung_task_panic = 1\n"
        "kernel.hung_task_timeout_secs = 120\n"
        "kernel.panic_on_oops = 1"
    )
    add_body("Result: If any kernel thread is frozen for more than 120 seconds, the kernel triggers a panic and automatically reboots the server after 10 seconds.")

    add_h2("5.3: Tier 3 — HP Hardware Power Recovery & Intel AMT Remote Reset")
    add_body(
        "To guarantee immediate recovery when station facility electricity returns after blackouts:"
    )
    add_bullet("BIOS After Power Loss: In HP BIOS Setup (F10) -> Advanced -> Power-On Options -> After Power Loss, set to 'Power On'. The workstation powers on automatically the moment mains electricity returns.", bold_prefix="BIOS Setting: ")
    add_bullet("Intel AMT / vPro Remote Reset: The HP Z6 G4 includes Out-of-Band remote management. Remote engineers can access https://10.54.23.55:16993 to execute cold power cycles over the network even if the OS is frozen.", bold_prefix="Remote Management: ")

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_autostart_power_recovery.png"),
        "Automated Multi-Tier Recovery & Power Restoration Lifecycle"
    )

    # -------------------------------------------------------------------------
    # SECTION 6: OPERATIONS GUIDE FOR JUNIORS & NEWCOMERS
    # -------------------------------------------------------------------------
    add_h1("6. Step-by-Step Operations Guide for Juniors & Newcomers")
    add_body(
        "This section is designed as a standalone operational runbook so any team member can verify, maintain, and deploy updates "
        "without senior engineer supervision."
    )

    add_h2("6.1: Daily Morning Health Check (5-Minute Routine)")
    add_code_block(
        "# 1. Check K3s Node Status (Must show 'Ready')\n"
        "kubectl get nodes\n\n"
        "# 2. Check All Running Pods (All crowdvision pods must show '1/1 Running')\n"
        "kubectl get pods -n crowdvision\n\n"
        "# 3. Check Dual GPU Status & Temperatures (Both RTX A4000 GPUs must be visible)\n"
        "nvidia-smi\n\n"
        "# 4. Check Overnight Monitor Daemon Status\n"
        "systemctl status crowdvision-monitor.service --no-pager"
    )

    add_h2("6.2: How to Deploy Backend Code Changes")
    add_body("Follow these exact steps when updating Python files in crowd-backend:")
    add_code_block(
        "# Step 1: Navigate to backend directory\n"
        "cd /home/user/k3s/Suraksha-deployment/crowd-backend\n\n"
        "# Step 2: Build the new Docker image\n"
        "docker build -t crowdvision-backend:local .\n\n"
        "# Step 3: Import image into K3s containerd\n"
        "docker save crowdvision-backend:local | sudo k3s ctr -n k8s.io images import -\n\n"
        "# Step 4: Restart the backend StatefulSet\n"
        "kubectl rollout restart statefulset/crowdvision-backend -n crowdvision\n"
        "kubectl rollout status statefulset/crowdvision-backend -n crowdvision\n\n"
        "# Step 5: Verify backend startup logs\n"
        "kubectl logs crowdvision-backend-0 -n crowdvision -f --tail=50"
    )

    add_h2("6.3: How to Deploy Frontend Code Changes")
    add_body("Follow these exact steps when updating UI / React code in Crowd_Vision_Frontend:")
    add_code_block(
        "# Step 1: Navigate to frontend directory\n"
        "cd /home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend\n\n"
        "# Step 2: Build the frontend Docker image\n"
        "docker build --build-arg \"VITE_API_URL=/api\" -t crowdvision-frontend:local .\n\n"
        "# Step 3: Import into K3s containerd\n"
        "docker save crowdvision-frontend:local | sudo k3s ctr -n k8s.io images import -\n\n"
        "# Step 4: Restart the frontend deployment\n"
        "kubectl rollout restart deployment/crowdvision-frontend -n crowdvision\n"
        "kubectl rollout status deployment/crowdvision-frontend -n crowdvision"
    )

    add_image_with_caption(
        os.path.join(ASSETS_DIR, "diagram_k3s_deployment_workflow.png"),
        "Standard Build, Import, and Rolling Restart Workflow"
    )

    add_h2("6.4: Safe Service Restart Cheatsheet")
    # Cheatsheet Table
    cs_tbl = doc.add_table(rows=6, cols=3)
    cs_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cs_headers = ["Action Required", "Command Line String", "Expected Impact"]
    for i, h in enumerate(cs_headers):
        cell = cs_tbl.rows[0].cells[i]
        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>'))
        run = cell.paragraphs[0].add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    cs_data = [
        ("Restart Backend AI Only", "kubectl rollout restart statefulset/crowdvision-backend -n crowdvision", "~15s rolling restart per pod"),
        ("Restart Web Dashboard Only", "kubectl rollout restart deployment/crowdvision-frontend -n crowdvision", "~5s momentary UI disconnect"),
        ("Restart Video Proxy Only", "kubectl rollout restart deployment/mediamtx -n crowdvision", "~5s video player reconnect"),
        ("Restart Monitor Daemon", "pkill -f overnight_monitor.py", "0s (Systemd restarts process in 10s)"),
        ("Restart Entire K3s Engine", "sudo systemctl restart k3s.service", "~30s total cluster reload"),
    ]
    for row_idx, row_values in enumerate(cs_data, start=1):
        row = cs_tbl.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_values):
            cell = row.cells[col_idx]
            cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>'))
            run = cell.paragraphs[0].add_run(val)
            set_font(run, "Calibri", 9.5, DARK_TEXT, bold=(col_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------------------
    # SECTION 7: TROUBLESHOOTING PLAYBOOKS & EMERGENCY RUNBOOK
    # -------------------------------------------------------------------------
    add_h1("7. Troubleshooting Playbooks & Emergency Runbook")

    add_h2("Playbook A: Camera Stream Frozen / Stalling")
    add_body("Symptom: Monitor email reports stream stall on camera (e.g. cam_hyb_pf1_a); video shows frozen frame in web dashboard.")
    add_bullet("Step 1: Test RTSP connectivity from terminal using ffprobe: ffprobe -v error rtsp://user:pass@camera-ip:554/stream", bold_prefix="Diagnostics: ")
    add_bullet("Step 2: If ffprobe hangs or times out, the camera or station switch port is offline. Contact CCTV electrical staff.", bold_prefix="Network Check: ")
    add_bullet("Step 3: If ffprobe succeeds cleanly, restart the pod: kubectl delete pod crowdvision-backend-0 -n crowdvision", bold_prefix="Resolution: ")

    add_h2("Playbook B: GPU Overheating & Thermal Throttling (98°C)")
    add_body("Symptom: Monitor email warns GPU 0 Critical Overheat (98°C); inference slows down significantly or host hard locks.")
    add_bullet("Step 1: Inspect live GPU temperatures: nvidia-smi -q -d TEMPERATURE,FAN", bold_prefix="Check Temp: ")
    add_bullet("Step 2: Physically clean the front air intake dust filter of the HP Z6 G4 Workstation. Ensure blower fans are unobstructed.", bold_prefix="Physical Action: ")
    add_bullet("Step 3: If access is delayed, throttle inference load in k3s/configmap.yaml: increase PET_INFERENCE_INTERVAL from 3 to 6.", bold_prefix="Load Reduction: ")

    add_h2("Playbook C: Hardware MCE Memory Error (RAM Repair)")
    add_body("Symptom: Kernel logs report recurring Machine Check Exceptions: EDAC skx MC0: CPU 0: ADDR 0x46e6fb800.")
    add_bullet("Diagnosis: Physical memory cell defect at address 0x46e6fb800 on Socket 0 / Memory Controller 0.", bold_prefix="Root Cause: ")
    add_bullet("Resolution: Schedule hardware maintenance. Power down workstation, open HP Z6 G4 side door, and reseat or replace DIMM in CPU0 Slot 1.", bold_prefix="Action: ")

    # -------------------------------------------------------------------------
    # SECTION 8: QUICK REFERENCE CHEATSHEET
    # -------------------------------------------------------------------------
    add_h1("8. Quick Reference Cheatsheet")
    add_bullet("Live Web Dashboard: http://10.54.23.55/", bold_prefix="Dashboard URL: ")
    add_bullet("Interactive Swagger API Docs: http://10.54.23.55/docs", bold_prefix="API Docs: ")
    add_bullet("Intel AMT Remote Management: https://10.54.23.55:16993", bold_prefix="Remote Console: ")
    add_bullet("Backend Source Directory: /home/user/k3s/Suraksha-deployment/crowd-backend", bold_prefix="Backend Path: ")
    add_bullet("Frontend Source Directory: /home/user/k3s/Suraksha-deployment/Crowd_Vision_Frontend", bold_prefix="Frontend Path: ")
    add_bullet("K3s Manifests Directory: /home/user/k3s/Suraksha-deployment/k3s", bold_prefix="K3s Manifests: ")
    add_bullet("Overnight Monitor Script: /home/user/Downloads/overnight_monitor.py", bold_prefix="Monitor Script: ")

    # Save to all target locations
    os.makedirs(os.path.dirname(OUTPUT_DOCS), exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_SCRIPTS), exist_ok=True)

    doc.save(OUTPUT_DOCS)
    doc.save(OUTPUT_SCRIPTS)
    doc.save(OUTPUT_ROOT)

    print(f"[SUCCESS] Generated Word Document in:")
    print(f"  1. {OUTPUT_DOCS}")
    print(f"  2. {OUTPUT_SCRIPTS}")
    print(f"  3. {OUTPUT_ROOT}")

if __name__ == "__main__":
    build_complete_word_doc()
