"""
WebSocket endpoints for real-time analytics push
Supports per-camera and all-cameras subscriptions

Authentication:
    When auth_enabled=True (production), all WebSocket connections require
    a valid JWT token via query parameter: ws://host/api/ws/analytics?token=xxx

    When auth_enabled=False (development), connections work without token.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
from services.websocket_manager import get_connection_manager
from api.security import ws_auth_required, ws_role_required
from utils.logging_config import get_logger
from datetime import UTC

router = APIRouter()
logger = get_logger(__name__)

@router.websocket("/ws/analytics")
async def websocket_all_cameras(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Subscribe to analytics from all cameras

    Authentication:
        Requires valid JWT token via query param when auth_enabled=True
        Example: ws://localhost:8000/api/ws/analytics?token=eyJhbG...

    Client will receive:
    - Analytics updates from all cameras
    - Alerts from all cameras

    Message format:
    ```json
    {
        "type": "analytics" | "alert",
        "camera_id": "camera_entry_stair",
        "data": {...},
        "timestamp": "2025-12-29T14:30:15.123456"
    }
    ```

    Usage:
    ```javascript
    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`ws://localhost:8000/api/ws/analytics?token=${token}`);

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'analytics') {
            console.log(`Analytics from ${message.camera_id}:`, message.data);
        } else if (message.type === 'alert') {
            console.log(`Alert from ${message.camera_id}:`, message.data);
        }
    };
    ```
    """
    # Authenticate before accepting connection
    payload = await ws_auth_required(websocket, token)
    if payload is None:
        return  # Connection closed by auth

    manager = get_connection_manager()
    await manager.connect(websocket, camera_id=None)

    try:
        while True:
            # Keep connection alive (heartbeat)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass  # Normal disconnect
    except Exception as e:
        logger.warning(f"WebSocket error (all cameras): {e}")
    finally:
        await manager.disconnect(websocket, camera_id=None)


@router.websocket("/ws/analytics/{camera_id}")
async def websocket_camera(websocket: WebSocket, camera_id: str, token: Optional[str] = Query(None)):
    """
    Subscribe to analytics from specific camera

    Access control:
        Admin only (single-camera live stream access is restricted)

    Authentication:
        Requires valid JWT token via query param when auth_enabled=True

    Client will receive:
    - Analytics updates from specified camera only
    - Alerts from specified camera only

    Message format: Same as /ws/analytics

    Usage:
    ```javascript
    const token = localStorage.getItem('access_token');
    const cameraId = 'camera_entry_stair';
    const ws = new WebSocket(`ws://localhost:8000/api/ws/analytics/${cameraId}?token=${token}`);

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        console.log(`Update from ${cameraId}:`, message.data);
    };
    ```
    """
    # Authenticate before accepting connection
    payload = await ws_role_required(websocket, token, allowed_roles=["admin"])
    if payload is None:
        return  # Connection closed by auth

    manager = get_connection_manager()
    await manager.connect(websocket, camera_id=camera_id)

    try:
        while True:
            # Keep connection alive (heartbeat)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass  # Normal disconnect
    except Exception as e:
        logger.warning(f"WebSocket error (camera {camera_id}): {e}")
    finally:
        await manager.disconnect(websocket, camera_id=camera_id)


@router.get("/ws/stats", tags=["WebSocket"])
async def get_websocket_stats():
    """
    Get WebSocket connection statistics

    Returns:
    - Total connections
    - Messages sent
    - Connection errors
    - Active cameras
    - Global subscribers
    """
    manager = get_connection_manager()
    stats = manager.get_stats()

    return {
        "status": "success",
        "stats": stats
    }


@router.get("/ws/cameras/{camera_id}/subscribers", tags=["WebSocket"])
async def get_camera_subscribers(camera_id: str):
    """
    Get number of subscribers for specific camera

    Args:
        camera_id: Camera identifier

    Returns:
        Subscriber count (camera-specific + global)
    """
    manager = get_connection_manager()
    subscribers = manager.get_camera_subscribers(camera_id)

    return {
        "status": "success",
        "camera_id": camera_id,
        "subscribers": subscribers
    }


# ============================================================================
# ZONE WEBSOCKET ENDPOINTS (for SVG rendering)
# ============================================================================

@router.websocket("/ws/zones/analytics")
async def websocket_all_zones(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Subscribe to zone analytics from all stations

    Authentication:
        Requires valid JWT token via query param when auth_enabled=True

    Client will receive aggregated zone analytics for SVG rendering.
    Updates are sent when any camera analytics change.

    Message format:
    ```json
    {
        "type": "zone_analytics",
        "station_id": "HYB",
        "timestamp": "2025-12-30T14:30:15.123456Z",
        "zones": [
            {
                "zone_id": "pf1_fob_hyb_end",
                "zone_name": "PF1 FOB - HYB END",
                "svg_region_id": "svg_pf1_fob_hyb_end",
                "display_order": 1,
                "people_count": 134,
                "risk_level": "MEDIUM",
                "risk_score": 45.5
            }
        ]
    }
    ```

    Usage:
    ```javascript
    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`ws://localhost:8000/api/ws/zones/analytics?token=${token}`);

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'zone_analytics') {
            message.zones.forEach(zone => {
                const el = document.getElementById(zone.svg_region_id);
                if (el) {
                    el.style.fill = riskColorMap[zone.risk_level];
                }
            });
        }
    };
    ```
    """
    # Authenticate before accepting connection
    payload = await ws_auth_required(websocket, token)
    if payload is None:
        return  # Connection closed by auth

    from services.zone_analytics import get_zone_analytics

    manager = get_connection_manager()
    await manager.connect_zone(websocket, station_id=None)

    # Send initial zone data immediately after connection
    try:
        initial_data = await get_zone_analytics(station_id=None)
        msg = {
            "type": "zone_analytics",
            "station_id": None,
            "timestamp": initial_data.get("timestamp"),
            "zones": initial_data.get("zones", []),
        }
        if "congestion" in initial_data:
            msg["congestion"] = initial_data["congestion"]
        await websocket.send_json(msg)
        logger.info(f"Sent initial zone data for all stations: {len(initial_data.get('zones', []))} zones")
    except Exception as e:
        logger.warning(f"Failed to send initial zone data: {e}")

    try:
        while True:
            # Keep connection alive (heartbeat)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass  # Normal disconnect
    except Exception as e:
        logger.warning(f"WebSocket error (all zones): {e}")
    finally:
        await manager.disconnect_zone(websocket, station_id=None)


@router.websocket("/ws/zones/analytics/{station_id}")
async def websocket_station_zones(websocket: WebSocket, station_id: str, token: Optional[str] = Query(None)):
    """
    Subscribe to zone analytics for a specific station

    Authentication:
        Requires valid JWT token via query param when auth_enabled=True

    Client will receive aggregated zone analytics for the specified station only.

    Args:
        station_id: Station identifier (e.g., 'HYB')

    Message format: Same as /ws/zones/analytics

    Usage:
    ```javascript
    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`ws://localhost:8000/api/ws/zones/analytics/HYB?token=${token}`);

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        // Update SVG for HYB station
        updateSVG(message.zones);
    };
    ```
    """
    # Authenticate before accepting connection
    payload = await ws_auth_required(websocket, token)
    if payload is None:
        return  # Connection closed by auth

    from services.zone_analytics import get_zone_analytics

    manager = get_connection_manager()
    await manager.connect_zone(websocket, station_id=station_id)
    logger.info(f"Client connected to zone analytics for station: {station_id}")

    # Send initial zone data immediately after connection
    try:
        initial_data = await get_zone_analytics(station_id=station_id)
        msg = {
            "type": "zone_analytics",
            "station_id": station_id,
            "timestamp": initial_data.get("timestamp"),
            "zones": initial_data.get("zones", []),
        }
        if "congestion" in initial_data:
            msg["congestion"] = initial_data["congestion"]
        await websocket.send_json(msg)
        logger.info(f"Sent initial zone data for {station_id}: {len(initial_data.get('zones', []))} zones")
    except Exception as e:
        logger.warning(f"Failed to send initial zone data for {station_id}: {e}")

    try:
        while True:
            # Keep connection alive (heartbeat)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass  # Normal disconnect
    except Exception as e:
        logger.warning(f"WebSocket error (station {station_id} zones): {e}")
    finally:
        await manager.disconnect_zone(websocket, station_id=station_id)
        logger.debug(f"Client disconnected from zone analytics for station: {station_id}")


@router.get("/ws/zones/subscribers", tags=["WebSocket"])
async def get_zone_subscribers():
    """
    Get number of zone analytics subscribers

    Returns:
        Total zone subscriber count
    """
    manager = get_connection_manager()
    subscribers = manager.get_zone_subscribers()

    return {
        "status": "success",
        "zone_subscribers": subscribers
    }


@router.get("/ws/zones/{station_id}/subscribers", tags=["WebSocket"])
async def get_station_zone_subscribers(station_id: str):
    """
    Get number of zone subscribers for specific station

    Args:
        station_id: Station identifier

    Returns:
        Subscriber count (station-specific + global zone)
    """
    manager = get_connection_manager()
    subscribers = manager.get_zone_subscribers(station_id)

    return {
        "status": "success",
        "station_id": station_id,
        "subscribers": subscribers
    }


# ============================================================================
# TRAIN SCHEDULE WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/ws/trains")
async def websocket_trains(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Subscribe to real-time train schedule updates.

    Authentication:
        Requires valid JWT token via query param when auth_enabled=True

    Client will receive:
    - upcoming_update: Periodic updates of upcoming trains (every 60 seconds)
    - schedule_uploaded: When new schedule Excel is uploaded

    Message format:
    ```json
    {
        "type": "train_schedule",
        "event": "upcoming_update",
        "timestamp": "2026-01-09T14:30:00.000Z",
        "data": {
            "arriving": [
                {
                    "train_number": "12733",
                    "train_name": "NARAYANADRI EXP",
                    "arrival_time": "2026-01-09T15:00:00.000Z",
                    "arrival_display": "15:00",
                    "minutes_until_arrival": 30,
                    ...
                }
            ],
            "departing": [...],
            "total_count": 8
        }
    }
    ```

    Usage:
    ```javascript
    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`ws://localhost:8000/api/ws/trains?token=${token}`);

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'train_schedule') {
            if (msg.event === 'upcoming_update') {
                updateTrainDisplay(msg.data.arriving, msg.data.departing);
            } else if (msg.event === 'schedule_uploaded') {
                showNotification('New train schedule uploaded');
            }
        }
    };
    ```
    """
    # Authenticate before accepting connection
    payload = await ws_auth_required(websocket, token)
    if payload is None:
        return  # Connection closed by auth

    from services.train_schedule_service import TrainScheduleService
    from datetime import datetime

    manager = get_connection_manager()
    await manager.connect_trains(websocket)

    # Send initial upcoming trains data immediately after connection
    try:
        initial_data = await TrainScheduleService.get_upcoming_trains()
        await websocket.send_json({
            "type": "train_schedule",
            "event": "upcoming_update",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": initial_data
        })
        logger.info(f"Sent initial train data: {initial_data['total_count']} trains")
    except Exception as e:
        logger.warning(f"Failed to send initial train data: {e}")

    try:
        while True:
            # Keep connection alive (heartbeat)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass  # Normal disconnect
    except Exception as e:
        logger.warning(f"WebSocket error (trains): {e}")
    finally:
        await manager.disconnect_trains(websocket)


@router.get("/ws/trains/subscribers", tags=["WebSocket"])
async def get_train_subscribers():
    """
    Get number of train schedule WebSocket subscribers

    Returns:
        Total train subscriber count
    """
    manager = get_connection_manager()
    subscribers = manager.get_train_subscribers()

    return {
        "status": "success",
        "train_subscribers": subscribers
    }
