"""
Homography Calibration Module for CrowdVision

Provides accurate pixel-to-real-world coordinate transformation using
a 3x3 homography matrix computed from reference point correspondences.

Compatible with existing PerspectiveCalibration - falls back to
visible_area_m2 if no homography is configured.

Usage:
    # Load from config (automatic detection)
    calibration = CalibrationManager().get_calibration("cam_pf1_fob_kzj")

    # If homography is configured:
    world_x, world_y = calibration.pixel_to_world(pixel_x, pixel_y)
    area_m2 = calibration.real_area_polygon([(x1,y1), (x2,y2), ...])

    # Falls back to visible_area_m2 if no homography
"""

from datetime import UTC
import logging
import cv2
import numpy as np
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReferencePoint:
    """A pixel to real-world coordinate mapping"""
    pixel: Tuple[float, float]  # (x, y) in pixels
    world: Tuple[float, float]  # (x, y) in meters


class HomographyCalibration:
    """
    Homography-based perspective calibration for accurate coordinate transformation.

    Uses a 3x3 homography matrix H where:
        [world_x']     [pixel_x]
        [world_y'] = H [pixel_y]
        [w       ]     [1      ]

        world_x = world_x' / w
        world_y = world_y' / w

    Provides:
    - Pixel (x,y) to real-world (x,y) in meters
    - Real area calculation for any polygon region
    - Real distance/speed with direction awareness
    - Backward compatibility with visible_area_m2 fallback
    """

    def __init__(self, camera_id: str, config: dict):
        """
        Initialize from config dictionary.

        Args:
            camera_id: Camera identifier
            config: Calibration config with optional 'homography' section
        """
        self.camera_id = camera_id

        # Backward compatibility: simple visible_area approach
        self.visible_area_m2 = config.get('visible_area_m2', 150.0)
        self.corridor_width_m = config.get('corridor_width_m', 4.0)
        self.coverage_length_m = config.get('coverage_length_m', 40.0)
        self.lane_count = config.get('lane_count', 1)
        self.camera_type = config.get('camera_type', 'unknown')
        self.notes = config.get('notes', '')

        # For compatibility with PerspectiveCalibration
        self.vanishing_y = config.get('vanishing_point_y', 100)

        # Homography-specific
        self._homography_enabled = False
        self._H: Optional[np.ndarray] = None  # Pixel -> World
        self._H_inv: Optional[np.ndarray] = None  # World -> Pixel
        self._reference_points: List[ReferencePoint] = []
        self._frame_size: Tuple[int, int] = (1280, 720)
        self._reprojection_error: float = 0.0
        self._calibrated_at: Optional[str] = None
        self._calibrated_by: Optional[str] = None

        # Load homography if available
        homography_config = config.get('homography')
        if homography_config and homography_config.get('enabled', False):
            self._load_homography(homography_config)

    def _load_homography(self, hom_config: dict) -> None:
        """Load homography matrix from config"""
        try:
            matrix = hom_config.get('matrix')
            if matrix is None:
                return

            self._H = np.array(matrix, dtype=np.float64)

            if self._H.shape != (3, 3):
                raise ValueError(f"Invalid homography matrix shape: {self._H.shape}")

            # Compute inverse for world -> pixel transformation
            self._H_inv = np.linalg.inv(self._H)

            # Load reference points
            ref_points = hom_config.get('reference_points', [])
            self._reference_points = [
                ReferencePoint(
                    pixel=tuple(p['pixel']),
                    world=tuple(p['world'])
                )
                for p in ref_points
            ]

            self._frame_size = tuple(hom_config.get('frame_size', [1280, 720]))
            self._reprojection_error = hom_config.get('reprojection_error', 0.0)
            self._calibrated_at = hom_config.get('calibrated_at')
            self._calibrated_by = hom_config.get('calibrated_by')
            self._homography_enabled = True

            logger.info(f"[Homography] Loaded calibration for {self.camera_id} "
                        f"(error={self._reprojection_error:.2f}m)")

        except Exception:
            logger.exception(f"[Homography] Failed to load for {self.camera_id}")
            self._homography_enabled = False

    @property
    def has_homography(self) -> bool:
        """Check if homography calibration is available"""
        return self._homography_enabled and self._H is not None

    # =========================================================================
    # Core Transformation Methods
    # =========================================================================

    def pixel_to_world(self, pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """
        Convert pixel coordinates to real-world coordinates (meters).

        Args:
            pixel_x: X coordinate in pixels (0 = left)
            pixel_y: Y coordinate in pixels (0 = top)

        Returns:
            (world_x, world_y) in meters

        Raises:
            ValueError: If no homography is configured
        """
        if not self.has_homography:
            raise ValueError(f"No homography calibration for camera {self.camera_id}")

        # Homogeneous coordinates
        pixel_h = np.array([pixel_x, pixel_y, 1.0], dtype=np.float64)

        # Transform
        world_h = self._H @ pixel_h

        # Normalize (perspective division)
        if abs(world_h[2]) < 1e-10:
            return (float('inf'), float('inf'))

        world_x = world_h[0] / world_h[2]
        world_y = world_h[1] / world_h[2]

        return (float(world_x), float(world_y))

    def world_to_pixel(self, world_x: float, world_y: float) -> Tuple[float, float]:
        """
        Convert real-world coordinates (meters) to pixel coordinates.

        Args:
            world_x: X coordinate in meters
            world_y: Y coordinate in meters

        Returns:
            (pixel_x, pixel_y) in pixels
        """
        if not self.has_homography:
            raise ValueError(f"No homography calibration for camera {self.camera_id}")

        world_h = np.array([world_x, world_y, 1.0], dtype=np.float64)
        pixel_h = self._H_inv @ world_h

        if abs(pixel_h[2]) < 1e-10:
            return (float('inf'), float('inf'))

        pixel_x = pixel_h[0] / pixel_h[2]
        pixel_y = pixel_h[1] / pixel_h[2]

        return (float(pixel_x), float(pixel_y))

    def pixel_to_world_batch(self, pixels: np.ndarray) -> np.ndarray:
        """
        Convert multiple pixel coordinates to world coordinates.

        Args:
            pixels: Nx2 array of (x, y) pixel coordinates

        Returns:
            Nx2 array of (x, y) world coordinates in meters
        """
        if not self.has_homography:
            raise ValueError(f"No homography calibration for camera {self.camera_id}")

        if pixels.shape[0] == 0:
            return np.empty((0, 2), dtype=np.float64)

        # Add homogeneous coordinate
        n = pixels.shape[0]
        pixels_h = np.hstack([pixels, np.ones((n, 1))])  # Nx3

        # Transform all at once: (3x3) @ (3xN) = (3xN)
        world_h = (self._H @ pixels_h.T).T  # Nx3

        # Normalize
        w = world_h[:, 2:3]
        w = np.where(np.abs(w) < 1e-10, 1e-10, w)
        world = world_h[:, :2] / w

        return world

    # =========================================================================
    # Area Calculation
    # =========================================================================

    def real_area_polygon(self, pixel_polygon: List[Tuple[float, float]]) -> float:
        """
        Calculate real-world area of a polygon defined in pixel coordinates.

        Uses the Shoelace formula after transforming all vertices to world coordinates.

        Args:
            pixel_polygon: List of (x, y) pixel coordinates defining polygon vertices

        Returns:
            Area in square meters
        """
        if not self.has_homography:
            return self._fallback_area_estimate(pixel_polygon)

        if len(pixel_polygon) < 3:
            return 0.0

        # Transform all vertices to world coordinates
        pixels = np.array(pixel_polygon, dtype=np.float64)
        world_vertices = self.pixel_to_world_batch(pixels)

        # Shoelace formula for polygon area
        n = len(world_vertices)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += world_vertices[i, 0] * world_vertices[j, 1]
            area -= world_vertices[j, 0] * world_vertices[i, 1]

        return abs(area) / 2.0

    def real_area_rect(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """
        Calculate real-world area of a rectangular region in pixels.

        Args:
            x1, y1: Top-left corner in pixels
            x2, y2: Bottom-right corner in pixels

        Returns:
            Area in square meters
        """
        polygon = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return self.real_area_polygon(polygon)

    def _fallback_area_estimate(self, pixel_polygon: List[Tuple[float, float]]) -> float:
        """Estimate area using visible_area_m2 when homography not available."""
        n = len(pixel_polygon)
        if n < 3:
            return 0.0

        # Calculate pixel area using Shoelace
        pixel_area = 0.0
        for i in range(n):
            j = (i + 1) % n
            pixel_area += pixel_polygon[i][0] * pixel_polygon[j][1]
            pixel_area -= pixel_polygon[j][0] * pixel_polygon[i][1]
        pixel_area = abs(pixel_area) / 2.0

        # Scale by configured visible area
        frame_pixel_area = self._frame_size[0] * self._frame_size[1]
        scale = self.visible_area_m2 / frame_pixel_area if frame_pixel_area > 0 else 0.0

        return pixel_area * scale

    # =========================================================================
    # Distance and Speed Calculation
    # =========================================================================

    def real_distance(
        self,
        pixel_start: Tuple[float, float],
        pixel_end: Tuple[float, float]
    ) -> float:
        """
        Calculate real-world distance between two points.

        Args:
            pixel_start: Starting point (x, y) in pixels
            pixel_end: Ending point (x, y) in pixels

        Returns:
            Distance in meters
        """
        if not self.has_homography:
            return self._fallback_distance(pixel_start, pixel_end)

        world_start = self.pixel_to_world(*pixel_start)
        world_end = self.pixel_to_world(*pixel_end)

        dx = world_end[0] - world_start[0]
        dy = world_end[1] - world_start[1]

        return math.sqrt(dx * dx + dy * dy)

    def real_displacement(
        self,
        pixel_start: Tuple[float, float],
        pixel_end: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Calculate real-world displacement vector between two points.

        Args:
            pixel_start: Starting point (x, y) in pixels
            pixel_end: Ending point (x, y) in pixels

        Returns:
            (dx, dy) displacement in meters
        """
        if not self.has_homography:
            scale = math.sqrt(self.visible_area_m2 / (self._frame_size[0] * self._frame_size[1]))
            dx = (pixel_end[0] - pixel_start[0]) * scale
            dy = (pixel_end[1] - pixel_start[1]) * scale
            return (dx, dy)

        world_start = self.pixel_to_world(*pixel_start)
        world_end = self.pixel_to_world(*pixel_end)

        return (
            world_end[0] - world_start[0],
            world_end[1] - world_start[1]
        )

    def real_speed(
        self,
        pixel_start: Tuple[float, float],
        pixel_end: Tuple[float, float],
        dt: float
    ) -> float:
        """
        Calculate real-world speed from pixel displacement over time.

        Args:
            pixel_start: Starting position in pixels
            pixel_end: Ending position in pixels
            dt: Time interval in seconds

        Returns:
            Speed in meters per second
        """
        if dt <= 0:
            return 0.0

        distance = self.real_distance(pixel_start, pixel_end)
        return distance / dt

    def real_velocity(
        self,
        pixel_start: Tuple[float, float],
        pixel_end: Tuple[float, float],
        dt: float
    ) -> Tuple[float, float]:
        """
        Calculate real-world velocity vector (with direction).

        Args:
            pixel_start: Starting position in pixels
            pixel_end: Ending position in pixels
            dt: Time interval in seconds

        Returns:
            (vx, vy) velocity in meters per second
        """
        if dt <= 0:
            return (0.0, 0.0)

        dx, dy = self.real_displacement(pixel_start, pixel_end)
        return (dx / dt, dy / dt)

    def _fallback_distance(
        self,
        pixel_start: Tuple[float, float],
        pixel_end: Tuple[float, float]
    ) -> float:
        """Fallback distance calculation using average scale"""
        dx = pixel_end[0] - pixel_start[0]
        dy = pixel_end[1] - pixel_start[1]
        pixel_dist = math.sqrt(dx * dx + dy * dy)

        # Average scale factor
        frame_diag = math.sqrt(self._frame_size[0]**2 + self._frame_size[1]**2)
        real_diag = math.sqrt(self.visible_area_m2 * 16/9)
        scale = real_diag / frame_diag if frame_diag > 0 else 0.01

        return pixel_dist * scale

    # =========================================================================
    # Compatibility Methods (matching PerspectiveCalibration interface)
    # =========================================================================

    def scale_at_y(self, y: int, frame_height: int, frame_width: int = None) -> float:
        """
        Get meters-per-pixel scale at given Y coordinate.

        For homography: calculates local Jacobian to get scale.
        For fallback: uses linear interpolation like PerspectiveCalibration.
        """
        if not self.has_homography:
            return self._fallback_scale_at_y(y, frame_height, frame_width)

        if frame_width is None:
            frame_width = self._frame_size[0]

        x_center = frame_width / 2
        delta = 10  # pixels

        # Horizontal scale at this Y
        world_left = self.pixel_to_world(x_center - delta, y)
        world_right = self.pixel_to_world(x_center + delta, y)
        h_scale = abs(world_right[0] - world_left[0]) / (2 * delta)

        # Vertical scale at this Y
        y_up = max(0, y - delta)
        y_down = min(frame_height - 1, y + delta)
        world_up = self.pixel_to_world(x_center, y_up)
        world_down = self.pixel_to_world(x_center, y_down)
        v_scale = abs(world_down[1] - world_up[1]) / (y_down - y_up) if y_down > y_up else h_scale

        # Return geometric mean
        return math.sqrt(h_scale * v_scale)

    def _fallback_scale_at_y(self, y: int, frame_height: int, frame_width: int = None) -> float:
        """Fallback scale calculation matching PerspectiveCalibration"""
        if frame_width is None:
            frame_width = int(frame_height * 16 / 9)

        pixel_area = frame_width * frame_height
        avg_scale = math.sqrt(self.visible_area_m2 / pixel_area)

        # Linear interpolation near=0.5x, far=2.0x
        if frame_height <= self.vanishing_y:
            return avg_scale * 0.5

        t = (frame_height - y) / (frame_height - self.vanishing_y)
        t = max(0.0, min(1.0, t))

        near_scale = avg_scale * 0.5
        far_scale = avg_scale * 2.0

        return near_scale + t * (far_scale - near_scale)

    def real_area_at_y(self, y: int, pixel_area: float, frame_height: int) -> float:
        """
        Get real area for a region at given Y coordinate.

        For homography: properly transforms the area.
        For fallback: returns visible_area_m2.
        """
        if not self.has_homography:
            return self.visible_area_m2

        # Create a small rectangle at this Y and compute its real area
        frame_width = self._frame_size[0]
        half_width = math.sqrt(pixel_area) / 2

        x_center = frame_width / 2

        polygon = [
            (x_center - half_width, y - half_width),
            (x_center + half_width, y - half_width),
            (x_center + half_width, y + half_width),
            (x_center - half_width, y + half_width)
        ]

        return self.real_area_polygon(polygon)

    def get_visible_area(self) -> float:
        """Get configured visible area (for backward compatibility)"""
        return self.visible_area_m2

    def get_lane_boundaries(self, frame_height: int) -> list:
        """
        Get Y-coordinate boundaries for each lane.
        Matches PerspectiveCalibration interface.
        """
        effective_height = frame_height - self.vanishing_y
        lane_height = effective_height // max(1, self.lane_count)

        lanes = []
        for i in range(self.lane_count):
            y_end = frame_height - (i * lane_height)
            y_start = frame_height - ((i + 1) * lane_height)
            y_start = max(self.vanishing_y, y_start)
            y_end = min(frame_height, y_end)

            if y_start < y_end:
                lanes.append((y_start, y_end))

        return lanes if lanes else [(0, frame_height)]

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        result = {
            'camera_id': self.camera_id,
            'visible_area_m2': self.visible_area_m2,
            'corridor_width_m': self.corridor_width_m,
            'coverage_length_m': self.coverage_length_m,
            'lane_count': self.lane_count,
            'camera_type': self.camera_type,
            'notes': self.notes
        }

        if self.has_homography:
            result['homography'] = {
                'enabled': True,
                'matrix': self._H.tolist(),
                'reference_points': [
                    {'pixel': list(p.pixel), 'world': list(p.world)}
                    for p in self._reference_points
                ],
                'frame_size': list(self._frame_size),
                'reprojection_error': self._reprojection_error,
                'calibrated_at': self._calibrated_at,
                'calibrated_by': self._calibrated_by
            }

        return result

    def __repr__(self) -> str:
        hom_str = f", homography=True (error={self._reprojection_error:.2f}m)" if self.has_homography else ""
        return (f"HomographyCalibration(camera_id='{self.camera_id}', "
                f"visible_area_m2={self.visible_area_m2}{hom_str})")


# =============================================================================
# Static Functions for Homography Computation
# =============================================================================

def compute_homography(
    reference_points: List[ReferencePoint],
    method: int = cv2.RANSAC
) -> Tuple[np.ndarray, float, np.ndarray]:
    """
    Compute homography matrix from reference point correspondences.

    Uses cv2.findHomography with RANSAC for robustness to outliers.

    Args:
        reference_points: List of at least 4 ReferencePoint objects
        method: OpenCV homography method (RANSAC recommended)

    Returns:
        (H, reprojection_error, mask)
        - H: 3x3 homography matrix (pixel -> world)
        - reprojection_error: RMS error in meters
        - mask: Inlier mask from RANSAC

    Raises:
        ValueError: If fewer than 4 points provided or computation fails
    """
    if len(reference_points) < 4:
        raise ValueError("At least 4 reference points required for homography")

    # Extract pixel and world coordinates
    pixels = np.array([p.pixel for p in reference_points], dtype=np.float64)
    worlds = np.array([p.world for p in reference_points], dtype=np.float64)

    # Compute homography: pixel -> world
    H, mask = cv2.findHomography(pixels, worlds, method, ransacReprojThreshold=5.0)

    if H is None:
        raise ValueError("Homography computation failed - check point configuration")

    # Compute reprojection error
    reprojection_error = _compute_reprojection_error(pixels, worlds, H, mask)

    return H, reprojection_error, mask


def _compute_reprojection_error(
    pixels: np.ndarray,
    worlds: np.ndarray,
    H: np.ndarray,
    mask: np.ndarray
) -> float:
    """Compute RMS reprojection error for homography in meters."""
    n = pixels.shape[0]

    # Transform pixels to world
    pixels_h = np.hstack([pixels, np.ones((n, 1))])
    worlds_h = (H @ pixels_h.T).T

    # Normalize
    w = worlds_h[:, 2:3]
    w = np.where(np.abs(w) < 1e-10, 1e-10, w)
    projected = worlds_h[:, :2] / w

    # Compute error for inliers
    if mask is not None:
        inlier_mask = mask.flatten() == 1
        if np.sum(inlier_mask) > 0:
            errors = np.sqrt(np.sum((projected[inlier_mask] - worlds[inlier_mask]) ** 2, axis=1))
        else:
            errors = np.sqrt(np.sum((projected - worlds) ** 2, axis=1))
    else:
        errors = np.sqrt(np.sum((projected - worlds) ** 2, axis=1))

    return float(np.sqrt(np.mean(errors ** 2)))


def validate_homography(
    H: np.ndarray,
    frame_size: Tuple[int, int],
    expected_area_range: Tuple[float, float] = (10.0, 1000.0)
) -> Tuple[bool, str]:
    """
    Validate a homography matrix for reasonableness.

    Checks:
    1. Frame corners transform to reasonable world coordinates
    2. Total area is within expected range
    3. No extreme distortion or flipping

    Args:
        H: 3x3 homography matrix
        frame_size: (width, height) of frame
        expected_area_range: (min, max) expected area in m²

    Returns:
        (is_valid, message)
    """
    w, h = frame_size

    # Define frame corners
    corners = np.array([
        [0, 0],      # top-left
        [w, 0],      # top-right
        [w, h],      # bottom-right
        [0, h]       # bottom-left
    ], dtype=np.float64)

    # Transform corners
    corners_h = np.hstack([corners, np.ones((4, 1))])
    worlds_h = (H @ corners_h.T).T

    # Check for points at infinity
    if np.any(np.abs(worlds_h[:, 2]) < 1e-10):
        return False, "Homography produces points at infinity"

    worlds = worlds_h[:, :2] / worlds_h[:, 2:3]

    # Check for reasonable world coordinates
    if np.any(np.abs(worlds) > 10000):
        return False, f"World coordinates unreasonably large: max={np.max(np.abs(worlds)):.1f}m"

    # Compute area using Shoelace
    area = 0.0
    for i in range(4):
        j = (i + 1) % 4
        area += worlds[i, 0] * worlds[j, 1]
        area -= worlds[j, 0] * worlds[i, 1]
    area = abs(area) / 2.0

    if area < expected_area_range[0]:
        return False, f"Computed area too small: {area:.1f}m² (expected >{expected_area_range[0]})"

    if area > expected_area_range[1]:
        return False, f"Computed area too large: {area:.1f}m² (expected <{expected_area_range[1]})"

    # Check for flipping (cross product should maintain sign)
    v1 = worlds[1] - worlds[0]  # top edge
    v2 = worlds[3] - worlds[0]  # left edge
    cross = v1[0] * v2[1] - v1[1] * v2[0]

    if cross < 0:
        return False, "Homography appears to flip the coordinate system"

    return True, f"Valid homography (computed area: {area:.1f}m²)"


def create_homography_config(
    reference_points: List[ReferencePoint],
    frame_size: Tuple[int, int],
    calibrated_by: str = "calibration_tool"
) -> dict:
    """
    Compute homography and create a config dictionary ready for storage.

    Args:
        reference_points: At least 4 reference points
        frame_size: (width, height) of the frame used for calibration
        calibrated_by: Identifier of who/what performed calibration

    Returns:
        Dictionary with homography config suitable for camera_calibrations.json

    Raises:
        ValueError: If computation fails or validation fails
    """
    from datetime import datetime

    H, error, mask = compute_homography(reference_points)

    is_valid, msg = validate_homography(H, frame_size)
    if not is_valid:
        raise ValueError(f"Homography validation failed: {msg}")

    return {
        'enabled': True,
        'matrix': H.tolist(),
        'reference_points': [
            {'pixel': list(p.pixel), 'world': list(p.world)}
            for p in reference_points
        ],
        'frame_size': list(frame_size),
        'reprojection_error': error,
        'calibrated_at': datetime.now(UTC).isoformat() + 'Z',
        'calibrated_by': calibrated_by
    }
