"""
RTSP Stream Worker - Independent thread for each RTSP stream

Each worker runs in its own thread with:
- Independent frame capture loop
- Own crowd analyzer instance
- Own state management
- Graceful error handling and recovery
"""
import logging
import cv2
import threading
import time
import queue
import logging
from typing import Dict, Optional, List
from collections import deque
import numpy as np
import uuid
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from services.crowd_analyzer import CrowdAnalyzer
from services.zone_analytics import broadcast_zone_update_for_camera
from config.config import get_settings
from utils.visualization import visualize_heatmap_only
from utils.circuit_breaker import CircuitBreaker, ExponentialBackoff
import os

logger = logging.getLogger(__name__)


class RTSPWorkerState:
    """Thread-safe state for RTSP worker"""

    def __init__(self):
        self._lock = threading.Lock()
        self._status = "initializing"
        self._frame_count = 0
        self._fps = 0.0
        self._error = None
        self._last_analysis = None
        self._connection_attempts = 0

    def update_status(self, status: str, error: Optional[str] = None):
        with self._lock:
            self._status = status
            self._error = error

    def increment_frame(self):
        with self._lock:
            self._frame_count += 1

    def update_fps(self, fps: float):
        with self._lock:
            self._fps = fps

    def update_analysis(self, result: Dict):
        with self._lock:
            self._last_analysis = result

    def increment_connection_attempts(self):
        with self._lock:
            self._connection_attempts += 1
            return self._connection_attempts

    def reset_connection_attempts(self):
        with self._lock:
            self._connection_attempts = 0

    def get_snapshot(self) -> Dict:
        """Get thread-safe snapshot of current state"""
        with self._lock:
            # Convert last_analysis to JSON-serializable format
            serializable_analysis = None
            if self._last_analysis:
                serializable_analysis = {
                    'frame_number': self._last_analysis.get('frame_number'),
                    'people_count': self._last_analysis.get('people_count'),
                    'head_detections': self._last_analysis.get('head_detections'),
                    'density_avg': self._last_analysis.get('density_avg'),
                    'density_max': self._last_analysis.get('density_max'),
                    'motion_intensity': self._last_analysis.get('motion_intensity'),
                    'zones': self._last_analysis.get('zones', {})
                    # Note: density_map and detections (numpy arrays) are excluded
                }

            return {
                'status': self._status,
                'frame_count': self._frame_count,
                'fps': self._fps,
                'error': self._error,
                'last_analysis': serializable_analysis,
                'connection_attempts': self._connection_attempts
            }


class RTSPWorker:
    """
    Independent RTSP stream worker running in dedicated thread

    Thread-based approach chosen because:
    1. Frame capture (cv2.VideoCapture.read()) is blocking I/O
    2. GIL released during OpenCV C++ operations
    3. Each stream needs independent blocking capture loop
    4. ML inference (PyTorch) releases GIL for computation
    5. Simpler state management than multiprocessing
    """

    def __init__(
        self,
        stream_id: str,
        rtsp_url: str,
        camera_id: str = None,  # NEW: Camera ID (distinct from stream_id)
        camera_name: str = None, # NEW: Human readable name
        fob_type: str = None,    # NEW: FOB ID/Type (HYD/KZJ)
        zone_id: str = None,     # Zone this camera belongs to (e.g. zone_hyb_fob)
        zone_type: str = None,   # Zone type: FOB, PLATFORM, BOOKING
        location: str = None,    # NEW: Camera location
        target_fps: Optional[int] = None,
        reconnect_attempts: Optional[int] = None,
        reconnect_delay: Optional[float] = None,
        frame_buffer_size: int = 1,
        persistence_worker = None,  # NEW: PersistenceWorker instance
        websocket_manager = None,   # NEW: ConnectionManager instance
        async_loop = None           # NEW: asyncio event loop reference
    ):
        """
        Initialize RTSP worker

        Args:
            stream_id: Unique identifier for this stream
            rtsp_url: RTSP stream URL
            camera_id: Camera ID (if None, uses stream_id)
            camera_name: Human readable name
            fob_type: FOB ID/Type (HYD/KZJ)
            location: Camera location
            target_fps: Target FPS for processing (None = process every frame)
            reconnect_attempts: Max reconnection attempts before giving up
            reconnect_delay: Delay between reconnection attempts (seconds)
            frame_buffer_size: Size of frame buffer (1 = latest frame only)
            persistence_worker: PersistenceWorker instance for async MongoDB writes
            websocket_manager: ConnectionManager instance for WebSocket broadcasts
            async_loop: asyncio event loop reference
        """
        # Load settings
        self.settings = get_settings()

        self.stream_id = stream_id
        self.rtsp_url = rtsp_url

        # NEW: Camera ID (single source of truth)
        self.camera_id = camera_id if camera_id else stream_id

        # NEW: Metadata for alerts
        self.camera_name = camera_name
        self.fob_type = fob_type
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.location = location

        # NEW: Shared services
        self.persistence_worker = persistence_worker
        self.websocket_manager = websocket_manager
        self.async_loop = async_loop

        # NEW: Alert state tracking
        self.last_risk_level = "LOW"
        self.last_alert_time = None
        self._risk_persist_level = None
        self._risk_persist_start = None
        self._risk_persist_count = 0
        self._last_alert_at_level = None  # Track which level the last alert was for

        # NEW: Image rate limiting
        self.last_image_time = None
        self.images_this_hour = 0
        self.images_this_day = 0
        self.current_hour = datetime.now(UTC).hour
        self.current_day = datetime.now(UTC).date()

        # Use config defaults if not provided
        self.target_fps = target_fps if target_fps is not None else self.settings.rtsp_default_fps
        self.reconnect_attempts = reconnect_attempts if reconnect_attempts is not None else self.settings.rtsp_reconnect_attempts
        self.reconnect_delay = reconnect_delay if reconnect_delay is not None else self.settings.rtsp_reconnect_delay

        # Circuit breaker for resilient reconnection
        self.circuit_breaker = CircuitBreaker(
            name=f"rtsp_{stream_id}",
            failure_threshold=3,       # 3 consecutive failures → OPEN
            recovery_timeout=30.0      # Wait 30s before testing recovery
        )
        self.backoff = ExponentialBackoff(
            base_delay=2.0,
            max_delay=60.0,
            jitter=0.5
        )

        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # State management
        self.state = RTSPWorkerState()

        # Frame buffer (thread-safe queue)
        self.frame_buffer = queue.Queue(maxsize=frame_buffer_size)

        # Analytics
        self.analyzer: Optional[CrowdAnalyzer] = None

        # Performance tracking
        self._frame_times = deque(maxlen=30)  # Last 30 frame times for FPS calculation
        self._timing_history = deque(maxlen=300)  # Recent analyzer timing_ms samples

        # Heatmap saving - use config settings
        self.save_heatmaps = self.settings.save_heatmaps  # Use config setting
        self.heatmap_save_interval = self.settings.rtsp_heatmap_save_interval
        os.makedirs(self.settings.heatmap_dir, exist_ok=True)

        # Analytics saving
        self.save_analytics = True  # Enable JSON analytics saving
        self.analytics_save_interval = self.settings.rtsp_heatmap_save_interval  # Same interval
        os.makedirs(self.settings.analytics_dir, exist_ok=True)
        self.analytics_file = os.path.join(self.settings.analytics_dir, f"{stream_id}_analytics.jsonl")

        # Background heatmap saver (Phase 2 optimization - removes blocking I/O)
        if self.settings.heatmap_async:
            self.heatmap_queue = queue.Queue(maxsize=self.settings.max_heatmap_queue_size)
            self.heatmap_thread = threading.Thread(
                target=self._heatmap_saver_worker,
                daemon=True,
                name=f"HeatmapSaver-{stream_id}"
            )
            self.heatmap_thread.start()
            # print(f"[RTSP Worker {stream_id}] Started background heatmap saver thread")
            logger.info(f"[RTSP Worker {stream_id}] Heatmap saver thread started")
        else:
            self.heatmap_queue = None
            self.heatmap_thread = None

        # Background analytics writer (Phase 2 optimization - batch writes)
        self.analytics_buffer = []
        self.analytics_lock = threading.Lock()
    
        logger.info(f"[RTSP Worker {stream_id}] Initialized")
        logger.info(f"[RTSP Worker {stream_id}] Target FPS: {self.target_fps} (process 1 frame every {1.0/self.target_fps if self.target_fps > 0 else 0:.1f}s)")
        logger.info(f"[RTSP Worker {stream_id}] Heatmap save interval: every {self.heatmap_save_interval} processed frame(s)")
        logger.info(f"[RTSP Worker {stream_id}] Heatmaps will be saved to: {self.settings.heatmap_dir}")
        logger.info(f"[RTSP Worker {stream_id}] Analytics will be saved to: {self.analytics_file}")
        logger.info(f"[RTSP Worker {stream_id}] Heatmap max width: {self.settings.heatmap_max_width}px (format: {self.settings.heatmap_format})")
        logger.info(f"[RTSP Worker {stream_id}] Initialized with RTSP URL: {self.rtsp_url}")

        self._needs_density_map = (
            self.settings.enable_density_map_generation
            or self.save_heatmaps
        )

    def start(self):
        """Start the worker thread"""
        if self._running:
            # print(f"[RTSP Worker {self.stream_id}] Already running")
            logger.info(f"[RTSP Worker {self.stream_id}] Already running")
            return False

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name=f"RTSPWorker-{self.stream_id}",
            daemon=True
        )
        self._thread.start()
        # print(f"[RTSP Worker {self.stream_id}] Thread started")
        logger.info(f"[RTSP Worker {self.stream_id}] Thread started")
        return True

    def stop(self):
        """Stop the worker thread gracefully"""
        if not self._running:
            return

        # print(f"[RTSP Worker {self.stream_id}] Stopping...")
        logger.info(f"[RTSP Worker {self.stream_id}] Stopping...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        # Shutdown heatmap saver thread
        if self.heatmap_thread is not None:
            try:
                self.heatmap_queue.put(None, timeout=1.0)  # Signal shutdown
                self.heatmap_thread.join(timeout=2.0)
            except Exception:
                pass

        # Flush any remaining analytics buffer
        if self.analytics_buffer:
            try:
                with self.analytics_lock:
                    if len(self.analytics_buffer) > 0:
                        import json
                        with open(self.analytics_file, 'a') as f:
                            for data in self.analytics_buffer:
                                f.write(json.dumps(data) + '\n')
                        logger.info(f"[RTSP Worker {self.stream_id}] Flushed {len(self.analytics_buffer)} buffered analytics")

                        self.analytics_buffer.clear()
            except Exception:
                logger.exception(f"[RTSP Worker {self.stream_id}] Error flushing analytics")

        self._running = False
        # print(f"[RTSP Worker {self.stream_id}] Stopped")
        logger.info(f"[RTSP Worker {self.stream_id}] Stopped")

    def is_running(self) -> bool:
        """Check if worker is running"""
        return self._running and (self._thread is not None and self._thread.is_alive())

    def get_state(self) -> Dict:
        """Get current state snapshot"""
        state = self.state.get_snapshot()
        state.update({
            'stream_id': self.stream_id,
            'camera_id': self.camera_id,
            'rtsp_url': self.rtsp_url,
            'is_running': self.is_running(),
            'target_fps': self.target_fps
        })
        return state

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get latest frame from buffer (non-blocking)"""
        try:
            return self.frame_buffer.get_nowait()
        except queue.Empty:
            return None

    def get_latest_analysis(self) -> Optional[Dict]:
        """Get latest analysis result (thread-safe)"""
        with self.state._lock:
            return self.state._last_analysis.copy() if self.state._last_analysis else None

    def get_full_analysis(self) -> Optional[Dict]:
        """Get full analysis including numpy arrays (for internal use)"""
        with self.state._lock:
            return self.state._last_analysis.copy() if self.state._last_analysis else None

    def get_timing_stats(self) -> Dict[str, float]:
        """Get p50/p95 timing metrics from recent analyzer samples."""
        if not self._timing_history:
            return {
                "roi_ms_p50": 0.0,
                "roi_ms_p95": 0.0,
                "end_to_end_ms_p50": 0.0,
                "end_to_end_ms_p95": 0.0,
            }

        roi_values = []
        e2e_values = []
        for item in self._timing_history:
            roi = item.get("roi_filtering")
            total = item.get("total")
            if roi is not None:
                roi_values.append(float(roi))
            if total is not None:
                e2e_values.append(float(total))

        def pct(values: List[float], p: float) -> float:
            if not values:
                return 0.0
            return float(np.percentile(np.array(values, dtype=np.float64), p))

        return {
            "roi_ms_p50": pct(roi_values, 50),
            "roi_ms_p95": pct(roi_values, 95),
            "end_to_end_ms_p50": pct(e2e_values, 50),
            "end_to_end_ms_p95": pct(e2e_values, 95),
        }

    def _prepare_analytics_data(self, result: Dict, frame_num: int, timestamp: datetime) -> Dict:
        """
        Prepare analytics data for WebSocket broadcasting.

        Simplified schema - no zones object, no raw detections.
        All values converted to native Python types for JSON serialization.

        Args:
            result: Analytics result from CrowdAnalyzer
            frame_num: Frame number
            timestamp: Capture timestamp of the frame
        """
        timestamp_iso = timestamp.isoformat()

        # Extract full_frame zone data
        full_frame = result['zones'].get('full_frame', {})

        # Convert all values to native Python types to ensure JSON serialization
        return {
            # Identifiers - include both for frontend flexibility
            "camera_id": str(self.camera_id),
            "stream_id": str(self.stream_id),
            "timestamp": timestamp_iso,
            "frame_number": int(frame_num),

            # Core metrics (all converted to native types, rounded for clean output)
            "people_count": int(result.get('people_count', 0)),
            "density_avg": round(float(result.get('density_avg', 0.0)), 2),
            "density_level": str(full_frame.get('density_level', 'UNKNOWN')),
            "motion_intensity": round(float(result.get('motion_intensity', 0.0)), 4),
            "motion_level": str(full_frame.get('motion_level', 'STATIC')),

            # Risk assessment
            "risk_score": round(float(full_frame.get('risk_score', 0.0)), 1),
            "risk_level": str(full_frame.get('risk_level', 'LOW')),
            "risk_factors": list(full_frame.get('risk_factors', [])),
            "density_regime": str(full_frame.get('density_regime', 'UNKNOWN')),
            "fusion_rule": str(full_frame.get('fusion_rule', 'UNKNOWN')),
        }

    def _prepare_storage_data(self, result: Dict, frame_num: int, timestamp: datetime) -> Dict:
        """
        Prepare minimal analytics data for MongoDB storage.
        
        Args:
            result: Analytics result
            frame_num: Frame number
            timestamp: Capture timestamp
        """
        full_frame = result['zones'].get('full_frame', {})
        timing = result.get("timing_ms", {})
        doc = {
            "camera_id": str(self.camera_id),
            "stream_id": str(self.stream_id),
            "timestamp": timestamp,  # BSON datetime for MongoDB
            "frame_number": int(frame_num),

            # Core metrics (rounded for clean storage)
            "people_count": int(result.get('people_count', 0)),
            "density_avg": round(float(result.get('density_avg', 0.0)), 2),
            "density_level": str(full_frame.get('density_level', 'UNKNOWN')),
            "motion_intensity": round(float(result.get('motion_intensity', 0.0)), 4),
            "motion_level": str(full_frame.get('motion_level', 'STATIC')),

            # Risk
            "risk_score": round(float(full_frame.get('risk_score', 0.0)), 1),
            "risk_level": str(full_frame.get('risk_level', 'LOW')),
            # Performance metrics (rounded to 0.1ms)
            "timing_ms": {
              "total": round(float(timing.get("total", 0.0)), 1),
              "model_inference": round(float(timing.get("model_inference", 0.0)), 1),
              "model_only": round(float(timing.get("model_only", 0.0)), 1),
              "inference_end_to_end": round(float(timing.get("inference_end_to_end", 0.0)), 1),
              "optical_flow": round(float(timing.get("optical_flow", 0.0)), 1),
              "roi_filtering": round(float(timing.get("roi_filtering", 0.0)), 1),
              "zone_analysis": round(float(timing.get("zone_analysis", 0.0)), 1),
            }
        }

        # Only include risk_factors if non-empty
        risk_factors = full_frame.get('risk_factors', [])
        if risk_factors:
            doc["risk_factors"] = list(risk_factors)

        return doc

    RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def _resolve_min_risk_index(self) -> int:
        min_severity = str(getattr(self.settings, "alert_min_severity", "CRITICAL")).upper()
        if min_severity not in self.RISK_ORDER:
            min_severity = "CRITICAL"
        return self.RISK_ORDER.index(min_severity)

    def _reset_risk_persistence(self):
        self._risk_persist_level = None
        self._risk_persist_start = None
        self._risk_persist_count = 0

    def _update_risk_persistence(self, current_risk: str, current_time: float) -> float:
        """Update sustained-risk tracking and return how long the risk has persisted (seconds)."""
        if self._risk_persist_level != current_risk:
            self._risk_persist_level = current_risk
            self._risk_persist_start = current_time
            self._risk_persist_count = 1
        else:
            self._risk_persist_count += 1

        if self._risk_persist_start is None:
            return 0.0
        return current_time - self._risk_persist_start

    def _meets_persistence_gate(self, persist_seconds: float) -> bool:
        min_persist_seconds = float(getattr(self.settings, "alert_min_persist_seconds", 5.0))
        min_consecutive_frames = int(getattr(self.settings, "alert_min_consecutive_frames", 3))
        return persist_seconds >= min_persist_seconds and self._risk_persist_count >= min_consecutive_frames

    def _in_alert_cooldown(self, current_time: float) -> bool:
        return bool(self.last_alert_time) and (current_time - self.last_alert_time) < self.settings.alert_cooldown_seconds

    def _should_alert(self, current_risk_idx: int, last_risk_idx: int, min_risk_idx: int, current_time: float) -> bool:
        if current_risk_idx > last_risk_idx:
            # Risk escalated — always alert
            return True
        if current_risk_idx >= min_risk_idx and self.last_alert_time:
            # Sustained danger — re-alert after interval so operators aren't left in silence
            realert_interval = float(getattr(self.settings, "alert_realert_interval_seconds", 120.0))
            return (current_time - self.last_alert_time) >= realert_interval
        return False

    def _build_alert_data(
        self, result: Dict, frame_num: int, current_risk: str, current_risk_idx: int, last_risk_idx: int, current_time: float
    ) -> Optional[Dict]:
        if current_risk not in self.settings.email_alert_levels_list:
            logger.info(
                f"[RTSP Worker {self.stream_id}] Risk at {current_risk} "
                f"(score: {result['zones']['full_frame']['risk_score']:.1f}). "
                f"No alert (requires: {self.settings.email_alert_levels_list})."
            )
            return None

        is_realert = current_risk_idx <= last_risk_idx
        timestamp_obj = datetime.now(UTC)

        alert_data = {
            "alert_id": str(uuid.uuid4()),
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "fob_id": self.fob_type,
            "zone_id": self.zone_id,
            "zone_type": self.zone_type,
            "timestamp": timestamp_obj,
            "timestamp_iso": timestamp_obj.isoformat(),
            "severity": current_risk,
            "trigger_reason": ", ".join(result['zones']['full_frame']['risk_factors']),
            "risk_score": result['zones']['full_frame']['risk_score'],
            "people_count": result['people_count'],
            "density_avg": result['density_avg'],
            "density_level": result['zones']['full_frame']['density_level'],
            "motion_intensity": result['motion_intensity'],
            "status": "re-alert" if is_realert else "triggered",
            "frame_number": frame_num,
            "has_image": current_risk in self.settings.alert_image_risk_levels_list
        }

        self.last_alert_time = current_time
        self._last_alert_at_level = current_risk
        return alert_data

    def _check_alert_conditions(self, result: Dict, frame_num: int) -> Optional[Dict]:
        """
        Check if alert should be triggered based on risk level changes

        Args:
            result: Analytics result from CrowdAnalyzer
            frame_num: Frame number

        Returns:
            Alert document if alert should be triggered, None otherwise
        """
        current_time = time.time()
        current_risk = result['zones']['full_frame']['risk_level']

        # Validate risk level
        if current_risk not in self.RISK_ORDER:
            # Invalid risk level - update tracking and return
            self.last_risk_level = current_risk
            self._reset_risk_persistence()
            return None

        current_risk_idx = self.RISK_ORDER.index(current_risk)
        min_risk_idx = self._resolve_min_risk_index()

        # Below minimum severity - reset persistence tracking
        if current_risk_idx < min_risk_idx:
            self._reset_risk_persistence()
            self.last_risk_level = current_risk
            return None

        # Persistence gate: require sustained severity before alerting
        persist_seconds = self._update_risk_persistence(current_risk, current_time)
        if not self._meets_persistence_gate(persist_seconds):
            return None

        if self._in_alert_cooldown(current_time):
            return None

        # Determine if alert should fire: escalation OR sustained danger re-alert
        if self.last_risk_level not in self.RISK_ORDER:
            self.last_risk_level = current_risk
            return None
        last_risk_idx = self.RISK_ORDER.index(self.last_risk_level)

        alert_data = None
        if self._should_alert(current_risk_idx, last_risk_idx, min_risk_idx, current_time):
            alert_data = self._build_alert_data(
                result, frame_num, current_risk, current_risk_idx, last_risk_idx, current_time
            )

        # Update risk level tracking (even if no alert)
        self.last_risk_level = current_risk
        return alert_data

    def _check_image_rate_limit(self) -> tuple[bool, str]:
        """
        Check if we can save an image based on rate limits.

        Returns:
            (can_save, reason) - True if allowed, False with reason if blocked
        """
        now = datetime.now(UTC)
        current_hour = now.hour
        current_day = now.date()

        # Reset hourly counter if hour changed
        if current_hour != self.current_hour:
            self.images_this_hour = 0
            self.current_hour = current_hour

        # Reset daily counter if day changed
        if current_day != self.current_day:
            self.images_this_day = 0
            self.current_day = current_day

        # Check minimum interval between images
        if self.last_image_time:
            elapsed = (now - self.last_image_time).total_seconds()
            if elapsed < self.settings.image_min_interval_seconds:
                return False, f"min_interval ({elapsed:.0f}s < {self.settings.image_min_interval_seconds}s)"

        # Check hourly limit
        if self.images_this_hour >= self.settings.image_max_per_camera_per_hour:
            return False, f"hourly_limit ({self.images_this_hour}/{self.settings.image_max_per_camera_per_hour})"

        # Check daily limit
        if self.images_this_day >= self.settings.image_max_per_camera_per_day:
            return False, f"daily_limit ({self.images_this_day}/{self.settings.image_max_per_camera_per_day})"

        # Check total storage limit (if configured)
        if self.settings.image_max_storage_gb > 0:
            images_dir = Path(self.settings.images_dir)
            if images_dir.exists():
                total_size_bytes = sum(f.stat().st_size for f in images_dir.rglob("*.jpg"))
                total_size_gb = total_size_bytes / (1024 ** 3)
                if total_size_gb >= self.settings.image_max_storage_gb:
                    return False, f"storage_limit ({total_size_gb:.2f}GB >= {self.settings.image_max_storage_gb}GB)"

        return True, "ok"

    def _capture_alert_image(self, frame, result: Dict, alert_data: Dict):
        """
        Capture and save alert image (HIGH/CRITICAL only) with rate limiting.

        Args:
            frame: Video frame (numpy array)
            result: Analytics result from CrowdAnalyzer
            alert_data: Alert document
        """
        # Check rate limits first
        can_save, reason = self._check_image_rate_limit()
        if not can_save: 
            logger.info(f"[RTSP Worker {self.stream_id}] Image skipped: {reason}")
            # Still mark alert as not having image
            alert_data['has_image'] = False
            return

        try:
            timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            date_dir = datetime.now(UTC).strftime("%Y%m%d")

            # Path: images/{camera_id}/{YYYYMMDD}/{alert_id}_{timestamp}.jpg
            image_dir = Path(self.settings.images_dir) / self.camera_id / date_dir
            image_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{alert_data['alert_id']}_{timestamp_str}.jpg"
            file_path = image_dir / filename

            density_map = result.get("density_map")
            if density_map is None:
                # Performance mode may skip per-frame density-map generation.
                # Build it on-demand for alert image capture only.
                pet_points = result.get("pet_points")
                if pet_points is not None and len(pet_points) > 0:
                    from utils.point_to_density import points_to_density_map

                    confidences = np.ones((len(pet_points),), dtype=np.float32)
                    density_map = points_to_density_map(
                        points=pet_points,
                        confidences=confidences,
                        image_shape=frame.shape[:2],
                        sigma=self.settings.density_gaussian_sigma,
                        method="gaussian",
                    )
                else:
                    density_map = np.zeros(frame.shape[:2], dtype=np.float32)

            # Generate heatmap overlay using existing visualization
            heatmap_frame = visualize_heatmap_only(
                frame=frame,
                detections=result['detections'],
                density=density_map,  # parameter name is 'density'
                people_count=result['people_count'],
                risk_score=result['zones']['full_frame']['risk_score'],
                settings=self.settings
            )

            # Save image
            cv2.imwrite(
                str(file_path),
                heatmap_frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.settings.image_jpeg_quality]
            )

            # Get file stats
            file_stats = file_path.stat()

            # Queue metadata for MongoDB
            image_metadata = {
                "camera_id": self.camera_id,
                "alert_id": alert_data['alert_id'],
                "timestamp": alert_data['timestamp'],
                "frame_number": alert_data['frame_number'],
                "risk_level": alert_data['severity'],
                "file_path": str(file_path.relative_to(self.settings.images_dir)),
                "file_size_bytes": file_stats.st_size,
                "width": heatmap_frame.shape[1],
                "height": heatmap_frame.shape[0],
                "format": "jpg",
                "people_count": result['people_count'],
                "risk_score": result['zones']['full_frame']['risk_score'],
                "density_avg": result['density_avg']
            }

            if self.persistence_worker and self.async_loop:
                asyncio.run_coroutine_threadsafe(
                    self.persistence_worker.queue_image_metadata(image_metadata),
                    self.async_loop
                )

            # Update rate limiting counters
            self.last_image_time = datetime.now(UTC)
            self.images_this_hour += 1
            self.images_this_day += 1

            print(f"[RTSP Worker {self.stream_id}] Alert image captured: {file_path.name} "
                  f"(hour: {self.images_this_hour}/{self.settings.image_max_per_camera_per_hour}, "
                  f"day: {self.images_this_day}/{self.settings.image_max_per_camera_per_day})")
            
            logger.info(f"[RTSP Worker {self.stream_id}] Alert image captured: {file_path.name} "
                         f"(hour: {self.images_this_hour}/{self.settings.image_max_per_camera_per_hour}, "
                         f"day: {self.images_this_day}/{self.settings.image_max_per_camera_per_day})")
            

        except Exception:
            logger.exception(f"[RTSP Worker {self.stream_id}] Error capturing alert image")

    def _run(self):
        """Main worker loop - runs in dedicated thread"""
        logger.info(f"[RTSP Worker {self.stream_id}] Main loop started")

        # Initialize analyzer in worker thread
        try:
            self.state.update_status("initializing_analyzer")

            # Use BatchedInferenceService for production-grade GPU batching
            # This enables parallel processing of multiple camera frames
            # instead of serialized single-lock processing (SharedModelPool)
            logger.info(f"[RTSP Worker {self.stream_id}] Initializing analyzer with BatchedInferenceService (production mode)...")

            self.analyzer = CrowdAnalyzer(use_batched_inference=True)

            # Load camera calibration (area_m2 + ROI) from MongoDB
            self.camera_config = None
            self._camera_config_refresh_counter = 0
            try:
                if self.async_loop:
                    from services.camera_service import CameraService
                    future = asyncio.run_coroutine_threadsafe(
                        CameraService.get_camera_calibration(self.camera_id),
                        self.async_loop
                    )
                    self.camera_config = future.result(timeout=5.0)
                    if self.camera_config:
                        area = self.camera_config.get('area_m2', 'N/A')
                        has_roi = bool(self.camera_config.get('roi', {}).get('points'))
                        logger.info(f"[RTSP Worker {self.stream_id}] Camera config loaded: area_m2={area}, has_roi={has_roi}")
                    else:
                        logger.info(f"[RTSP Worker {self.stream_id}] No camera calibration in DB, using fallback")

            except Exception as e:
                print(f"[RTSP Worker {self.stream_id}] Failed to load camera config: {e}, using fallback")

            # Log GPU memory usage for this worker
            import torch
            if torch.cuda.is_available():
                gpu_allocated = torch.cuda.memory_allocated() / 1024**2
                gpu_reserved = torch.cuda.memory_reserved() / 1024**2
                logger.info(f"[RTSP Worker {self.stream_id}] GPU Memory - Allocated: {gpu_allocated:.2f} MB, Reserved: {gpu_reserved:.2f} MB")

            logger.info(f"[RTSP Worker {self.stream_id}] Analyzer initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize analyzer: {e}"
            logger.error(f"[RTSP Worker {self.stream_id}] {error_msg}")
            self.state.update_status("error", error_msg)
            self._running = False
            return

        # Main reconnection loop with circuit breaker
        reconnect_attempt = 0
        while not self._stop_event.is_set():
            # Fast-fail if circuit is OPEN (stream known to be down)
            if not self.circuit_breaker.is_available():
                delay = self.backoff.get_delay(reconnect_attempt)
                print(f"[RTSP Worker {self.stream_id}] Circuit OPEN, waiting {delay:.1f}s before retry")
                logger.warning(f"[RTSP Worker {self.stream_id}] Circuit OPEN, waiting {delay:.1f}s before retry")
                self.state.update_status("circuit_open")
                self._stop_event.wait(delay)
                reconnect_attempt += 1
                continue

            try:
                self._connect_and_process()
                # Success - record it and reset attempt counter
                self.circuit_breaker.record_success()
                reconnect_attempt = 0

            except Exception as e:
                error_msg = f"Connection error: {e}"
                logger.error(f"[RTSP Worker {self.stream_id}] {error_msg}")
                self.state.update_status("error", error_msg)

                # Record failure in circuit breaker
                self.circuit_breaker.record_failure()
                reconnect_attempt += 1

                # Check if we should give up completely
                attempts = self.state.increment_connection_attempts()
                if attempts >= self.reconnect_attempts:
                    logger.info(f"[RTSP Worker {self.stream_id}] Max reconnection attempts ({self.reconnect_attempts}) reached, giving up")
                    break

                # Exponential backoff with jitter
                delay = self.backoff.get_delay(reconnect_attempt)
                logger.info(f"[RTSP Worker {self.stream_id}] Reconnecting in {delay:.1f}s (attempt {attempts}/{self.reconnect_attempts}, circuit: {self.circuit_breaker.state.value})")
                self._stop_event.wait(delay)

        self.state.update_status("stopped")
        logger.info(f"[RTSP Worker {self.stream_id}] Main loop ended")

    MAX_CONSECUTIVE_FRAME_ERRORS = 50  # Roughly 2-3 seconds of bad frames before restart

    def _open_capture(self):
        """Configure OpenCV for RTSP and open the stream. Raises if the stream can't be opened."""
        # rtsp_transport;tcp: Force TCP to avoid UDP packet loss
        # analyzeduration;2000000: allow 2s to find keyframes/SPS/PPS headers
        # probesize;1000000: allow 1MB of data for format detection
        # fflags;+discardcorrupt: skip corrupt frames instead of failing
        # flags;low_delay: minimize latency after initial detection
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
            'rtsp_transport;tcp|analyzeduration;2000000|probesize;1000000|fflags;+discardcorrupt|flags;low_delay'
        )

        print(f"[RTSP Worker {self.stream_id}] Using optimized TCP transport options")
        logger.info(f"[RTSP Worker {self.stream_id}] Using optimized TCP transport options")
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        # Small buffer for low latency while allowing keyframe detection
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)

        if not cap.isOpened():
            error_msg = f"Failed to open RTSP stream: {self.rtsp_url}"
            logger.error(f"[RTSP Worker {self.stream_id}] {error_msg}")
            logger.error(f"[RTSP Worker {self.stream_id}] Troubleshooting:")
            logger.error(f"[RTSP Worker {self.stream_id}]   - Check URL is correct")
            logger.error(f"[RTSP Worker {self.stream_id}]   - Verify stream is publishing (docker logs rtsp-server)")
            logger.error(f"[RTSP Worker {self.stream_id}]   - Test with: ffplay {self.rtsp_url}")
            raise Exception(error_msg)

        stream_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[RTSP Worker {self.stream_id}] Connected: {width}x{height} @ {stream_fps}fps")

        return cap, stream_fps

    def _calculate_frame_skip(self, stream_fps: float) -> int:
        frame_skip = 1
        if self.target_fps and self.target_fps < stream_fps:
            frame_skip = max(1, int(stream_fps / self.target_fps))
            print(f"[RTSP Worker {self.stream_id}] Processing every {frame_skip} frame(s) to achieve ~{self.target_fps}fps")
        return frame_skip

    def _handle_bad_frame(self, consecutive_errors: int) -> int:
        """Track a failed frame read; raises once the stream looks unstable."""
        consecutive_errors += 1
        if consecutive_errors % 10 == 0:
            print(
                f"[RTSP Worker {self.stream_id}] WARNING: Partial stream failure "
                f"(bad frame {consecutive_errors}/{self.MAX_CONSECUTIVE_FRAME_ERRORS})"
            )

        if consecutive_errors >= self.MAX_CONSECUTIVE_FRAME_ERRORS:
            logger.error(f"[RTSP Worker {self.stream_id}] Too many consecutive bad frames. Reconnecting...")
            raise Exception("Stream unstable - forced reconnect")

        # Sleep briefly to avoid CPU spin loop during packet loss
        time.sleep(0.01)
        return consecutive_errors

    def _maybe_refresh_camera_config(self):
        """Periodically reload camera calibration from MongoDB (every 300 processed frames)."""
        self._camera_config_refresh_counter += 1
        if self._camera_config_refresh_counter < 300:
            return
        self._camera_config_refresh_counter = 0

        try:
            if self.async_loop:
                from services.camera_service import CameraService
                future = asyncio.run_coroutine_threadsafe(
                    CameraService.get_camera_calibration(self.camera_id),
                    self.async_loop
                )
                refreshed = future.result(timeout=3.0)
                if refreshed != self.camera_config:
                    self.camera_config = refreshed
                    print(f"[RTSP Worker {self.stream_id}] Camera config refreshed from DB")
        except Exception:
            pass  # Keep existing config on refresh failure

    def _run_analysis(self, frame, frame_timestamp: datetime) -> Dict:
        """Run crowd analysis on a frame and update worker state with the result."""
        result = self.analyzer.analyze_frame(
            frame,
            camera_id=self.camera_id,
            camera_config=self.camera_config,
            needs_density_map=self._needs_density_map,
            capture_timestamp=frame_timestamp.timestamp(),
        )
        if "timing_ms" in result and isinstance(result["timing_ms"], dict):
            self._timing_history.append(result["timing_ms"])

        # Inject timestamp for latency tracking (used by zone_analytics)
        result['timestamp'] = frame_timestamp.timestamp()  # Unix timestamp (float)

        self.state.increment_frame()
        self.state.update_analysis(result)
        return result

    def _broadcast_analytics(self, result: Dict, processed_frame_num: int, frame_timestamp: datetime):
        """Broadcast analytics over WebSocket (instant) and queue them for MongoDB (async)."""
        websocket_data = self._prepare_analytics_data(result, processed_frame_num, frame_timestamp)
        storage_data = self._prepare_storage_data(result, processed_frame_num, frame_timestamp)

        if self.websocket_manager and self.async_loop:
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.broadcast_analytics(self.camera_id, self.stream_id, websocket_data),
                self.async_loop
            )
            # Trigger zone-level aggregation and broadcast for SVG rendering
            asyncio.run_coroutine_threadsafe(
                broadcast_zone_update_for_camera(self.camera_id, self.websocket_manager),
                self.async_loop
            )
        else:
            if not self.websocket_manager:
                print(f"[RTSP Worker {self.stream_id}] WARNING: websocket_manager is None!")
            if not self.async_loop:
                print(f"[RTSP Worker {self.stream_id}] WARNING: async_loop is None!")

        if self.save_analytics and self.persistence_worker and self.async_loop:
            asyncio.run_coroutine_threadsafe(
                self.persistence_worker.queue_analytics(storage_data),
                self.async_loop
            )

    def _handle_alert(self, frame, result: Dict, processed_frame_num: int):
        """Check alert conditions and broadcast/persist/capture an image if one fires."""
        alert_data = self._check_alert_conditions(result, processed_frame_num)
        if not alert_data:
            return

        print(f"[RTSP Worker {self.stream_id}] ALERT TRIGGERED: {alert_data['severity']} - {alert_data['trigger_reason']}")

        # BROADCAST: Send JSON-serializable version (timestamp as ISO string)
        ws_alert_data = alert_data.copy()
        ws_alert_data["timestamp"] = alert_data["timestamp_iso"]

        if self.websocket_manager and self.async_loop:
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.broadcast_alert(self.camera_id, self.stream_id, ws_alert_data),
                self.async_loop
            )

        # PERSIST: Send datetime version (better for MongoDB querying)
        if self.persistence_worker and self.async_loop:
            asyncio.run_coroutine_threadsafe(
                self.persistence_worker.queue_alert(alert_data),
                self.async_loop
            )

        # Capture image for HIGH/CRITICAL alerts
        if alert_data['severity'] in self.settings.alert_image_risk_levels_list:
            self._capture_alert_image(frame, result, alert_data)

    def _save_legacy_analytics_if_needed(self, result: Dict, processed_frame_num: int):
        """Fallback JSONL analytics write, only used when MongoDB persistence isn't available."""
        if not (self.save_analytics and processed_frame_num % self.analytics_save_interval == 0):
            return
        if not self.persistence_worker:
            self._save_analytics(result, processed_frame_num)

    def _save_heatmap_if_needed(self, frame, result: Dict, processed_frame_num: int):
        if not (self.save_heatmaps and processed_frame_num % self.heatmap_save_interval == 0):
            return

        risk_score = 0.0
        if 'zones' in result and result['zones']:
            zone = next(iter(result['zones'].values()))
            risk_score = zone.get('risk_score', 0.0)

        density_map = result.get("density_map")
        if density_map is None:
            if processed_frame_num % 50 == 0:
                print(f"[RTSP Worker {self.stream_id}] density_map unavailable, skipping heatmap frame {processed_frame_num}")
            return

        if self.settings.heatmap_async and self.heatmap_queue is not None:
            # Non-blocking queue push for background processing
            try:
                heatmap_data = (
                    frame.copy(),  # Must copy since frame will be reused
                    result['detections'],
                    density_map.copy(),
                    processed_frame_num,
                    result['people_count'],
                    risk_score
                )
                self.heatmap_queue.put_nowait(heatmap_data)
            except queue.Full:
                # Queue full - skip this heatmap (not critical)
                if processed_frame_num % 50 == 0:
                    print(f"[RTSP Worker {self.stream_id}] Heatmap queue full, skipping frame {processed_frame_num}")
        else:
            # Synchronous fallback (if async disabled)
            self._save_heatmap(
                frame, result['detections'], density_map, processed_frame_num, result['people_count'], risk_score
            )

    def _update_frame_buffer(self, frame):
        try:
            self.frame_buffer.put_nowait(frame.copy())
        except queue.Full:
            # Remove old frame and add new one
            try:
                self.frame_buffer.get_nowait()
            except queue.Empty:
                pass
            self.frame_buffer.put_nowait(frame.copy())

    def _update_fps_and_progress(self, start_time: float, last_process_time: float, result: Dict) -> float:
        """Update the rolling FPS estimate and periodically log a progress report."""
        frame_time = time.time() - start_time
        self._frame_times.append(frame_time)

        if len(self._frame_times) >= 5:
            avg_frame_time = sum(self._frame_times) / len(self._frame_times)
            calculated_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
            self.state.update_fps(calculated_fps)

        now = time.time()
        if now - last_process_time >= 10.0:
            state = self.state.get_snapshot()
            print(f"[RTSP Worker {self.stream_id}] Progress Report:")
            print(f"  - Processed Frames: {state['frame_count']}")
            print(f"  - Processing FPS: {state['fps']:.1f}")
            print(f"  - People Count: {result['people_count']}")
            print(f"  - Density (avg/max): {result['density_avg']:.4f} / {result['density_max']:.4f}")
            print(f"  - Motion Intensity: {result['motion_intensity']:.2f}")
            return now

        return last_process_time

    def _process_frame(self, frame, frame_timestamp: datetime, last_process_time: float) -> float:
        """Run analysis on a single captured frame and fan the result out to all sinks."""
        start_time = time.time()

        self._maybe_refresh_camera_config()

        result = self._run_analysis(frame, frame_timestamp)
        processed_frame_num = self.state._frame_count

        self._broadcast_analytics(result, processed_frame_num, frame_timestamp)
        self._handle_alert(frame, result, processed_frame_num)
        self._save_legacy_analytics_if_needed(result, processed_frame_num)
        self._save_heatmap_if_needed(frame, result, processed_frame_num)
        self._update_frame_buffer(frame)

        return self._update_fps_and_progress(start_time, last_process_time, result)

    def _connect_and_process(self):
        """Connect to RTSP stream and process frames"""
        self.state.update_status("connecting")
        print(f"[RTSP Worker {self.stream_id}] Connecting to {self.rtsp_url}...")

        cap, stream_fps = self._open_capture()

        self.state.update_status("running")
        self.state.reset_connection_attempts()
        self.circuit_breaker.record_success()  # Mark successful connection

        frame_skip = self._calculate_frame_skip(stream_fps)

        frame_counter = 0
        consecutive_errors = 0
        last_process_time = time.time()

        try:
            # Frame capture and processing loop
            while not self._stop_event.is_set():
                ret, frame = cap.read()

                if not ret or frame is None:
                    consecutive_errors = self._handle_bad_frame(consecutive_errors)
                    continue

                # Reset error counter on successful frame
                consecutive_errors = 0
                frame_counter += 1

                # Capture timestamp immediately when frame is read
                frame_timestamp = datetime.now(UTC)

                # Skip frames if target FPS is set
                if frame_counter % frame_skip != 0:
                    continue

                try:
                    last_process_time = self._process_frame(frame, frame_timestamp, last_process_time)
                except TimeoutError:
                    # Inference timeout - log clearly so user knows results aren't reaching frontend
                    logger.warning(
                        f"[RTSP Worker {self.stream_id}] Inference timeout after "
                        f"{self.settings.inference_timeout_ms/1000:.0f}s, skipping frame {frame_counter}. "
                        f"If running on CPU, increase INFERENCE_TIMEOUT_MS (current: {self.settings.inference_timeout_ms}ms)"
                    )
                    continue
                except Exception:
                    logger.exception(f"[RTSP Worker {self.stream_id}] Frame processing error")
                    # Continue processing next frame
                    continue

        finally:
            cap.release()
            logger.info(f"[RTSP Worker {self.stream_id}] Released video capture")

    def _heatmap_saver_worker(self):
        """Background thread for saving heatmaps without blocking main loop"""
        while True:
            try:
                # Block until heatmap available (or thread stops)
                heatmap_data = self.heatmap_queue.get(timeout=1.0)

                if heatmap_data is None:  # Shutdown signal
                    break

                # Unpack data
                frame, detections, density, frame_num, people_count, risk_score = heatmap_data

                # Generate and save heatmap (this is slow, but now in background)
                self._save_heatmap(frame, detections, density, frame_num, people_count, risk_score)

            except queue.Empty:
                # Timeout - just continue
                continue
            except Exception:
                logger.exception(f"[RTSP Worker {self.stream_id}] Heatmap worker error")
                continue

        logger.info(f"[RTSP Worker {self.stream_id}] Heatmap saver thread stopped")

    def _save_analytics(self, result: Dict, frame_number: int):
        """Buffer analytics and write in batches for performance"""
        try:
            import json
            import time

            # Extract serializable data (no numpy arrays)
            analytics_data = {
                'stream_id': self.stream_id,
                'frame_number': frame_number,
                'timestamp': time.time(),
                'timestamp_iso': time.strftime('%Y-%m-%d %H:%M:%S'),
                'people_count': result.get('people_count', 0),
                'head_detections': result.get('head_detections', 0),
                'density_avg': float(result.get('density_avg', 0.0)),
                'density_max': float(result.get('density_max', 0.0)),
                'motion_intensity': float(result.get('motion_intensity', 0.0)),
                'zones': result.get('zones', {}),
                'detections': [
                    {
                        'bbox': det.get('bbox', [0, 0, 0, 0]),
                        'confidence': float(det.get('confidence', 0.0))
                    }
                    for det in result.get('detections', [])
                ]
            }

            # Add to buffer
            with self.analytics_lock:
                self.analytics_buffer.append(analytics_data)

                # Batch write when buffer is full
                if len(self.analytics_buffer) >= self.settings.analytics_batch_size:
                    # Write all buffered analytics at once
                    with open(self.analytics_file, 'a') as f:
                        for data in self.analytics_buffer:
                            f.write(json.dumps(data) + '\n')

                    if frame_number <= 30 or frame_number % 100 == 0:
                        print(f"[RTSP Worker {self.stream_id}] ✓ Batch wrote {len(self.analytics_buffer)} analytics entries")
                        logger.info(f"[RTSP Worker {self.stream_id}] Batch wrote {len(self.analytics_buffer)} analytics entries")

                    self.analytics_buffer.clear()

        except Exception:
            if frame_number <= 10:
                logger.exception(f"[RTSP Worker {self.stream_id}] ✗ Analytics buffer error")

    def _scale_detections(self, detections: List[Dict], scale: float) -> List[Dict]:
        scaled = []
        for det in detections:
            bbox = det.get('bbox', [0, 0, 0, 0])
            scaled_bbox = [int(coord * scale) for coord in bbox]
            scaled.append({'bbox': scaled_bbox, 'confidence': det.get('confidence', 0.0)})
        return scaled

    def _resize_for_heatmap(self, frame: np.ndarray, density_map: np.ndarray, detections: List[Dict], frame_number: int):
        """Resize frame/density/detections to the configured max width, preserving aspect ratio."""
        h, w = frame.shape[:2]
        max_width = self.settings.heatmap_max_width

        if w <= max_width:
            return frame, density_map, detections

        scale = max_width / w
        new_w = max_width
        new_h = int(h * scale)

        frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        density_resized = cv2.resize(density_map, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        detections_resized = self._scale_detections(detections, scale)

        if frame_number <= 3:
            print(f"[RTSP Worker {self.stream_id}] Resized heatmap from {w}x{h} to {new_w}x{new_h}")

        return frame_resized, density_resized, detections_resized

    def _write_heatmap_file(self, heatmap_frame: np.ndarray, frame_number: int) -> None:
        file_ext = self.settings.heatmap_format
        filename = f"{self.stream_id}_frame_{frame_number:06d}.{file_ext}"
        filepath = os.path.join(self.settings.heatmap_dir, filename)

        if frame_number <= 5:
            print(f"[RTSP Worker {self.stream_id}] Saving to: {filepath}")

        # JPEG is faster and smaller than PNG
        if file_ext == 'jpg':
            success = cv2.imwrite(filepath, heatmap_frame, [cv2.IMWRITE_JPEG_QUALITY, self.settings.heatmap_jpeg_quality])
        else:
            success = cv2.imwrite(filepath, heatmap_frame)

        if not success:
            logger.warning(f"[RTSP Worker {self.stream_id}] ⚠ Failed to save heatmap: {filepath}")
        elif frame_number <= 5 or frame_number % 100 == 0:
            file_size = os.path.getsize(filepath) / 1024  # KB
            print(f"[RTSP Worker {self.stream_id}] ✓ Saved heatmap: {filename} ({file_size:.1f} KB)")

    def _save_heatmap(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        density_map: np.ndarray,
        frame_number: int,
        people_count: int = 0,
        risk_score: float = 0.0
    ):
        """Save heatmap visualization for a frame (resized for performance)"""
        try:
            # Log first few attempts for debugging
            if frame_number <= 5:
                print(f"[RTSP Worker {self.stream_id}] Attempting to save heatmap for frame {frame_number}")

            frame_resized, density_resized, detections_resized = self._resize_for_heatmap(
                frame, density_map, detections, frame_number
            )

            # Generate heatmap overlay
            heatmap_frame = visualize_heatmap_only(
                frame=frame_resized,
                detections=detections_resized,
                density=density_resized,
                accumulated_heatmap=None,
                alpha=0.6,
                people_count=people_count,
                risk_score=risk_score,  # NEW - pass risk score for risk-based visualization
                settings=self.settings
            )

            self._write_heatmap_file(heatmap_frame, frame_number)

        except Exception:
            # Log all errors initially, then periodically
            if frame_number <= 10 or frame_number % 50 == 0:
                logger.exception(f"[RTSP Worker {self.stream_id}] ✗ Heatmap save error")
