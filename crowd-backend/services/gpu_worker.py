"""
Dedicated GPU inference worker.

Production PET-only version:
- Uses SharedModelPool model wrapper directly for each request.
- Preserves queueing, worker lifecycle, and stats contract.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional
from collections import deque
import logging
logger = logging.getLogger(__name__)
import numpy as np
from config.config import get_settings
from services.frame_queue import FrameQueue, InferenceRequest

logger = logging.getLogger(__name__)


class GPUWorker:
    """Dedicated inference worker running in a single thread."""

    def __init__(self, frame_queue: FrameQueue, settings=None):
        self._queue = frame_queue
        self._settings = settings or get_settings()

        self._batch_size = self._settings.batch_yolo_size
        self._batch_timeout_ms = self._settings.batch_timeout_ms

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        self._model_wrapper = None

        self._stats = {
            "batches_processed": 0,
            "frames_processed": 0,
            "total_inference_ms": 0.0,
            "avg_batch_size": 0.0,
            "avg_inference_ms": 0.0,
            "max_inference_ms": 0.0,
            "errors": 0,
        }
        self._stats_lock = threading.Lock()
        self._model_samples_ms: deque = deque(maxlen=5000)
        self._end_to_end_samples_ms: deque = deque(maxlen=5000)

    def start(self) -> None:
        if self._running:
            logger.info("[GPUWorker] Already running")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, name="GPUWorker", daemon=True)
        self._thread.start()
        logger.info("[GPUWorker] Started")

    def stop(self, timeout: float = 5.0) -> None:
        if not self._running:
            return

        logger.info("[GPUWorker] Stopping...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("[GPUWorker] WARNING: Thread did not stop within timeout")

        self._running = False
        logger.info("[GPUWorker] Stopped")

    def _run(self) -> None:
        logger.info("[GPUWorker] Processing loop started")

        try:
            self._init_models()
            self._warmup()
        except Exception:
            logger.exception("[GPUWorker] FATAL: Model initialization failed")
            self._running = False
            return

        while not self._stop_event.is_set():
            try:
                batch = self._queue.get_batch(
                    max_batch=self._batch_size,
                    timeout_ms=self._batch_timeout_ms,
                )
                if not batch:
                    time.sleep(0.001)
                    continue

                self._process_batch(batch)
            except Exception:
                logger.exception("[GPUWorker] Error in processing loop")
                with self._stats_lock:
                    self._stats["errors"] += 1
                time.sleep(0.1)

        logger.info("[GPUWorker] Processing loop ended")

    def _init_models(self) -> None:
        from models.model_wrapper import SharedModelPool

        pool = SharedModelPool.get_instance()
        if not pool.is_initialized:
            raise RuntimeError("SharedModelPool not initialized")

        self._model_wrapper = pool._model
        logger.info(f"[GPUWorker] Models initialized on {self._model_wrapper.device}")

    def _warmup(self) -> None:
        logger.info("[GPUWorker] Warming up inference path...")
        dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
        try:
            _ = self._model_wrapper.predict(dummy)
            print("[GPUWorker] Warmup complete")
        except Exception:
            logger.exception("[GPUWorker] Warmup failed (non-fatal)")

    def _process_batch(self, batch: List[InferenceRequest]) -> None:
        start_time = time.perf_counter()
        batch_size = len(batch)

        # Collect per-request parameters for batched inference
        frames = [req.frame for req in batch]
        density_regimes = [req.density_regime for req in batch]
        density_maps = [req.needs_density_map for req in batch]
        skip_pets = [req.skip_pet for req in batch]

        batch_model_start = time.perf_counter()
        try:
            results = self._model_wrapper.predict_batch(
                frames,
                density_regimes=density_regimes,
                generate_density_maps=density_maps,
                skip_pets=skip_pets,
            )
        except Exception as e:
            # Whole-batch failure (e.g. YOLO GPU error): mark every request as errored
            for req in batch:
                req.set_error(e)
            with self._stats_lock:
                self._stats["errors"] += batch_size
            inference_ms = (time.perf_counter() - start_time) * 1000
            self._update_stats(batch_size, inference_ms)
            return

        batch_model_ms = (time.perf_counter() - batch_model_start) * 1000
        per_frame_ms = batch_model_ms / batch_size  # amortised share

        # Distribute results with per-request timing
        completion_time = time.perf_counter()
        for req, result in zip(batch, results):
            end_to_end_ms = (completion_time - req.enqueue_time) * 1000
            result["inference_latency_ms"] = end_to_end_ms
            result["model_inference_ms"] = per_frame_ms
            req.set_result(result)
            self._model_samples_ms.append(per_frame_ms)
            self._end_to_end_samples_ms.append(end_to_end_ms)

        inference_ms = (time.perf_counter() - start_time) * 1000
        self._update_stats(batch_size, inference_ms)

    def _update_stats(self, batch_size: int, inference_ms: float) -> None:
        with self._stats_lock:
            self._stats["batches_processed"] += 1
            self._stats["frames_processed"] += batch_size
            self._stats["total_inference_ms"] += inference_ms
            self._stats["max_inference_ms"] = max(self._stats["max_inference_ms"], inference_ms)

            total_batches = self._stats["batches_processed"]
            self._stats["avg_batch_size"] = self._stats["frames_processed"] / total_batches
            self._stats["avg_inference_ms"] = self._stats["total_inference_ms"] / total_batches

    @property
    def stats(self) -> Dict:
        with self._stats_lock:
            stats = self._stats.copy()
            if self._model_samples_ms:
                model_array = np.array(self._model_samples_ms, dtype=np.float64)
                stats["model_p50_ms"] = float(np.percentile(model_array, 50))
                stats["model_p95_ms"] = float(np.percentile(model_array, 95))
            else:
                stats["model_p50_ms"] = 0.0
                stats["model_p95_ms"] = 0.0

            if self._end_to_end_samples_ms:
                e2e_array = np.array(self._end_to_end_samples_ms, dtype=np.float64)
                stats["end_to_end_p50_ms"] = float(np.percentile(e2e_array, 50))
                stats["end_to_end_p95_ms"] = float(np.percentile(e2e_array, 95))
            else:
                stats["end_to_end_p50_ms"] = 0.0
                stats["end_to_end_p95_ms"] = 0.0

            return stats

    @property
    def is_running(self) -> bool:
        return self._running
