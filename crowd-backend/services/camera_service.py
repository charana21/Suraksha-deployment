"""
Camera metadata management service
Provides CRUD operations for camera metadata (single source of truth)
"""
from typing import Optional, List, Dict, Any
from datetime import UTC, datetime, timedelta, timezone
import json
import logging
import os
import time
import asyncio
import aiofiles
from pymongo import DESCENDING
from db.mongodb import MongoDB
from services.notification_service import NotificationService
logger = logging.getLogger(__name__)

FEED_MONITOR_CAMERAS_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "feed_monitor_cameras.json",
)

# ============================================================
# INITIAL CAMERA DEFINITIONS (ONE-TIME SEEDING)
# Must match seed_platform_zones.py (single source of truth)
# ============================================================
CUSTOM_LEGACY_PF_DEFAULT_NAMES = {
    "cam_hyb_pf1": "PF 1 NEAR KZJ END FACING GATE 2",
    "cam_hyb_pf2": "PF 2 KZJ FOB FACING RRI",
    "cam_hyb_pf4": "PF 4&5 NEAR KZJ FOB FACING HYB",
    "cam_hyb_pf8": "PF 8 NEAR KZJ FOB FACING HYB",
    "cam_hyb_pf10": "PF 10 OPPOSITE TO GATE 8 FACING KZJ END",
}

CUSTOM_MULTI_PF_DEFAULT_NAMES = {
    "cam_hyb_pf1_a": "PF 1 NEAR GATE 4 FACING HYB",
}

INITIAL_CAMERAS = [
    # --- HYB FOB CAMERAS (9) → zone_hyb_fob ---
    {"camera_id": "cam_pf1_fob_kzj",       "default_name": "HYB FOB FACING PF 10",         "rtsp_url": "rtsp://localhost:8554/mystream",       "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf1_fob_pf10",       "default_name": "PF 1 HYB FOB FC PF 10",        "rtsp_url": "rtsp://localhost:8554/mystream1",      "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf1_hyd_fob_fc_hyd_end", "default_name": "PF 1 HYD FOB FACING HYD END", "rtsp_url": "rtsp://localhost:8554/mystream",       "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_middle_fob_4_5",     "default_name": "HYB FOB MIDDLE FACING PF 4&5",  "rtsp_url": "rtsp://localhost:8554/middle_4_5",     "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_middle_fob_6_7",     "default_name": "HYB FOB MIDD FC 6&7",           "rtsp_url": "rtsp://localhost:8554/middle_6_7",     "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf10_fob_pf1",       "default_name": "PF 10 HYB FOB FC PF1",          "rtsp_url": "rtsp://localhost:8554/pf10_pf1",       "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf10_fob_steps",     "default_name": "PF 10 HYB FOB FC HYB STEPS",    "rtsp_url": "rtsp://localhost:8554/pf10_steps",     "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf10_fob_vip",       "default_name": "PF 10 HYB FOB FC VIP ENTRANCE", "rtsp_url": "rtsp://localhost:8554/pf10_vip",       "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf1_fob_lift",       "default_name": "PF 1 HYB FOB LIFT",             "rtsp_url": "rtsp://localhost:8554/pf1_lift",       "fob_type": "HYD", "zone_id": "zone_hyb_fob"},
    {"camera_id": "cam_pf1_fob_hyb_end",    "default_name": "PF 10 HYB FOB PATHWAY FACING PF 1", "rtsp_url": "rtsp://localhost:8554/pf1_fob_hyb_end", "fob_type": "HYD", "zone_id": "zone_hyb_fob"},

    # --- KZJ FOB CAMERAS (6) → zone_kzj_fob ---
    {"camera_id": "cam_kzj_pf1_fob_kzj",   "default_name": "PF 1 KZJ FOB FACING PF 10",     "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_kzj",  "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},
    {"camera_id": "cam_kzj_pf1_fob_pf10",  "default_name": "KZJ FOB ESCALATOR FACING PF 1", "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_pf10", "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},
    {"camera_id": "cam_kzj_pf1_fob_hyb",    "default_name": "PF 1 KZJ FOB FC HYB END",       "rtsp_url": "rtsp://localhost:8554/kzj_pf1_fob_hyb",  "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},
    {"camera_id": "cam_kzj_fob_mid_4_5",    "default_name": "KZJ FOB MIDD FC 4&5",            "rtsp_url": "rtsp://localhost:8554/kzj_fob_mid_4_5",  "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},
    {"camera_id": "cam_kzj_fob_mid_8_9",    "default_name": "KZJ FOB MIDD FC 8&9",            "rtsp_url": "rtsp://localhost:8554/kzj_fob_mid_8_9",  "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},
    {"camera_id": "cam_kzj_fob_escalator",  "default_name": "PF 10 KZJ FOB ESCL FC PF1",      "rtsp_url": "rtsp://localhost:8554/kzj_fob_escalator", "fob_type": "KZJ", "zone_id": "zone_kzj_fob"},

    # --- Middle FOB CAMERAS (3) → zone_mid_fob ---
    {"camera_id": "cam_mid_fob_pf1",    "default_name": "NEW KZJ FOB FACING PF 10",        "rtsp_url": "rtsp://localhost:8554/mid_fob_pf1",    "fob_type": "HYD", "zone_id": "zone_mid_fob"},
    {"camera_id": "cam_mid_fob_center", "default_name": "NEW KZJ FOB MIDDLE FACING PF 10", "rtsp_url": "rtsp://localhost:8554/mid_fob_center",  "fob_type": "HYD", "zone_id": "zone_mid_fob"},
    {"camera_id": "cam_mid_fob_pf10",   "default_name": "Middle FOB PF10 Side",            "rtsp_url": "rtsp://localhost:8554/mid_fob_pf10",    "fob_type": "HYD", "zone_id": "zone_mid_fob"},

    # --- Platform CAMERAS ---
    *[{"camera_id": f"cam_hyb_pf{n}", "default_name": CUSTOM_LEGACY_PF_DEFAULT_NAMES.get(f"cam_hyb_pf{n}", f"Platform {n} Camera"), "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}", "fob_type": None, "zone_id": f"zone_hyb_pf{n}"} for n in range(1, 11)],
    *[
        cam
        for n in range(1, 11)
        for cam in [
            {"camera_id": f"cam_hyb_pf{n}_a", "default_name": CUSTOM_MULTI_PF_DEFAULT_NAMES.get(f"cam_hyb_pf{n}_a", f"Platform {n} Start Camera"),  "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_a", "fob_type": None, "zone_id": f"zone_hyb_pf{n}"},
            {"camera_id": f"cam_hyb_pf{n}_b", "default_name": f"Platform {n} Middle Camera", "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_b", "fob_type": None, "zone_id": f"zone_hyb_pf{n}"},
            {"camera_id": f"cam_hyb_pf{n}_c", "default_name": f"Platform {n} End Camera",    "rtsp_url": f"rtsp://localhost:8554/hyb_pf{n}_c", "fob_type": None, "zone_id": f"zone_hyb_pf{n}"},
        ]
    ],

    # --- Booking CAMERAS ---
    {"camera_id": "cam_hyb_booking", "default_name": "GATE 2A BOOKING COUNTER", "rtsp_url": "rtsp://localhost:8554/hyb_booking", "fob_type": None, "zone_id": "zone_hyb_booking"},
    {"camera_id": "cam_hyb_booking_gate6", "default_name": "GATE 6 BOOKING OFFICE", "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate6", "fob_type": None, "zone_id": "zone_gate6_booking"},
    {"camera_id": "cam_hyb_booking_gate8", "default_name": "GATE 8 OUTSIDE", "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate8", "fob_type": None, "zone_id": "zone_hyb_booking"},
    {"camera_id": "cam_hyb_booking_gate4a", "default_name": "GATE 4 GENERAL WAITING HALL", "rtsp_url": "rtsp://localhost:8554/hyb_booking_gate4a", "fob_type": None, "zone_id": "zone_gate4a_booking"},
]

# Old granular FOB zone IDs to clean up on startup
OLD_FOB_ZONE_IDS = [
    "zone_pf1_fob_kzj", "zone_pf1_hyb_fob_fc_pf10", "zone_pf1_fob_hyb_end",
    "zone_middle_fob_4_5", "zone_middle_fob_6_7",
    "zone_pf10_hyb_fob_fc_pf1", "zone_pf10_fob_steps", "zone_pf10_fob_vip", "zone_pf1_fob_lift",
    "zone_pf1_kzj_fob_fc_kzj", "zone_new_kzj_fob_middle_fc_pf10", "zone_pf1_kzj_fob_fc_hyb",
    "zone_kzj_fob_middle_fc_4_5", "zone_kzj_fob_middle_fc_8_9", "zone_kzj_fob_escalator_fc_pf1",
]

# Old camera IDs that were renamed and should be cleaned up on startup
OLD_KZJ_CAMERA_IDS = [
    "cam_kzj_pf1_fc_kzj", "cam_kzj_pf1_fc_pf10", "cam_kzj_pf1_fc_hyb",
    "cam_kzj_mid_4_5", "cam_kzj_mid_8_9", "cam_kzj_escl_pf1", "cam_pf1_fob_hyb_end",
]


class CameraService:
    """Camera metadata CRUD operations"""

    _feed_monitor_config: Optional[Dict[str, Any]] = None

    @staticmethod
    def _load_feed_monitor_config() -> Dict[str, Any]:
        if CameraService._feed_monitor_config is not None:
            return CameraService._feed_monitor_config

        try:
            with open(FEED_MONITOR_CAMERAS_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            logger.error(
                "[CameraService][FeedMonitor] Camera config not found: %s",
                FEED_MONITOR_CAMERAS_CONFIG_PATH,
            )
            config = {}
        except Exception:
            logger.exception("[CameraService][FeedMonitor] Failed to read camera config")
            config = {}

        CameraService._feed_monitor_config = config
        return config

    @staticmethod
    def _load_feed_monitor_camera_ids() -> List[str]:
        camera_ids = CameraService._load_feed_monitor_config().get("camera_ids", [])
        return list(dict.fromkeys(camera_ids))

    @staticmethod
    def _feed_monitor_check_interval_seconds() -> int:
        return CameraService._load_feed_monitor_config()["check_interval_seconds"]

    @staticmethod
    def _feed_monitor_freshness_window_minutes() -> int:
        return CameraService._load_feed_monitor_config()["freshness_window_minutes"]

    @staticmethod
    def _as_utc(timestamp):
        if timestamp is None:
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @staticmethod
    async def _latest_analytics_by_camera(camera_ids: List[str]) -> Dict[str, Dict]:
        projection = {"_id": 0, "camera_id": 1, "timestamp": 1}

        async def fetch_latest(camera_id: str):
            return await MongoDB.database.analytics.find_one(
                {"camera_id": camera_id},
                projection,
                sort=[("timestamp", DESCENDING)],
            )

        results = await asyncio.gather(
            *(fetch_latest(camera_id) for camera_id in camera_ids),
            return_exceptions=True,
        )

        latest = {}
        failed_cameras = []
        for camera_id, result in zip(camera_ids, results):
            if isinstance(result, Exception):
                failed_cameras.append((camera_id, result))
                continue
            if result:
                latest[camera_id] = result

        if failed_cameras:
            failed_camera_ids = ", ".join(camera_id for camera_id, _ in failed_cameras)
            raise RuntimeError(
                f"Failed to fetch latest analytics for camera(s): {failed_camera_ids}"
            ) from failed_cameras[0][1]

        return latest

    @staticmethod
    def _stale_camera_rows(
        camera_ids: List[str],
        latest_by_camera: Dict[str, Dict],
        now_utc: datetime,
    ) -> List[Dict[str, Any]]:
        cutoff = now_utc - timedelta(
            minutes=CameraService._feed_monitor_freshness_window_minutes()
        )
        stale_rows = []

        for camera_id in camera_ids:
            latest = latest_by_camera.get(camera_id)
            timestamp = CameraService._as_utc(latest.get("timestamp")) if latest else None
            if timestamp and timestamp >= cutoff:
                continue

            stale_rows.append({
                "camera_id": camera_id,
                "latest_timestamp": timestamp,
                "minutes_since_latest": (
                    round((now_utc - timestamp).total_seconds() / 60, 1)
                    if timestamp else None
                ),
            })

        return stale_rows

    @staticmethod
    def _format_inactive_duration(minutes: Optional[float]) -> Optional[str]:
        """Format minutes as '15min' under an hour, otherwise '1h 24min'."""
        if minutes is None:
            return None
        total_minutes = int(minutes)
        hours, mins = divmod(total_minutes, 60)
        return f"{hours}h {mins}min" if hours else f"{mins}min"

    @staticmethod
    def _format_stale_camera_rows(stale_rows: List[Dict[str, Any]]) -> str:
        lines = []
        for row in stale_rows:
            latest = row["latest_timestamp"]
            latest_text = latest.isoformat(timespec="seconds").replace("+00:00", "Z") if latest else "no record found"
            age_text = (
                CameraService._format_inactive_duration(row["minutes_since_latest"])
                or "unknown (no analytics record)"
            )
            lines.append(
                f"Camera Id: {row['camera_id']}<br>"
                f"Last Timestamp: {latest_text}<br>"
                f"Inactive Duration: {age_text}"
            )
        return "<br>".join(lines)

    @staticmethod
    async def check_camera_feeds_once() -> Dict[str, Any]:
        if MongoDB.database is None:
            return {"status": "skipped", "reason": "database unavailable"}

        camera_ids = CameraService._load_feed_monitor_camera_ids()
        if not camera_ids:
            return {"status": "skipped", "reason": "no monitored cameras configured"}

        now_utc = datetime.now(timezone.utc)
        latest_by_camera = await CameraService._latest_analytics_by_camera(camera_ids)
        stale_rows = CameraService._stale_camera_rows(camera_ids, latest_by_camera, now_utc)

        if not stale_rows:
            logger.info(
                "[CameraService][FeedMonitor] All %d monitored cameras are fresh",
                len(camera_ids),
            )
            return {"status": "ok", "stale_count": 0}

        if len(stale_rows) == 1:
            trigger_reason = CameraService._format_stale_camera_rows(stale_rows)
        else:
            trigger_reason = (
                f"{len(stale_rows)} camera feeds have been inactive for more than "
                f"{CameraService._feed_monitor_freshness_window_minutes()} minutes. "
                "See the attached Excel report for camera IDs, last timestamps, and inactive durations."
            )

        feed_monitor_rows = [
            {
                "camera_id": row["camera_id"],
                "last_timestamp": (
                    row["latest_timestamp"].isoformat(timespec="seconds").replace("+00:00", "Z")
                    if row["latest_timestamp"] else None
                ),
                "inactive_duration": CameraService._format_inactive_duration(
                    row["minutes_since_latest"]
                ),
            }
            for row in stale_rows
        ]
        alert_data = {
            "alert_id": f"feed_monitor_{now_utc.strftime('%Y%m%d%H%M%S')}",
            "camera_id": "camera_feed_monitor",
            "camera_name": "Camera Feed Monitor",
            "location": "Analytics ingestion",
            "severity": "CRITICAL",
            "people_count": len(stale_rows),
            "density_level": "N/A",
            "risk_level": "CRITICAL",
            "timestamp": now_utc,
            "trigger_reason": trigger_reason,
            "feed_monitor_rows": feed_monitor_rows,
            "email_subject": "Inactive Camera Feed Monitor",
            "send_email": True,
        }

        result = await NotificationService.get_instance().send_email_alert(
            alert_data,
            skip_checks=True,
        )
        logger.warning(
            "[CameraService][FeedMonitor] Stale cameras detected: %s; email_result=%s",
            [row["camera_id"] for row in stale_rows],
            result,
        )
        return {"status": "alerted", "stale_count": len(stale_rows), "email": result}

    @staticmethod
    async def camera_feed_monitor_scheduler() -> None:
        while True:
            try:
                await CameraService.check_camera_feeds_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[CameraService][FeedMonitor] Camera feed monitor check failed")

            await asyncio.sleep(CameraService._feed_monitor_check_interval_seconds())

    @staticmethod
    async def _cleanup_old_zones_and_cameras(db):
        """Remove old granular FOB zones and renamed KZJ camera entries."""
        if OLD_FOB_ZONE_IDS:
            result = await db.zones.delete_many({"zone_id": {"$in": OLD_FOB_ZONE_IDS}})
            if result.deleted_count > 0:
                print(f"[CameraService] Removed {result.deleted_count} old granular FOB zones")

        if OLD_KZJ_CAMERA_IDS:
            result = await db.cameras.delete_many({"camera_id": {"$in": OLD_KZJ_CAMERA_IDS}})
            if result.deleted_count > 0:
                print(f"[CameraService] Removed {result.deleted_count} old KZJ camera entries")

    @staticmethod
    async def _create_camera_from_def(cam_def: Dict) -> None:
        camera_id = cam_def["camera_id"]
        await CameraService.register_camera(
            camera_id=camera_id,
            name=cam_def.get("default_name", camera_id),
            rtsp_url=cam_def.get("rtsp_url", ""),
            location="Unknown",
            fob_type=cam_def.get("fob_type"),
            zone_id=cam_def["zone_id"],
            is_active=False
        )
        # Set svg_region_id on newly created camera
        await CameraService.update_camera(camera_id, {"svg_region_id": camera_id})

    @staticmethod
    async def _sync_existing_camera(cam_def: Dict, existing: Dict) -> bool:
        """Enforce correct zone_id/svg_region_id/fob_type. Returns True if updated."""
        camera_id = cam_def["camera_id"]
        zone_id = cam_def["zone_id"]

        updates = {}
        if existing.get("zone_id") != zone_id:
            updates["zone_id"] = zone_id
        if existing.get("svg_region_id") != camera_id:
            updates["svg_region_id"] = camera_id
        if cam_def.get("fob_type") and existing.get("fob_type") != cam_def["fob_type"]:
            updates["fob_type"] = cam_def["fob_type"]

        if not updates:
            return False

        await CameraService.update_camera(camera_id, updates)
        print(f"[CameraService] Updated {camera_id}: {list(updates.keys())}")
        return True

    @staticmethod
    async def seed_cameras_from_config():
        """
        No-op: Camera seeding is handled exclusively by scripts/seed_platform_zones.py.
        CameraService relies strictly on MongoDB as the single source of truth.
        """
        logger.info("[CameraService] Seeding skipped (managed by scripts/seed_platform_zones.py)")
        return


    @staticmethod
    def _serialize_camera(camera_doc: Dict) -> Dict:
        """Helper to serprintialize camera document for API response (remove ObjectId)"""
        if not camera_doc:
            return None
        camera_doc.pop("_id", None)
        return camera_doc

    @staticmethod
    async def register_camera(
        camera_id: str,
        name: str,
        rtsp_url: str,
        location: str = "Unknown",
        fob_type: Optional[str] = None,
        zone_id: Optional[str] = None,
        is_active: bool = False,
        settings: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Register a new camera in the system (or One-Time Seed)
        """
        if MongoDB.database is None:
            raise RuntimeError("MongoDB not connected")

        if settings is None:
            settings = {
                "target_fps": 1,
                "enable_analytics": True,
                "enable_alerts": True,
                "enable_heatmaps": True
            }

        camera_doc = {
            "camera_id": camera_id,
            "name": name,
            "rtsp_url": rtsp_url,
            "location": location, # Kept for backward compat
            "fob_type": fob_type, # HYD or KZJ
            "zone_id": zone_id,
            "svg_region_id": camera_id,
            "status": "active" if is_active else "inactive", # active, inactive, error
            "is_active": is_active, # Explicit control flag
            "settings": settings,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "last_seen_at": None
        }

        try:
            await MongoDB.database.cameras.insert_one(camera_doc)
            logger.info(f"[CameraService] Registered camera: {camera_id} ({name})")
            return CameraService._serialize_camera(camera_doc)
        except Exception:
            logger.exception(f"[CameraService] Failed to register camera {camera_id}")
            raise


    _camera_cache: Dict[str, tuple] = {}

    @staticmethod
    async def get_camera(camera_id: str) -> Optional[Dict]:
        """Get camera by ID (with 30s in-memory cache)"""
        now = time.time()
        if hasattr(CameraService, "_camera_cache") and camera_id in CameraService._camera_cache:
            cache_ts, cached_doc = CameraService._camera_cache[camera_id]
            if now - cache_ts < 30.0:
                return cached_doc

        if MongoDB.database is None:
            return None
        doc = await MongoDB.database.cameras.find_one({"camera_id": camera_id})
        serialized = CameraService._serialize_camera(doc)
        if not hasattr(CameraService, "_camera_cache"):
            CameraService._camera_cache = {}
        CameraService._camera_cache[camera_id] = (now, serialized)
        return serialized


    @staticmethod
    async def get_or_create_camera(
        camera_id: str,
        name: str,
        rtsp_url: str,
        location: str
    ) -> Dict[str, Any]:
        """Get existing camera or create new one"""
        camera = await CameraService.get_camera(camera_id)
        if camera:
            return camera
        return await CameraService.register_camera(camera_id, name, rtsp_url, location)


    @staticmethod
    async def list_cameras(
        status: Optional[str] = None,
        location: Optional[str] = None,
        fob_type: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict]:
        """List cameras with optional filters"""
        if MongoDB.database is None:
            return []

        query = {}
        if status:
            query["status"] = status  # Note: this filters by runtime status
        if location:
            query["location"] = location
        if fob_type:
            query["fob_type"] = fob_type

        cursor = MongoDB.database.cameras.find(query)
        cameras = await cursor.to_list(length=limit)
        return [CameraService._serialize_camera(c) for c in cameras]


    @staticmethod
    async def update_camera(
        camera_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update camera fields"""
        if MongoDB.database is None:
            return False

        updates["updated_at"] = datetime.now(UTC)

        result = await MongoDB.database.cameras.update_one(
            {"camera_id": camera_id},
            {"$set": updates}
        )
        return result.modified_count > 0


    @staticmethod
    async def update_camera_status(camera_id: str, status: str) -> bool:
        """Update camera status"""
        # Also update is_active flag to match
        is_active = (status == "active")
        return await CameraService.update_camera(camera_id, {
            "status": status,
            "is_active": is_active
        })


    @staticmethod
    async def update_last_seen(camera_id: str) -> bool:
        """Update last_seen_at timestamp"""
        if MongoDB.database is None:
            return False
        return (await MongoDB.database.cameras.update_one(
            {"camera_id": camera_id},
            {"$set": {"last_seen_at": datetime.now(UTC)}}
        )).modified_count > 0


    @staticmethod
    async def delete_camera(camera_id: str) -> bool:
        """Delete camera"""
        if MongoDB.database is None:
            return False
        return (await MongoDB.database.cameras.delete_one({"camera_id": camera_id})).deleted_count > 0


    @staticmethod
    async def count_cameras() -> int:
        if MongoDB.database is None: return 0
        return await MongoDB.database.cameras.count_documents({})


    @staticmethod
    async def get_active_cameras() -> List[Dict]:
        """Get all cameras marked as active"""
        # We rely on the is_active flag or status='active'
        return await CameraService.list_cameras(status="active")

    # ============================================================
    # CALIBRATION (ROI + area_m2) MANAGEMENT
    # ============================================================

    @staticmethod
    async def set_camera_calibration(
        camera_id: str,
        area_m2: float,
        roi_points: list = None,
        frame_width: int = None,
        frame_height: int = None
    ) -> bool:
        """
        Set spatial calibration for a camera (ROI polygon + real-world area).

        Args:
            camera_id: Camera identifier
            area_m2: Real-world area in m² (provided by station staff)
            roi_points: Optional ROI polygon as [[x_px, y_px], ...] in pixel coords
            frame_width: Frame width when ROI was drawn (required if roi_points set)
            frame_height: Frame height when ROI was drawn (required if roi_points set)
        """
        calibration = {
            "area_m2": area_m2,
            "roi": None,
            "updated_at": datetime.now(UTC)
        }

        if roi_points and frame_width and frame_height:
            calibration["roi"] = {
                "points": roi_points,
                "frame_width": frame_width,
                "frame_height": frame_height
            }

        return await CameraService.update_camera(camera_id, {"calibration": calibration})

    @staticmethod
    async def get_camera_calibration(camera_id: str) -> Optional[Dict]:
        """Get calibration (ROI + area_m2) for a camera. Returns None if not set."""
        camera = await CameraService.get_camera(camera_id)
        if camera:
            return camera.get("calibration")
        return None

    @staticmethod
    async def delete_camera_calibration(camera_id: str) -> bool:
        """Remove calibration from a camera (reverts to full-frame fallback)."""
        return await CameraService.update_camera(camera_id, {"calibration": None})

    @staticmethod
    async def migrate_calibrations_from_json():
        """
        One-time migration: copy visible_area_m2 from camera_calibrations.json
        into camera documents that don't have calibration yet.

        Seeds area_m2 from JSON, leaves ROI as None (must be drawn separately).
        """
        if MongoDB.database is None:
            return

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "camera_calibrations.json"
        )
        if not os.path.exists(config_path):
            logger.info("[CameraService] camera_calibrations.json not found, skipping migration")
            return

        try:
            async with aiofiles.open(config_path, 'r') as f:
                data = json.loads(await f.read())
        except Exception:
            logger.exception("[CameraService] Failed to read camera_calibrations.json")
            return

        migrated = 0
        for camera_id, config in data.items():
            if camera_id.startswith('_'):
                continue  # Skip examples/templates

            # Only migrate if camera exists in DB and has no calibration yet
            existing = await CameraService.get_camera(camera_id)
            if existing and not existing.get("calibration"):
                area_m2 = config.get("visible_area_m2", 150.0)
                await CameraService.update_camera(camera_id, {
                    "calibration": {
                        "area_m2": area_m2,
                        "roi": None,
                        "updated_at": datetime.now(UTC)
                    }
                })
                migrated += 1

        if migrated > 0:
            logger.info(f"[CameraService] Migrated calibrations from JSON for {migrated} cameras")
