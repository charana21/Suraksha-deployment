"""
MongoDB connection and index management
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from typing import Optional
import logging
logger = logging.getLogger(__name__)
 
class DualWriteCollection:
    def __init__(self, prod_coll, test_coll):
        self.prod_coll = prod_coll
        self.test_coll = test_coll
 
    def __getattr__(self, name):
        write_methods = {
            'insert_one', 'insert_many',
            'update_one', 'update_many',
            'delete_one', 'delete_many',
            'replace_one', 'bulk_write',
            'find_one_and_update', 'find_one_and_replace', 'find_one_and_delete',
            'drop'
        }
       
        prod_attr = getattr(self.prod_coll, name)
       
        if name in write_methods and callable(prod_attr):
            async def dual_write_wrapper(*args, **kwargs):
                # Test DB writes are disabled for now - only writing to prod.
                # To re-enable dual write, uncomment the block below and
                # remove this early return.
                return await prod_attr(*args, **kwargs)

                # if self.test_coll is None:
                #     return await prod_attr(*args, **kwargs)
                #
                # test_attr = getattr(self.test_coll, name)
                #
                # async def run_prod():
                #     try:
                #         return await prod_attr(*args, **kwargs)
                #     except Exception as e:
                #         print(f"[MongoDB DualWrite] Prod Error on {self.prod_coll.name}.{name}: {e}")
                #         raise e
                #
                # async def run_test():
                #     try:
                #         test_args = args
                #         test_kwargs = kwargs
                #         if name in ('insert_one', 'insert_many', 'bulk_write', 'replace_one'):
                #             test_args = copy.deepcopy(args)
                #             test_kwargs = copy.deepcopy(kwargs)
                #         await test_attr(*test_args, **test_kwargs)
                #     except Exception as e:
                #         print(f"[MongoDB DualWrite] Test Error on {self.test_coll.name}.{name}: {e}")
                #
                # prod_task = asyncio.create_task(run_prod())
                # test_task = asyncio.create_task(run_test())
                #
                # results = await asyncio.gather(prod_task, test_task, return_exceptions=True)
                #
                # if isinstance(results[0], Exception):
                #     raise results[0]
                # return results[0]

            return dual_write_wrapper
        else:
            return prod_attr
 
class DualWriteDatabase:
    def __init__(self, prod_db, test_db):
        self.prod_db = prod_db
        self.test_db = test_db
 
    def __getattr__(self, name):
        prod_coll = getattr(self.prod_db, name)
        test_coll = getattr(self.test_db, name) if self.test_db is not None else None
        return DualWriteCollection(prod_coll, test_coll)
       
    def __getitem__(self, name):
        prod_coll = self.prod_db[name]
        test_coll = self.test_db[name] if self.test_db is not None else None
        return DualWriteCollection(prod_coll, test_coll)
 
class MongoDB:
    """MongoDB connection singleton"""
    client: Optional[AsyncIOMotorClient] = None
    prod_database = None  # Raw prod DB (reads + index management)
    database = None  # Dual-write facade when test DB is configured, else prod
    test_client: Optional[AsyncIOMotorClient] = None
    test_database = None
 
 
def _enable_dual_write():
    """Route all collection writes to prod + test; reads stay on prod only."""
    if MongoDB.prod_database is not None and MongoDB.test_database is not None:
        MongoDB.database = DualWriteDatabase(MongoDB.prod_database, MongoDB.test_database)
 
 
async def connect_to_mongo(settings):
    """Connect to MongoDB on startup"""
    try:
        MongoDB.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=settings.mongodb_max_pool_size,
            connectTimeoutMS=settings.mongodb_connect_timeout_ms,
            serverSelectionTimeoutMS=30000
        )
 
        MongoDB.prod_database = MongoDB.client[settings.mongodb_database]
        MongoDB.database = MongoDB.prod_database
 
        # Test connection
        await MongoDB.client.admin.command('ping')
       
        if getattr(settings, 'mongodb_test_uri', None) and getattr(settings, 'mongodb_test_database', None):
            try:
                MongoDB.test_client = AsyncIOMotorClient(
                    settings.mongodb_test_uri,
                    maxPoolSize=settings.mongodb_max_pool_size,
                    connectTimeoutMS=settings.mongodb_connect_timeout_ms,
                    serverSelectionTimeoutMS=3000
                )
                MongoDB.test_database = MongoDB.test_client[settings.mongodb_test_database]
                await MongoDB.test_client.admin.command('ping')
                _enable_dual_write()
                print(f"[MongoDB] Connected to test database: {settings.mongodb_test_database}")
                print("[MongoDB] Dual-write enabled (writes -> prod + test, reads -> prod only)")
            except Exception as e:
                print(f"[MongoDB] Test connection failed: {e}")
                MongoDB.test_client = None
                MongoDB.test_database = None
 
        # Index management is explicit/manual by default to avoid
        # index mutations on every backend restart.
        if settings.mongodb_auto_manage_indexes:
            await create_indexes()
            logger.info("[MongoDB] Indexes synchronized on startup")
        else:
            logger.info("[MongoDB] Startup index sync skipped (mongodb_auto_manage_indexes=false)")

        logger.info(f"[MongoDB] Connected to database: {settings.mongodb_database}")

    except Exception as e:
        print(f"[MongoDB] Connection failed: {e}")
        logger.error(f"[MongoDB] Connection failed: {e}")
        logger.info("[MongoDB] System will fall back to file-based storage")
        MongoDB.client = None
        MongoDB.prod_database = None
        MongoDB.database = None
        MongoDB.test_client = None
        MongoDB.test_database = None
 
 
async def close_mongo_connection():
    """Close MongoDB connection on shutdown"""
    if MongoDB.client:
        MongoDB.client.close()
        print("[MongoDB] Connection closed")
    if getattr(MongoDB, 'test_client', None):
        MongoDB.test_client.close()
        print("[MongoDB] Test Connection closed")
 
async def create_indexes():
    """Create all required indexes for optimal query performance"""
    if MongoDB.prod_database is None:
        return
 
    db = MongoDB.prod_database
 
    try:
        # ===== CAMERAS COLLECTION =====
        # Primary key: camera_id (unique)
        await db.cameras.create_index("camera_id", unique=True, name="idx_camera_id")
 
        # Filter by status
        await db.cameras.create_index("status", name="idx_status")
 
        # Filter by location
        await db.cameras.create_index("location", name="idx_location")
 
        # Filter by zone_id (for zone analytics aggregation)
        await db.cameras.create_index("zone_id", name="idx_zone_id")
 
        print("[MongoDB] Created indexes for 'cameras' collection")
 
 
        # ===== ZONES COLLECTION =====
        # Primary key: zone_id (unique)
        await db.zones.create_index("zone_id", unique=True, name="idx_zone_id")
 
        # Filter by station
        await db.zones.create_index("station_id", name="idx_station_id")
 
        # Ordered listing by station and display order
        await db.zones.create_index(
            [("station_id", ASCENDING), ("display_order", ASCENDING)],
            name="idx_station_order"
        )
 
        # Filter active zones
        await db.zones.create_index("is_active", name="idx_is_active")
 
        # Zone type + station compound index (for type-filtered queries)
        await db.zones.create_index(
            [("station_id", ASCENDING), ("zone_type", ASCENDING)],
            name="idx_zone_type_station"
        )
 
        # Adjacent zones index (for flow graph traversal)
        await db.zones.create_index("adjacent_zones", name="idx_adjacent_zones")
 
        print("[MongoDB] Created indexes for 'zones' collection")
 
 
        # ===== ANALYTICS COLLECTION =====
        # Primary query: Get analytics for camera by time (descending)
        # Also works for ASC queries (MongoDB scans in reverse)
        await db.analytics.create_index(
            [("camera_id", DESCENDING), ("timestamp", DESCENDING)],
            name="idx_camera_time"
        )
 
        # Time index for global time-range queries (non-TTL)
        await db.analytics.create_index(
            [("timestamp", DESCENDING)],
            name="idx_timestamp"
        )
 
        # REMOVED: idx_risk_camera - not used in any queries
        # REMOVED: idx_camera_time_asc - redundant (DESC index works for both directions)
 
        print("[MongoDB] Created indexes for 'analytics' collection")
 
 
        # ===== ALERTS COLLECTION =====
        # Unique alert ID
        await db.alerts.create_index("alert_id", unique=True, name="idx_alert_id")
 
        # Get alerts for camera by time
        await db.alerts.create_index(
            [("camera_id", DESCENDING), ("timestamp", DESCENDING)],
            name="idx_alert_camera_time"
        )
 
        # Filter by severity and status
        await db.alerts.create_index(
            [("severity", ASCENDING), ("status", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_severity_status_time"
        )
 
        # Get active/unresolved alerts
        await db.alerts.create_index(
            [("status", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_status_time"
        )
 
        # Time index for retention/archival jobs and time slicing (non-TTL)
        await db.alerts.create_index(
            [("timestamp", DESCENDING)],
            name="idx_alert_timestamp"
        )
 
        print("[MongoDB] Created indexes for 'alerts' collection")
 
 
        # ===== IMAGES COLLECTION =====
        # Get images for camera by time
        await db.images.create_index(
            [("camera_id", DESCENDING), ("timestamp", DESCENDING)],
            name="idx_image_camera_time"
        )
 
        # Link to alert
        await db.images.create_index("alert_id", unique=True, name="idx_image_alert")
 
        # Filter by risk level
        await db.images.create_index(
            [("risk_level", ASCENDING), ("camera_id", ASCENDING)],
            name="idx_risk_level_camera"
        )
 
        # Time index for retention/cleanup jobs (non-TTL)
        # Note: Actual image files need separate cleanup (cron job or scheduled task)
        await db.images.create_index(
            [("timestamp", DESCENDING)],
            name="idx_image_timestamp"
        )
 
        print("[MongoDB] Created indexes for 'images' collection")
 
 
        # REMOVED: detections collection - was write-only for debugging, never queried
 
 
        # ===== TRAIN_SCHEDULES COLLECTION =====
        # Unique composite key: train_number + schedule_date + arrival_time + departure_time
        await db.train_schedules.create_index(
            [
                ("train_number", ASCENDING),
                ("schedule_date", ASCENDING),
                ("arrival_time", ASCENDING),
                ("departure_time", ASCENDING)
            ],
            unique=True,
            name="idx_train_schedule_unique"
        )
 
        # Query upcoming arrivals by date and time
        await db.train_schedules.create_index(
            [("schedule_date", ASCENDING), ("arrival_time", ASCENDING)],
            name="idx_schedule_arrival"
        )
 
        # Query upcoming departures by date and time
        await db.train_schedules.create_index(
            [("schedule_date", ASCENDING), ("departure_time", ASCENDING)],
            name="idx_schedule_departure"
        )
 
        # Train lookup by number
        await db.train_schedules.create_index("train_number", name="idx_train_number")
 
        # Time index for schedule cleanup/range queries (non-TTL)
        await db.train_schedules.create_index(
            [("schedule_date", DESCENDING)],
            name="idx_train_schedule_date"
        )
 
        print("[MongoDB] Created indexes for 'train_schedules' collection")
 
 
        # ===== TRAIN_LIVE_STATUS COLLECTION =====
        # Unique composite key: train_number + schedule_date + station_code
        await db.train_live_status.create_index(
            [
                ("train_number", ASCENDING),
                ("schedule_date", ASCENDING),
                ("station_code", ASCENDING)
            ],
            unique=True,
            name="idx_live_status_unique"
        )
 
        # Query by station and last fetch time (for fetch cycle management)
        await db.train_live_status.create_index(
            [("station_code", ASCENDING), ("last_fetched_at", DESCENDING)],
            name="idx_station_fetch_time"
        )
 
        # Query by fetch cycle (to find trains already fetched in current cycle)
        await db.train_live_status.create_index(
            [("fetch_cycle", ASCENDING), ("station_code", ASCENDING)],
            name="idx_fetch_cycle_station"
        )
 
        # Filter by terminal status (skip ARRIVED/DEPARTED trains)
        await db.train_live_status.create_index(
            "is_terminal_status",
            name="idx_terminal_status"
        )
 
        # Time index for fetch-cycle and maintenance queries (non-TTL)
        await db.train_live_status.create_index(
            [("last_fetched_at", DESCENDING)],
            name="idx_live_status_last_fetched"
        )
 
        print("[MongoDB] Created indexes for 'train_live_status' collection")
 
 
        # ===== PLATFORM_HISTORY COLLECTION =====
        # Unique train number
        await db.platform_history.create_index("train_number", unique=True, name="idx_platform_train")
 
        print("[MongoDB] Created indexes for 'platform_history' collection")
 
 
        # ===== ISLAND_ALERTS COLLECTION =====
        # Unique alert ID
        await db.island_alerts.create_index("alert_id", unique=True, name="idx_island_alert_id")
 
        # Query alerts by island and time window
        await db.island_alerts.create_index(
            [("island_id", ASCENDING), ("window_start", DESCENDING)],
            name="idx_island_window"
        )
 
        # Filter by status and creation time
        await db.island_alerts.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_island_status_time"
        )
 
        # Filter by risk level and status
        await db.island_alerts.create_index(
            [("risk_level", ASCENDING), ("status", ASCENDING)],
            name="idx_island_risk_status"
        )
 
        # Optimized index for overlap detection (island + status + window_start range)
        await db.island_alerts.create_index(
            [("island_id", ASCENDING), ("status", ASCENDING), ("window_start", ASCENDING)],
            name="idx_island_overlap_detection"
        )
 
        # Time index for archival/reporting jobs (non-TTL)
        await db.island_alerts.create_index(
            [("created_at", DESCENDING)],
            name="idx_island_alert_created_at"
        )
 
        print("[MongoDB] Created indexes for 'island_alerts' collection")
 
 
        # ===== USERS COLLECTION =====
        # Maintained here (manual/admin flow), not in request path.
        await db.users.create_index("username", unique=True)
        await db.users.create_index("email", unique=True, sparse=True)
        await db.users.create_index("phone", unique=True, sparse=True)
 
        print("[MongoDB] Created indexes for 'users' collection")
 
 
        # ===== MASTER RBAC COLLECTIONS =====
        await db.viewers_user_collection.create_index("email", unique=True, name="idx_viewers_user_email")
        await db.viewers_user_collection.create_index("roleID", name="idx_viewers_user_role")
        await db.viewers_user_collection.create_index("active", name="idx_viewers_user_active")
        await db.viewers_user_collection.create_index("services", name="idx_viewers_user_services")
        print("[MongoDB] Created indexes for 'viewers_user_collection'")
 
        await db.roles.create_index("name", unique=True, name="idx_roles_name")
        await db.roles.create_index("level", name="idx_roles_level")
        print("[MongoDB] Created indexes for 'roles'")
 
        await db.modules.create_index("name", unique=True, name="idx_modules_name")
        await db.modules.create_index("urlName", unique=True, name="idx_modules_url_name")
        print("[MongoDB] Created indexes for 'modules'")
 
        await db.userlogin.create_index([("userID", ASCENDING), ("createAt", DESCENDING)], name="idx_userlogin_user_time")
        print("[MongoDB] Created indexes for 'userlogin'")
 
 
        # ===== WHATSAPP_SUBSCRIPTIONS COLLECTION =====
        await db.whatsapp_subscriptions.create_index("phone_number", unique=True, name="idx_whatsapp_phone")
        await db.whatsapp_subscriptions.create_index("username", name="idx_whatsapp_username")
        await db.whatsapp_subscriptions.create_index(
            [("opt_in_confirmed", ASCENDING), ("train_alert_enabled", ASCENDING)],
            name="idx_whatsapp_confirmed_enabled",
        )
        await db.whatsapp_subscriptions.create_index("updated_at", name="idx_whatsapp_updated")
 
        print("[MongoDB] Created indexes for 'whatsapp_subscriptions' collection")
 
 
        # ===== FOB_ANALYTICS COLLECTION (enhanced) =====
        await db.fob_analytics.create_index(
            [("fob_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_fob_id_time"
        )
        await db.fob_analytics.create_index(
            [("station_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_fob_station_time"
        )
 
        print("[MongoDB] Created indexes for 'fob_analytics' collection")
 
 
        # ===== PLATFORM_ANALYTICS COLLECTION =====
        await db.platform_analytics.create_index(
            [("zone_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_platform_zone_time"
        )
        await db.platform_analytics.create_index(
            [("station_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_platform_station_time"
        )
 
        print("[MongoDB] Created indexes for 'platform_analytics' collection")
 
 
        # ===== STATION_ANALYTICS COLLECTION =====
        await db.station_analytics.create_index(
            [("station_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_station_id_time"
        )
 
        print("[MongoDB] Created indexes for 'station_analytics' collection")
 
 
        # ===== ALERTS - Zone filtering indexes =====
        await db.alerts.create_index(
            [("zone_type", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_alert_zone_type_time"
        )
        await db.alerts.create_index(
            [("zone_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_alert_zone_id_time"
        )
 
        print("[MongoDB] Created zone-aware indexes for 'alerts' collection")
 
    except Exception as e:
        print(f"[MongoDB] Index creation warning: {e}")
 
 
def get_database():
    """Get MongoDB database instance (dual-write when test DB is configured)."""
    return MongoDB.database
 
 
def is_connected() -> bool:
    """Check if MongoDB is connected"""
    return (MongoDB.client is not None) and (MongoDB.prod_database is not None)
 