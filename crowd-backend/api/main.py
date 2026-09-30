"""
FastAPI main application
"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import signal
import sys
import multiprocessing
from config.config import get_settings
from api.routes import analysis, analytics, health, rtsp, cameras, alerts, websocket_routes, images, zones, trains, island_alerts, calibration, location, user_login
import train_announcement
from services.rtsp_manager import get_rtsp_manager
from services.camera_service import CameraService
from db.mongodb import connect_to_mongo, close_mongo_connection
from services import footfallinsights
from services.persistence_worker import PersistenceWorker
from services.websocket_manager import get_connection_manager
from utils.logging_config import setup_logging, get_logger
from api.security import require_viewer, require_authorized
from api.middleware.error_handlers import register_error_handlers
from api import startup as lifespan_tasks


async def _startup(app: FastAPI, settings):
    """Run all startup steps and populate app.state; returns the logger."""
    setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
        app_env=settings.app_env
    )
    logger = get_logger("crowdvision.main")

    logger.info("=" * 50)
    logger.info("CrowdVision API v1.0.0 Starting...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Device: {settings.device}")
    logger.info("=" * 50)

    lifespan_tasks.create_directories(settings)

    await connect_to_mongo(settings)
    logger.info("MongoDB connection initialized")
    await lifespan_tasks.ensure_announcement_indexes()
    await lifespan_tasks.ensure_forecasting_collections()
    app.state.auto_forecast_watcher_task = lifespan_tasks.start_auto_forecast_watcher()

    persistence_worker = PersistenceWorker(settings)
    await persistence_worker.start()
    logger.info("PersistenceWorker started")

    logger.info("Seeding cameras from configuration...")
    await CameraService.seed_cameras_from_config()
    logger.info("Camera seeding complete")

    await lifespan_tasks.migrate_calibrations()
    await lifespan_tasks.load_platform_history(settings)

    websocket_manager = get_connection_manager()
    logger.info("WebSocket Manager initialized")

    lifespan_tasks.init_shared_model_pool(settings)
    batched_inference_service = lifespan_tasks.init_batched_inference(settings)

    rtsp_manager = get_rtsp_manager()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    rtsp_manager.set_services(
        persistence_worker=persistence_worker,
        websocket_manager=websocket_manager,
        async_loop=loop
    )
    logger.info("RTSP Manager initialized with shared services")

    await lifespan_tasks.start_active_cameras(settings, rtsp_manager)

    app.state.persistence_worker = persistence_worker
    app.state.websocket_manager = websocket_manager
    app.state.rtsp_manager = rtsp_manager
    app.state.batched_inference_service = batched_inference_service

    app.state.train_broadcaster_task = asyncio.create_task(
        lifespan_tasks.train_schedule_broadcaster(websocket_manager)
    )
    logger.info("Train schedule broadcaster started (60s interval)")

    app.state.suraksha_optin_task = asyncio.create_task(lifespan_tasks.suraksha_optin_scheduler())
    app.state.suraksha_reset_task = asyncio.create_task(lifespan_tasks.suraksha_reset_scheduler())
    logger.info("Suraksha opt-in and reset schedulers started")

    trigger_announcement_event = asyncio.Event()
    app.state.announcement_task = asyncio.create_task(
        lifespan_tasks.announcement_generator(settings, trigger_announcement_event)
    )
    logger.info(
        f"Announcement generator started (synchronized, max "
        f"{settings.live_train_fetch_interval_minutes} min interval)"
    )

    if settings.live_train_api_enabled:
        app.state.live_train_fetcher_task = asyncio.create_task(
            lifespan_tasks.live_train_fetcher(settings, trigger_announcement_event)
        )
        logger.info(f"Live train fetcher started ({settings.live_train_fetch_interval_minutes}min interval)")
    else:
        app.state.live_train_fetcher_task = None
        logger.info("Live train fetcher disabled (API not enabled)")

    app.state.flow_analysis_task = lifespan_tasks.start_flow_analysis(settings)

    return logger


async def _shutdown(app: FastAPI, logger):
    cancel_task = lifespan_tasks.cancel_task
    cancel_task(app.state.train_broadcaster_task, "Train schedule broadcaster stopped")
    cancel_task(app.state.suraksha_optin_task, "Suraksha opt-in scheduler stopped")
    cancel_task(app.state.suraksha_reset_task, "Suraksha reset scheduler stopped")
    cancel_task(app.state.announcement_task, "Announcement generator stopped")
    cancel_task(app.state.live_train_fetcher_task, "Live train fetcher stopped")
    cancel_task(app.state.flow_analysis_task, "Flow analysis service stopped")
    # Stop the auto-forecast watcher
    try:
        from services.forecasting.auto_pipeline import AutoForecastTrigger
        AutoForecastTrigger.stop()
    except Exception:
        pass

    logger.info("=" * 50)
    logger.info("CrowdVision API Shutting Down...")
    logger.info("=" * 50)

    logger.info("Stopping all RTSP streams...")
    app.state.rtsp_manager.shutdown()
    logger.info("RTSP streams stopped")

    if app.state.batched_inference_service is not None:
        logger.info("Stopping BatchedInferenceService...")
        app.state.batched_inference_service.stop()
        logger.info("BatchedInferenceService stopped")

    logger.info("Stopping PersistenceWorker...")
    await app.state.persistence_worker.stop()
    logger.info("PersistenceWorker stopped")

    logger.info("Closing MongoDB connection...")
    await close_mongo_connection()
    logger.info("MongoDB connection closed")

    logger.info("CrowdVision API shutdown complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    settings = get_settings()
    logger = await _startup(app, settings)

    yield

    await _shutdown(app, logger)


app = FastAPI(
    title="CrowdVision API",
    description="Production crowd analysis with RTSP streaming support",
    version="1.0.0",
    lifespan=lifespan
)
register_error_handlers(app)

settings = get_settings()
allowed_origins = [
     "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://crowdanalytics-api.tride.live",
    "https://surakshaai.tride.live",
    "http://localhost:80",
    "http://localhost:5080",
    "http://127.0.0.1:5080",
    "https://sec-dt-dev.tride.live",
    "https://sec-dt.tride.live",
    "https://dev.surakshaai.tride.live"
]

# Include any extra allowed origins from settings (avoid hardcoded IPs in source)
if getattr(settings, "extra_allowed_origins_list", None):
    allowed_origins.extend(settings.extra_allowed_origins_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.ngrok-free\.dev",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"], dependencies=[require_viewer])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"], dependencies=[require_viewer])
app.include_router(rtsp.router, prefix="/api", tags=["RTSP Streaming"])
app.include_router(cameras.router, prefix="/api", tags=["Cameras"], dependencies=[require_authorized])
app.include_router(zones.router, prefix="/api", tags=["Zones"], dependencies=[require_viewer])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"], dependencies=[require_viewer])
app.include_router(websocket_routes.router, prefix="/api", tags=["WebSocket"])
app.include_router(images.router, prefix="/api", tags=["Images"], dependencies=[require_viewer])
app.include_router(trains.router, prefix="/api", tags=["Trains"])
app.include_router(train_announcement.router, prefix="/api", tags=["Announcements"])
app.include_router(island_alerts.router, prefix="/api", tags=["Island Platform Alerts"], dependencies=[require_viewer])
app.include_router(calibration.router, prefix="/api", tags=["Calibration"], dependencies=[require_authorized])
app.include_router(footfallinsights.router, prefix="/api", tags=["Footfall Insights"])
app.include_router(location.router, prefix="/api", tags=["Location"])
app.include_router(user_login.router, prefix="/api")
    # Removed webhooks.router


@app.get("/api/docs", include_in_schema=False)
async def api_docs():
    """Redirect /api/docs to /docs for Swagger UI"""
    return RedirectResponse(url="/docs")


@app.get("/api/openapi.json", include_in_schema=False)
async def api_openapi():
    """Redirect /api/openapi.json to /openapi.json"""
    return RedirectResponse(url="/openapi.json")


@app.get("/api/redoc", include_in_schema=False)
async def api_redoc():
    """Redirect /api/redoc to /redoc for ReDoc"""
    return RedirectResponse(url="/redoc")


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "CrowdVision API v1.0.0",
        "endpoints": {
            "docs": "/docs",
            "api_docs": "/api/docs",
            "master_auth": {
                "login": "POST /api/master/login",
                "users": "GET/POST/PUT/DELETE /api/master/users/*",
                "roles": "GET/POST/PUT/DELETE /api/master/roles/*",
                "modules": "GET/POST/PUT/DELETE /api/master/modules/*"
            },
            "health": "/api/health",
            "analyze": "POST /api/analyze",
            "status": "GET /api/status/{job_id}",
            "rtsp": {
                "start": "POST /api/rtsp/start",
                "stop": "POST /api/rtsp/stop/{stream_id}",
                "status": "GET /api/rtsp/status/{stream_id}",
                "list": "GET /api/rtsp/list",
                "frame": "GET /api/rtsp/frame/{stream_id} (admin only)",
                "live": "GET /api/rtsp/live/{stream_id} (admin only)"
            },
            "cameras": {
                "list": "GET /api/cameras (viewer/operator/admin)",
                "create_update_delete": "POST/PUT/DELETE /api/cameras/* (admin only)"
            },
            "zones": {
                "list": "GET /api/zones",
                "create": "POST /api/zones",
                "analytics": "GET /api/zones/analytics",
                "ws_all": "ws://host/api/ws/zones/analytics",
                "ws_station": "ws://host/api/ws/zones/analytics/{station_id}"
            },
            "trains": {
                "upload": "POST /api/trains/upload",
                "upcoming": "GET /api/trains/upcoming",
                "schedule": "GET /api/trains/schedule",
                "dates": "GET /api/trains/dates",
                "ws": "ws://host/api/ws/trains"
            }
        }
    }


def start_server():
    import uvicorn
    settings = get_settings()

    # Configure signal handlers for graceful shutdown
    def handle_signal(signum, _frame):
        """Handle shutdown signals gracefully"""
        sig_name = signal.Signals(signum).name
        print(f"\n[SIGNAL] Received {sig_name}, initiating graceful shutdown...")
        sys.exit(0)

    # Register signal handlers (Windows compatible)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Production config
    use_reload = (settings.app_env == "development")
    
    # In frozen mode (PyInstaller), we must pass the app object directly
    # Import string "api.main:app" fails because the module is __main__
    config = uvicorn.Config(
        "api.main:app" if use_reload else app,
        host=settings.api_host,
        port=settings.api_port,
        reload=use_reload,
        log_level="info" if settings.app_env == "development" else "warning",
        access_log=(settings.app_env == "development"),
        timeout_graceful_shutdown=30  # 30 second timeout for graceful shutdown
    )

    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    start_server()
