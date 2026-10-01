"""
RTSP Stream API endpoints

Provides REST API for managing multiple RTSP streams:
- Start new streams
- Stop existing streams
- Get status of streams
- List all streams
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import cv2
import numpy as np
import logging
import os
import aiohttp
from services.rtsp_manager import get_rtsp_manager
from services.camera_service import CameraService
from services.sharding import (
    is_camera_owned_by_current_pod,
    get_camera_shard,
    get_owning_pod_host,
    get_pod_host_for_shard,
    get_shard_count,
    get_current_shard_index,
)
from utils.visualization import visualize_heatmap_only
from api.security import require_admin, require_viewer, require_authorized
import uuid
logger = logging.getLogger(__name__)
router = APIRouter()

STREAM_NOT_FOUND_DESC = "Stream not found"
INTERNAL_ERROR_DESC = "Internal Server Error"


# Request/Response Models
class StartStreamRequest(BaseModel):
    """Request model for starting RTSP stream"""
    rtsp_url: str = Field(..., description="RTSP stream URL (e.g., rtsp://camera.example.com:554/stream)")
    stream_id: Optional[str] = Field(None, description="Optional custom stream ID")
    camera_id: Optional[str] = Field(None, description="Optional camera ID (auto-generated if not provided)")
    target_fps: Optional[int] = Field(None, description="Target processing FPS (None = process all frames)")
    name: Optional[str] = Field(None, description="Human-readable name for the stream")
    location: Optional[str] = Field(None, description="Physical location of the camera")

    @validator('rtsp_url')
    def validate_rtsp_url(cls, v):
        if not v.startswith(('rtsp://', 'rtmp://', 'http://')):
            raise ValueError('URL must start with rtsp://, rtmp://, or http://')
        return v

    @validator('target_fps')
    def validate_target_fps(cls, v):
        if v is not None and (v < 1 or v > 60):
            raise ValueError('target_fps must be between 1 and 60')
        return v


class StartStreamsRequest(BaseModel):
    """Request model for starting multiple RTSP streams"""
    streams: List[StartStreamRequest] = Field(..., description="List of streams to start")


class StreamResponse(BaseModel):
    """Response model for stream information"""
    stream_id: str
    camera_id: str
    rtsp_url: str
    status: str
    message: str


# API Endpoints

@router.post(
    "/rtsp/start",
    response_model=StreamResponse,
    dependencies=[require_admin],
    responses={
        400: {"description": "Invalid request parameters"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def start_rtsp_stream(request: StartStreamRequest):
    """
    Start a new RTSP stream for real-time crowd analysis

    The stream will be processed in a dedicated thread with:
    - Independent frame capture loop
    - Real-time crowd detection and density analysis
    - Automatic reconnection on failures
    - Automatic camera registration in database

    Camera ID will be auto-generated if not provided.

    Returns stream_id for monitoring and control
    """
    print(f"[RTSP API] Starting stream: {request.rtsp_url}")

    manager = get_rtsp_manager()

    try:
        # Auto-generate camera_id if not provided
        camera_id = request.camera_id
        if not camera_id:
            # Generate camera_id from stream_id or create new UUID
            camera_id = request.stream_id if request.stream_id else f"camera_{str(uuid.uuid4())[:8]}"
            # print(f"[RTSP API] Auto-generated camera_id: {camera_id}")
            logger.info(f"[RTSP API] Auto-generated camera_id: {camera_id}")

        # Auto-create or get camera in database
        camera_name = request.name or f"Camera {camera_id}"
        camera_location = request.location or "Unknown"

        try:
            # Try to get or create camera in MongoDB
            camera = await CameraService.get_or_create_camera(
                camera_id=camera_id,
                name=camera_name,
                rtsp_url=request.rtsp_url,
                location=camera_location
            )
            logger.info(f"[RTSP API] Camera registered: {camera_id} ({camera_name})")
        except Exception as db_error:
            # If MongoDB is not available, continue without camera registration
            logger.warning(f"[RTSP API] Warning: Could not register camera in database: {db_error}")
            logger.info(f"[RTSP API] Continuing with camera_id: {camera_id}")

        # Start RTSP stream
        stream_id = manager.start_stream(
            rtsp_url=request.rtsp_url,
            camera_id=camera_id,  # Now we have camera_id
            stream_id=request.stream_id,
            target_fps=request.target_fps,
            name=camera_name,
            location=camera_location
        )

        return StreamResponse(
            stream_id=stream_id,
            camera_id=camera_id,
            rtsp_url=request.rtsp_url,
            status="started",
            message=f"Stream {stream_id} started successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")


@router.post("/rtsp/start-multiple", dependencies=[require_admin])
async def start_multiple_rtsp_streams(request: StartStreamsRequest):
    """
    Start multiple RTSP streams in parallel

    All streams will be processed simultaneously in independent threads.
    This endpoint allows bulk stream initialization.

    Returns list of stream_ids and their status
    """
    manager = get_rtsp_manager()
    results = []

    for stream_req in request.streams:
        try:
            stream_id = manager.start_stream(
                rtsp_url=stream_req.rtsp_url,
                stream_id=stream_req.stream_id,
                target_fps=stream_req.target_fps,
                name=stream_req.name
            )

            results.append({
                'stream_id': stream_id,
                'rtsp_url': stream_req.rtsp_url,
                'status': 'started',
                'message': 'Stream started successfully'
            })

        except Exception as e:
            results.append({
                'stream_id': stream_req.stream_id or 'unknown',
                'rtsp_url': stream_req.rtsp_url,
                'status': 'error',
                'message': str(e)
            })

    return JSONResponse({
        'total': len(request.streams),
        'started': len([r for r in results if r['status'] == 'started']),
        'failed': len([r for r in results if r['status'] == 'error']),
        'results': results
    })


@router.post(
    "/rtsp/stop/{stream_id}",
    dependencies=[require_admin],
    responses={404: {"description": STREAM_NOT_FOUND_DESC}},
)
async def stop_rtsp_stream(stream_id: str):
    """
    Stop a specific RTSP stream

    Gracefully stops the stream processing thread and releases resources.
    """
    manager = get_rtsp_manager()

    success = manager.stop_stream(stream_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")

    return JSONResponse({
        'stream_id': stream_id,
        'status': 'stopped',
        'message': 'Stream stopped successfully'
    })


@router.post("/rtsp/stop-all", dependencies=[require_admin])
async def stop_all_rtsp_streams():
    """
    Stop all active RTSP streams

    Gracefully stops all stream processing threads.
    """
    manager = get_rtsp_manager()

    count_before = manager.get_stream_count()['total']
    manager.stop_all_streams()

    return JSONResponse({
        'status': 'success',
        'message': f'Stopped {count_before} stream(s)',
        'streams_stopped': count_before
    })


@router.get(
    "/rtsp/status/{stream_id}",
    dependencies=[require_authorized],
    responses={404: {"description": STREAM_NOT_FOUND_DESC}},
)
async def get_stream_status(stream_id: str, request: Request = None):
    """
    Get detailed status of a specific RTSP stream

    Returns:
    - Stream metadata
    - Current status (connecting, running, error, stopped)
    - Performance metrics (FPS, frame count)
    - Latest analysis results (people count, density, risk)
    """
    manager = get_rtsp_manager()

    state = manager.get_stream_state(stream_id)

    if state is not None:
        return JSONResponse(state)

    # If stream is not running locally, check if it belongs to another shard
    if not is_camera_owned_by_current_pod(stream_id):
        # Prevent forwarding loops
        if request and request.headers.get("X-Internal-Forwarded"):
            raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")

        target_host = get_owning_pod_host(stream_id)
        target_url = f"http://{target_host}/api/rtsp/status/{stream_id}"
        timeout = aiohttp.ClientTimeout(total=4.0)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(target_url, headers={"X-Internal-Forwarded": "true"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return JSONResponse(data)
                    elif resp.status == 404:
                        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[RTSPRouting] Failed forwarding stream status for {stream_id} to {target_host}: {e}")

    raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")


@router.get("/rtsp/list", dependencies=[require_authorized])
async def list_rtsp_streams(request: Request = None):
    """
    List all RTSP streams with their status

    Returns list of all active streams with key metrics across shards
    """
    manager = get_rtsp_manager()

    streams = manager.get_all_streams()
    counts = manager.get_stream_count()

    # If this request came internally from another pod, return only local streams to avoid recursion
    if request and request.headers.get("X-Internal-Forwarded"):
        return JSONResponse({
            'summary': counts,
            'streams': streams
        })

    # Otherwise aggregate from peer shards if multi-shard deployment
    shard_count = get_shard_count()
    current_shard = get_current_shard_index()

    if shard_count > 1:
        aggregated_streams = list(streams)
        timeout = aiohttp.ClientTimeout(total=3.0)
        for shard_idx in range(shard_count):
            if shard_idx == current_shard:
                continue
            peer_host = get_pod_host_for_shard(shard_idx)
            peer_url = f"http://{peer_host}/api/rtsp/list"
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(peer_url, headers={"X-Internal-Forwarded": "true"}) as resp:
                        if resp.status == 200:
                            peer_data = await resp.json()
                            aggregated_streams.extend(peer_data.get('streams', []))
            except Exception as e:
                logger.warning(f"[RTSPAggregation] Failed to aggregate streams from {peer_host}: {e}")

        # Recalculate summary counts across all streams
        total_counts = {
            'total': len(aggregated_streams),
            'running': sum(1 for s in aggregated_streams if s.get('status') == 'running'),
            'error': sum(1 for s in aggregated_streams if s.get('status') == 'error'),
            'connecting': sum(1 for s in aggregated_streams if s.get('status') == 'connecting'),
            'stopped': sum(1 for s in aggregated_streams if s.get('status') == 'stopped')
        }
        return JSONResponse({
            'summary': total_counts,
            'streams': aggregated_streams
        })

    return JSONResponse({
        'summary': counts,
        'streams': streams
    })


@router.get("/rtsp/health", dependencies=[require_viewer])
async def rtsp_health_check():
    """
    Health check for RTSP streaming system

    Returns overall system status and stream counts
    """
    manager = get_rtsp_manager()
    counts = manager.get_stream_count()

    return JSONResponse({
        'status': 'healthy',
        'service': 'RTSP Streaming',
        'streams': counts,
        'parallel_processing': True
    })


@router.get(
    "/rtsp/frame/{stream_id}",
    dependencies=[require_admin],
    responses={
        404: {"description": STREAM_NOT_FOUND_DESC},
        503: {"description": "No frame available yet"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_stream_frame(stream_id: str, heatmap: bool = False):
    """
    Get latest frame from a specific stream

    Args:
        stream_id: Stream identifier
        heatmap: If True, return frame with heatmap overlay

    Returns:
        JPEG image of latest frame
    """
    manager = get_rtsp_manager()

    # Check if stream exists
    state = manager.get_stream_state(stream_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")

    # Get worker
    with manager._lock:
        worker = manager._streams.get(stream_id)

    if worker is None:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} worker not found")

    # Get latest frame
    frame = worker.get_latest_frame()

    if frame is None:
        raise HTTPException(status_code=503, detail="No frame available yet")

    # Apply heatmap if requested
    if heatmap:
        # Get full analysis with numpy arrays
        full_analysis = worker.get_full_analysis()
        if full_analysis:
            frame = visualize_heatmap_only(
                frame=frame,
                detections=full_analysis.get('detections', []),
                density=full_analysis.get('density_map', np.zeros((frame.shape[0], frame.shape[1]))),
                accumulated_heatmap=None,
                alpha=0.6
            )

    # Encode frame as JPEG
    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode frame")

    # Return as image
    return StreamingResponse(
        iter([buffer.tobytes()]),
        media_type="image/jpeg",
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )


@router.get(
    "/rtsp/live/{stream_id}",
    dependencies=[require_admin],
    responses={404: {"description": STREAM_NOT_FOUND_DESC}},
)
async def get_live_stream(stream_id: str, request: Request = None):
    """
    Get live video stream as MJPEG without any processing

    This endpoint provides a direct video feed without crowd analysis overlays.
    Simply forwards the raw RTSP frames as MJPEG stream for viewing.

    Args:
        stream_id: Stream identifier

    Returns:
        MJPEG stream (multipart/x-mixed-replace)

    Usage:
        <img src="/api/rtsp/live/{stream_id}" />
        or open in browser: http://localhost:8000/api/rtsp/live/{stream_id}
    """
    manager = get_rtsp_manager()

    # Check if stream exists locally
    state = manager.get_stream_state(stream_id)
    if state is None:
        # Check if owned by another pod
        if not is_camera_owned_by_current_pod(stream_id):
            if request and request.headers.get("X-Internal-Forwarded"):
                raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
            target_host = get_owning_pod_host(stream_id)
            target_url = f"http://{target_host}/api/rtsp/live/{stream_id}"

            async def forward_remote_stream():
                timeout = aiohttp.ClientTimeout(total=None, connect=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    try:
                        async with session.get(target_url, headers={"X-Internal-Forwarded": "true"}) as resp:
                            if resp.status != 200:
                                return
                            async for chunk in resp.content.iter_any():
                                yield chunk
                    except Exception as e:
                        logger.warning(f"[RTSPLiveRouting] Internal stream forwarding error for {stream_id}: {e}")

            return StreamingResponse(
                forward_remote_stream(),
                media_type='multipart/x-mixed-replace; boundary=frame',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Live-Routing': 'internal-forwarded',
                }
            )
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")

    # Get worker
    with manager._lock:
        worker = manager._streams.get(stream_id)

    if worker is None:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} worker not found")

    def generate_frames():
        """Generate MJPEG frames"""
        import time

        while True:
            # Get latest frame (raw, no processing)
            frame = worker.get_latest_frame()

            if frame is not None:
                # Encode frame as JPEG
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                if success:
                    # Yield frame in MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            # Small delay to prevent overwhelming the client
            time.sleep(0.033)  # ~30 FPS max

    return StreamingResponse(
        generate_frames(),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive'
        }
    )


@router.post("/rtsp/cleanup", dependencies=[require_admin])
async def cleanup_stopped_streams():
    """
    Clean up stopped streams from tracking

    Removes streams that have stopped running from the manager's tracking
    """
    manager = get_rtsp_manager()

    count = manager.cleanup_stopped_streams()

    return JSONResponse({
        'status': 'success',
        'message': f'Cleaned up {count} stopped stream(s)',
        'streams_cleaned': count
    })


@router.get(
    "/rtsp/analytics/{stream_id}",
    dependencies=[require_viewer],
    responses={
        404: {"description": "Analytics not found for stream"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_stream_analytics(stream_id: str, limit: int = 100, offset: int = 0):
    """
    Get analytics data for a specific stream

    Returns JSON analytics with all frame data including:
    - People count
    - Density metrics
    - Motion intensity
    - Detection bounding boxes
    - Timestamps

    Args:
        stream_id: Stream identifier
        limit: Maximum number of frames to return (default 100)
        offset: Skip first N frames (default 0)

    Returns:
        List of analytics data for each frame
    """
    from config.config import get_settings
    import os
    import json
    import aiofiles

    settings = get_settings()
    analytics_file = os.path.join(settings.analytics_dir, f"{stream_id}_analytics.jsonl")

    if not os.path.exists(analytics_file):
        raise HTTPException(status_code=404, detail=f"Analytics not found for stream {stream_id}")

    # Read JSONL file (one JSON object per line)
    analytics_data = []
    try:
        async with aiofiles.open(analytics_file, 'r') as f:
            lines = await f.readlines()

            # Apply offset and limit
            start = offset
            end = min(offset + limit, len(lines))

            for line in lines[start:end]:
                if line.strip():
                    analytics_data.append(json.loads(line))

        return JSONResponse({
            'stream_id': stream_id,
            'total_frames': len(lines),
            'returned_frames': len(analytics_data),
            'offset': offset,
            'limit': limit,
            'analytics': analytics_data
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read analytics: {str(e)}")


@router.get(
    "/rtsp/analytics/{stream_id}/frame/{frame_number}",
    dependencies=[require_viewer],
    responses={
        404: {"description": "Analytics or frame not found"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_stream_frame_analytics(stream_id: str, frame_number: int):
    """
    Get analytics data for a specific frame

    Returns detailed analytics for a single frame including all metrics
    """
    from config.config import get_settings
    import os
    import json
    import aiofiles

    settings = get_settings()
    analytics_file = os.path.join(settings.analytics_dir, f"{stream_id}_analytics.jsonl")

    if not os.path.exists(analytics_file):
        raise HTTPException(status_code=404, detail=f"Analytics not found for stream {stream_id}")

    try:
        async with aiofiles.open(analytics_file, 'r') as f:
            async for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get('frame_number') == frame_number:
                        return JSONResponse(data)

        raise HTTPException(status_code=404, detail=f"Frame {frame_number} not found in analytics")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read analytics: {str(e)}")


@router.get("/rtsp/heatmaps/{stream_id}", dependencies=[require_authorized])
async def list_stream_heatmaps(stream_id: str):
    """
    List all saved heatmaps for a specific stream

    Returns list of heatmap files with frame numbers
    """
    from config.config import get_settings
    import os
    import glob

    settings = get_settings()
    # Support both jpg and png formats
    pattern_jpg = os.path.join(settings.heatmap_dir, f"{stream_id}_frame_*.jpg")
    pattern_png = os.path.join(settings.heatmap_dir, f"{stream_id}_frame_*.png")
    heatmap_files = glob.glob(pattern_jpg) + glob.glob(pattern_png)

    # Extract frame numbers and create file info
    heatmaps = []
    for filepath in sorted(heatmap_files):
        filename = os.path.basename(filepath)
        # Extract frame number from filename: {stream_id}_frame_{frame_number:06d}.{ext}
        try:
            frame_num_str = filename.split('_frame_')[1].split('.')[0]
            frame_number = int(frame_num_str)
            heatmaps.append({
                'frame_number': frame_number,
                'filename': filename,
                'url': f'/api/rtsp/heatmap/{stream_id}/{frame_number}'
            })
        except (IndexError, ValueError):
            continue

    return JSONResponse({
        'stream_id': stream_id,
        'total_heatmaps': len(heatmaps),
        'heatmaps': heatmaps
    })


@router.get(
    "/rtsp/heatmap/{stream_id}/{frame_number}",
    dependencies=[require_authorized],
    responses={404: {"description": "Heatmap not found for frame"}},
)
async def get_stream_heatmap(stream_id: str, frame_number: int):
    """
    Get heatmap image for a specific frame from RTSP stream

    Returns heatmap visualization (JPG or PNG depending on configuration)
    """
    from config.config import get_settings
    import os

    settings = get_settings()

    # Try both jpg and png formats
    filename_jpg = f"{stream_id}_frame_{frame_number:06d}.jpg"
    filename_png = f"{stream_id}_frame_{frame_number:06d}.png"
    filepath_jpg = os.path.join(settings.heatmap_dir, filename_jpg)
    filepath_png = os.path.join(settings.heatmap_dir, filename_png)

    if os.path.exists(filepath_jpg):
        filepath = filepath_jpg
        filename = filename_jpg
        media_type = 'image/jpeg'
    elif os.path.exists(filepath_png):
        filepath = filepath_png
        filename = filename_png
        media_type = 'image/png'
    else:
        raise HTTPException(status_code=404, detail=f"Heatmap not found for frame {frame_number}")

    return FileResponse(
        filepath,
        media_type=media_type,
        headers={
            'Cache-Control': 'public, max-age=3600',
            'Content-Disposition': f'inline; filename="{filename}"'
        }
    )