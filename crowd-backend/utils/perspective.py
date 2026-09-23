"""
Camera Calibration Module

Supports two calibration modes:
1. Simple visible_area_m2: density = count / area (quick deployment)
2. Homography: Full 3x3 matrix for precise pixel-to-world conversion

Usage:
    calibration = CalibrationManager().get_calibration("cam_pf1_fob_kzj")
    density = people_count / calibration.visible_area_m2

    # If homography is configured:
    world_x, world_y = calibration.pixel_to_world(pixel_x, pixel_y)
"""

import json
import logging
import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
logger = logging.getLogger(__name__)

class PerspectiveCalibration:
    """
    Per-camera calibration.

    Primary approach: Simple visible_area_m2
    - Each camera has a configured visible area in m²
    - Density = people_count / visible_area_m2
    - Easy to calibrate: just measure the real area the camera sees
    """

    def __init__(self, camera_id: str, config: dict):
        self.camera_id = camera_id
        self.visible_area_m2 = config.get('visible_area_m2', 150.0)
        self.corridor_width_m = config.get('corridor_width_m', 4.0)
        self.coverage_length_m = config.get('coverage_length_m', 40.0)
        self.lane_count = config.get('lane_count', 1)
        self.camera_type = config.get('camera_type', 'unknown')
        self.notes = config.get('notes', '')

    def get_visible_area(self) -> float:
        """Get the configured visible area in m²."""
        return self.visible_area_m2

    def to_dict(self) -> dict:
        """Convert calibration to dictionary for serialization."""
        return {
            'camera_id': self.camera_id,
            'visible_area_m2': self.visible_area_m2,
            'corridor_width_m': self.corridor_width_m,
            'coverage_length_m': self.coverage_length_m,
            'lane_count': self.lane_count,
            'camera_type': self.camera_type,
            'notes': self.notes
        }

    def __repr__(self) -> str:
        return (f"PerspectiveCalibration(camera_id='{self.camera_id}', "
                f"visible_area_m2={self.visible_area_m2}, "
                f"corridor={self.coverage_length_m}m x {self.corridor_width_m}m)")


# ============================================================
# STANDALONE ROI FILTERING (uses camera_config from DB)
# ============================================================

def build_roi_contour(
    roi_points: List[List[float]],
    frame_w: int,
    frame_h: int,
    actual_w: int = None,
    actual_h: int = None,
) -> np.ndarray:
    """
    Build OpenCV contour from ROI points, scaling if frame size differs.

    Args:
        roi_points: [[x_px, y_px], ...] polygon vertices in pixel coords
        frame_w: Frame width when ROI was drawn
        frame_h: Frame height when ROI was drawn
        actual_w: Actual frame width at runtime (None = same as frame_w)
        actual_h: Actual frame height at runtime (None = same as frame_h)

    Returns:
        numpy contour array for cv2.pointPolygonTest
    """
    if actual_w and actual_h and (actual_w != frame_w or actual_h != frame_h):
        # Scale ROI points proportionally to current frame size
        scale_x = actual_w / frame_w
        scale_y = actual_h / frame_h
        scaled = [[p[0] * scale_x, p[1] * scale_y] for p in roi_points]
    else:
        scaled = roi_points

    return np.array(scaled, dtype=np.float32).reshape(-1, 1, 2)


def _build_roi_contour(
    roi_points: List[List[float]],
    frame_w: int,
    frame_h: int,
    actual_w: int = None,
    actual_h: int = None,
) -> np.ndarray:
    """Backward-compatible alias for older call sites."""
    return build_roi_contour(roi_points, frame_w, frame_h, actual_w, actual_h)


def get_roi_signature(roi_points: List[List[float]]) -> Tuple:
    """Create stable signature for ROI cache keys."""
    if not roi_points:
        return tuple()
    signature = []
    for p in roi_points:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        signature.append((round(float(p[0]), 3), round(float(p[1]), 3)))
    return tuple(signature)


def foot_point_in_roi(bbox: list, roi_contour: np.ndarray) -> bool:
    """
    Check if the foot point (bottom-center of bounding box) is inside the ROI polygon.

    Foot point = bottom center of bbox, representing where the person stands.
    This is more accurate than using bbox center for ground-plane ROI filtering.

    Args:
        bbox: [x1, y1, x2, y2] bounding box coordinates
        roi_contour: Pre-built contour from _build_roi_contour()

    Returns:
        True if foot point is inside or on the ROI boundary
    """
    foot_x = (bbox[0] + bbox[2]) / 2.0
    foot_y = bbox[3]  # Bottom of bbox = where person stands
    result = cv2.pointPolygonTest(roi_contour, (foot_x, foot_y), False)
    return result >= 0  # >= 0 means inside or on edge


def filter_detections_by_roi(
    detections: List[Dict],
    roi_points: List[List[float]],
    frame_w: int,
    frame_h: int,
    actual_w: int = None,
    actual_h: int = None
) -> List[Dict]:
    """
    Filter detections to only those with foot points inside ROI polygon.

    Args:
        detections: List of detection dicts with 'bbox' key [x1, y1, x2, y2]
        roi_points: ROI polygon vertices [[x_px, y_px], ...]
        frame_w: Frame width when ROI was drawn
        frame_h: Frame height when ROI was drawn
        actual_w: Current frame width (None = same as frame_w)
        actual_h: Current frame height (None = same as frame_h)

    Returns:
        Filtered list of detections with foot points inside ROI
    """
    if not roi_points or not detections:
        return detections

    contour = build_roi_contour(roi_points, frame_w, frame_h, actual_w, actual_h)
    return [d for d in detections if foot_point_in_roi(d['bbox'], contour)]


def create_roi_mask(
    map_shape: Tuple[int, int],
    roi_points: List[List[float]],
    frame_w: int,
    frame_h: int
) -> np.ndarray:
    """
    Create a binary mask for the ROI polygon at arbitrary resolution (e.g., density map size).

    The ROI points are in pixel coordinates of the original frame. This function scales
    them to the target map resolution.

    Args:
        map_shape: (height, width) of the target mask
        roi_points: ROI polygon vertices [[x_px, y_px], ...] in original frame coords
        frame_w: Original frame width
        frame_h: Original frame height

    Returns:
        Binary mask (float32, 0.0 or 1.0) at map_shape resolution
    """
    map_h, map_w = map_shape[:2]

    # Scale ROI points from original frame coords to map resolution
    scale_x = map_w / frame_w
    scale_y = map_h / frame_h
    scaled = [[p[0] * scale_x, p[1] * scale_y] for p in roi_points]
    contour = np.array(scaled, dtype=np.int32).reshape(-1, 1, 2)

    mask = np.zeros((map_h, map_w), dtype=np.float32)
    cv2.fillPoly(mask, [contour], 1.0)
    return mask


class CalibrationManager:
    """
    Manages perspective calibrations for multiple cameras.
    Loads from JSON config file and provides default calibrations.

    Supports both simple PerspectiveCalibration and HomographyCalibration.
    Automatically returns HomographyCalibration when homography data is configured.
    """

    DEFAULT_FOB_CALIBRATION = {
        'visible_area_m2': 150.0,
        'corridor_width_m': 4.0,
        'coverage_length_m': 40.0,
        'lane_count': 1,
        'camera_type': 'default',
        'notes': 'Default FOB calibration (~40m x 4m)'
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize calibration manager.

        Args:
            config_path: Path to camera_calibrations.json
                        If None, uses default path in config directory
        """
        # Store as Union type to support both calibration classes
        self._calibrations: Dict[str, Union[PerspectiveCalibration, 'HomographyCalibration']] = {}
        self._config_path = config_path

        if config_path is None:
            base_dir = Path(__file__).parent.parent
            self._config_path = str(base_dir / 'config' / 'camera_calibrations.json')

        self._load_calibrations()

    def _build_calibration(self, camera_id: str, config: dict) -> Tuple[Union[PerspectiveCalibration, 'HomographyCalibration'], bool]:
        """Build a calibration for one camera. Returns (calibration, used_homography)."""
        if config.get('homography', {}).get('enabled', False):
            try:
                from utils.homography import HomographyCalibration
                return HomographyCalibration(camera_id, config), True
            except ImportError:
                pass  # Fallback if homography module not available
        return PerspectiveCalibration(camera_id, config), False

    def _load_calibrations_from_file(self) -> None:
        with open(self._config_path, 'r') as f:
            data = json.load(f)

        homography_count = 0
        for camera_id, config in data.items():
            # Skip metadata entries
            if camera_id.startswith('_') and camera_id != '_default_fob':
                continue

            calibration, used_homography = self._build_calibration(camera_id, config)
            self._calibrations[camera_id] = calibration
            if used_homography:
                homography_count += 1

        total = len(self._calibrations)
        if homography_count > 0:
            print(f"[Calibration] Loaded {total} calibrations "
                  f"({homography_count} with homography)")
        else:
            print(f"[Calibration] Loaded {total} camera calibrations")

    def _load_calibrations(self) -> None:
        """Load calibrations from JSON file.

        Uses HomographyCalibration if homography data is present and enabled,
        otherwise falls back to PerspectiveCalibration.
        """
        if not (self._config_path and os.path.exists(self._config_path)):
            print("[Calibration] No calibration file found, using defaults")
            return

        try:
            self._load_calibrations_from_file()
        except Exception:
            logger.exception("[Calibration] Error loading calibrations")

    def get_calibration(self, camera_id: str) -> Union[PerspectiveCalibration, 'HomographyCalibration']:
        """
        Get calibration for a specific camera.

        Returns HomographyCalibration if homography is configured,
        otherwise returns PerspectiveCalibration.

        Falls back to _default_fob if camera not found.

        Args:
            camera_id: Camera identifier

        Returns:
            PerspectiveCalibration or HomographyCalibration for the camera
        """
        if camera_id in self._calibrations:
            return self._calibrations[camera_id]

        # Try _default_fob calibration
        if '_default_fob' in self._calibrations:
            logger.info(f"[Calibration] Using _default_fob for unknown camera: {camera_id}")
            return self._calibrations['_default_fob']

        # Return hardcoded default
        logger.info(f"[Calibration] Using hardcoded default for: {camera_id}")
        return PerspectiveCalibration(camera_id, self.DEFAULT_FOB_CALIBRATION)

    def add_calibration(self, camera_id: str, config: dict) -> None:
        """Add or update calibration for a camera.

        Automatically uses HomographyCalibration if homography data is present.
        """
        if config.get('homography', {}).get('enabled', False):
            try:
                from utils.homography import HomographyCalibration
                self._calibrations[camera_id] = HomographyCalibration(camera_id, config)
                return
            except ImportError:
                pass
        self._calibrations[camera_id] = PerspectiveCalibration(camera_id, config)

    def save_calibrations(self, path: Optional[str] = None) -> None:
        """Save all calibrations to JSON file."""
        path = path or self._config_path
        if path is None:
            raise ValueError("No path specified for saving calibrations")

        data = {
            cam_id: cal.to_dict()
            for cam_id, cal in self._calibrations.items()
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"[Calibration] Saved {len(data)} calibrations to {path}")

    def list_cameras(self) -> list:
        """Get list of calibrated camera IDs."""
        return list(self._calibrations.keys())
