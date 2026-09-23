"""
RTSP Stream Manager - Coordinates multiple RTSP streams in parallel

Manages lifecycle of multiple RTSP workers:
- Start/stop individual streams
- Track status of all streams
- Graceful shutdown of all streams
- Thread-safe access to stream states
"""
import threading
from typing import Dict, List, Optional
from datetime import UTC, datetime
import uuid
import logging
from services.rtsp_worker import RTSPWorker
logger = logging.getLogger(__name__)

class RTSPManager:
    """
    Thread-safe manager for multiple parallel RTSP streams

    Why this architecture:
    1. Each RTSP stream = independent thread (RTSPWorker)
    2. Manager = coordination layer, not processing layer
    3. Failures in one stream don't affect others
    4. Streams can be started/stopped independently
    5. Global state tracking for monitoring
    """

    def __init__(self):
        """Initialize RTSP manager"""
        self._streams: Dict[str, RTSPWorker] = {}
        self._lock = threading.Lock()
        self._stream_metadata: Dict[str, Dict] = {}

        # NEW: Shared services (set via set_services method)
        self.persistence_worker = None
        self.websocket_manager = None
        self.async_loop = None

        logger.info("[RTSP Manager] Initialized")

    def set_services(self, persistence_worker, websocket_manager, async_loop):
        """
        Set shared services for all RTSP workers

        Args:
            persistence_worker: PersistenceWorker instance
            websocket_manager: ConnectionManager instance
            async_loop: asyncio event loop reference
        """
        self.persistence_worker = persistence_worker
        self.websocket_manager = websocket_manager
        self.async_loop = async_loop
        logger.info("[RTSP Manager] Shared services configured")

    def start_stream(
        self,
        rtsp_url: str,
        camera_id: str,  # NEW: Required camera_id parameter
        stream_id: Optional[str] = None,
        target_fps: Optional[int] = None,
        name: Optional[str] = None,
        location: Optional[str] = None,  # NEW: Camera location
        **kwargs # Allow passing extra metadata like fob_type
    ) -> str:
        """
        Start a new RTSP stream

        Args:
            rtsp_url: RTSP stream URL
            camera_id: Camera ID (from cameras collection)
            stream_id: Optional custom stream ID (auto-generated if None)
            target_fps: Target processing FPS (None = process every frame)
            name: Optional human-readable name for the stream
            location: Optional camera location

        Returns:
            stream_id: Unique identifier for this stream

        Raises:
            ValueError: If stream_id already exists
        """
        with self._lock:
            # Generate stream ID if not provided
            if stream_id is None:
                stream_id = str(uuid.uuid4())

            # Check if stream already exists
            if stream_id in self._streams:
                raise ValueError(f"Stream {stream_id} already exists")

            # Create and start worker
            worker = RTSPWorker(
                stream_id=stream_id,
                rtsp_url=rtsp_url,
                camera_id=camera_id,  # NEW
                camera_name=name,     # NEW
                fob_type=kwargs.get('fob_type'), # NEW
                zone_id=kwargs.get('zone_id'),
                zone_type=kwargs.get('zone_type'),
                location=location,    # NEW: Pass location to worker
                target_fps=target_fps,
                persistence_worker=self.persistence_worker,  # NEW
                websocket_manager=self.websocket_manager,    # NEW
                async_loop=self.async_loop                   # NEW
            )

            # Store metadata
            self._stream_metadata[stream_id] = {
                'stream_id': stream_id,
                'camera_id': camera_id,  # NEW
                'rtsp_url': rtsp_url,
                'target_fps': target_fps,
                'name': name or f"Stream {stream_id[:8]}",
                'location': location,  # NEW
                'started_at': datetime.now(UTC).isoformat(),
                'stopped_at': None
            }

            # Start worker
            success = worker.start()

            if not success:
                raise Exception(f"Failed to start worker for stream {stream_id}")

            self._streams[stream_id] = worker

            logger.info(f"[RTSP Manager] Started stream {stream_id}: {rtsp_url}")
            return stream_id

    def stop_stream(self, stream_id: str) -> bool:
        """
        Stop a specific RTSP stream

        Args:
            stream_id: Stream identifier

        Returns:
            bool: True if stream was stopped, False if not found
        """
        with self._lock:
            worker = self._streams.get(stream_id)

            if worker is None:
                logger.info(f"[RTSP Manager] Stream {stream_id} not found")
                return False

            # Stop worker
            worker.stop()

            # Update metadata
            if stream_id in self._stream_metadata:
                self._stream_metadata[stream_id]['stopped_at'] = datetime.now(UTC).isoformat()

            # Remove from active streams
            del self._streams[stream_id]

            logger.info(f"[RTSP Manager] Stopped stream {stream_id}")
            return True

    def stop_all_streams(self):
        """Stop all active RTSP streams"""
        logger.info("[RTSP Manager] Stopping all streams...")

        with self._lock:
            stream_ids = list(self._streams.keys())

        for stream_id in stream_ids:
            self.stop_stream(stream_id)

        logger.info(f"[RTSP Manager] Stopped {len(stream_ids)} stream(s)")

    def get_stream_state(self, stream_id: str) -> Optional[Dict]:
        """
        Get state of a specific stream

        Args:
            stream_id: Stream identifier

        Returns:
            Dict with stream state, or None if not found
        """
        with self._lock:
            worker = self._streams.get(stream_id)
            metadata = self._stream_metadata.get(stream_id)

            if worker is None:
                return None

            # Get worker state
            state = worker.get_state()

            # Add metadata
            if metadata:
                state['metadata'] = metadata

            return state

    def get_all_streams(self) -> List[Dict]:
        """
        Get state of all streams

        Returns:
            List of stream states
        """
        with self._lock:
            stream_ids = list(self._streams.keys())

        return [self.get_stream_state(sid) for sid in stream_ids if self.get_stream_state(sid)]

    def get_stream_count(self) -> Dict[str, int]:
        """
        Get count of streams by status

        Returns:
            Dict with counts by status
        """
        states = self.get_all_streams()

        counts = {
            'total': len(states),
            'running': 0,
            'error': 0,
            'connecting': 0,
            'stopped': 0
        }

        for state in states:
            status = state.get('status', 'unknown')
            if status == 'running':
                counts['running'] += 1
            elif status == 'error':
                counts['error'] += 1
            elif status == 'connecting':
                counts['connecting'] += 1
            elif status == 'stopped':
                counts['stopped'] += 1

        return counts

    def stream_exists(self, stream_id: str) -> bool:
        """Check if stream exists"""
        with self._lock:
            return stream_id in self._streams

    def cleanup_stopped_streams(self):
        """Remove stopped streams from tracking"""
        with self._lock:
            stopped_streams = [
                sid for sid, worker in self._streams.items()
                if not worker.is_running()
            ]

            for stream_id in stopped_streams:
                logger.info(f"[RTSP Manager] Cleaning up stopped stream {stream_id}")
                del self._streams[stream_id]

        return len(stopped_streams)

    def shutdown(self):
        """Graceful shutdown of all streams"""
        logger.info("[RTSP Manager] Shutting down...")
        self.stop_all_streams()
        logger.info("[RTSP Manager] Shutdown complete")


# Global RTSP manager instance
_rtsp_manager: Optional[RTSPManager] = None
_manager_lock = threading.Lock()


def get_rtsp_manager() -> RTSPManager:
    """Get or create global RTSP manager instance (singleton pattern)"""
    global _rtsp_manager

    if _rtsp_manager is None:
        with _manager_lock:
            # Double-check locking
            if _rtsp_manager is None:
                _rtsp_manager = RTSPManager()

    return _rtsp_manager
