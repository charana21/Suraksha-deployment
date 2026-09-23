"""
Startup/shutdown helpers for the FastAPI lifespan.

Extracted from api.main.lifespan to keep cognitive complexity of that
function low; each function here handles one independent startup concern.
"""
import asyncio
import os
import time
from services.camera_service import CameraService
from db.mongodb import MongoDB
from services.live_refresh_toggle_service import LiveTrainRefreshToggleService
from services.live_train_service import LiveTrainService
from models.model_wrapper import SharedModelPool
from services.batched_inference import BatchedInferenceService
from utils.logging_config import get_logger

logger = get_logger("crowdvision.main")


async def ensure_announcement_indexes():
    try:
        if MongoDB.database is not None:
            await MongoDB.database.train_announcements.create_index([("updated_at", -1)])
            await MongoDB.database.train_announcements.create_index(
                [("station_code", 1), ("updated_at", -1)]
            )
            logger.info("MongoDB announcement indexes ensured")
    except Exception as e:
        logger.warning(f"Failed to create MongoDB indexes for announcements: {e}")


async def ensure_forecasting_collections():
    """Initializes MongoDB collections historical_data and forecasting_data from reference CSVs if empty."""
    try:
        if MongoDB.database is not None:
            from services.forecasting.data_loader import seed_all_collections
            from services.footfallinsights import FootfallInsightsService
            await FootfallInsightsService.ensure_indexes()
            res = seed_all_collections()
            logger.info(f"MongoDB historical_data and forecasting_data initialized: {res}")
    except Exception as e:
        logger.warning(f"Failed to initialize forecasting data collections: {e}")


def start_auto_forecast_watcher() -> "asyncio.Task":
    """
    Starts the AutoForecastTrigger background watcher task.
    This polls `historical_data` every 5 minutes and auto-runs the
    UTS/PRS forecasting pipeline whenever new data is detected.
    Call once during app startup, after MongoDB is connected.
    """
    try:
        from services.forecasting.auto_pipeline import AutoForecastTrigger
        task = AutoForecastTrigger.start_watcher_task()
        logger.info("AutoForecastTrigger watcher started — will auto-run pipeline on historical_data changes.")
        return task
    except Exception as e:
        logger.warning(f"Failed to start AutoForecastTrigger watcher: {e}")
        return None


def create_directories(settings):
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.heatmap_dir, exist_ok=True)
    os.makedirs(settings.analytics_dir, exist_ok=True)
    os.makedirs(settings.images_dir, exist_ok=True)


async def migrate_calibrations():
    try:
        await CameraService.migrate_calibrations_from_json()
    except Exception:
        logger.exception("Failed to migrate calibrations")
        logger.warning("Continuing without calibration migration")


async def load_platform_history(settings):
    if not settings.island_platform_detection_enabled:
        logger.info("Island platform detection disabled")
        return

    logger.info("Island platform detection enabled - loading platform history...")
    try:
        from services.platform_history_service import platform_history_service
        csv_path = "platform_occupation_summary_CORRECTED.csv"

        if not os.path.exists(csv_path):
            logger.warning(f"Platform history CSV not found: {csv_path}")
            logger.warning("Island platform detection will be limited without platform history")
            return

        logger.info(f"Loading platform history from: {csv_path}")
        result = await platform_history_service.load_platform_history_from_csv(csv_path)
        logger.info(
            f"Platform history loaded: {result['records_loaded']} new, "
            f"{result['records_updated']} updated, "
            f"{len(result.get('errors', []))} errors"
        )

        stats = await platform_history_service.get_collection_stats()
        logger.info(
            f"Platform history stats: {stats['total_trains']} trains "
            f"({stats['stable_trains']} stable, {stats['unstable_trains']} unstable)"
        )
    except Exception:
        logger.exception("Failed to load platform history")
        logger.warning("Island platform detection will continue without historical data")


def init_shared_model_pool(settings):
    if not settings.use_shared_model_pool:
        logger.info("SharedModelPool disabled - each stream will load its own models")
        return

    logger.info("Initializing SharedModelPool (95% GPU memory reduction)...")
    pool = SharedModelPool.get_instance()
    pool.initialize(
        yolo_path=settings.yolo_model_path,
        device=settings.device,
        density_model=settings.density_model,
        density_gaussian_sigma=settings.density_gaussian_sigma,
        pet_weights_path=settings.pet_weights_path,
        pet_conf_threshold=settings.pet_conf_threshold,
        pet_nms_distance=settings.pet_nms_distance
    )
    logger.info("SharedModelPool initialized - all streams will share models")


def init_batched_inference(settings):
    if not settings.use_batched_inference:
        logger.info("BatchedInferenceService disabled - using legacy serial inference")
        return None

    logger.info("Initializing BatchedInferenceService (production batching)...")
    service = BatchedInferenceService.get_instance(settings)
    service.start()
    logger.info(
        f"BatchedInferenceService started - batch size: {settings.batch_yolo_size}, "
        f"timeout: {settings.batch_timeout_ms}ms"
    )
    return service


async def build_zone_type_lookup():
    zone_type_lookup = {}
    try:
        from db.mongodb import get_database
        _db = get_database()
        if _db:
            _zones = await _db.zones.find({}, {"zone_id": 1, "zone_type": 1}).to_list(100)
            zone_type_lookup = {z["zone_id"]: z.get("zone_type") for z in _zones}
            logger.info(f"Loaded zone_type lookup: {len(zone_type_lookup)} zones")
    except Exception as e:
        logger.warning(f"Could not load zone_type lookup: {e}")
    return zone_type_lookup


def _start_camera_stream(rtsp_manager, camera, zone_type_lookup):
    cam_settings = camera.get("settings", {})
    target_fps = cam_settings.get("target_fps", 1)
    cam_zone_id = camera.get("zone_id")

    stream_id = rtsp_manager.start_stream(
        rtsp_url=camera["rtsp_url"],
        camera_id=camera["camera_id"],
        stream_id=camera["camera_id"],  # FORCE 1:1 Mapping
        target_fps=target_fps,
        name=camera["name"],
        location=camera.get("location", "Unknown"),
        fob_type=camera.get("fob_type"),
        zone_id=cam_zone_id,
        zone_type=zone_type_lookup.get(cam_zone_id)
    )
    logger.info(f"Auto-started stream for camera: {camera['name']} (ID: {stream_id})")


async def start_active_cameras(settings, rtsp_manager):
    logger.info("Loading active cameras...")
    try:
        active_cameras = await CameraService.get_active_cameras()
        logger.info(f"Found {len(active_cameras)} active cameras in database")
        zone_type_lookup = await build_zone_type_lookup()

        for camera in active_cameras:
            # Determine debug target stream from environment (allow misspelling) or settings
            debug_target = (
                os.getenv("DEBUG_TARGET_STREAM")
                or settings.debug_target_stream
            )
            if debug_target:
                debug_target = debug_target.strip()
                if (debug_target.startswith('"') and debug_target.endswith('"')) or (
                    debug_target.startswith("'") and debug_target.endswith("'")
                ):
                    debug_target = debug_target[1:-1]

            if settings.debug_single_stream and debug_target and camera.get("rtsp_url") != debug_target:
                logger.debug(f"Skipping {camera['name']} - debug mode active")
                continue

            try:
                _start_camera_stream(rtsp_manager, camera, zone_type_lookup)
            except Exception:
                logger.exception(f"FAILED to auto-start camera {camera.get('camera_id')}")
    except Exception:
        logger.exception("Error loading cameras")


async def train_schedule_broadcaster(websocket_manager):
    """Periodically broadcast upcoming trains to WebSocket subscribers"""
    from services.train_schedule_service import TrainScheduleService

    while True:
        await asyncio.sleep(60)
        try:
            if websocket_manager.get_train_subscribers() > 0:
                data = await TrainScheduleService.get_upcoming_trains()
                await websocket_manager.broadcast_train_schedule_update(
                    event="upcoming_update",
                    data=data
                )
        except Exception:
            logger.exception("Train schedule broadcast error")


async def suraksha_optin_scheduler():
    from services.suraksha_optin_service import SurakshaOptInService
    await SurakshaOptInService.run_daily_scheduler()


async def suraksha_reset_scheduler():
    from services.suraksha_optin_service import SurakshaOptInService
    await SurakshaOptInService.run_reset_alerts_scheduler()


async def announcement_generator(settings, trigger_announcement_event):
    """Generate next-hour train announcements, triggered by live fetch or fallback timer"""
    import train_announcement

    await asyncio.sleep(10)
    while True:
        try:
            await train_announcement.generate_next_hour_announcements()
        except Exception:
            logger.exception("Announcement generation failed")

        try:
            await asyncio.wait_for(
                trigger_announcement_event.wait(),
                timeout=settings.live_train_fetch_interval_minutes * 60
            )
            trigger_announcement_event.clear()
        except asyncio.TimeoutError:
            pass


async def _run_live_train_fetch_cycle(settings, logger_):
    logger_.info("Starting live train status fetch cycle...")
    stats = await LiveTrainService.run_hourly_fetch_cycle()
    logger_.info(
        f"Live train fetch complete: fetched={stats.get('fetched', 0)}, "
        f"failed={stats.get('failed', 0)}, skipped={stats.get('skipped', 0)}"
    )


async def live_train_fetcher(settings, trigger_announcement_event):
    """Fetch live train status from RapidAPI every hour for upcoming trains"""
    await asyncio.sleep(30)

    last_fetch_time = 0
    fetch_interval_seconds = settings.live_train_fetch_interval_minutes * 60

    while True:
        try:
            toggle_enabled = await LiveTrainRefreshToggleService.is_live_refresh_enabled()
            current_time = time.time()
            time_since_last_fetch = current_time - last_fetch_time

            if toggle_enabled and time_since_last_fetch >= fetch_interval_seconds:
                if settings.live_train_api_enabled and settings.live_train_api_key:
                    await _run_live_train_fetch_cycle(settings, logger)
                    last_fetch_time = current_time
                    trigger_announcement_event.set()
                else:
                    logger.debug("Live train API disabled or no API key configured")
            elif not toggle_enabled:
                logger.debug("Live train refresh toggle is OFF; not fetching.")
            else:
                remaining_time = fetch_interval_seconds - time_since_last_fetch
                logger.debug(f"Waiting {remaining_time:.0f}s before next fetch...")
        except Exception:
            logger.exception("Live train fetch error")

        await asyncio.sleep(60)


async def flow_analysis_runner(settings, flow_service):
    """Periodically run flow analysis cycle (snapshots, deltas, congestion)"""
    while True:
        await asyncio.sleep(settings.flow_analysis_interval)
        try:
            await flow_service.run_cycle()
        except Exception:
            logger.exception("Flow analysis cycle error")


def start_flow_analysis(settings):
    if not settings.flow_analysis_enabled:
        logger.info("Flow analysis service disabled")
        return None

    from services.flow_analysis_service import FlowAnalysisService, set_flow_service
    flow_service = FlowAnalysisService(settings)
    set_flow_service(flow_service)  # expose singleton for zone_analytics to read

    task = asyncio.create_task(flow_analysis_runner(settings, flow_service))
    logger.info(f"Flow analysis service started ({settings.flow_analysis_interval}s interval)")
    return task


def cancel_task(task, stopped_message):
    if task:
        task.cancel()
        logger.info(stopped_message)
