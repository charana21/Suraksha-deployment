"""
Thread-safe frame queue for batched GPU inference.

This queue collects frames from multiple RTSP workers and provides
batch retrieval for efficient GPU processing.
"""
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import List, Dict, Optional, Any, Tuple
import uuid
import numpy as np

@dataclass
class InferenceRequest:
    """Represents a single frame inference request."""
    request_id: str
    camera_id: str
    frame: np.ndarray
    original_size: Tuple[int, int]  # (height, width) for coordinate mapping
    timestamp: datetime
    enqueue_time: float
    density_regime: Optional[str] = None
    needs_density_map: bool = True
    skip_pet: bool = False  # If True, skip PET inference — return YOLO-only result
    result_callback: Any = None  # Callable or threading.Event for result delivery
    result: Optional[Dict] = field(default=None, repr=False)
    error: Optional[Exception] = field(default=None, repr=False)
    completed: threading.Event = field(default_factory=threading.Event, repr=False)

    @classmethod
    def create(
        cls,
        camera_id: str,
        frame: np.ndarray,
        original_size: Tuple[int, int],
        callback: Any = None,
        density_regime: Optional[str] = None,
        needs_density_map: bool = True,
        skip_pet: bool = False,
    ) -> 'InferenceRequest':
        """Factory method to create a new request."""
        return cls(
            request_id=str(uuid.uuid4()),
            camera_id=camera_id,
            frame=frame,
            original_size=original_size,
            density_regime=density_regime,
            needs_density_map=needs_density_map,
            skip_pet=skip_pet,
            timestamp=datetime.now(UTC),
            enqueue_time=time.perf_counter(),
            result_callback=callback
        )

    def set_result(self, result: Dict) -> None:
        """Set the inference result and signal completion."""
        self.result = result
        self.completed.set()
        if callable(self.result_callback):
            try:
                self.result_callback(result)
            except Exception:
                pass

    def set_error(self, error: Exception) -> None:
        """Set an error and signal completion."""
        self.error = error
        self.completed.set()
        if callable(self.result_callback):
            try:
                self.result_callback(None, error)
            except Exception:
                pass

    def wait(self, timeout: float = None) -> Optional[Dict]:
        """
        Wait for the result with optional timeout.

        Returns:
            The inference result dict, or None if timeout/error.

        Raises:
            TimeoutError: If timeout exceeded
            Exception: If inference failed with an error
        """
        if not self.completed.wait(timeout=timeout):
            raise TimeoutError(f"Inference request {self.request_id} timed out after {timeout}s")
        if self.error:
            raise self.error
        return self.result


class FrameQueue:
    """
    Thread-safe bounded queue for inference requests.

    Key Features:
    - Bounded size prevents memory exhaustion
    - Per-camera limiting ensures fairness
    - Batch retrieval with timeout for latency control
    - Statistics tracking for monitoring

    Usage:
        queue = FrameQueue(max_size=100, per_camera_limit=3)

        # From RTSP worker threads:
        request = InferenceRequest.create(camera_id, frame)
        queue.put(request)
        result = request.wait(timeout=0.5)

        # From GPU worker thread:
        batch = queue.get_batch(max_batch=8, timeout_ms=100)
        # process batch...
        for req in batch:
            req.set_result(result)
    """

    def __init__(
        self,
        max_size: int = 100,
        per_camera_limit: int = 3,
        drop_oldest: bool = True
    ):
        """
        Initialize the frame queue.

        Args:
            max_size: Maximum total frames in queue
            per_camera_limit: Max frames per camera (prevents one slow camera from blocking)
            drop_oldest: If True, drop oldest frame when limit exceeded; else drop newest
        """
        self._max_size = max_size
        self._per_camera_limit = per_camera_limit
        self._drop_oldest = drop_oldest

        self._queue: deque = deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._camera_counts: Dict[str, int] = defaultdict(int)

        # Statistics
        self._stats = {
            "enqueued": 0,
            "dropped": 0,
            "processed": 0,
            "total_wait_ms": 0.0,
            "max_wait_ms": 0.0,
        }
        self._wait_samples_ms: deque = deque(maxlen=5000)

    def put(self, request: InferenceRequest) -> bool:
        """
        Add a request to the queue.

        Args:
            request: The inference request to enqueue

        Returns:
            True if enqueued, False if dropped

        Note:
            If per-camera limit is exceeded, oldest request from the same camera
            is removed (and marked as error) before adding the new one.
        """
        with self._lock:
            camera_id = request.camera_id

            # Check per-camera limit
            if self._camera_counts[camera_id] >= self._per_camera_limit:
                dropped = self._remove_oldest_for_camera(camera_id)
                if dropped:
                    dropped.set_error(RuntimeError("Dropped: per-camera queue limit exceeded"))
                    self._stats["dropped"] += 1

            # Check total queue limit
            if len(self._queue) >= self._max_size:
                if self._drop_oldest:
                    dropped = self._queue.popleft()
                    self._camera_counts[dropped.camera_id] -= 1
                    dropped.set_error(RuntimeError("Dropped: total queue limit exceeded"))
                else:
                    request.set_error(RuntimeError("Dropped: queue full"))
                    return False
                self._stats["dropped"] += 1

            # Add to queue
            self._queue.append(request)
            self._camera_counts[camera_id] += 1
            self._stats["enqueued"] += 1

            # Signal waiting consumers
            self._not_empty.notify()

            return True

    def get_batch(self, max_batch: int, timeout_ms: float) -> List[InferenceRequest]:
        """
        Get up to max_batch requests, waiting at most timeout_ms.

        Batching Strategy:
        1. Wait for at least 1 request (with timeout)
        2. Greedily collect up to max_batch without additional waiting
        3. Return immediately when batch is full or queue is empty

        Args:
            max_batch: Maximum number of requests to return
            timeout_ms: Maximum milliseconds to wait for first request

        Returns:
            List of InferenceRequest objects (may be empty if timeout)
        """
        batch = []
        deadline = time.perf_counter() + (timeout_ms / 1000.0)

        with self._lock:
            # Wait for at least one request
            while len(self._queue) == 0:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return batch  # Timeout, return empty
                self._not_empty.wait(timeout=remaining)

            # Greedily collect batch (no additional waiting)
            while len(batch) < max_batch and len(self._queue) > 0:
                req = self._queue.popleft()
                self._camera_counts[req.camera_id] -= 1
                batch.append(req)

            self._stats["processed"] += len(batch)

            # Track wait time statistics
            if batch:
                now = time.perf_counter()
                for req in batch:
                    wait_ms = (now - req.enqueue_time) * 1000
                    self._stats["total_wait_ms"] += wait_ms
                    self._stats["max_wait_ms"] = max(self._stats["max_wait_ms"], wait_ms)
                    self._wait_samples_ms.append(wait_ms)

        return batch

    def _remove_oldest_for_camera(self, camera_id: str) -> Optional[InferenceRequest]:
        """Remove and return the oldest request from a specific camera."""
        # Must be called with lock held
        for i, req in enumerate(self._queue):
            if req.camera_id == camera_id:
                del self._queue[i]
                self._camera_counts[camera_id] -= 1
                return req
        return None

    def size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._queue)

    def clear(self) -> int:
        """
        Clear all pending requests.

        Returns:
            Number of requests cleared
        """
        with self._lock:
            count = len(self._queue)
            for req in self._queue:
                req.set_error(RuntimeError("Queue cleared"))
            self._queue.clear()
            self._camera_counts.clear()
            return count

    @property
    def stats(self) -> Dict:
        """Get queue statistics."""
        with self._lock:
            stats = self._stats.copy()
            stats["current_size"] = len(self._queue)
            stats["cameras_active"] = len([c for c, count in self._camera_counts.items() if count > 0])
            if stats["processed"] > 0:
                stats["avg_wait_ms"] = stats["total_wait_ms"] / stats["processed"]
            else:
                stats["avg_wait_ms"] = 0.0
            if self._wait_samples_ms:
                wait_array = np.array(self._wait_samples_ms, dtype=np.float64)
                stats["wait_p50_ms"] = float(np.percentile(wait_array, 50))
                stats["wait_p95_ms"] = float(np.percentile(wait_array, 95))
            else:
                stats["wait_p50_ms"] = 0.0
                stats["wait_p95_ms"] = 0.0
            return stats

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._stats = {
                "enqueued": 0,
                "dropped": 0,
                "processed": 0,
                "total_wait_ms": 0.0,
                "max_wait_ms": 0.0,
            }
            self._wait_samples_ms.clear()
