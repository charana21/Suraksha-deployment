"""
YOLO wrapper for head detection

Enhanced with occupancy metrics for regime-based fusion.
"""
from typing import List, Dict, Tuple
import numpy as np
from ultralytics import YOLO
from config.config import get_settings
import logging
logger = logging.getLogger(__name__)
class YOLOWrapper:
    """Wrapper for YOLOv8 head detection"""
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.10,  # Even lower threshold for dense crowds
        head_size_min: int = 5,  # Allow much smaller detections for distant people
        head_size_max: int = 300,  # Allow larger detections
        device: str = "cuda"
    ):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.head_size_min = head_size_min
        self.head_size_max = head_size_max
        self.settings = get_settings()
        # Ultralytics already performs NMS in model.predict().
        # Keep Python NMS optional for troubleshooting only.
        self.python_post_nms_enabled = bool(getattr(self.settings, "yolo_python_post_nms_enabled", False))

        logger.info(f"[YOLO] Initialized with conf={conf_threshold}, size_range=[{head_size_min}, {head_size_max}]")

        try:
            self.model.to(device)
        except Exception as e:
            print(f"[WARN] Could not move YOLO to {device}: {e}")
    
    def _parse_result(self, result, h: int, w: int) -> List[Dict]:
        """Parse a single Ultralytics Results object into detection dicts."""
        detections = []
        boxes = result.boxes
        if boxes is None:
            return detections

        adaptive_max_size = max(self.head_size_max, int(max(h, w) * 0.95))
        for box in boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, xyxy)

            box_w, box_h = x2 - x1, y2 - y1
            box_size = max(box_w, box_h)
            if not (self.head_size_min <= box_size <= adaptive_max_size):
                continue

            conf = float(box.conf[0].cpu().numpy())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if not (0 <= cx < w and 0 <= cy < h):
                continue

            detections.append({
                'bbox': (x1, y1, x2, y2),
                'center': (cx, cy),
                'size': box_size,
                'confidence': conf
            })
        return detections

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """Detect people (persons) in frame."""
        h, w = frame.shape[:2]

        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            iou=0.5,
            classes=[0],
            verbose=False,
            imgsz=1280,
            agnostic_nms=True,
            max_det=500
        )

        detections = []
        for result in results:
            detections.extend(self._parse_result(result, h, w))

        if self.python_post_nms_enabled:
            detections = self._nms_detections(detections)

        if len(detections) > 0 and np.random.random() < 0.03:
            logger.info(f"[YOLO] Detected {len(detections)} people")

        return detections

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[Dict]]:
        """Run YOLO on N frames in a single GPU forward pass.

        Ultralytics handles letterbox-padding all frames to imgsz=1280 internally.
        Returns one detection list per frame.
        """
        if not frames:
            return []

        batch_results = self.model.predict(
            frames,
            conf=self.conf_threshold,
            iou=0.5,
            classes=[0],
            verbose=False,
            imgsz=1280,
            agnostic_nms=True,
            max_det=500,
        )

        all_detections = []
        for frame, result in zip(frames, batch_results):
            h, w = frame.shape[:2]
            dets = self._parse_result(result, h, w)
            if self.python_post_nms_enabled:
                dets = self._nms_detections(dets)
            all_detections.append(dets)
        return all_detections

    def detect_batch_with_metrics(self, frames: List[np.ndarray]) -> List[Dict]:
        """Batch version of detect_with_metrics(). Single GPU forward pass."""
        all_detections = self.detect_batch(frames)
        results = []
        for frame, detections in zip(frames, all_detections):
            h, w = frame.shape[:2]
            count = len(detections)
            if count == 0:
                results.append({
                    'detections': [], 'count': 0,
                    'avg_confidence': 0.0, 'occupancy_ratio': 0.0,
                })
            else:
                frame_area = h * w
                total_bbox_area = sum(
                    (d['bbox'][2] - d['bbox'][0]) * (d['bbox'][3] - d['bbox'][1])
                    for d in detections
                )
                total_conf = sum(d['confidence'] for d in detections)
                results.append({
                    'detections': detections,
                    'count': count,
                    'avg_confidence': total_conf / count,
                    'occupancy_ratio': total_bbox_area / frame_area,
                })
        return results

    def detect_with_metrics(self, frame: np.ndarray) -> Dict:
        """Detect people and return enhanced metrics for fusion."""
        h, w = frame.shape[:2]
        frame_area = h * w

        detections = self.detect(frame)
        count = len(detections)

        if count == 0:
            return {
                'detections': [],
                'count': 0,
                'avg_confidence': 0.0,
                'occupancy_ratio': 0.0
            }

        total_bbox_area = 0.0
        total_confidence = 0.0

        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            total_bbox_area += (x2 - x1) * (y2 - y1)
            total_confidence += det['confidence']

        return {
            'detections': detections,
            'count': count,
            'avg_confidence': total_confidence / count,
            'occupancy_ratio': total_bbox_area / frame_area
        }
    
    def _nms_detections(self, detections: List[Dict], iou_threshold: float = 0.4) -> List[Dict]:
        """Apply non-maximum suppression"""
        if len(detections) == 0:
            return []
        
        detections = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            
            detections = [
                det for det in detections
                if self._calculate_iou(best['bbox'], det['bbox']) < iou_threshold
            ]
        
        return keep
    
    @staticmethod
    def _calculate_iou(box1: Tuple, box2: Tuple) -> float:
        """Calculate IoU"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
