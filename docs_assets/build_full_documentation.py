"""
Comprehensive Word Document Generator for Suraksha / CrowdVision Platform
Generates an executive-grade .docx document with professional styling,
embedded 300-DPI diagrams, structured tables, callouts, and exhaustive technical details.
"""
import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

DOCX_OUTPUT_PATH = "/home/user/k3s/Suraksha-deployment/Suraksha_CrowdVision_End_To_End_Documentation.docx"
ASSETS_DIR = "/home/user/k3s/Suraksha-deployment/docs_assets"

# Brand Color Palette
HEX_PRIMARY = "1E3A8A"      # Deep Royal Blue
HEX_SECONDARY = "0284C7"    # Sky Blue
HEX_ACCENT = "D97706"       # Amber / Warning
HEX_DARK = "0F172A"         # Slate Dark (Body)
HEX_MUTED = "64748B"        # Slate Muted
HEX_LIGHT_BG = "F8FAFC"     # Light Slate Background
HEX_ALT_ROW = "F1F5F9"      # Table Alternating Row
HEX_BORDER = "CBD5E1"       # Subtle Border
HEX_CRITICAL = "DC2626"     # Critical Red
HEX_SUCCESS = "16A34A"      # Success Green

COLOR_PRIMARY = RGBColor(30, 58, 138)
COLOR_SECONDARY = RGBColor(2, 132, 199)
COLOR_ACCENT = RGBColor(217, 119, 6)
COLOR_DARK = RGBColor(15, 23, 42)
COLOR_MUTED = RGBColor(100, 116, 139)

def set_cell_background(cell, hex_color):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
    for side, border in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        if border:
            el = parse_xml(f'<w:{side} {nsdecls("w")} w:val="{border.get("val","single")}" w:sz="{border.get("sz",4)}" w:space="0" w:color="{border.get("color",HEX_BORDER)}"/>')
            tcBorders.append(el)
        else:
            el = parse_xml(f'<w:{side} {nsdecls("w")} w:val="none"/>')
            tcBorders.append(el)
    tcPr.append(tcBorders)

def add_callout(doc, text, title="KEY ARCHITECTURAL HIGHLIGHT", alert_type="info"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.5)

    cell = table.cell(0, 0)
    bg = HEX_LIGHT_BG
    border_color = HEX_PRIMARY if alert_type == "info" else (HEX_ACCENT if alert_type == "warning" else HEX_CRITICAL)
    if alert_type == "warning":
        bg = "FFFBEB"
    elif alert_type == "danger":
        bg = "FEF2F2"

    set_cell_background(cell, bg)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=160)
    set_cell_borders(cell, left={"val": "single", "sz": 24, "color": border_color},
                           top={"val": "single", "sz": 4, "color": HEX_BORDER},
                           bottom={"val": "single", "sz": 4, "color": HEX_BORDER},
                           right={"val": "single", "sz": 4, "color": HEX_BORDER})

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r_title = p.add_run(f"[{title}]\n")
    r_title.bold = True
    r_title.font.size = Pt(9.5)
    r_title.font.color.rgb = COLOR_PRIMARY if alert_type == "info" else (COLOR_ACCENT if alert_type == "warning" else RGBColor(220, 38, 38))

    r_text = p.add_run(text)
    r_text.font.size = Pt(9.5)
    r_text.font.color.rgb = COLOR_DARK
    doc.add_paragraph() # spacing

def format_table(table, col_widths, headers, data):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = Inches(col_widths[i])
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], HEX_PRIMARY)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.bold = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for row_idx, row_data in enumerate(data):
        row_cells = table.add_row().cells
        bg_color = HEX_ALT_ROW if row_idx % 2 == 1 else "FFFFFF"
        for i, val in enumerate(row_data):
            row_cells[i].width = Inches(col_widths[i])
            row_cells[i].text = str(val)
            set_cell_background(row_cells[i], bg_color)
            set_cell_margins(row_cells[i], top=100, bottom=100, left=120, right=120)
            set_cell_borders(row_cells[i], top={"val": "single", "sz": 4, "color": HEX_BORDER},
                                          bottom={"val": "single", "sz": 4, "color": HEX_BORDER},
                                          left={"val": "single", "sz": 4, "color": HEX_BORDER},
                                          right={"val": "single", "sz": 4, "color": HEX_BORDER})
            p = row_cells[i].paragraphs[0]
            for run in p.runs:
                run.font.size = Pt(8.5)
                run.font.color.rgb = COLOR_DARK
    doc_add_spacing = docx.Document()

def build_document():
    doc = docx.Document()

    # Configure Margins (0.75 in / 54pt)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Configure Base Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Arial'
    normal_style.font.size = Pt(10)
    normal_style.font.color.rgb = COLOR_DARK
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(4)

    # --- COVER SECTION ---
    p_pre = doc.add_paragraph()
    p_pre.paragraph_format.space_before = Pt(36)
    p_pre.paragraph_format.space_after = Pt(4)
    r_badge = p_pre.add_run("OFFICIAL TECHNICAL & OPERATIONAL DOCUMENTATION")
    r_badge.font.size = Pt(11)
    r_badge.bold = True
    r_badge.font.color.rgb = COLOR_SECONDARY

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("Suraksha AI / CrowdVision Platform\nEnd-to-End Architecture, Application Flow & Operational Documentation")
    r_title.font.size = Pt(24)
    r_title.bold = True
    r_title.font.color.rgb = COLOR_PRIMARY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(24)
    r_sub = p_sub.add_run("Real-Time Footfall Analytics, Multi-Regime Deep Learning Inference, Stampede Early Warning, Automated Incident Response, and Production K3s Edge Deployment")
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = COLOR_MUTED

    # Meta Table
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    meta_table.columns[0].width = Inches(2.2)
    meta_table.columns[1].width = Inches(4.3)
    meta_items = [
        ("Deployment Sites", "Secunderabad Junction (SC), Kazipet (KZJ), Sanchalan Bhavan Control Room"),
        ("System Release", "v1.0.0 Production Baseline (GPU-Accelerated Hybrid Edge/Cloud)"),
        ("Core Models", "YOLOv8m (Head Detection) + PET Transformer (Density & Point Queries)"),
        ("Orchestration & Ingress", "K3s Lightweight Kubernetes, Traefik Ingress, MediaMTX RTSP Proxy"),
        ("Target Stakeholders", "Station Directors, Railway Protection Force (RPF), Commercial Ops, DevOps & AI Engineers")
    ]
    for idx, (label, val) in enumerate(meta_items):
        r_c1 = meta_table.cell(idx, 0)
        r_c2 = meta_table.cell(idx, 1)
        r_c1.text = label
        r_c2.text = val
        set_cell_background(r_c1, HEX_LIGHT_BG)
        set_cell_background(r_c2, "FFFFFF")
        set_cell_margins(r_c1, top=80, bottom=80, left=100, right=100)
        set_cell_margins(r_c2, top=80, bottom=80, left=100, right=100)
        set_cell_borders(r_c1, top={"val":"single","sz":4,"color":HEX_BORDER}, bottom={"val":"single","sz":4,"color":HEX_BORDER},
                               left={"val":"single","sz":4,"color":HEX_BORDER}, right={"val":"single","sz":4,"color":HEX_BORDER})
        set_cell_borders(r_c2, top={"val":"single","sz":4,"color":HEX_BORDER}, bottom={"val":"single","sz":4,"color":HEX_BORDER},
                               left={"val":"single","sz":4,"color":HEX_BORDER}, right={"val":"single","sz":4,"color":HEX_BORDER})
        r_c1.paragraphs[0].runs[0].bold = True
        r_c1.paragraphs[0].runs[0].font.size = Pt(9)
        r_c2.paragraphs[0].runs[0].font.size = Pt(9)

    doc.add_page_break()

    # --- TABLE OF CONTENTS SUMMARY ---
    h1 = doc.add_heading("Table of Contents", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY
    
    toc_items = [
        "1. Executive Summary & Operational Scope",
        "2. End-to-End System Architecture (Logical & Physical)",
        "3. High-Throughput Video Ingestion & Stream Decoupling",
        "4. Deep Learning & Computer Vision Core (YOLOv8 + PET Transformer)",
        "5. Adaptive Regime-Based Fusion & Count Calibration",
        "6. Optical Flow, Crowd Dynamics & Stampede Early Warning",
        "7. Zone-Level Spatial Aggregation & Conservative Risk Modeling",
        "8. Automated Notification & Operational Actioning Engines",
        "9. Real-Time Frontend Experience & Interactive SVG Floor Plan",
        "10. Database Schema, Storage Lifecycle & TTL Data Retention",
        "11. Production Infrastructure Topology, K3s & NVIDIA GPU Toolkit",
        "12. Production Runbook, Health Verification & Maintenance Procedures"
    ]
    for item in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(item)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = COLOR_PRIMARY

    doc.add_page_break()

    # --- SECTION 1 ---
    h1 = doc.add_heading("1. Executive Summary & Operational Scope", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "The Suraksha AI (CrowdVision) platform is a high-availability, mission-critical computer vision and spatial "
        "crowd intelligence system engineered specifically for major Indian Railway transit hubs, including Secunderabad "
        "Junction (SC), Hyderabad, and Kazipet (KZJ). Designed to operate in high-density, rapidly fluctuating transit environments, "
        "the system continuously ingests dozens of live CCTV/RTSP camera feeds across critical Foot Over Bridges (FOBs), "
        "island platforms, station stairways, concourses, and ticket counters."
    )

    doc.add_paragraph(
        "The primary mission of the platform is the prevention of crowd surges, dangerous bottlenecks, and stampede risks, "
        "while providing station masters, commercial controllers, and Railway Protection Force (RPF) personnel with real-time "
        "situational awareness and automated incident actioning. Suraksha replaces subjective, error-prone visual inspection "
        "with sub-second quantitative intelligence: continuous head detection, deep spatial density mapping, crowd velocity tracking, "
        "and multi-camera zone fusion."
    )

    add_callout(
        doc,
        "Suraksha AI processes up to 40 concurrent HD RTSP streams per edge workstation with sub-500ms latency. "
        "Through centralized GPU batching and model pooling, GPU VRAM requirements are reduced by over 95%, allowing "
        "full production deployment on a single NVIDIA workstation GPU (RTX 3080/4090 or A4000).",
        "MISSION OBJECTIVE & HARDWARE FOOTPRINT",
        "info"
    )

    doc.add_heading("Key Operational Capabilities", level=2).style.font.color.rgb = COLOR_SECONDARY
    capabilities = [
        ("Sub-Second Crowd Counting & Density Estimation", "Simultaneous multi-stream detection using YOLOv8m for sparse-to-medium heads and Point-query Efficient Transformer (PET) for extreme crowd clustering."),
        ("Adaptive Regime-Based Blending", "Dynamically arbitrates model weights across SPARSE (<15 pax), LOW (15-50 pax), MEDIUM (50-120 pax), and HIGH (>120 pax) regimes to eliminate systematic bias."),
        ("Stampede & Compression Warning", "Computes negative spatial divergence of dense optical flow fields to detect physical crowd compression up to minutes before stampede initiation."),
        ("Interactive SVG Floor Plan Maps", "Visualizes real-time crowd distribution across Hyderabad and Kazipet FOB spans with percentage-based responsive bounding geometries."),
        ("Island Platform Congestion Forecast", "Evaluates multi-train arrival schedules to predict footfall spikes on narrow island platforms 90 minutes before arrival."),
        ("Automated Multi-Channel Notifications", "Dispatches instant WhatsApp alerts via MSG91 to railway authorities and synthesizes automated multilingual voice announcements (Hindi/Telugu/English) stored on AWS S3.")
    ]
    for title, desc in capabilities:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(3)
        r1 = p.add_run(f"• {title}: ")
        r1.bold = True
        r1.font.color.rgb = COLOR_PRIMARY
        r2 = p.add_run(desc)
        r2.font.color.rgb = COLOR_DARK

    # --- SECTION 2 ---
    h1 = doc.add_heading("2. End-to-End System Architecture", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "The architecture is organized as a decoupled, multi-tier distributed pipeline spanning Edge Hardware "
        "(on-premise CCTV cameras and GPU compute node at Sanchalan Bhavan/Station), Operational Persistence (MongoDB), "
        "and External Cloud Communication Gateways (MSG91, AWS S3, RapidAPI). The application flow eliminates bottlenecks "
        "by isolating real-time video capture from compute-intensive deep learning forward passes."
    )

    img_p = doc.add_paragraph()
    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_picture(f"{ASSETS_DIR}/diagram_e2e_architecture.png", width=Inches(6.5))
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cap = cap_p.add_run("Figure 1: Suraksha / CrowdVision High-Level End-to-End System Architecture")
    r_cap.font.size = Pt(8.5)
    r_cap.italic = True
    r_cap.font.color.rgb = COLOR_MUTED

    doc.add_paragraph(
        "Communication between components is strictly standardized across environments:"
    )

    arch_headers = ["Layer", "Primary Technology", "Protocol / Ingress", "Responsibilities"]
    arch_data = [
        ["Edge Ingestion", "MediaMTX / OpenCV Decoupled Loops", "RTSP over TCP/UDP (Port 8554)", "Pulls H.264/H.265 CCTV feeds; maintains zero-backlog latest frame buffer; auto-reconnect."],
        ["GPU Inference", "PyTorch, CUDA 11.8+, TensorRT", "BatchedInferenceService (IPC/Queue)", "Dynamic micro-batching (batch=16); YOLOv8m forward pass + PET Transformer density point queries."],
        ["Business & Fusion", "FastAPI (Python 3.11+)", "Internal In-Memory Async Queues", "Regime arbitration, count calibration, optical flow divergence, zone-level aggregation."],
        ["Real-Time Gateway", "FastAPI WebSockets / Starlette", "WSS (/api/ws/analytics, /api/ws/zones/*)", "Sub-second broadcast of live zone metrics, alert triggers, and upcoming train schedules."],
        ["Persistence", "MongoDB (Motor Async Driver)", "TCP Port 27017 (Batched Worker)", "Micro-batched flush every 5s; stores time-series metrics, alert incidents, and user metadata."],
        ["External Gateways", "MSG91, AWS S3, RapidAPI", "HTTPS REST APIs (TLS 1.3)", "WhatsApp alert dispatch, multi-lingual TTS MP3 storage, and real-time live train schedule synchronization."],
        ["Operations UI", "React 18, TypeScript, Vite, Tailwind", "HTTPS (Port 443) + WSS", "Responsive SVG FOB map rendering, 1-hour rolling footfall chart with LocalStorage cache, alert console."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.2, 1.6, 1.4, 2.3], arch_headers, arch_data)
    doc.add_paragraph()

    # --- SECTION 3 ---
    h1 = doc.add_heading("3. High-Throughput Video Ingestion & Stream Decoupling", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "A critical vulnerability in traditional computer vision deployments is frame backlog: when deep learning models "
        "run slower than incoming camera frame rates (e.g. 25-30 FPS), buffer queues build up in memory, introducing fatal multi-minute "
        "delays in alert generation. Suraksha solves this through a completely decoupled, dual-threaded architecture within "
        "the RTSPWorker service."
    )

    doc.add_heading("Decoupled Capture vs. Inference Architecture", level=2).style.font.color.rgb = COLOR_SECONDARY

    doc.add_paragraph(
        "Each active RTSP camera feed is allocated an independent, long-running worker consisting of two decoupled concurrent threads:"
    )

    p_c1 = doc.add_paragraph()
    p_c1.paragraph_format.left_indent = Inches(0.25)
    r1 = p_c1.add_run("1. High-Speed Frame Capture Thread (_connect_and_process): ")
    r1.bold = True
    p_c1.add_run(
        "Continuously reads raw frames from the RTSP source at the camera's native speed (25-30 FPS). Upon decoding a valid frame, "
        "it immediately updates an atomic, thread-safe memory pointer (_latest_raw_frame) and timestamp (_latest_capture_timestamp). "
        "Older frames are overwritten instantly without queueing. This guarantees zero frame lag under all operating loads."
    )

    p_c2 = doc.add_paragraph()
    p_c2.paragraph_format.left_indent = Inches(0.25)
    r2 = p_c2.add_run("2. Cadenced AI Sampling Loop (_ai_loop): ")
    r2.bold = True
    p_c2.add_run(
        "Executes at the configured target cadence (default 1.0 FPS). On each interval, it peeks at the freshest raw frame "
        "using get_latest_frame_with_metadata(). It validates frame freshness (age < 500ms) and dispatches the frame to the central "
        "batched inference queue without stalling the capture loop."
    )

    doc.add_heading("Resilience: Circuit Breaker & Exponential Backoff", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Station network conditions can suffer from temporary packet drops, power interruptions, or switch reboots. RTSPWorker "
        "incorporates an enterprise-grade CircuitBreaker utility:"
    )

    cb_headers = ["State", "Trigger Condition", "Worker Behavior", "Recovery Strategy"]
    cb_data = [
        ["CLOSED", "Normal stream operation", "Reads frames continuously; resets failure counters.", "Transitions to OPEN if consecutive failures exceed threshold (default 5)."],
        ["OPEN", "Consecutive camera decode failures", "Halts capture loop; releases OpenCV VideoCapture descriptors; prevents CPU thrashing.", "Enters cooldown window; applies ExponentialBackoff (2s, 4s, 8s... up to 60s)."],
        ["HALF-OPEN", "Cooldown interval expired", "Attempts a single test probe to reopen RTSP socket.", "If test frame is successfully decoded, state reverts to CLOSED; otherwise backoff doubles."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.1, 1.6, 2.0, 1.8], cb_headers, cb_data)
    doc.add_paragraph()

    # --- SECTION 4 ---
    h1 = doc.add_heading("4. Deep Learning & Computer Vision Core", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "Traditional single-model crowd analytics platforms fail in real-world railway environments because crowd densities "
        "vary radically by location and time—from sparse midnight platforms to crush-load festival peaks during Sabarimala or Diwali. "
        "Suraksha employs a synergistic dual-model architecture combining YOLOv8m object detection with the Point-query Efficient "
        "Transformer (PET)."
    )

    img_p = doc.add_paragraph()
    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_picture(f"{ASSETS_DIR}/diagram_inference_pipeline.png", width=Inches(6.5))
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cap = cap_p.add_run("Figure 2: Computer Vision Inference Pipeline (YOLOv8 + PET Dual-Model Fusion)")
    r_cap.font.size = Pt(8.5)
    r_cap.italic = True
    r_cap.font.color.rgb = COLOR_MUTED

    doc.add_heading("YOLOv8m: Object Detection & Spatial Occupancy", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "YOLOv8m (You Only Look Once, medium variant) is optimized for head and upper-body detection. In sparse-to-medium crowd "
        "scenes, individual passengers exhibit distinct boundaries. YOLO generates discrete bounding boxes with bounding box coordinates, "
        "confidence scores, and computes the frame's total Spatial Occupancy Ratio (the percentage of active pedestrian ROI covered by "
        "detected human bounding boxes). Occupancy ratio serves as a critical gating factor for regime switching."
    )

    doc.add_heading("PET: Point-Query Efficient Transformer", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Under extreme congestion (over 100-200 passengers per camera view), severe occlusions prevent YOLO from isolating individual "
        "heads. Earlier iterations attempted using CSRNet (Congested Scene Recognition Network), but production testing demonstrated "
        "unacceptable blurriness and false positives around luggage and platform infrastructure. The system was upgraded to the "
        "PET (Point-query Efficient Transformer) model."
    )
    doc.add_paragraph(
        "PET models crowd density as direct point queries, generating sharp, localized coordinate predictions and high-fidelity "
        "density maps. A 2D Gaussian kernel (sigma=15.0) is applied over point predictions to render density maps. To balance GPU load, "
        "PET inference is cadenced to run every 3rd frame (pet_inference_interval=3) while intermediate frames utilize YOLO forward passes "
        "coupled with cached PET spatial baselines."
    )

    # --- SECTION 5 ---
    h1 = doc.add_heading("5. Adaptive Regime-Based Fusion & Count Calibration", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "The core mathematical innovation in Suraksha is its adaptive fusion algorithm (compute_fusion in utils/fusion.py). "
        "Rather than relying strictly on a single detector or static averaging, the system dynamically classifies each frame into one "
        "of four density regimes based on combined headcount estimates and YOLO spatial occupancy:"
    )

    regime_headers = ["Regime", "Max Count Range", "Occupancy Ratio", "PET Weight", "YOLO Weight", "Fusion Logic Rationale"]
    regime_data = [
        ["SPARSE", "< 15 pax", "< 5% (<0.05)", "0.50", "0.50", "Balanced blend; YOLO floor guard active to prevent undercounting."],
        ["LOW", "15 - 50 pax", "< 5% (<0.05)", "0.60", "0.40", "PET begins taking precedence; handles mild overlapping boundaries."],
        ["MEDIUM", "50 - 120 pax", "5% - 15% (0.05-0.15)", "0.75", "0.25", "PET dominates; YOLO provides boundary stabilization."],
        ["HIGH", "> 120 pax", "15% - 30% (0.15-0.30)", "0.95", "0.05", "Extreme occlusion; PET provides 95% of prediction weight."]
    ]
    format_table(doc.add_table(rows=1, cols=6), [0.9, 1.1, 1.2, 0.8, 0.8, 1.7], regime_headers, regime_data)
    doc.add_paragraph()

    doc.add_heading("Dense-Scene PET Guard", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "In severe surge conditions (e.g. general compartment boarding), blending with YOLO can cause an artificial downward drag "
        "on the count due to head occlusion. When the PET headcount exceeds 220 people and YOLO occupancy surpasses 18% (0.18), "
        "the fusion_pet_guard triggers automatically, forcing 100% PET-direct counting (PET_GUARD_DIRECT) and bypassing "
        "the YOLO blend entirely."
    )

    doc.add_heading("Piecewise ShanghaiTech Count Calibration", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Extensive benchmarking against the ShanghaiTech Crowd Dataset demonstrated a slight systematic negative bias in standard "
        "neural density integration. Suraksha implements a piecewise calibration function (calibrate_fused_count in utils/count_calibration.py) "
        "that applies fine-grained multipliers according to headcount bins:"
    )

    calib_headers = ["Headcount Bin", "Count Range", "Calibration Multiplier", "Correction Purpose"]
    calib_data = [
        ["Bin 1", "< 50 pax", "x1.12 (+12%)", "Compensates for subtle edge clipping and partial head crops."],
        ["Bin 2", "50 - 200 pax", "x1.28 (+28%)", "Addresses medium-density inter-person occlusion in platform corridors."],
        ["Bin 3", "200 - 500 pax", "x1.09 (+9%)", "Fine-tunes high-density transformer query saturation."],
        ["Bin 4", "> 500 pax", "x1.19 (+19%)", "Extreme surge calibration; capped at a strict x1.40 safety ceiling."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.2, 1.3, 1.5, 2.5], calib_headers, calib_data)
    doc.add_paragraph()

    # --- SECTION 6 ---
    h1 = doc.add_heading("6. Optical Flow, Crowd Dynamics & Stampede Early Warning", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "Headcount alone does not determine physical danger: 300 passengers walking smoothly at 1.2 m/s represent normal operation, "
        "whereas 150 passengers compressed into a bottleneck with opposing velocity vectors can trigger a fatal stampede within seconds. "
        "Suraksha integrates a real-time crowd dynamics module that computes velocity vectors and spatial divergence."
    )

    doc.add_heading("Farneback Dense Optical Flow & Real-World Velocity", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "The system executes two-frame Farneback Optical Flow on grayscale downsampled frames (every 3 frames on CPU, or every frame "
        "on GPU). Pixel displacement is mapped to real-world velocity (m/s) using calibrated homography ratios (meters_per_pixel). "
        "Motion classifications follow the Fruin/Weidmann transit standards:"
    )

    flow_headers = ["Motion Classification", "Velocity Range (m/s)", "Real-World Interpretation", "Risk Implication"]
    flow_data = [
        ["STATIC", "< 0.10 m/s", "Stationary crowd or stationary queue", "Evaluated for static queue dampening."],
        ["SLOW", "0.10 - 0.50 m/s", "Dense shuffling; constrained movement", "Indicates beginning of transit friction."],
        ["NORMAL", "0.50 - 1.30 m/s", "Standard pedestrian walking pace", "Normal transit flow; low operational risk."],
        ["FAST", "1.30 - 2.50 m/s", "Brisk walking or rapid boarding", "Elevated transit activity."],
        ["RUNNING", "> 2.50 m/s", "Running, panic, or rapid evacuation", "Immediate operational trigger; flags potential panic."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.4, 1.3, 2.0, 1.8], flow_headers, flow_data)
    doc.add_paragraph()

    doc.add_heading("Stampede Detection: Negative Divergence (Compression)", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Stampedes are physically preceded by crowd compression—regions where pedestrians enter faster than they can exit. "
        "Mathematically, this corresponds to negative divergence in the optical flow vector field (div V = dVx/dx + dVy/dy). "
        "When spatial divergence falls below -4.0 (compression_threshold = -4.0), it indicates severe pedestrian pinch-points. "
        "The system immediately injects a heavy risk penalty (+10.0 points to the risk score) and triggers a stampede warning."
    )

    doc.add_heading("Static Queue Risk Dampening", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "A common false positive in transit stations is long, orderly queues at ticket counters or IRCTC catering stalls. "
        "Although density is high (>3.0 pax/m²), motion is near zero (<0.15 m/s) and orderly. Suraksha detects static queues "
        "and applies a 60% risk dampening factor (static_queue_risk_dampening = 0.4), preventing spurious alerts while keeping "
        "active monitoring engaged."
    )

    # --- SECTION 7 ---
    h1 = doc.add_heading("7. Zone-Level Spatial Aggregation & Conservative Risk Modeling", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "Individual camera views cover limited physical sectors. To provide actionable intelligence for railway operations, "
        "camera metrics must be synthesized into physical railway zones (e.g., 'Zone PF 1-2 Kazipet FOB', 'North Stairs Escalator', "
        "'Island Platform 4/5 Central')."
    )

    img_p = doc.add_paragraph()
    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_picture(f"{ASSETS_DIR}/diagram_zone_alert_flow.png", width=Inches(6.5))
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cap = cap_p.add_run("Figure 3: Zone Aggregation, Risk Scoring & Multi-Channel Alert Flow")
    r_cap.font.size = Pt(8.5)
    r_cap.italic = True
    r_cap.font.color.rgb = COLOR_MUTED

    doc.add_heading("Conservative Aggregation Rules", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "To ensure passenger safety, the Zone Analytics Engine (services/zone_analytics.py) applies strictly conservative synthesis rules:"
    )

    p_r1 = doc.add_paragraph()
    p_r1.paragraph_format.left_indent = Inches(0.25)
    p_r1.add_run("• Total Headcount: ").bold = True
    p_r1.add_run("SUM(Camera Headcounts). The total estimated number of people occupying the entire contiguous zone.")

    p_r2 = doc.add_paragraph()
    p_r2.paragraph_format.left_indent = Inches(0.25)
    p_r2.add_run("• Average Density: ").bold = True
    p_r2.add_run("MAX(Camera Densities). If one camera covering a narrow stairway exhibits critical density (4.5 pax/m²) while another over a landing is empty, the zone is classified by the localized danger point (4.5 pax/m²).")

    p_r3 = doc.add_paragraph()
    p_r3.paragraph_format.left_indent = Inches(0.25)
    p_r3.add_run("• Risk Score & Level: ").bold = True
    p_r3.add_run("MAX(Camera Risk Scores). High-risk pinch points are never diluted by adjacent empty areas.")

    p_r4 = doc.add_paragraph()
    p_r4.paragraph_format.left_indent = Inches(0.25)
    p_r4.add_run("• Motion Intensity: ").bold = True
    p_r4.add_run("MAX(Camera Motion Intensities). Detects localized running or panic anywhere within the zone.")

    doc.add_heading("Unified Risk Level Matrix (Fruin Level of Service)", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Risk scores (0 - 100) and density classifications are standardized across all stations according to transit safety research:"
    )

    risk_headers = ["Risk Level", "Score Range", "Density Threshold", "Visual UI Styling", "Operational Incident Action"]
    risk_data = [
        ["LOW", "0 - 35", "< 0.5 pax/m²", "Solid Green Badge", "Normal operational state. Free passenger movement."],
        ["MEDIUM", "35 - 55", "0.5 - 1.5 pax/m²", "Amber / Yellow Badge", "Elevated monitoring. Normal peak boarding."],
        ["HIGH", "55 - 80", "1.5 - 2.5 pax/m²", "Orange Border & Icon", "Station master notified. Monitor stairs for spillback."],
        ["CRITICAL", "> 80", "> 2.5 pax/m² (>4.0 crush)", "Flashing Red + Dark Background", "Emergency alert. WhatsApp notification sent to RPF; automated voice announcement triggered."]
    ]
    format_table(doc.add_table(rows=1, cols=5), [1.0, 0.9, 1.3, 1.4, 1.9], risk_headers, risk_data)
    doc.add_paragraph()

    # --- SECTION 8 ---
    h1 = doc.add_heading("8. Automated Notification & Operational Actioning Engines", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "Suraksha is not merely an observational tool; it is an active operational control system that initiates automated "
        "remediation workflows upon detecting critical conditions."
    )

    doc.add_heading("MSG91 WhatsApp Notification Engine", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "When high or critical risks persist for at least 5 seconds across 3 consecutive frames, the notification service "
        "(services/whatsapp_alert_service.py) formats a structured WhatsApp message using approved MSG91 templates. "
        "Alerts are dispatched directly to the Railway Protection Force duty officer, Station Superintendent, and commercial inspectors. "
        "Alerts contain the exact platform/FOB location, headcount, risk level, and emergency SOP links."
    )

    doc.add_heading("Automated Multilingual Voice Announcements", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Under overcrowding or platform reassignments, the Announcement Engine (train_announcement.py) dynamically composes "
        "natural language audio notices. Audio is synthesized using gTTS or Sarvam AI Bulbul neural models in three languages: "
        "English, Hindi, and Telugu. The synthesized MP3 audio files are automatically uploaded to AWS S3 and their URLs are "
        "broadcast to station audio distribution units to direct passengers away from congested FOBs."
    )

    doc.add_heading("Island Platform Risk Engine", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Island platforms (e.g. Platform 4/5 or 6/7 at Secunderabad) serve tracks on both sides. A unique transit hazard occurs "
        "when two heavy trains arrive simultaneously, causing dual passenger egress onto a narrow platform. The Island Alert Service "
        "(services/island_alert_service.py) links train schedules with spatial footfall risk algorithms, evaluating a 90-minute "
        "predictive window to warn controllers of dangerous concurrent dwell times before the trains even enter the station yard."
    )

    # --- SECTION 9 ---
    h1 = doc.add_heading("9. Real-Time Frontend Experience & Interactive SVG Floor Plan", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "The frontend application (Crowd_Vision_Frontend) is an enterprise single-page application built with React 18, "
        "TypeScript, Vite, and Tailwind CSS. It communicates with the backend via WebSocket channels (/api/ws/analytics, "
        "/api/ws/zones/analytics, /api/ws/trains) with an automatic 3-second reconnection loop and fallback to REST polling."
    )

    doc.add_heading("Interactive SVG Map Viewer (FOBMapViewer.tsx)", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "Rather than forcing operators to inspect disconnected camera tiles, the FOB Map Viewer displays an overhead architectural "
        "schematic of the Secunderabad Foot Over Bridge. Key implementation highlights include:"
    )

    p_f1 = doc.add_paragraph()
    p_f1.paragraph_format.left_indent = Inches(0.25)
    p_f1.add_run("• Percentage-Based Spatial Mapping: ").bold = True
    p_f1.add_run("Zone polygons and data overlay boxes are positioned using percentage coordinates (ZONE_POSITIONS), ensuring flawless scaling across 1080p, 4K video walls, and tablet screens.")

    p_f2 = doc.add_paragraph()
    p_f2.paragraph_format.left_indent = Inches(0.25)
    p_f2.add_run("• Dynamic Risk-Responsive Styling: ").bold = True
    p_f2.add_run("As WebSocket updates arrive, zone sectors dynamically transition between emerald green, golden amber, vibrant orange, and pulsing crimson according to live risk levels.")

    p_f3 = doc.add_paragraph()
    p_f3.paragraph_format.left_indent = Inches(0.25)
    p_f3.add_run("• Interactive Spatial Telemetry: ").bold = True
    p_f3.add_run("Clicking any FOB sector immediately opens an inspector displaying active camera sources, individual camera densities, motion velocity vectors, and historical trends.")

    doc.add_heading("1-Hour Rolling Footfall Chart with LocalStorage Caching", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "A critical production requirement addressed in FOBPeopleCountChart.tsx was the elimination of data loss upon browser refresh. "
        "The chart maintains a continuous 1-hour rolling window of footfall samples (5-second intervals). All incoming data points are "
        "automatically synchronized to the browser's localStorage cache (fob_chart_data_HYB_1h). Upon page reload or network hiccup, "
        "the historical trend curve re-renders instantly without requesting heavy historical aggregates from the database."
    )

    # --- SECTION 10 ---
    h1 = doc.add_heading("10. Database Schema, Storage Lifecycle & TTL Data Retention", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "MongoDB serves as the operational and time-series document store. All write operations are routed through the asynchronous "
        "PersistenceWorker (services/persistence_worker.py) to prevent disk I/O latency from degrading the real-time processing loop."
    )

    db_headers = ["Collection Name", "Record Contents", "Indexing Strategy", "Automated Retention Policy (TTL)"]
    db_data = [
        ["analytics", "Per-camera/zone footfall samples (people count, density, motion, risk).", "compound: [camera_id, timestamp], [zone_id, timestamp]", "Auto-purged after 30 days via MongoDB TTL index."],
        ["alerts", "Incident records (severity, trigger reason, zone, status, resolution).", "compound: [status, severity, timestamp]", "Retained for 90 days for statutory safety compliance."],
        ["cameras", "RTSP URLs, calibration homography, zone mappings, stream status.", "unique: [camera_id]", "Permanent operational configuration."],
        ["zones", "SVG coordinates, display orders, parent station IDs, thresholds.", "unique: [zone_id]", "Permanent spatial layout metadata."],
        ["train_schedules", "Train numbers, names, arrival/departure schedules, platforms.", "compound: [train_number, scheduled_arrival]", "Rolling 7-day schedule window."],
        ["island_alerts", "Concurrent multi-train footfall surge projections.", "compound: [island_id, window_start]", "Retained for 30 days."],
        ["images", "File paths and metadata for critical incident snapshots.", "compound: [alert_id, camera_id]", "Retained for 90 days (10 GB max storage cap)."],
        ["detections", "Raw YOLO bounding box coordinates (debug/verification mode).", "index: [timestamp]", "Strict 7-day TTL cleanup to prevent storage exhaustion."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.3, 1.9, 1.6, 1.7], db_headers, db_data)
    doc.add_paragraph()

    # --- SECTION 11 ---
    h1 = doc.add_heading("11. Production Infrastructure Topology, K3s & NVIDIA GPU Toolkit", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "The production deployment utilizes K3s—a lightweight, highly efficient Kubernetes distribution optimized for edge "
        "workstations and IoT appliances. The cluster topology is orchestrated using Kustomize manifests located in k3s/stack/."
    )

    img_p = doc.add_paragraph()
    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_picture(f"{ASSETS_DIR}/diagram_k3s_deployment.png", width=Inches(6.5))
    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cap = cap_p.add_run("Figure 4: K3s Edge Workstation Cluster Architecture & Container Topology")
    r_cap.font.size = Pt(8.5)
    r_cap.italic = True
    r_cap.font.color.rgb = COLOR_MUTED

    doc.add_heading("K3s Kubernetes Manifest Architecture", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "The cluster operates under the isolated crowdvision namespace. Key architectural components include:"
    )

    p_k1 = doc.add_paragraph()
    p_k1.paragraph_format.left_indent = Inches(0.25)
    p_k1.add_run("• Traefik Ingress Controller: ").bold = True
    p_k1.add_run("Acts as the unified gateway. Routes / to the React frontend Nginx pod, /api to the FastAPI backend pod, and /api/ws/* to the WebSocket cluster, providing clean TLS termination and CORS isolation.")

    p_k2 = doc.add_paragraph()
    p_k2.paragraph_format.left_indent = Inches(0.25)
    p_k2.add_run("• GPU Workstation Acceleration (NVIDIA Container Toolkit): ").bold = True
    p_k2.add_run("The backend deployment utilizes runtimeClassName: nvidia and requests nvidia.com/gpu: 1. Model weights (yolov8m.pt and SHA_model.pth) are mounted from a high-throughput PersistentVolumeClaim (crowdvision-data) at /app/data/weights.")

    p_k3 = doc.add_paragraph()
    p_k3.paragraph_format.left_indent = Inches(0.25)
    p_k3.add_run("• MediaMTX Pod: ").bold = True
    p_k3.add_run("An in-cluster RTSP proxy that ingests external camera feeds and serves high-efficiency internal RTSP endpoints (rtsp://mediamtx:8554/cam_01), decoupling external network flaps from backend workers.")

    doc.add_heading("Deterministic Sharding Across Pods", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "When expanding beyond single-workstation capacity (e.g., monitoring 100+ cameras across multiple GPU nodes), "
        "the backend supports deterministic sharding (services/sharding.py). Camera IDs are hashed via CRC32 modulo the total "
        "pod count (CRC32(camera_id) % CAMERA_SHARD_COUNT). Each StatefulSet pod (crowdvision-backend-0, crowdvision-backend-1) "
        "automatically binds to its designated camera shard, ensuring balanced GPU distribution without cross-pod locks."
    )

    # --- SECTION 12 ---
    h1 = doc.add_heading("12. Production Runbook, Health Verification & Maintenance", level=1)
    h1.style.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph(
        "This section details standard operational runbooks, daily health verification commands, and emergency troubleshooting "
        "procedures for railway IT and on-site engineering staff."
    )

    doc.add_heading("Health Check API Endpoints", level=2).style.font.color.rgb = COLOR_SECONDARY
    doc.add_paragraph(
        "The backend exposes tiered health check probes designed for Kubernetes liveness and readiness monitoring:"
    )

    health_headers = ["Endpoint", "Probe Type", "Evaluation Criteria", "HTTP Response"]
    health_data = [
        ["GET /api/health/simple", "K3s Liveness Probe", "Validates FastAPI process responsiveness.", "200 OK: {\"status\": \"alive\"}"],
        ["GET /api/health", "K3s Readiness Probe", "Validates MongoDB connectivity, GPU availability, and active RTSP workers.", "200 OK: {\"status\": \"healthy\", \"database\": \"connected\", \"gpu\": true}"],
        ["GET /api/rtsp/list", "Operator Stream Audit", "Reports active frame rates, buffer lag, and circuit breaker status per camera.", "200 OK: List of stream health objects."]
    ]
    format_table(doc.add_table(rows=1, cols=4), [1.5, 1.4, 2.1, 1.5], health_headers, health_data)
    doc.add_paragraph()

    doc.add_heading("Standard Operating Commands (K3s Runbook)", level=2).style.font.color.rgb = COLOR_SECONDARY

    cmds = [
        ("Deploy Entire Stack", "kubectl apply -k k3s/stack/overlays/workstation"),
        ("Monitor Cluster Rollout", "kubectl -n crowdvision rollout status deploy/crowdvision-backend --timeout=10m"),
        ("Inspect Real-Time Logs", "kubectl -n crowdvision logs deploy/crowdvision-backend -f --tail=100"),
        ("Verify Pods & GPU Binding", "kubectl -n crowdvision get pods -o wide"),
        ("Emergency Restart Backend", "kubectl -n crowdvision rollout restart deploy/crowdvision-backend"),
        ("Local Port-Forward Testing", "kubectl -n crowdvision port-forward svc/crowdvision-backend 8000:80")
    ]
    for cmd_title, cmd_str in cmds:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(f"• {cmd_title}:\n  ")
        r1.bold = True
        r1.font.color.rgb = COLOR_PRIMARY
        r2 = p.add_run(cmd_str)
        r2.font.name = "Consolas"
        r2.font.size = Pt(9)
        r2.font.color.rgb = RGBColor(30, 41, 59)

    doc.add_heading("Troubleshooting Common Operational Issues", level=2).style.font.color.rgb = COLOR_SECONDARY

    issues = [
        ("GPU Out of Memory (OOM)", "Symptom: CUDA error: out of memory during initialization.\nResolution: Ensure SharedModelPool or BatchedInferenceService is active. Check that use_shared_model_pool=True in config.py. Verify no orphaned python processes hold the GPU using 'nvidia-smi'."),
        ("RTSP Frame Freezing", "Symptom: Camera status stays 'running' but headcount is static.\nResolution: The decoupled capture thread detects bad frames and trips the CircuitBreaker. Check camera network ping. Restart stream via UI 'Restart' button or verify MediaMTX RTSP ingress."),
        ("WhatsApp Alert Not Delivered", "Symptom: Alert logged in MongoDB but no WhatsApp message received.\nResolution: Verify MSG91_AUTH_KEY in secret.yaml. Confirm recipient numbers include international country code (e.g. 919876543210). Inspect logs with 'grep -i whatsapp'."),
        ("Chart Flatlining on UI", "Symptom: 1-hour graph stops rendering new points.\nResolution: Inspect WebSocket connection badge in UI header. If red, verify port 443/WSS route in Traefik ingress. Confirm client local time matches Indian Standard Time (IST).")
    ]
    for issue_title, issue_desc in issues:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"Issue: {issue_title}\n")
        r1.bold = True
        r1.font.color.rgb = RGBColor(220, 38, 38)
        r2 = p.add_run(issue_desc)
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = COLOR_DARK

    # Save Document
    doc.save(DOCX_OUTPUT_PATH)
    print(f"Successfully generated comprehensive Word document: {DOCX_OUTPUT_PATH}")

if __name__ == "__main__":
    build_document()
