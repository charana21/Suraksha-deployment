"""
Zone Analytics Service - Aggregates camera analytics to zone level

Provides real-time zone-level analytics for SVG rendering by:
1. Fetching latest analytics from all cameras in each zone
2. Aggregating metrics using conservative rules (SUM for count, MAX for risk)
3. Broadcasting zone updates via WebSocket

Aggregation Rules:
- people_count = SUM(camera_people_counts)
- density_avg = MAX(camera_densities)
- risk_score = MAX(camera_risk_scores)
- risk_level = MAX(camera_risk_levels)
- motion_intensity = MAX(camera_motion_intensities)
"""
from typing import Dict, List, Optional, Any
from datetime import UTC, datetime
from db.mongodb import get_database
from config.config import get_settings

# Risk level ordering for MAX comparison
RISK_LEVEL_ORDER = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "CRITICAL": 3
}

DENSITY_LEVEL_ORDER = {
    "LOW": 0,
    "MODERATE": 1,
    "HIGH": 2,
    "CRITICAL": 3
}

MOTION_LEVEL_ORDER = {
    "STATIC": 0,
    "SLOW": 1,
    "NORMAL": 2,
    "FAST": 3,
    "RUNNING": 4
}


def get_max_risk_level(levels: List[str]) -> str:
    """Get highest risk level from list"""
    if not levels:
        return "LOW"
    max_level = max(levels, key=lambda x: RISK_LEVEL_ORDER.get(x, 0))
    return max_level


def get_max_density_level(levels: List[str]) -> str:
    """Get highest density level from list"""
    if not levels:
        return "LOW"
    max_level = max(levels, key=lambda x: DENSITY_LEVEL_ORDER.get(x, 0))
    return max_level


def get_max_motion_level(levels: List[str]) -> str:
    """Get highest motion level from list"""
    if not levels:
        return "STATIC"
    max_level = max(levels, key=lambda x: MOTION_LEVEL_ORDER.get(x, 0))
    return max_level


async def get_zones_for_station(station_id: Optional[str] = None) -> List[Dict]:
    """
    Get all active zones, optionally filtered by station

    Args:
        station_id: Optional station filter

    Returns:
        List of zone documents ordered by display_order
    """
    db = get_database()
    if db is None:
        return []

    query = {"is_active": True}
    if station_id:
        query["station_id"] = station_id

    cursor = db.zones.find(query).sort("display_order", 1)
    zones = await cursor.to_list(length=100)

    return zones


async def get_cameras_for_zone(zone_id: str) -> List[Dict]:
    """
    Get all cameras mapped to a specific zone

    Args:
        zone_id: Zone identifier

    Returns:
        List of camera documents
    """
    db = get_database()
    if db is None:
        return []

    cursor = db.cameras.find({"zone_id": zone_id, "status": "active"})
    cameras = await cursor.to_list(length=50)

    return cameras


async def get_cameras_by_zone() -> Dict[str, List[Dict]]:
    """
    Get all cameras grouped by zone_id

    Returns:
        Dict mapping zone_id to list of cameras
    """
    db = get_database()
    if db is None:
        return {}

    cursor = db.cameras.find({"zone_id": {"$ne": None}, "status": "active"})
    cameras = await cursor.to_list(length=500)

    # Group by zone_id
    grouped = {}
    for camera in cameras:
        zone_id = camera.get("zone_id")
        if zone_id:
            if zone_id not in grouped:
                grouped[zone_id] = []
            grouped[zone_id].append(camera)

    return grouped


def get_camera_latest_analytics(camera_id: str) -> Optional[Dict]:
    """
    Get latest analytics for a camera from running RTSP streams

    Args:
        camera_id: Camera identifier

    Returns:
        Latest analytics dict or None if not available
    """
    # Import here to avoid circular import (rtsp_worker -> zone_analytics -> rtsp_manager -> rtsp_worker)
    from services.rtsp_manager import get_rtsp_manager
    rtsp_manager = get_rtsp_manager()

    # Find the stream for this camera
    for stream_state in rtsp_manager.get_all_streams():
        if stream_state.get("camera_id") == camera_id:
            # Get latest analysis from the stream
            stream_id = stream_state.get("stream_id")
            worker = rtsp_manager._streams.get(stream_id)
            if worker:
                return worker.get_latest_analysis()

    return None


def _extract_camera_metrics(camera: Dict) -> Dict[str, Any]:
    """Pull one camera's latest analytics (or zeroed defaults) plus its SVG detail entry."""
    camera_id = camera.get("camera_id")
    svg_region_id = camera.get("svg_region_id", camera_id)
    analytics = get_camera_latest_analytics(camera_id)

    if not analytics:
        return {
            "has_analytics": False,
            "latency": None,
            "detail": {
                "camera_id": camera_id,
                "svg_region_id": svg_region_id,
                "people_count": 0,
                "density_avg": 0.0,
                "density_level": "LOW",
                "motion_intensity": 0.0,
                "motion_level": "STATIC",
                "risk_score": 0.0,
                "risk_level": "LOW",
            },
        }

    zone_data = analytics.get("zones", {}).get("full_frame", {})
    pc = zone_data.get("people_count", 0)
    da = zone_data.get("density_estimate", 0.0)
    dl = zone_data.get("density_level", "LOW")
    mi = zone_data.get("avg_motion", 0.0)
    ml = zone_data.get("motion_level", "STATIC")
    rs = zone_data.get("risk_score", 0.0)
    rl = zone_data.get("risk_level", "LOW")

    ts = analytics.get("timestamp")
    latency = max(0, datetime.now(UTC).timestamp() - ts) if ts else None

    return {
        "has_analytics": True,
        "people_count": pc,
        "density_avg": da,
        "density_level": dl,
        "motion_intensity": mi,
        "motion_level": ml,
        "risk_score": rs,
        "risk_level": rl,
        "latency": latency,
        "detail": {
            "camera_id": camera_id,
            "svg_region_id": svg_region_id,
            "people_count": pc,
            "density_avg": round(da, 2),
            "density_level": dl,
            "motion_intensity": round(mi, 4),
            "motion_level": ml,
            "risk_score": round(rs, 1),
            "risk_level": rl,
        },
    }


def _compute_latency_stats(latencies: List[float]) -> Dict[str, float]:
    worst = max(latencies) if latencies else 0.0
    best = min(latencies) if latencies else 0.0
    avg = sum(latencies) / len(latencies) if latencies else 0.0
    return {
        "worst": float(f"{worst:.2f}"),
        "best": float(f"{best:.2f}"),
        "avg": float(f"{avg:.2f}"),
    }


def _build_aggregate_metrics(
    people_counts: List[int],
    densities: List[float],
    density_levels: List[str],
    motions: List[float],
    motion_levels: List[str],
    risk_scores: List[float],
    risk_levels: List[str],
) -> Dict[str, Any]:
    """Aggregate using rules: people_count = SUM, density/motion/risk = MAX."""
    return {
        "people_count": sum(people_counts) if people_counts else 0,
        "density_avg": round(max(densities), 2) if densities else 0.0,
        "density_level": get_max_density_level(density_levels) if density_levels else "LOW",
        "motion_intensity": round(max(motions), 4) if motions else 0.0,
        "motion_level": get_max_motion_level(motion_levels) if motion_levels else "STATIC",
        "risk_score": round(max(risk_scores), 1) if risk_scores else 0.0,
        "risk_level": get_max_risk_level(risk_levels) if risk_levels else "LOW",
    }


def aggregate_camera_analytics(cameras: List[Dict]) -> Dict[str, Any]:
    """
    Aggregate analytics from multiple cameras

    Args:
        cameras: List of camera documents

    Returns:
        Aggregated analytics dict
    """
    people_counts = []
    densities = []
    density_levels = []
    motions = []
    motion_levels = []
    risk_scores = []
    risk_levels = []
    latencies = []
    camera_details = []

    for camera in cameras:
        metrics = _extract_camera_metrics(camera)
        camera_details.append(metrics["detail"])

        if metrics["has_analytics"]:
            people_counts.append(metrics["people_count"])
            densities.append(metrics["density_avg"])
            density_levels.append(metrics["density_level"])
            motions.append(metrics["motion_intensity"])
            motion_levels.append(metrics["motion_level"])
            risk_scores.append(metrics["risk_score"])
            risk_levels.append(metrics["risk_level"])

        if metrics["latency"] is not None:
            latencies.append(metrics["latency"])

    return {
        "camera_details": camera_details,
        "camera_count": len(cameras),
        **_build_aggregate_metrics(
            people_counts, densities, density_levels,
            motions, motion_levels, risk_scores, risk_levels,
        ),
        "latency": _compute_latency_stats(latencies),
        "timestamp": datetime.now(UTC).isoformat(),
        "unix_timestamp": datetime.now(UTC).timestamp(),
    }


async def get_zone_analytics(station_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get aggregated analytics for all zones

    Args:
        station_id: Optional station filter

    Returns:
        Zone analytics response for frontend SVG rendering
    """
    # Get all zones
    zones = await get_zones_for_station(station_id)

    # Get cameras grouped by zone
    cameras_by_zone = await get_cameras_by_zone()

    # Build response
    zone_analytics = []

    for zone in zones:
        zone_id = zone.get("zone_id")
        cameras = cameras_by_zone.get(zone_id, [])

        # Aggregate camera analytics
        aggregated = aggregate_camera_analytics(cameras)

        zone_analytics.append({
            "zone_id": zone_id,
            "zone_name": zone.get("zone_name", ""),
            "zone_type": zone.get("zone_type", "FOB"),
            "display_order": zone.get("display_order", 0),
            "people_count": aggregated["people_count"],
            "density_avg": aggregated["density_avg"],
            "density_level": aggregated["density_level"],
            "motion_intensity": aggregated["motion_intensity"],
            "motion_level": aggregated["motion_level"],
            "risk_score": aggregated["risk_score"],
            "risk_level": aggregated["risk_level"],
            "camera_count": aggregated["camera_count"],
            "cameras": aggregated["camera_details"],
            "latency": aggregated["latency"]
        })

    result = {
        "station_id": station_id,
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "zones": zone_analytics,
    }

    # Enrich with flow analysis data if available
    if station_id:
        result = enrich_with_flow_data(result, station_id)

    return result


def enrich_with_flow_data(zone_data: Dict[str, Any], station_id: str) -> Dict[str, Any]:
    """Merge flow deltas and congestion data into zone analytics payload.

    Reads from FlowAnalysisService's in-memory latest result.
    Safe to call even when flow service is not running (returns data unchanged).
    """
    try:
        from services.flow_analysis_service import _flow_service_instance
        if _flow_service_instance is None:
            return zone_data

        latest = _flow_service_instance.get_latest(station_id)
        if not latest:
            return zone_data

        zone_deltas = latest.get("zone_deltas", {})
        camera_deltas = latest.get("camera_deltas", {})
        congestion = latest.get("congestion")

        # Merge per-zone deltas + per-camera deltas
        for zone in zone_data.get("zones", []):
            zid = zone["zone_id"]
            deltas = zone_deltas.get(zid, {})
            zone["delta_1min"] = deltas.get("delta_1min", 0)
            zone["delta_5min"] = deltas.get("delta_5min", 0)
            zone["flow_status"] = deltas.get("flow_status", "stable")

            # Per-camera flow deltas
            for cam in zone.get("cameras", []):
                cid = cam.get("camera_id")
                cam_deltas = camera_deltas.get(cid, {})
                cam["delta_1min"] = cam_deltas.get("delta_1min", 0)
                cam["delta_5min"] = cam_deltas.get("delta_5min", 0)
                cam["flow_status"] = cam_deltas.get("flow_status", "stable")

        # Attach congestion block if active
        if congestion:
            zone_data["congestion"] = congestion

    except (ImportError, Exception) as e:
        # Flow service not available — return data unchanged
        pass

    return zone_data


# Cache for camera -> station mapping to avoid DB hits on every frame
_camera_station_cache: Dict[str, str] = {}
_last_cache_update = 0
CACHE_TTL = 300  # 5 minutes
_last_station_broadcast_ts: Dict[str, float] = {}

async def broadcast_zone_update_for_camera(camera_id: str, websocket_manager) -> None:
    """
    Trigger zone analytics broadcast when a camera's analytics are updated.
    
    OPTIMIZED: Uses in-memory cache to avoid 2 DB calls per frame.
    """
    if websocket_manager is None:
        return

    # Check cache first
    global _camera_station_cache, _last_cache_update
    now = datetime.now(UTC).timestamp()
    
    # Simple TTL cache invalidation
    if now - _last_cache_update > CACHE_TTL:
        _camera_station_cache.clear()
        _last_cache_update = now

    station_id = _camera_station_cache.get(camera_id)

    if not station_id:
        # Cache miss - perform DB lookup
        db = get_database()
        if db is None:
            return

        # Find which zone this camera belongs to
        camera = await db.cameras.find_one({"camera_id": camera_id})
        if not camera or not camera.get("zone_id"):
            return

        zone_id = camera.get("zone_id")

        # Find the station for this zone
        zone = await db.zones.find_one({"zone_id": zone_id})
        if not zone or not zone.get("station_id"):
            return

        station_id = zone.get("station_id")
        
        # Update cache
        _camera_station_cache[camera_id] = station_id
        # print(f"[ZoneBroadcast] Cache update: {camera_id} -> {station_id}")

    # Check subscribers (fast check)
    zone_subscribers = websocket_manager.get_zone_subscribers(station_id)
    if zone_subscribers == 0:
        return

    # Rate-limit zone broadcasts per station to avoid per-frame fan-out cost.
    settings = get_settings()
    min_interval_sec = max(0.0, float(settings.zone_broadcast_min_interval_ms) / 1000.0)
    if min_interval_sec > 0:
        last_ts = _last_station_broadcast_ts.get(station_id, 0.0)
        if now - last_ts < min_interval_sec:
            return
        _last_station_broadcast_ts[station_id] = now

    # Get aggregated zone analytics (This may still be expensive, usually ~5-10ms)
    # Could be further optimized with rate limiting if needed
    zone_data = await get_zone_analytics(station_id=station_id)

    # Broadcast
    await websocket_manager.broadcast_zone_analytics(station_id, zone_data)


async def get_single_zone_analytics(zone_id: str) -> Optional[Dict[str, Any]]:
    """
    Get analytics for a single zone

    Args:
        zone_id: Zone identifier

    Returns:
        Zone analytics or None if zone not found
    """
    db = get_database()
    if db is None:
        return None

    # Get zone
    zone = await db.zones.find_one({"zone_id": zone_id})
    if not zone:
        return None

    # Get cameras for this zone
    cameras = await get_cameras_for_zone(zone_id)

    # Aggregate analytics
    aggregated = aggregate_camera_analytics(cameras)

    return {
        "zone_id": zone_id,
        "zone_name": zone.get("zone_name", ""),
        "zone_type": zone.get("zone_type", "FOB"),
        "display_order": zone.get("display_order", 0),
        "people_count": aggregated["people_count"],
        "density_avg": aggregated["density_avg"],
        "density_level": aggregated["density_level"],
        "motion_intensity": aggregated["motion_intensity"],
        "motion_level": aggregated["motion_level"],
        "risk_score": aggregated["risk_score"],
        "risk_level": aggregated["risk_level"],
        "camera_count": aggregated["camera_count"],
        "cameras": aggregated["camera_details"]
    }
