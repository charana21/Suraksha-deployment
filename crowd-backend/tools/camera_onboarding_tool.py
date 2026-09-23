"""
Camera ROI onboarding tool.

For cameras already seeded via seed_platform_zones.py, this tool captures
a frame from the camera's RTSP stream and opens an interactive ROI editor.
No metadata prompts — goes straight to ROI drawing.

Usage:
    # List all cameras and their ROI status
    python tools/camera_onboarding_tool.py --list

    # Add/edit ROI for a seeded camera (skips metadata prompts)
    python tools/camera_onboarding_tool.py --camera-id cam_pf1_fob_kzj

    # Override area_m2 (optional in pixel density mode)
    python tools/camera_onboarding_tool.py --camera-id cam_pf1_fob_kzj --area-m2 120.0

    # Full mode for new camera (prompts for all metadata)
    python tools/camera_onboarding_tool.py --camera-id cam_new --name "New Cam" --rtsp-url rtsp://...
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np
import logging
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import get_settings
from db.mongodb import connect_to_mongo, close_mongo_connection
from services.camera_service import CameraService

class ROIEditor:
    """Interactive ROI editor with stable coordinate mapping and easy editing."""

    def __init__(
        self,
        camera_id: str,
        frame: np.ndarray,
        area_m2: float,
        initial_points: Optional[List[List[float]]] = None,
    ):
        self.camera_id = camera_id
        self.frame = frame.copy()
        self.frame_h, self.frame_w = frame.shape[:2]
        self.area_m2 = area_m2

        # Keep explicit view scaling so mouse coordinates always map correctly.
        max_view_w, max_view_h = 1400, 900
        self.view_scale = min(max_view_w / self.frame_w, max_view_h / self.frame_h, 1.0)
        self.view_w = max(1, int(round(self.frame_w * self.view_scale)))
        self.view_h = max(1, int(round(self.frame_h * self.view_scale)))

        interpolation = cv2.INTER_AREA if self.view_scale < 1.0 else cv2.INTER_LINEAR
        self.base_view = cv2.resize(self.frame, (self.view_w, self.view_h), interpolation=interpolation)
        self.display_frame = self.base_view.copy()

        self.points: List[Tuple[int, int]] = []
        if initial_points:
            self.points = self._sanitize_points(initial_points)
        self.polygon_closed = len(self.points) >= 3

        self.dragging_index: Optional[int] = None
        self.mouse_img_point: Optional[Tuple[int, int]] = None

        self.snap_radius_px = 14
        self.select_radius_px = 12
        self.window_name = f"Onboarding ROI: {camera_id}"

    def _sanitize_points(self, points: List[List[float]]) -> List[Tuple[int, int]]:
        cleaned: List[Tuple[int, int]] = []
        for pt in points:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            try:
                x = int(round(float(pt[0])))
                y = int(round(float(pt[1])))
            except (TypeError, ValueError):
                continue
            x = max(0, min(self.frame_w - 1, x))
            y = max(0, min(self.frame_h - 1, y))
            xy = (x, y)
            if not cleaned or cleaned[-1] != xy:
                cleaned.append(xy)

        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
            cleaned.pop()
        return cleaned

    def _img_to_view(self, point: Tuple[int, int]) -> Tuple[int, int]:
        return (
            int(round(point[0] * self.view_scale)),
            int(round(point[1] * self.view_scale)),
        )

    def _view_to_img(self, x: int, y: int) -> Tuple[int, int]:
        img_x = int(round(x / self.view_scale))
        img_y = int(round(y / self.view_scale))
        img_x = max(0, min(self.frame_w - 1, img_x))
        img_y = max(0, min(self.frame_h - 1, img_y))
        return (img_x, img_y)

    def _find_nearest_point(self, view_x: int, view_y: int, threshold_px: int) -> Optional[int]:
        threshold_sq = threshold_px * threshold_px
        best_idx: Optional[int] = None
        best_dist_sq = threshold_sq + 1

        for idx, pt in enumerate(self.points):
            px, py = self._img_to_view(pt)
            dist_sq = (px - view_x) ** 2 + (py - view_y) ** 2
            if dist_sq <= threshold_sq and dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_idx = idx
        return best_idx

    def _is_near_first_point(self, view_x: int, view_y: int) -> bool:
        if len(self.points) < 3:
            return False
        first_x, first_y = self._img_to_view(self.points[0])
        dist_sq = (first_x - view_x) ** 2 + (first_y - view_y) ** 2
        return dist_sq <= self.snap_radius_px * self.snap_radius_px

    def _handle_left_button_down(self, x, y, img_pt):
        nearest_idx = self._find_nearest_point(x, y, self.select_radius_px)

        # Drag existing points both in open/closed mode.
        if nearest_idx is not None:
            self.dragging_index = nearest_idx
            return

        if self.polygon_closed:
            return

        # Quick close by clicking near the first point.
        if self._is_near_first_point(x, y):
            self.polygon_closed = True
            self._update_display(self.mouse_img_point)
            print(f"Polygon closed with {len(self.points)} points.")
            return

        self.points.append(img_pt)
        self._update_display(self.mouse_img_point)

    def _handle_mouse_move(self, img_pt):
        if self.dragging_index is not None:
            self.points[self.dragging_index] = img_pt
        self._update_display(self.mouse_img_point)

    def _handle_left_button_up(self, img_pt):
        if self.dragging_index is not None:
            self.points[self.dragging_index] = img_pt
            self.dragging_index = None
        self._update_display(self.mouse_img_point)

    def _handle_right_button_down(self, x, y):
        if not self.points:
            return

        nearest_idx = self._find_nearest_point(x, y, self.select_radius_px)
        remove_idx = nearest_idx if nearest_idx is not None else len(self.points) - 1
        self.points.pop(remove_idx)

        if len(self.points) < 3:
            self.polygon_closed = False
        self._update_display(self.mouse_img_point)

    def mouse_callback(self, event, x, y, flags, param):
        img_pt = self._view_to_img(x, y)
        self.mouse_img_point = img_pt

        if event == cv2.EVENT_LBUTTONDOWN:
            self._handle_left_button_down(x, y, img_pt)
        elif event == cv2.EVENT_MOUSEMOVE:
            self._handle_mouse_move(img_pt)
        elif event == cv2.EVENT_LBUTTONUP:
            self._handle_left_button_up(img_pt)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._handle_right_button_down(x, y)

    def _draw_info(self):
        overlay = self.display_frame.copy()
        panel_bottom = min(self.view_h - 8, 200)
        panel_right = min(self.view_w - 8, 980)
        cv2.rectangle(overlay, (8, 8), (panel_right, panel_bottom), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, self.display_frame, 0.3, 0, self.display_frame)

        lines = [
            f"Camera: {self.camera_id} | area_m2: {self.area_m2}",
            f"Vertices: {len(self.points)} | Closed: {self.polygon_closed}",
            "Left: add point / drag point | Right: remove nearest point",
            "Click near point #1 or press C to close | E to reopen",
            "S: save ROI (auto-close) | R: reset | Q/ESC: cancel",
        ]
        y = 34
        for line in lines:
            cv2.putText(
                self.display_frame,
                line,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y += 30

    def _draw_polygon_lines(self):
        for i in range(len(self.points) - 1):
            p1 = self._img_to_view(self.points[i])
            p2 = self._img_to_view(self.points[i + 1])
            cv2.line(self.display_frame, p1, p2, (0, 255, 0), 2, cv2.LINE_AA)

        if self.polygon_closed and len(self.points) >= 3:
            first = self._img_to_view(self.points[0])
            last = self._img_to_view(self.points[-1])
            cv2.line(self.display_frame, last, first, (0, 255, 0), 2, cv2.LINE_AA)

            pts = np.array([self._img_to_view(pt) for pt in self.points], dtype=np.int32)
            overlay = self.display_frame.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            cv2.addWeighted(overlay, 0.2, self.display_frame, 0.8, 0, self.display_frame)

    def _draw_points(self):
        for idx, pt in enumerate(self.points):
            vpt = self._img_to_view(pt)
            point_color = (0, 165, 255) if idx == 0 else (0, 255, 0)
            cv2.circle(self.display_frame, vpt, 6, point_color, -1, cv2.LINE_AA)
            cv2.circle(self.display_frame, vpt, 8, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(
                self.display_frame,
                str(idx + 1),
                (vpt[0] + 9, vpt[1] - 9),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    def _draw_preview(self, preview_img_point: Tuple[int, int]):
        px, py = self._img_to_view(preview_img_point)

        # Crosshair.
        cv2.line(self.display_frame, (px, 0), (px, self.view_h), (0, 255, 255), 1, cv2.LINE_AA)
        cv2.line(self.display_frame, (0, py), (self.view_w, py), (0, 255, 255), 1, cv2.LINE_AA)

        # Preview edge while drawing.
        if self.points and not self.polygon_closed:
            start = self._img_to_view(self.points[-1])
            if self._is_near_first_point(px, py):
                end = self._img_to_view(self.points[0])
                color = (0, 165, 255)
            else:
                end = (px, py)
                color = (0, 255, 0)
            cv2.line(self.display_frame, start, end, color, 2, cv2.LINE_AA)

        hover_idx = self._find_nearest_point(px, py, self.select_radius_px)
        if hover_idx is not None:
            hpt = self._img_to_view(self.points[hover_idx])
            cv2.circle(self.display_frame, hpt, 12, (0, 255, 255), 1, cv2.LINE_AA)

    def _update_display(self, preview_img_point: Optional[Tuple[int, int]] = None):
        self.display_frame = self.base_view.copy()

        if self.points:
            self._draw_polygon_lines()
            self._draw_points()

        if preview_img_point is not None:
            self._draw_preview(preview_img_point)

        self._draw_info()
        cv2.imshow(self.window_name, self.display_frame)

    def _handle_reset_key(self):
        self.points = []
        self.polygon_closed = False
        self.dragging_index = None
        self._update_display(self.mouse_img_point)

    def _handle_reopen_key(self):
        if self.polygon_closed:
            self.polygon_closed = False
            print("Polygon reopened. Add more points, then close again.")
            self._update_display(self.mouse_img_point)

    def _handle_close_key(self):
        if len(self.points) < 3:
            print("Need at least 3 points to close polygon.")
        else:
            self.polygon_closed = True
            self._update_display(self.mouse_img_point)
            print(f"Polygon closed with {len(self.points)} points.")

    def _handle_save_key(self) -> Optional[List[List[float]]]:
        if len(self.points) < 3:
            print("Cannot save: need at least 3 points.")
            return None
        if not self.polygon_closed:
            self.polygon_closed = True
            print("Polygon auto-closed on save.")
            self._update_display(self.mouse_img_point)
        roi_points = [[float(x), float(y)] for x, y in self.points]
        print(f"ROI saved with {len(roi_points)} points.")
        return roi_points

    def _handle_key(self, key: int) -> Tuple[bool, Optional[List[List[float]]]]:
        """Handle a key press. Returns (should_exit, roi_points_or_None)."""
        if key in (ord("q"), ord("Q"), 27):
            print("ROI capture cancelled.")
            return True, None

        if key in (ord("r"), ord("R")):
            self._handle_reset_key()
        elif key in (ord("e"), ord("E")):
            self._handle_reopen_key()
        elif key in (ord("c"), ord("C")):
            self._handle_close_key()
        elif key in (ord("s"), ord("S")):
            roi_points = self._handle_save_key()
            if roi_points is not None:
                return True, roi_points

        return False, None

    def run(self) -> Optional[List[List[float]]]:
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.view_w, self.view_h)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        self._update_display()

        logger.info("\nROI editor opened.")
        if self.points:
            logger.info(f"Loaded existing ROI with {len(self.points)} points. Drag points and press S to save.")
        else:
            logger.info("Draw polygon and press S to save.")

        try:
            while True:
                key = cv2.waitKey(50) & 0xFF
                should_exit, roi_points = self._handle_key(key)
                if should_exit:
                    return roi_points
        finally:
            cv2.destroyAllWindows()


def prepare_roi_points_for_current_frame(
    stored_points: Optional[List[List[float]]],
    stored_frame_width: Optional[int],
    stored_frame_height: Optional[int],
    current_frame_width: int,
    current_frame_height: int,
) -> List[List[float]]:
    """Scale stored ROI points to current frame size for edit mode."""
    if not stored_points:
        return []

    scale_x = 1.0
    scale_y = 1.0
    if (
        stored_frame_width
        and stored_frame_height
        and stored_frame_width > 0
        and stored_frame_height > 0
    ):
        scale_x = float(current_frame_width) / float(stored_frame_width)
        scale_y = float(current_frame_height) / float(stored_frame_height)

    prepared: List[List[float]] = []
    for pt in stored_points:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        try:
            x = float(pt[0]) * scale_x
            y = float(pt[1]) * scale_y
        except (TypeError, ValueError):
            continue

        x = max(0.0, min(float(current_frame_width - 1), x))
        y = max(0.0, min(float(current_frame_height - 1), y))
        candidate = [x, y]
        if not prepared or prepared[-1] != candidate:
            prepared.append(candidate)

    if len(prepared) >= 2 and prepared[0] == prepared[-1]:
        prepared.pop()

    return prepared


def capture_reference_frame(
    rtsp_url: str,
    timeout_seconds: int = 10,
    warmup_frames: int = 15,
) -> Optional[np.ndarray]:
    """Capture one stable frame directly from RTSP."""
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp|analyzeduration;2000000|probesize;1000000|fflags;+discardcorrupt|flags;low_delay"
    )

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

    start = time.time()
    good_frames = 0
    captured = None

    while time.time() - start < timeout_seconds:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        good_frames += 1
        if good_frames >= max(1, warmup_frames):
            captured = frame
            break

    cap.release()
    return captured


async def upsert_camera_metadata(
    camera_id: str,
    name: str,
    rtsp_url: str,
    location: Optional[str],
    fob_type: Optional[str],
    zone_id: Optional[str],
) -> Tuple[str, dict]:
    """Create or update camera metadata and force active state."""
    existing = await CameraService.get_camera(camera_id)
    if not existing:
        created = await CameraService.register_camera(
            camera_id=camera_id,
            name=name,
            rtsp_url=rtsp_url,
            location=location or "Unknown",
            fob_type=fob_type,
            zone_id=zone_id,
            is_active=True,
        )
        await CameraService.update_camera(camera_id, {"status": "active", "is_active": True})
        latest = await CameraService.get_camera(camera_id)
        return "created", latest or created

    updates = {
        "name": name,
        "rtsp_url": rtsp_url,
        "status": "active",
        "is_active": True,
    }
    if location is not None:
        updates["location"] = location
    if fob_type is not None:
        updates["fob_type"] = fob_type
    if zone_id is not None:
        updates["zone_id"] = zone_id

    await CameraService.update_camera(camera_id, updates)
    latest = await CameraService.get_camera(camera_id)
    return "updated", latest or existing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Camera onboarding: add/edit ROI for cameras seeded via seed_platform_zones.py."
    )
    parser.add_argument("--camera-id", required=False, help="Unique camera identifier")
    parser.add_argument("--list", action="store_true", help="List all cameras and their ROI/calibration status")
    parser.add_argument("--area-m2", default=None, type=float, help="Visible area in square meters (optional in pixel density mode)")

    # Override metadata (usually not needed — cameras are pre-seeded)
    parser.add_argument("--name", default=None, help="Override camera display name")
    parser.add_argument("--rtsp-url", default=None, help="Override RTSP stream URL")
    parser.add_argument("--location", default=None, help="Override physical location")
    parser.add_argument("--fob-type", default=None, help="FOB type (example: HYD, KZJ)")
    parser.add_argument("--zone-id", default=None, help="Zone mapping id")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Disable interactive prompts (all required values must be supplied via args).",
    )

    parser.add_argument(
        "--capture-timeout",
        type=int,
        default=10,
        help="RTSP frame capture timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=15,
        help="Number of good frames to skip before capture (default: 15)",
    )
    parser.add_argument(
        "--save-frame-path",
        default=None,
        help="Optional path to save captured reference frame",
    )
    return parser


async def prompt_text(label: str, current: Optional[str], required: bool = False) -> Optional[str]:
    """Prompt for text input. Empty input keeps current value when available."""
    while True:
        suffix = f" [{current}]" if current not in (None, "") else ""
        value = (await asyncio.to_thread(input, f"{label}{suffix}: ")).strip()

        if value == "":
            if current is not None:
                return current
            if required:
                logger.info(f"{label} is required.")
                continue
            return None

        if value.lower() in ("none", "null", "-"):
            return None

        return value


async def prompt_float(label: str, current: Optional[float], required: bool = False) -> Optional[float]:
    """Prompt for float input. Empty input keeps current value when available."""
    while True:
        suffix = f" [{current}]" if current is not None else ""
        value = (await asyncio.to_thread(input, f"{label}{suffix}: ")).strip()

        if value == "":
            if current is not None:
                return float(current)
            if required:
                logger.info(f"{label} is required.")
                continue
            return None

        try:
            parsed = float(value)
        except ValueError:
            logger.info(f"{label} must be a numeric value.")
            continue

        return parsed


async def list_cameras() -> int:
    """List all cameras in MongoDB with their ROI/calibration status."""
    settings = get_settings()
    await connect_to_mongo(settings)

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(settings.mongodb_uri)
        db = client[settings.mongodb_database]

        cameras = await db.cameras.find(
            {},
            {"camera_id": 1, "name": 1, "zone_id": 1, "rtsp_url": 1, "calibration": 1, "is_active": 1}
        ).sort("camera_id", 1).to_list(length=500)

        if not cameras:
            print("No cameras found in MongoDB.")
            return 1

        logger.info(f"\nAvailable cameras ({len(cameras)} total):\n")
        logger.info(f"  {'CAMERA ID':<30} {'ZONE':<18} {'ROI':<6} {'AREA_M2':<10} {'RTSP URL'}")
        logger.info(f"  {'-'*30} {'-'*18} {'-'*6} {'-'*10} {'-'*40}")

        for cam in cameras:
            cam_id = cam.get("camera_id", "?")
            zone = cam.get("zone_id", "-") or "-"
            calibration = cam.get("calibration") or {}
            roi = calibration.get("roi") or {}
            has_roi = "Y" if roi.get("points") else "N"
            area = calibration.get("area_m2")
            area_str = f"{area:.0f}" if area else "-"
            rtsp = cam.get("rtsp_url", "-") or "-"
            logger.info(f"  {cam_id:<30} {zone:<18} {has_roi:<6} {area_str:<10} {rtsp}")

        print()
        return 0
    finally:
        await close_mongo_connection()


async def _resolve_camera_id(args: argparse.Namespace) -> Tuple[Optional[str], int]:
    """Returns (camera_id, error_code). error_code is 0 on success."""
    camera_id = (args.camera_id or "").strip()
    if camera_id:
        return camera_id, 0

    if args.no_prompt:
        print("Error: --camera-id is required with --no-prompt.")
        return None, 2

    camera_id = (await asyncio.to_thread(input, "Camera ID: ")).strip()
    if not camera_id:
        print("Error: camera_id is required.")
        return None, 2
    return camera_id, 0


async def _resolve_roi_only_metadata(
    camera_id: str, existing: dict, existing_area: Optional[float], args: argparse.Namespace, settings
) -> Tuple[Optional[dict], int]:
    """ROI-only mode: camera already seeded, skip metadata prompts."""
    print(f"[Onboarding] ROI mode for existing camera: {camera_id}")
    rtsp_url = existing.get("rtsp_url")
    if not rtsp_url:
        print("Error: camera has no RTSP URL. Use --rtsp-url to provide one.")
        return None, 2

    if args.area_m2 is not None:
        area_m2 = args.area_m2
    elif existing_area is not None:
        area_m2 = float(existing_area)
    elif settings.density_mode == "pixel":
        area_m2 = 150.0  # fallback, not critical in pixel mode
        print(f"[Onboarding] Using default area_m2={area_m2} (pixel density mode)")
    elif not args.no_prompt:
        area_m2 = await prompt_float("Visible area (m2)", None, required=True)
    else:
        print("Error: area_m2 is required in area density mode. Use --area-m2.")
        return None, 2

    return {
        "name": existing.get("name"),
        "rtsp_url": rtsp_url,
        "location": existing.get("location"),
        "fob_type": existing.get("fob_type"),
        "zone_id": existing.get("zone_id"),
        "area_m2": area_m2,
    }, 0


async def _resolve_field(args_value, existing: Optional[dict], key: str, label: str, default=None, required: bool = False, no_prompt: bool = False):
    if args_value is not None:
        return args_value
    if no_prompt:
        return (existing.get(key) if existing else default)
    return await prompt_text(label, (existing.get(key) if existing else default), required=required)


async def _resolve_full_area_m2(existing_area: Optional[float], args: argparse.Namespace, settings) -> Optional[float]:
    if args.area_m2 is not None:
        return args.area_m2
    if existing_area is not None:
        return float(existing_area)
    if settings.density_mode == "pixel":
        if not args.no_prompt:
            area_m2 = await prompt_float("Visible area (m2, optional in pixel mode)", existing_area, required=False)
            return area_m2 if area_m2 is not None else 150.0
        return 150.0
    if not args.no_prompt:
        return await prompt_float("Visible area (m2)", existing_area, required=True)
    return None


async def _resolve_full_metadata(
    camera_id: str, existing: Optional[dict], existing_area: Optional[float], args: argparse.Namespace, settings
) -> Tuple[Optional[dict], int]:
    """Full mode: new camera or metadata overrides."""
    if existing:
        print(f"[Onboarding] Edit mode for existing camera: {camera_id}")
        print("[Onboarding] Press Enter to keep existing values.")
    else:
        print(f"[Onboarding] Create mode for new camera: {camera_id}")

    name = await _resolve_field(args.name, existing, "name", "Camera name", required=True, no_prompt=args.no_prompt)
    rtsp_url = await _resolve_field(args.rtsp_url, existing, "rtsp_url", "RTSP URL", required=True, no_prompt=args.no_prompt)
    location = await _resolve_field(args.location, existing, "location", "Location", default="Unknown", no_prompt=args.no_prompt)
    fob_type = await _resolve_field(args.fob_type, existing, "fob_type", "FOB Type (optional)", no_prompt=args.no_prompt)
    zone_id = await _resolve_field(args.zone_id, existing, "zone_id", "Zone ID (optional)", no_prompt=args.no_prompt)

    area_m2 = await _resolve_full_area_m2(existing_area, args, settings)
    if area_m2 is None and args.no_prompt:
        print("Error: area_m2 is required in area density mode.")
        return None, 2

    if not name or not rtsp_url:
        print("Error: name and rtsp_url are required.")
        return None, 2

    return {
        "name": name,
        "rtsp_url": rtsp_url,
        "location": location,
        "fob_type": fob_type,
        "zone_id": zone_id,
        "area_m2": area_m2,
    }, 0


async def _resolve_metadata(
    camera_id: str, existing: Optional[dict], existing_area: Optional[float], args: argparse.Namespace, settings
) -> Tuple[Optional[dict], int]:
    has_metadata_overrides = any([
        args.name, args.rtsp_url, args.location, args.fob_type, args.zone_id
    ])

    if existing and not has_metadata_overrides:
        return await _resolve_roi_only_metadata(camera_id, existing, existing_area, args, settings)
    return await _resolve_full_metadata(camera_id, existing, existing_area, args, settings)


def _capture_and_save_frame(rtsp_url: str, args: argparse.Namespace) -> Optional[np.ndarray]:
    print(f"[Onboarding] Capturing frame from: {rtsp_url}")
    frame = capture_reference_frame(
        rtsp_url=rtsp_url,
        timeout_seconds=args.capture_timeout,
        warmup_frames=args.warmup_frames,
    )
    if frame is None:
        print("[Onboarding] Error: could not capture frame from RTSP. Calibration not written.")
        return None

    frame_h, frame_w = frame.shape[:2]
    print(f"[Onboarding] Captured frame: {frame_w}x{frame_h}")

    if args.save_frame_path:
        frame_path = Path(args.save_frame_path)
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(args.save_frame_path, frame)
        if ok:
            print(f"[Onboarding] Saved reference frame to: {args.save_frame_path}")
        else:
            print(f"[Onboarding] Warning: failed to save reference frame to: {args.save_frame_path}")

    return frame


async def _run_roi_editor_and_persist(
    camera_id: str, frame: np.ndarray, existing_calibration: dict, area_m2: float, zone_id: Optional[str]
) -> int:
    frame_h, frame_w = frame.shape[:2]

    existing_roi = existing_calibration.get("roi") or {}
    initial_roi_points = prepare_roi_points_for_current_frame(
        stored_points=existing_roi.get("points"),
        stored_frame_width=existing_roi.get("frame_width"),
        stored_frame_height=existing_roi.get("frame_height"),
        current_frame_width=frame_w,
        current_frame_height=frame_h,
    )
    if initial_roi_points:
        print(f"[Onboarding] Loaded existing ROI for edit: {len(initial_roi_points)} points.")

    roi_editor = ROIEditor(
        camera_id=camera_id,
        frame=frame,
        area_m2=area_m2,
        initial_points=initial_roi_points,
    )
    roi_points = roi_editor.run()
    if roi_points is None:
        print("[Onboarding] Calibration not written (ROI save was cancelled).")
        return 1

    success = await CameraService.set_camera_calibration(
        camera_id=camera_id,
        area_m2=area_m2,
        roi_points=roi_points,
        frame_width=frame_w,
        frame_height=frame_h,
    )
    if not success:
        print("[Onboarding] Error: failed to persist calibration to MongoDB.")
        return 1

    calibration = await CameraService.get_camera_calibration(camera_id)
    roi_count = len((calibration or {}).get("roi", {}).get("points", []))

    print("\n[Onboarding] Completed successfully")
    print(f"  camera_id: {camera_id}")
    print(f"  zone_id: {zone_id or '-'}")
    print(f"  area_m2: {area_m2}")
    print(f"  roi_vertices: {roi_count}")
    print(f"  frame_size: {frame_w}x{frame_h}")
    return 0


async def async_main(args: argparse.Namespace) -> int:
    # Handle --list mode
    if args.list:
        return await list_cameras()

    camera_id, error_code = await _resolve_camera_id(args)
    if camera_id is None:
        return error_code

    settings = get_settings()
    await connect_to_mongo(settings)

    try:
        existing = await CameraService.get_camera(camera_id)
        existing_calibration = (existing or {}).get("calibration") or {}
        existing_area = existing_calibration.get("area_m2")

        metadata, error_code = await _resolve_metadata(camera_id, existing, existing_area, args, settings)
        if metadata is None:
            return error_code

        area_m2 = metadata["area_m2"]
        zone_id = metadata["zone_id"]

        if area_m2 is not None and area_m2 <= 0:
            print("Error: area_m2 must be > 0")
            return 2

        action, _ = await upsert_camera_metadata(
            camera_id=camera_id,
            name=metadata["name"],
            rtsp_url=metadata["rtsp_url"],
            location=metadata["location"],
            fob_type=metadata["fob_type"],
            zone_id=zone_id,
        )
        print(f"[Onboarding] Camera {action}: {camera_id}")

        frame = _capture_and_save_frame(metadata["rtsp_url"], args)
        if frame is None:
            return 1

        return await _run_roi_editor_and_persist(
            camera_id, frame, existing_calibration, area_m2 or 150.0, zone_id
        )
    finally:
        await close_mongo_connection()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
