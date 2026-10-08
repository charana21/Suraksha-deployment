#!/usr/bin/env python3
"""
Suraksha CrowdVision - Production Overnight In-Memory Monitor & 3-Hour Reporter
================================================================================

Architecture:
1. ZERO Local File Logging:
   - Does NOT save continuous backend logs, frontend logs, CSVs, or text reports to disk.
   - All logs and metrics are processed strictly in-memory (RAM) via rolling ring buffers.
   - Preserves disk space and prevents drive exhaustion overnight.

2. Automated 3-Hour Email Reports:
   - Dispatches a comprehensive health and streaming report every 3 hours (10,800s).
   - Sends an initial startup verification report after 30 seconds.

3. 30-Minute Plots & Visual Graphs:
   - Aggregates rolling metrics into 30-minute buckets over each 3-hour window.
   - Generates a multi-panel visual graph (CPU, RAM, GPU 0/1 temps & utils, camera health).
   - Embeds the graph directly inside the HTML email (CID inline image) and as an attachment.
   - Includes a structured summary table of the 30-minute plots in the email body.
"""

import collections
import datetime
import email.mime.image
import email.mime.multipart
import email.mime.text
import io
import json
import os
import re
import signal
import smtplib
import subprocess
import sys
import threading
import time
from typing import Dict, Any, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import psutil

# Configuration
REPORT_INTERVAL_SEC = 3 * 3600  # 3 hours (10,800 seconds)
METRICS_SAMPLE_INTERVAL_SEC = 15  # Sample metrics every 15 seconds
BUCKET_MINUTES = 30  # Group data points into 30-minute plots
MAX_SAMPLES = int((3.5 * 3600) / METRICS_SAMPLE_INTERVAL_SEC)  # ~840 samples (~3.5 hrs rolling buffer in RAM)

# Email Settings (Configurable via environment or defaults)
EMAIL_RECIPIENT = os.environ.get("MONITOR_EMAIL_RECIPIENT", "saicharananandapu@tridemobility.com")
SMTP_USER = os.environ.get("MONITOR_SMTP_USER", "tridetech5@gmail.com")
SMTP_PASS = os.environ.get("MONITOR_SMTP_PASS", "cauxjqvufexbrayu")
SMTP_HOST = os.environ.get("MONITOR_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("MONITOR_SMTP_PORT", 587))

RUNNING = True
START_TIME = datetime.datetime.now()

# In-Memory Rolling Buffers (Strictly in RAM, Zero Local Files)
metrics_lock = threading.Lock()
metrics_history: collections.deque = collections.deque(maxlen=MAX_SAMPLES)

events_lock = threading.Lock()
events_history: collections.deque = collections.deque(maxlen=100)

camera_lock = threading.Lock()
camera_tracker: Dict[str, Dict[str, Any]] = {}

pod_status_lock = threading.Lock()
latest_pod_statuses: Dict[str, Dict[str, Any]] = {}

stats_lock = threading.Lock()
running_stats = {
    "total_reconnect_events": 0,
    "pod_restarts_detected": 0,
    "email_cycles_sent": 0,
}


def log_console(msg: str):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] {msg}", flush=True)


def log_event(category: str, detail: str):
    """Records an operational event into memory."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now_str}] [{category}] {detail}"
    with events_lock:
        events_history.append(entry)
    log_console(f"EVENT [{category}]: {detail}")


def load_active_camera_ids() -> List[str]:
    """Fetch active camera IDs from MongoDB if available, otherwise use default active set."""
    try:
        from pymongo import MongoClient
        uri = os.environ.get(
            "MONGODB_URI",
            "mongodb://suraksha_ai:Tr%21deSuraksha%4026@telematics-mongo0.evrides.in:12021/crowdvision?authSource=crowdvision"
        )
        dbname = os.environ.get("MONGODB_DATABASE", "crowdvision_prod")
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        cams = list(client[dbname].cameras.find({"is_active": True}, {"camera_id": 1}))
        if cams:
            cids = [c["camera_id"] for c in cams if "camera_id" in c]
            log_console(f"Loaded {len(cids)} active cameras from database {dbname}.")
            return sorted(cids)
    except Exception as e:
        log_console(f"Could not query MongoDB for cameras ({e}), using default fleet.")

    return [
        "cam_middle_fob_4_5", "cam_pf1_fob_hyb_end", "cam_kzj_pf1_fob_kzj",
        "cam_kzj_pf1_fob_pf10", "cam_mid_fob_pf1", "cam_mid_fob_center",
        "cam_hyb_pf1", "cam_hyb_pf2", "cam_hyb_pf4", "cam_hyb_pf10",
        "cam_hyb_pf1_a", "cam_hyb_booking", "cam_hyb_booking_gate4a",
        "cam_hyb_booking_gate6", "cam_hyb_booking_gate8", "cam_pf2_fc_hyd_side",
        "cam_pf8_mid_fc_kzj", "cam_gate2_wh", "cam_kzj_fob_mid_4_5",
        "cam_kzj_fob_mid_8_9", "cam_hyd_booking_gate2a", "cam_near_gate_2a_fc_swathi_ent",
        "cam_gate2_fc_ac_wh", "cam_gate2a_fc_parking", "cam_pf1_fob_pf10",
        "cam_new_kzj_fob_fc_pf1", "cam_new_kzj_fob_near_pf1", "cam_pf10_bme_counter"
    ]


def init_camera_tracker():
    cids = load_active_camera_ids()
    with camera_lock:
        for cid in cids:
            camera_tracker[cid] = {
                "camera_id": cid,
                "shard": "unknown",
                "status": "INITIALIZING",
                "fps": 0.0,
                "frames": 0,
                "people_count": 0,
                "density_avg": 0.0,
                "motion": 0.0,
                "last_seen": None,
                "reconnect_count": 0,
                "last_error": None,
            }


# ---------------------------------------------------------------------------
# In-Memory Log Parsing (Zero Disk Storage)
# ---------------------------------------------------------------------------
def stream_backend_logs():
    """Tails logs from backend pods in-memory only (DOES NOT WRITE TO DISK)."""
    global RUNNING
    log_console("Starting In-Memory Backend Logs streaming thread...")
    while RUNNING:
        try:
            cmd = [
                "kubectl", "logs",
                "-n", "crowdvision",
                "-l", "app.kubernetes.io/name=crowdvision-backend",
                "-f", "--prefix", "--tail=50"
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            current_camera = None
            for line in proc.stdout:
                if not RUNNING:
                    proc.terminate()
                    break

                shard = "backend-0" if "crowdvision-backend-0" in line else (
                    "backend-1" if "crowdvision-backend-1" in line else "unknown"
                )

                # Parse Progress Report header
                prog_match = re.search(r"\[RTSP Worker (?P<cid>cam_\w+)\] Progress Report:", line)
                if prog_match:
                    current_camera = prog_match.group("cid")
                    with camera_lock:
                        if current_camera not in camera_tracker:
                            camera_tracker[current_camera] = {"camera_id": current_camera, "reconnect_count": 0}
                        camera_tracker[current_camera]["status"] = "ACTIVE STREAMING"
                        camera_tracker[current_camera]["shard"] = shard
                        camera_tracker[current_camera]["last_seen"] = time.time()
                    continue

                # Parse Progress Report metrics
                if current_camera:
                    with camera_lock:
                        if "Processed Frames:" in line:
                            m = re.search(r"Processed Frames:\s*(\d+)", line)
                            if m:
                                camera_tracker[current_camera]["frames"] = int(m.group(1))
                        elif "Processing FPS:" in line:
                            m = re.search(r"Processing FPS:\s*([\d\.]+)", line)
                            if m:
                                camera_tracker[current_camera]["fps"] = float(m.group(1))
                        elif "People Count:" in line:
                            m = re.search(r"People Count:\s*(\d+)", line)
                            if m:
                                camera_tracker[current_camera]["people_count"] = int(m.group(1))
                        elif "Density (avg/max):" in line:
                            m = re.search(r"Density \(avg/max\):\s*([\d\.]+)", line)
                            if m:
                                camera_tracker[current_camera]["density_avg"] = float(m.group(1))
                        elif "Motion Intensity:" in line:
                            m = re.search(r"Motion Intensity:\s*([\d\.]+)", line)
                            if m:
                                camera_tracker[current_camera]["motion"] = float(m.group(1))
                            current_camera = None

                # Parse Lifecycle events
                conn_match = re.search(r"\[Lifecycle\] Camera (?P<cid>cam_\w+).*?\bconnected\b", line)
                if conn_match:
                    cid = conn_match.group("cid")
                    with camera_lock:
                        if cid not in camera_tracker:
                            camera_tracker[cid] = {"camera_id": cid, "reconnect_count": 0}
                        camera_tracker[cid]["status"] = "ACTIVE STREAMING"
                        camera_tracker[cid]["shard"] = shard
                        camera_tracker[cid]["last_seen"] = time.time()
                        camera_tracker[cid]["last_error"] = None

                disc_match = re.search(r"\[Lifecycle\] Camera (?P<cid>cam_\w+).*?\bdisconnected:\s*(?P<reason>[^\n]+)", line)
                if disc_match:
                    cid = disc_match.group("cid")
                    reason = disc_match.group("reason").strip()
                    with camera_lock:
                        if cid not in camera_tracker:
                            camera_tracker[cid] = {"camera_id": cid, "reconnect_count": 0}
                        camera_tracker[cid]["status"] = "RECONNECTING"
                        camera_tracker[cid]["shard"] = shard
                        camera_tracker[cid]["last_error"] = reason
                        camera_tracker[cid]["reconnect_count"] = camera_tracker[cid].get("reconnect_count", 0) + 1
                    with stats_lock:
                        running_stats["total_reconnect_events"] += 1
                    log_event("RTSP_DISCONNECT", f"Camera {cid} disconnected on {shard}: {reason}")

            if proc.poll() is not None and RUNNING:
                time.sleep(3)
        except Exception as e:
            log_console(f"Backend log stream warning: {e}. Retrying in 3s...")
            time.sleep(3)


# ---------------------------------------------------------------------------
# In-Memory Metrics Collection (Zero Disk Storage)
# ---------------------------------------------------------------------------
def collect_metrics_loop():
    """Collects system & GPU metrics every 15s into an in-memory deque (NO CSV)."""
    global RUNNING
    log_console(f"Starting In-Memory Metrics collector (sampling every {METRICS_SAMPLE_INTERVAL_SEC}s)...")

    while RUNNING:
        try:
            now_dt = datetime.datetime.now()

            # Host CPU & RAM
            cpu_pct = psutil.cpu_percent(interval=1.0)
            mem = psutil.virtual_memory()
            ram_used_gb = round(mem.used / (1024 ** 3), 2)
            ram_total_gb = round(mem.total / (1024 ** 3), 2)
            ram_pct = mem.percent

            # Root Disk
            disk = psutil.disk_usage("/")
            disk_used_gb = round(disk.used / (1024 ** 3), 2)
            disk_pct = disk.percent

            # GPU Query via nvidia-smi
            gpu0_temp, gpu0_util, gpu0_mem = 0, 0, 0
            gpu1_temp, gpu1_util, gpu1_mem = 0, 0, 0
            try:
                smi_out = subprocess.check_output([
                    "nvidia-smi",
                    "--query-gpu=index,temperature.gpu,utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits"
                ], text=True, timeout=5)
                for line in smi_out.strip().split("\n"):
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    idx = int(parts[0])
                    temp = int(parts[1])
                    util = int(parts[2])
                    m_used = int(parts[3])
                    if idx == 0:
                        gpu0_temp, gpu0_util, gpu0_mem = temp, util, m_used
                    elif idx == 1:
                        gpu1_temp, gpu1_util, gpu1_mem = temp, util, m_used
            except Exception:
                pass

            # Calculate current active streaming cameras
            with camera_lock:
                curr_t = time.time()
                active_cams = sum(
                    1 for c in camera_tracker.values()
                    if (c.get("last_seen") and (curr_t - c["last_seen"]) < 45.0) or c.get("status") == "ACTIVE STREAMING"
                )
                reconnect_events = sum(c.get("reconnect_count", 0) for c in camera_tracker.values())

            sample = {
                "timestamp": now_dt,
                "cpu_pct": cpu_pct,
                "ram_used_gb": ram_used_gb,
                "ram_total_gb": ram_total_gb,
                "ram_pct": ram_pct,
                "disk_used_gb": disk_used_gb,
                "disk_pct": disk_pct,
                "gpu0_temp": gpu0_temp,
                "gpu0_util": gpu0_util,
                "gpu0_mem_mb": gpu0_mem,
                "gpu1_temp": gpu1_temp,
                "gpu1_util": gpu1_util,
                "gpu1_mem_mb": gpu1_mem,
                "active_cameras": active_cams,
                "reconnect_events": reconnect_events
            }

            with metrics_lock:
                metrics_history.append(sample)

            # Sleep remaining interval
            sleep_time = max(1, METRICS_SAMPLE_INTERVAL_SEC - 1)
            for _ in range(sleep_time):
                if not RUNNING:
                    break
                time.sleep(1)

        except Exception as e:
            log_console(f"Metrics collection error: {e}")
            time.sleep(5)


# ---------------------------------------------------------------------------
# Kubernetes Pod Monitor (In-Memory)
# ---------------------------------------------------------------------------
def monitor_k8s_pods():
    """Monitors k8s pod readiness and restarts every 30s."""
    global RUNNING
    log_console("Starting Kubernetes Pod Health monitor thread...")
    last_restarts: Dict[str, int] = {}

    while RUNNING:
        try:
            cmd = ["kubectl", "get", "pods", "-n", "crowdvision", "-o", "json"]
            out = subprocess.check_output(cmd, text=True, timeout=10)
            data = json.loads(out)
            items = data.get("items", [])

            current_map = {}
            for item in items:
                pname = item.get("metadata", {}).get("name", "unknown")
                phase = item.get("status", {}).get("phase", "Unknown")
                cstatuses = item.get("status", {}).get("containerStatuses", [])
                restarts = sum(c.get("restartCount", 0) for c in cstatuses)
                ready = all(c.get("ready", False) for c in cstatuses) if cstatuses else False

                current_map[pname] = {
                    "phase": phase,
                    "ready": ready,
                    "restarts": restarts,
                    "last_seen": time.time()
                }

                if pname in last_restarts:
                    if restarts > last_restarts[pname]:
                        diff = restarts - last_restarts[pname]
                        log_event("K8S_POD_RESTART", f"Pod {pname} restart count increased by {diff} (Total: {restarts})")
                        with stats_lock:
                            running_stats["pod_restarts_detected"] += diff
                last_restarts[pname] = restarts

            with pod_status_lock:
                latest_pod_statuses.clear()
                latest_pod_statuses.update(current_map)

            for _ in range(30):
                if not RUNNING:
                    break
                time.sleep(1)
        except Exception as e:
            log_console(f"K8s pod monitor warning: {e}")
            time.sleep(15)


# ---------------------------------------------------------------------------
# 30-Minute Plots Generation (Matplotlib In-Memory)
# ---------------------------------------------------------------------------
def compute_30min_buckets(samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups metrics samples into 30-minute buckets."""
    if not samples:
        return []

    # Sort samples chronologically
    sorted_samples = sorted(samples, key=lambda x: x["timestamp"])
    start_t = sorted_samples[0]["timestamp"]
    end_t = sorted_samples[-1]["timestamp"]

    buckets = []
    bucket_delta = datetime.timedelta(minutes=BUCKET_MINUTES)
    curr_start = start_t

    while curr_start <= end_t:
        curr_end = curr_start + bucket_delta
        in_bucket = [s for s in sorted_samples if curr_start <= s["timestamp"] < curr_end]
        if in_bucket:
            b_label = f"{curr_start.strftime('%H:%M')} - {curr_end.strftime('%H:%M')}"
            mid_time = curr_start + (bucket_delta / 2)
            cpus = [s["cpu_pct"] for s in in_bucket]
            rams = [s["ram_pct"] for s in in_bucket]
            ram_gb = [s["ram_used_gb"] for s in in_bucket]
            g0_temps = [s["gpu0_temp"] for s in in_bucket]
            g0_utils = [s["gpu0_util"] for s in in_bucket]
            g1_temps = [s["gpu1_temp"] for s in in_bucket]
            g1_utils = [s["gpu1_util"] for s in in_bucket]
            active_c = [s["active_cameras"] for s in in_bucket]
            reconnects = in_bucket[-1]["reconnect_events"] - in_bucket[0]["reconnect_events"]

            buckets.append({
                "time_label": b_label,
                "timestamp": mid_time,
                "sample_count": len(in_bucket),
                "cpu_avg": round(sum(cpus) / len(cpus), 1),
                "cpu_max": round(max(cpus), 1),
                "ram_avg_pct": round(sum(rams) / len(rams), 1),
                "ram_max_gb": round(max(ram_gb), 2),
                "gpu0_temp_avg": round(sum(g0_temps) / len(g0_temps), 1),
                "gpu0_temp_max": max(g0_temps),
                "gpu0_util_avg": round(sum(g0_utils) / len(g0_utils), 1),
                "gpu1_temp_avg": round(sum(g1_temps) / len(g1_temps), 1),
                "gpu1_temp_max": max(g1_temps),
                "gpu1_util_avg": round(sum(g1_utils) / len(g1_utils), 1),
                "active_cameras_avg": round(sum(active_c) / len(active_c), 1),
                "active_cameras_min": min(active_c),
                "reconnect_events": max(0, reconnects)
            })

        curr_start = curr_end

    return buckets


def generate_30min_plots_image(buckets: List[Dict[str, Any]]) -> Optional[bytes]:
    """Generates a professional 4-panel graph with 30-minute plots in-memory (Returns PNG bytes)."""
    if not buckets:
        return None

    try:
        labels = [b["time_label"].split(" - ")[0] for b in buckets]
        # Append final boundary label
        labels_plot = [b["time_label"] for b in buckets]

        fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
        fig.patch.set_facecolor("#0f172a")

        for ax in axes:
            ax.set_facecolor("#1e293b")
            ax.grid(True, linestyle="--", alpha=0.3, color="#94a3b8")
            ax.tick_params(colors="#cbd5e1", labelsize=9)
            for spine in ax.spines.values():
                spine.set_color("#475569")

        x_indices = list(range(len(buckets)))

        # Subplot 1: CPU & RAM (%)
        cpu_avgs = [b["cpu_avg"] for b in buckets]
        cpu_maxs = [b["cpu_max"] for b in buckets]
        ram_avgs = [b["ram_avg_pct"] for b in buckets]

        axes[0].plot(x_indices, cpu_avgs, marker="o", color="#38bdf8", linewidth=2.2, label="CPU Avg (%)")
        axes[0].plot(x_indices, cpu_maxs, marker="x", color="#60a5fa", linestyle=":", linewidth=1.5, label="CPU Peak (%)")
        axes[0].plot(x_indices, ram_avgs, marker="s", color="#a855f7", linewidth=2.0, label="RAM Used (%)")
        axes[0].set_ylabel("System %", color="#f8fafc", fontsize=10, fontweight="bold")
        axes[0].set_ylim(0, max(100, max(cpu_maxs + [70]) + 10))
        axes[0].legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#e2e8f0", fontsize=8.5)
        axes[0].set_title("30-Minute Intervals — Host CPU & RAM Utilization", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)

        # Subplot 2: GPU Temperatures (°C)
        g0_temps = [b["gpu0_temp_avg"] for b in buckets]
        g1_temps = [b["gpu1_temp_avg"] for b in buckets]

        axes[1].plot(x_indices, g0_temps, marker="^", color="#fb923c", linewidth=2.2, label="GPU 0 Temp (°C) [Shard 0]")
        axes[1].plot(x_indices, g1_temps, marker="v", color="#f87171", linewidth=2.2, label="GPU 1 Temp (°C) [Shard 1]")
        axes[1].axhline(y=85, color="#ef4444", linestyle="--", linewidth=1.2, alpha=0.7, label="Warning Threshold (85°C)")
        axes[1].set_ylabel("Temp (°C)", color="#f8fafc", fontsize=10, fontweight="bold")
        axes[1].set_ylim(40, 100)
        axes[1].legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#e2e8f0", fontsize=8.5)
        axes[1].set_title("30-Minute Intervals — Dual RTX A4000 GPU Temperatures", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)

        # Subplot 3: GPU Utilization (%)
        g0_utils = [b["gpu0_util_avg"] for b in buckets]
        g1_utils = [b["gpu1_util_avg"] for b in buckets]

        axes[2].plot(x_indices, g0_utils, marker="D", color="#34d399", linewidth=2.0, label="GPU 0 Util (%)")
        axes[2].plot(x_indices, g1_utils, marker="d", color="#10b981", linewidth=2.0, label="GPU 1 Util (%)")
        axes[2].set_ylabel("GPU Util %", color="#f8fafc", fontsize=10, fontweight="bold")
        axes[2].set_ylim(0, 105)
        axes[2].legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#e2e8f0", fontsize=8.5)
        axes[2].set_title("30-Minute Intervals — GPU Compute Engine Utilization", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)

        # Subplot 4: Active Camera Fleet
        active_c = [b["active_cameras_avg"] for b in buckets]
        reconnects = [b["reconnect_events"] for b in buckets]

        axes[3].bar([x - 0.15 for x in x_indices], active_c, width=0.3, color="#22c55e", alpha=0.85, label="Active Streams")
        axes[3].bar([x + 0.15 for x in x_indices], reconnects, width=0.3, color="#f43f5e", alpha=0.85, label="Disconnect Events")
        axes[3].set_ylabel("Cameras", color="#f8fafc", fontsize=10, fontweight="bold")
        axes[3].set_ylim(0, max(32, max(active_c + [28]) + 4))
        axes[3].set_xticks(x_indices)
        axes[3].set_xticklabels(labels_plot, rotation=25, ha="right", color="#e2e8f0", fontsize=9)
        axes[3].legend(loc="upper left", facecolor="#0f172a", edgecolor="#475569", labelcolor="#e2e8f0", fontsize=8.5)
        axes[3].set_title("30-Minute Intervals — Active Camera Streams & Reconnect Events", color="#f8fafc", fontsize=11, fontweight="bold", pad=8)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        log_console(f"Failed to generate 30-min plot: {e}")
        return None


# ---------------------------------------------------------------------------
# 3-Hour Email Report Dispatcher
# ---------------------------------------------------------------------------
def send_3hour_report(subject_prefix: str = "[3-Hour Report]", is_startup: bool = False):
    """Builds and dispatches the 3-hour health report with 30-minute plots."""
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    elapsed = str(now - START_TIME).split(".")[0]

    with metrics_lock:
        samples_snapshot = list(metrics_history)

    with camera_lock:
        cam_snapshot = [dict(v) for v in camera_tracker.values()]

    with events_lock:
        recent_events = list(events_history)[-10:]

    with pod_status_lock:
        pods_snapshot = dict(latest_pod_statuses)

    with stats_lock:
        running_stats["email_cycles_sent"] += 1
        cycle_num = running_stats["email_cycles_sent"]
        total_reconnects = running_stats["total_reconnect_events"]
        pod_restarts = running_stats["pod_restarts_detected"]

    # Compute 30-minute buckets
    buckets = compute_30min_buckets(samples_snapshot)

    # Generate the 30-min plot image
    chart_png_bytes = generate_30min_plots_image(buckets)

    # Camera Fleet Summary
    total_cams = len(cam_snapshot)
    active_cams = sum(1 for c in cam_snapshot if c.get("status") == "ACTIVE STREAMING" or (c.get("last_seen") and (time.time() - c["last_seen"] < 45.0)))
    uptime_pct = round((active_cams / total_cams * 100), 1) if total_cams else 0.0
    offline_cams = [c for c in cam_snapshot if not (c.get("status") == "ACTIVE STREAMING" or (c.get("last_seen") and (time.time() - c["last_seen"] < 45.0)))]

    # Overall Status
    if pod_restarts > 0 or uptime_pct < 65:
        health_status = "CRITICAL / ATTENTION"
        status_color = "#dc3545"
    elif uptime_pct < 85:
        health_status = "WARNING"
        status_color = "#f59e0b"
    else:
        health_status = "HEALTHY / OPERATIONAL"
        status_color = "#22c55e"

    subject = f"{subject_prefix} Suraksha CrowdVision — {now.strftime('%H:%M IST')} (Cycle #{cycle_num})"

    # Build 30-Min Bucket Table
    bucket_rows_html = ""
    if buckets:
        for b in buckets:
            bucket_rows_html += f"""
            <tr>
              <td style="padding: 6px 10px; border: 1px solid #334155; font-weight: bold; color: #38bdf8;">{b['time_label']}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center;">{b['cpu_avg']}% <span style="color:#94a3b8; font-size:11px;">(pk: {b['cpu_max']}%)</span></td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center;">{b['ram_avg_pct']}% <span style="color:#94a3b8; font-size:11px;">({b['ram_max_gb']} GB)</span></td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center;">{b['gpu0_temp_avg']}°C / {b['gpu1_temp_avg']}°C</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center;">{b['gpu0_util_avg']}% / {b['gpu1_util_avg']}%</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center; color: #4ade80; font-weight: bold;">{b['active_cameras_avg']}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center; color: {'#f87171' if b['reconnect_events'] > 0 else '#94a3b8'};">{b['reconnect_events']}</td>
            </tr>
            """
    else:
        bucket_rows_html = "<tr><td colspan='7' style='padding: 10px; text-align: center; color: #94a3b8;'>Monitoring initiated — data points accumulating for next 30-minute plot.</td></tr>"

    # Offline Cameras Rows
    offline_rows_html = ""
    if offline_cams:
        for c in offline_cams:
            offline_rows_html += f"""
            <tr>
              <td style="padding: 6px 10px; border: 1px solid #334155; font-family: monospace; color: #f87171;">{c['camera_id']}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155;">{c.get('shard', 'unknown')}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; color: #fbbf24;">{c.get('status', 'OFFLINE')}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; text-align: center;">{c.get('reconnect_count', 0)}</td>
              <td style="padding: 6px 10px; border: 1px solid #334155; font-size: 11px; color: #94a3b8;">{c.get('last_error') or 'Awaiting initial feed'}</td>
            </tr>
            """
    else:
        offline_rows_html = f"<tr><td colspan='5' style='padding: 10px; text-align: center; color: #4ade80;'>All {total_cams} cameras are actively streaming without error!</td></tr>"

    # Events HTML
    events_html = ""
    if recent_events:
        for ev in recent_events:
            events_html += f"<li style='margin-bottom: 4px; font-size: 12px; color: #cbd5e1;'>{ev}</li>"
    else:
        events_html = "<li style='font-size: 12px; color: #94a3b8;'>No critical restart or system events logged.</li>"

    # HTML Email Template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background-color: #0b1120; color: #e2e8f0; margin: 0; padding: 20px; }}
        .card {{ max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .header {{ border-bottom: 2px solid #334155; padding-bottom: 16px; margin-bottom: 20px; }}
        .title {{ font-size: 20px; font-weight: bold; color: #f8fafc; margin: 0 0 6px 0; }}
        .subtitle {{ font-size: 13px; color: #94a3b8; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: bold; color: #fff; background-color: {status_color}; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 20px; font-size: 12.5px; }}
        th {{ background-color: #0f172a; color: #94a3b8; padding: 8px 10px; border: 1px solid #334155; text-align: left; font-size: 11px; text-transform: uppercase; }}
        td {{ border: 1px solid #334155; }}
        .section-title {{ font-size: 14px; font-weight: bold; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.05em; margin: 20px 0 8px 0; border-left: 4px solid #38bdf8; padding-left: 8px; }}
        .graph-img {{ width: 100%; height: auto; border-radius: 8px; border: 1px solid #334155; margin-top: 8px; }}
        .footer {{ border-top: 1px solid #334155; margin-top: 24px; padding-top: 12px; font-size: 11px; color: #64748b; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <h1 class="title">Suraksha CrowdVision — 3-Hour Overnight Monitoring Report</h1>
            <span class="badge">{health_status}</span>
          </div>
          <div class="subtitle">Generated: {now_str} IST | Monitoring Uptime: {elapsed} | Cadence: Every 3 Hours</div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;">
          <div style="background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
            <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Active Streams</div>
            <div style="font-size: 18px; font-weight: bold; color: #4ade80;">{active_cams}/{total_cams}</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
            <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Fleet Uptime</div>
            <div style="font-size: 18px; font-weight: bold; color: #38bdf8;">{uptime_pct}%</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
            <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Total Reconnects</div>
            <div style="font-size: 18px; font-weight: bold; color: {'#f87171' if total_reconnects > 10 else '#f8fafc'};">{total_reconnects}</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
            <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Pod Restarts</div>
            <div style="font-size: 18px; font-weight: bold; color: {'#f87171' if pod_restarts > 0 else '#4ade80'};">{pod_restarts}</div>
          </div>
        </div>

        <div class="section-title">1. Multi-Panel 30-Minute Plots (Last 3 Hours)</div>
        <p style="font-size: 12px; color: #94a3b8; margin: 0 0 10px 0;">Visual trends sampled in-memory and bucketed into 30-minute intervals:</p>
        {'<img src="cid:metrics_graph" class="graph-img" alt="30-Minute Plots">' if chart_png_bytes else '<p style="color:#94a3b8; font-size:12px;">Accumulating metric points for graph...</p>'}

        <div class="section-title">2. 30-Minute Plot Interval Data Table</div>
        <table>
          <thead>
            <tr>
              <th>Time Window</th>
              <th style="text-align:center;">CPU (Avg/Peak)</th>
              <th style="text-align:center;">RAM (Avg/Peak)</th>
              <th style="text-align:center;">GPU Temps (0 / 1)</th>
              <th style="text-align:center;">GPU Utils (0 / 1)</th>
              <th style="text-align:center;">Active Cams</th>
              <th style="text-align:center;">Reconnects</th>
            </tr>
          </thead>
          <tbody>
            {bucket_rows_html}
          </tbody>
        </table>

        <div class="section-title">3. Offline / Attention Cameras ({len(offline_cams)})</div>
        <table>
          <thead>
            <tr>
              <th>Camera ID</th>
              <th>Shard</th>
              <th>Status</th>
              <th style="text-align:center;">Reconnects</th>
              <th>Diagnostics / Reason</th>
            </tr>
          </thead>
          <tbody>
            {offline_rows_html}
          </tbody>
        </table>

        <div class="section-title">4. Recent System Events</div>
        <ul style="padding-left: 20px; margin: 0;">
          {events_html}
        </ul>

        <div class="footer">
          Suraksha CrowdVision Monitoring Daemon | In-Memory Ephemeral Engine (Zero Local Disk Writes)<br>
          Automated 3-Hour notification sent to <code>{EMAIL_RECIPIENT}</code>.
        </div>
      </div>
    </body>
    </html>
    """

    # Dispatch Email via SMTP
    try:
        msg = email.mime.multipart.MIMEMultipart("related")
        msg["From"] = f"Suraksha Monitor <{SMTP_USER}>"
        msg["To"] = EMAIL_RECIPIENT
        msg["Subject"] = subject

        alt_part = email.mime.multipart.MIMEMultipart("alternative")
        msg.attach(alt_part)

        plain_text = f"SURAKSHA CROWDVISION - 3-HOUR HEALTH REPORT\nGenerated: {now_str}\nStatus: {health_status}\nActive Streams: {active_cams}/{total_cams} ({uptime_pct}%)\nTotal Reconnects: {total_reconnects}\nPod Restarts: {pod_restarts}\n"
        alt_part.attach(email.mime.text.MIMEText(plain_text, "plain"))
        alt_part.attach(email.mime.text.MIMEText(html_content, "html"))

        # Attach image as inline CID
        if chart_png_bytes:
            img_part = email.mime.image.MIMEImage(chart_png_bytes)
            img_part.add_header("Content-ID", "<metrics_graph>")
            img_part.add_header("Content-Disposition", "inline", filename="crowdvision_3hr_plot.png")
            msg.attach(img_part)

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [EMAIL_RECIPIENT], msg.as_string())
        server.quit()
        log_console(f"3-Hour email report #{cycle_num} dispatched successfully to {EMAIL_RECIPIENT}!")
    except Exception as e:
        log_console(f"Failed to dispatch 3-hour email report: {e}")
        log_event("EMAIL_ERROR", f"SMTP delivery failed: {e}")


def email_dispatcher_loop():
    """Manages the 3-hour recurring report cycle."""
    global RUNNING
    log_console(f"Email dispatcher thread started. Interval: Every 3 Hours ({REPORT_INTERVAL_SEC}s). Target: {EMAIL_RECIPIENT}")

    # Initial test email after 30 seconds
    log_console("Waiting 30 seconds for initial startup verification email...")
    for _ in range(30):
        if not RUNNING:
            return
        time.sleep(1)

    log_console("Sending initial startup verification email with plots...")
    send_3hour_report(subject_prefix="[Initial Startup Report]", is_startup=True)

    while RUNNING:
        try:
            for _ in range(REPORT_INTERVAL_SEC):
                if not RUNNING:
                    break
                time.sleep(1)

            if not RUNNING:
                break

            log_console("Generating and dispatching 3-hour recurring monitoring report...")
            send_3hour_report(subject_prefix="[3-Hour Report]")
        except Exception as e:
            log_console(f"Email dispatcher loop error: {e}")
            time.sleep(15)


def handle_shutdown(signum, frame):
    global RUNNING
    log_console("\nShutdown signal received. Exiting gracefully without local file clutter...")
    RUNNING = False
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    log_console("=" * 72)
    log_console(" SURAKSHA CROWDVISION - IN-MEMORY OVERNIGHT MONITOR & 3-HOUR REPORTER")
    log_console(" Storage Mode:       ZERO LOCAL FILES (Pure RAM Ring Buffers)")
    log_console(f" Reporting Cadence:  Every 3 Hours ({REPORT_INTERVAL_SEC} seconds)")
    log_console(f" Plotting Intervals: 30-Minute Buckets with Visual Graphs")
    log_console(f" Email Recipient:    {EMAIL_RECIPIENT}")
    log_console("=" * 72)

    init_camera_tracker()

    threads = [
        threading.Thread(target=stream_backend_logs, daemon=True, name="BackendLogs"),
        threading.Thread(target=monitor_k8s_pods, daemon=True, name="K8sPods"),
        threading.Thread(target=collect_metrics_loop, daemon=True, name="Metrics"),
        threading.Thread(target=email_dispatcher_loop, daemon=True, name="EmailDispatcher"),
    ]

    for t in threads:
        t.start()

    try:
        while RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_shutdown(None, None)


if __name__ == "__main__":
    main()
