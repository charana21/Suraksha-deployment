"""
Analytics endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import aiofiles
import os
import json

from config.config import get_settings
from api.security import require_authorized
from db.mongodb import MongoDB
from datetime import datetime

router = APIRouter()
settings = get_settings()

ISO_UTC_SUFFIX = '+00:00'
ERR_DATABASE_NOT_AVAILABLE = "Database not available"
ERR_INVALID_TIMESTAMP_FORMAT = "Invalid timestamp format. Use ISO 8601."
ERR_ANALYTICS_NOT_FOUND = "Analytics not found"
ERR_HEATMAP_NOT_FOUND = "Heatmap not found"
SERVICE_UNAVAILABLE_RESPONSES = {503: {"description": ERR_DATABASE_NOT_AVAILABLE}}
INVALID_TIMESTAMP_RESPONSES = {400: {"description": ERR_INVALID_TIMESTAMP_FORMAT}}
MISSING_PARAMS_RESPONSES = {400: {"description": "Required query parameters are missing"}}
ANALYTICS_NOT_FOUND_RESPONSES = {404: {"description": ERR_ANALYTICS_NOT_FOUND}}
HEATMAP_NOT_FOUND_RESPONSES = {404: {"description": ERR_HEATMAP_NOT_FOUND}}

# MongoDB aggregation pipeline operators
OP_MATCH = "$match"
OP_GROUP = "$group"
OP_PROJECT = "$project"
OP_SORT = "$sort"
OP_TO_DATE = "$toDate"
OP_SUBTRACT = "$subtract"
OP_TO_LONG = "$toLong"
OP_ROUND = "$round"
OP_DATE_TO_STRING = "$dateToString"

# MongoDB field references used within aggregation pipelines
FIELD_TIMESTAMP = "$timestamp"
FIELD_TOTAL_PEOPLE_COUNT = "$total_people_count"
FIELD_AVG_COUNT = "$avg_count"
FIELD_PEAK_COUNT = "$peak_count"
FIELD_MIN_COUNT = "$min_count"
FIELD_CAMERA_ID = "$camera_id"
FIELD_PEOPLE_COUNT = "$people_count"
FIELD_ID_TIME_BUCKET = "$_id.time_bucket"
FIELD_CAM_COUNT = "$cam_count"
FIELD_TOTAL_FOB_LOAD = "$total_fob_load"
FIELD_TOTAL_LOAD = "$total_load"

ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_interval_to_ms(interval: str) -> int:
    """Convert interval string (1m, 1h, 1d) to milliseconds"""
    if not interval:
        return 5 * 60 * 1000  # Default 5m

    unit = interval[-1].lower()
    try:
        value = int(interval[:-1])
    except ValueError:
        return 5 * 60 * 1000

    if unit == 's':
        return value * 1000
    if unit == 'm':
        return value * 60 * 1000
    if unit == 'h':
        return value * 3600 * 1000
    if unit == 'd':
        return value * 86400 * 1000
    if unit == 'w':
        return value * 7 * 86400 * 1000
    return 5 * 60 * 1000


@router.get(
    "/analytics/fob/history",
    responses={**SERVICE_UNAVAILABLE_RESPONSES, **INVALID_TIMESTAMP_RESPONSES}
)
async def get_fob_history(
    fob_id: str,
    start: str,
    end: str,
    interval: str = "5m",
    force_fallback: bool = False  # Default to False (Trust fob_analytics collection)
):
    """
    Get historical people count for a FOB.
    Aggregates data from all cameras mapped to this FOB.
    
    Args:
        fob_id: FOB Identifier (e.g., "HYB", "KZJ")
        start: Start timestamp (ISO)
        end: End timestamp (ISO)
        interval: Data resolution (1m, 5m, 1h, 1d)
        force_fallback: If True, bypass fob_analytics and calc from raw data (Recommended for accuracy)
    """
    if MongoDB.database is None:
        raise HTTPException(503, ERR_DATABASE_NOT_AVAILABLE)

    try:
        start_dt = datetime.fromisoformat(start.replace('Z', ISO_UTC_SUFFIX))
        end_dt = datetime.fromisoformat(end.replace('Z', ISO_UTC_SUFFIX))
    except ValueError:
        raise HTTPException(400, ERR_INVALID_TIMESTAMP_FORMAT)

    # 1. Resolve FOB ID (Handle mappings)
    # Accepts: station_id (e.g. "HYB" for combined all-FOB) or zone_id (e.g. "zone_hyb_fob")
    query_fob_ids = [fob_id]
    if fob_id == "HYB":
        query_fob_ids.append("HYD")

    # 2. Query Pre-Aggregated FOB Analytics
    results = []
    data_source = "fob_analytics"
    
    if not force_fallback:
        # Use the fob_analytics collection which already has summed counts per timestamp
        interval_ms = parse_interval_to_ms(interval)
        
        pipeline = [
            # Match time range and FOB ID
            {
                OP_MATCH: {
                    "fob_id": {"$in": query_fob_ids},
                    "timestamp": {
                        "$gte": start_dt,
                        "$lte": end_dt
                    }
                }
            },
            # Bucket by time interval
            {
                OP_GROUP: {
                    "_id": {
                        OP_TO_DATE: {
                            OP_SUBTRACT: [
                                {OP_TO_LONG: FIELD_TIMESTAMP},
                                {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, interval_ms]}
                            ]
                        }
                    },
                    # Calculate statistics for this bucket
                    "avg_count": {"$avg": FIELD_TOTAL_PEOPLE_COUNT},
                    "peak_count": {"$max": FIELD_TOTAL_PEOPLE_COUNT},
                    "min_count": {"$min": FIELD_TOTAL_PEOPLE_COUNT},
                    "samples": {"$sum": 1}
                }
            },
            # Format output
            {
                OP_PROJECT: {
                    "_id": 0,
                    "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                    "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]}, # Backward compat
                    "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "peak_count": FIELD_PEAK_COUNT,
                    "min_count": FIELD_MIN_COUNT
                }
            },
            {OP_SORT: {"timestamp": 1}}
        ]

        results = await MongoDB.database.fob_analytics.aggregate(pipeline).to_list(None)

        # Get overall peak across entire range (not per-interval)
        overall_peak_pipeline = [
            {
                OP_MATCH: {
                    "fob_id": {"$in": query_fob_ids},
                    "timestamp": {"$gte": start_dt, "$lte": end_dt}
                }
            },
            {
                OP_GROUP: {
                    "_id": None,
                    "overall_peak": {"$max": FIELD_TOTAL_PEOPLE_COUNT}
                }
            }
        ]
        overall_peak_result = await MongoDB.database.fob_analytics.aggregate(overall_peak_pipeline).to_list(1)
        overall_peak = overall_peak_result[0]["overall_peak"] if overall_peak_result else 0
    else:
        results = []
        overall_peak = 0
        data_source = "forced_fallback"

    # 3. Fallback to Raw Analytics (Accurate Recalculation)
    if not results:
        # Resolve cameras for this FOB
        cursor = MongoDB.database.cameras.find(
            {"fob_type": {"$in": query_fob_ids}},
            {"camera_id": 1}
        )
        cameras = await cursor.to_list(length=100)
        camera_ids = [c["camera_id"] for c in cameras]
        
        if not camera_ids:
            return {
                "status": "success",
                "fob_id": fob_id,
                "interval": interval,
                "overall_peak": 0,
                "data": [],
                "source": "no_cameras_found"
            }

        # CALCULATE FROM RAW DATA
        # Strategy: 
        # 1. Snap all camera records to nearest Second (or 2s window)
        # 2. Sum counts of all cameras for that Window -> True Total at Time T
        # 3. Bucket these Totals into the requested Interval (e.g. 5m) -> Find Peak of Totals
        
        interval_ms = parse_interval_to_ms(interval)
        
        # We use a small "alignment window" to snap camera frames together.
        ALIGNMENT_WINDOW_MS = 2000 

        pipeline = [
            # Match Raw Analytics
            {
                OP_MATCH: {
                    "camera_id": {"$in": camera_ids},
                    "timestamp": {
                        "$gte": start_dt,
                        "$lte": end_dt
                    }
                }
            },
            # Step 1: Align frames to common time windows (Snap to grid)
            {
                OP_GROUP: {
                    "_id": {
                        "camera_id": FIELD_CAMERA_ID,
                        "time_bucket": {
                            OP_TO_DATE: {
                                OP_SUBTRACT: [
                                    {OP_TO_LONG: FIELD_TIMESTAMP},
                                    {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, ALIGNMENT_WINDOW_MS]}
                                ]
                            }
                        }
                    },
                    "cam_count": {"$avg": FIELD_PEOPLE_COUNT}
                }
            },
            # Step 2: Sum ALL cameras for that Time Bucket
            {
                OP_GROUP: {
                    "_id": FIELD_ID_TIME_BUCKET,
                    "total_fob_load": {"$sum": FIELD_CAM_COUNT}
                }
            },
            # Step 3: Bucket into Requested Output Interval
            {
                OP_GROUP: {
                    "_id": {
                        OP_TO_DATE: {
                            OP_SUBTRACT: [
                                {OP_TO_LONG: "$_id"},
                                {"$mod": [{OP_TO_LONG: "$_id"}, interval_ms]} 
                            ]
                        }
                    },
                    # True Peak calculation
                    "peak_count": {"$max": FIELD_TOTAL_FOB_LOAD},
                    "avg_count": {"$avg": FIELD_TOTAL_FOB_LOAD},
                    "min_count": {"$min": FIELD_TOTAL_FOB_LOAD},
                    "samples": {"$sum": 1}
                }
            },
            # Format Output
            {
                OP_PROJECT: {
                    "_id": 0,
                    "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                    "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "peak_count": {OP_ROUND: [FIELD_PEAK_COUNT, 0]},
                    "min_count": {OP_ROUND: [FIELD_MIN_COUNT, 0]}
                }
            },
            {OP_SORT: {"timestamp": 1}}
        ]
        
        results = await MongoDB.database.analytics.aggregate(pipeline).to_list(None)

        # Calculate overall peak from raw data (same logic but without interval bucketing)
        overall_peak_pipeline = [
            {
                OP_MATCH: {
                    "camera_id": {"$in": camera_ids},
                    "timestamp": {"$gte": start_dt, "$lte": end_dt}
                }
            },
            # Align frames to common time windows
            {
                OP_GROUP: {
                    "_id": {
                        "camera_id": FIELD_CAMERA_ID,
                        "time_bucket": {
                            OP_TO_DATE: {
                                OP_SUBTRACT: [
                                    {OP_TO_LONG: FIELD_TIMESTAMP},
                                    {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, ALIGNMENT_WINDOW_MS]}
                                ]
                            }
                        }
                    },
                    "cam_count": {"$avg": FIELD_PEOPLE_COUNT}
                }
            },
            # Sum ALL cameras for each time bucket
            {
                OP_GROUP: {
                    "_id": FIELD_ID_TIME_BUCKET,
                    "total_fob_load": {"$sum": FIELD_CAM_COUNT}
                }
            },
            # Get the overall maximum across all time buckets
            {
                OP_GROUP: {
                    "_id": None,
                    "overall_peak": {"$max": FIELD_TOTAL_FOB_LOAD}
                }
            }
        ]
        overall_peak_result = await MongoDB.database.analytics.aggregate(overall_peak_pipeline).to_list(1)
        overall_peak = int(overall_peak_result[0]["overall_peak"]) if overall_peak_result and overall_peak_result[0].get("overall_peak") else 0

        if data_source != "forced_fallback":
            data_source = "raw_analytics_recalculated"

    return {
        "status": "success",
        "fob_id": fob_id,
        "interval": interval,
        "overall_peak": overall_peak,
        "data": results,
        "source": data_source
    }


@router.get(
    "/analytics/zone/history",
    responses={**SERVICE_UNAVAILABLE_RESPONSES, **MISSING_PARAMS_RESPONSES, **INVALID_TIMESTAMP_RESPONSES}
)
async def get_zone_history(
    zone_id: str = None,
    start: str = None,
    end: str = None,
    interval: str = "5m"
):
    """
    Get historical people count for any zone (FOB, PLATFORM, or BOOKING).

    Automatically routes to the correct collection based on zone_type:
    - FOB zones → fob_analytics
    - PLATFORM zones → platform_analytics
    - Other → raw analytics fallback

    Args:
        zone_id: Zone identifier (e.g. "zone_hyb_fob", "zone_hyb_pf1")
        start: Start timestamp (ISO 8601)
        end: End timestamp (ISO 8601)
        interval: Data resolution (1m, 5m, 1h, 1d)
    """
    if MongoDB.database is None:
        raise HTTPException(503, ERR_DATABASE_NOT_AVAILABLE)

    if not zone_id or not start or not end:
        raise HTTPException(400, "zone_id, start, and end are required")

    try:
        start_dt = datetime.fromisoformat(start.replace('Z', ISO_UTC_SUFFIX))
        end_dt = datetime.fromisoformat(end.replace('Z', ISO_UTC_SUFFIX))
    except ValueError:
        raise HTTPException(400, ERR_INVALID_TIMESTAMP_FORMAT)

    # Look up zone_type
    zone_doc = await MongoDB.database.zones.find_one({"zone_id": zone_id}, {"zone_type": 1})
    zone_type = zone_doc.get("zone_type") if zone_doc else None

    interval_ms = parse_interval_to_ms(interval)
    results = []
    data_source = "unknown"

    # Route to correct collection
    if zone_type == "FOB":
        # Query fob_analytics where fob_id == zone_id
        pipeline = [
            {OP_MATCH: {
                "fob_id": zone_id,
                "timestamp": {"$gte": start_dt, "$lte": end_dt}
            }},
            {OP_GROUP: {
                "_id": {OP_TO_DATE: {OP_SUBTRACT: [
                    {OP_TO_LONG: FIELD_TIMESTAMP},
                    {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, interval_ms]}
                ]}},
                "avg_count": {"$avg": FIELD_TOTAL_PEOPLE_COUNT},
                "peak_count": {"$max": FIELD_TOTAL_PEOPLE_COUNT},
                "min_count": {"$min": FIELD_TOTAL_PEOPLE_COUNT},
                "samples": {"$sum": 1}
            }},
            {OP_PROJECT: {
                "_id": 0,
                "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                "peak_count": FIELD_PEAK_COUNT,
                "min_count": FIELD_MIN_COUNT
            }},
            {OP_SORT: {"timestamp": 1}}
        ]
        results = await MongoDB.database.fob_analytics.aggregate(pipeline).to_list(None)
        data_source = "fob_analytics"

    elif zone_type == "PLATFORM":
        # Query platform_analytics where zone_id == zone_id
        pipeline = [
            {OP_MATCH: {
                "zone_id": zone_id,
                "timestamp": {"$gte": start_dt, "$lte": end_dt}
            }},
            {OP_GROUP: {
                "_id": {OP_TO_DATE: {OP_SUBTRACT: [
                    {OP_TO_LONG: FIELD_TIMESTAMP},
                    {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, interval_ms]}
                ]}},
                "avg_count": {"$avg": FIELD_TOTAL_PEOPLE_COUNT},
                "peak_count": {"$max": FIELD_TOTAL_PEOPLE_COUNT},
                "min_count": {"$min": FIELD_TOTAL_PEOPLE_COUNT},
                "samples": {"$sum": 1}
            }},
            {OP_PROJECT: {
                "_id": 0,
                "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                "peak_count": FIELD_PEAK_COUNT,
                "min_count": FIELD_MIN_COUNT
            }},
            {OP_SORT: {"timestamp": 1}}
        ]
        results = await MongoDB.database.platform_analytics.aggregate(pipeline).to_list(None)
        data_source = "platform_analytics"

    # Fallback to raw analytics for any zone type (BOOKING or empty pre-aggregated data)
    if not results:
        # Get cameras in this zone
        cursor = MongoDB.database.cameras.find({"zone_id": zone_id}, {"camera_id": 1})
        cameras = await cursor.to_list(length=50)
        camera_ids = [c["camera_id"] for c in cameras]

        if camera_ids:
            ALIGNMENT_WINDOW_MS = 2000
            pipeline = [
                {OP_MATCH: {
                    "camera_id": {"$in": camera_ids},
                    "timestamp": {"$gte": start_dt, "$lte": end_dt}
                }},
                {OP_GROUP: {
                    "_id": {
                        "camera_id": FIELD_CAMERA_ID,
                        "time_bucket": {OP_TO_DATE: {OP_SUBTRACT: [
                            {OP_TO_LONG: FIELD_TIMESTAMP},
                            {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, ALIGNMENT_WINDOW_MS]}
                        ]}}
                    },
                    "cam_count": {"$avg": FIELD_PEOPLE_COUNT}
                }},
                {OP_GROUP: {
                    "_id": FIELD_ID_TIME_BUCKET,
                    "total_load": {"$sum": FIELD_CAM_COUNT}
                }},
                {OP_GROUP: {
                    "_id": {OP_TO_DATE: {OP_SUBTRACT: [
                        {OP_TO_LONG: "$_id"},
                        {"$mod": [{OP_TO_LONG: "$_id"}, interval_ms]}
                    ]}},
                    "peak_count": {"$max": FIELD_TOTAL_LOAD},
                    "avg_count": {"$avg": FIELD_TOTAL_LOAD},
                    "min_count": {"$min": FIELD_TOTAL_LOAD},
                    "samples": {"$sum": 1}
                }},
                {OP_PROJECT: {
                    "_id": 0,
                    "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                    "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "peak_count": {OP_ROUND: [FIELD_PEAK_COUNT, 0]},
                    "min_count": {OP_ROUND: [FIELD_MIN_COUNT, 0]}
                }},
                {OP_SORT: {"timestamp": 1}}
            ]
            results = await MongoDB.database.analytics.aggregate(pipeline).to_list(None)
            data_source = "raw_analytics_recalculated"

    # Overall peak
    overall_peak = max((r.get("peak_count", 0) for r in results), default=0)

    return {
        "status": "success",
        "zone_id": zone_id,
        "zone_type": zone_type,
        "interval": interval,
        "overall_peak": overall_peak,
        "data": results,
        "source": data_source
    }


@router.get(
    "/analytics/station/history",
    responses={**SERVICE_UNAVAILABLE_RESPONSES, **MISSING_PARAMS_RESPONSES, **INVALID_TIMESTAMP_RESPONSES}
)
async def get_station_history(
    station_id: str = "HYB",
    start: str = None,
    end: str = None,
    interval: str = "5m"
):
    """
    Get station-wide historical people count with zone_type breakdown.

    Args:
        station_id: Station identifier (default: "HYB")
        start: Start timestamp (ISO 8601)
        end: End timestamp (ISO 8601)
        interval: Data resolution (1m, 5m, 1h, 1d)
    """
    if MongoDB.database is None:
        raise HTTPException(503, ERR_DATABASE_NOT_AVAILABLE)

    if not start or not end:
        raise HTTPException(400, "start and end are required")

    try:
        start_dt = datetime.fromisoformat(start.replace('Z', ISO_UTC_SUFFIX))
        end_dt = datetime.fromisoformat(end.replace('Z', ISO_UTC_SUFFIX))
    except ValueError:
        raise HTTPException(400, ERR_INVALID_TIMESTAMP_FORMAT)

    interval_ms = parse_interval_to_ms(interval)

    # Query station_analytics
    pipeline = [
        {OP_MATCH: {
            "station_id": station_id,
            "timestamp": {"$gte": start_dt, "$lte": end_dt}
        }},
        {OP_GROUP: {
            "_id": {OP_TO_DATE: {OP_SUBTRACT: [
                {OP_TO_LONG: FIELD_TIMESTAMP},
                {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, interval_ms]}
            ]}},
            "avg_count": {"$avg": FIELD_TOTAL_PEOPLE_COUNT},
            "peak_count": {"$max": FIELD_TOTAL_PEOPLE_COUNT},
            "min_count": {"$min": FIELD_TOTAL_PEOPLE_COUNT},
            "avg_fob": {"$avg": "$zone_type_breakdown.FOB"},
            "avg_platform": {"$avg": "$zone_type_breakdown.PLATFORM"},
            "avg_booking": {"$avg": "$zone_type_breakdown.BOOKING"},
            "samples": {"$sum": 1}
        }},
        {OP_PROJECT: {
            "_id": 0,
            "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
            "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
            "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
            "peak_count": FIELD_PEAK_COUNT,
            "min_count": FIELD_MIN_COUNT,
            "zone_type_breakdown": {
                "FOB": {OP_ROUND: [{"$ifNull": ["$avg_fob", 0]}, 0]},
                "PLATFORM": {OP_ROUND: [{"$ifNull": ["$avg_platform", 0]}, 0]},
                "BOOKING": {OP_ROUND: [{"$ifNull": ["$avg_booking", 0]}, 0]}
            }
        }},
        {OP_SORT: {"timestamp": 1}}
    ]

    results = await MongoDB.database.station_analytics.aggregate(pipeline).to_list(None)
    data_source = "station_analytics"

    # Fallback to raw analytics if no pre-aggregated data
    if not results:
        # Get all cameras for this station
        cursor = MongoDB.database.cameras.find(
            {"station_id": station_id},
            {"camera_id": 1}
        )
        cameras = await cursor.to_list(length=100)

        if not cameras:
            # Try via fob_type fallback
            cursor = MongoDB.database.cameras.find(
                {"fob_type": station_id},
                {"camera_id": 1}
            )
            cameras = await cursor.to_list(length=100)

        camera_ids = [c["camera_id"] for c in cameras]
        if camera_ids:
            ALIGNMENT_WINDOW_MS = 2000
            pipeline = [
                {OP_MATCH: {
                    "camera_id": {"$in": camera_ids},
                    "timestamp": {"$gte": start_dt, "$lte": end_dt}
                }},
                {OP_GROUP: {
                    "_id": {
                        "camera_id": FIELD_CAMERA_ID,
                        "time_bucket": {OP_TO_DATE: {OP_SUBTRACT: [
                            {OP_TO_LONG: FIELD_TIMESTAMP},
                            {"$mod": [{OP_TO_LONG: FIELD_TIMESTAMP}, ALIGNMENT_WINDOW_MS]}
                        ]}}
                    },
                    "cam_count": {"$avg": FIELD_PEOPLE_COUNT}
                }},
                {OP_GROUP: {
                    "_id": FIELD_ID_TIME_BUCKET,
                    "total_load": {"$sum": FIELD_CAM_COUNT}
                }},
                {OP_GROUP: {
                    "_id": {OP_TO_DATE: {OP_SUBTRACT: [
                        {OP_TO_LONG: "$_id"},
                        {"$mod": [{OP_TO_LONG: "$_id"}, interval_ms]}
                    ]}},
                    "peak_count": {"$max": FIELD_TOTAL_LOAD},
                    "avg_count": {"$avg": FIELD_TOTAL_LOAD},
                    "min_count": {"$min": FIELD_TOTAL_LOAD},
                    "samples": {"$sum": 1}
                }},
                {OP_PROJECT: {
                    "_id": 0,
                    "timestamp": {OP_DATE_TO_STRING: {"format": ISO_DATE_FORMAT, "date": "$_id"}},
                    "count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "avg_count": {OP_ROUND: [FIELD_AVG_COUNT, 0]},
                    "peak_count": {OP_ROUND: [FIELD_PEAK_COUNT, 0]},
                    "min_count": {OP_ROUND: [FIELD_MIN_COUNT, 0]}
                }},
                {OP_SORT: {"timestamp": 1}}
            ]
            results = await MongoDB.database.analytics.aggregate(pipeline).to_list(None)
            data_source = "raw_analytics_recalculated"

    overall_peak = max((r.get("peak_count", 0) for r in results), default=0)

    return {
        "status": "success",
        "station_id": station_id,
        "interval": interval,
        "overall_peak": overall_peak,
        "data": results,
        "source": data_source
    }


@router.get(
    "/analytics/{job_id}",
    dependencies=[require_authorized],
    responses=ANALYTICS_NOT_FOUND_RESPONSES
)
async def get_analytics(job_id: str):
    """Get frame-by-frame analytics"""
    analytics_path = os.path.join(settings.output_dir, f"{job_id}_analytics.json")

    if not os.path.exists(analytics_path):
        raise HTTPException(404, ERR_ANALYTICS_NOT_FOUND)

    async with aiofiles.open(analytics_path, 'r') as f:
        data = json.loads(await f.read())

    return JSONResponse(data)


@router.get(
    "/analytics/{job_id}/{frame_number}",
    dependencies=[require_authorized],
    responses=HEATMAP_NOT_FOUND_RESPONSES
)
async def get_heatmap(job_id: str, frame_number: int):
    """Get density heatmap for specific frame"""
    heatmap_path = os.path.join(settings.heatmap_dir, f"{job_id}_frame_{frame_number:06d}.png")

    if not os.path.exists(heatmap_path):
        raise HTTPException(404, ERR_HEATMAP_NOT_FOUND)
    
    return FileResponse(
        heatmap_path,
        media_type='image/png',
        headers={'Content-Disposition': f'inline; filename="heatmap_{job_id}_{frame_number}.png"'}
    )
