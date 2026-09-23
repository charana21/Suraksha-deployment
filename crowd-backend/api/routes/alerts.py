"""
Alerts API endpoints
Provides access to historical and active alerts
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta, timezone
from typing import Optional
import re
from db.mongodb import MongoDB
from api.security import require_authorized
logger = logging.getLogger(__name__)

DB_ERROR_MSG = "Database not available"
ALERT_NOT_FOUND_MSG = "Alert not found"
MONGO_SORT = "$sort"
MONGO_GROUP = "$group"
MONGO_ARRAY_ELEM_AT = "$arrayElemAt"
MONGO_IF_NULL = "$ifNull"
TIMESTAMP_FIELD = "$timestamp"

DB_ERROR_RESPONSE = {503: {"description": DB_ERROR_MSG}}
ALERT_NOT_FOUND_RESPONSE = {404: {"description": ALERT_NOT_FOUND_MSG}}
INTERNAL_ERROR_RESPONSE = {500: {"description": "Internal Server Error"}}


def parse_time_range(range_str: str) -> int:
    """Convert range string (e.g. '7d', '24h') to hours"""
    if range_str.endswith('d'):
        return int(range_str[:-1]) * 24
    elif range_str.endswith('h'):
        return int(range_str[:-1])
    return 24  # Default

def _add_validated_filter(query: dict, key: str, value: Optional[str], valid_values: list, error_msg: str):
    if value:
        if value not in valid_values:
            raise HTTPException(status_code=400, detail=error_msg)
        query[key] = value


def _serialize_alert(alert: dict) -> dict:
    alert["_id"] = str(alert["_id"])
    if alert.get("image_id"):
        alert["image_id"] = str(alert["image_id"])
    return alert


def _serialize_alerts(alerts: list) -> list:
    return [_serialize_alert(alert) for alert in alerts]


async def _resolve_camera_name_clause(camera_name: str) -> dict:
    """Build an $and clause matching alerts by camera name substring (case-insensitive)."""
    escaped = re.escape(camera_name)
    name_regex = {"$regex": escaped, "$options": "i"}
    matched_cameras = await MongoDB.database.cameras.find(
        {"name": name_regex}, {"camera_id": 1}
    ).to_list(length=None)
    matched_camera_ids = [c["camera_id"] for c in matched_cameras if c.get("camera_id")]
    return {"$or": [
        {"camera_id": {"$in": matched_camera_ids}},
        {"camera_name": name_regex}
    ]}


router = APIRouter()


@router.get("/alerts", tags=["Alerts"], responses={
    503: {"description": DB_ERROR_MSG},
    400: {"description": "Invalid filter parameters"}
})
async def list_alerts(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (MEDIUM/HIGH/CRITICAL)"),
    status: Optional[str] = Query(None, description="Filter by status (triggered/acknowledged/resolved)"),
    zone_type: Optional[str] = Query(None, description="Filter by zone type (FOB/PLATFORM/BOOKING)"),
    zone_id: Optional[str] = Query(None, description="Filter by zone ID (e.g. zone_hyb_fob)"),
    camera_name: Optional[str] = Query(None, description="Search by camera name (case-insensitive, matches this value anywhere in the name)"),
    hours: int = Query(24, ge=1, description="Time range in hours (default: 24)"),
    page: int = Query(1, ge=1, description="Page number to return"),
    pagesize: int = Query(100, ge=1, le=200, description="Number of alerts per page"),
    limit: Optional[int] = Query(None, ge=1, le=5000, description="Deprecated alias for pagesize")
):
    """
    List alerts with filters

    - **camera_id**: Filter by camera
    - **severity**: Filter by severity level (MEDIUM, HIGH, CRITICAL)
    - **status**: Filter by status (triggered, acknowledged, resolved)
    - **zone_type**: Filter by zone type (FOB, PLATFORM, BOOKING)
    - **zone_id**: Filter by specific zone ID
    - **camera_name**: Search by camera name, case-insensitive substring match (e.g. "10" matches "Platform 10 Camera", "mi" matches "Mid Platform")
    - **hours**: Time range (default: last 24 hours)
    - **limit**: Maximum results (default: 100)

    Returns alerts sorted by timestamp (newest first)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    # Build query
    query = {}

    if camera_id:
        query["camera_id"] = camera_id

    _add_validated_filter(query, "severity", severity, ["MEDIUM", "HIGH", "CRITICAL"], "Invalid severity. Must be: MEDIUM, HIGH, or CRITICAL")
    _add_validated_filter(query, "status", status, ["triggered", "acknowledged", "resolved"], "Invalid status. Must be: triggered, acknowledged, or resolved")
    _add_validated_filter(query, "zone_type", zone_type, ["FOB", "PLATFORM", "BOOKING"], "Invalid zone_type. Must be: FOB, PLATFORM, or BOOKING")

    if zone_id:
        query["zone_id"] = zone_id

    # Time range
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # MIXED TYPE SUPPORT: Handle both Date objects (new) and Strings (legacy)
    # This ensures both the manual test alerts and real system alerts appear
    query["$or"] = [
        {"timestamp": {"$gte": cutoff}},
        {"timestamp": {"$gte": cutoff.isoformat()}}
    ]

    # SEARCH: Case-insensitive "contains" match on camera name.
    # Resolve matching camera_ids from the small `cameras` collection first,
    # then filter alerts on the indexed camera_id (or the alert's own
    # camera_name, for alerts that already store it directly) instead of
    # joining every alert in the time range against `cameras`.
    if camera_name:
        query["$and"] = [await _resolve_camera_name_clause(camera_name)]

    effective_pagesize = limit if limit is not None else pagesize

    total_count = await MongoDB.database.alerts.count_documents(query)
    skip = (page - 1) * effective_pagesize

    # Aggregation Pipeline for Lookup
    pipeline = [
        {"$match": query},
        {MONGO_SORT: {"timestamp": -1}},
        {"$skip": skip},
        {"$limit": effective_pagesize},

        # JOIN with cameras to get name/fob_type if missing
        {
            "$lookup": {
                "from": "cameras",
                "localField": "camera_id",
                "foreignField": "camera_id",
                "as": "camera_info"
            }
        },

        # ENRICHMENT: Add camera_name/fob_id/zone_id/zone_type if missing in alert
        {
            "$addFields": {
                "camera_name": {
                    MONGO_IF_NULL: ["$camera_name", {MONGO_ARRAY_ELEM_AT: ["$camera_info.name", 0]}]
                },
                "fob_id": {
                    MONGO_IF_NULL: ["$fob_id", {MONGO_ARRAY_ELEM_AT: ["$camera_info.fob_type", 0]}]
                },
                "zone_id": {
                    MONGO_IF_NULL: ["$zone_id", {MONGO_ARRAY_ELEM_AT: ["$camera_info.zone_id", 0]}]
                },
                "zone_type": {
                    MONGO_IF_NULL: ["$zone_type", {MONGO_ARRAY_ELEM_AT: ["$camera_info.zone_type", 0]}]
                }
            }
        },

        # CLEANUP: Remove lookup array
        {"$project": {"camera_info": 0}}
    ]

    # Execute Aggregation
    cursor = MongoDB.database.alerts.aggregate(pipeline)
    alerts = _serialize_alerts(await cursor.to_list(length=limit))

    return {
        "status": "success",
        "count": len(alerts),
        "alerts": alerts,
        "query": {
            "camera_id": camera_id,
            "severity": severity,
            "status": status,
            "zone_type": zone_type,
            "zone_id": zone_id,
            "camera_name": camera_name,
            "hours": hours,
            "limit": limit
        }
    }


@router.get("/alerts/active", tags=["Alerts"], responses={503: {"description": DB_ERROR_MSG}})
async def get_active_alerts():
    """
    Get all active (unresolved) alerts

    Returns alerts with status="triggered" sorted by timestamp (newest first)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    cursor = MongoDB.database.alerts.find(
        {"status": "triggered"}
    ).sort("timestamp", -1)

    alerts = _serialize_alerts(await cursor.to_list(length=100))

    return {
        "status": "success",
        "count": len(alerts),
        "alerts": alerts
    }


@router.get("/alerts/{alert_id}", tags=["Alerts"], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": ALERT_NOT_FOUND_MSG}
})
async def get_alert(alert_id: str):
    """
    Get specific alert by ID

    - **alert_id**: Alert identifier (UUID)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    alert = await MongoDB.database.alerts.find_one({"alert_id": alert_id})

    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {
        "status": "success",
        "alert": _serialize_alert(alert)
    }


@router.post("/alerts/{alert_id}/acknowledge", tags=["Alerts"], dependencies=[require_authorized], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": ALERT_NOT_FOUND_MSG}
})
async def acknowledge_alert(alert_id: str):
    """
    Acknowledge an alert (mark as acknowledged)

    - **alert_id**: Alert identifier (UUID)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    result = await MongoDB.database.alerts.update_one(
        {"alert_id": alert_id},
        {
            "$set": {
                "status": "acknowledged",
                "acknowledged_at": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {
        "status": "success",
        "message": f"Alert {alert_id} acknowledged",
        "alert_id": alert_id
    }


@router.post("/alerts/{alert_id}/resolve", tags=["Alerts"], dependencies=[require_authorized], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": ALERT_NOT_FOUND_MSG}
})
async def resolve_alert(alert_id: str):
    """
    Resolve an alert (mark as resolved)

    - **alert_id**: Alert identifier (UUID)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    result = await MongoDB.database.alerts.update_one(
        {"alert_id": alert_id},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {
        "status": "success",
        "message": f"Alert {alert_id} resolved",
        "alert_id": alert_id
    }



@router.post("/alerts/test", tags=["Alerts"], dependencies=[require_authorized], responses={
    503: {"description": DB_ERROR_MSG},
    500: {"description": "Internal Server Error"}
})
async def trigger_test_alert(
    camera_id: str = Query("test_cam_01", description="Camera ID to associate with alert"),
    severity: str = Query("CRITICAL", description="Severity (MEDIUM/HIGH/CRITICAL)")
):
    """
    Manually trigger a test alert for debugging (DB only, no email)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    import uuid
    alert_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    alert_data = {
        "alert_id": alert_id,
        "camera_id": camera_id,
        "timestamp": timestamp,
        "timestamp_iso": timestamp.isoformat(),
        "severity": severity,
        "trigger_reason": "MANUAL TEST: Triggered via API",
        "risk_score": 95.0 if severity == "CRITICAL" else 75.0,
        "people_count": 100,
        "density_avg": 10.5,
        "motion_intensity": 5.0,
        "status": "triggered",
        "frame_number": 0,
        "has_image": False
    }

    try:
        await MongoDB.database.alerts.insert_one(alert_data)
        return {
            "status": "success",
            "message": "Test alert created",
            "alert_id": alert_id,
            "data": alert_data
        }
    except Exception as e:
        logger.exception("Failed to create test alert")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/test-email", tags=["Alerts"], responses={
    500: {"description": "Internal Server Error"}
})
async def test_email_alert(
    severity: str = Query("HIGH", description="Severity (HIGH/CRITICAL)"),
    camera_name: str = Query("Test Camera", description="Camera name for email"),
    location: str = Query("Platform 1, Test Location", description="Location for email")
):
    """
    Send a TEST email alert to verify email configuration is working.

    This endpoint:
    1. Creates a fake alert with provided details
    2. Sends an actual email via the notification service
    3. Does NOT save to database

    Use this to verify your email settings (.env) are correct.
    """
    from services.notification_service import NotificationService
    from config.config import get_settings
    import uuid

    settings = get_settings()

    # Check if email is enabled
    if not settings.email_alerts_enabled:
        return {
            "status": "error",
            "message": "Email alerts are disabled. Set EMAIL_ALERTS_ENABLED=true in .env"
        }

    # Check if receiver emails are set
    if not settings.alert_receiver_emails_list:
        return {
            "status": "error",
            "message": "No receiver emails configured. Set ALERT_RECEIVER_EMAILS in .env (comma-separated)"
        }

    # Create test alert data
    timestamp = datetime.now(timezone.utc)
    alert_data = {
        "alert_id": str(uuid.uuid4()),
        "camera_id": "test_camera_email",
        "camera_name": camera_name,
        "location": location,
        "fob_id": "TEST",
        "timestamp": timestamp,
        "timestamp_iso": timestamp.isoformat(),
        "severity": severity,
        "trigger_reason": "TEST EMAIL: Verifying email configuration",
        "risk_score": 95.0 if severity == "CRITICAL" else 75.0,
        "people_count": 150,
        "density_avg": 12.5,
        "density_level": "Very High" if severity == "CRITICAL" else "High",
        "motion_intensity": 8.5,
        "status": "triggered",
        "frame_number": 0,
        "has_image": False
    }

    try:
        # Get notification service and send email (skip_checks=True for testing)
        notification_service = NotificationService.get_instance()
        result = await notification_service.send_email_alert(alert_data, skip_checks=True)

        if result.get("status") == "sent":
            return {
                "status": "success",
                "message": f"Test email sent successfully to {settings.alert_receiver_emails_list}",
                "provider": settings.email_provider,
                "recipients": settings.alert_receiver_emails_list,
                "alert_data": {
                    "severity": severity,
                    "camera_name": camera_name,
                    "location": location
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Email failed: {result.get('error', 'Unknown error')}",
                "details": result
            }

    except Exception as e:
        logger.exception("Test email alert failed")
        raise HTTPException(status_code=500, detail=f"Email test failed: {str(e)}")


@router.get("/alerts/camera/{camera_id}/summary", tags=["Alerts"], responses={503: {"description": DB_ERROR_MSG}})
async def get_camera_alerts_summary(
    camera_id: str,
    hours: int = Query(24, description="Time range in hours")
):
    """
    Get alert summary for specific camera

    - **camera_id**: Camera identifier
    - **hours**: Time range (default: 24 hours)

    Returns:
    - Total alerts
    - Alerts by severity
    - Alerts by status
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Get all alerts for camera in time range
    # Mixed type support
    cursor = MongoDB.database.alerts.find({
        "camera_id": camera_id,
        "$or": [
            {"timestamp": {"$gte": cutoff}},
            {"timestamp": {"$gte": cutoff.isoformat()}}
        ]
    })

    alerts = await cursor.to_list(length=1000)

    # Count by severity
    severity_counts = {"MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    status_counts = {"triggered": 0, "acknowledged": 0, "resolved": 0}

    for alert in alerts:
        severity = alert.get("severity")
        status = alert.get("status")

        if severity in severity_counts:
            severity_counts[severity] += 1

        if status in status_counts:
            status_counts[status] += 1

    return {
        "status": "success",
        "camera_id": camera_id,
        "time_range_hours": hours,
        "total_alerts": len(alerts),
        "by_severity": severity_counts,
        "by_status": status_counts
    }


@router.get("/alerts/report/stats", tags=["Alerts"], responses={
    503: {"description": DB_ERROR_MSG},
    500: {"description": "Internal Server Error"}
})
async def get_alert_stats(
    time_range: str = Query("7d", alias="range", description="Time range (e.g. '24h', '7d', '30d')")
):
    """
    Get comprehensive alert analytics report

    Returns:
    - **summary**: Total, Critical, Avg/Day, Peak Hour
    - **daily_trend**: Alerts per day
    - **severity_distribution**: Count by severity
    - **top_cameras**: Top 5 cameras by alert count
    - **hourly_distribution**: Frequency by hour of day (0-23)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    hours = parse_time_range(time_range)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    pipeline = [
        {"$match": {
            "$or": [
                {"timestamp": {"$gte": cutoff}},
                {"timestamp": {"$gte": cutoff.isoformat()}}
            ]
        }},
        # NORMALIZE TIMESTAMP: Convert strings to Date objects if needed
        # This allows aggregations to work on mixed data types
        {"$addFields": {
            "timestamp": {"$toDate": TIMESTAMP_FIELD}
        }},
        {"$facet": {
            # 1. Severity Distribution & Critical Count
            "severity_counts": [
                {MONGO_GROUP: {"_id": "$severity", "count": {"$sum": 1}}}
            ],

            # 2. Daily Trend
            "daily_trend": [
                {
                    MONGO_GROUP: {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": TIMESTAMP_FIELD}
                        },
                        "count": {"$sum": 1},
                        "critical": {
                            "$sum": {"$cond": [{"$eq": ["$severity", "CRITICAL"]}, 1, 0]}
                        }
                    }
                },
                {MONGO_SORT: {"_id": 1}}
            ],

            # 3. Top Cameras
            "top_cameras": [
                {MONGO_GROUP: {"_id": "$camera_id", "count": {"$sum": 1}}},
                {MONGO_SORT: {"count": -1}},
                {"$limit": 5}
            ],

            # 4. Hourly Distribution (Peak Hour)
            "hourly_distribution": [
                {
                    MONGO_GROUP: {
                        "_id": {"$hour": TIMESTAMP_FIELD},
                        "count": {"$sum": 1}
                    }
                },
                {MONGO_SORT: {"_id": 1}}
            ],

            # 5. Zone Type Distribution
            "zone_type_counts": [
                {MONGO_GROUP: {"_id": "$zone_type", "count": {"$sum": 1}}}
            ]
        }}
    ]

    try:
        results = await MongoDB.database.alerts.aggregate(pipeline).to_list(length=1)
        data = results[0]

        # Process Severity
        severity_map = {item["_id"]: item["count"] for item in data["severity_counts"]}
        total_alerts = sum(severity_map.values())
        critical_incidents = severity_map.get("CRITICAL", 0)

        # Process Daily Trend
        # Fill missing days if needed (simplified here to just return data)
        daily_trend = []
        for item in data["daily_trend"]:
            daily_trend.append({
                "date": item["_id"],
                "total": item["count"],
                "critical": item["critical"]
            })

        # Calculate Avg Alerts/Day
        num_days = max(1, hours / 24)
        avg_alerts_day = round(total_alerts / num_days, 1)

        # Process Hourly & Find Peak
        hourly_map = {i: 0 for i in range(24)}
        peak_hour = "00:00"
        max_hourly_count = 0

        for item in data["hourly_distribution"]:
            hour = item["_id"]
            count = item["count"]
            hourly_map[hour] = count

            if count > max_hourly_count:
                max_hourly_count = count
                peak_hour = f"{hour:02d}:00"

        hourly_trend = [{"hour": f"{h:02d}:00", "count": c} for h, c in hourly_map.items()]

        # Format Top Cameras
        top_cameras = [
            {"camera_id": item["_id"], "count": item["count"]}
            for item in data["top_cameras"]
        ]

        # Process Zone Type Distribution
        zone_type_distribution = {
            item["_id"]: item["count"]
            for item in data.get("zone_type_counts", [])
            if item["_id"]  # Skip None zone_type (legacy alerts)
        }

        return {
            "status": "success",
            "range": time_range,
            "summary": {
                "total_alerts": total_alerts,
                "critical_incidents": critical_incidents,
                "avg_alerts_per_day": avg_alerts_day,
                "peak_hour": peak_hour
            },
            "daily_trend": daily_trend,
            "severity_distribution": severity_map,
            "zone_type_distribution": zone_type_distribution,
            "top_cameras": top_cameras,
            "hourly_distribution": hourly_trend
        }

    except Exception as e:
        logger.exception("Aggregation error")
        raise HTTPException(status_code=500, detail=str(e))
