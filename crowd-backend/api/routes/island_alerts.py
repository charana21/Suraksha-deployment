"""
Island Platform Alert API Routes

RESTful API endpoints for island platform footfall risk detection.
Phase-1: Historical + planning-based early warning system.
"""

import time
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from services.island_alert_service import island_alert_service
from services.platform_history_service import platform_history_service
from api.security import require_authorized, require_admin
from models.schemas import (
    GenerateAlertsRequest,
    GenerateAlertsResponse,
    ListAlertsResponse,
    AlertActionResponse,
    IslandAlertSummary,
    PlatformHistoryStats
)
from utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

INTERNAL_ERROR_DESC = "Internal Server Error"
BAD_REQUEST_DESC = "Invalid request parameters"
ALERT_NOT_FOUND_DESC = "Alert not found"

# Alert datetime fields that need ISO-string conversion before being sent in a JSON response
_ALERT_DATETIME_FIELDS = (
    "window_start",
    "window_end",
    "created_at",
    "updated_at",
    "acknowledged_at",
    "resolved_at",
)


def _serialize_alert(alert: dict) -> dict:
    """Convert datetime fields on an alert dict to ISO strings and drop the Mongo _id."""
    for field in _ALERT_DATETIME_FIELDS:
        value = alert.get(field)
        if isinstance(value, datetime):
            alert[field] = value.isoformat()
    alert.pop('_id', None)
    return alert


def _parse_date_or_400(value: str, error_prefix: str = "Invalid date format") -> date:
    """Parse an ISO date string, raising a documented 400 on failure."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{error_prefix}: {value}")


# ============================================================================
# ALERT GENERATION
# ============================================================================

@router.post(
    "/island-alerts/generate",
    response_model=GenerateAlertsResponse,
    dependencies=[require_authorized],
    responses={
        400: {"description": BAD_REQUEST_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def generate_island_alerts(request: GenerateAlertsRequest):
    """
    Generate island platform footfall alerts for specified date(s).

    This endpoint analyzes train schedules and platform history to detect
    potential congestion risks on island platforms.

    **Request Body:**
    - `start_date`: Start date (YYYY-MM-DD)
    - `end_date`: End date (optional, defaults to start_date)

    **Response:**
    - `status`: "success" or "error"
    - `dates_processed`: List of dates processed
    - `alerts_created`: Total number of alerts created
    - `execution_time_seconds`: Processing time
    - `errors`: Any errors encountered during processing

    **Example:**
    ```json
    {
      "start_date": "2026-01-14",
      "end_date": "2026-01-15"
    }
    ```
    """
    try:
        start_time = time.time()

        # Parse dates
        try:
            start_date_obj = date.fromisoformat(request.start_date)
            end_date_obj = date.fromisoformat(request.end_date) if request.end_date else start_date_obj
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format. Use YYYY-MM-DD: {e}"
            )

        if end_date_obj < start_date_obj:
            raise HTTPException(
                status_code=400,
                detail="end_date must be >= start_date"
            )

        # Limit date range to avoid excessive processing
        date_diff = (end_date_obj - start_date_obj).days
        if date_diff > 30:
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 30 days"
            )

        # Generate alerts for each date
        dates_processed = []
        total_alerts_created = 0
        all_errors = []

        current_date = start_date_obj
        while current_date <= end_date_obj:
            result = await island_alert_service.generate_alerts_for_day(current_date)

            dates_processed.append(str(current_date))
            total_alerts_created += result.get('alerts_created', 0)
            all_errors.extend(result.get('errors', []))

            current_date += timedelta(days=1)

        execution_time = time.time() - start_time

        return GenerateAlertsResponse(
            status="success",
            dates_processed=dates_processed,
            alerts_created=total_alerts_created,
            execution_time_seconds=round(execution_time, 2),
            errors=all_errors[:100]  # Limit to first 100 errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating island alerts")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ALERT QUERIES
# ============================================================================

@router.get(
    "/island-alerts",
    response_model=ListAlertsResponse,
    responses={
        400: {"description": BAD_REQUEST_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def list_island_alerts(
    island_id: Optional[str] = Query(None, description="Filter by island (e.g., 'island_2_3')"),
    status: Optional[str] = Query(None, description="Filter by status (triggered/acknowledged/resolved)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (MEDIUM/HIGH/CRITICAL)"),
    start_date: Optional[str] = Query(None, description="Filter by window_start >= date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter by window_start <= date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    List island platform alerts with optional filters.

    **Query Parameters:**
    - `island_id`: Filter by specific island (e.g., "island_2_3")
    - `status`: Filter by alert status (triggered, acknowledged, resolved)
    - `risk_level`: Filter by risk level (MEDIUM, HIGH, CRITICAL)
    - `start_date`: Show alerts with window_start >= this date
    - `end_date`: Show alerts with window_start <= this date
    - `limit`: Results per page (1-200, default: 50)
    - `offset`: Pagination offset

    **Response:**
    - `count`: Number of alerts in this page
    - `total`: Total alerts matching filters
    - `alerts`: List of alert documents

    **Example:**
    ```
    GET /api/island-alerts?island_id=island_2_3&status=triggered&limit=20
    ```
    """
    try:
        # Parse dates if provided
        start_date_obj = _parse_date_or_400(start_date, "Invalid start_date format") if start_date else None
        end_date_obj = _parse_date_or_400(end_date, "Invalid end_date format") if end_date else None

        # Query alerts
        result = await island_alert_service.list_alerts(
            island_id=island_id,
            status=status,
            risk_level=risk_level,
            start_date=start_date_obj,
            end_date=end_date_obj,
            limit=limit,
            offset=offset
        )

        # Convert datetime objects to ISO strings for JSON serialization
        for alert in result['alerts']:
            _serialize_alert(alert)

        return ListAlertsResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing island alerts")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/island-alerts/summary",
    response_model=IslandAlertSummary,
    responses={
        400: {"description": BAD_REQUEST_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_island_alert_summary(
    date_param: Optional[str] = Query(None, alias="date", description="Date YYYY-MM-DD (default: today)")
):
    """
    Get daily summary statistics for island alerts.

    **Query Parameters:**
    - `date`: Date to summarize (YYYY-MM-DD), defaults to today

    **Response:**
    - `total_alerts`: Total alerts for the day
    - `by_island`: Alert counts per island
    - `by_risk_level`: Alert counts per risk level
    - `by_status`: Alert counts per alert status
    - `peak_hours`: Hours with most alerts

    **Example:**
    ```
    GET /api/island-alerts/summary?date=2026-01-14
    ```
    """
    try:
        # Parse date
        target_date = _parse_date_or_400(date_param, "Invalid date format") if date_param else date.today()

        # Get summary
        summary = await island_alert_service.get_daily_summary(target_date)

        return IslandAlertSummary(**summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting alert summary")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/island-alerts/live",
    responses={500: {"description": INTERNAL_ERROR_DESC}},
)
async def get_live_island_alerts(
    hours_ahead: int = Query(2, ge=1, le=12, description="Hours to look ahead")
):
    """
    Get active alerts for current time + next N hours.

    Returns upcoming and active alerts that require attention.
    Useful for real-time monitoring dashboards.

    **Query Parameters:**
    - `hours_ahead`: Hours to look ahead (1-12, default: 2)

    **Response:**
    - `current_time`: Current server time
    - `window_end`: End of lookahead window
    - `count`: Number of active alerts
    - `alerts`: List of alert documents

    **Example:**
    ```
    GET /api/island-alerts/live?hours_ahead=2
    ```
    """
    try:
        result = await island_alert_service.get_live_alerts(hours_ahead)

        # Convert datetime objects to ISO strings
        for alert in result.get('alerts', []):
            _serialize_alert(alert)

        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Error getting live alerts")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/island-alerts/{alert_id}",
    responses={
        404: {"description": ALERT_NOT_FOUND_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_island_alert(alert_id: str):
    """
    Get detailed information for a specific alert.

    **Path Parameters:**
    - `alert_id`: Alert UUID

    **Response:**
    Complete alert document including:
    - Alert metadata (island, time window, risk level)
    - Footfall metrics (total, threshold, exceeds_by)
    - Complete list of contributing trains with platform history
    - Certainty breakdown
    - Advisory message

    **Example:**
    ```
    GET /api/island-alerts/123e4567-e89b-12d3-a456-426614174000
    ```
    """
    try:
        alert = await island_alert_service.get_alert_by_id(alert_id)

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Convert datetime objects to ISO strings
        _serialize_alert(alert)

        return JSONResponse(content={
            "status": "success",
            "alert": alert
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting alert {alert_id}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ALERT ACTIONS
# ============================================================================

@router.post(
    "/island-alerts/{alert_id}/acknowledge",
    response_model=AlertActionResponse,
    dependencies=[require_authorized],
    responses={
        404: {"description": ALERT_NOT_FOUND_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def acknowledge_island_alert(alert_id: str):
    """
    Mark an alert as acknowledged.

    This indicates that operators have seen the alert and are aware of
    the potential congestion risk.

    **Path Parameters:**
    - `alert_id`: Alert UUID

    **Response:**
    - `status`: "success" or "error"
    - `alert_id`: Alert UUID
    - `acknowledged_at`: Timestamp when acknowledged

    **Alert Lifecycle:**
    ```
    triggered → acknowledged → resolved
    ```
    """
    try:
        result = await island_alert_service.acknowledge_alert(alert_id)

        if result['status'] == 'error':
            raise HTTPException(status_code=404, detail=result.get('message', 'Alert not found'))

        return AlertActionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error acknowledging alert {alert_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/island-alerts/{alert_id}/resolve",
    response_model=AlertActionResponse,
    dependencies=[require_authorized],
    responses={
        404: {"description": ALERT_NOT_FOUND_DESC},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def resolve_island_alert(alert_id: str):
    """
    Mark an alert as resolved.

    This indicates that the congestion risk has passed or has been
    addressed through operational interventions.

    **Path Parameters:**
    - `alert_id`: Alert UUID

    **Response:**
    - `status`: "success" or "error"
    - `alert_id`: Alert UUID
    - `resolved_at`: Timestamp when resolved
    """
    try:
        result = await island_alert_service.resolve_alert(alert_id)

        if result['status'] == 'error':
            raise HTTPException(status_code=404, detail=result.get('message', 'Alert not found'))

        return AlertActionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error resolving alert {alert_id}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PLATFORM HISTORY
# ============================================================================

@router.post(
    "/platform-history/load",
    dependencies=[require_admin],
    responses={
        404: {"description": "CSV file not found"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def load_platform_history(csv_path: str = Query(..., description="Path to CSV file")):
    """
    Load platform history from CSV file into MongoDB.

    **This endpoint should be called:**
    - On initial setup
    - Monthly to update platform patterns
    - After receiving updated platform occupation data

    **Query Parameters:**
    - `csv_path`: Absolute or relative path to CSV file

    **Response:**
    - `records_loaded`: New records inserted
    - `records_updated`: Existing records updated
    - `errors`: Any parsing errors encountered

    **CSV Format:**
    ```
    train_number,PF 1,PF 2,PF 3,...,total_occurrences,dominant_platform,dominant_count,stability_percent
    ```

    **Security Note:** In production, restrict this endpoint to admin users only.
    """
    try:
        result = await platform_history_service.load_platform_history_from_csv(csv_path)

        return JSONResponse(content={
            "status": "success",
            **result
        })

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error loading platform history")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/platform-history/stats",
    response_model=PlatformHistoryStats,
    responses={500: {"description": INTERNAL_ERROR_DESC}},
)
async def get_platform_history_stats():
    """
    Get statistics about the platform history collection.

    **Response:**
    - `total_trains`: Total trains in history
    - `stable_trains`: Trains with ≥80% platform stability
    - `unstable_trains`: Trains with <80% platform stability
    - `last_loaded_at`: When CSV was last loaded

    **Use this to:**
    - Verify platform history is loaded
    - Check data freshness
    - Understand platform stability distribution
    """
    try:
        stats = await platform_history_service.get_collection_stats()

        # Convert datetime to ISO string
        if stats.get('last_loaded_at') and isinstance(stats['last_loaded_at'], datetime):
            stats['last_loaded_at'] = stats['last_loaded_at'].isoformat()

        return PlatformHistoryStats(**stats)

    except Exception as e:
        logger.exception("Error getting platform history stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/platform-history/{train_number}",
    responses={
        404: {"description": "Train not found in platform history"},
        500: {"description": INTERNAL_ERROR_DESC},
    },
)
async def get_train_platform_history(train_number: str):
    """
    Get platform history for a specific train.

    **Path Parameters:**
    - `train_number`: Train identifier

    **Response:**
    - Platform occurrence counts
    - Dominant platform
    - Stability percentage
    - Certainty label

    **Use this to:**
    - Debug train platform assignments
    - Understand why a train appears on multiple islands
    - Verify platform history data quality
    """
    try:
        stability = await platform_history_service.get_platform_stability(train_number)

        if not stability['found']:
            raise HTTPException(
                status_code=404,
                detail=f"Train {train_number} not found in platform history"
            )

        history = await platform_history_service.get_train_platform_history(train_number)

        # Convert datetime to ISO string
        if history and 'loaded_at' in history and isinstance(history['loaded_at'], datetime):
            history['loaded_at'] = history['loaded_at'].isoformat()

        # Remove MongoDB _id
        if history:
            history.pop('_id', None)

        return JSONResponse(content={
            "status": "success",
            "train_number": train_number,
            "stability": stability,
            "history": history
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting platform history for train {train_number}")
        raise HTTPException(status_code=500, detail=str(e))