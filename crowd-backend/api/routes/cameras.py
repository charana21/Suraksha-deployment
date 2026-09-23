"""
Camera management API endpoints
Provides CRUD operations for camera metadata and stream control
"""
import asyncio
import os
import cv2
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from services.camera_service import CameraService
from services.rtsp_manager import get_rtsp_manager
from services.websocket_manager import get_connection_manager
from api.security import require_admin, require_viewer

router = APIRouter()

SNAPSHOT_CAPTURE_TIMEOUT_SECONDS = 8

CAMERA_NOT_FOUND_DESC = "Camera not found"


# ===== Request/Response Models =====

class CameraCreate(BaseModel):
    """Request model for creating a camera"""
    camera_id: str = Field(..., description="Unique camera identifier", example="camera_entry_stair")
    name: str = Field(..., description="Human-readable camera name", example="Entry Stair")
    # Use example RTSP URL from settings/.env to avoid hardcoded IP in source
    try:
        _EXAMPLE_RTSP = os.getenv("EXAMPLE_RTSP_URL")
    except Exception:
        _EXAMPLE_RTSP = os.getenv("EXAMPLE_RTSP_URL")

    if _EXAMPLE_RTSP:
        _EXAMPLE_RTSP = _EXAMPLE_RTSP.strip()
        if (_EXAMPLE_RTSP.startswith('"') and _EXAMPLE_RTSP.endswith('"')) or (
            _EXAMPLE_RTSP.startswith("'") and _EXAMPLE_RTSP.endswith("'")
        ):
            _EXAMPLE_RTSP = _EXAMPLE_RTSP[1:-1]
    else:
        _EXAMPLE_RTSP = "rtsp://<EXAMPLE_HOST>/stream1"

    rtsp_url: str = Field(..., description="RTSP stream URL", example=_EXAMPLE_RTSP)
    location: Optional[str] = Field("Unknown", description="Physical location (Legacy)")
    fob_type: Optional[str] = Field(None, description="FOB Type (HYD, KZJ)", example="HYD")
    zone_id: Optional[str] = Field(None, description="Zone ID mapping", example="zone_pf1_lift")
    settings: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional camera-specific settings"
    )


class CameraUpdate(BaseModel):
    """Request model for updating a camera"""
    name: Optional[str] = Field(None, description="Camera name")
    rtsp_url: Optional[str] = Field(None, description="RTSP stream URL")
    location: Optional[str] = Field(None, description="Physical location")
    fob_type: Optional[str] = Field(None, description="FOB Type")
    zone_id: Optional[str] = Field(None, description="Zone ID")
    status: Optional[str] = Field(None, description="Camera status (active/inactive/error)")
    settings: Optional[Dict[str, Any]] = Field(None, description="Camera settings")


class CameraResponse(BaseModel):
    """Response model for camera data"""
    camera_id: str
    name: str
    rtsp_url: str
    location: str
    fob_type: Optional[str] = None
    zone_id: Optional[str] = None
    status: str
    is_active: bool
    created_at: str
    updated_at: str
    last_seen_at: Optional[str] = None


# ===== API Endpoints =====

@router.post(
    "/cameras",
    status_code=201,
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={400: {"description": "Camera registration failed"}},
)
@router.post(
    "/cameras",
    status_code=201,
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={400: {"description": "Invalid camera parameters"}},
)
async def create_camera(camera: CameraCreate):
    """
    Register a new camera in the system
    """
    try:
        camera_doc = await CameraService.register_camera(
            camera_id=camera.camera_id,
            name=camera.name,
            rtsp_url=camera.rtsp_url,
            location=camera.location,
            fob_type=camera.fob_type,
            zone_id=camera.zone_id,
            settings=camera.settings
        )

        # Broadcast update
        await get_connection_manager().broadcast_camera_update(
            camera_id=camera.camera_id,
            event_type="created",
            camera_data=camera_doc
        )

        return {
            "status": "success",
            "message": f"Camera {camera.camera_id} registered successfully",
            "camera": camera_doc
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cameras", tags=["Cameras"], dependencies=[require_viewer])
async def list_cameras(
    status: Optional[str] = Query(None, description="Filter by status (active/inactive/error)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    fob_type: Optional[str] = Query(None, description="Filter by FOB Type (HYD, KZJ)")
):
    """
    List all cameras with optional filters
    """
    cameras = await CameraService.list_cameras(status=status, location=location, fob_type=fob_type)

    return {
        "status": "success",
        "count": len(cameras),
        "cameras": cameras
    }


@router.get(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": "Camera not found"}},
)
@router.get(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": CAMERA_NOT_FOUND_DESC}},
)
async def get_camera(camera_id: str):
    """
    Get camera details by ID
    """
    camera = await CameraService.get_camera(camera_id)

    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return {
        "status": "success",
        "camera": camera
    }


@router.put(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        400: {"description": "No fields to update"},
        404: {"description": "Camera not found"},
        500: {"description": "Failed to update camera"},
    },
)
@router.put(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        400: {"description": "No fields to update"},
        404: {"description": CAMERA_NOT_FOUND_DESC},
        500: {"description": "Failed to update camera"},
    },
)
async def update_camera(camera_id: str, updates: CameraUpdate):
    """
    Update camera metadata (name, RTSP URL, etc.)
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    update_dict = updates.dict(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = await CameraService.update_camera(camera_id, update_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update camera")

    updated_camera = await CameraService.get_camera(camera_id)

    # Broadcast update
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="updated",
        camera_data=updated_camera
    )

    return {
        "status": "success",
        "message": f"Camera {camera_id} updated successfully",
        "camera": updated_camera
    }


@router.delete(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Failed to delete camera"},
    },
)
@router.delete(
    "/cameras/{camera_id}",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        404: {"description": CAMERA_NOT_FOUND_DESC},
        500: {"description": "Failed to delete camera"},
    },
)
async def delete_camera(camera_id: str):
    """
    Delete camera (use with caution)
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    success = await CameraService.delete_camera(camera_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete camera")

    # Broadcast update
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="deleted",
        camera_data={"camera_id": camera_id}
    )

    return {
        "status": "success",
        "message": f"Camera {camera_id} deleted successfully"
    }


# ===== STREAM CONTROL =====

@router.post(
    "/cameras/{camera_id}/start",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        404: {"description": "Camera not found"},
        500: {"description": "Failed to start stream"},
    },
)
@router.post(
    "/cameras/{camera_id}/start",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        404: {"description": CAMERA_NOT_FOUND_DESC},
        500: {"description": "Failed to start stream"},
    },
)
async def start_camera_stream(camera_id: str):
    """
    Start the RTSP stream for this camera
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    rtsp_manager = get_rtsp_manager()

    try:
        # Check if already running using camera_id (mapped to stream_id)
        if rtsp_manager.stream_exists(camera_id):
             return {
                "status": "success",
                "message": f"Stream for camera {camera_id} is already running",
                "stream_id": camera_id
            }

        # Start stream using camera_id as stream_id
        stream_id = rtsp_manager.start_stream(
            rtsp_url=camera["rtsp_url"],
            camera_id=camera_id,
            stream_id=camera_id, # Force 1:1 mapping
            name=camera["name"],
            location=camera.get("location", "Unknown"),
            target_fps=camera.get("settings", {}).get("target_fps", 1)
        )

        # Update DB status
        await CameraService.update_camera_status(camera_id, "active")

        # Broadcast update - fetch fresh status
        updated_camera = await CameraService.get_camera(camera_id)
        await get_connection_manager().broadcast_camera_update(
            camera_id=camera_id,
            event_type="started",
            camera_data=updated_camera
        )

        return {
            "status": "success",
            "message": f"Stream started for camera {camera_id}",
            "stream_id": stream_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")


@router.post(
    "/cameras/{camera_id}/stop",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={404: {"description": "Camera not found"}},
)
@router.post(
    "/cameras/{camera_id}/stop",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={404: {"description": CAMERA_NOT_FOUND_DESC}},
)
async def stop_camera_stream(camera_id: str):
    """
    Stop the RTSP stream for this camera
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    rtsp_manager = get_rtsp_manager()

    # Stop stream (assuming stream_id == camera_id)
    success = rtsp_manager.stop_stream(camera_id)
    
    # Update DB status even if stream wasn't found (to ensure sync)
    await CameraService.update_camera_status(camera_id, "inactive")

    # Broadcast update
    updated_camera = await CameraService.get_camera(camera_id)
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="stopped",
        camera_data=updated_camera
    )

    if not success:
        # Might have been stopped already or never started
        return {
             "status": "success",
             "message": f"Stream for camera {camera_id} was not running"
        }

    return {
        "status": "success",
        "message": f"Stream stopped for camera {camera_id}"
    }


def _capture_single_frame(rtsp_url: str):
    """
    Open a short-lived RTSP connection, grab one frame, and release it.
    Runs in a worker thread (blocking OpenCV I/O) — call via asyncio.to_thread.
    """
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
        'rtsp_transport;tcp|analyzeduration;2000000|probesize;1000000|fflags;+discardcorrupt|flags;low_delay'
    )

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        if not cap.isOpened():
            return None

        # Discard a couple of stale/partial frames so we return a fresh one
        frame = None
        for _ in range(5):
            ret, candidate = cap.read()
            if ret:
                frame = candidate
        return frame
    finally:
        cap.release()


@router.get(
    "/cameras/{camera_id}/snapshot",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={
        404: {"description": "Camera not found"},
        422: {"description": "Camera has no rtsp_url configured"},
        500: {"description": "Failed to encode snapshot"},
        503: {"description": "Could not capture a frame from camera"},
        504: {"description": "Timed out connecting to camera"},
    },
)
@router.get(
    "/cameras/{camera_id}/snapshot",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={
        404: {"description": CAMERA_NOT_FOUND_DESC},
        422: {"description": "Camera has no rtsp_url configured"},
        500: {"description": "Failed to encode snapshot"},
        503: {"description": "Could not capture a frame from camera"},
        504: {"description": "Timed out connecting to camera"},
    },
)
async def get_camera_snapshot(camera_id: str):
    """
    Get a live JPEG snapshot from the camera.

    If the camera's RTSP stream is already running, this returns the most
    recently captured frame instantly (no extra connection). Otherwise it
    opens a short-lived direct connection to the camera's RTSP URL, grabs
    a single frame, and releases the connection.
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    # Fast path: reuse the already-connected stream's latest cached frame
    rtsp_manager = get_rtsp_manager()
    with rtsp_manager._lock:
        worker = rtsp_manager._streams.get(camera_id)

    frame = worker.get_latest_frame() if worker else None

    # Fallback: open a one-shot direct connection to the camera
    if frame is None:
        rtsp_url = camera.get("rtsp_url")
        if not rtsp_url:
            raise HTTPException(status_code=422, detail=f"Camera {camera_id} has no rtsp_url configured")

        try:
            frame = await asyncio.wait_for(
                asyncio.to_thread(_capture_single_frame, rtsp_url),
                timeout=SNAPSHOT_CAPTURE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Timed out connecting to camera {camera_id}")

    if frame is None:
        raise HTTPException(status_code=503, detail=f"Could not capture a frame from camera {camera_id}")

    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode snapshot")

    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )


@router.get(
    "/cameras/{camera_id}/live",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={
        404: {"description": "Camera not found"},
        503: {"description": "No active stream for camera"},
    },
)
@router.get(
    "/cameras/{camera_id}/live",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={
        404: {"description": CAMERA_NOT_FOUND_DESC},
        503: {"description": "No active stream for camera; start it first"},
    },
)
async def get_camera_live_feed(camera_id: str):
    """
    Continuous live view of the camera as an MJPEG stream, throttled to 1 frame/second.

    Requires the camera's RTSP stream to already be running (via /cameras/{camera_id}/start
    or /rtsp/start). Each second, pulls whatever frame is currently cached by the stream
    worker and pushes it to the client, replacing the previous one.

    Usage: <img src="/api/cameras/{camera_id}/live" />
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    rtsp_manager = get_rtsp_manager()
    with rtsp_manager._lock:
        worker = rtsp_manager._streams.get(camera_id)

    if worker is None:
        raise HTTPException(status_code=503, detail=f"No active stream for camera {camera_id}; start it first")

    def generate_frames():
        import time

        while True:
            frame = worker.get_latest_frame()

            if frame is not None:
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if success:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(1)  # 1 frame per second

    return StreamingResponse(
        generate_frames(),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive'
        }
    )


@router.get(
    "/cameras/{camera_id}/status",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": "Camera not found"}},
)
@router.get(
    "/cameras/{camera_id}/status",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": CAMERA_NOT_FOUND_DESC}},
)
async def get_camera_status(camera_id: str):
    """
    Get real-time camera status (checking both DB and Runtime)
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    rtsp_manager = get_rtsp_manager()
    stream_state = rtsp_manager.get_stream_state(camera_id) # Using camera_id as stream_id

    # Determine real status
    real_status = "inactive"
    if stream_state:
        real_status = stream_state.get("status", "unknown")
    
    # Check if DB mismatch
    if camera.get("status") != real_status and stream_state:
         # Optional: Auto-correct DB? No, let's just return truth
         pass

    return {
        "status": "success",
        "camera_id": camera["camera_id"],
        "name": camera["name"],
        "db_status": camera.get("status"),
        "runtime_status": real_status,
        "is_active": camera.get("is_active", False),
        "last_seen_at": camera.get("last_seen_at"),
        "fob_type": camera.get("fob_type"),
        "zone_id": camera.get("zone_id")
    }


@router.post(
    "/cameras/{camera_id}/status",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={400: {"description": "Invalid status"}},
)
@router.post(
    "/cameras/{camera_id}/status",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={400: {"description": "Invalid status"}},
)
async def update_camera_status_manual(camera_id: str, status: str):
    """
    Manually update status (Legacy support)
    """
    if status not in ["active", "inactive", "error"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    await CameraService.update_camera_status(camera_id, status)

    # Broadcast update
    updated_camera = await CameraService.get_camera(camera_id)
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="updated",
        camera_data=updated_camera
    )

    return {"status": "success", "message": "Status updated"}


@router.get("/cameras/stats/summary", tags=["Cameras"], dependencies=[require_viewer])
async def get_cameras_summary():
    """
    Get summary statistics
    """
    all_cameras = await CameraService.list_cameras()
    active_cameras = [c for c in all_cameras if c.get("status") == "active"]

    location_counts = {}
    fob_counts = {}
    
    for camera in all_cameras:
        loc = camera.get("location", "Unknown")
        fob = camera.get("fob_type", "Unknown")
        location_counts[loc] = location_counts.get(loc, 0) + 1
        fob_counts[fob] = fob_counts.get(fob, 0) + 1

    return {
        "status": "success",
        "total_cameras": len(all_cameras),
        "active_cameras": len(active_cameras),
        "by_location": location_counts,
        "by_fob_type": fob_counts
    }


# ===== ROI & CALIBRATION =====

class SetROIRequest(BaseModel):
    """Request model for setting camera ROI + area"""
    area_m2: float = Field(..., gt=0, description="Real-world area in m² (provided by station staff)")
    roi_points: Optional[List[List[float]]] = Field(
        None,
        min_length=3,
        description="ROI polygon vertices as [[x_px, y_px], ...] in pixel coordinates"
    )
    frame_width: Optional[int] = Field(None, gt=0, description="Frame width when ROI was drawn")
    frame_height: Optional[int] = Field(None, gt=0, description="Frame height when ROI was drawn")


@router.put(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        400: {"description": "frame_width and frame_height required when roi_points is provided"},
        404: {"description": "Camera not found"},
        500: {"description": "Failed to set calibration"},
    },
)
@router.put(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={
        400: {"description": "frame_width and frame_height are required when roi_points is provided"},
        404: {"description": CAMERA_NOT_FOUND_DESC},
        500: {"description": "Failed to set calibration"},
    },
)
async def set_camera_roi(camera_id: str, request: SetROIRequest):
    """
    Set ROI polygon and area_m2 for a camera.

    area_m2 is always required (real-world area provided by station staff).
    roi_points is optional -- if provided, frame_width and frame_height are also required.
    """
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    # Validate: if roi_points provided, frame dimensions required
    if request.roi_points and (not request.frame_width or not request.frame_height):
        raise HTTPException(
            status_code=400,
            detail="frame_width and frame_height are required when roi_points is provided"
        )

    success = await CameraService.set_camera_calibration(
        camera_id=camera_id,
        area_m2=request.area_m2,
        roi_points=request.roi_points,
        frame_width=request.frame_width,
        frame_height=request.frame_height
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to set calibration")

    # Broadcast update
    updated_camera = await CameraService.get_camera(camera_id)
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="calibration_updated",
        camera_data=updated_camera
    )

    return {
        "status": "success",
        "message": f"Calibration set for camera {camera_id}",
        "area_m2": request.area_m2,
        "has_roi": request.roi_points is not None
    }


@router.get(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": "Camera not found"}},
)
@router.get(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_viewer],
    responses={404: {"description": CAMERA_NOT_FOUND_DESC}},
)
async def get_camera_roi(camera_id: str):
    """Get ROI and area configuration for a camera"""
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    calibration = camera.get("calibration")

    if not calibration:
        return {
            "status": "success",
            "camera_id": camera_id,
            "has_calibration": False,
            "area_m2": None,
            "has_roi": False,
            "roi": None
        }

    roi = calibration.get("roi")
    return {
        "status": "success",
        "camera_id": camera_id,
        "has_calibration": True,
        "area_m2": calibration.get("area_m2"),
        "has_roi": roi is not None,
        "roi": roi
    }


@router.delete(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={404: {"description": "Camera not found"}},
)
@router.delete(
    "/cameras/{camera_id}/roi",
    tags=["Cameras"],
    dependencies=[require_admin],
    responses={404: {"description": CAMERA_NOT_FOUND_DESC}},
)
async def delete_camera_roi(camera_id: str):
    """Remove calibration from a camera (reverts to full-frame fallback)"""
    camera = await CameraService.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    success = await CameraService.delete_camera_calibration(camera_id)

    # Broadcast update
    updated_camera = await CameraService.get_camera(camera_id)
    await get_connection_manager().broadcast_camera_update(
        camera_id=camera_id,
        event_type="calibration_removed",
        camera_data=updated_camera
    )

    return {
        "status": "success",
        "message": f"Calibration removed for camera {camera_id}"
    }
