"""
Train schedule API endpoints
Provides Excel upload and upcoming trains query
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from datetime import UTC, datetime, timedelta
from services.train_schedule_service import TrainScheduleService
from services.calendar_upload_service import CalendarUploadService
from services.live_refresh_toggle_service import LiveTrainRefreshToggleService
from services.live_train_service import LiveTrainService
from services.websocket_manager import get_connection_manager
from services.whatsapp_optin_service import WhatsAppOptInService
from services.whatsapp_alert_service import WhatsAppNotificationService as WhatsAppTemplateService
from db.mongodb import MongoDB
from api.security import require_authorized, require_role, require_viewer, verify_token
from config.config import get_settings
import logging
logger= logging.getLogger(__name__)
logger = logging.getLogger(__name__)

router = APIRouter()

# Holds references to fire-and-forget background tasks so they aren't
# garbage-collected before completion.
_background_tasks: set[asyncio.Task] = set()

DB_NOT_AVAILABLE_DETAIL = "Database not available"
INVALID_DATE_FORMAT_DETAIL = "Invalid date format. Use YYYY-MM-DD"
DB_NOT_AVAILABLE_RESPONSE = {503: {"description": DB_NOT_AVAILABLE_DETAIL}}

class WhatsAppOptInRequest(BaseModel):
    phone_number: str = Field(..., min_length=7, max_length=25)
    full_name: Optional[str] = Field(None, max_length=100)
    enabled: bool = True


class WhatsAppTextAlertRequest(BaseModel):
    phone_number: str = Field(..., min_length=7, max_length=25)
    message: str = Field(..., min_length=1, max_length=2000)


class LiveTrainToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Enable live API refresh cycle")


class MSG91WebhookPayload(BaseModel):
    """MSG91 inbound WhatsApp webhook payload."""
    customerNumber: Optional[str] = Field(None, description="Sender phone number from MSG91 (e.g. 916304543584)")
    customer_number: Optional[str] = Field(None, description="Alternative sender phone field")
    text: Optional[str] = Field(None, description="Plain text reply (e.g. 'allow' or 'deny')")
    button: Optional[Any] = Field(None, description="Button click data from MSG91 (string or dict)")
    button_reply: Optional[Any] = Field(None, description="Button reply object from MSG91")
    interactive: Optional[Any] = Field(None, description="Interactive message data")
    content: Optional[Any] = Field(None, description="Content field")


async def _generate_island_alerts_background(dates_found: list):
    """Background task to generate island alerts for uploaded dates"""
    try:
        from config.config import get_settings
        from services.island_alert_service import island_alert_service
        from datetime import date

        settings = get_settings()
        if not settings.island_platform_detection_enabled:
            return

        logger.info(f"[IslandAlerts] Background: Generating alerts for {len(dates_found)} dates...")

        for date_str in dates_found:
            try:
                date_obj = date.fromisoformat(date_str)
                result = await island_alert_service.generate_alerts_for_day(date_obj)
                logger.info(f"[IslandAlerts] Background: Generated {result.get('alerts_created', 0)} alerts for {date_str}")
            except Exception:
                logger.exception(f"[IslandAlerts] Background: Failed for {date_str}")

        logger.info("[IslandAlerts] Background: Completed all dates")
    except Exception:
        logger.exception("[IslandAlerts] Background task failed")


@router.post(
    "/trains/upload",
    tags=["Trains"],
    dependencies=[require_role(["admin", "operator", "viewer"], methods=["POST"])],
    responses={
        400: {"description": "File must be Excel format (.xlsx or .xls)"},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def upload_train_schedule(
    file: UploadFile = File(..., description="Railway Excel file (.xlsx/.xls)"),
    replace_dates: bool = Query(False, description="Replace existing schedules for dates found in file")
):
    """
    Upload Railway train schedule Excel file.

    **Request:**
    - Content-Type: multipart/form-data
    - file: Excel file (.xlsx/.xls)
    - replace_dates: If true, delete existing schedules for dates found before inserting

    **Expected Excel Columns:**
    - Train: Train number
    - Train Name: Train name
    - Type: Train type (EXP, PASS, SF)
    - Src: Source station code
    - Dstn: Destination station code
    - Train Event: ORIGINATING/TERMINATING/THROUGH
    - Arrv: Arrival datetime (DD-MM-YYYY HH:MM)
    - Dep: Departure datetime (DD-MM-YYYY HH:MM)
    - Boarding: Passengers boarding
    - Deboarding: Passengers deboarding
    - Total: Total passengers
    - UTS: UTS ticket passengers

    **Duplicate Handling:**
    - If same (train_number + date + times) exists, updates other fields
    - If different, inserts new record
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be Excel format (.xlsx or .xls)")

    # Read file content
    content = await file.read()

    # Parse Excel
    parse_result = await TrainScheduleService.parse_excel(content, file.filename)

    if not parse_result["records"]:
        return {
            "status": "error",
            "message": "No valid records found in Excel file",
            "errors": parse_result["errors"],
            "records_processed": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "dates_found": parse_result["dates_found"]
        }

    # Optionally delete existing for dates
    if replace_dates:
        for date_str in parse_result["dates_found"]:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            deleted = await TrainScheduleService.delete_schedules_by_date(date_obj)
            print(f"[TrainSchedule] Deleted {deleted} existing records for {date_str}")
            logger.info(f"[TrainSchedule] Deleted {deleted} existing records for {date_str}")

    # Upsert records
    stats = await TrainScheduleService.upsert_schedules(parse_result["records"])

    # Broadcast schedule update via WebSocket
    try:
        manager = get_connection_manager()
        await manager.broadcast_train_schedule_update(
            event="schedule_uploaded",
            data={
                "filename": file.filename,
                "dates_affected": parse_result["dates_found"],
                "records_inserted": stats["inserted"],
                "records_updated": stats["updated"]
            }
        )
    except Exception:
        logger.exception("[TrainSchedule] WebSocket broadcast failed")

    # Auto-generate island platform alerts in BACKGROUND (don't block response)
    if parse_result["dates_found"]:
        task = asyncio.create_task(_generate_island_alerts_background(parse_result["dates_found"]))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return {
        "status": "success",
        "message": f"Processed {len(parse_result['records'])} train schedules",
        "records_processed": len(parse_result["records"]),
        "records_inserted": stats["inserted"],
        "records_updated": stats["updated"],
        "records_skipped": stats["skipped"],
        "dates_found": parse_result["dates_found"],
        "errors": parse_result["errors"][:10],  # Limit errors in response
        "island_alerts_generating": True  # Alerts generating in background
    }


@router.post(
    "/trains/upload-calendar",
    tags=["Trains"],
    dependencies=[require_role(["admin", "operator", "viewer"], methods=["POST"])],
    responses={
        400: {"description": "File must be an Excel/CSV file, or no valid records found"},
        500: {"description": "Calendar upload processing failed"},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def upload_calendar_excel(
    file: UploadFile = File(..., description="Calendar Excel file (.xlsx/.xls)")
):
    """
    Upload calendar Excel data into the calendar collection.

    Supported headers are matched flexibly, so names like:
    - Scheduled _Date
    - Train Number
    - Boarding Count
    - Deboarding Count

    will be accepted even when the exact field names differ.
    If a document with the same train_number + schedule_date already exists,
    the boarding/deboarding counts are updated in place.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="File must be an Excel or CSV file (.xlsx, .xls, .csv)")

    content = await file.read()
    try:
        result = await CalendarUploadService.upload_calendar_excel(content, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "No valid records found"))

    return {
        "status": result.get("status", "success"),
        "message": "Calendar upload completed",
        "inserted": result.get("records_inserted", 0),
        "updated": result.get("records_updated", 0),
        "skipped": result.get("records_skipped", 0),
        "records_processed": result.get("records_processed", 0),
        "errors": result.get("errors", [])
    }


@router.get(
    "/trains/live-toggle",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def get_live_toggle_state():
    """Get the current live RapidAPI refresh toggle state."""
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    enabled = await LiveTrainRefreshToggleService.is_live_refresh_enabled()
    doc = await LiveTrainRefreshToggleService.get_toggle_document()
    last_updated_at = None
    last_updated_by = None
    if doc:
        updated_at = doc.get("updated_at")
        if updated_at:
            last_updated_at = updated_at.isoformat()
        last_updated_by = doc.get("updated_by")

    last_fetch_cycle = await LiveTrainService.get_last_fetch_cycle()
    return {
        "status": "success",
        "live_refresh_enabled": enabled,
        "last_updated_at": last_updated_at,
        "last_updated_by": last_updated_by,
        "last_fetch_cycle": last_fetch_cycle,
    }


@router.post(
    "/trains/live-toggle",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses={
        500: {"description": "Failed to update toggle state"},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def set_live_toggle_state(
    payload: LiveTrainToggleRequest,
    token_payload: Dict[str, Any] = Depends(verify_token),
):
    """Enable or disable the periodic live train refresh cycle."""
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    username = str(token_payload.get("sub") or "system")
    doc = await LiveTrainRefreshToggleService.set_live_refresh_enabled(payload.enabled, updated_by=username)
    if doc is None:
        raise HTTPException(status_code=500, detail="Failed to update toggle state")

    last_fetch_cycle = await LiveTrainService.get_last_fetch_cycle()
    updated_at = doc.get("updated_at")
    return {
        "status": "success",
        "message": "Live train refresh toggle updated",
        "live_refresh_enabled": doc.get("live_train_refresh_enabled", payload.enabled),
        "last_updated_at": updated_at.isoformat() if updated_at else None,
        "last_updated_by": doc.get("updated_by"),
        "last_fetch_cycle": last_fetch_cycle,
    }


@router.get(
    "/trains/upcoming",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def get_upcoming_trains(
    window_hours: Optional[float] = Query(None, description="Lookahead window in hours", ge=0.1, le=24.0),
    include_live: bool = Query(True, description="Include live status from RapidAPI")
):
    """
    Get trains arriving/departing within the specified time window.
    Includes live train status (delay, platform, actual times) when available.

    **Query Parameters:**
    - window_hours: Lookahead window (default: 1 hour, range: 0.5-24)
    - include_live: Include live status data (default: true)

    **Response Fields:**
    Each train includes:
    - scheduled_arrival / scheduled_departure: Scheduled times (HH:MM IST)
    - actual_arrival / actual_departure: Actual times from live API (HH:MM IST)
    - delay_minutes: Delay in minutes (0 = on time, negative = early)
    - platform_number: Platform number (if available)
    - current_status: SCHEDULED / ON_TIME / DELAYED / ARRIVED / DEPARTED
    - minutes_until_arrival / minutes_until_departure: countdown
    - last_updated_at: When live status was last fetched

    **Live Data:**
    - Live status is fetched hourly for trains in the 1-hour window
    - `live_data_enabled`: Whether live API is enabled
    - `last_fetch_cycle`: Timestamp of last hourly fetch

    **Real-time Updates:**
    Connect to WebSocket at `/api/ws/trains` for auto-updates without page reload.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    result = await TrainScheduleService.get_upcoming_trains(
        window_hours=window_hours,
        include_live_status=include_live
    )
    
    from config.config import get_settings
    settings = get_settings()
    effective_window_hours = window_hours if window_hours is not None else settings.live_train_window_hours

    return {
        "status": "success",
        "timestamp": datetime.now(UTC).isoformat(),
        "window_hours": effective_window_hours,
        "trains": result["trains"],
        "total_count": result["total_count"],
        "live_data_enabled": result.get("live_data_enabled", False),
        "live_refresh_enabled": result.get("live_refresh_enabled", True),
        "live_data_active": result.get("live_data_active", False),
        "last_fetch_cycle": result.get("last_fetch_cycle"),
    }


@router.get(
    "/trains/schedule",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses={
        400: {"description": INVALID_DATE_FORMAT_DETAIL},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def get_train_schedule(
    date: str = Query(None, description="Date in YYYY-MM-DD format (default: today)")
):
    """
    Get full train schedule for a specific date.

    **Query Parameters:**
    - date: Target date in YYYY-MM-DD format (default: today)

    **Response:**
    Returns all trains scheduled for the given date, sorted by arrival/departure time.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    # Parse date or use today
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=INVALID_DATE_FORMAT_DETAIL)
    else:
        target_date = datetime.now(UTC)

    schedules = await TrainScheduleService.get_schedules_by_date(target_date)

    # Serialize for response
    for s in schedules:
        s["_id"] = str(s["_id"])
        if s.get("arrival_time"):
            s["arrival_time"] = s["arrival_time"].isoformat()
        if s.get("departure_time"):
            s["departure_time"] = s["departure_time"].isoformat()
        if s.get("schedule_date"):
            s["schedule_date"] = s["schedule_date"].isoformat()
        if s.get("uploaded_at"):
            s["uploaded_at"] = s["uploaded_at"].isoformat()

    return {
        "status": "success",
        "date": target_date.strftime("%Y-%m-%d"),
        "count": len(schedules),
        "schedules": schedules
    }


@router.get(
    "/trains/dates",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def get_available_dates():
    """
    Get list of dates that have schedule data available.

    Useful for frontend to show which dates have train data uploaded.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    dates = await TrainScheduleService.get_available_dates()

    return {
        "status": "success",
        "dates": dates,
        "count": len(dates)
    }


def _parse_history_date_range(start_date: Optional[str], end_date: Optional[str]):
    """Parse and validate start_date/end_date query params for live-status history endpoints.

    Each param is parsed independently, then cross-defaulted so a single date
    (only start_date, only end_date, or start_date == end_date) resolves to a
    one-day range, and two distinct dates resolve to an inclusive range.
    """
    start_dt = None
    end_dt = None

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    if start_dt is None:
        start_dt = end_dt
    if end_dt is None:
        end_dt = start_dt

    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    return start_dt, end_dt


@router.get("/trains/live-status/history", tags=["Trains"], dependencies=[require_viewer])
async def get_live_status_history(
    start_date: Optional[str] = Query(None, description="Range start date, YYYY-MM-DD (overrides `days`)"),
    end_date: Optional[str] = Query(None, description="Range end date, YYYY-MM-DD (defaults to start_date)"),
    days: int = Query(10, ge=1, le=90, description="Days to look back from today, used only if start_date is not given (default: 10)"),
    train_number: Optional[str] = Query(None, description="Filter by a specific train number"),
    download: bool = Query(False, description="If true, returns a CSV file attachment instead of JSON")
):
    """
    
    Get train_live_status records for a date range.

    Includes actual_arrival and actual_departure for each train, along with
    platform, delay, and status data as recorded by the live tracking poller.

    **Query Parameters:**
    - start_date / end_date: Explicit date range, YYYY-MM-DD (preferred for a calendar picker).
      Send the same value for both (or just one of them) to get a single day's records;
      send different values to get an inclusive range.
    - days: Fallback lookback window from today, used only when neither start_date nor
      end_date is given (default: 10, max: 90)
    - train_number: Optional filter for a single train
    - download: If true, responds with a downloadable CSV file instead of JSON

    **Response:**
    Returns train_live_status documents sorted by schedule_date (newest first),
    or a CSV attachment when download=true.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail="Database not available")

    start_dt, end_dt = _parse_history_date_range(start_date, end_date)

    records = await LiveTrainService.get_recent_history(
        days=days,
        train_number=train_number,
        start_date=start_dt,
        end_date=end_dt
    )

    if start_dt is not None:
        range_start = start_dt.strftime("%Y-%m-%d")
        range_end = end_dt.strftime("%Y-%m-%d")
    else:
        range_start = (datetime.now(UTC) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        range_end = datetime.now(UTC).strftime("%Y-%m-%d")

    if download:
        columns = [
            "train_number", "schedule_date", "station_code", "platform_number",
            "actual_arrival", "actual_departure", "current_status",
            "delay_minutes", "delay_status", "is_terminal_status", "last_fetched_at"
        ]

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)
        buffer.seek(0)

        filename = f"train_live_status_{range_start}_to_{range_end}.csv"

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    return {
        "status": "success",
        "start_date": range_start,
        "end_date": range_end,
        "count": len(records),
        "trains": records
    }


@router.get("/trains/{train_number}", tags=["Trains"], dependencies=[require_viewer])
@router.get(
    "/trains/{train_number}",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses={
        400: {"description": INVALID_DATE_FORMAT_DETAIL},
        404: {"description": "Train not found"},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def get_train_by_number(
    train_number: str,
    date: str = Query(None, description="Date filter YYYY-MM-DD")
):
    """
    Get schedule for specific train number.

    **Path Parameters:**
    - train_number: Train number (e.g., "12733")

    **Query Parameters:**
    - date: Optional date filter in YYYY-MM-DD format
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    query = {"train_number": train_number}

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            query["schedule_date"] = target_date.replace(hour=0, minute=0, second=0)
        except ValueError:
            raise HTTPException(status_code=400, detail=INVALID_DATE_FORMAT_DETAIL)

    cursor = MongoDB.database.train_schedules.find(query).sort("schedule_date", -1).limit(10)
    schedules = await cursor.to_list(length=10)

    if not schedules:
        raise HTTPException(status_code=404, detail=f"Train {train_number} not found")

    # Serialize
    for s in schedules:
        s["_id"] = str(s["_id"])
        if s.get("arrival_time"):
            s["arrival_time"] = s["arrival_time"].isoformat()
        if s.get("departure_time"):
            s["departure_time"] = s["departure_time"].isoformat()
        if s.get("schedule_date"):
            s["schedule_date"] = s["schedule_date"].isoformat()
        if s.get("uploaded_at"):
            s["uploaded_at"] = s["uploaded_at"].isoformat()

    return {
        "status": "success",
        "train_number": train_number,
        "count": len(schedules),
        "schedules": schedules
    }


@router.delete(
    "/trains/schedule/{date}",
    tags=["Trains"],
    dependencies=[require_authorized],
    responses={
        400: {"description": INVALID_DATE_FORMAT_DETAIL},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def delete_schedule_by_date(date: str):
    """
    Delete all train schedules for a specific date.

    **Path Parameters:**
    - date: Date to delete in YYYY-MM-DD format

    Use with caution - this action is irreversible.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=INVALID_DATE_FORMAT_DETAIL)

    deleted = await TrainScheduleService.delete_schedules_by_date(target_date)

    return {
        "status": "success",
        "message": f"Deleted {deleted} schedules for {date}",
        "date": date,
        "deleted_count": deleted
    }


@router.post(
    "/trains/whatsapp/opt-in",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def save_whatsapp_opt_in(
    payload: WhatsAppOptInRequest,
    token_payload: Dict[str, Any] = Depends(verify_token),
):
    """
    Save WhatsApp checkbox selection and trigger opt-in message.
    User must confirm by replying YES/START in WhatsApp before train alerts are sent.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    username = str(token_payload.get("sub") or "unknown")
    if payload.enabled:
        result = await WhatsAppOptInService.request_opt_in(
            username=username,
            phone_number=payload.phone_number,
            full_name=payload.full_name or username,
        )
    else:
        result = await WhatsAppOptInService.disable_opt_in(
            username=username,
            phone_number=payload.phone_number,
        )

    return {"status": "success", "data": result}


@router.get(
    "/trains/whatsapp/opt-in/status",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def get_whatsapp_opt_in_status(phone_number: str = Query(..., min_length=7, max_length=25)):
    """Get WhatsApp opt-in status for a phone number."""
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    data = await WhatsAppOptInService.get_subscription(phone_number)
    if not data:
        return {"status": "success", "data": None}
    return {"status": "success", "data": data}



def _extract_msg91_button_reply_text(payload: MSG91WebhookPayload) -> str:
    """Extract reply text from MSG91's button_reply field."""
    if not payload.button_reply:
        return ""
    br = payload.button_reply
    if isinstance(br, dict):
        body_text = br.get("button_text") or br.get("text") or br.get("payload") or ""
    elif isinstance(br, str):
        body_text = br
    else:
        body_text = ""
    print(f"[MSG91 Webhook] From button_reply: {body_text}")
    return body_text


def _extract_msg91_button_text(payload: MSG91WebhookPayload) -> str:
    """Extract reply text from MSG91's button field (string-encoded JSON or dict)."""
    if not payload.button:
        return ""
    bf = payload.button
    if isinstance(bf, str):
        try:
            parsed = json.loads(bf)
            body_text = parsed.get("payload") or parsed.get("text") or parsed.get("button_text") or ""
        except Exception:
            body_text = bf
    elif isinstance(bf, dict):
        body_text = bf.get("payload") or bf.get("text") or bf.get("button_text") or ""
    else:
        body_text = ""
    print(f"[MSG91 Webhook] From button: {body_text}")
    return body_text


def _extract_msg91_interactive_text(payload: MSG91WebhookPayload) -> str:
    """Extract reply text from MSG91's interactive field."""
    if not payload.interactive:
        return ""
    ia = payload.interactive
    if isinstance(ia, str):
        try:
            ia = json.loads(ia)
        except Exception:
            pass
    body_text = ""
    if isinstance(ia, dict):
        body_text = (
            ia.get("button_reply", {}).get("id", "")
            or ia.get("list_reply", {}).get("id", "")
        )
    print(f"[MSG91 Webhook] From interactive: {body_text}")
    return body_text


def _extract_msg91_reply_text(payload: MSG91WebhookPayload) -> str:
    """Extract the reply text from whichever MSG91 field carries it, in priority order."""
    body_text = _extract_msg91_button_reply_text(payload)

    if not body_text:
        body_text = _extract_msg91_button_text(payload)

    if not body_text:
        body_text = _extract_msg91_interactive_text(payload)

    if not body_text and payload.text:
        body_text = payload.text
        logger.info(f"[MSG91 Webhook] From text: {body_text}")

    return str(body_text).strip().lower()


async def _apply_msg91_optin_decision(phone: str, body_text: str) -> None:
    """Update sendAlerts in viewers_user_collection based on the user's Allow/Deny reply."""
    positive = {"allow", "yes", "y", "start", "subscribe", "optin", "opt in", "confirm"}
    negative = {"deny", "stop", "unsubscribe", "cancel", "no", "n", "optout", "opt out"}

    from modules.users import UsersManager

    if body_text in positive:
        logger.info(f"[MSG91 Webhook] → ALLOW: updating sendAlerts=True in viewers_user_collection for {phone}")
        success = await UsersManager.update_alert_optin(phone_number=phone, allowed=True)
        logger.info(f"[MSG91 Webhook] ✓ sendAlerts=True updated: {success}")
        if not success:
            logger.warning(f"[MSG91 Webhook] ⚠ Phone {phone} not found in viewers_user_collection")
    elif body_text in negative:
        logger.info(f"[MSG91 Webhook] → DENY: updating sendAlerts=False in viewers_user_collection for {phone}")
        success = await UsersManager.update_alert_optin(phone_number=phone, allowed=False)
        logger.info(f"[MSG91 Webhook] ✓ sendAlerts=False updated: {success}")
        if not success:
            logger.warning(f"[MSG91 Webhook] ⚠ Phone {phone} not found in viewers_user_collection")
    else:
        logger.warning(f"[MSG91 Webhook] ⚠ Unrecognized reply '{body_text}' — ignoring")


@router.post("/trains/whatsapp/msg91-webhook", tags=["Trains"])
async def msg91_whatsapp_webhook(payload: MSG91WebhookPayload):
    """
    MSG91 inbound WhatsApp webhook for opt-in/opt-out confirmation.

    When a user clicks **Allow** or **Deny** on the Suraksha AI WhatsApp message,
    MSG91 calls this endpoint with the user's phone number and their reply.
    The backend then updates **sendAlerts** in **viewers_user_collection**:
    - Allow → sendAlerts = true  (user starts receiving alerts)
    - Deny  → sendAlerts = false (user stops receiving alerts)

    **To test from FastAPI Docs:**
    - For Radhika (Allow):  `{"customerNumber": "916304543584", "text": "allow"}`
    - For Harshini (Deny):  `{"customerNumber": "918497961169", "text": "deny"}`
    """
    data = payload.model_dump()
    print(f"[MSG91 Webhook] Received payload: {data}")

    # Resolve phone number
    phone = payload.customerNumber or payload.customer_number
    if not phone:
        print("[MSG91 Webhook] Missing customer phone number in payload")
        return PlainTextResponse("Missing phone number", status_code=400)

    body_text = _extract_msg91_reply_text(payload)
    print(f"[MSG91 Webhook] Final reply text: '{body_text}' | Phone: {phone}")

    if not body_text:
        print("[MSG91 Webhook] No reply text found — ignoring")
        return PlainTextResponse("OK")

    await _apply_msg91_optin_decision(phone, body_text)
    return PlainTextResponse("OK")


@router.post(
    "/trains/whatsapp/send-text",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses={
        400: {"description": "WhatsApp number is not opt-in confirmed"},
        502: {"description": "Failed to send WhatsApp message"},
        503: {"description": DB_NOT_AVAILABLE_DETAIL},
    },
)
async def send_whatsapp_text_alert(
    payload: WhatsAppTextAlertRequest,
    token_payload: Dict[str, Any] = Depends(verify_token),
):
    """
    Send plain WhatsApp text alert to a single number.
    Allowed only when number is opt-in confirmed and enabled.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    username = str(token_payload.get("sub") or "unknown")
    is_allowed = await WhatsAppOptInService.is_confirmed_enabled(payload.phone_number)
    if not is_allowed:
        raise HTTPException(
            status_code=400,
            detail="WhatsApp number is not opt-in confirmed. Ask user to enable and reply YES first.",
        )

    result = WhatsAppTemplateService.send_text_message(
        phone_number=payload.phone_number,
        message_text=payload.message,
    )
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error") or "Failed to send WhatsApp message")

    return {
        "status": "success",
        "sent_by": username,
        "phone_number": payload.phone_number,
        "message_sid": result.get("sid"),
    }


@router.get(
    "/trains/whatsapp/debug/platform-eligibility",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
def _classify_platform_alert_type(has_new_platform: bool, has_old_platform: bool, old_platform: str, new_platform: str) -> str:
    if has_new_platform and has_old_platform and old_platform != new_platform:
        return "platform_change"
    if has_new_platform:
        return "platform_assigned"
    return "not_eligible"


async def _evaluate_train_platform_eligibility(train: Dict[str, Any], settings) -> Dict[str, Any]:
    """Evaluate whether a single upcoming train is eligible for a WhatsApp platform alert."""
    train_number = str(train.get("train_number") or "").strip()
    schedule_date = train.get("schedule_date")
    if not train_number or not schedule_date:
        return {
            "train_number": train_number or None,
            "eligible": False,
            "reason": "Missing train_number or schedule_date in train_schedules",
        }

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    schedule_day = schedule_date.replace(hour=0, minute=0, second=0, microsecond=0)
    start_day = max(0, (today - schedule_day).days)

    api_data = await LiveTrainService.fetch_train_status(train_number, start_day)
    if not api_data:
        return {
            "train_number": train_number,
            "schedule_date": schedule_day.strftime("%Y-%m-%d"),
            "eligible": False,
            "reason": "No live API data for configured station",
        }

    existing = await MongoDB.database.train_live_status.find_one({
        "train_number": train_number,
        "schedule_date": schedule_day,
        "station_code": settings.live_train_station_code,
    })
    old_platform = str((existing or {}).get("platform_number") or "").strip()
    new_platform = str(api_data.get("platform_number") or "").strip()
    has_new_platform = WhatsAppTemplateService._is_meaningful_platform(new_platform)
    has_old_platform = WhatsAppTemplateService._is_meaningful_platform(old_platform)

    return {
        "train_number": train_number,
        "train_name": str(train.get("train_name") or "").strip() or None,
        "schedule_date": schedule_day.strftime("%Y-%m-%d"),
        "arrival_time": train.get("arrival_time").strftime("%H:%M") if train.get("arrival_time") else None,
        "departure_time": train.get("departure_time").strftime("%H:%M") if train.get("departure_time") else None,
        "old_platform": old_platform or None,
        "new_platform": new_platform or None,
        "eligible": bool(has_new_platform),
        "alert_type": _classify_platform_alert_type(has_new_platform, has_old_platform, old_platform, new_platform),
        "reason": (
            "Meaningful platform available from live API"
            if has_new_platform
            else "Platform missing/placeholder in live API"
        ),
    }


async def debug_platform_alert_eligibility(
    window_hours: Optional[float] = Query(None, ge=0.5, le=24.0, description="Override fetch window used for eligibility check"),
    limit: int = Query(20, ge=1, le=100, description="Max trains to inspect in this debug run"),
):
    """
    One-time debug endpoint to inspect which upcoming trains are currently eligible
    for WhatsApp platform alerts (without sending alerts or updating DB).
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    settings = get_settings()
    effective_window = window_hours or settings.live_train_window_hours

    if not settings.live_train_api_enabled:
        return {
            "status": "success",
            "eligible_count": 0,
            "inspected_count": 0,
            "window_hours": effective_window,
            "message": "Live train API is disabled",
            "trains": [],
        }

    if not settings.live_train_api_key:
        return {
            "status": "success",
            "eligible_count": 0,
            "inspected_count": 0,
            "window_hours": effective_window,
            "message": "LIVE_TRAIN_API_KEY is not configured",
            "trains": [],
        }

    candidates = await LiveTrainService.get_trains_to_fetch(window_hours=effective_window)
    inspected = candidates[:limit]
    evaluations = []

    for train in inspected:
        evaluations.append(await _evaluate_train_platform_eligibility(train, settings))

    eligible_count = sum(1 for item in evaluations if item.get("eligible"))
    return {
        "status": "success",
        "window_hours": effective_window,
        "candidate_count": len(candidates),
        "inspected_count": len(evaluations),
        "eligible_count": eligible_count,
        "ineligible_count": len(evaluations) - eligible_count,
        "station_code": settings.live_train_station_code,
        "trains": evaluations,
    }


@router.post(
    "/trains/whatsapp/debug/trigger-live-cycle",
    tags=["Trains"],
    dependencies=[require_viewer],
    responses=DB_NOT_AVAILABLE_RESPONSE,
)
async def debug_trigger_live_cycle():
    """
    Debug helper to trigger one immediate live-train fetch cycle.
    This will execute the same path that sends WhatsApp alerts.
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_NOT_AVAILABLE_DETAIL)

    settings = get_settings()
    if not settings.live_train_api_enabled:
        return {
            "status": "success",
            "message": "Live train API is disabled",
            "stats": {"fetched": 0, "failed": 0, "skipped": 0},
        }

    stats = await LiveTrainService.run_hourly_fetch_cycle()
    return {
        "status": "success",
        "message": "Triggered one live fetch cycle. Check server logs for WhatsApp send details.",
        "stats": stats,
        "timestamp": datetime.now(UTC).isoformat(),
    }
