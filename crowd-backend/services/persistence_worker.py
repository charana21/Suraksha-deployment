"""
Asynchronous persistence worker for MongoDB writes
Ensures live analytics are NEVER blocked by storage operations
"""
import os
import json
import re
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from jose.jwt import UTC
from db.mongodb import MongoDB
from services.notification_service import NotificationService
from services.firebase_service import FirebaseService
import logging
logger = logging.getLogger(__name__)

# Import TTS utility from train_announcement
try:
    from train_announcement import _generate_audio_and_upload_multilang, _transliterate_station
except ImportError:
    import sys
    sys.path.append(os.getcwd())
    try:
        from train_announcement import _generate_audio_and_upload_multilang, _transliterate_station
    except ImportError:
        _generate_audio_and_upload_multilang = None
        _transliterate_station = None

logger = logging.getLogger(__name__)

# FOB name literals (config key variants and their localized display names).
HYB_FOB_KEY = "HYB FOB"
HYB_FOB_KEY_ALT = "HYB Fob"
KZJ_FOB_KEY = "KZJ FOB"
KZJ_FOB_KEY_ALT = "KZT Fob"
MIDDLE_FOB_KEY = "Middle FOB"
MIDDLE_FOB_KEY_ALT = "Middle Fob"

HYB_FOB_NAME_EN = "Hyderabad Side Foot Over Bridge"
KZJ_FOB_NAME_EN = "Kazipeta Side Foot Over Bridge"
MIDDLE_FOB_NAME_EN = "Middle Foot Over Bridge"

FOOT_OVER_BRIDGE = "Foot Over Bridge"
ALL_FOBS_ZONE_NAME = "All FOBs"


def _localize_fob_name(name: str, lang_key: str) -> str:
    """Helper to localize FOB names with specific overrides for HYB/KZT/Middle."""
    fob_map = {
        HYB_FOB_KEY: {
            "eng": HYB_FOB_NAME_EN,
            "hin": "हैदराबाद साइड फुट ओवर ब्रिज",
            "tel": "హైదరాబాద్ సైడ్ ఫుట్ ఓవర్ బ్రిడ్జి"
        },
        HYB_FOB_KEY_ALT: {
            "eng": HYB_FOB_NAME_EN,
            "hin": "हैदराबाद साइड फुट ओवर ब्रिज",
            "tel": "హైదరాబాద్ సైడ్ ఫుట్ ఓవర్ బ్రిడ్జి"
        },
        KZJ_FOB_KEY: {
            "eng": KZJ_FOB_NAME_EN,
            "hin": "काजीपेटा साइड फुट ओवर ब्रिज",
            "tel": "కాజీపేట సైడ్ ఫుట్ ఓవర్ బ్రిడ్జి"
        },
        KZJ_FOB_KEY_ALT: {
            "eng": KZJ_FOB_NAME_EN,
            "hin": "काजीपेटा साइड फुट ओवर ब्रिज",
            "tel": "కాజీపేట సైడ్ ఫుట్ ఓవర్ బ్రిడ్జి"
        },
        MIDDLE_FOB_KEY: {
            "eng": MIDDLE_FOB_NAME_EN,
            "hin": "मिडिल फुट ओवर ब्रिज",
            "tel": "మిడిల్ ఫుట్ ఓవర్ బ్రిడ్జి"
        },
        MIDDLE_FOB_KEY_ALT: {
            "eng": MIDDLE_FOB_NAME_EN,
            "hin": "मिडिल फुट ओवर ब्रिज",
            "tel": "మిడిల్ ఫుట్ ఓవర్ బ్రిడ్జి"
        }
    }

    if name in fob_map:
        return fob_map[name].get(lang_key, fob_map[name]["eng"])

    # Generic replacement
    res = name.replace("FOB", FOOT_OVER_BRIDGE).replace("Fob", FOOT_OVER_BRIDGE)

    # Strip station prefixes if they appear at the start
    res = re.sub(r'^(HYB|KZJ|KZT|SC)\s+', '', res, flags=re.IGNORECASE).strip()

    if lang_key == "hin":
        return res.replace(FOOT_OVER_BRIDGE, "फुट ओवर ब्रिज")
    elif lang_key == "tel":
        return res.replace(FOOT_OVER_BRIDGE, "ఫుట్ ఓవర్ బ్రిడ్జి")
    return res


def _whatsapp_fob_name(name: str) -> str:
    """Returns the WhatsApp-specific FOB display name (used only for Twilio template variables)."""
    whatsapp_map = {
        HYB_FOB_KEY: HYB_FOB_NAME_EN,
        HYB_FOB_KEY_ALT: HYB_FOB_NAME_EN,
        KZJ_FOB_KEY: KZJ_FOB_NAME_EN,
        KZJ_FOB_KEY_ALT: KZJ_FOB_NAME_EN,
        MIDDLE_FOB_KEY: MIDDLE_FOB_NAME_EN,
        MIDDLE_FOB_KEY_ALT: MIDDLE_FOB_NAME_EN,
    }
    return whatsapp_map.get(name, _localize_fob_name(name, "eng"))


class PersistenceWorker:
    """
    Non-blocking async MongoDB writer with batching

    Key Design:
    - Analytics: Non-blocking queue, drops if full (not critical)
    - Alerts: Blocking queue, never drops (critical)
    - Images: Blocking queue, never drops (critical)
    - Batch writes for analytics (performance optimization)
    """

    def __init__(self, settings):
        self.settings = settings
        self.notification_service = NotificationService.get_instance()
        self.fob_analytics_whatsapp_threshold = int(
            getattr(settings, "fob_analytics_whatsapp_threshold", 1)
        )
        self._ist_offset = timedelta(hours=5, minutes=30)

        # Queues
        self.analytics_queue = asyncio.Queue(maxsize=settings.persistence_analytics_queue_size)
        self.alerts_queue = asyncio.Queue(maxsize=settings.persistence_alerts_queue_size)
        self.images_queue = asyncio.Queue(maxsize=settings.persistence_images_queue_size)
        self.detections_queue = asyncio.Queue(maxsize=settings.persistence_detections_queue_size)

        # Batch configuration
        self.analytics_batch_size = settings.persistence_batch_size
        self.detections_batch_size = settings.persistence_detections_batch_size
        self.flush_interval = settings.persistence_flush_interval

        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Statistics
        self.stats = {
            "analytics_written": 0,
            "analytics_dropped": 0,
            "detections_written": 0,
            "detections_dropped": 0,
            "alerts_written": 0,
            "images_written": 0,
            "errors": 0
        }

        # Camera/zone/station maps (populated in _load_station_config)
        self.camera_name_map = {}
        self.zone_station_map = {}
        self.booking_office_cameras = {}

        # Cooldown tracking
        self._booking_office_last_alert_time: Dict[str, float] = {}
        self._booking_office_last_any_alert_time: float = 0.0
        self._last_fob_alert_time: Dict[str, float] = {}
        self._last_db_alert_time: Dict[str, float] = {}

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self):
        """Start background worker tasks"""
        if MongoDB.database is None:
            logger.warning("[PersistenceWorker] MongoDB not connected - persistence disabled")
            return

        await self._load_station_config()

        self._running = True

        self._tasks = [
            asyncio.create_task(self._analytics_worker(),      name="analytics_worker"),
            asyncio.create_task(self._detections_worker(),     name="detections_worker"),
            asyncio.create_task(self._alerts_worker(),         name="alerts_worker"),
            asyncio.create_task(self._images_worker(),         name="images_worker"),
            asyncio.create_task(self._zone_analytics_worker(), name="zone_analytics_worker"),
        ]

        # Historical alerts must not affect live booking-office alerting after restart.
        await self._initialize_booking_office_cooldown()

        logger.info("[PersistenceWorker] Started 5 background workers")
        logger.info(f"[PersistenceWorker] Analytics batch size: {self.analytics_batch_size}")
        logger.info(f"[PersistenceWorker] Flush interval: {self.flush_interval}s")

    async def stop(self):
        """Graceful shutdown - flush all queues"""
        logger.info("[PersistenceWorker] Stopping workers...")
        self._running = False
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info(f"[PersistenceWorker] Stopped - Stats: {self.stats}")

    # -------------------------------------------------------------------------
    # Station / camera config loading
    # -------------------------------------------------------------------------

    def _reset_station_config_state(self):
        """Reset all camera/zone/station maps prior to a (re)load."""
        self.camera_station_map = {}
        self.station_camera_lists = {}
        self.station_name_map = {}
        self.latest_camera_counts = {}

        self.camera_zone_map = {}
        self.camera_zone_type_map = {}
        self.zone_camera_lists = {}
        self.zone_type_map = {}
        self.zone_name_map = {}
        self.camera_name_map = {}
        self.zone_station_map = {}
        self.booking_office_cameras = {}

    def _load_static_station_config(self) -> Dict[str, Dict[str, str]]:
        """Load stations_config.json and populate the static (file-based) maps.

        Returns dicts of camera_name -> station_id and camera_name -> zone_id,
        used later to cross-reference DB camera documents.
        """
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "stations_config.json"
        )
        name_to_station: Dict[str, str] = {}
        name_to_zone: Dict[str, str] = {}

        with open(config_path, 'r') as f:
            config = json.load(f)

        for station_id, station_data in config.items():
            self.station_camera_lists[station_id] = set()
            self.station_name_map[station_id] = station_data.get("station_name", station_id)

            for zone_def in station_data.get("zones", []):
                zid = zone_def["zone_id"]
                self.zone_type_map[zid] = zone_def.get("zone_type", "FOB")
                self.zone_name_map[zid] = zone_def.get("zone_name", "")
                self.zone_camera_lists[zid] = set()
                self.zone_station_map[zid] = station_id

            for mapping in station_data.get("camera_mappings", []):
                self._apply_static_camera_mapping(mapping, station_id, name_to_station, name_to_zone)

        return {"name_to_station": name_to_station, "name_to_zone": name_to_zone}

    def _apply_static_camera_mapping(self, mapping, station_id, name_to_station, name_to_zone):
        cam_name = mapping.get("camera_name")
        zone_id = mapping.get("zone_id")
        if not cam_name:
            return

        name_to_station[cam_name] = station_id
        if zone_id:
            name_to_zone[cam_name] = zone_id

        if not mapping.get("camera_id"):
            return

        c_id = mapping["camera_id"]
        self.camera_name_map[c_id] = cam_name or c_id
        self.camera_station_map[c_id] = station_id
        self.station_camera_lists[station_id].add(c_id)
        if zone_id:
            self.camera_zone_map[c_id] = zone_id
            self.camera_zone_type_map[c_id] = self.zone_type_map.get(zone_id, "FOB")
            self.zone_camera_lists.setdefault(zone_id, set()).add(c_id)

    async def _load_db_zone_fallback_map(self) -> Dict[str, Dict[str, Any]]:
        """Build zone_id -> {station_id, zone_type, zone_name} from the DB, refreshing zone maps."""
        db_zone_map: Dict[str, Dict[str, Any]] = {}
        try:
            zone_cursor = MongoDB.database.zones.find(
                {},
                {"zone_id": 1, "station_id": 1, "zone_type": 1, "zone_name": 1}
            )
            async for zdoc in zone_cursor:
                zid = zdoc.get("zone_id")
                if not zid:
                    continue
                db_zone_map[zid] = {
                    "station_id": zdoc.get("station_id"),
                    "zone_type": zdoc.get("zone_type"),
                    "zone_name": zdoc.get("zone_name"),
                }
                # Keep zone metadata fresh from DB as source of truth.
                if zdoc.get("zone_type"):
                    self.zone_type_map[zid] = zdoc.get("zone_type")
                if zdoc.get("zone_name"):
                    self.zone_name_map[zid] = zdoc.get("zone_name")
                if zdoc.get("station_id"):
                    self.zone_station_map[zid] = zdoc.get("station_id")
        except Exception:
            logger.exception("[PersistenceWorker] Zone DB fallback map load failed")
        return db_zone_map

    def _apply_db_camera_by_name(self, cam_doc, name_to_station, name_to_zone) -> bool:
        """Map a DB camera doc via its name against the static config. Returns True if mapped."""
        c_id = cam_doc.get("camera_id")
        c_name = cam_doc.get("name")

        if not c_name or c_name not in name_to_station:
            return False

        st_id = name_to_station[c_name]
        self.camera_station_map[c_id] = st_id
        if c_id:
            self.camera_name_map[c_id] = c_name
        self.station_camera_lists[st_id].add(c_id)

        zone_id = name_to_zone.get(c_name)
        if zone_id:
            self.camera_zone_map[c_id] = zone_id
            self.camera_zone_type_map[c_id] = self.zone_type_map.get(zone_id, "FOB")
            self.zone_camera_lists.setdefault(zone_id, set()).add(c_id)

        return True

    def _apply_db_camera_fallback(self, cam_doc, db_zone_map):
        """Fallback mapping by camera_id + DB zone/station fields when name lookup misses.

        Prevents silent rollup drops when config camera_name changes.
        """
        c_id = cam_doc.get("camera_id")
        c_name = cam_doc.get("name")
        if not c_id or c_id in self.camera_station_map:
            return

        fallback_station_id = cam_doc.get("station_id")
        fallback_zone_id = cam_doc.get("zone_id")
        if not fallback_station_id and fallback_zone_id in db_zone_map:
            fallback_station_id = db_zone_map[fallback_zone_id].get("station_id")

        if fallback_station_id:
            self.camera_station_map[c_id] = fallback_station_id
            self.station_camera_lists.setdefault(fallback_station_id, set()).add(c_id)
            if c_name:
                self.camera_name_map[c_id] = c_name

        if fallback_zone_id:
            self.camera_zone_map[c_id] = fallback_zone_id
            ztype = self.zone_type_map.get(fallback_zone_id) or db_zone_map.get(fallback_zone_id, {}).get("zone_type")
            self.camera_zone_type_map[c_id] = ztype or "FOB"
            self.zone_camera_lists.setdefault(fallback_zone_id, set()).add(c_id)

    async def _load_db_camera_mappings(self, name_to_station, name_to_zone, db_zone_map) -> int:
        """Load camera mappings directly from MongoDB as the primary source of truth.

        MongoDB camera documents always take precedence over static file configurations.
        """
        mapped_count = 0
        cursor = MongoDB.database.cameras.find({})
        async for cam_doc in cursor:
            c_id = cam_doc.get("camera_id")
            if not c_id:
                continue

            c_name = cam_doc.get("name") or c_id
            zone_id = cam_doc.get("zone_id") or name_to_zone.get(c_name)

            # Determine station_id from camera doc, or fallback to zone DB map, or static config
            station_id = (
                cam_doc.get("station_id")
                or (db_zone_map.get(zone_id, {}).get("station_id") if zone_id else None)
                or name_to_station.get(c_name)
                or "HYB"
            )

            # Determine zone_type from DB zone map or static zone_type map
            zone_type = (
                (db_zone_map.get(zone_id, {}).get("zone_type") if zone_id else None)
                or (self.zone_type_map.get(zone_id) if zone_id else None)
                or "FOB"
            )

            # ALWAYS USE MONGODB VALUES AS SOURCE OF TRUTH
            self.camera_station_map[c_id] = station_id
            self.camera_name_map[c_id] = c_name
            self.station_camera_lists.setdefault(station_id, set()).add(c_id)

            if zone_id:
                self.camera_zone_map[c_id] = zone_id
                self.camera_zone_type_map[c_id] = zone_type
                self.zone_camera_lists.setdefault(zone_id, set()).add(c_id)

            mapped_count += 1

        return mapped_count

    def _log_station_config_summary(self, mapped_count: int) -> None:
        logger.info(f"[PersistenceWorker] Mapped {mapped_count} camera IDs to stations via DB lookup")
        for st_id, cams in self.station_camera_lists.items():
            logger.info(f"[PersistenceWorker] Station {st_id} expects {len(cams)} cameras: {cams}")
        for zid, cams in self.zone_camera_lists.items():
            ztype = self.zone_type_map.get(zid, "?")
            logger.info(f"[PersistenceWorker] Zone {zid} ({ztype}) has {len(cams)} cameras: {cams}")

    def _build_booking_office_cameras(self) -> None:
        """Populate booking_office_cameras with the specific whatsapp-enabled cameras."""
        booking_whatsapp_camera_ids = {"cam_hyb_booking", "cam_hyb_booking_gate4a"}
        for camera_id, zone_id in self.camera_zone_map.items():
            if self.camera_zone_type_map.get(camera_id) != "BOOKING":
                continue
            if camera_id not in booking_whatsapp_camera_ids:
                continue
            zone_name = self.zone_name_map.get(zone_id, "")
            self.booking_office_cameras[camera_id] = {
                "camera_name": self.camera_name_map.get(camera_id, camera_id),
                "zone_id": zone_id,
                "zone_name": zone_name,
                "location_label": self._format_booking_location_label(zone_name),
                "station_id": self.zone_station_map.get(zone_id, self.camera_station_map.get(camera_id, "")),
            }

    async def _load_station_config(self):
        """Load station config and build camera -> station/zone maps"""
        self._reset_station_config_state()

        try:
            name_maps = self._load_static_station_config()
            name_to_station = name_maps["name_to_station"]
            name_to_zone = name_maps["name_to_zone"]

            mapped_count = 0
            if MongoDB.database is not None:
                db_zone_map = await self._load_db_zone_fallback_map()
                mapped_count = await self._load_db_camera_mappings(name_to_station, name_to_zone, db_zone_map)

            self._log_station_config_summary(mapped_count)

            for name, st_id in name_to_station.items():
                if name not in self.camera_station_map:
                    self.camera_station_map[name] = st_id

            self._build_booking_office_cameras()

        except Exception:
            logger.exception("[PersistenceWorker] Failed to load station config")

    # -------------------------------------------------------------------------
    # IST / timestamp helpers
    # -------------------------------------------------------------------------

    def _now_ist(self) -> datetime:
        return (datetime.now(UTC) + self._ist_offset).replace(tzinfo=None)

    def _to_ist(self, timestamp: Any) -> Optional[datetime]:
        if not isinstance(timestamp, datetime):
            return None
        if timestamp.tzinfo is None:
            return timestamp + self._ist_offset
        return timestamp.astimezone(timezone(self._ist_offset)).replace(tzinfo=None)

    def _is_live_current_ist_timestamp(
        self,
        timestamp: Any,
        *,
        reference_ist: Optional[datetime] = None,
        max_age_seconds: float = 180.0,
    ) -> bool:
        timestamp_ist = self._to_ist(timestamp)
        if timestamp_ist is None:
            return False
        now_ist = reference_ist or self._now_ist()
        age_seconds = (now_ist - timestamp_ist).total_seconds()
        if age_seconds < -300.0 or age_seconds > max_age_seconds:
            return False
        return timestamp_ist.date() == now_ist.date()

    def _format_booking_location_label(self, zone_name: str) -> str:
        # Bound the input length before regex matching so worst-case regex
        # work has a hard ceiling regardless of pattern (defense in depth
        # against ReDoS / Sonar python:S5852).
        label = (zone_name or "").strip()[:128]
        # Quantifiers are bounded (no unbounded \s+ runs) so matching stays linear.
        label = re.sub(r"\s{1,10}Booking\s{1,10}(Area|Office)\s{0,10}$", "", label, flags=re.IGNORECASE).strip()
        return label or "Booking Office"

    # -------------------------------------------------------------------------
    # Queue methods
    # -------------------------------------------------------------------------

    async def queue_analytics(self, data: Dict[str, Any]):
        """Queue analytics data for MongoDB write (non-blocking). Drops if queue full."""
        cam_id = data.get("camera_id")
        count = data.get("people_count", 0)

        if cam_id:
            self.latest_camera_counts[cam_id] = {
                "count": count,
                "updated_at": datetime.now(UTC),
                "analytics_timestamp": data.get("timestamp"),
            }

        try:
            self.analytics_queue.put_nowait(data)
        except asyncio.QueueFull:
            self.stats["analytics_dropped"] += 1
            if self.stats["analytics_dropped"] % 100 == 0:
                logger.warning(f"[PersistenceWorker] Analytics queue full - dropped {self.stats['analytics_dropped']} total")

    async def queue_detections(self, data: Dict[str, Any]):
        """DISABLED: Raw detections storage removed. No-op for backward compatibility."""
        pass

    async def queue_alert(self, data: Dict[str, Any]):
        """Queue alert data for MongoDB write (blocking, never drops)."""
        await self.alerts_queue.put(data)

    async def queue_image_metadata(self, data: Dict[str, Any]):
        """Queue image metadata for MongoDB write (blocking, never drops)."""
        await self.images_queue.put(data)

    # -------------------------------------------------------------------------
    # Booking Office alerting (Doc 1 - live snapshot based)
    # -------------------------------------------------------------------------

    async def _initialize_booking_office_cooldown(self):
        """Reset booking-office cooldown on startup so old alerts don't suppress new ones."""
        self._booking_office_last_any_alert_time = 0.0

    def _get_booking_office_cooldown_seconds(self) -> float:
        cooldown = float(getattr(self.settings, "booking_office_alert_cooldown_seconds", 0.0) or 0.0)
        if cooldown > 0:
            return cooldown
        return 600.0  # 45 mins defaults

    async def _get_best_analytics_snapshot(
        self,
        camera_id: str,
        max_age_seconds: float = 180.0,
        reference_ist: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest live in-memory snapshot for the current IST date."""
        cache_data = self.latest_camera_counts.get(camera_id)
        if not cache_data:
            return None

        if isinstance(cache_data, int):
            effective_timestamp = datetime.now(UTC)
            count = int(cache_data)
            source = "memory-legacy"
        else:
            effective_timestamp = cache_data.get("analytics_timestamp") or cache_data.get("updated_at")
            try:
                count = int(cache_data.get("count", 0) or 0)
            except (TypeError, ValueError):
                count = 0
            source = "memory"

        if not self._is_live_current_ist_timestamp(
            effective_timestamp,
            reference_ist=reference_ist,
            max_age_seconds=max_age_seconds,
        ):
            return None

        return {
            "count": count,
            "timestamp": effective_timestamp,
            "source": source,
            "timestamp_ist": self._to_ist(effective_timestamp),
        }

    def _determine_booking_diversion(
        self, gate4a_count, main_count, primary_threshold, alternate_clear_threshold, gate4a_id, main_id
    ) -> Optional[tuple]:
        """Decide which booking-office camera (if any) should trigger a diversion alert."""
        if gate4a_count >= alternate_clear_threshold and main_count >= alternate_clear_threshold:
            logger.info(
                "[PersistenceWorker][BookingOffice] Both booking offices crowded; no diversion alert. "
                f"(both >= {alternate_clear_threshold})"
            )
            return None

        if gate4a_count >= primary_threshold and main_count < alternate_clear_threshold:
            return gate4a_id, main_id
        if main_count >= primary_threshold and gate4a_count < alternate_clear_threshold:
            return main_id, gate4a_id

        logger.info("[PersistenceWorker][BookingOffice] No valid diversion condition met.")
        return None

    async def _recheck_booking_diversion(
        self, booking_camera_ids, reference_ist, source_camera_id, alternate_camera_id,
        primary_threshold, alternate_clear_threshold,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Re-fetch live snapshots and confirm the diversion condition still holds."""
        recheck = await self._get_latest_live_booking_snapshots_from_db(
            booking_camera_ids, reference_ist=reference_ist
        )
        if source_camera_id not in recheck or alternate_camera_id not in recheck:
            logger.info("[PersistenceWorker][BookingOffice] Recheck failed due to missing live snapshots; skip alert.")
            return None

        source_recheck_count = recheck[source_camera_id]["count"]
        alternate_recheck_count = recheck[alternate_camera_id]["count"]

        if alternate_recheck_count >= alternate_clear_threshold:
            logger.info(
                "[PersistenceWorker][BookingOffice] Recheck cancelled alert: alternate now crowded "
                f"({alternate_camera_id}={alternate_recheck_count} >= {alternate_clear_threshold})"
            )
            return None
        if source_recheck_count < primary_threshold:
            logger.info(
                "[PersistenceWorker][BookingOffice] Recheck cancelled alert: source no longer crowded "
                f"({source_camera_id}={source_recheck_count} < {primary_threshold})"
            )
            return None

        return recheck

    async def _monitor_booking_office_whatsapp_alerts(self) -> None:
        """
        Continuously monitor booking office cameras for overcrowding.

        Logic:
        - If BOTH cameras > threshold: No alert (both crowded).
        - If ONE camera > threshold AND alternate < alternate_clear_threshold: Send alert.
        - Cooldown: 45 minutes (global) after any alert.
        - Uses analytics timestamp for all time calculations.
        """
        primary_threshold = int(getattr(self.settings, "booking_office_alert_threshold", 190))
        alternate_clear_threshold = int(getattr(self.settings, "booking_office_alternate_clear_threshold", 120))
        cooldown = self._get_booking_office_cooldown_seconds()
        reference_ist = self._now_ist()

        # Requirement: monitor only these two booking office cameras.
        booking_camera_ids = ["cam_hyb_booking_gate4a", "cam_hyb_booking"]
        snapshots = await self._get_latest_live_booking_snapshots_from_db(
            booking_camera_ids, reference_ist=reference_ist
        )
        if not snapshots:
            logger.info("[PersistenceWorker][BookingOffice] No live booking snapshots found in analytics collection.")
            return

        if any(cam_id not in snapshots for cam_id in booking_camera_ids):
            logger.info(f"[PersistenceWorker][BookingOffice] Missing live snapshot for one/both cameras: have={list(snapshots.keys())}")
            return

        # Determine current time from latest available booking analytics
        latest_analytics_ts = max(snap["timestamp"].timestamp() for snap in snapshots.values())

        # Check global cooldown
        time_since_last = latest_analytics_ts - self._booking_office_last_any_alert_time
        if time_since_last < cooldown:
            if int(latest_analytics_ts) % 60 == 0:
                remaining = int(cooldown - time_since_last)
                logger.info(
                    f"[PersistenceWorker][BookingOffice] Global cooldown active: {remaining}s remaining "
                    f"(Analytics TS: {datetime.fromtimestamp(latest_analytics_ts)})"
                )
            return

        gate4a_id = "cam_hyb_booking_gate4a"
        main_id = "cam_hyb_booking"
        gate4a_count = snapshots[gate4a_id]["count"]
        main_count = snapshots[main_id]["count"]

        logger.info(
            f"[PersistenceWorker][BookingOffice] Live counts: {gate4a_id}={gate4a_count}, {main_id}={main_count} "
            f"(threshold={primary_threshold}, alternate_clear<{alternate_clear_threshold})"
        )

        diversion = self._determine_booking_diversion(
            gate4a_count, main_count, primary_threshold, alternate_clear_threshold, gate4a_id, main_id
        )
        if not diversion:
            return
        source_camera_id, alternate_camera_id = diversion

        recheck = await self._recheck_booking_diversion(
            booking_camera_ids, reference_ist, source_camera_id, alternate_camera_id,
            primary_threshold, alternate_clear_threshold,
        )
        if not recheck:
            return
        source_recheck_count = recheck[source_camera_id]["count"]
        alternate_recheck_count = recheck[alternate_camera_id]["count"]

        source_metadata = self.booking_office_cameras.get(source_camera_id, {
            "camera_name": source_camera_id,
            "location_label": source_camera_id,
        })
        alternate_metadata = self.booking_office_cameras.get(alternate_camera_id, {
            "camera_name": alternate_camera_id,
            "location_label": alternate_camera_id,
        })

        logger.info(
            f"[PersistenceWorker][BookingOffice] ALERT TRIGGERED: "
            f"{source_camera_id}({source_recheck_count}) -> {alternate_camera_id}({alternate_recheck_count})"
        )
        await self._send_booking_office_whatsapp_alert(
            source_camera_id,
            source_recheck_count,
            alternate_recheck_count,
            recheck[source_camera_id]["timestamp"],
            source_metadata,
            alternate_camera_id,
            alternate_metadata,
        )

    async def _get_latest_live_booking_snapshots_from_db(
        self,
        camera_ids: List[str],
        *,
        reference_ist: Optional[datetime] = None,
        max_age_seconds: float = 180.0,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch latest live analytics record per booking camera from MongoDB analytics collection."""
        if MongoDB.database is None:
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for cam_id in camera_ids:
            doc = await MongoDB.database.analytics.find_one(
                {"camera_id": cam_id},
                sort=[("timestamp", -1)],
                projection={"timestamp": 1, "people_count": 1, "camera_id": 1}
            )
            if not doc:
                continue
            ts = doc.get("timestamp")
            if not self._is_live_current_ist_timestamp(
                ts, reference_ist=reference_ist, max_age_seconds=max_age_seconds
            ):
                continue
            try:
                count = int(doc.get("people_count", 0) or 0)
            except (TypeError, ValueError):
                count = 0
            result[cam_id] = {
                "count": count,
                "timestamp": ts,
                "source": "analytics_collection",
                "timestamp_ist": self._to_ist(ts),
            }
        return result

    async def _send_booking_office_whatsapp_alert(
        self,
        camera_id: str,
        source_count: int,
        alternate_count: int,
        analytics_timestamp: datetime,
        metadata: Dict[str, Any],
        alternate_camera_id: str,
        alternate_metadata: Dict[str, Any],
    ) -> None:
        """Constructs and sends the booking-office diversion WhatsApp alert."""
        cooldown = self._get_booking_office_cooldown_seconds()
        current_ts = analytics_timestamp.timestamp()

        def get_gate_label(cam_id: str, default_label: str) -> str:
            if cam_id == "cam_hyb_booking":
                return "Gate 2A"
            if cam_id == "cam_hyb_booking_gate4a":
                return "Gate 4A"
            return default_label

        s_label = get_gate_label(camera_id, metadata.get("location_label", ""))
        a_label = get_gate_label(alternate_camera_id, alternate_metadata.get("location_label", ""))

        source_label = f"Booking Office - {s_label}"
        alternate_label = f"Booking Office - {a_label}"

        template_id = getattr(self.settings, "msg91_whatsapp_booking_office_template_id", "") or "bookingoffice_alert"
        variables = {"var_1": source_label, "var_2": alternate_label}

        message_text = (
            f"⚠️ Overcrowding detected near {source_label}.\n\n"
            f"Immediate crowd diversion required towards {alternate_label} to avoid congestion."
        )

        alert_payload = {
            "alert_id": f"booking_office_diversion_{camera_id}_{int(current_ts)}",
            "severity": "HIGH",
            "camera_id": camera_id,
            "camera_name": metadata["camera_name"],
            "location": f"{source_label} Booking Office",
            "people_count": source_count,
            "density_level": "HIGH",
            "trigger_reason": (
                f"Crowd at {source_label} ({source_count}) exceeds "
                f"{self.settings.booking_office_alert_threshold} "
                f"while {alternate_label} is clear "
                f"({alternate_count} < {self.settings.booking_office_alternate_clear_threshold})"
            ),
            "timestamp": analytics_timestamp,
            "send_email": False,
            "send_whatsapp": True,
            "whatsapp_content_sid": template_id,
            "whatsapp_template_variables": variables,
            "custom_whatsapp_message": message_text,
            "whatsapp_cooldown_seconds": cooldown,
            "alert_category": "booking_office_diversion",
            "alternate_camera_id": alternate_camera_id,
            "alternate_camera_name": alternate_metadata["camera_name"],
            "alternate_location": f"{alternate_label} Booking Office",
        }

        self._booking_office_last_alert_time[camera_id] = current_ts
        self._booking_office_last_any_alert_time = current_ts

        logger.info(f"[PersistenceWorker][BookingOffice] Sending WhatsApp alert for {camera_id} at {analytics_timestamp}")
        whatsapp_result = await self.notification_service.send_whatsapp_alert(alert_payload)
        logger.info(f"[PersistenceWorker][BookingOffice] WhatsApp dispatch result: {whatsapp_result}")

        # Queue for DB persistence but suppress duplicate WhatsApp send in alerts worker
        persisted_record = dict(alert_payload)
        persisted_record["send_whatsapp"] = False
        await self.queue_alert(persisted_record)

    # -------------------------------------------------------------------------
    # FOB alerting — LIVE (Doc 1: flow_service based)
    # -------------------------------------------------------------------------

    def _collect_station_fob_candidates(self, station_id, fob_zones, flow_service, reference_ist):
        """Gather congested-zone alert candidates for a single station."""
        latest = flow_service.get_latest(station_id)
        if not latest or not latest.get("congestion"):
            return []

        congestion = latest["congestion"]
        congested_zones = congestion.get("congested_zones", [])
        alternative_zones = congestion.get("alternative_zones", [])

        result = []
        for cz in congested_zones:
            zone_id = cz.get("zone_id")
            zone_data = fob_zones.get(zone_id)
            if not zone_data:
                continue

            zone_timestamp = zone_data.get("latest_timestamp")
            if not self._is_live_current_ist_timestamp(
                zone_timestamp, reference_ist=reference_ist, max_age_seconds=180.0,
            ):
                continue

            total_people = cz.get("people_count", 0)
            result.append((zone_timestamp, total_people, zone_id, zone_data, alternative_zones))
        return result

    def _collect_fob_alert_candidates(self, fob_zones, flow_service, reference_ist):
        """Gather all live congested-zone alert candidates across stations, sorted by priority."""
        candidates = []
        if flow_service:
            stations = {data.get("station_id") for data in fob_zones.values() if data.get("station_id")}
            for station_id in stations:
                candidates.extend(
                    self._collect_station_fob_candidates(station_id, fob_zones, flow_service, reference_ist)
                )

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates

    async def _queue_live_fob_whatsapp_alerts(
        self,
        fob_zones: Dict[str, Dict[str, Any]],
        *,
        reference_utc: datetime,
        reference_ist: Optional[datetime] = None,
    ) -> None:
        """
        Live FOB congestion alerts driven by flow_analysis_service congestion data.
        Sends WhatsApp alert + injects into congestion_alerts collection.
        """
        from services.flow_analysis_service import get_flow_service
        flow_service = get_flow_service()

        reference_ist = reference_ist or self._now_ist()
        cooldown = float(getattr(self.settings, "whatsapp_alert_cooldown_seconds", 3600.0) or 3600.0)

        candidates = self._collect_fob_alert_candidates(fob_zones, flow_service, reference_ist)
        if not candidates:
            return

        for zone_timestamp, total_people, zone_id, zone_data, alternative_zones in candidates:
            last_alert = self._last_fob_alert_time.get(zone_id, 0.0)
            current_time = zone_timestamp.timestamp()
            if (current_time - last_alert) < cooldown:
                continue

            station_id = zone_data.get("station_id", "")
            raw_zone_name = self.zone_name_map.get(zone_id, zone_id)
            zone_name = _localize_fob_name(raw_zone_name, "eng")
            station_name = self.station_name_map.get(station_id, station_id).replace("FOB", FOOT_OVER_BRIDGE)

            alternative_zone_raw_names = [
                alt.get("zone_name", alt.get("zone_id")) for alt in alternative_zones
            ]

            messages_i18n, audio_urls_i18n, audio_errors_i18n, alt1_eng, alt2_eng = self._build_i18n_messages(
                raw_zone_name, station_name, alternative_zone_raw_names
            )

            alert_payload = {
                "alert_id": f"fob_congestion_{station_id}_{zone_id}_{int(zone_timestamp.timestamp())}",
                "severity": "HIGH",
                "camera_id": f"fob_{zone_id}",
                "camera_name": zone_name,
                "location": f"Secunderabad Railway Station - {zone_name}",
                "people_count": total_people,
                "density_level": "HIGH",
                "trigger_reason": (
                    f"{zone_name} total_people_count crossed threshold: "
                    f"{total_people} > {self.fob_analytics_whatsapp_threshold}"
                ),
                "timestamp": zone_timestamp,
                "custom_whatsapp_message": messages_i18n.get("eng", ""),
                "whatsapp_content_sid": "HXca4c5d5ad4e892ab818cebfd45c30f0c",
                "whatsapp_template_variables": {
                    "1": str(station_name),
                    "2": str(_whatsapp_fob_name(raw_zone_name)),
                    "3": str(alt1_eng),
                    "4": str(alt2_eng),
                },
                "alert_category": "fob_congestion",
            }

            logger.info(f"[PersistenceWorker] Queueing LIVE FOB alert for {zone_id} ({total_people} people)")
            await self.queue_alert(alert_payload)
            self._last_fob_alert_time[zone_id] = current_time

            await self._upsert_congestion_alert(
                zone_id,
                station_id,
                total_people,
                zone_timestamp,
                messages_i18n,
                audio_urls_i18n,
                audio_errors_i18n,
                reference_utc,
            )

            break  # One alert per cycle

    # -------------------------------------------------------------------------
    # FOB alerting — DB-BACKED (Doc 2: fob_analytics query based)
    # -------------------------------------------------------------------------

    async def _queue_db_fob_whatsapp_alerts(
        self,
        timestamp_now: datetime,
    ) -> None:
        """
        DB-backed FOB congestion alerts: queries fob_analytics for recent records
        crossing the threshold and sends WhatsApp alerts with per-zone cooldown.
        """
        if MongoDB.database is None:
            return

        recent_cutoff = timestamp_now - timedelta(minutes=15)
        cooldown = float(getattr(self.settings, "whatsapp_alert_cooldown_seconds", 1800.0))

        query_cond = {
            "timestamp": {"$gte": recent_cutoff},
            "total_people_count": {"$gt": self.fob_analytics_whatsapp_threshold},
            "zone_name": {"$ne": ALL_FOBS_ZONE_NAME},
        }

        cursor = MongoDB.database.fob_analytics.find(query_cond).sort([
            ("timestamp", -1),
            ("total_people_count", -1),
        ])

        processed_zones = set()
        found_count = 0

        async for record in cursor:
            found_count += 1
            zone_id = record.get("fob_id")
            if not zone_id or zone_id in processed_zones:
                continue
            processed_zones.add(zone_id)

            last_alert = self._last_fob_alert_time.get(zone_id, 0.0)
            current_time = timestamp_now.timestamp()
            if (current_time - last_alert) < cooldown:
                continue

            self._last_fob_alert_time[zone_id] = current_time

            station_id = record.get("station_id", "")
            raw_zone_name = record.get("zone_name", zone_id)
            zone_name = _localize_fob_name(raw_zone_name, "eng")
            total_people = record.get("total_people_count", 0)
            station_name = self.station_name_map.get(station_id, station_id).replace("FOB", FOOT_OVER_BRIDGE)

            # Get alternative zones from DB (low congestion, same station)
            alt_cursor = MongoDB.database.fob_analytics.find({
                "timestamp": {"$gte": recent_cutoff},
                "station_id": station_id,
                "fob_id": {"$ne": zone_id},
                "zone_name": {"$ne": ALL_FOBS_ZONE_NAME},
                "total_people_count": {"$lte": self.fob_analytics_whatsapp_threshold},
            }).sort("timestamp", -1)

            alt_processed = set()
            alternative_zone_raw_names = []
            async for alt_record in alt_cursor:
                alt_zid = alt_record.get("fob_id")
                if alt_zid and alt_zid not in alt_processed:
                    alt_processed.add(alt_zid)
                    alternative_zone_raw_names.append(alt_record.get("zone_name", ""))

            messages_i18n, audio_urls_i18n, audio_errors_i18n, alt1_eng, alt2_eng = self._build_i18n_messages(
                raw_zone_name, station_name, alternative_zone_raw_names
            )

            alert_payload = {
                "alert_id": f"fob_congestion_{station_id}_{zone_id}_{int(timestamp_now.timestamp())}",
                "severity": "HIGH",
                "camera_id": f"fob_{zone_id}",
                "camera_name": zone_name,
                "location": f"{station_name} - {zone_name}",
                "people_count": total_people,
                "density_level": "HIGH",
                "trigger_reason": (
                    f"{zone_name} total_people_count crossed threshold: "
                    f"{total_people} > {self.fob_analytics_whatsapp_threshold}"
                ),
                "timestamp": timestamp_now,
                "custom_whatsapp_message": messages_i18n.get("eng", ""),
                "whatsapp_content_sid": "HXca4c5d5ad4e892ab818cebfd45c30f0c",
                "whatsapp_template_variables": {
                    "1": str(station_name),
                    "2": str(_whatsapp_fob_name(raw_zone_name)),
                    "3": str(alt1_eng),
                    "4": str(alt2_eng),
                },
                "alert_category": "fob_congestion",
            }

            logger.info(f"[PersistenceWorker] Queueing DB-backed FOB alert for {zone_id} ({total_people} people)")
            await self.queue_alert(alert_payload)

            await self._upsert_congestion_alert(
                zone_id,
                station_id,
                total_people,
                timestamp_now,
                messages_i18n,
                audio_urls_i18n,
                audio_errors_i18n,
                timestamp_now,
            )

        if found_count > 0:
            logger.info(
                f"[PersistenceWorker] DB Alert Poll: Found {found_count} records crossing "
                f"threshold ({self.fob_analytics_whatsapp_threshold}) in the last 60 minutes."
            )

    async def _queue_db_camera_whatsapp_alerts(self, timestamp_now: datetime) -> None:
        """
        DB-backed camera alerts: queries the 'alerts' collection for recent CRITICAL
        alerts that haven't been sent via WhatsApp yet, and dispatches them.
        """
        if MongoDB.database is None:
            return

        # Look back 30 minutes to prevent sending extremely old alerts if the system was down
        recent_cutoff = timestamp_now - timedelta(minutes=30)

        query_cond = {
            "timestamp": {"$gte": recent_cutoff},
            "severity": "CRITICAL",
            "whatsapp_sent": {"$ne": True},
            "send_whatsapp": {"$ne": False},
            "alert_category": {"$ne": "fob_congestion"} # handled separately
        }

        # Find unsent critical alerts, oldest first so they are sent in order
        cursor = MongoDB.database.alerts.find(query_cond).sort("timestamp", 1)

        found_count = 0
        async for alert_data in cursor:
            found_count += 1
            
            # Send the WhatsApp alert
            logger.info(f"[PersistenceWorker] DB Alert Poll: Sending delayed WhatsApp alert for {alert_data.get('alert_id')}")
            try:
                await self.notification_service.send_whatsapp_alert(alert_data)
            except Exception:
                logger.exception("[PersistenceWorker] send_whatsapp_alert failed")

            # Mark as sent regardless of success to prevent infinite loops on failing alerts
            try:
                await MongoDB.database.alerts.update_one(
                    {"_id": alert_data["_id"]},
                    {"$set": {"whatsapp_sent": True}}
                )
                logger.info(f"[PersistenceWorker] marked whatsapp_sent=True for {alert_data.get('alert_id')}")
            except Exception:
                logger.exception("[PersistenceWorker] update_one failed")

        if found_count > 0:
            logger.info(f"[PersistenceWorker] DB Alert Poll: Dispatched {found_count} camera WhatsApp alerts from DB.")

    # -------------------------------------------------------------------------
    # Shared helpers
    # -------------------------------------------------------------------------

    def _resolve_alt_names(self, raw_zone_name: str, alternative_zone_raw_names: List[str]) -> List[str]:
        """Return unique alternative FOB raw names, with a static fallback by zone prefix."""
        unique_alt_raw = list(dict.fromkeys(n for n in alternative_zone_raw_names if n))
        if unique_alt_raw:
            return unique_alt_raw

        # Dynamic fallback if no alternatives are provided/found
        upper_zone = raw_zone_name.upper()
        if "HYB" in upper_zone:
            return [KZJ_FOB_KEY, MIDDLE_FOB_KEY]
        if "KZJ" in upper_zone or "KZT" in upper_zone:
            return [HYB_FOB_KEY, MIDDLE_FOB_KEY]
        if "MIDDLE" in upper_zone:
            return [HYB_FOB_KEY, KZJ_FOB_KEY]
        return []

    def _localize_alt_names(self, lang_key: str, unique_alt_raw: List[str]):
        """Return (alt1_local, alt2_local) for a language, falling back when only one alt exists."""
        default_alt2 = {
            "hin": "वैकल्पिक मार्ग",
            "tel": "ప్రత్యామ్నాయ మార్గాలను",
            "eng": "alternative routes",
        }[lang_key]

        alt1_local = _localize_fob_name(unique_alt_raw[0], lang_key)
        alt2_local = (
            _localize_fob_name(unique_alt_raw[1], lang_key) if len(unique_alt_raw) > 1 else default_alt2
        )
        return alt1_local, alt2_local

    def _generate_alert_audio(self, msg: str, raw_zone_name: str, lang_key: str):
        """Generate TTS audio for an alert message. Returns (audio_url, audio_error)."""
        if not _generate_audio_and_upload_multilang:
            return "", ""
        try:
            audio_url = _generate_audio_and_upload_multilang(
                msg, f"ALERT_{raw_zone_name}", f"congestion_{lang_key}", lang=lang_key[:2]
            )
            return audio_url, ""
        except Exception as tts_err:
            logger.exception(f"[PersistenceWorker] Audio generation warning ({lang_key})")
            return "", str(tts_err)

    def _build_single_language_message(
        self, lang_key: str, raw_zone_name: str, station_name: str, unique_alt_raw: List[str], templates: dict
    ):
        """Build the localized message + audio for one language. Returns (msg, audio_url, audio_error)."""
        target_lang_code = {"eng": "en-IN", "hin": "hi-IN", "tel": "te-IN"}[lang_key]

        # Mobile app: use 'side' FOB name for zone display in English, localized name otherwise
        z_name = _whatsapp_fob_name(raw_zone_name) if lang_key == "eng" else _localize_fob_name(raw_zone_name, lang_key)
        s_name = _transliterate_station(station_name, target_lang_code) if _transliterate_station else station_name

        if unique_alt_raw:
            alt1_local, alt2_local = self._localize_alt_names(lang_key, unique_alt_raw)
            msg = templates[lang_key]["main"].format(
                station_name=s_name, zone_name=z_name, alt1=alt1_local, alt2=alt2_local
            )
        else:
            msg = templates[lang_key]["fallback"].format(station_name=s_name, zone_name=z_name)

        audio_url, audio_error = self._generate_alert_audio(msg, raw_zone_name, lang_key)
        return msg, audio_url, audio_error

    def _build_i18n_messages(
        self,
        raw_zone_name: str,
        station_name: str,
        alternative_zone_raw_names: List[str],
    ):
        """
        Build multilingual (eng/hin/tel) alert messages and generate audio URLs.
        Returns (messages_i18n, audio_urls_i18n, audio_errors_i18n, alt1_eng, alt2_eng).
        """
        templates = {
            "eng": {
                # Mobile app / TTS: zone with 'side' suffix, generic alt routes
                "main": "{zone_name} is currently overcrowded. Please use other Foot Over Bridges as alternative routes to reach your platforms.",
                "fallback": "{zone_name} is currently overcrowded. Please use other Foot Over Bridges as alternative routes to reach your platforms."
            },
            "hin": {
                "main": "{zone_name} में इस समय बहुत भीड़ है।\n\nअपने प्लेटफार्मों तक पहुँचने के लिए कृपया {alt1}\nया {alt2} का उपयोग करें।",
                "fallback": "{zone_name} में इस समय बहुत भीड़ है।\n\nअपने प्लेटफार्मों तक पहुँचने के लिए कृपया अन्य फुट ओवर ब्रिज\nया वैकल्पिक मार्ग का उपयोग करें।"
            },
            "tel": {
                "main": "{zone_name} ప్రస్తుతం చాలా రద్దీగా ఉంది.\n\nమీ ప్లాట్‌ఫారమ్‌లకు చేరుకోవడానికి దయచేసి {alt1}\nలేదా {alt2} ఉపయోగించండి.",
                "fallback": "{zone_name} ప్రస్తుతం చాలా రద్దీగా ఉంది.\n\nమీ ప్లాట్‌ఫారమ్‌లకు చేరుకోవడానికి దయచేసి ఇతర ఫుట్ ఓవర్ బ్రిడ్జిలను\nలేదా ప్రత్యామ్నాయ మార్గాలను ఉపయోగించండి."
            }
        }

        messages_i18n = {}
        audio_urls_i18n = {"eng": "", "hin": "", "tel": ""}
        audio_errors_i18n = {"eng": "", "hin": "", "tel": ""}

        unique_alt_raw = self._resolve_alt_names(raw_zone_name, alternative_zone_raw_names)
        alt1_eng = _whatsapp_fob_name(unique_alt_raw[0]) if len(unique_alt_raw) > 0 else "other Foot Over Bridges"
        alt2_eng = _whatsapp_fob_name(unique_alt_raw[1]) if len(unique_alt_raw) > 1 else "alternative routes"

        for lang_key in ["eng", "hin", "tel"]:
            msg, audio_url, audio_error = self._build_single_language_message(
                lang_key, raw_zone_name, station_name, unique_alt_raw, templates
            )
            messages_i18n[lang_key] = msg
            audio_urls_i18n[lang_key] = audio_url
            audio_errors_i18n[lang_key] = audio_error

        return messages_i18n, audio_urls_i18n, audio_errors_i18n, alt1_eng, alt2_eng

    async def _upsert_congestion_alert(
        self,
        zone_id: str,
        station_id: str,
        people_count: int,
        zone_timestamp: datetime,
        messages_i18n: Dict[str, str],
        audio_urls_i18n: Dict[str, str],
        audio_errors_i18n: Dict[str, str],
        reference_utc: datetime,
    ) -> None:
        """Upsert a congestion alert document into the congestion_alerts collection."""
        if MongoDB.database is None:
            return
        try:
            existing_doc = await MongoDB.database.congestion_alerts.find_one(
                {"alert_id": f"ALERT_{zone_id}", "station_id": station_id}
            ) or {}
            existing_i18n = existing_doc.get("i18n", {}) if isinstance(existing_doc, dict) else {}

            merged_i18n = {}
            for lang_key in ("eng", "hin", "tel"):
                existing_lang = existing_i18n.get(lang_key, {}) if isinstance(existing_i18n, dict) else {}
                generated_audio_url = audio_urls_i18n.get(lang_key, "")
                stored_audio_url = existing_lang.get("audio_url", "") if isinstance(existing_lang, dict) else ""
                effective_audio_url = generated_audio_url or stored_audio_url
                audio_error = audio_errors_i18n.get(lang_key, "")

                merged_i18n[lang_key] = {
                    "text": messages_i18n.get(lang_key, ""),
                    "audio_url": effective_audio_url,
                    "audio_status": "ready" if effective_audio_url else "failed",
                    "audio_error": "" if effective_audio_url else audio_error,
                }

            congestion_doc = {
                "alert_id": f"ALERT_{zone_id}",
                "station_id": station_id,
                "zone_id": zone_id,
                "people_count": people_count,
                "timestamp": zone_timestamp,
                "i18n": merged_i18n,
                "updated_at": reference_utc,
            }
            await MongoDB.database.congestion_alerts.update_one(
                {"alert_id": f"ALERT_{zone_id}", "station_id": station_id},
                {"$set": congestion_doc},
                upsert=True,
            )
            await FirebaseService.publish_congestion(congestion_doc)
            logger.info(f"[PersistenceWorker] Upserted congestion_alerts for {zone_id}")
        except Exception:
            logger.exception("[PersistenceWorker] Failed to upsert congestion alert")

    # -------------------------------------------------------------------------
    # Zone analytics worker (orchestrates everything)
    # -------------------------------------------------------------------------

    async def _maybe_reload_station_config(self, tick: int) -> None:
        if tick % 10 == 0:
            await self._load_station_config()

    async def _run_periodic_alert_checks(self, timestamp_now: datetime) -> None:
        # --- Booking office live alerts ---
        await self._monitor_booking_office_whatsapp_alerts()
        # --- DB-backed FOB alerts ---
        await self._queue_db_fob_whatsapp_alerts(timestamp_now)
        # --- DB-backed Camera WhatsApp alerts ---
        await self._queue_db_camera_whatsapp_alerts(timestamp_now)

    def _extract_camera_snapshot(self, data, now: datetime):
        """Return (count, last_updated, analytics_timestamp) for a latest_camera_counts entry."""
        if isinstance(data, int):
            return data, now, None
        return data.get("count", 0), data.get("updated_at", now), data.get("analytics_timestamp")

    def _accumulate_station_total(self, station_totals, station_id, cam_id, count, zone_type):
        if station_id not in station_totals:
            station_totals[station_id] = {
                "total": 0, "cameras": {}, "active": 0,
                "fob": 0, "platform": 0, "booking": 0,
            }
        st = station_totals[station_id]
        st["total"] += count
        st["cameras"][cam_id] = count
        st["active"] += 1
        if zone_type:
            st[zone_type.lower()] = st.get(zone_type.lower(), 0) + count

    def _select_zone_bucket(self, zone_type, fob_zones, platform_zones):
        if zone_type == "FOB":
            return fob_zones
        if zone_type == "PLATFORM":
            return platform_zones
        return None

    def _accumulate_zone_bucket(self, bucket, zone_id, cam_id, count, station_id, analytics_timestamp, last_updated):
        if zone_id not in bucket:
            bucket[zone_id] = {
                "total": 0, "cameras": {}, "active": 0,
                "station_id": station_id, "latest_timestamp": None,
            }

        bucket[zone_id]["total"] += count
        bucket[zone_id]["cameras"][cam_id] = count
        bucket[zone_id]["active"] += 1

        effective_timestamp = analytics_timestamp if isinstance(analytics_timestamp, datetime) else last_updated
        is_newer = (
            bucket[zone_id]["latest_timestamp"] is None
            or effective_timestamp > bucket[zone_id]["latest_timestamp"]
        )
        if isinstance(effective_timestamp, datetime) and is_newer:
            bucket[zone_id]["latest_timestamp"] = effective_timestamp

    def _aggregate_zone_counts(self):
        """Aggregate latest_camera_counts into station/FOB/platform buckets, dropping stale entries."""
        now = datetime.now(UTC)
        stale_threshold = 180.0
        station_totals = {}
        fob_zones = {}
        platform_zones = {}

        for cam_id, data in list(self.latest_camera_counts.items()):
            count, last_updated, analytics_timestamp = self._extract_camera_snapshot(data, now)

            if (now - last_updated).total_seconds() > stale_threshold:
                continue

            station_id = self.camera_station_map.get(cam_id)
            if not station_id:
                continue

            zone_id = self.camera_zone_map.get(cam_id)
            zone_type = self.camera_zone_type_map.get(cam_id)

            self._accumulate_station_total(station_totals, station_id, cam_id, count, zone_type)

            if not zone_id or not zone_type:
                continue

            bucket = self._select_zone_bucket(zone_type, fob_zones, platform_zones)
            if bucket is None:
                continue

            self._accumulate_zone_bucket(bucket, zone_id, cam_id, count, station_id, analytics_timestamp, last_updated)

        return station_totals, fob_zones, platform_zones

    def _build_fob_zone_doc(self, zone_id, zdata, timestamp):
        return {
            "fob_id": zone_id,
            "station_id": zdata["station_id"],
            "zone_name": self.zone_name_map.get(zone_id, ""),
            "timestamp": timestamp,
            "total_people_count": zdata["total"],
            "cameras_active": zdata["active"],
            "camera_counts": zdata["cameras"],
            "density_status": "HIGH" if zdata["total"] > 100 else "LOW",
        }

    def _build_all_fobs_doc(self, sid, combined, timestamp):
        return {
            "fob_id": sid,
            "station_id": sid,
            "zone_name": ALL_FOBS_ZONE_NAME,
            "timestamp": timestamp,
            "total_people_count": combined["total"],
            "cameras_active": combined["active"],
            "camera_counts": combined["cameras"],
            "density_status": "HIGH" if combined["total"] > 200 else "LOW",
        }

    async def _write_fob_analytics(self, fob_zones, timestamp) -> None:
        fob_docs = []
        station_fob_combined = {}

        for zone_id, zdata in fob_zones.items():
            sid = zdata["station_id"]
            fob_docs.append(self._build_fob_zone_doc(zone_id, zdata, timestamp))

            if sid not in station_fob_combined:
                station_fob_combined[sid] = {"total": 0, "active": 0, "cameras": {}}
            combined = station_fob_combined[sid]
            combined["total"] += zdata["total"]
            combined["active"] += zdata["active"]
            combined["cameras"].update(zdata["cameras"])

        for sid, combined in station_fob_combined.items():
            fob_docs.append(self._build_all_fobs_doc(sid, combined, timestamp))

        if fob_docs:
            await MongoDB.database.fob_analytics.insert_many(fob_docs)

    async def _write_platform_analytics(self, platform_zones, timestamp) -> None:
        platform_docs = [
            {
                "zone_id": zone_id,
                "station_id": zdata["station_id"],
                "zone_name": self.zone_name_map.get(zone_id, ""),
                "timestamp": timestamp,
                "total_people_count": zdata["total"],
                "cameras_active": zdata["active"],
                "camera_counts": zdata["cameras"],
                "density_status": "HIGH" if zdata["total"] > 80 else "LOW",
            }
            for zone_id, zdata in platform_zones.items()
        ]

        if platform_docs:
            await MongoDB.database.platform_analytics.insert_many(platform_docs)

    def _warn_if_partial_station_data(self, station_id, st) -> None:
        expected_cams = self.station_camera_lists.get(station_id, set())
        if len(expected_cams) > 0 and st["active"] < len(expected_cams):
            logger.warning(
                f"[PersistenceWorker] Warning: Partial data for {station_id} "
                f"({st['active']}/{len(expected_cams)} cameras)"
            )

    def _build_station_analytics_doc(self, station_id, st, timestamp):
        return {
            "station_id": station_id,
            "timestamp": timestamp,
            "total_people_count": st["total"],
            "cameras_active": st["active"],
            "zone_type_breakdown": {
                "FOB": st.get("fob", 0),
                "PLATFORM": st.get("platform", 0),
                "BOOKING": st.get("booking", 0),
            },
            "camera_counts": st["cameras"],
            "density_status": "HIGH" if st["total"] > 300 else "LOW",
        }

    async def _write_station_analytics(self, station_totals, timestamp) -> None:
        for station_id, st in station_totals.items():
            if st["active"] == 0:
                continue
            self._warn_if_partial_station_data(station_id, st)
            await MongoDB.database.station_analytics.insert_one(
                self._build_station_analytics_doc(station_id, st, timestamp)
            )

    async def _run_zone_analytics_cycle(self, tick: int) -> None:
        await self._maybe_reload_station_config(tick)

        timestamp_now = datetime.now(UTC)
        reference_ist = self._to_ist(timestamp_now)

        await self._run_periodic_alert_checks(timestamp_now)

        if not self.latest_camera_counts:
            return

        station_totals, fob_zones, platform_zones = self._aggregate_zone_counts()

        logger.info(
            f"[PersistenceWorker] Analytics cycle: active_cameras={len(self.latest_camera_counts)}, "
            f"fob_zones={len(fob_zones)}, platform_zones={len(platform_zones)}"
        )

        # --- Live FOB alerts (flow_service) ---
        await self._queue_live_fob_whatsapp_alerts(
            fob_zones, reference_utc=timestamp_now, reference_ist=reference_ist,
        )

        if MongoDB.database is None:
            logger.warning("[PersistenceWorker] Warning: MongoDB database is None. Skipping analytics write.")
            return

        timestamp = datetime.now(UTC)
        await self._write_fob_analytics(fob_zones, timestamp)
        await self._write_platform_analytics(platform_zones, timestamp)
        await self._write_station_analytics(station_totals, timestamp)

    async def _zone_analytics_worker(self):
        """
        Periodically aggregate live camera counts by zone type and write to:
        - fob_analytics: per-FOB-zone + combined all-FOB doc
        - platform_analytics: per-platform zone
        - station_analytics: station-wide totals with zone-type breakdown

        Alerting:
        - Booking Office alerts: live BOOKING camera snapshots (Doc 1 logic)
        - FOB live alerts: flow_analysis_service congestion data (Doc 1 logic)
        - FOB DB-backed alerts: fob_analytics query (Doc 2 logic)
        All three run every cycle; individual cooldowns prevent flooding.
        """
        tick = 0
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                tick += 1
                await self._run_zone_analytics_cycle(tick)
            except Exception:
                logger.exception("[PersistenceWorker] Zone analytics worker error")

    # -------------------------------------------------------------------------
    # Background workers
    # -------------------------------------------------------------------------

    async def _collect_analytics_batch(self, buffer: list) -> None:
        """Wait for at least one item, then drain the queue up to the batch size."""
        try:
            item = await asyncio.wait_for(
                self.analytics_queue.get(), timeout=self.flush_interval
            )
            buffer.append(item)
        except asyncio.TimeoutError:
            pass

        while len(buffer) < self.analytics_batch_size:
            try:
                buffer.append(self.analytics_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

    async def _flush_analytics_buffer(self, buffer: list, final: bool = False) -> None:
        """Write the buffered analytics to MongoDB and clear it."""
        if MongoDB.database is None:
            return
        try:
            await MongoDB.database.analytics.insert_many(buffer, ordered=False)
            self.stats["analytics_written"] += len(buffer)
            if final:
                logger.info(f"[PersistenceWorker] Flushed {len(buffer)} analytics on shutdown")
            elif self.stats["analytics_written"] % 100 == 0:
                logger.info(f"[PersistenceWorker] Analytics written: {self.stats['analytics_written']}")
        except Exception:
            logger.exception(
                "[PersistenceWorker] Final analytics flush failed" if final
                else "[PersistenceWorker] Analytics write failed"
            )
            self.stats["errors"] += 1
        finally:
            buffer.clear()

    async def _analytics_worker(self):
        """Batch write analytics to MongoDB."""
        buffer = []
        while self._running:
            try:
                await self._collect_analytics_batch(buffer)
                if buffer:
                    await self._flush_analytics_buffer(buffer)
            except Exception:
                logger.exception("[PersistenceWorker] Analytics worker error")
                self.stats["errors"] += 1
                buffer.clear()

        if buffer:
            await self._flush_analytics_buffer(buffer, final=True)

    async def _detections_worker(self):
        """DISABLED: Detections collection removed. No-op worker."""
        while self._running:
            await asyncio.sleep(60)

    async def _alerts_worker(self):
        """Write alerts to MongoDB one at a time (time-sensitive)."""
        while self._running:
            try:
                alert_data = await self.alerts_queue.get()
                if MongoDB.database is not None:
                    # Initialize whatsapp_sent flag to False for tracking DB-polled sends
                    if "whatsapp_sent" not in alert_data:
                        alert_data["whatsapp_sent"] = False

                    await MongoDB.database.alerts.insert_one(alert_data)
                    self.stats["alerts_written"] += 1
                    logger.info(
                        f"[PersistenceWorker] Alert written: {alert_data['alert_id']} "
                        f"(Camera: {alert_data['camera_id']}, Severity: {alert_data['severity']})"
                    )
                    await self.notification_service.send_email_alert(alert_data)
                    # FOB congestion WhatsApp is sent exclusively by _queue_live_fob_whatsapp_alerts
                    # and _queue_db_fob_whatsapp_alerts (with the proper Twilio template).
                    # Standard camera WhatsApp alerts are handled by DB polling via
                    # `_queue_db_camera_whatsapp_alerts`, so live dispatch is bypassed here.
            except Exception:
                logger.exception("[PersistenceWorker] Alert write failed")
                self.stats["errors"] += 1
        logger.info("[PersistenceWorker] Alerts worker stopped")

    async def _images_worker(self):
        """Write image metadata to MongoDB and link back to alert."""
        while self._running:
            try:
                image_data = await self.images_queue.get()
                if MongoDB.database is not None:
                    result = await MongoDB.database.images.insert_one(image_data)
                    self.stats["images_written"] += 1
                    logger.info(
                        f"[PersistenceWorker] Image metadata written: {image_data['file_path']} "
                        f"(Alert: {image_data['alert_id']}, Risk: {image_data['risk_level']})"
                    )
                    if "alert_id" in image_data:
                        await MongoDB.database.alerts.update_one(
                            {"alert_id": image_data["alert_id"]},
                            {"$set": {"image_id": result.inserted_id}},
                        )
            except Exception:
                logger.exception("[PersistenceWorker] Image metadata write failed")
                self.stats["errors"] += 1
        logger.info("[PersistenceWorker] Images worker stopped")

    # -------------------------------------------------------------------------
    # Stats / health
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, int]:
        return self.stats.copy()

    def get_queue_sizes(self) -> Dict[str, int]:
        return {
            "analytics": self.analytics_queue.qsize(),
            "detections": self.detections_queue.qsize(),
            "alerts": self.alerts_queue.qsize(),
            "images": self.images_queue.qsize(),
        }

    def is_healthy(self) -> bool:
        if not self._running:
            return False
        for task in self._tasks:
            if task.done():
                return False
        return True
