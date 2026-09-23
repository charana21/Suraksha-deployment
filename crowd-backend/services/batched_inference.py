"""
Batched Inference Service - Public API for GPU inference batching.

This service provides a drop-in replacement for direct SharedModelPool.predict() calls,
enabling centralized GPU batching for production-grade performance.

Usage:
    # At app startup (api/main.py):
    service = BatchedInferenceService.get_instance()
    service.start()

    # In RTSP workers (sync context):
    result = service.predict_sync(
        camera_id="cam1",
        frame=frame,
        original_size=frame.shape[:2],
        timeout_ms=500,
        density_regime="SPARSE"
    )

    # The result has the same format as SharedModelPool.predict()
"""
import threading
from typing import Dict, Optional
import numpy as np
from config.config import get_settings, Settings
from services.frame_queue import FrameQueue, InferenceRequest
from services.gpu_worker import GPUWorker
import logging
logger = logging.getLogger(__name__)

class BatchedInferenceService:
    """
    Public interface for batched GPU inference.

    This singleton service:
    1. Manages the FrameQueue and GPUWorker
    2. Provides sync and async inference APIs
    3. Handles graceful startup/shutdown
    4. Exposes statistics for monitoring

    Thread Safety:
    - All public methods are thread-safe
    - Designed for use from multiple RTSP worker threads
    """

    _instance: Optional['BatchedInferenceService'] = None
    _lock = threading.Lock()

    def __init__(self, settings: Settings = None):
        """
        Initialize the service.

        Args:
            settings: Optional settings (uses get_settings() if None)
        """
        if BatchedInferenceService._instance is not None:
            raise RuntimeError("Use BatchedInferenceService.get_instance() instead")

        self._settings = settings or get_settings()

        # Create frame queue
        self._frame_queue = FrameQueue(
            max_size=self._settings.inference_queue_size,
            per_camera_limit=self._settings.inference_per_camera_limit
        )

        # Create GPU worker
        self._gpu_worker = GPUWorker(
            frame_queue=self._frame_queue,
            settings=self._settings
        )

        self._started = False
        logger.info("[BatchedInferenceService] Initialized")

    @classmethod
    def get_instance(cls, settings: Settings = None) -> 'BatchedInferenceService':
        """
        Get the singleton instance (thread-safe).

        Args:
            settings: Optional settings for first initialization

        Returns:
            The BatchedInferenceService singleton
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing or reinitialization)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
                cls._instance = None

    def start(self) -> None:
        """
        Start the batched inference service.

        This starts the GPU worker thread. Call this once at app startup
        after SharedModelPool is initialized.
        """
        if self._started:
            logger.info("[BatchedInferenceService] Already started")
            return

        logger.info("[BatchedInferenceService] Starting...")
        self._gpu_worker.start()
        self._started = True
        logger.info("[BatchedInferenceService] Started")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the batched inference service.

        Args:
            timeout: Max seconds to wait for worker shutdown
        """
        if not self._started:
            return

        logger.info("[BatchedInferenceService] Stopping...")

        # Clear pending requests
        cleared = self._frame_queue.clear()
        if cleared > 0:
            logger.info(f"[BatchedInferenceService] Cleared {cleared} pending requests")

        # Stop GPU worker
        self._gpu_worker.stop(timeout=timeout)

        self._started = False
        logger.info("[BatchedInferenceService] Stopped")

    def predict_sync(
        self,
        camera_id: str,
        frame: np.ndarray,
        original_size: tuple,
        timeout_ms: float = None,
        density_regime: Optional[str] = None,
        needs_density_map: bool = True,
        skip_pet: bool = False,
    ) -> Dict:
        """
        Synchronous prediction (blocking).

        This is the primary API for RTSP workers running in sync threads.
        Submits the frame to the queue and waits for the result.

        Args:
            camera_id: Camera identifier (for queue fairness)
            frame: BGR image (numpy array, possibly resized)
            original_size: (height, width) of original frame for coordinate mapping
            timeout_ms: Max wait time in milliseconds (default from settings)
            density_regime: Optional prior regime hint ("SPARSE"/"LOW"/"MEDIUM"/"HIGH")

        Returns:
            Dict with keys: head_count, density_count, final_count, density_map, detections

        Raises:
            TimeoutError: If inference doesn't complete within timeout
            RuntimeError: If inference fails or service not started
        """
        if not self._started:
            raise RuntimeError("BatchedInferenceService not started. Call start() first.")

        timeout_ms = timeout_ms or self._settings.inference_timeout_ms

        # Create request
        request = InferenceRequest.create(
            camera_id=camera_id,
            frame=frame,
            original_size=original_size,
            density_regime=density_regime,
            needs_density_map=needs_density_map,
            skip_pet=skip_pet,
        )

        # Submit to queue
        if not self._frame_queue.put(request):
            raise RuntimeError("Failed to enqueue inference request")

        # Wait for result
        try:
            result = request.wait(timeout=timeout_ms / 1000.0)
            return result
        except TimeoutError:
            raise TimeoutError(f"Inference timeout after {timeout_ms}ms for camera {camera_id}")

    def submit(
        self,
        camera_id: str,
        frame: np.ndarray,
        original_size: tuple,
        density_regime: Optional[str] = None,
        needs_density_map: bool = True,
        skip_pet: bool = False,
    ) -> InferenceRequest:
        """
        Submit a frame for inference (non-blocking).

        Returns immediately with an InferenceRequest that can be awaited later.

        Args:
            camera_id: Camera identifier
            frame: BGR image
            original_size: (height, width) of original frame

        Returns:
            InferenceRequest object - call request.wait() to get result

        Raises:
            RuntimeError: If service not started
        """
        if not self._started:
            raise RuntimeError("BatchedInferenceService not started. Call start() first.")

        request = InferenceRequest.create(
            camera_id=camera_id,
            frame=frame,
            original_size=original_size,
            density_regime=density_regime,
            needs_density_map=needs_density_map,
            skip_pet=skip_pet,
        )

        if not self._frame_queue.put(request):
            request.set_error(RuntimeError("Failed to enqueue"))

        return request

    @property
    def is_started(self) -> bool:
        """Check if service is started."""
        return self._started

    @property
    def stats(self) -> Dict:
        """
        Get comprehensive statistics.

        Returns dict with:
        - queue_*: Queue statistics (enqueued, dropped, processed, etc.)
        - worker_*: GPU worker statistics (batches, inference times, etc.)
        """
        queue_stats = self._frame_queue.stats
        worker_stats = self._gpu_worker.stats

        return {
            # Queue stats
            "queue_size": queue_stats.get("current_size", 0),
            "queue_enqueued": queue_stats.get("enqueued", 0),
            "queue_dropped": queue_stats.get("dropped", 0),
            "queue_processed": queue_stats.get("processed", 0),
            "queue_avg_wait_ms": queue_stats.get("avg_wait_ms", 0),
            "queue_max_wait_ms": queue_stats.get("max_wait_ms", 0),
            "queue_wait_p50_ms": queue_stats.get("wait_p50_ms", 0),
            "queue_wait_p95_ms": queue_stats.get("wait_p95_ms", 0),
            "queue_cameras_active": queue_stats.get("cameras_active", 0),

            # Worker stats
            "worker_batches": worker_stats.get("batches_processed", 0),
            "worker_frames": worker_stats.get("frames_processed", 0),
            "worker_avg_batch_size": worker_stats.get("avg_batch_size", 0),
            "worker_avg_inference_ms": worker_stats.get("avg_inference_ms", 0),
            "worker_max_inference_ms": worker_stats.get("max_inference_ms", 0),
            "worker_model_p50_ms": worker_stats.get("model_p50_ms", 0),
            "worker_model_p95_ms": worker_stats.get("model_p95_ms", 0),
            "worker_e2e_p50_ms": worker_stats.get("end_to_end_p50_ms", 0),
            "worker_e2e_p95_ms": worker_stats.get("end_to_end_p95_ms", 0),
            "worker_errors": worker_stats.get("errors", 0),
        }

    def get_status(self) -> Dict:
        """
        Get service status for health checks.

        Returns dict with:
        - started: bool
        - worker_running: bool
        - queue_size: int
        - healthy: bool
        """
        stats = self.stats

        return {
            "started": self._started,
            "worker_running": self._gpu_worker.is_running,
            "queue_size": stats["queue_size"],
            "frames_processed": stats["worker_frames"],
            "errors": stats["worker_errors"],
            "healthy": self._started and self._gpu_worker.is_running
        }
