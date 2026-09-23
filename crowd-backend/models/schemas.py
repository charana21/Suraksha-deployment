"""
Database and API Schema Definitions
Single source of truth for all data structures in CrowdVision

Collections:
- cameras: Camera configuration and status
- analytics: Real-time crowd metrics (30-day TTL)
- detections: Raw detection data for debugging (7-day TTL)
- alerts: Risk alerts with status tracking
- images: Alert image metadata

WebSocket Messages:
- analytics: Real-time crowd metrics push
- alert: Risk alert notifications
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from util.constants import (
    DESC_ZONE_NAME,
    DESC_AGGREGATION_TIMESTAMP,
    DESC_OVERALL_DENSITY_STATUS,
    DESC_RENDERING_ORDER,
    DESC_ISO8601_TIMESTAMP,
    DESC_CAMERA_ID,
    DESC_PHYSICAL_ZONE_TYPE,
    DESC_STATION_ID,
)

# ============================================================================
# ENUMS
# ============================================================================

class RiskLevel(str, Enum):
    """Risk level classification for crowd safety"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DensityLevel(str, Enum):
    """Crowd density classification"""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MotionLevel(str, Enum):
    """
    Motion intensity classification based on crowd speed (m/s).

    Ranges (motion_intensity value in m/s):
    - STATIC: < 0.1 (near-stationary)
    - SLOW: 0.1 - 0.5 (shuffling, dense queue)
    - NORMAL: 0.5 - 1.3 (walking pace)
    - FAST: 1.3 - 2.5 (brisk walking / jogging)
    - RUNNING: > 2.5 (running / stampede)

    Thresholds are configurable via settings (motion_threshold_*).
    """
    STATIC = "STATIC"
    SLOW = "SLOW"
    NORMAL = "NORMAL"
    FAST = "FAST"
    RUNNING = "RUNNING"


class CameraStatus(str, Enum):
    """Camera operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class StreamStatus(str, Enum):
    """RTSP stream processing status"""
    CONNECTING = "connecting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class AlertStatus(str, Enum):
    """Alert lifecycle status"""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ZoneType(str, Enum):
    """Physical zone type classification"""
    FOB = "FOB"               # Foot Over Bridge section
    PLATFORM = "PLATFORM"     # Platform area
    STAIRS = "STAIRS"         # Staircase
    LIFT = "LIFT"             # Elevator/lift area
    ESCALATOR = "ESCALATOR"   # Escalator
    GATE = "GATE"             # Entry/exit gate
    BOOKING = "BOOKING"       # Booking/ticketing counter
    CONCOURSE = "CONCOURSE"   # General concourse/waiting area
    VIP = "VIP"               # VIP lounge/area
    PARKING = "PARKING"       # Parking area
    ENTRY = "ENTRY"           # Entry point
    EXIT = "EXIT"             # Exit point


# ============================================================================
# MONGODB DOCUMENT SCHEMAS
# ============================================================================

class CameraDocument(BaseModel):
    """
    cameras collection - Camera configuration and status

    Primary key: camera_id (unique)
    """
    camera_id: str = Field(..., description="Unique camera identifier (e.g., 'camera_entry_stair')")
    name: str = Field(..., description="Human-readable camera name")
    rtsp_url: str = Field(..., description="RTSP stream URL")
    location: Optional[str] = Field(None, description="Physical location description")
    zone_id: Optional[str] = Field(None, description="Mapped zone identifier for SVG rendering")
    adjacent_cameras: List[str] = Field(default=[], description="Camera IDs of physically adjacent cameras for flow detection")
    svg_region_id: Optional[str] = Field(None, description="SVG element ID for frontend map rendering")
    status: CameraStatus = Field(CameraStatus.ACTIVE, description="Camera operational status")
    calibration: Optional[Dict] = Field(
        None,
        description="Spatial calibration: { area_m2: float, roi: { points: [[x,y],...], frame_width: int, frame_height: int } }"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class ZoneDocument(BaseModel):
    """
    zones collection - Logical zone definitions for SVG mapping

    Primary key: zone_id (unique)
    Multiple cameras can map to one zone (Many:1 relationship)
    Each zone maps to exactly one SVG element (1:1 relationship)

    Indexes:
    - idx_zone_id: unique zone_id
    - idx_station_order: (station_id, display_order) for ordered listing
    - idx_zone_type_station: (station_id, zone_type) for type-filtered queries
    """
    zone_id: str = Field(..., description="Unique zone identifier (e.g., 'pf1_fob_hyb_end')")
    zone_name: str = Field(..., description="Human-readable zone name (e.g., 'PF1 FOB - HYB END')")
    svg_region_id: str = Field(..., description="SVG element ID for frontend rendering")
    display_order: int = Field(..., description="Rendering order in frontend (1, 2, 3...)")
    station_id: str = Field(..., description="Station identifier (e.g., 'HYB')")
    zone_type: ZoneType = Field(ZoneType.FOB, description=DESC_PHYSICAL_ZONE_TYPE)
    description: Optional[str] = Field(None, description="Optional zone description")
    is_active: bool = Field(True, description="Whether zone is active for analytics")
    adjacent_zones: List[str] = Field(default=[], description="Zone IDs of physically connected zones for flow analysis")
    area_m2: Optional[float] = Field(None, description="Physical area in square meters (for density calculation)")
    capacity: Optional[int] = Field(None, description="Rated safe capacity (for % utilization)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class AnalyticsDocument(BaseModel):
    """
    analytics collection - Minimal storage schema (30-day TTL)

    Indexes:
    - idx_camera_time: (camera_id, timestamp DESC)
    - idx_timestamp_ttl: TTL auto-delete after 30 days
    - idx_risk_camera: (risk_level, camera_id)
    """
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    timestamp: datetime = Field(..., description="BSON datetime for TTL indexing")
    frame_number: int = Field(..., description="Processing frame counter")

    # Aggregated metrics (no raw detections)
    people_count: int = Field(0, description="Total detected people in frame")
    density_avg: float = Field(0.0, description="Average crowd density (people/m²)")
    density_level: DensityLevel = Field(DensityLevel.LOW, description="Categorical density level")
    motion_intensity: float = Field(0.0, description="Average crowd speed in m/s (approximate, uniform scaling)")
    motion_level: MotionLevel = Field(MotionLevel.STATIC, description="Categorical motion level")
    risk_score: float = Field(0.0, description="Computed risk score (0-100)")
    risk_level: RiskLevel = Field(RiskLevel.LOW, description="Categorical risk level")
    risk_factors: Optional[List[str]] = Field(None, description="Active risk factors (if any)")

    class Config:
        use_enum_values = True


class DetectionsDocument(BaseModel):
    """
    detections collection - Raw detection data for debugging (7-day TTL)

    Stored separately from analytics to reduce main collection size.
    Contains bounding boxes and confidence scores for each detection.

    Indexes:
    - idx_detections_ttl: TTL auto-delete after 7 days
    - idx_detections_camera_frame: (camera_id, frame_number DESC)
    """
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    stream_id: str = Field(..., description="Stream UUID for frontend tracking")
    frame_number: int = Field(..., description="Processing frame counter")
    timestamp: datetime = Field(..., description="BSON datetime for TTL indexing")
    detection_count: int = Field(0, description="Number of detections in this frame")
    detections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {bbox: [x1,y1,x2,y2], confidence: float}"
    )


class AlertDocument(BaseModel):
    """
    alerts collection - Risk alerts with status tracking

    Primary key: alert_id (unique UUID string)

    Indexes:
    - idx_alert_id: unique alert_id
    - idx_alert_camera_time: (camera_id, timestamp DESC)
    - idx_severity_status_time: (severity, status, timestamp DESC)
    """
    alert_id: str = Field(..., description="Unique alert UUID")
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    zone_id: Optional[str] = Field(None, description="Zone this camera belongs to (e.g. zone_hyb_fob)")
    zone_type: Optional[str] = Field(None, description="Zone type: FOB, PLATFORM, or BOOKING")
    timestamp: datetime = Field(..., description="When alert was triggered")
    severity: RiskLevel = Field(..., description="Alert severity level")
    status: AlertStatus = Field(AlertStatus.TRIGGERED, description="Alert lifecycle status")
    trigger_reason: str = Field(..., description="Why alert was triggered")
    risk_score: float = Field(..., description="Risk score when triggered")
    people_count: int = Field(..., description="People count when triggered")
    risk_factors: List[str] = Field(default_factory=list, description="Active risk factors")
    has_image: bool = Field(False, description="Whether alert has associated image")
    image_id: Optional[str] = Field(None, description="ObjectId reference to images collection")

    class Config:
        use_enum_values = True



class FobAnalyticsDocument(BaseModel):
    """
    fob_analytics collection - Aggregated footfall for FOB zones

    Each document represents one FOB zone (e.g. zone_hyb_fob, zone_kzj_fob).
    A combined "all FOBs" doc uses fob_id = station_id (e.g. "HYB") for backward compat.
    """
    fob_id: str = Field(..., description="FOB zone_id (e.g. 'zone_hyb_fob') or station_id for combined")
    station_id: str = Field(..., description=DESC_STATION_ID)
    zone_name: Optional[str] = Field(None, description=DESC_ZONE_NAME)
    timestamp: datetime = Field(..., description=DESC_AGGREGATION_TIMESTAMP)
    total_people_count: int = Field(..., description="Sum of people_count across FOB cameras")
    density_status: str = Field("LOW", description=DESC_OVERALL_DENSITY_STATUS)
    cameras_active: int = Field(0, description="Number of active cameras contributing")
    camera_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Snapshot of individual camera counts at this timestamp"
    )

    class Config:
        use_enum_values = True


class PlatformAnalyticsDocument(BaseModel):
    """
    platform_analytics collection - Per-platform crowd counts

    One document per platform zone per flush interval.
    """
    zone_id: str = Field(..., description="Platform zone_id (e.g. 'zone_hyb_pf1')")
    station_id: str = Field(..., description=DESC_STATION_ID)
    zone_name: Optional[str] = Field(None, description=DESC_ZONE_NAME)
    timestamp: datetime = Field(..., description=DESC_AGGREGATION_TIMESTAMP)
    total_people_count: int = Field(..., description="Sum of people_count for this platform")
    density_status: str = Field("LOW", description=DESC_OVERALL_DENSITY_STATUS)
    cameras_active: int = Field(0, description="Number of active cameras contributing")
    camera_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Snapshot of individual camera counts"
    )

    class Config:
        use_enum_values = True


class StationAnalyticsDocument(BaseModel):
    """
    station_analytics collection - Station-wide crowd totals

    Aggregates ALL cameras across all zone types for whole-station view.
    """
    station_id: str = Field(..., description=DESC_STATION_ID)
    timestamp: datetime = Field(..., description=DESC_AGGREGATION_TIMESTAMP)
    total_people_count: int = Field(..., description="Total people across entire station")
    cameras_active: int = Field(0, description="Number of active cameras")
    zone_type_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="People count per zone type: {FOB: N, PLATFORM: N, BOOKING: N}"
    )
    camera_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Snapshot of individual camera counts"
    )
    density_status: str = Field("LOW", description=DESC_OVERALL_DENSITY_STATUS)

    class Config:
        use_enum_values = True


class ImageDocument(BaseModel):
    """
    images collection - Alert image metadata

    Actual images stored on filesystem, metadata in MongoDB.

    Indexes:
    - idx_image_alert: unique alert_id reference
    - idx_image_camera_time: (camera_id, timestamp DESC)
    """
    alert_id: str = Field(..., description="Reference to alert UUID")
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    timestamp: datetime = Field(..., description="When image was captured")
    file_path: str = Field(..., description="Filesystem path to image")
    risk_level: RiskLevel = Field(..., description="Risk level when captured")
    people_count: int = Field(..., description="People count when captured")

    class Config:
        use_enum_values = True


# ============================================================================
# WEBSOCKET MESSAGE SCHEMAS
# ============================================================================

class AnalyticsWebSocketMessage(BaseModel):
    """
    WebSocket analytics message - Real-time crowd metrics push

    Sent every processed frame to subscribed clients.
    Contains simplified metrics without raw detections.
    """
    type: Literal["analytics"] = "analytics"
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    stream_id: str = Field(..., description="Stream UUID for frontend filtering")
    timestamp: str = Field(..., description="ISO 8601 timestamp string")
    data: Dict[str, Any] = Field(
        ...,
        description="""
        Contains:
        - frame_number: int
        - people_count: int
        - density_avg: float
        - density_level: str
        - motion_intensity: float
        - risk_score: float
        - risk_level: str
        - risk_factors: List[str]
        """
    )


class AlertWebSocketMessage(BaseModel):
    """
    WebSocket alert message - Risk alert notification

    Sent when risk threshold is exceeded.
    """
    type: Literal["alert"] = "alert"
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    stream_id: str = Field(..., description="Stream UUID for frontend filtering")
    timestamp: str = Field(..., description="ISO 8601 timestamp string")
    data: Dict[str, Any] = Field(
        ...,
        description="""
        Contains:
        - alert_id: str
        - severity: str (HIGH/CRITICAL)
        - trigger_reason: str
        - risk_score: float
        - people_count: int
        - risk_factors: List[str]
        """
    )


# ============================================================================
# API REQUEST/RESPONSE SCHEMAS
# ============================================================================

class StartStreamRequest(BaseModel):
    """POST /api/rtsp/start - Start RTSP stream processing"""
    rtsp_url: str = Field(..., description="RTSP stream URL to process")
    name: Optional[str] = Field(None, description="Human-readable stream name")
    location: Optional[str] = Field(None, description="Camera physical location")


class StartStreamResponse(BaseModel):
    """Response from POST /api/rtsp/start"""
    stream_id: str = Field(..., description="Unique stream UUID")
    camera_id: str = Field(..., description="Camera identifier in database")
    rtsp_url: str = Field(..., description="RTSP URL being processed")
    status: str = Field(..., description="Stream status (running/error)")
    message: str = Field(..., description="Status message")


class StreamStatusResponse(BaseModel):
    """GET /api/rtsp/status/{stream_id}"""
    stream_id: str = Field(..., description="Stream UUID")
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    name: str = Field(..., description="Stream name")
    status: StreamStatus = Field(..., description="Current stream status")
    is_running: bool = Field(..., description="Whether stream is active")
    fps: float = Field(..., description="Current processing FPS")
    frame_count: int = Field(..., description="Total frames processed")
    last_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Most recent analytics data"
    )

    class Config:
        use_enum_values = True


class StreamListItem(BaseModel):
    """Single item in GET /api/rtsp/list response"""
    stream_id: str
    camera_id: str
    name: str
    status: str
    is_running: bool
    fps: float
    frame_count: int


class CameraResponse(BaseModel):
    """GET /api/cameras/{camera_id}"""
    camera_id: str
    name: str
    rtsp_url: str
    location: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class AlertResponse(BaseModel):
    """Single alert in GET /api/alerts response"""
    alert_id: str
    camera_id: str
    timestamp: str
    severity: str
    status: str
    trigger_reason: str
    risk_score: float
    people_count: int
    risk_factors: List[str]
    has_image: bool


class HealthResponse(BaseModel):
    """GET /api/health"""
    status: str = Field(..., description="Service status (healthy/degraded)")
    version: str = Field(..., description="API version")
    mongodb_connected: bool = Field(..., description="MongoDB connection status")
    active_streams: int = Field(..., description="Number of active RTSP streams")
    websocket_connections: int = Field(..., description="Active WebSocket connections")


# ============================================================================
# ZONE API SCHEMAS
# ============================================================================

class ZoneCreateRequest(BaseModel):
    """POST /api/zones - Create new zone"""
    zone_id: str = Field(..., description="Unique zone identifier")
    zone_name: str = Field(..., description=DESC_ZONE_NAME)
    svg_region_id: str = Field(..., description="SVG element ID")
    display_order: int = Field(..., description=DESC_RENDERING_ORDER)
    station_id: str = Field(..., description="Station identifier")
    zone_type: ZoneType = Field(ZoneType.FOB, description=DESC_PHYSICAL_ZONE_TYPE)
    description: Optional[str] = Field(None, description="Optional description")
    adjacent_zones: List[str] = Field(default=[], description="Zone IDs of physically connected zones")
    area_m2: Optional[float] = Field(None, description="Physical area in square meters")
    capacity: Optional[int] = Field(None, description="Rated safe capacity")


class ZoneUpdateRequest(BaseModel):
    """PUT /api/zones/{zone_id} - Update zone"""
    zone_name: Optional[str] = Field(None, description=DESC_ZONE_NAME)
    svg_region_id: Optional[str] = Field(None, description="SVG element ID")
    display_order: Optional[int] = Field(None, description=DESC_RENDERING_ORDER)
    zone_type: Optional[ZoneType] = Field(None, description=DESC_PHYSICAL_ZONE_TYPE)
    description: Optional[str] = Field(None, description="Optional description")
    is_active: Optional[bool] = Field(None, description="Whether zone is active")
    adjacent_zones: Optional[List[str]] = Field(None, description="Zone IDs of physically connected zones")
    area_m2: Optional[float] = Field(None, description="Physical area in square meters")
    capacity: Optional[int] = Field(None, description="Rated safe capacity")


class ZoneResponse(BaseModel):
    """GET /api/zones/{zone_id} - Zone details"""
    zone_id: str
    zone_name: str
    svg_region_id: str
    display_order: int
    station_id: str
    zone_type: str
    description: Optional[str] = None
    is_active: bool
    adjacent_zones: List[str] = []
    area_m2: Optional[float] = None
    capacity: Optional[int] = None
    created_at: str
    updated_at: str


class ZoneAnalyticsItem(BaseModel):
    """Single zone in zone analytics response"""
    zone_id: str = Field(..., description="Zone identifier")
    zone_name: str = Field(..., description=DESC_ZONE_NAME)
    svg_region_id: str = Field(..., description="SVG element ID for frontend")
    display_order: int = Field(..., description=DESC_RENDERING_ORDER)
    zone_type: str = Field(..., description=DESC_PHYSICAL_ZONE_TYPE)
    people_count: int = Field(0, description="Total people in zone (sum of cameras)")
    density_avg: float = Field(0.0, description="Max density across cameras")
    density_level: str = Field("LOW", description="Density level")
    motion_intensity: float = Field(0.0, description="Max motion across cameras")
    risk_score: float = Field(0.0, description="Max risk score across cameras")
    risk_level: str = Field("LOW", description="Highest risk level")
    camera_count: int = Field(0, description="Number of cameras in zone")
    cameras: List[str] = Field(default_factory=list, description="Camera IDs in zone")


class ZoneAnalyticsResponse(BaseModel):
    """GET /api/zones/analytics - Aggregated zone analytics for SVG rendering"""
    station_id: Optional[str] = Field(None, description="Station filter if applied")
    timestamp: str = Field(..., description=DESC_ISO8601_TIMESTAMP)
    zones: List[ZoneAnalyticsItem] = Field(..., description="Zone analytics list")


class ZoneWebSocketMessage(BaseModel):
    """WebSocket zone analytics message"""
    type: Literal["zone_analytics"] = "zone_analytics"
    station_id: str = Field(..., description="Station identifier")
    timestamp: str = Field(..., description=DESC_ISO8601_TIMESTAMP)
    zones: List[Dict[str, Any]] = Field(..., description="Zone analytics data")


class CameraZoneAssignRequest(BaseModel):
    """PUT /api/cameras/{camera_id}/zone - Assign camera to zone"""
    zone_id: Optional[str] = Field(None, description="Zone ID to assign (null to unassign)")


# ============================================================================
# INTERNAL DATA STRUCTURES
# ============================================================================

class FrameAnalysisResult(BaseModel):
    """
    Internal: Result from crowd analysis pipeline

    Used between rtsp_worker.py and data preparation methods.
    """
    frame_number: int
    people_count: int
    density_avg: float
    density_max: float
    motion_intensity: float
    detections: List[Dict[str, Any]]
    zones: Dict[str, Any]


class WebSocketStats(BaseModel):
    """
    Internal: WebSocket manager statistics
    """
    total_connections: int
    messages_sent: int
    connection_errors: int
    active_cameras: int
    global_subscribers: int
    total_active_connections: int


class PersistenceStats(BaseModel):
    """
    Internal: Persistence worker statistics
    """
    analytics_written: int
    analytics_dropped: int
    detections_written: int
    detections_dropped: int
    alerts_written: int
    images_written: int
    errors: int


# ============================================================================
# TRAIN SCHEDULE SCHEMAS
# ============================================================================

class TrainEvent(str, Enum):
    """Train event type at this station"""
    ORIGINATING = "ORIGINATING"
    TERMINATING = "TERMINATING"
    THROUGH = "THROUGH"


class TrainScheduleDocument(BaseModel):
    """
    train_schedules collection - Train schedule entries from Railway Excel

    Primary key: (train_number, schedule_date, arrival_time, departure_time)
    """
    train_number: str = Field(..., description="Train number (e.g., '12733')")
    train_name: str = Field(..., description="Train name (e.g., 'NARAYANADRI EXP')")
    train_type: str = Field(..., description="Train type (EXP, PASS, SF)")

    schedule_date: datetime = Field(..., description="Date of schedule (date portion only)")
    source: str = Field(..., description="Source station code")
    destination: str = Field(..., description="Destination station code")
    train_event: TrainEvent = Field(..., description="ORIGINATING/TERMINATING/THROUGH")

    arrival_time: Optional[datetime] = Field(None, description="Arrival datetime (None for ORIGINATING)")
    departure_time: Optional[datetime] = Field(None, description="Departure datetime (None for TERMINATING)")

    boarding_count: int = Field(0, description="Number of passengers boarding")
    deboarding_count: int = Field(0, description="Number of passengers deboarding")
    total_passengers: int = Field(0, description="Total passengers")
    uts_passengers: int = Field(0, description="UTS ticket passengers")

    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    source_file: Optional[str] = Field(None, description="Source Excel filename")

    arrival_hour: Optional[int] = Field(None, description="Hour of arrival (0-23)")
    departure_hour: Optional[int] = Field(None, description="Hour of departure (0-23)")

    class Config:
        use_enum_values = True


class TrainScheduleUploadResponse(BaseModel):
    """Response from POST /api/trains/upload"""
    status: str = Field(..., description="success/error")
    message: str = Field(..., description="Status message")
    records_processed: int = Field(..., description="Total rows processed")
    records_inserted: int = Field(..., description="New records created")
    records_updated: int = Field(..., description="Existing records updated")
    records_skipped: int = Field(..., description="Duplicate records skipped")
    dates_found: List[str] = Field(..., description="Dates found in Excel (YYYY-MM-DD)")
    errors: List[str] = Field(default_factory=list, description="Parsing errors")


class TrainScheduleItem(BaseModel):
    """Single train in upcoming trains response"""
    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str
    train_event: str
    arrival_time: Optional[str] = Field(None, description="ISO format or None")
    departure_time: Optional[str] = Field(None, description="ISO format or None")
    arrival_display: Optional[str] = Field(None, description="HH:MM format")
    departure_display: Optional[str] = Field(None, description="HH:MM format")
    minutes_until_arrival: Optional[int] = Field(None, description="Minutes until arrival")
    minutes_until_departure: Optional[int] = Field(None, description="Minutes until departure")
    boarding_count: int = Field(0)
    deboarding_count: int = Field(0)
    total_passengers: int = Field(0)
    status: str = Field("scheduled", description="scheduled/arriving/departing/departed")


class UpcomingTrainsResponse(BaseModel):
    """GET /api/trains/upcoming response"""
    status: str = Field("success")
    timestamp: str = Field(..., description="Current server time ISO format")
    window_hours: float = Field(2.0, description="Lookahead window in hours")
    arriving: List[TrainScheduleItem] = Field(..., description="Trains arriving soon")
    departing: List[TrainScheduleItem] = Field(..., description="Trains departing soon")
    total_count: int = Field(..., description="Total trains in window")


class TrainScheduleWebSocketMessage(BaseModel):
    """WebSocket message for train schedule updates"""
    type: Literal["train_schedule"] = "train_schedule"
    event: str = Field(..., description="'upcoming_update' or 'schedule_uploaded'")
    timestamp: str = Field(..., description=DESC_ISO8601_TIMESTAMP)
    data: Dict[str, Any] = Field(..., description="Upcoming trains data")


# ============================================================================
# LIVE TRAIN STATUS SCHEMAS
# ============================================================================

class TrainLiveStatus(str, Enum):
    """Live train status from API"""
    SCHEDULED = "SCHEDULED"  # No live data yet
    ON_TIME = "ON_TIME"      # Running on time
    DELAYED = "DELAYED"      # Running late
    ARRIVED = "ARRIVED"      # Arrived at station
    DEPARTED = "DEPARTED"    # Departed from station


class TrainLiveStatusDocument(BaseModel):
    """
    train_live_status collection - Live train status from RapidAPI

    Primary key: (train_number, schedule_date, station_code)
    TTL: 7 days auto-delete
    """
    train_number: str = Field(..., description="Train number (e.g., '17646')")
    schedule_date: datetime = Field(..., description="Date of schedule")
    station_code: str = Field(..., description="Station code (e.g., 'SC' for Secunderabad)")

    # Live data from API
    delay_minutes: int = Field(0, description="Delay in minutes (0 = on time, negative = early)")
    platform_number: Optional[str] = Field(None, description="Platform number (e.g., '5')")
    actual_arrival: Optional[str] = Field(None, description="Actual arrival time HH:MM (IST)")
    actual_departure: Optional[str] = Field(None, description="Actual departure time HH:MM (IST)")
    current_status: TrainLiveStatus = Field(TrainLiveStatus.SCHEDULED, description="Current train status")
    delay_status: Optional[str] = Field(None, description="Raw delay status from API (e.g., 'Delay 16m')")

    # API metadata
    last_fetched_at: datetime = Field(default_factory=datetime.utcnow, description="When status was last fetched")
    api_response_raw: Optional[Dict[str, Any]] = Field(None, description="Full station data from API (debugging)")
    fetch_cycle: Optional[str] = Field(None, description="Hourly cycle identifier (e.g., '2026-01-09T14:00')")

    # Flags
    is_terminal_status: bool = Field(False, description="True if ARRIVED/DEPARTED (no more fetches needed)")

    class Config:
        use_enum_values = True


class TrainWithLiveStatus(BaseModel):
    """Enhanced train schedule item with live status merged"""
    train_number: str
    train_name: str
    train_type: str
    source: str
    destination: str
    train_event: str

    # Scheduled times (from Excel)
    scheduled_arrival: Optional[str] = Field(None, description="Scheduled arrival HH:MM")
    scheduled_departure: Optional[str] = Field(None, description="Scheduled departure HH:MM")

    # Actual times (from live API)
    actual_arrival: Optional[str] = Field(None, description="Actual arrival HH:MM (from live API)")
    actual_departure: Optional[str] = Field(None, description="Actual departure HH:MM (from live API)")

    # Live status info
    delay_minutes: int = Field(0, description="Delay in minutes")
    platform_number: Optional[str] = Field(None, description="Platform number")
    current_status: str = Field("SCHEDULED", description="ON_TIME/DELAYED/ARRIVED/DEPARTED/SCHEDULED")

    # Countdown
    minutes_until_arrival: Optional[int] = Field(None, description="Minutes until scheduled arrival")
    minutes_until_departure: Optional[int] = Field(None, description="Minutes until scheduled departure")

    # Passenger counts
    boarding_count: int = Field(0)
    deboarding_count: int = Field(0)
    total_passengers: int = Field(0)

    # Metadata
    last_updated_at: Optional[str] = Field(None, description="When live status was last fetched")


class UpcomingTrainsWithLiveResponse(BaseModel):
    """GET /api/trains/upcoming response with live status"""
    status: str = Field("success")
    timestamp: str = Field(..., description="Current server time ISO format")
    window_hours: float = Field(1.0, description="Lookahead window in hours")
    trains: List[TrainWithLiveStatus] = Field(..., description="All trains in window with live status")
    total_count: int = Field(..., description="Total trains in window")
    live_data_enabled: bool = Field(True, description="Whether live API is enabled")
    last_fetch_cycle: Optional[str] = Field(None, description="Last hourly fetch cycle timestamp")


# ============================================================================
# ISLAND PLATFORM SCHEMAS (Phase-1: Historical + Planning Based)
# ============================================================================

class IslandPlatformCertainty(str, Enum):
    """Platform certainty level based on historical stability"""
    HIGH = "HIGH"       # ≥80% stability
    MEDIUM = "MEDIUM"   # 50-79% stability
    LOW = "LOW"         # <50% stability


class IslandAlertStatus(str, Enum):
    """Island alert lifecycle status"""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ContributingTrain(BaseModel):
    """Train contributing to island footfall"""
    train_number: str = Field(..., description="Train identifier")
    train_name: str = Field(..., description="Train name")
    arrival_time: str = Field(..., description="Arrival time HH:MM:SS")
    passengers: int = Field(..., description="Total passengers (boarding + deboarding)")
    expected_platforms: List[str] = Field(..., description="Platforms this train could appear on")
    stability_percent: float = Field(..., description="Historical platform stability percentage")
    certainty: IslandPlatformCertainty = Field(..., description="Certainty label")
    explanation: str = Field(..., description="Human-readable explanation of platform assignment")

    class Config:
        use_enum_values = True


class CertaintyBreakdown(BaseModel):
    """Breakdown of train certainties in alert"""
    high_certainty_trains: int = Field(0, description="Count of HIGH certainty trains")
    medium_certainty_trains: int = Field(0, description="Count of MEDIUM certainty trains")
    low_certainty_trains: int = Field(0, description="Count of LOW certainty trains")
    total_trains: int = Field(0, description="Total trains contributing to footfall")


class IslandAlertDocument(BaseModel):
    """
    island_alerts collection - Island platform footfall risk alerts

    Phase-1: Historical + planning-based early warning system.
    Safety principle: Footfall determines risk existence; certainty determines confidence.

    Indexes:
    - idx_island_alert_id: unique alert_id
    - idx_island_window: (island_id, window_start DESC)
    - idx_island_status_time: (status, created_at DESC)
    - idx_island_risk_status: (risk_level, status)
    - TTL: created_at (90 days)
    """
    alert_id: str = Field(..., description="Unique alert UUID")
    alert_type: Literal["ISLAND_FOOTFALL_RISK"] = Field("ISLAND_FOOTFALL_RISK")
    island_id: str = Field(..., description="Island identifier (e.g., 'island_2_3')")
    island_name: str = Field(..., description="Human-readable island name (e.g., 'Platforms 2 & 3')")

    # Time window
    window_start: datetime = Field(..., description="45-min window start time")
    window_end: datetime = Field(..., description="45-min window end time")

    # Footfall metrics
    total_footfall: int = Field(..., description="Total passengers in window")
    threshold: int = Field(..., description="Threshold value (default: 1200)")
    exceeds_by: int = Field(..., description="Passengers over threshold")
    exceeds_by_percent: float = Field(..., description="Percentage over threshold")

    # Risk assessment
    risk_level: RiskLevel = Field(..., description="MEDIUM/HIGH/CRITICAL based on footfall")
    certainty_breakdown: CertaintyBreakdown = Field(..., description="Train certainty breakdown")

    # Contributing trains
    contributing_trains: List[ContributingTrain] = Field(..., description="All trains in window")

    # Alert lifecycle
    status: IslandAlertStatus = Field(IslandAlertStatus.TRIGGERED, description="Alert status")
    created_at: datetime = Field(..., description="When alert was created")
    acknowledged_at: Optional[datetime] = Field(None, description="When alert was acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")

    # Advisory message
    advisory_message: str = Field(..., description="Human-readable advisory message")

    class Config:
        use_enum_values = True


# ============================================================================
# ISLAND ALERT API REQUEST/RESPONSE SCHEMAS
# ============================================================================

class GenerateAlertsRequest(BaseModel):
    """POST /api/island-alerts/generate request"""
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date YYYY-MM-DD (optional)")


class GenerateAlertsResponse(BaseModel):
    """POST /api/island-alerts/generate response"""
    status: str = Field(..., description="success or error")
    dates_processed: List[str] = Field(..., description="List of dates processed")
    alerts_created: int = Field(..., description="Total alerts created")
    execution_time_seconds: Optional[float] = Field(None, description="Execution time")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class ListAlertsResponse(BaseModel):
    """GET /api/island-alerts response"""
    status: str = Field("success")
    count: int = Field(..., description="Count of alerts in this page")
    total: int = Field(..., description="Total alerts matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Pagination offset")
    alerts: List[Dict[str, Any]] = Field(..., description="Alert documents")


class AlertActionResponse(BaseModel):
    """Response for acknowledge/resolve actions"""
    status: str = Field(..., description="success or error")
    alert_id: str = Field(..., description="Alert UUID")
    acknowledged_at: Optional[str] = Field(None, description="Acknowledgement timestamp")
    resolved_at: Optional[str] = Field(None, description="Resolution timestamp")
    message: Optional[str] = Field(None, description="Error message if status=error")


class IslandAlertSummary(BaseModel):
    """Daily summary statistics"""
    status: str = Field("success")
    date: str = Field(..., description="Summary date YYYY-MM-DD")
    total_alerts: int = Field(..., description="Total alerts for the day")
    by_island: Dict[str, int] = Field(..., description="Alert counts per island")
    by_risk_level: Dict[str, int] = Field(..., description="Alert counts per risk level")
    by_status: Dict[str, int] = Field(..., description="Alert counts per status")
    peak_hours: List[Dict[str, int]] = Field(..., description="Peak hour breakdown")


class PlatformHistoryStats(BaseModel):
    """Platform history collection statistics"""
    status: str = Field("success")
    total_trains: int = Field(..., description="Total trains in history")
    stable_trains: int = Field(..., description="Trains with ≥80% stability")
    unstable_trains: int = Field(..., description="Trains with <80% stability")
    last_loaded_at: Optional[str] = Field(None, description="Last CSV load timestamp")


# ============================================================================
# CALIBRATION SCHEMAS (Homography)
# ============================================================================

class CalibrationReferencePoint(BaseModel):
    """Single calibration reference point mapping pixel to world coordinates"""
    pixel: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Pixel coordinates [x, y]"
    )
    world: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Real-world coordinates in meters [x, y]"
    )


class HomographyCalibrationRequest(BaseModel):
    """Request to compute/save homography calibration"""
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    reference_points: List[CalibrationReferencePoint] = Field(
        ...,
        min_length=4,
        description="At least 4 reference points for homography"
    )
    frame_size: List[int] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Frame dimensions [width, height] in pixels"
    )


class HomographyCalibrationResponse(BaseModel):
    """Response after computing homography"""
    status: str = Field(..., description="success, warning, or error")
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    matrix: Optional[List[List[float]]] = Field(
        None,
        description="Computed 3x3 homography matrix (row-major)"
    )
    reprojection_error: Optional[float] = Field(
        None,
        description="RMS reprojection error in meters"
    )
    computed_area_m2: Optional[float] = Field(
        None,
        description="Computed visible area in m²"
    )
    message: str = Field(..., description="Status message or error details")


class CalibrationInfo(BaseModel):
    """Calibration information for a camera"""
    camera_id: str = Field(..., description=DESC_CAMERA_ID)
    visible_area_m2: float = Field(..., description="Visible area in m²")
    corridor_width_m: Optional[float] = Field(None, description="Corridor width in meters")
    coverage_length_m: Optional[float] = Field(None, description="Coverage length in meters")
    has_homography: bool = Field(False, description="Whether homography calibration exists")
    reprojection_error: Optional[float] = Field(
        None,
        description="Homography reprojection error in meters"
    )
    calibrated_at: Optional[str] = Field(None, description="Calibration timestamp")
    calibrated_by: Optional[str] = Field(None, description="Who performed calibration")


class CalibrationListResponse(BaseModel):
    """Response for listing all calibrations"""
    status: str = Field("success")
    count: int = Field(..., description="Number of calibrations")
    cameras: List[CalibrationInfo] = Field(..., description="Calibration info per camera")
