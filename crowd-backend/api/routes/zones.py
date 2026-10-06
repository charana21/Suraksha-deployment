"""
Zone management and analytics API endpoints

Provides:
- CRUD operations for zone configuration
- Camera-to-zone mapping
- Aggregated zone analytics for SVG rendering
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from typing import Optional, List
from datetime import datetime
from api.security import require_authorized
import asyncio
import pymongo.errors
from db.mongodb import get_database
from services.zone_analytics import (
    get_zone_analytics,
    get_single_zone_analytics,
    get_cameras_for_zone
)
from models.schemas import (
    ZoneCreateRequest,
    ZoneUpdateRequest,
    CameraZoneAssignRequest
)
from datetime import datetime, timezone as UTC
from util.constants import DATABASE_UNAVAILABLE

router = APIRouter()


# ============================================================================
# ZONE CRUD ENDPOINTS
# ============================================================================

@router.post(
    "/zones",
    status_code=201,
    tags=["Zones"],
    dependencies=[require_authorized],
    responses={
        400: {"description": "Zone already exists"},
        503: {"description": "Database unavailable"},
    },
)
async def create_zone(zone: ZoneCreateRequest):
    """
    Create a new zone for SVG mapping

    - **zone_id**: Unique zone identifier (e.g., 'pf1_fob_hyb_end')
    - **zone_name**: Human-readable name (e.g., 'PF1 FOB - HYB END')
    - **svg_region_id**: SVG element ID for frontend rendering
    - **display_order**: Rendering order in frontend
    - **station_id**: Station identifier (e.g., 'HYB')
    - **zone_type**: Physical zone type (FOB, PLATFORM, STAIRS, LIFT, ENTRY, EXIT)
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if zone already exists
    existing = await db.zones.find_one({"zone_id": zone.zone_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Zone {zone.zone_id} already exists"
        )

    # Create zone document
    now = datetime.now(UTC)
    zone_doc = {
        "zone_id": zone.zone_id,
        "zone_name": zone.zone_name,
        "svg_region_id": zone.svg_region_id,
        "display_order": zone.display_order,
        "station_id": zone.station_id,
        "zone_type": zone.zone_type.value if hasattr(zone.zone_type, 'value') else zone.zone_type,
        "description": zone.description,
        "adjacent_zones": zone.adjacent_zones,
        "area_m2": zone.area_m2,
        "capacity": zone.capacity,
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }

    await db.zones.insert_one(zone_doc)

    # Convert for response
    zone_doc["created_at"] = now.isoformat()
    zone_doc["updated_at"] = now.isoformat()
    del zone_doc["_id"]

    return {
        "status": "success",
        "message": f"Zone {zone.zone_id} created successfully",
        "zone": zone_doc
    }


@router.get("/zones", tags=["Zones"], responses={503: {"description": "Database unavailable"}})
async def list_zones(
    station_id: Optional[str] = Query(None, description="Filter by station ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    List all zones with optional filters

    - **station_id**: Filter by station (e.g., 'HYB')
    - **is_active**: Filter by active status
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    query = {}
    if station_id:
        query["station_id"] = station_id
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.zones.find(query).sort("display_order", 1)
    zones = await cursor.to_list(length=100)

    # Convert for response
    for zone in zones:
        zone["_id"] = str(zone["_id"])
        if "created_at" in zone:
            zone["created_at"] = zone["created_at"].isoformat()
        if "updated_at" in zone:
            zone["updated_at"] = zone["updated_at"].isoformat()

    return {
        "status": "success",
        "count": len(zones),
        "zones": zones
    }


@router.get(
    "/zones/station/{station_id}",
    tags=["Zones"],
    responses={503: {"description": "Database unavailable"}},
)
async def get_zones_by_station(station_id: str):
    """
    Get all zones for a specific station, ordered by display_order

    - **station_id**: Station identifier (e.g., 'HYB')
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail= DATABASE_UNAVAILABLE)

    cursor = db.zones.find({
        "station_id": station_id,
        "is_active": True
    }).sort("display_order", 1)

    zones = await cursor.to_list(length=100)

    # Convert for response
    for zone in zones:
        zone["_id"] = str(zone["_id"])
        if "created_at" in zone:
            zone["created_at"] = zone["created_at"].isoformat()
        if "updated_at" in zone:
            zone["updated_at"] = zone["updated_at"].isoformat()

    return {
        "status": "success",
        "station_id": station_id,
        "count": len(zones),
        "zones": zones
    }


# ============================================================================
# ZONE ANALYTICS ENDPOINTS (for SVG rendering)
# IMPORTANT: These must be defined BEFORE /zones/{zone_id} to avoid route conflict
# ============================================================================

@router.get("/zones/analytics", tags=["Zone Analytics"])
async def get_all_zones_analytics(
    station_id: Optional[str] = Query(None, description="Filter by station ID")
):
    """
    Get aggregated analytics for all zones (for SVG rendering)

    This is the primary endpoint for frontend SVG visualization.
    Returns real-time aggregated metrics for each zone.

    - **station_id**: Optional station filter (e.g., 'HYB')

    Response includes for each zone:
    - zone_id, zone_name, svg_region_id, display_order
    - people_count (SUM of all cameras)
    - density_avg, density_level (MAX across cameras)
    - risk_score, risk_level (MAX across cameras)
    - camera_count, cameras (list of camera IDs)
    """
    analytics = await get_zone_analytics(station_id=station_id)

    return {
        "status": "success",
        **analytics
    }


LATEST_CAMERA_IDS = [
    "cam_pf1_fob_kzj",
    "cam_pf1_fob_pf10",
    "cam_pf1_fob_hyb_end",
    "cam_middle_fob_4_5",
    "cam_kzj_pf1_fob_kzj",
    "cam_kzj_pf1_fob_pf10",
    "cam_mid_fob_pf1",
    "cam_mid_fob_center",
    "cam_hyb_pf1",
    "cam_hyb_pf2",
    "cam_hyb_pf4",
    "cam_hyb_pf6",
    "cam_hyb_pf8",
    "cam_hyb_pf10",
    "cam_hyb_pf1_a",
    "cam_hyb_booking",
    "cam_hyb_booking_gate4a",
    "cam_hyb_booking_gate6",
    "cam_hyb_booking_gate8",
    "cam_pf2_fc_hyd_side",
    "cam_pf7_hyd_end",
    "cam_pf8_mid_fc_kzj",
    "cam_north_parking",
    "cam_gate2_wh",
    "cam_pf_6_7_mmts_fc_hyd",
    "cam_hyd_fob_fc_6_7",
    "cam_kzj_fob_mid_8_9",
    "cam_hyd_booking_gate2a",
    "cam_near_gate_2a_fc_swathi_ent",
    "cam_gate_5_booking_office",
    "cam_gate2_fc_ac_wh",
    "cam_rethifile_bo",
    "cam_gate2a_towards_avtm",
    "cam_gate2a_fc_parking",
]


async def _build_camera_zone_map(db) -> dict:
    """Build {camera_id: zone_id} directly from active cameras in the cameras collection."""
    try:
        docs = await db.cameras.find(
            {"status": "active"},
            {"camera_id": 1, "zone_id": 1, "_id": 0}
        ).to_list(length=200)
    except pymongo.errors.PyMongoError:
        docs = []

    cam_map = {doc["camera_id"]: doc.get("zone_id") for doc in docs if "camera_id" in doc}
    for cid in LATEST_CAMERA_IDS:
        if cid not in cam_map:
            cam_map[cid] = "zone_hyb_fob" if "fob" in cid else "zone_hyb_pf1"
    if "cam_pf1_fob_pf10" in cam_map and "cam_pf1_fob_kzj" not in cam_map:
        cam_map["cam_pf1_fob_kzj"] = cam_map["cam_pf1_fob_pf10"]
    elif "cam_pf1_fob_kzj" in cam_map and "cam_pf1_fob_pf10" not in cam_map:
        cam_map["cam_pf1_fob_pf10"] = cam_map["cam_pf1_fob_kzj"]
    return cam_map

# latest_analytics_data is a collection that stores the most recent analytics record for each camera, enriched with zone_id. This is used for quick access in the frontend without needing to aggregate from the entire analytics collection.
async def _upsert_latest_analytics(records: list, camera_to_zone: dict):
    """Background task: upsert fetched analytics (with zone_id) into latest_analytics_data."""
    db = get_database()
    if db is None:
        return
    for record in records:
        camera_id = record.get("camera_id")
        if not camera_id:
            continue
        upsert_doc = {k: v for k, v in record.items() if k != "_id"}
        upsert_doc["zone_id"] = camera_to_zone.get(camera_id)
        upsert_doc["updated_at"] = datetime.now(UTC)
        try:
            await db.latest_analytics_data.update_one(
                {"camera_id": camera_id},
                {"$set": upsert_doc},
                upsert=True
            )
        except pymongo.errors.PyMongoError:
            pass


@router.get(
    "/zones/latest_camera",
    tags=["Zone Analytics"],
    responses={
        503: {"description": "Database unavailable"},
        500: {"description": "Database query failed"},
    },
)
async def get_latest_camera_analytics(background_tasks: BackgroundTasks):
    """
    Get the latest analytics record for each defined camera, enriched with zone_id.
    Upserts results into latest_analytics_data in the background (non-blocking).
    Excludes timing_ms from the response.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    camera_to_zone = await _build_camera_zone_map(db)
    target_ids = list(camera_to_zone.keys()) if camera_to_zone else LATEST_CAMERA_IDS

    # Sort by (camera_id, timestamp DESC) to match the compound index — avoids in-memory sort
    analytics_pipeline = [
        {"$match": {"camera_id": {"$in": target_ids}}},
        {"$sort": {"camera_id": 1, "timestamp": -1}},
        {"$group": {
            "_id": "$camera_id",
            "doc": {"$first": "$$ROOT"}
        }},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"timing_ms": 0}}
    ]

    try:
        # Run queries
        records = await db.analytics.aggregate(analytics_pipeline).to_list(length=max(100, len(target_ids)))
    except (pymongo.errors.AutoReconnect, pymongo.errors.NetworkTimeout, pymongo.errors.ConnectionFailure) as e:
        raise HTTPException(status_code=503, detail=f"Database connection lost: {e}")
    except pymongo.errors.PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Upsert in background — response goes to FE immediately
    background_tasks.add_task(_upsert_latest_analytics, records, camera_to_zone)

    # Build serializable response without mutating original records
    results = []
    for record in records:
        r = dict(record)
        r["_id"] = str(r["_id"])
        r["zone_id"] = camera_to_zone.get(r.get("camera_id"))
        if "timestamp" in r and hasattr(r["timestamp"], "isoformat"):
            r["timestamp"] = r["timestamp"].isoformat() + "Z"
        results.append(r)

    return {
        "status": "success",
        "count": len(results),
        "cameras": results
    }


@router.get(
    "/zones/{zone_id}",
    tags=["Zones"],
    responses={
        404: {"description": "Zone not found"},
        503: {"description": "Database unavailable"},
    },
)
async def get_zone(zone_id: str):
    """
    Get zone details by ID

    - **zone_id**: Zone identifier
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    zone = await db.zones.find_one({"zone_id": zone_id})

    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    # Convert for response
    zone["_id"] = str(zone["_id"])
    if "created_at" in zone:
        zone["created_at"] = zone["created_at"].isoformat()
    if "updated_at" in zone:
        zone["updated_at"] = zone["updated_at"].isoformat()

    return {
        "status": "success",
        "zone": zone
    }


@router.put(
    "/zones/{zone_id}",
    tags=["Zones"],
    dependencies=[require_authorized],
    responses={
        400: {"description": "No fields to update"},
        404: {"description": "Zone not found"},
        500: {"description": "Failed to update zone"},
        503: {"description": "Database unavailable"},
    },
)
async def update_zone(zone_id: str, updates: ZoneUpdateRequest):
    """
    Update zone configuration

    - **zone_id**: Zone identifier
    - **updates**: Fields to update
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if zone exists
    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    # Prepare updates
    update_dict = updates.dict(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert enum to string if present
    if "zone_type" in update_dict and update_dict["zone_type"]:
        if hasattr(update_dict["zone_type"], 'value'):
            update_dict["zone_type"] = update_dict["zone_type"].value

    update_dict["updated_at"] = datetime.now(UTC)

    # Update zone
    result = await db.zones.update_one(
        {"zone_id": zone_id},
        {"$set": update_dict}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update zone")

    # Get updated zone
    updated_zone = await db.zones.find_one({"zone_id": zone_id})
    updated_zone["_id"] = str(updated_zone["_id"])
    if "created_at" in updated_zone:
        updated_zone["created_at"] = updated_zone["created_at"].isoformat()
    if "updated_at" in updated_zone:
        updated_zone["updated_at"] = updated_zone["updated_at"].isoformat()

    return {
        "status": "success",
        "message": f"Zone {zone_id} updated successfully",
        "zone": updated_zone
    }


@router.delete(
    "/zones/{zone_id}",
    tags=["Zones"],
    dependencies=[require_authorized],
    responses={
        404: {"description": "Zone not found"},
        500: {"description": "Failed to delete zone"},
        503: {"description": "Database unavailable"},
    },
)
async def delete_zone(zone_id: str):
    """
    Delete a zone (cameras will be unmapped)

    - **zone_id**: Zone identifier
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if zone exists
    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    # Unmap all cameras from this zone
    await db.cameras.update_many(
        {"zone_id": zone_id},
        {"$set": {"zone_id": None, "updated_at": datetime.now(UTC)}}
    )

    # Delete zone
    result = await db.zones.delete_one({"zone_id": zone_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete zone")

    return {
        "status": "success",
        "message": f"Zone {zone_id} deleted successfully"
    }


# ============================================================================
# ZONE ADJACENCY ENDPOINT
# ============================================================================

@router.put(
    "/zones/{zone_id}/adjacency",
    tags=["Zones"],
    dependencies=[require_authorized],
    responses={
        400: {"description": "Adjacent zone does not exist"},
        404: {"description": "Zone not found"},
        503: {"description": "Database unavailable"},
    },
)
async def update_zone_adjacency(zone_id: str, adjacent_zones: List[str]):
    """
    Update the adjacent zones for a zone (for flow analysis graph).

    - **zone_id**: Zone identifier
    - **adjacent_zones**: List of zone_ids that are physically connected
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    # Validate that all referenced zones exist
    for adj_id in adjacent_zones:
        adj_zone = await db.zones.find_one({"zone_id": adj_id})
        if not adj_zone:
            raise HTTPException(
                status_code=400,
                detail=f"Adjacent zone {adj_id} does not exist"
            )

    result = await db.zones.update_one(
        {"zone_id": zone_id},
        {"$set": {"adjacent_zones": adjacent_zones, "updated_at": datetime.now(UTC)}}
    )

    return {
        "status": "success",
        "message": f"Zone {zone_id} adjacency updated ({len(adjacent_zones)} adjacent zones)",
        "zone_id": zone_id,
        "adjacent_zones": adjacent_zones
    }


# ============================================================================
# CAMERA-ZONE MAPPING ENDPOINTS
# ============================================================================

@router.get(
    "/zones/{zone_id}/cameras",
    tags=["Zones"],
    responses={
        404: {"description": "Zone not found"},
        503: {"description": "Database unavailable"},
    },
)
async def get_cameras_in_zone(zone_id: str):
    """
    Get all cameras mapped to a specific zone

    - **zone_id**: Zone identifier
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if zone exists
    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    # Get cameras
    cameras = await get_cameras_for_zone(zone_id)

    # Convert for response
    for camera in cameras:
        if "_id" in camera:
            camera["_id"] = str(camera["_id"])
        if "created_at" in camera:
            camera["created_at"] = camera["created_at"].isoformat()
        if "updated_at" in camera:
            camera["updated_at"] = camera["updated_at"].isoformat()

    return {
        "status": "success",
        "zone_id": zone_id,
        "zone_name": zone.get("zone_name"),
        "count": len(cameras),
        "cameras": cameras
    }


@router.put(
    "/cameras/{camera_id}/zone",
    tags=["Zones"],
    dependencies=[require_authorized],
    responses={
        404: {"description": "Camera or zone not found"},
        500: {"description": "Failed to update camera zone"},
        503: {"description": "Database unavailable"},
    },
)
async def assign_camera_to_zone(camera_id: str, request: CameraZoneAssignRequest):
    """
    Assign a camera to a zone (or unassign if zone_id is null)

    - **camera_id**: Camera identifier
    - **zone_id**: Zone to assign (null to unassign)
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if camera exists
    camera = await db.cameras.find_one({"camera_id": camera_id})
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    # If assigning to a zone, verify zone exists
    if request.zone_id:
        zone = await db.zones.find_one({"zone_id": request.zone_id})
        if not zone:
            raise HTTPException(status_code=404, detail=f"Zone {request.zone_id} not found")

    # Update camera
    result = await db.cameras.update_one(
        {"camera_id": camera_id},
        {"$set": {"zone_id": request.zone_id, "updated_at": datetime.now(UTC)}}
    )

    if result.modified_count == 0 and camera.get("zone_id") != request.zone_id:
        raise HTTPException(status_code=500, detail="Failed to update camera zone")

    action = "assigned to" if request.zone_id else "unassigned from"
    zone_info = request.zone_id if request.zone_id else "any zone"

    return {
        "status": "success",
        "message": f"Camera {camera_id} {action} {zone_info}",
        "camera_id": camera_id,
        "zone_id": request.zone_id
    }


@router.get(
    "/zones/{zone_id}/analytics",
    tags=["Zone Analytics"],
    responses={
        404: {"description": "Zone not found"},
        500: {"description": "Failed to get zone analytics"},
        503: {"description": "Database unavailable"},
    },
)
async def get_zone_analytics_single(zone_id: str):
    """
    Get analytics for a single zone

    - **zone_id**: Zone identifier
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    # Check if zone exists
    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")

    analytics = await get_single_zone_analytics(zone_id)

    if not analytics:
        raise HTTPException(status_code=500, detail="Failed to get zone analytics")

    return {
        "status": "success",
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "zone": analytics
    }


# ============================================================================
# INTERNAL CROSS-SHARD ANALYTICS & BROADCAST ENDPOINTS
# ============================================================================

@router.get("/internal/camera-analytics", include_in_schema=False)
async def get_internal_camera_analytics():
    """Returns local camera analytics for peer shards."""
    from services.zone_analytics import get_local_camera_analytics
    from services.sharding import get_current_shard_index
    from fastapi.responses import JSONResponse
    return JSONResponse(content={
        "status": "success",
        "shard_id": get_current_shard_index(),
        "analytics": get_local_camera_analytics()
    })


@router.post("/internal/broadcast-zones", include_in_schema=False)
async def receive_internal_zone_broadcast(request: Request):
    """Receives zone updates forwarded from peer shard and broadcasts to local subscribers."""
    try:
        payload = await request.json()
        station_id = payload.get("station_id")
        zone_data = payload.get("zone_data")
        if station_id and zone_data:
            from services.websocket_manager import get_connection_manager
            ws_mgr = get_connection_manager()
            await ws_mgr.broadcast_zone_analytics(station_id, zone_data)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

