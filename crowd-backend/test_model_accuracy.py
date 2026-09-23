"""
Standalone Model Accuracy Test Script
=====================================
Tests PET + YOLO fusion logic on a video file without RTSP/WebSocket overhead.

Usage:
    python test_model_accuracy.py <video_path> [--frames N] [--skip N]
    python test_model_accuracy.py <video_path> --camera cam_pf1_fob_kzj --show
    python test_model_accuracy.py <video_path> --no-density-map --no-python-post-nms
    python test_model_accuracy.py <video_path> --log-every 10 --summary-json run_a.json

Examples:
    python test_model_accuracy.py test_video.mp4
    python test_model_accuracy.py test_video.mp4 --frames 50 --skip 5
    python test_model_accuracy.py test_video.mp4 --show  # Show frames with detections
    python test_model_accuracy.py test_video.mp4 --device cpu --summary-json cpu_run.json
"""

import sys
import os
import argparse
import time
import json
import cv2
import numpy as np
from collections import deque

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import get_settings
from utils.fusion import compute_fusion


def load_models(device="cuda", density_model: str = None):
    """Load YOLO and PET backend."""
    settings = get_settings()
    selected_density_model = (density_model or settings.density_model or "pet").lower()
    if selected_density_model != "pet":
        print(f"[WARNING] density_model='{selected_density_model}' requested, forcing PET")

    print("\n" + "="*60)
    print("LOADING MODELS")
    print("="*60)

    # Load YOLO
    print("\n[1/2] Loading YOLO...")
    from models.yolo_wrapper import YOLOWrapper
    yolo = YOLOWrapper(model_path=settings.yolo_model_path, device=device)
    print(f"      YOLO loaded on {device}")

    print("\n[2/2] Loading PET...")
    from models.pet_wrapper import PETWrapper
    density_backend = PETWrapper(
        weights_path=settings.pet_weights_path,
        conf_threshold=settings.pet_conf_threshold,
        nms_distance=settings.pet_nms_distance,
        device=device
    )
    density_label = "PET"
    print(f"      PET loaded on {device}")
    print(f"      Confidence threshold: {settings.pet_conf_threshold}")
    print(f"      NMS distance: {settings.pet_nms_distance}px")

    return yolo, density_backend, settings, density_label


def get_density_level(density_avg, settings=None):
    """Convert density value (people/m²) to level using unified thresholds."""
    if settings:
        t_low = settings.density_threshold_low
        t_mod = settings.density_threshold_moderate
        t_high = settings.density_threshold_high
        t_crit = settings.density_threshold_critical
    else:
        t_low, t_mod, t_high, t_crit = 0.5, 1.5, 2.5, 4.0

    if density_avg < t_low:
        return "LOW"
    elif density_avg < t_mod:
        return "LOW"
    elif density_avg < t_high:
        return "MODERATE"
    elif density_avg < t_crit:
        return "HIGH"
    else:
        return "CRITICAL"


def get_risk_level(risk_score, settings=None):
    """Convert risk score to level using unified thresholds."""
    if settings:
        t_med = settings.risk_threshold_medium
        t_high = settings.risk_threshold_high
        t_crit = settings.risk_threshold_critical
    else:
        t_med, t_high, t_crit = 35.0, 55.0, 80.0

    if risk_score < t_med:
        return "LOW"
    elif risk_score < t_high:
        return "MEDIUM"
    elif risk_score < t_crit:
        return "HIGH"
    else:
        return "CRITICAL"


def summarize_latency_ms(values):
    """Return avg/p50/p95 latency summary for a list of timings in ms."""
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0}

    arr = np.array(values, dtype=np.float32)
    return {
        "avg": float(np.mean(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
    }


class MotionTracker:
    """Motion tracker using Optical Flow with real-world m/s output.

    Matches production crowd_analyzer._analyze_optical_flow() logic.
    Uses area_m2 + frame resolution to convert pixel displacement to m/s,
    and video FPS + frame skip to compute correct elapsed time between frames.

    In pixel mode, area_m2 is derived from the DensityStabilizer's cached
    YOLO head size, so _meters_per_pixel updates dynamically.
    """
    def __init__(self, area_m2: float = 150.0, video_fps: float = 25.0,
                 frame_skip: int = 1, flow_interval: int = 3,
                 density_stabilizer=None):
        self.prev_gray = None
        self.flow_history = deque(maxlen=15)
        self.frame_count = 0
        self._cached_flow = None
        self._cached_flow_mag = 0.0
        self._cached_divergence = None
        self.area_m2 = area_m2
        self.video_fps = video_fps
        self.frame_skip = frame_skip
        self.flow_interval = flow_interval  # compute flow every N processed frames
        self._meters_per_pixel = None
        self._density_stabilizer = density_stabilizer  # for pixel mode area derivation

    def _update_meters_per_pixel(self, frame_shape):
        """Recompute meters_per_pixel from area_m2 (may change in pixel mode)."""
        import math
        # In pixel mode, derive area from density stabilizer's cached head size
        if self._density_stabilizer is not None:
            effective_area = self._density_stabilizer.get_effective_area_m2(frame_shape)
        else:
            effective_area = self.area_m2

        h, w = frame_shape[:2]
        frame_pixel_area = float(h * w)
        if effective_area > 0 and frame_pixel_area > 0:
            self._meters_per_pixel = math.sqrt(effective_area / frame_pixel_area)

    def analyze(self, frame):
        self.frame_count += 1

        # Run every flow_interval frames for performance, similar to production
        if self.frame_count % self.flow_interval != 0 and self.prev_gray is not None:
            return self._cached_flow, self._cached_flow_mag, self._cached_divergence

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Downsample at 50% (matches production)
        scale = 0.5
        h, w = gray.shape
        small_h, small_w = int(h * scale), int(w * scale)
        small_gray = cv2.resize(gray, (small_w, small_h))

        # Update meters_per_pixel each flow computation (may change in pixel mode)
        self._update_meters_per_pixel(frame.shape)

        if self.prev_gray is None or self.prev_gray.shape != small_gray.shape:
            self.prev_gray = small_gray.copy()
            self._cached_flow = np.zeros((small_h, small_w, 2))
            self._cached_divergence = np.zeros((small_h, small_w))
            return self._cached_flow, 0.0, self._cached_divergence

        # Calculate flow
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, small_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2,
            flags=0
        )

        # Magnitude
        magnitude = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)

        # Filter noise (>0.5 pixels)
        significant_motion = magnitude[magnitude > 0.5]
        if len(significant_motion) > 0:
            avg_pixel_disp = float(np.mean(significant_motion))
        else:
            avg_pixel_disp = 0.0

        # Convert to m/s (matches production crowd_analyzer logic)
        # avg_pixel_disp is at 50% resolution -> upscale x2 for full-res pixels
        # elapsed = real-world seconds between compared frames
        avg_speed_m_s = 0.0
        if self._meters_per_pixel is not None:
            # Elapsed = flow_interval * frame_skip / video_fps
            elapsed = self.flow_interval * self.frame_skip / self.video_fps
            if elapsed > 0:
                avg_speed_m_s = (avg_pixel_disp * 2.0 * self._meters_per_pixel) / elapsed

        # Calculate divergence
        flow_x_grad = cv2.Sobel(flow[:, :, 0], cv2.CV_32F, 1, 0, ksize=3)
        flow_y_grad = cv2.Sobel(flow[:, :, 1], cv2.CV_32F, 0, 1, ksize=3)
        divergence = flow_x_grad + flow_y_grad

        self.prev_gray = small_gray.copy()
        self.flow_history.append(avg_speed_m_s)
        self._cached_flow = flow
        self._cached_flow_mag = avg_speed_m_s
        self._cached_divergence = divergence

        return flow, avg_speed_m_s, divergence

    def get_level(self, speed_m_s, settings=None):
        """Classify motion speed (m/s) into level using config thresholds."""
        if settings:
            t_slow = settings.motion_threshold_slow
            t_normal = settings.motion_threshold_normal
            t_fast = settings.motion_threshold_fast
            t_running = settings.motion_threshold_running
        else:
            t_slow, t_normal, t_fast, t_running = 0.1, 0.5, 1.3, 2.5

        if speed_m_s < t_slow: return "STATIC"
        elif speed_m_s < t_normal: return "SLOW"
        elif speed_m_s < t_fast: return "NORMAL"
        elif speed_m_s < t_running: return "FAST"
        else: return "RUNNING"


def compute_turbulence(flow):
    """Compute motion turbulence (0-1 scale)"""
    if flow is None or flow.size == 0:
        return 0.0

    vx = flow[:, :, 0].flatten()
    vy = flow[:, :, 1].flatten()

    magnitudes = np.sqrt(vx**2 + vy**2)
    mask = magnitudes > 0.5

    if np.sum(mask) < 10:
        return 0.0

    vx, vy = vx[mask], vy[mask]
    angles = np.arctan2(vy, vx)
    mean_vector = np.mean(np.exp(1j * angles))
    turbulence = 1.0 - np.abs(mean_vector)

    return float(turbulence)


def detect_counter_flow(flow):
    """Detect counter-flow (people moving opposite directions)"""
    if flow is None or flow.size == 0:
        return False, 0.0

    vx = flow[:, :, 0]
    positive_flow = np.sum(vx > 1.0)
    negative_flow = np.sum(vx < -1.0)

    total_flow = positive_flow + negative_flow
    if total_flow < 100:
        return False, 0.0

    ratio = min(positive_flow, negative_flow) / total_flow
    is_counter_flow = ratio > 0.25
    severity = ratio * 2

    return is_counter_flow, min(severity, 1.0)


class DensityStabilizer:
    """
    Density calculation supporting two modes (matches production CrowdAnalyzer):

    - "pixel": PET density map + YOLO head bbox calibration (no physical area needed)
    - "area":  count / area_m2 (calibrated physical measurements)
    """
    def __init__(self, settings, camera_id: str = "_default_fob"):
        from utils.perspective import CalibrationManager

        self.settings = settings
        # Get area_m2 from calibration (fallback chain: JSON → default 150 m²)
        calibration = CalibrationManager().get_calibration(camera_id)
        self.area_m2 = calibration.visible_area_m2
        self.ema_density = None
        self.alpha_density = 0.1
        # Pixel mode: cached YOLO head bbox sizes (mirrors production _cached_head_sizes)
        self._cached_head_size_px = None

    def set_area_m2(self, area_m2: float):
        """Override area from DB config"""
        self.area_m2 = area_m2

    def get_effective_area_m2(self, frame_shape):
        """Derive area_m2 from cached YOLO head scale (pixel mode) or use calibrated value."""
        if self.settings.density_mode == "pixel" and self._cached_head_size_px and self._cached_head_size_px > 0:
            h, w = frame_shape[:2]
            px_per_m2 = self._cached_head_size_px / self.settings.pixel_head_reference_m2
            return (w * h) / px_per_m2
        return self.area_m2

    def calculate(self, frame, points, yolo_count, pet_count, regime, final_count,
                  detections=None, density_map=None, yolo_avg_confidence=0.0):
        """
        Calculate density in people per m².

        In pixel mode: uses _estimate_pixel_density (PET map + YOLO head calibration).
        In area mode: simple count / area_m2.

        Returns:
            (smoothed_density, raw_density, final_count)
        """
        if self.settings.density_mode == "pixel":
            current_density = self._estimate_pixel_density(
                density_map=density_map,
                detections=detections or [],
                head_count=yolo_count,
                final_count=final_count,
                h=frame.shape[0],
                w=frame.shape[1],
                yolo_avg_confidence=yolo_avg_confidence,
            )
        else:
            # Area mode: count / area_m2
            current_density = final_count / self.area_m2 if self.area_m2 > 0 else 0.0

        # EMA Smoothing
        if self.ema_density is None:
            self.ema_density = current_density
        else:
            diff = abs(current_density - self.ema_density)
            adaptive_alpha = self.alpha_density
            if diff > 0.5:
                adaptive_alpha = 0.3
            self.ema_density = adaptive_alpha * current_density + (1 - adaptive_alpha) * self.ema_density

        return self.ema_density, current_density, final_count

    def _estimate_pixel_density(self, density_map, detections, head_count,
                                final_count, h, w, yolo_avg_confidence):
        """PET-driven pixel density with optional YOLO head calibration.

        Mirrors production CrowdAnalyzer._estimate_pixel_density():
        - Layer 1 (PET): normalize density map, extract peak + crowded fraction
        - Layer 2 (YOLO): median head bbox → px_per_m² → real density
        """
        if final_count == 0:
            return 0.0

        roi_area_px = float(h * w)

        # --- Layer 1: PET density map spatial metrics ---
        peak_ppx = 0.0
        crowded_fraction = 0.0

        if density_map is not None and density_map.size > 0:
            dmap_sum = float(np.sum(density_map))
            if dmap_sum > 0:
                normalized = density_map * (final_count / dmap_sum)
                peak_ppx = float(np.max(normalized))
                if peak_ppx > 0:
                    high_thresh = peak_ppx * 0.3
                    high_density_pixels = float(np.count_nonzero(normalized > high_thresh))
                    crowded_fraction = high_density_pixels / roi_area_px

        # --- Layer 2: YOLO head scale calibration ---
        if (head_count >= self.settings.pixel_head_min_detections
                and head_count <= self.settings.pixel_head_max_detections
                and yolo_avg_confidence >= self.settings.pixel_head_min_confidence):
            bbox_areas = [
                (d['bbox'][2] - d['bbox'][0]) * (d['bbox'][3] - d['bbox'][1])
                for d in detections
            ]
            if bbox_areas:
                new_median = float(np.median(bbox_areas))
                if self._cached_head_size_px is not None:
                    self._cached_head_size_px = 0.1 * new_median + 0.9 * self._cached_head_size_px
                else:
                    self._cached_head_size_px = new_median

        head_size_px = self._cached_head_size_px

        # --- Combine layers ---
        if head_size_px and head_size_px > 0:
            px_per_m2 = head_size_px / self.settings.pixel_head_reference_m2
            # Average density (count-based — stable and physically correct)
            avg_density = (final_count / roi_area_px) * px_per_m2
        else:
            # No YOLO scale (cold start) — PET-only fallback
            # Count-based signal is reliable; spatial concentration is secondary
            count_signal = min(final_count / 50.0, 5.0)
            spatial_signal = min(crowded_fraction * 8.0, count_signal * 1.5)
            avg_density = 0.7 * count_signal + 0.3 * spatial_signal

        return max(min(avg_density, 9.0), 0.0)


def process_frame(frame, yolo, pet, frame_num, settings, motion_tracker, density_stabilizer):
    """Process a single frame and return stats using unified fusion"""
    h, w = frame.shape[:2]

    # === LIGHTING ANALYSIS (Phase 5.1) ===
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray) / 255.0)  # 0-1 scale

    # Classify lighting condition
    if brightness > 0.6:
        lighting_level = "BRIGHT"
    elif brightness > 0.4:
        lighting_level = "NORMAL"
    elif brightness > 0.25:
        lighting_level = "DIM"
    else:
        lighting_level = "DARK"

    # YOLO detection with metrics
    t0 = time.time()
    yolo_result = yolo.detect_with_metrics(frame)
    yolo_time = (time.time() - t0) * 1000

    yolo_detections = yolo_result['detections']
    yolo_count = yolo_result['count']
    yolo_occupancy = yolo_result['occupancy_ratio']
    yolo_avg_conf = yolo_result['avg_confidence']

    # PET detection (points + count)
    t0 = time.time()
    points, confidences, pet_count, avg_confidence, conf_std = pet.predict(frame)
    pet_time = (time.time() - t0) * 1000

    # Generate PET density map: required for pixel mode, optional for area mode
    density_map_time = 0.0
    density_map = None
    need_density_map = (settings.density_mode == "pixel") or settings.enable_density_map_generation
    if need_density_map:
        t0 = time.time()
        from utils.point_to_density import points_to_density_map
        density_map = points_to_density_map(
            points=points,
            confidences=confidences,
            image_shape=(h, w),
            sigma=settings.density_gaussian_sigma,
            method="gaussian",
        )
        density_map_time = (time.time() - t0) * 1000

    # Apply unified regime-based fusion
    final_count, fusion_rule, density_regime = compute_fusion(
        yolo_count=yolo_count,
        pet_count=pet_count,
        pet_avg_conf=avg_confidence,
        yolo_occupancy=yolo_occupancy,
        yolo_avg_conf=yolo_avg_conf,
        pet_conf_std=conf_std,
        settings=settings
    )

    # Density calculation (people per m² — pixel or area mode)
    density_avg, raw_density, _ = density_stabilizer.calculate(
        frame=frame,
        points=points,
        yolo_count=yolo_count,
        pet_count=pet_count,
        regime=density_regime,
        final_count=final_count,
        detections=yolo_detections,
        density_map=density_map,
        yolo_avg_confidence=yolo_avg_conf,
    )

    density_level = get_density_level(density_avg, settings)

    # Motion calculation with flow data (m/s output)
    flow, motion_val, divergence = motion_tracker.analyze(frame)
    motion_level = motion_tracker.get_level(motion_val, settings)

    # Turbulence and counter-flow
    turbulence = compute_turbulence(flow)
    is_counter_flow, counter_flow_severity = detect_counter_flow(flow)

    # Kinetic Energy = density × speed² (density now in people/m²)
    kinetic_energy = density_avg * (motion_val ** 2)

    # Risk score calculation (using unified configurable thresholds)
    if density_avg > settings.density_threshold_critical:
        density_score = 80
    elif density_avg > settings.density_threshold_high:
        density_score = 50
    elif density_avg > settings.density_threshold_moderate:
        density_score = 25
    else:
        density_score = density_avg * 15

    # Motion weight based on people count
    if final_count < 15:
        motion_weight = 0.2
    elif final_count < 30:
        motion_weight = 0.5
    else:
        motion_weight = 1.0

    motion_multiplier = 2.0 if density_avg > settings.density_threshold_high else 1.0
    # motion_val is in m/s: 2.5 m/s (fast) * 12 = 30 (full score)
    motion_score = min(motion_val * 12 * motion_multiplier * motion_weight, 30)

    # KE score (thresholds adjusted for people/m² density)
    if kinetic_energy > 30:
        ke_score = 25
    elif kinetic_energy > 15:
        ke_score = 18
    elif kinetic_energy > 8:
        ke_score = 10
    else:
        ke_score = kinetic_energy * 1.0  # Linear scaling
    ke_score = ke_score * motion_weight

    # Turbulence score — only when motion is meaningful (>0.3 = not noise)
    turbulence_score = 0
    if motion_val > 0.3:
        if is_counter_flow and density_avg > settings.density_threshold_moderate:
            turbulence_score = counter_flow_severity * 20 * motion_weight
        elif turbulence > 0.6:
            turbulence_score = turbulence * 12 * motion_weight

    risk_score = density_score + motion_score + ke_score + turbulence_score

    # Static boost for high density static crowds
    if density_avg >= settings.density_threshold_high and motion_val < settings.static_queue_motion_threshold:
         risk_score += 20

    # Count-based risk caps — count is most reliable signal
    if final_count < 15:
        risk_score = min(risk_score, 30)
    elif final_count < 30:
        risk_score = min(risk_score, 45)
    elif final_count < 80:
        risk_score = min(risk_score, 70)

    risk_score = min(100, risk_score)
    risk_level = get_risk_level(risk_score, settings)

    return {
        "frame": frame_num,
        "density_model_name": (settings.density_model or "pet").upper(),
        "yolo_count": yolo_count,
        "pet_count": pet_count,
        "pet_avg_confidence": avg_confidence,
        "pet_conf_std": conf_std,
        "yolo_occupancy": yolo_occupancy,
        "yolo_avg_confidence": yolo_avg_conf,
        "final_count": final_count,
        "fusion_rule": fusion_rule,
        "density_regime": density_regime,
        "brightness": brightness,
        "lighting_level": lighting_level,
        "density_avg": density_avg,
        "density_level": density_level,
        "motion_val": motion_val,
        "motion_level": motion_level,
        "kinetic_energy": kinetic_energy,
        "turbulence": turbulence,
        "is_counter_flow": is_counter_flow,
        "counter_flow_severity": counter_flow_severity,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "yolo_time_ms": yolo_time,
        "pet_time_ms": pet_time,
        "density_map_time_ms": density_map_time,
        "pet_points": points,
        "yolo_detections": yolo_detections
    }


def draw_detections(frame, result):
    """Draw detections on frame for visualization"""
    frame_vis = frame.copy()

    # Draw YOLO boxes (green)
    for det in result["yolo_detections"]:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        cv2.rectangle(frame_vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Draw PET points (red)
    for point in result["pet_points"]:
        x, y = int(point[0]), int(point[1])
        cv2.circle(frame_vis, (x, y), 4, (0, 0, 255), -1)

    # Color coding for regime
    regime_colors = {
        "SPARSE": (255, 200, 100),
        "LOW": (0, 255, 0),
        "MEDIUM": (0, 255, 255),
        "HIGH": (0, 0, 255)
    }
    regime_color = regime_colors.get(result['density_regime'], (255, 255, 255))

    # Add text overlay
    y_offset = 30

    # Counter-flow indicator
    cf_text = f" | CF: {result['counter_flow_severity']:.0%}" if result['is_counter_flow'] else ""

    density_label = result.get("density_model_name", "PET")
    texts = [
        f"Frame: {result['frame']} | Regime: {result['density_regime']} | Light: {result.get('lighting_level', 'N/A')}",
        f"YOLO: {result['yolo_count']} (occ={result['yolo_occupancy']:.2f}, conf={result['yolo_avg_confidence']:.2f})",
        f"{density_label}: {result['pet_count']} (conf={result['pet_avg_confidence']:.2f}, std={result['pet_conf_std']:.2f})",
        f"Final: {result['final_count']} | {result['fusion_rule'][:40]}",
        f"Density: {result['density_avg']:.2f} ({result['density_level']}) | Risk: {result['risk_level']} ({result['risk_score']:.0f})",
        f"Motion: {result['motion_val']:.3f} m/s ({result['motion_level']}) | KE: {result['kinetic_energy']:.1f} | Turb: {result['turbulence']:.2f}{cf_text}"
    ]

    for i, text in enumerate(texts):
        color = regime_color if i == 0 else (255, 255, 255)
        cv2.putText(frame_vis, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame_vis, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 1, cv2.LINE_AA)
        y_offset += 22

    return frame_vis


def main():
    parser = argparse.ArgumentParser(description="Test model accuracy on video file")
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to process (default: 100)")
    parser.add_argument("--skip", type=int, default=1, help="Process every Nth frame (default: 1)")
    parser.add_argument("--show", action="store_true", help="Show frames with detections")
    parser.add_argument("--device", default="cuda", help="Device: cuda or cpu (default: cuda)")
    parser.add_argument("--output", help="Save output video to file")
    parser.add_argument("--camera", default="cam_pf1_fob_kzj", help="Camera ID for calibration (default: cam_pf1_fob_kzj)")
    parser.add_argument("--density-model", choices=["pet"],
                        help="Density backend for testing (PET only)")
    parser.add_argument("--no-count-calibration", action="store_true",
                        help="Disable post-fusion count calibration for A/B testing")
    parser.add_argument("--density-map", dest="density_map", action="store_true",
                        help="Force density-map generation (adds latency, for A/B testing)")
    parser.add_argument("--no-density-map", dest="density_map", action="store_false",
                        help="Disable density-map generation (fast path latency test)")
    parser.add_argument("--python-post-nms", dest="python_post_nms", action="store_true",
                        help="Enable additional Python NMS in YOLO wrapper (for A/B testing)")
    parser.add_argument("--no-python-post-nms", dest="python_post_nms", action="store_false",
                        help="Disable additional Python NMS in YOLO wrapper (recommended)")
    parser.add_argument("--log-every", type=int, default=1,
                        help="Print one row every N processed frames (default: 1)")
    parser.add_argument("--summary-json",
                        help="Optional output path for machine-readable summary JSON")
    parser.add_argument("--area-m2", type=float, default=None,
                        help="Override visible area (m²) for density/motion calculation. "
                             "If not set, uses camera calibration value.")
    parser.add_argument("--flow-interval", type=int, default=3,
                        help="Compute optical flow every N processed frames (default: 3)")
    parser.add_argument("--density-mode", choices=["pixel", "area"], default=None,
                        help="Density estimation mode: 'pixel' (PET map + YOLO head scale) "
                             "or 'area' (count / area_m2). Default: from config.")
    parser.set_defaults(density_map=None, python_post_nms=None)
    args = parser.parse_args()

    # Check video exists
    if not os.path.exists(args.video_path):
        print(f"ERROR: Video file not found: {args.video_path}")
        sys.exit(1)

    # Load settings
    settings = get_settings()
    settings.device = args.device
    if args.density_model:
        settings.density_model = args.density_model
    if (settings.density_model or "pet").lower() != "pet":
        print(f"[WARNING] DENSITY_MODEL='{settings.density_model}' is deprecated. Forcing PET.")
    settings.density_model = "pet"
    if args.no_count_calibration:
        settings.count_calibration_enabled = False
    if args.density_map is not None:
        settings.enable_density_map_generation = bool(args.density_map)
    if args.python_post_nms is not None:
        settings.yolo_python_post_nms_enabled = bool(args.python_post_nms)
    if args.density_mode:
        settings.density_mode = args.density_mode

    # Open video
    print(f"\n[DEBUG] Opening video: {args.video_path}")
    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {args.video_path}")
        sys.exit(1)

    # Test read
    ret, test_frame = cap.read()
    if not ret:
        print("[ERROR] Failed to read first frame from video!")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("\n" + "="*60)
    print("VIDEO INFO")
    print("="*60)
    print(f"File: {args.video_path}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps:.2f}")
    print(f"Total frames: {total_frames}")
    print(f"Density model: {settings.density_model}")
    print(f"Density mode: {settings.density_mode}")
    print(f"Density map generation: {'ON' if settings.enable_density_map_generation or settings.density_mode == 'pixel' else 'OFF'}")
    print(f"YOLO Python post-NMS: {'ON' if settings.yolo_python_post_nms_enabled else 'OFF'}")
    print(f"Count calibration: {'ON' if settings.count_calibration_enabled else 'OFF'}")
    if settings.count_calibration_enabled:
        print(
            "Calibration bins: "
            f"<{settings.count_calibration_bin1_max} x{settings.count_calibration_scale_bin1}, "
            f"{settings.count_calibration_bin1_max}-{settings.count_calibration_bin2_max} x{settings.count_calibration_scale_bin2}, "
            f"{settings.count_calibration_bin2_max}-{settings.count_calibration_bin3_max} x{settings.count_calibration_scale_bin3}, "
            f"{settings.count_calibration_bin3_max}+ x{settings.count_calibration_scale_bin4}"
        )
    print(f"PET adaptive fusion: {'ON' if settings.pet_use_adaptive_fusion else 'OFF'}")
    print(
        "PET fusion guard: "
        f"{'ON' if settings.fusion_pet_guard_enabled else 'OFF'} "
        f"(min_count={settings.fusion_pet_guard_min_count}, "
        f"min_occ={settings.fusion_pet_guard_min_occupancy}, "
        f"skip_cal={'ON' if settings.fusion_pet_guard_skip_calibration else 'OFF'})"
    )
    # Load models
    yolo, pet, _, density_label = load_models(
        device=args.device,
        density_model=args.density_model
    )
    # Use camera-specific calibration for density calculation
    density_stabilizer = DensityStabilizer(settings, camera_id=args.camera)

    # Show calibration info
    from utils.perspective import CalibrationManager
    calibration = CalibrationManager().get_calibration(args.camera)
    print(f"\nCalibration loaded for {args.camera}: {calibration}")

    # Allow area override for arbitrary test videos
    effective_area_m2 = args.area_m2 if args.area_m2 else calibration.visible_area_m2
    if args.area_m2:
        density_stabilizer.set_area_m2(args.area_m2)
        print(f"  Area override: {args.area_m2} m² (from --area-m2)")

    # Motion tracker needs area_m2 + video FPS for m/s conversion
    # In pixel mode, pass density_stabilizer so area_m2 updates dynamically from YOLO head scale
    motion_tracker = MotionTracker(
        area_m2=effective_area_m2,
        video_fps=fps,
        frame_skip=args.skip,
        flow_interval=args.flow_interval,
        density_stabilizer=density_stabilizer if settings.density_mode == "pixel" else None,
    )
    flow_elapsed = args.flow_interval * args.skip / fps
    area_source = "pixel (YOLO head scale)" if settings.density_mode == "pixel" else f"{effective_area_m2:.1f}m²"
    print(f"  Motion config: area={area_source}, flow_elapsed={flow_elapsed:.3f}s "
          f"(interval={args.flow_interval} × skip={args.skip} / fps={fps:.0f})")

    print("\n" + "="*60)
    print(f"PROCESSING FRAMES (Standard + KE/Turbulence + {density_label})")
    print("="*60)
    print(f"{'Frame':>6} | {'YOLO':>5} | {'PET':>5} | {'Final':>5} | {'Density':>7} | {'Motion':>8} | {'KE':>6} | {'Turb':>5} | {'Risk':>12} | {'Time':>8}")
    print("-"*190)

    # Setup output video
    out_writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(args.output, fourcc, fps/args.skip, (width, height))
        print(f"Output video: {args.output}")

    results = []
    frame_num = 0
    processed = 0

    while processed < args.frames:
        ret, frame = cap.read()
        if not ret:
            break

        frame_num += 1

        if frame_num % args.skip != 0:
            continue

        # Process frame
        try:
            result = process_frame(frame, yolo, pet, frame_num, settings, motion_tracker, density_stabilizer)
            total_time = result["yolo_time_ms"] + result["pet_time_ms"] + result["density_map_time_ms"]
            cf = "*" if result['is_counter_flow'] else ""
            risk_str = f"{result['risk_level']}({result['risk_score']:.0f})"
            should_log_frame = args.log_every <= 1 or (processed + 1) % args.log_every == 0
            if should_log_frame:
                print(f"{result['frame']:>6} | {result['yolo_count']:>5} | {result['pet_count']:>5} | "
                      f"{result['final_count']:>5} | {result['density_avg']:>7.2f} | {result['motion_val']:>7.3f}  | {result['kinetic_energy']:>6.1f} | "
                      f"{result['turbulence']:>4.2f}{cf} | {risk_str:>12} | {total_time:>6.0f}ms")
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Crash at frame {frame_num}: {e}")
            traceback.print_exc()
            break

        results.append(result)
        processed += 1

        # Show/save frame
        if args.show or out_writer:
            frame_vis = draw_detections(frame, result)

            if args.show:
                cv2.imshow("Model Test", frame_vis)
                key = cv2.waitKey(1)
                if key == 27:  # ESC to quit
                    break
                elif key == ord(' '):  # Pause/resume
                    print("\n[PAUSED] Press any key to continue...")
                    cv2.waitKey(0)

            if out_writer:
                out_writer.write(frame_vis)

    cap.release()
    if out_writer:
        out_writer.release()
    if args.show:
        cv2.destroyAllWindows()

    # Summary statistics
    if results:
        print("\n" + "="*60)
        print("SUMMARY STATISTICS")
        print("="*60)
        print(f"\nFrames processed: {len(results)}")

        density_label = results[0].get("density_model_name", "PET")
        yolo_counts = [r["yolo_count"] for r in results]
        pet_counts = [r["pet_count"] for r in results]
        final_counts = [r["final_count"] for r in results]
        kinetic_energies = [r["kinetic_energy"] for r in results]
        turbulences = [r["turbulence"] for r in results]

        print(f"\n{'Metric':<20} | {'YOLO':>10} | {density_label[:10]:>10} | {'Final':>10}")
        print("-"*60)
        print(f"{'Min count':<20} | {min(yolo_counts):>10} | {min(pet_counts):>10} | {min(final_counts):>10}")
        print(f"{'Max count':<20} | {max(yolo_counts):>10} | {max(pet_counts):>10} | {max(final_counts):>10}")
        print(f"{'Avg count':<20} | {np.mean(yolo_counts):>10.1f} | {np.mean(pet_counts):>10.1f} | {np.mean(final_counts):>10.1f}")

        # Motion, Kinetic Energy & Turbulence stats
        motion_vals = [r["motion_val"] for r in results]
        print("\n" + "-"*60)
        print("ADVANCED METRICS:")
        print(f"  Motion (m/s): min={min(motion_vals):.3f}, max={max(motion_vals):.3f}, avg={np.mean(motion_vals):.3f}")
        print(f"  Kinetic Energy: min={min(kinetic_energies):.1f}, max={max(kinetic_energies):.1f}, avg={np.mean(kinetic_energies):.1f}")
        print(f"  Turbulence: min={min(turbulences):.2f}, max={max(turbulences):.2f}, avg={np.mean(turbulences):.2f}")

        counter_flow_frames = sum(1 for r in results if r['is_counter_flow'])
        print(f"  Counter-flow detected: {counter_flow_frames} frames ({counter_flow_frames/len(results)*100:.1f}%)")

        # Motion level distribution
        print("\n" + "-"*60)
        print("MOTION LEVEL DISTRIBUTION:")
        motion_level_counts = {}
        for r in results:
            ml = r["motion_level"]
            motion_level_counts[ml] = motion_level_counts.get(ml, 0) + 1

        for level in ["STATIC", "SLOW", "NORMAL", "FAST", "RUNNING"]:
            count = motion_level_counts.get(level, 0)
            pct = count / len(results) * 100
            bar = "*" * int(pct / 2)
            print(f"  {level:<10}: {count:>4} frames ({pct:>5.1f}%) {bar}")

        # Lighting condition analysis (Phase 5.1)
        print("\n" + "-"*60)
        print("ACCURACY BY LIGHTING CONDITION:")
        lighting_groups = {"BRIGHT": [], "NORMAL": [], "DIM": [], "DARK": []}
        for r in results:
            level = r.get('lighting_level', 'UNKNOWN')
            if level in lighting_groups:
                lighting_groups[level].append(r)

        for level in ["BRIGHT", "NORMAL", "DIM", "DARK"]:
            group = lighting_groups[level]
            if not group:
                continue

            avg_count = np.mean([r['final_count'] for r in group])
            avg_conf = np.mean([r['yolo_avg_confidence'] for r in group])
            avg_density = np.mean([r['density_avg'] for r in group])

            print(f"  {level:<8}: {len(group):>3} frames | "
                  f"Avg Count: {avg_count:>6.1f} | "
                  f"Avg Conf: {avg_conf:.3f} | "
                  f"Avg Density: {avg_density:.2f}/m²")

        # Regime distribution
        print("\n" + "-"*60)
        print("DENSITY REGIME DISTRIBUTION:")
        regime_counts = {}
        for r in results:
            regime = r["density_regime"]
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        for regime in ["SPARSE", "LOW", "MEDIUM", "HIGH"]:
            count = regime_counts.get(regime, 0)
            pct = count / len(results) * 100
            bar = "*" * int(pct / 2)
            print(f"  {regime:<8}: {count:>4} frames ({pct:>5.1f}%) {bar}")

        # Density level distribution (output labels: LOW/MODERATE/HIGH/CRITICAL)
        print("\nDENSITY LEVEL DISTRIBUTION:")
        dl_counts = {}
        for r in results:
            dl = r["density_level"]
            dl_counts[dl] = dl_counts.get(dl, 0) + 1
        for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            count = dl_counts.get(level, 0)
            pct = count / len(results) * 100
            bar = "*" * int(pct / 2)
            print(f"  {level:<10}: {count:>4} frames ({pct:>5.1f}%) {bar}")

        # Risk distribution
        print("\n" + "-"*60)
        print("RISK LEVEL DISTRIBUTION:")
        risk_counts = {}
        for r in results:
            level = r["risk_level"]
            risk_counts[level] = risk_counts.get(level, 0) + 1

        for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            count = risk_counts.get(level, 0)
            pct = count / len(results) * 100
            bar = "*" * int(pct / 2)
            print(f"  {level:<10}: {count:>4} frames ({pct:>5.1f}%) {bar}")

        # Performance
        print("\n" + "-"*60)
        print("PERFORMANCE:")
        yolo_times = [r["yolo_time_ms"] for r in results]
        pet_times = [r["pet_time_ms"] for r in results]
        density_map_times = [r["density_map_time_ms"] for r in results]
        total_times = [r["yolo_time_ms"] + r["pet_time_ms"] + r["density_map_time_ms"] for r in results]
        yolo_perf = summarize_latency_ms(yolo_times)
        pet_perf = summarize_latency_ms(pet_times)
        density_map_perf = summarize_latency_ms(density_map_times)
        total_perf = summarize_latency_ms(total_times)
        effective_fps = 1000 / total_perf["avg"] if total_perf["avg"] > 0 else 0.0

        print(f"  YOLO (avg/p50/p95):        {yolo_perf['avg']:>6.1f}/{yolo_perf['p50']:>6.1f}/{yolo_perf['p95']:>6.1f} ms")
        print(f"  PET (avg/p50/p95):         {pet_perf['avg']:>6.1f}/{pet_perf['p50']:>6.1f}/{pet_perf['p95']:>6.1f} ms")
        print(f"  Density map (avg/p50/p95): {density_map_perf['avg']:>6.1f}/{density_map_perf['p50']:>6.1f}/{density_map_perf['p95']:>6.1f} ms")
        print(f"  Total (avg/p50/p95):       {total_perf['avg']:>6.1f}/{total_perf['p50']:>6.1f}/{total_perf['p95']:>6.1f} ms")
        print(f"  Effective FPS (avg):       {effective_fps:>6.1f}")

        if args.summary_json:
            summary_payload = {
                "video_path": args.video_path,
                "frames_processed": len(results),
                "device": args.device,
                "camera_id": args.camera,
                "density_model": settings.density_model,
                "toggles": {
                    "density_map_generation": bool(settings.enable_density_map_generation),
                    "yolo_python_post_nms_enabled": bool(settings.yolo_python_post_nms_enabled),
                    "count_calibration_enabled": bool(settings.count_calibration_enabled),
                },
                "performance_ms": {
                    "yolo": yolo_perf,
                    "pet": pet_perf,
                    "density_map": density_map_perf,
                    "total": total_perf,
                },
                "effective_fps_avg": float(effective_fps),
                "count_summary": {
                    "yolo_avg": float(np.mean(yolo_counts)),
                    "pet_avg": float(np.mean(pet_counts)),
                    "final_avg": float(np.mean(final_counts)),
                },
            }
            with open(args.summary_json, "w", encoding="utf-8") as f:
                json.dump(summary_payload, f, indent=2)
            print(f"  Summary JSON saved: {args.summary_json}")

        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)


if __name__ == "__main__":
    main()
