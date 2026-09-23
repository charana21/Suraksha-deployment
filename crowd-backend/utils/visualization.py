"""
Visualization utilities
"""
import cv2
import numpy as np
from typing import Dict, List, Tuple
from scipy.ndimage import gaussian_filter
import logging
logger = logging.getLogger(__name__)

def _generate_detection_heatmap(detections: List[Dict], h: int, w: int) -> np.ndarray:
    """
    Generate heatmap from YOLO detections using Gaussian blobs
    This serves as a fallback when PET density is invalid
    """
    heatmap = np.zeros((h, w), dtype=np.float32)

    if len(detections) == 0:
        return heatmap

    # Create Gaussian blob for each detection
    for det in detections:
        cx, cy = det['center']
        bbox = det['bbox']

        # Determine blob size from bounding box
        box_w = bbox[2] - bbox[0]
        box_h = bbox[3] - bbox[1]
        sigma = max(box_w, box_h) * 0.6  # Gaussian spread based on detection size
        sigma = max(sigma, 8)  # Minimum sigma

        # Create coordinate grids
        y_grid, x_grid = np.ogrid[0:h, 0:w]

        # Gaussian formula: exp(-((x-cx)^2 + (y-cy)^2) / (2*sigma^2))
        gaussian = np.exp(-((x_grid - cx)**2 + (y_grid - cy)**2) / (2 * sigma**2))

        # Accumulate
        heatmap += gaussian

    # Smooth the result
    heatmap = gaussian_filter(heatmap, sigma=3.0)

    return heatmap


def _risk_score_to_color(risk_score: float, settings) -> tuple:
    """
    Map risk score (0-100) to RGBA color

    Args:
        risk_score: Risk score from 0-100
        settings: Configuration settings with color definitions

    Returns:
        (B, G, R, A) tuple
    """
    risk_score = max(0, min(100, risk_score))

    if risk_score < 25:
        return settings.risk_color_blue
    elif risk_score < 50:
        return settings.risk_color_green
    elif risk_score < 75:
        return settings.risk_color_yellow
    else:
        return settings.risk_color_red


def visualize_risk_heatmap(
    frame: np.ndarray,
    risk_score: float,
    settings
) -> np.ndarray:
    """
    Generate full-frame risk-based heatmap overlay

    Args:
        frame: Original frame
        risk_score: Risk score from 0-100
        settings: Configuration settings

    Returns:
        Frame with risk-based color overlay
    """
    output = frame.copy()
    h, w = frame.shape[:2]

    # Get risk color (BGRA)
    b, g, r, a = _risk_score_to_color(risk_score, settings)

    # Create solid color overlay
    overlay = np.zeros((h, w, 3), dtype=np.uint8)
    overlay[:, :] = (b, g, r)

    # Blend with alpha
    alpha = settings.risk_heatmap_alpha
    output = cv2.addWeighted(output, 1.0 - alpha, overlay, alpha, 0)

    return output


def _is_density_map_valid(density: np.ndarray) -> Tuple[bool, float, int]:
    """Check if a PET density map has meaningful signal and spatial variation.

    Returns (is_valid, density_max, density_nonzero) for reuse by the caller.
    """
    density_max = np.max(density)
    density_mean = np.mean(density)
    density_nonzero = np.count_nonzero(density > 0.001)

    print(f"[HEATMAP] Density stats: max={density_max:.4f}, mean={density_mean:.4f}, nonzero_pixels={density_nonzero}")

    # Check if density map has meaningful spatial variation
    # If PET output is too uniform, it's likely not working properly
    density_std = np.std(density)
    spatial_variation = density_std / (density_mean + 1e-10)

    is_valid = (
        density_max > 0.0001 and  # Has some signal
        density_nonzero > 100 and  # Reasonable coverage
        spatial_variation > 0.01  # Has spatial variation (lowered threshold for PET native resolution)
    )

    if not is_valid:
        logger.info(f"[HEATMAP] PET density invalid (std={density_std:.6f}, variation={spatial_variation:.2f}), using detection-based heatmap")

    return is_valid, density_max, density_nonzero


def _normalize_pet_density(
    density: np.ndarray, density_max: float, density_nonzero: int, people_count: int
) -> np.ndarray:
    """Use PET density map"""
    print("[HEATMAP] Using PET density map")

    # Use adaptive percentile clipping based on data distribution
    # For very sparse data, use lower percentile; for dense data, use higher
    if density_nonzero < 500:
        clip_percentile = 95
    elif density_nonzero < 2000:
        clip_percentile = 97
    else:
        clip_percentile = 99

    percentile_clip = np.percentile(density, clip_percentile)

    # If the percentile is too close to max, use a different strategy
    if percentile_clip < density_max * 0.5:
        percentile_clip = density_max * 0.8

    density_clipped = np.clip(density, 0, percentile_clip)

    # Apply gamma correction to enhance visibility of mid-range values
    if percentile_clip > 0:
        density_normalized = density_clipped / percentile_clip

        # Adaptive gamma: more people = higher gamma (less aggressive brightening)
        gamma = min(0.7 + (people_count / 100) * 0.2, 1.0)

        density_gamma = np.power(density_normalized, gamma)
        density_norm = (density_gamma * 255).astype(np.uint8)
    else:
        density_norm = np.zeros_like(density, dtype=np.uint8)

    # Ensure we have some contrast
    if np.max(density_norm) < 50:
        # Stretch the histogram to use full range
        min_val = np.min(density_norm)
        max_val = np.max(density_norm)
        if max_val > min_val:
            density_norm = ((density_norm - min_val) / (max_val - min_val) * 255).astype(np.uint8)

    return density_norm


def _normalize_detection_heatmap(
    detections: List[Dict], h: int, w: int, people_count: int
) -> np.ndarray:
    """Fallback to detection-based heatmap"""
    print(f"[HEATMAP] PET density invalid, using detection-based heatmap ({len(detections)} detections)")

    detection_heatmap = _generate_detection_heatmap(detections, h, w)

    # Normalize detection heatmap with gamma correction
    heatmap_max = np.max(detection_heatmap)
    if heatmap_max > 0:
        normalized = detection_heatmap / heatmap_max
        gamma = min(0.7 + (people_count / 100) * 0.2, 1.0)
        gamma_corrected = np.power(normalized, gamma)
        return (gamma_corrected * 255).astype(np.uint8)
    return np.zeros((h, w), dtype=np.uint8)


def _normalize_density_for_heatmap(
    density: np.ndarray,
    detections: List[Dict],
    h: int,
    w: int,
    people_count: int = 0,
    settings = None
) -> np.ndarray:
    """
    Normalize density map for heatmap visualization with proper validation
    Falls back to detection-based heatmap if density is invalid

    Args:
        density: Density map from PET
        detections: YOLO detections (for fallback)
        h: Frame height
        w: Frame width
        people_count: Total people count in frame (for railway station mode)
        settings: Configuration settings (for railway station mode)
    """
    is_valid, density_max, density_nonzero = _is_density_map_valid(density)

    if is_valid:
        density_norm = _normalize_pet_density(density, density_max, density_nonzero, people_count)
    else:
        density_norm = _normalize_detection_heatmap(detections, h, w, people_count)

    logger.info(f"[HEATMAP] Output range: min={np.min(density_norm)}, max={np.max(density_norm)}, mean={np.mean(density_norm):.1f}")

    return density_norm


def visualize_heatmap_only(
    frame: np.ndarray,
    detections: List[Dict],
    density: np.ndarray,
    accumulated_heatmap: np.ndarray = None,
    alpha: float = 0.6,
    people_count: int = 0,
    risk_score: float = 0.0,
    settings = None
) -> np.ndarray:
    """
    Generate clean heatmap visualization without any detection overlays

    Args:
        frame: Original frame
        detections: YOLO detections (used as fallback if PET fails)
        density: PET density map
        accumulated_heatmap: Optional accumulated heatmap for temporal accumulation
        alpha: Transparency of heatmap overlay (0-1, higher = more opaque)
        people_count: Total people count in frame (for railway station mode)
        risk_score: Risk score from 0-100 (for risk-based visualization)
        settings: Configuration settings (for railway station mode)

    Returns:
        Frame with heatmap overlay only
    """
    output = frame.copy()
    h, w = frame.shape[:2]

    # Risk-based visualization removed as per user request (was considered "useless gradient")
    # Fall through to standard density-based heatmap visualization below

    # Otherwise fall back to legacy density-based visualization
    # Get normalized density map (with fallback to detection-based heatmap)
    density_norm = _normalize_density_for_heatmap(density, detections, h, w, people_count, settings)

    # If accumulated heatmap is provided, blend it with current frame's density
    if accumulated_heatmap is not None:
        # Normalize accumulated heatmap
        acc_max = np.max(accumulated_heatmap)
        if acc_max > 0:
            acc_norm = (accumulated_heatmap / acc_max * 255).astype(np.uint8)
        else:
            acc_norm = np.zeros((h, w), dtype=np.uint8)

        # Blend current with accumulated (70% accumulated, 30% current)
        density_norm = cv2.addWeighted(acc_norm, 0.7, density_norm, 0.3, 0)

    # Resize density_norm to match frame dimensions if needed
    if density_norm.shape[0] != h or density_norm.shape[1] != w:
        density_norm = cv2.resize(density_norm, (w, h), interpolation=cv2.INTER_CUBIC)

    # Apply JET colormap (blue=low, green=medium, yellow/red=high)
    heatmap = cv2.applyColorMap(density_norm, cv2.COLORMAP_JET)

    # Blend with original frame
    output = cv2.addWeighted(output, 1.0 - alpha, heatmap, alpha, 0)

    # Draw detection boxes if enabled
    if settings and settings.show_detection_boxes and detections:
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            cx, cy = det['center']

            # Draw bounding box (magenta)
            cv2.rectangle(output, (x1, y1), (x2, y2), (255, 0, 255), 2)

            # Draw center dot (green)
            cv2.circle(output, (cx, cy), 3, (0, 255, 0), -1)

    return output


def visualize_analysis(
    frame: np.ndarray,
    detections: List[Dict],
    zones: Dict[str, Dict],
    density: np.ndarray,
    frame_number: int,
    people_count: int = 0,
    settings = None
) -> np.ndarray:
    """Create comprehensive visualization"""
    output = frame.copy()
    h, w = frame.shape[:2]

    # Always use density-based heatmap (removed risk overlay per request)
    density_norm = _normalize_density_for_heatmap(density, detections, h, w, people_count, settings)
    heatmap = cv2.applyColorMap(density_norm, cv2.COLORMAP_JET)
    output = cv2.addWeighted(output, 0.55, heatmap, 0.45, 0)

    # Draw detections
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        cx, cy = det['center']

        cv2.rectangle(output, (x1, y1), (x2, y2), (255, 0, 255), 2)
        cv2.circle(output, (cx, cy), 3, (0, 255, 0), -1)

    # Get single zone info for risk-based border
    color_map = {
        'LOW': (0, 255, 0),
        'MEDIUM': (0, 255, 255),
        'HIGH': (0, 165, 255),
        'CRITICAL': (0, 0, 255)
    }

    # Draw border based on risk level (single full-frame zone)
    if zones:
        # Use iterator to avoid materializing the full list of values
        zone = next(iter(zones.values()))  # Get the single full-frame zone
        color = color_map.get(zone['risk_level'], (255, 255, 255))

        # Draw border around entire frame
        border_thickness = 8
        cv2.rectangle(output, (0, 0), (w - 1, h - 1), color, border_thickness)

    # Global stats from single full-frame zone
    if zones:
        # Use iterator to avoid materializing the full list of values
        zone = next(iter(zones.values()))
        total_people = zone['people_count']
        risk_level = zone['risk_level']
        risk_score = zone['risk_score']
        density_level = zone['density_level']
    else:
        total_people = 0
        risk_level = "UNKNOWN"
        risk_score = 0
        density_level = "UNKNOWN"

    stats = [
        f"Frame {frame_number}",
        f"Count: {total_people} people",
        f"Density: {density_level}",
        f"Risk: {risk_level} ({risk_score:.0f})"
    ]

    panel_x, panel_y = 10, 10
    for i, text in enumerate(stats):
        y_pos = panel_y + i * 28

        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

        cv2.rectangle(
            output,
            (panel_x, y_pos - text_h - 3),
            (panel_x + text_w + 10, y_pos + 3),
            (0, 0, 0),
            -1
        )

        cv2.rectangle(
            output,
            (panel_x, y_pos - text_h - 3),
            (panel_x + text_w + 10, y_pos + 3),
            (0, 255, 0),
            2
        )

        cv2.putText(
            output, text,
            (panel_x + 5, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (0, 255, 0), 2, cv2.LINE_AA
        )

    return output
