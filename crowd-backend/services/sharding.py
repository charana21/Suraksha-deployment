"""
Deterministic Camera Sharding and Pod Ownership Service.

Provides a single source of truth for:
- Deterministic camera-to-shard mapping using CRC32 hashing
- Pod shard index auto-detection (via environment variable or StatefulSet hostname)
- Ownership checks for RTSP workers, AI processing, and live stream routing
- Owning pod host resolution for internal cross-pod stream forwarding
"""

import logging
import os
import zlib
from typing import Optional

logger = logging.getLogger(__name__)


def get_shard_count() -> int:
    """Return the total number of camera shards configured for this deployment."""
    from config.config import get_settings
    settings = get_settings()

    env_val = os.getenv("CAMERA_SHARD_COUNT")
    if env_val is not None:
        try:
            return max(1, int(env_val))
        except ValueError:
            logger.warning(f"[Sharding] Invalid CAMERA_SHARD_COUNT '{env_val}', falling back to settings")

    return max(1, int(getattr(settings, "camera_shard_count", 1)))


def get_current_shard_index() -> int:
    """Determine the current pod's shard index.

    Resolution order:
    1. Explicit CAMERA_SHARD_INDEX environment variable.
    2. StatefulSet hostname ordinal (e.g. 'crowdvision-backend-0' -> 0).
    3. settings.camera_shard_index from configuration file.
    4. Default fallback: 0.
    """
    # 1. Explicit environment variable
    env_val = os.getenv("CAMERA_SHARD_INDEX")
    if env_val is not None:
        try:
            return int(env_val)
        except ValueError:
            logger.warning(f"[Sharding] Invalid CAMERA_SHARD_INDEX '{env_val}', checking hostname")

    # 2. StatefulSet hostname / POD_NAME ordinal
    for var in ["POD_NAME", "HOSTNAME"]:
        hostname = os.getenv(var, "")
        if "-" in hostname:
            parts = hostname.rsplit("-", 1)
            if parts[-1].isdigit():
                ordinal = int(parts[-1])
                return ordinal

    # 3. Settings fallback
    try:
        from config.config import get_settings
        settings = get_settings()
        if settings.camera_shard_index is not None:
            return int(settings.camera_shard_index)
    except Exception:
        pass

    # 4. Default fallback
    return 0


def get_camera_shard(camera_id: str, shard_count: Optional[int] = None) -> int:
    """Deterministically map a camera ID to a shard index [0 .. shard_count - 1].

    Uses CRC32 hash of the UTF-8 encoded camera_id.
    Guaranteed deterministic across all Python runtimes, pods, and platforms.

    Args:
        camera_id: Unique string camera identifier
        shard_count: Total shards (defaults to get_shard_count())

    Returns:
        Integer shard index
    """
    if not camera_id:
        return 0

    count = shard_count if shard_count is not None else get_shard_count()
    if count <= 1:
        return 0

    return zlib.crc32(camera_id.encode("utf-8")) % count


def is_camera_owned_by_current_pod(camera_id: str) -> bool:
    """Check if the current pod owns and should process the given camera.

    Args:
        camera_id: Unique string camera identifier

    Returns:
        True if current pod owns this camera, False otherwise
    """
    shard_count = get_shard_count()
    if shard_count <= 1:
        return True

    assigned_shard = get_camera_shard(camera_id, shard_count)
    current_shard = get_current_shard_index()
    return assigned_shard == current_shard


def get_pod_host_for_shard(shard_index: int) -> str:
    """Resolve internal cluster address for a specific shard index."""
    from config.config import get_settings
    settings = get_settings()

    svc_name = os.getenv("HEADLESS_SERVICE_NAME") or getattr(settings, "headless_service_name", "crowdvision-backend-headless")
    svc_port = os.getenv("HEADLESS_SERVICE_PORT") or getattr(settings, "headless_service_port", 8000)

    # In StatefulSet: pod-name.headless-svc:port
    return f"crowdvision-backend-{shard_index}.{svc_name}:{svc_port}"


def get_owning_pod_host(camera_id: str) -> str:
    """Resolve the internal cluster address of the pod owning this camera.

    Used by non-owning pods to internally forward live stream requests.

    Args:
        camera_id: Unique string camera identifier

    Returns:
        Internal host:port string (e.g. 'crowdvision-backend-0.crowdvision-backend-headless:8000')
    """
    owner_shard = get_camera_shard(camera_id)
    return get_pod_host_for_shard(owner_shard)
