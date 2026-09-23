"""
ROI Drawing Tool for CrowdVision

Interactive GUI tool to draw ROI polygons and set area_m2 for cameras.
Saves to MongoDB via API or to camera_calibrations.json.

Usage:
    python tools/roi_tool.py <camera_id> --frame <image_path> --area 120.5
    python tools/roi_tool.py <camera_id> --rtsp rtsp://192.168.1.100/stream --area 80
    python tools/roi_tool.py <camera_id> --frame snapshot.jpg --area 100 --save-db --api-url http://localhost:8000

Controls:
    - Left click: Add ROI vertex
    - Right click: Remove last vertex
    - C: Close polygon (connect last to first)
    - S: Save ROI
    - R: Reset all points
    - Q/ESC: Quit
"""
import cv2
import numpy as np
import json
import argparse
import logging
import sys
import requests
from pathlib import Path
from typing import List, Tuple, Optional
logger = logging.getLogger(__name__)

class ROITool:
    """Interactive ROI polygon drawing tool"""

    def __init__(self, camera_id: str, frame: np.ndarray, area_m2: float):
        self.camera_id = camera_id
        self.frame = frame.copy()
        self.display_frame = frame.copy()
        self.frame_w = frame.shape[1]
        self.frame_h = frame.shape[0]
        self.area_m2 = area_m2

        self.points: List[Tuple[int, int]] = []
        self.polygon_closed = False

        self.window_name = f"ROI Tool: {camera_id}"

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and not self.polygon_closed:
            self.points.append((x, y))
            self._update_display()

        elif event == cv2.EVENT_RBUTTONDOWN and self.points and not self.polygon_closed:
            self.points.pop()
            self._update_display()

        elif event == cv2.EVENT_MOUSEMOVE:
            temp = self.display_frame.copy()
            # Crosshair
            cv2.line(temp, (x, 0), (x, self.frame_h), (0, 255, 255), 1)
            cv2.line(temp, (0, y), (self.frame_w, y), (0, 255, 255), 1)
            # Preview line from last point
            if self.points and not self.polygon_closed:
                cv2.line(temp, self.points[-1], (x, y), (0, 255, 0), 1)
            cv2.imshow(self.window_name, temp)

    def _update_display(self):
        self.display_frame = self.frame.copy()

        if len(self.points) >= 1:
            # Draw points
            for i, pt in enumerate(self.points):
                cv2.circle(self.display_frame, pt, 5, (0, 255, 0), -1)
                cv2.circle(self.display_frame, pt, 7, (255, 255, 255), 2)
                cv2.putText(self.display_frame, str(i + 1), (pt[0] + 10, pt[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Draw lines between points
            for i in range(len(self.points) - 1):
                cv2.line(self.display_frame, self.points[i], self.points[i + 1], (0, 255, 0), 2)

            # Draw closing line if polygon is closed
            if self.polygon_closed and len(self.points) >= 3:
                cv2.line(self.display_frame, self.points[-1], self.points[0], (0, 255, 0), 2)
                # Semi-transparent fill
                overlay = self.display_frame.copy()
                pts = np.array(self.points, dtype=np.int32)
                cv2.fillPoly(overlay, [pts], (0, 255, 0))
                cv2.addWeighted(overlay, 0.2, self.display_frame, 0.8, 0, self.display_frame)

        # Info panel
        self._draw_info()
        cv2.imshow(self.window_name, self.display_frame)

    def _draw_info(self):
        overlay = self.display_frame.copy()
        cv2.rectangle(overlay, (5, 5), (420, 140), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, self.display_frame, 0.3, 0, self.display_frame)

        lines = [
            f"Camera: {self.camera_id} | Area: {self.area_m2} m2",
            f"Vertices: {len(self.points)} | Closed: {self.polygon_closed}",
            "",
            "L-Click: Add point | R-Click: Undo",
            "C: Close polygon | S: Save | R: Reset | Q: Quit"
        ]

        y = 25
        for line in lines:
            cv2.putText(self.display_frame, line, (15, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            y += 20

    def get_roi_points(self) -> List[List[float]]:
        """Get ROI points as [[x, y], ...]"""
        return [[float(x), float(y)] for x, y in self.points]

    def save_to_json(self):
        """Save ROI to camera_calibrations.json"""
        if not self.polygon_closed or len(self.points) < 3:
            logger.warning("Cannot save: polygon not closed (need 3+ points, press C)")
            return False

        config_path = Path(__file__).parent.parent / 'config' / 'camera_calibrations.json'

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        if self.camera_id not in config:
            config[self.camera_id] = {}

        config[self.camera_id]['visible_area_m2'] = self.area_m2
        config[self.camera_id]['roi'] = {
            'points': self.get_roi_points(),
            'frame_width': self.frame_w,
            'frame_height': self.frame_h
        }

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Saved ROI to {config_path}")
        return True

    def save_to_db(self, api_url: str, token: str = None):
        """Save ROI to MongoDB via API"""
        if not self.polygon_closed or len(self.points) < 3:
            logger.warning("Cannot save: polygon not closed (need 3+ points, press C)")
            return False

        url = f"{api_url.rstrip('/')}/api/cameras/{self.camera_id}/roi"
        payload = {
            "area_m2": self.area_m2,
            "roi_points": self.get_roi_points(),
            "frame_width": self.frame_w,
            "frame_height": self.frame_h
        }

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resp = requests.put(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Saved ROI to database via API: {url}")
                return True
            else:
                logger.error(f"API error {resp.status_code}: {resp.text}")
                return False
        except Exception:
            logger.exception("Failed to save to DB")
            return False

    def _handle_reset_key(self):
        self.points = []
        self.polygon_closed = False
        print("Points reset.")
        self._update_display()

    def _handle_close_key(self):
        if len(self.points) >= 3:
            self.polygon_closed = True
            print(f"Polygon closed with {len(self.points)} vertices.")
            self._update_display()
        else:
            print("Need at least 3 points to close polygon.")

    def _handle_save_key(self, save_db: bool, api_url: str, token: Optional[str]):
        if save_db:
            self.save_to_db(api_url, token)
        else:
            self.save_to_json()

    def _handle_key(self, key: int, save_db: bool, api_url: str, token: Optional[str]) -> bool:
        """Handle a key press. Returns True if the tool should quit."""
        if key in (ord('q'), ord('Q'), 27):
            return True
        if key in (ord('r'), ord('R')):
            self._handle_reset_key()
        elif key in (ord('c'), ord('C')):
            self._handle_close_key()
        elif key in (ord('s'), ord('S')):
            self._handle_save_key(save_db, api_url, token)
        return False

    def run(self, save_db: bool = False, api_url: str = "http://localhost:8000", token: str = None):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, min(1280, self.frame_w), min(720, self.frame_h))
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        self._update_display()

        logger.info(f"\nROI Tool | Camera: {self.camera_id} | Area: {self.area_m2} m²")
        logger.info(f"Frame: {self.frame_w}x{self.frame_h}")
        logger.info(f"Save to: {'MongoDB via API' if save_db else 'camera_calibrations.json'}")
        logger.info("Draw ROI polygon by clicking vertices, then press C to close, S to save.\n")

        while True:
            key = cv2.waitKey(50) & 0xFF
            if self._handle_key(key, save_db, api_url, token):
                break

        cv2.destroyAllWindows()


def capture_frame(source: str, frame_number: int = 30) -> Optional[np.ndarray]:
    """Capture a frame from image, video, or RTSP"""
    # Try as image first
    frame = cv2.imread(source)
    if frame is not None:
        return frame

    # Try as video/RTSP
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return None

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    for _ in range(30):
        ret, frame = cap.read()
        if ret:
            cap.release()
            return frame

    cap.release()
    return None


def main():
    parser = argparse.ArgumentParser(
        description="ROI Drawing Tool for CrowdVision",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("camera_id", help="Camera identifier")
    parser.add_argument("--frame", help="Path to reference frame image")
    parser.add_argument("--rtsp", help="RTSP URL to capture frame from")
    parser.add_argument("--video", help="Video file to extract frame from")
    parser.add_argument("--area", type=float, required=True, help="Real-world area in m² (from station staff)")
    parser.add_argument("--save-db", action="store_true",
                       help="Save to MongoDB via API instead of camera_calibrations.json")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL (for --save-db)")
    parser.add_argument("--token", default=None, help="JWT token for API auth (for --save-db)")

    args = parser.parse_args()

    # Get frame
    source = args.frame or args.rtsp or args.video
    if not source:
        logger.error("Error: Provide --frame, --rtsp, or --video")
        parser.print_help()
        sys.exit(1)

    frame = capture_frame(source)
    if frame is None:
        logger.error(f"Error: Cannot read frame from: {source}")
        sys.exit(1)

    logger.info(f"Loaded frame: {frame.shape[1]}x{frame.shape[0]}")

    tool = ROITool(args.camera_id, frame, args.area)
    tool.run(save_db=args.save_db, api_url=args.api_url, token=args.token)


if __name__ == "__main__":
    main()
