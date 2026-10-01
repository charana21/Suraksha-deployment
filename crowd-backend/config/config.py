"""
Configuration management using pydantic settings
"""
from typing import Optional, List, Union
from pydantic_settings import BaseSettings
from functools import lru_cache
import sys
import os

from sympy import true

def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return relative_path

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    log_file: Optional[str] = "data-drive/logs/app.log"  # Single file, rotates daily at midnight
    log_max_bytes: int = 10 * 1024 * 1024  # Unused (kept for backwards-compat)
    log_backup_count: int = 30  # Keep 30 days of rotated log files
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    # Comma-separated extra allowed CORS origins (useful for site-specific IPs)
    extra_allowed_origins: str = ""
    
    # Models
    yolo_model_path: str = get_resource_path("yolov8m.pt")
    device: str = "cuda"
    
    # Directories
    upload_dir: str = "data/uploads"
    output_dir: str = "data/outputs"
    models_dir: str = "data/weights"
    heatmap_dir: str = "data/heatmaps"
    analytics_dir: str = "data/analytics"
    
    # Adaptive Frame Enhancement (Phase 1.1)
    adaptive_enhancement_enabled: bool = True  # Enable conditional enhancement based on brightness
    brightness_threshold_for_enhancement: float = 0.4  # 0-1 scale: enhance if brightness < threshold
    enhancement_clahe_clip_limit: float = 2.0  # CLAHE contrast limiting parameter
    enhancement_denoise_strength: int = 10  # Denoising strength (higher = more smoothing)

    use_gpu: bool = True
    batch_size: int = 8
    optical_flow_interval: int = 3  # Run optical flow every N frames (CPU mode, saves 200ms)
    optical_flow_interval_gpu: int = 1  # Run every frame in GPU mode (fast enough)
    
    # Model Parameters
    head_size_min: int = 12
    head_size_max: int = 100
    head_conf_threshold: float = 0.2
    density_scale: float = 1.0  # Density map sum to count scale factor

    # RTSP Stream Settings
    rtsp_default_fps: int = 1  # Process 1 frame per second (1 FPS)
    rtsp_heatmap_save_interval: int = 1  # Save every Nth processed frame (1 = save all)
    rtsp_reconnect_attempts: int = 5  # Max reconnection attempts
    rtsp_reconnect_delay: float = 2.0  # Delay between reconnections (seconds)
    
    # Debug Settings
    debug_single_stream: bool = False  # If True, only start the target stream
    debug_target_stream: str = ""


    # Heatmap Settings
    heatmap_max_width: int = 800  # Resize heatmaps to this max width (maintains aspect ratio)
    heatmap_jpeg_quality: int = 75  # JPEG quality for heatmaps (70-85 recommended)
    heatmap_format: str = "jpg"  # jpg or png (jpg is faster and smaller)
    show_detection_boxes: bool = True  # Show YOLO detection boxes on heatmaps (for testing)
    save_heatmaps: bool = False  # Global switch to enable/disable heatmap saving

    # === UNIFIED DENSITY THRESHOLDS (people/m²) ===
    # Global standardized thresholds -- same density = same risk label for ALL cameras
    # Based on crowd safety research (Fruin/Togawa):
    density_threshold_low: float = 0.5       # Below = SPARSE (free movement)
    density_threshold_moderate: float = 1.5   # 0.5-1.5 = LOW (comfortable spacing)
    density_threshold_high: float = 2.5       # 1.5-2.5 = MODERATE (some contact, slowed movement)
    density_threshold_critical: float = 4.0   # 2.5-4.0 = HIGH (frequent contact), >4.0 = CRITICAL (crush risk)

    # === DENSITY ESTIMATION MODE ===
    # "pixel" = PET density map + optional YOLO head calibration (no physical measurements needed)
    # "area"  = use calibrated area_m2 from DB / camera_calibrations.json
    density_mode: str = "pixel"
    # Physical area of a typical YOLO head bbox (m²) — used for pixel→density scale calibration
    # YOLO bboxes include head + margins/shoulders → ~0.25m²
    pixel_head_reference_m2: float = 0.25
    # YOLO detection range for reliable head size caching
    pixel_head_min_detections: int = 3
    pixel_head_max_detections: int = 80
    pixel_head_min_confidence: float = 0.35

    # === PET INFERENCE INTERVAL ===
    # Run PET every Nth frame per camera; intermediate frames use YOLO-only + cached PET data.
    # Reduces GPU load to 8 inferences/sec for 40 cameras (every 5th frame), which 1 GPU can comfortably handle.
    pet_inference_interval: int = 3  # 1 = every frame (no skip), 3 = PET every 3rd frame (production baseline)

    # === UNIFIED RISK SCORE THRESHOLDS (0-100) ===
    # Single set of thresholds for all cameras -- no per-camera variation
    risk_threshold_medium: float = 35.0
    risk_threshold_high: float = 55.0
    risk_threshold_critical: float = 80.0

    # === MOTION LEVEL THRESHOLDS (m/s) ===
    # Based on crowd dynamics research (Fruin, Weidmann):
    # Walking ~1.2 m/s, brisk walking ~1.8 m/s, running ~3-5 m/s
    motion_threshold_slow: float = 0.1       # Below = STATIC (near-stationary)
    motion_threshold_normal: float = 0.5     # 0.1-0.5 = SLOW (shuffling, dense queue)
    motion_threshold_fast: float = 1.3       # 0.5-1.3 = NORMAL (walking pace)
    motion_threshold_running: float = 2.5    # 1.3-2.5 = FAST, >2.5 = RUNNING

    # Stampede Detection Parameters
    compression_threshold: float = -4.0  # Negative divergence threshold
    compression_weight: float = 10.0  # Risk score contribution from compression detection
    static_queue_motion_threshold: float = 0.15  # m/s — maximum motion to consider crowd as static queue
    static_queue_density_threshold: float = 3.0  # Minimum density to evaluate as potential queue
    static_queue_risk_dampening: float = 0.4  # Risk reduction factor for static queues (60% reduction)
    acceleration_threshold: float = 0.3  # m/s increase per flow interval that triggers "sudden acceleration"

    # Risk-Based Heatmap Colors (BGR + Alpha format for OpenCV)
    risk_color_blue: tuple = (255, 100, 0, 180)  # Low risk (0-25) - Blue
    risk_color_green: tuple = (0, 255, 0, 180)  # Normal (25-50) - Green
    risk_color_yellow: tuple = (0, 255, 255, 180)  # Elevated (50-75) - Yellow
    risk_color_red: tuple = (0, 0, 255, 180)  # Critical (75-100) - Red
    risk_heatmap_alpha: float = 0.6  # Overlay transparency (0-1)

    # Density backend (production PET-only)
    density_model: str = "pet"
    density_gaussian_sigma: float = 15.0  # Gaussian sigma for density map generation from PET points.
    enable_density_map_generation: bool = True  # If False, skip density-map generation unless runtime needs it.
    roi_cache_enabled: bool = True  # Cache ROI contour/masks to reduce per-frame polygon overhead.

    # PET Configuration
    pet_weights_path: Optional[str] = (
        get_resource_path("data/weights/SHB_model.pth")
        if os.path.exists(get_resource_path("data/weights/SHB_model.pth"))
        else get_resource_path("data/weights/SHA_model.pth")
    )
    pet_conf_threshold: float = 0.5
    pet_nms_distance: float = 6.0
    pet_max_height_sparse: int = 1280
    pet_max_height_medium: int = 1024
    pet_max_height_high: int = 896
    pet_max_height_default: int = 1024
    pet_use_adaptive_fusion: bool = True  # If false, use PET_DIRECT legacy count path (no YOLO blend)
    fusion_yolo_floor_enabled: bool = True  # In sparse/low/medium regimes, prevent under-predicting PET from dragging down YOLO count
    temporal_smoother_alpha: float = 0.6  # Responsive EMA alpha for real-time crowd dynamics

    # Regime-Based Fusion Configuration
    # Density Regime Thresholds (based on max of YOLO/PET count)
    density_regime_sparse_max: int = 15    # <15 = SPARSE
    density_regime_low_max: int = 50       # 15-50 = LOW
    density_regime_medium_max: int = 120   # 50-120 = MEDIUM, >120 = HIGH

    # YOLO Occupancy Thresholds (fraction of frame covered by bboxes)
    yolo_occupancy_low_max: float = 0.05      # <5% = sparse/low
    yolo_occupancy_medium_max: float = 0.15   # 5-15% = medium
    yolo_occupancy_high_max: float = 0.30     # 15-30% = high, >30% = very dense

    # Fusion Weights by Regime (PET weight; YOLO weight = 1 - this)
    fusion_weight_sparse: float = 0.5
    fusion_weight_low: float = 0.6
    fusion_weight_medium: float = 0.75
    fusion_weight_high: float = 0.95

    # PET dense-scene fusion guard.
    # In very dense scenes PET can outperform blended fusion; force PET-only count path.
    fusion_pet_guard_enabled: bool = True
    fusion_pet_guard_min_count: int = 220
    fusion_pet_guard_min_occupancy: float = 0.18
    fusion_pet_guard_skip_calibration: bool = True

    # Post-fusion count calibration (piecewise undercount correction)
    # Tuned from ShanghaiTech evaluation to reduce systematic negative bias.
    count_calibration_enabled: bool = True
    count_calibration_min_raw_count: int = 3
    count_calibration_max_multiplier: float = 1.40
    count_calibration_bin1_max: int = 50
    count_calibration_bin2_max: int = 200
    count_calibration_bin3_max: int = 500
    count_calibration_scale_bin1: float = 1.12   # <50
    count_calibration_scale_bin2: float = 1.28   # 50-200
    count_calibration_scale_bin3: float = 1.09   # 200-500
    count_calibration_scale_bin4: float = 1.19   # 500+

    # Performance Optimization Flags
    heatmap_async: bool = True  # Save heatmaps in background thread (removes 150-400ms blocking)
    analytics_batch_size: int = 10  # Batch analytics writes (saves I/O overhead)
    max_heatmap_queue_size: int = 10  # Max buffered heatmaps in background queue
    use_shared_model_pool: bool = True  # Share models across streams (95% GPU memory reduction)
    websocket_verbose_logging: bool = False  # Enable high-frequency websocket debug logs.
    zone_broadcast_min_interval_ms: int = 500  # Rate-limit zone broadcasts per station (2 Hz default).
    yolo_python_post_nms_enabled: bool = False  # Keep model-side NMS only by default.

    # Batched GPU Inference Configuration (Production-grade)
    # Now actually used! RTSPWorker creates CrowdAnalyzer with use_batched_inference=True
    use_batched_inference: bool = True  # Enable centralized GPU batching
    batch_yolo_size: int = 16  # Production baseline
    batch_timeout_ms: float = 200.0  # Accumulate bigger batches
    inference_queue_size: int = 100  # Production baseline
    inference_per_camera_limit: int = 2  # Production baseline
    inference_timeout_ms: float = 120000.0  # 120s default — CPU inference can take 30-60s per frame

    # MongoDB Configuration
    # Use values from .env only; leave blank if not configured.
    mongodb_uri: str = ""
    mongodb_database: str = ""
    mongodb_test_uri: Optional[str] = None
    mongodb_test_database: Optional[str] = None
    mongodb_max_pool_size: int = 100
    mongodb_connect_timeout_ms: int = 30000
    mongodb_auto_manage_indexes: bool = False  # If True, sync indexes during backend startup

    # Data Retention Policies
    analytics_retention_days: int = 30  # Auto-delete analytics older than 30 days
    alerts_retention_days: int = 90  # Keep alerts for 90 days
    images_retention_days: int = 90  # Keep images for 90 days
    detections_retention_days: int = 7  # Keep raw detections for 7 days (debugging only)

    # Alert System Configuration
    alert_cooldown_seconds: float = 1800.0  # Minimum time between alerts per camera (prevent spam)
    alert_image_risk_levels: str = "CRITICAL"  # Risk levels that trigger image capture (comma-separated)
    alert_min_severity: str = "CRITICAL"  # Minimum severity to consider for alerts
    alert_min_persist_seconds: float = 5.0  # Risk must persist this long before alerting
    alert_min_consecutive_frames: int = 3  # Minimum consecutive frames at/above severity
    alert_realert_interval_seconds: float = 120.0  # Re-alert if risk stays HIGH/CRITICAL for this long

    # Image Storage Configuration
    images_dir: str = "data/images"  # Directory for alert images
    image_jpeg_quality: int = 85  # JPEG quality for alert images (70-95 recommended)
    image_max_width: int = 1920  # Max width for saved images (maintains aspect ratio)

    # Image Storage Limits (prevents runaway storage)
    image_max_per_camera_per_hour: int = 20  # Max images per camera per hour
    image_max_per_camera_per_day: int = 100  # Max images per camera per day
    image_max_storage_gb: float = 10.0  # Max total image storage in GB (0 = unlimited)
    image_min_interval_seconds: float = 60.0  # Minimum seconds between images for same camera

    # WebSocket Configuration
    websocket_heartbeat_interval: float = 30.0  # Ping interval to keep connections alive
    websocket_max_connections_per_camera: int = 50  # Max concurrent connections per camera

    # Live Train API Configuration (RapidAPI)
    live_train_api_enabled: bool = True  # Enable/disable live train status fetching
    live_train_api_host: str = "train-running-api.p.rapidapi.com"
    live_train_api_key: str = ""  # Set via .env: LIVE_TRAIN_API_KEY
    
    live_train_fetch_interval_minutes: int = 10 # Fetch every N minutes (Increased for optimization)
    live_train_window_hours: float = 1.0  # Fetch for trains in next N hours
    live_train_station_code: str = "SC"  # Station code to filter (SC = Secunderabad)
    live_train_station_name: str = "Secunderabad Jn"  # Station Name for display

    # Firebase Realtime Database live sync
    firebase_enabled: bool = False
    firebase_database_url: str = ""
    firebase_service_account_path: str = ""

    # Persistence Worker Configuration
    persistence_analytics_queue_size: int = 1000  # Max buffered analytics before dropping
    persistence_alerts_queue_size: int = 500  # Max buffered alerts
    persistence_images_queue_size: int = 100  # Max buffered image metadata
    persistence_detections_queue_size: int = 500  # Max buffered detections (7-day TTL storage)
    persistence_batch_size: int = 20  # Batch size for analytics writes
    persistence_detections_batch_size: int = 50  # Batch size for detections writes
    persistence_flush_interval: float = 5.0  # Max seconds before flushing batch

    # Email Alert Configuration
    email_alerts_enabled: bool = False
    email_provider: str = "gmail"  # "gmail" or "milrcrosoft"

    # Gmail SMTP Configuration (with App Password)
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    msg91_whatsapp_enabled: bool = True
    msg91_auth_key: str = ""
    msg91_whatsapp_number: str = ""

    msg91_whatsapp_optin_template_id: str = ""
    msg91_whatsapp_subscribed_template_id: str = ""
    msg91_whatsapp_train_alert_template_id: str = ""

    msg91_whatsapp_otp_template_id: str = ""
    otp_master_phone: str = ""   # phone that gets a permanent non-expiring OTP
    otp_master_code: str = "070668"  # fixed OTP for that master phone

    msg91_train_delay_alert_template_id: str = ""
    msg91_platform_change_template_id: str = ""
    msg91_platform_assigned_template_id: str = "platform_alert"
    msg91_whatsapp_crowd_alert_template_id: str = ""
    msg91_whatsapp_booking_office_template_id: str = "bookingoffice_alert"
    msg91_custom_whatsapp_message_template_id: str = "camera_alert"

    fob_analytics_whatsapp_threshold: int = 120
    booking_office_alert_threshold: int = 190
    booking_office_alternate_clear_threshold: int = 120
    booking_office_recheck_delay_seconds: float = 180.0
    booking_office_alert_cooldown_seconds: float = 3600.0


  
    # aws_region :str ="ap-south-1"
    # aws_s3_bucket : str ="surakshai"

    # sarvam_api_key: str = ""  # Sarvam AI API key for TTS (set via .env)    
    sarvam_tts_model: str = "Bulbul V2"  # Sarvam TTS model name
    sarvam_tts_speaker: str = "manisha"  # Sarvam T
    

   

    
    # Microsoft OAuth2 Configuration (for corporate accounts)
    microsoft_tenant_id: str = ""  # Azure AD Tenant ID
    microsoft_client_id: str = ""  # Application (client) ID
    microsoft_client_secret: str = ""  # Client secret value
    microsoft_sender_email: str = ""  # Sender email address
    # Common Email Settings
    alert_receiver_emails: str = ""  # Recipient emails (comma-separated in .env), parsed to list by validator
    email_alert_cooldown_seconds: float = 600.0  # Email specific cooldown (e.g. 10 minutes)
    email_alert_levels: str = "HIGH,CRITICAL"  # Risk levels that trigger email alerts (comma-separated)
    whatsapp_alert_cooldown_seconds: float = 1800.0  # WhatsApp cooldown (default 10 minutes)

    # Flow Analysis Service (replaces FOB congestion service)
    flow_analysis_enabled: bool = True
    flow_analysis_interval: float = 10.0              # seconds between analysis cycles
    flow_history_window_seconds: float = 300.0        # rolling history window (5 min)
    flow_snapshot_interval: float = 10.0              # seconds between count snapshots
    flow_delta_min_threshold: int = 5                 # minimum people change to count as significant
    flow_congestion_density_threshold: float = 2.5    # people/m² to mark FOB zone as congested
    flow_alternative_density_threshold: float = 1.5   # max density to recommend as alternative
    flow_congestion_min_persist_seconds: float = 15.0 # congestion must sustain before advisory
    flow_congestion_cooldown_seconds: float = 60.0    # min gap between advisories per station
    flow_adjacency_max_hops: int = 2                  # max hops in adjacency graph for source attribution
    flow_filling_threshold: int = 10                   # delta_5min >= this = "filling"
    flow_emptying_threshold: int = 10                  # delta_5min <= -this = "emptying"

    # Island Platform Configuration (Phase-1: Historical + Planning Based)
    island_platform_detection_enabled: bool = True  # Enable/disable island platform footfall detection
    island_footfall_threshold: int = 900  # Passengers per 45-min window that triggers alert
    island_alert_window_minutes: int = 45  # Sliding window duration
    island_alert_step_minutes: int = 5  # Sliding window step size
    island_planning_advance_minutes: int = 90  # Start alerts N minutes before first train

    # Platform Certainty Label Thresholds
    platform_certainty_high_threshold: float = 80.0  # ≥80% stability = HIGH certainty
    platform_certainty_medium_threshold: float = 50.0  # 50-79% stability = MEDIUM certainty
    # <50% stability = LOW certainty

    # Island Risk Level Thresholds (multiplier of baseline threshold)
    island_risk_medium_threshold: float = 1.0  # At threshold = MEDIUM risk
    island_risk_high_threshold: float = 1.25  # 25% over threshold = HIGH risk
    island_risk_critical_threshold: float = 1.5  # 50% over threshold = CRITICAL risk

    # Station Configuration
    station_code: str = "SC"  # Secunderabad (already exists but included here for clarity)
    station_name: str = "Secunderabad Junction"  # Full station name

    # Camera Sharding & Multi-Pod Scaling
    camera_shard_count: int = 1  # Total number of pod shards
    camera_shard_index: Optional[int] = None  # None = auto-detect from HOSTNAME ordinal, or integer 0, 1...
    headless_service_name: str = "crowdvision-backend-headless"
    headless_service_port: int = 8000
    internal_forward_timeout: float = 5.0

    # Live Streaming Cadence & Telemetry
    live_stream_max_fps: int = 25  # Max FPS for live stream generator (replaces artificial 1s sleep)
    enable_live_frame_telemetry: bool = True

    # Zone Analytics State & TTL
    zone_analytics_cache_ttl: float = 30.0  # Max seconds to preserve last-known camera metrics before declaring NO_DATA

    # Security & Authentication (JWT only for local railway station deployment)
    auth_enabled: bool = True  # Set to True in production
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET"  # Override via JWT_SECRET env var
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Properties to convert comma-separated strings to lists
    @property
    def email_alert_levels_list(self) -> list:
        """Get email alert levels as a list"""
        if not self.email_alert_levels:
            return []
        return [item.strip().upper() for item in self.email_alert_levels.split(',') if item.strip()]

    @property
    def alert_image_risk_levels_list(self) -> list:
        """Get alert image risk levels as a list"""
        if not self.alert_image_risk_levels:
            return []
        return [item.strip().upper() for item in self.alert_image_risk_levels.split(',') if item.strip()]

    @property
    def alert_receiver_emails_list(self) -> list:
        """Get receiver emails as a list"""
        if not self.alert_receiver_emails:
            return []
        return [item.strip() for item in self.alert_receiver_emails.split(',') if item.strip()]

    @property
    def extra_allowed_origins_list(self) -> list:
        """Return extra allowed origins as a list parsed from comma-separated env var"""
        if not self.extra_allowed_origins:
            return []
        return [item.strip() for item in self.extra_allowed_origins.split(',') if item.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create directories on import
def create_directories():
    """Create necessary directories"""
    settings = get_settings()
    dirs = [
        settings.upload_dir,
        settings.output_dir,
        settings.models_dir,
        settings.heatmap_dir,
        settings.analytics_dir,
        settings.images_dir,
    ]
    if settings.log_file:
        dirs.append(os.path.dirname(settings.log_file))
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)


create_directories()
