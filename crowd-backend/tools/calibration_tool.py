"""
Camera Calibration Tool for CrowdVision

Interactive GUI tool to collect reference points and compute homography.

Usage:
    python tools/calibration_tool.py <camera_id> --frame <image_path>
    python tools/calibration_tool.py cam_pf1_fob_kzj --frame snapshot.jpg
    python tools/calibration_tool.py cam_pf1_fob_kzj --rtsp rtsp://192.168.1.100/stream

Controls:
    - Left click: Add reference point
    - R: Reset all points
    - C: Compute homography (need 4+ points)
    - S: Save to config after computing
    - Q/ESC: Quit
"""

import cv2
import numpy as np
import json
import argparse
import logging
import sys
from pathlib import Path
from datetime import UTC, datetime
from typing import List, Tuple, Optional
import logging
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

from utils.homography import (
    ReferencePoint,
    compute_homography,
    validate_homography,
    create_homography_config
)


class CalibrationTool:
    """Interactive calibration point collection tool"""

    def __init__(self, camera_id: str, frame: np.ndarray):
        self.camera_id = camera_id
        self.frame = frame.copy()
        self.display_frame = frame.copy()
        self.frame_size = (frame.shape[1], frame.shape[0])  # (width, height)

        self.pixel_points: List[Tuple[float, float]] = []
        self.world_points: List[Tuple[float, float]] = []
        self.current_pixel: Optional[Tuple[int, int]] = None
        self.computed_homography: Optional[dict] = None

        self.window_name = f"Calibration: {camera_id}"
        self.input_mode = False

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events"""
        if self.input_mode:
            return  # Don't process clicks during input

        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_pixel = (x, y)
            self._update_display()
            self._prompt_world_coords()

        elif event == cv2.EVENT_MOUSEMOVE:
            # Show crosshair at current position
            temp = self.display_frame.copy()
            cv2.line(temp, (x, 0), (x, self.frame_size[1]), (0, 255, 255), 1)
            cv2.line(temp, (0, y), (self.frame_size[0], y), (0, 255, 255), 1)

            # Show coordinates
            coord_text = f"({x}, {y})"
            cv2.putText(temp, coord_text, (x + 10, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            cv2.imshow(self.window_name, temp)

    def _update_display(self):
        """Update display with current points"""
        self.display_frame = self.frame.copy()

        # Draw existing points
        for i, (px, py) in enumerate(self.pixel_points):
            # Draw point marker
            px_int, py_int = int(px), int(py)
            cv2.circle(self.display_frame, (px_int, py_int), 8, (0, 255, 0), -1)
            cv2.circle(self.display_frame, (px_int, py_int), 10, (255, 255, 255), 2)

            # Draw label with world coordinates
            wx, wy = self.world_points[i]
            label = f"P{i+1}: ({wx:.2f}m, {wy:.2f}m)"
            cv2.putText(self.display_frame, label, (px_int + 15, py_int - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
            cv2.putText(self.display_frame, label, (px_int + 15, py_int - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Draw polygon connecting points (if >= 3)
        if len(self.pixel_points) >= 3:
            pts = np.array(self.pixel_points, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(self.display_frame, [pts], True, (255, 0, 0), 2)

        # Draw instructions panel
        self._draw_instructions()

    def _draw_instructions(self):
        """Draw instruction panel on the frame"""
        # Semi-transparent background
        overlay = self.display_frame.copy()
        cv2.rectangle(overlay, (5, 5), (400, 160), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, self.display_frame, 0.3, 0, self.display_frame)

        instructions = [
            f"Camera: {self.camera_id}",
            f"Points: {len(self.pixel_points)}/4+ (need at least 4)",
            "",
            "Click on known floor points (tile corners, etc.)",
            "Then enter real-world X,Y coordinates in meters",
            "",
            "Keys: C=Compute | S=Save | R=Reset | Q=Quit"
        ]

        y_offset = 25
        for line in instructions:
            color = (0, 255, 0) if "Points:" in line and len(self.pixel_points) >= 4 else (255, 255, 255)
            cv2.putText(self.display_frame, line, (15, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
            y_offset += 20

    def _prompt_world_coords(self):
        """Prompt user for world coordinates via console"""
        if self.current_pixel is None:
            return

        self.input_mode = True
        print(f"\n{'='*50}")
        logger.info(f"Point {len(self.pixel_points) + 1} clicked at pixel: {self.current_pixel}")
        logger.info(f"Point {len(self.pixel_points) + 1} clicked at pixel: {self.current_pixel}")
        logger.info("Enter real-world coordinates in METERS")
        logger.info("(Use the floor plane coordinate system)")

        try:
            x_str = input("  World X (meters): ").strip()
            y_str = input("  World Y (meters): ").strip()

            world_x = float(x_str)
            world_y = float(y_str)

            self.pixel_points.append(self.current_pixel)
            self.world_points.append((world_x, world_y))

            logger.info(f"  Added: pixel={self.current_pixel} -> world=({world_x:.2f}, {world_y:.2f})")

        except ValueError:
            logger.error("  Invalid input - please enter numeric values")
        except KeyboardInterrupt:
            logger.info("\n  Point cancelled")

        self.current_pixel = None
        self.input_mode = False
        self._update_display()

    def _compute_homography(self) -> bool:
        """Compute homography from current points"""
        if len(self.pixel_points) < 4:
            logger.info(f"\nNeed at least 4 points, have {len(self.pixel_points)}")
            return False

        logger.info(f"\n{'='*50}")
        logger.info("Computing homography...")

        ref_points = [
            ReferencePoint(pixel=p, world=w)
            for p, w in zip(self.pixel_points, self.world_points)
        ]

        try:
            H, error, mask = compute_homography(ref_points)

            # Validate
            is_valid, msg = validate_homography(H, self.frame_size)
            logger.info(f"Validation: {msg}")

            inliers = int(np.sum(mask)) if mask is not None else len(ref_points)
            logger.info(f"Reprojection error: {error:.3f} meters")
            logger.info(f"Inliers: {inliers}/{len(ref_points)}")

            if not is_valid:
                logger.warning("\nWARNING: Homography validation failed!")
                logger.warning("The calibration may produce incorrect results.")

            # Store computed config
            self.computed_homography = {
                'enabled': True,
                'matrix': H.tolist(),
                'reference_points': [
                    {'pixel': list(p.pixel), 'world': list(p.world)}
                    for p in ref_points
                ],
                'frame_size': list(self.frame_size),
                'reprojection_error': error,
                'calibrated_at': datetime.now(UTC).isoformat() + 'Z',
                'calibrated_by': 'calibration_tool'
            }

            logger.info("\nHomography computed successfully!")
            logger.info("Press 'S' to save to camera_calibrations.json")
            return True

        except Exception:
            logger.exception("Error computing homography")
            return False

    def _save_to_config(self):
        """Save homography config to camera_calibrations.json"""
        if self.computed_homography is None:
            logger.info("\nNo homography computed yet. Press 'C' first.")
            return

        config_path = Path(__file__).parent.parent / 'config' / 'camera_calibrations.json'

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        # Ensure camera entry exists
        if self.camera_id not in config:
            config[self.camera_id] = {
                'visible_area_m2': 150.0,
                'corridor_width_m': 4.0,
                'coverage_length_m': 40.0,
                'lane_count': 1,
                'camera_type': 'fob',
                'notes': f'Calibrated via calibration_tool'
            }

        # Add homography
        config[self.camera_id]['homography'] = self.computed_homography

        # Also update visible_area_m2 based on computed homography
        H = np.array(self.computed_homography['matrix'])
        is_valid, msg = validate_homography(H, self.frame_size)
        if is_valid and "area:" in msg:
            # Extract computed area from validation message
            import re
            match = re.search(r'area: ([\d.]+)', msg)
            if match:
                computed_area = float(match.group(1))
                config[self.camera_id]['visible_area_m2'] = computed_area
                logger.info(f"Updated visible_area_m2 to {computed_area:.1f} m²")

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"\nSaved to {config_path}")
        logger.info(f"Camera '{self.camera_id}' now has homography calibration enabled.")

    def run(self) -> Optional[dict]:
        """Run the calibration tool"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, min(1280, self.frame_size[0]), min(720, self.frame_size[1]))
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        self._update_display()

        logger.info("\n" + "="*60)
        logger.info("CALIBRATION TOOL")
        logger.info("="*60)
        logger.info(f"Camera: {self.camera_id}")
        logger.info(f"Frame size: {self.frame_size[0]}x{self.frame_size[1]}")
        logger.info("\nInstructions:")
        logger.info("1. Click on 4+ points on the FLOOR that you can measure")
        logger.info("2. For each point, enter the real-world X,Y in meters")
        logger.info("3. Press 'C' to compute homography")
        logger.info("4. Press 'S' to save to config")
        logger.info("\nTip: Use floor tiles, door frames, or known markers")
        logger.info("="*60 + "\n")

        while True:
            cv2.imshow(self.window_name, self.display_frame)
            key = cv2.waitKey(50) & 0xFF

            if key == ord('q') or key == ord('Q') or key == 27:  # Q or ESC
                logger.info("\nCalibration tool closed.")
                break

            elif key == ord('r') or key == ord('R'):
                self.pixel_points = []
                self.world_points = []
                self.computed_homography = None
                logger.info("\nPoints reset.")
                self._update_display()

            elif key == ord('c') or key == ord('C'):
                self._compute_homography()

            elif key == ord('s') or key == ord('S'):
                self._save_to_config()

        cv2.destroyAllWindows()
        return self.computed_homography


def capture_frame_from_rtsp(rtsp_url: str, timeout: int = 10) -> Optional[np.ndarray]:
    """Capture a single frame from RTSP stream"""
    logger.info(f"Connecting to RTSP: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        logger.error("Error: Cannot open RTSP stream")
        return None

    # Try to read a frame
    for _ in range(30):  # Try up to 30 frames
        ret, frame = cap.read()
        if ret:
            cap.release()
            logger.info(f"Captured frame: {frame.shape[1]}x{frame.shape[0]}")
            return frame

    cap.release()
    logger.error("Error: Cannot read frame from RTSP stream")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Camera Calibration Tool for CrowdVision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/calibration_tool.py cam_pf1_fob_kzj --frame snapshot.jpg
    python tools/calibration_tool.py cam_test --rtsp rtsp://192.168.1.100/stream
    python tools/calibration_tool.py cam_test --video test.mp4

Workflow:
    1. Click on 4+ reference points on the floor
    2. Enter real-world coordinates (X, Y in meters) for each
    3. Press 'C' to compute homography
    4. Press 'S' to save to config/camera_calibrations.json
        """
    )
    parser.add_argument("camera_id", help="Camera identifier (e.g., cam_pf1_fob_kzj)")
    parser.add_argument("--frame", help="Path to reference frame image")
    parser.add_argument("--rtsp", help="RTSP URL to capture frame from")
    parser.add_argument("--video", help="Video file to extract frame from")
    parser.add_argument("--frame-number", type=int, default=30,
                       help="Frame number to extract from video (default: 30)")

    args = parser.parse_args()

    # Get frame from one of the sources
    frame = None

    if args.frame:
        frame = cv2.imread(args.frame)
        if frame is None:
            logger.error(f"Error: Cannot read image: {args.frame}")
            sys.exit(1)
        logger.info(f"Loaded image: {args.frame}")

    elif args.rtsp:
        frame = capture_frame_from_rtsp(args.rtsp)
        if frame is None:
            sys.exit(1)

    elif args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            logger.error(f"Error: Cannot open video: {args.video}")
            sys.exit(1)

        # Seek to specified frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            logger.error(f"Error: Cannot read frame {args.frame_number} from video")
            sys.exit(1)
        logger.info(f"Extracted frame {args.frame_number} from {args.video}")

    else:
        logger.error("Error: Provide --frame, --rtsp, or --video")
        parser.print_help()
        sys.exit(1)

    # Run calibration tool
    tool = CalibrationTool(args.camera_id, frame)
    result = tool.run()

    if result:
        logger.info("\n" + "="*60)
        logger.info("CALIBRATION COMPLETE")
        logger.info("="*60)
        logger.info(f"Reprojection error: {result['reprojection_error']:.3f} meters")
        logger.info(f"Reference points: {len(result['reference_points'])}")
        logger.info("\nHomography matrix:")
        for row in result['matrix']:
            logger.info(f"  [{row[0]:12.6f}, {row[1]:12.6f}, {row[2]:12.6f}]")


if __name__ == "__main__":
    main()
