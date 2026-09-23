"""
Seed Station Layout Script

Seeds the MongoDB database with zone configurations from station layout JSON files.
Also optionally auto-maps existing cameras to zones based on camera name matching.

Usage:
    python scripts/seed_station_layout.py [--station HYB] [--auto-map] [--clear]

Options:
    --station   Station ID to seed (default: HYB)
    --auto-map  Automatically map existing cameras to zones by name matching
    --clear     Clear existing zones for the station before seeding
"""
import asyncio
import json
import logging
import os
import sys
import argparse
from datetime import UTC, datetime
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
import aiofiles
from motor.motor_asyncio import AsyncIOMotorClient
from config.config import get_settings
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def load_station_config(station_id: str) -> dict:
    """Load station configuration from JSON file"""
    # Try new consolidated config first
    stations_config_path = Path(__file__).parent.parent / "config" / "stations_config.json"
    
    if stations_config_path.exists():
        try:
            async with aiofiles.open(stations_config_path, 'r') as f:
                full_config = json.loads(await f.read())
                if station_id in full_config:
                    return full_config[station_id]
        except Exception:
            logger.exception("[WARN] Failed to read stations_config.json")

    # Fallback to old separate files
    config_path = Path(__file__).parent.parent / "config" / "stations" / f"{station_id.lower()}_fob.json"

    if not config_path.exists():
        logger.error(f"[ERROR] Station config not found: {stations_config_path} or {config_path}")
        return None

    async with aiofiles.open(config_path, 'r') as f:
        return json.loads(await f.read())


async def seed_zones(db, station_config: dict, clear_existing: bool = False):
    """Seed zones from station configuration"""
    station_id = station_config["station_id"]
    zones = station_config["zones"]

    if clear_existing:
        # Delete existing zones for this station
        result = await db.zones.delete_many({"station_id": station_id})
        logger.info(f"[INFO] Cleared {result.deleted_count} existing zones for station {station_id}")

    # Insert zones
    now = datetime.now(UTC)
    zones_created = 0
    zones_skipped = 0

    for zone in zones:
        # Check if zone already exists
        existing = await db.zones.find_one({"zone_id": zone["zone_id"]})
        if existing:
            logger.info(f"[SKIP] Zone {zone['zone_id']} already exists")
            zones_skipped += 1
            continue

        zone_doc = {
            "zone_id": zone["zone_id"],
            "zone_name": zone["zone_name"],
            "svg_region_id": zone["svg_region_id"],
            "display_order": zone["display_order"],
            "station_id": station_id,
            "zone_type": zone["zone_type"],
            "description": zone.get("description", ""),
            "adjacent_zones": zone.get("adjacent_zones", []),
            "area_m2": zone.get("area_m2"),
            "capacity": zone.get("capacity"),
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }

        await db.zones.insert_one(zone_doc)
        logger.info(f"[OK] Created zone: {zone['zone_id']} ({zone['zone_name']})")
        zones_created += 1

    logger.info(f"\n[SUMMARY] Zones: {zones_created} created, {zones_skipped} skipped")
    return zones_created


async def auto_map_cameras(db, station_config: dict):
    """Auto-map existing cameras to zones based on name matching"""
    camera_mappings = station_config.get("camera_mappings", [])
    now = datetime.now(UTC)

    cameras_mapped = 0
    cameras_not_found = 0

    for mapping in camera_mappings:
        camera_name = mapping["camera_name"]
        zone_id = mapping["zone_id"]

        # Find camera by name (case-insensitive, partial match)
        camera = await db.cameras.find_one({
            "name": {"$regex": camera_name, "$options": "i"}
        })

        if not camera:
            # Try exact match
            camera = await db.cameras.find_one({"name": camera_name})

        if camera:
            # Update camera with zone_id
            await db.cameras.update_one(
                {"camera_id": camera["camera_id"]},
                {"$set": {"zone_id": zone_id, "updated_at": now}}
            )
            logger.info(f"[OK] Mapped camera '{camera['name']}' -> zone '{zone_id}'")
            cameras_mapped += 1
        else:
            logger.warning(f"[WARN] Camera not found: '{camera_name}'")
            cameras_not_found += 1

    logger.info(f"\n[SUMMARY] Cameras: {cameras_mapped} mapped, {cameras_not_found} not found")
    return cameras_mapped


async def main():
    parser = argparse.ArgumentParser(description="Seed station layout to MongoDB")
    parser.add_argument("--station", default="HYB", help="Station ID (default: HYB)")
    parser.add_argument("--auto-map", action="store_true", help="Auto-map cameras to zones")
    parser.add_argument("--clear", action="store_true", help="Clear existing zones first")

    args = parser.parse_args()

    settings = get_settings()

    logger.info(f"[INFO] Connecting to MongoDB: {settings.mongodb_uri}")
    logger.info(f"[INFO] Database: {settings.mongodb_database}")
    logger.info(f"[INFO] Station: {args.station}")
    logger.info()

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    try:
        # Test connection
        await client.admin.command('ping')
        logger.info("[OK] MongoDB connected\n")

        # Load station config
        station_config = await load_station_config(args.station)
        if not station_config:
            return 1

        logger.info(f"[INFO] Loaded config: {station_config['station_name']}")
        logger.info(f"[INFO] Layout: {station_config['layout_name']}")
        logger.info(f"[INFO] Version: {station_config['layout_version']}")
        logger.info(f"[INFO] Zones: {len(station_config['zones'])}")
        logger.info(f"[INFO] Camera mappings: {len(station_config.get('camera_mappings', []))}")
        logger.info()

        # Seed zones
        logger.info("=" * 50)
        logger.info("SEEDING ZONES")
        logger.info("=" * 50)
        await seed_zones(db, station_config, clear_existing=args.clear)

        # Auto-map cameras if requested
        if args.auto_map:
            logger.info()
            logger.info("=" * 50)
            logger.info("AUTO-MAPPING CAMERAS")
            logger.info("=" * 50)
            await auto_map_cameras(db, station_config)

        logger.info()
        logger.info("[DONE] Seeding complete!")
        return 0

    except Exception:
        logger.exception("[ERROR]")
        return 1

    finally:
        client.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
