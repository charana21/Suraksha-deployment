
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import get_settings

async def add_missing_cameras():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    cameras_to_add = [
        {
            "camera_id": "cam_pf10_fob_vip",
            "name": "PF 10 HYB FOB FC VIP ENTRANCE",
            "rtsp_url": "rtsp://localhost:8554/vip_entrance",
            "fob_type": "HYD",
            "zone_id": "zone_pf10_fob_vip",
            "location": "PF-10",
            "status": "inactive",
            "is_active": False,
            "settings": {"target_fps": 1}
        },
        {
            "camera_id": "cam_pf1_fob_lift",
            "name": "PF 1 HYB FOB LIFT",
            "rtsp_url": "rtsp://localhost:8554/lift_area",
            "fob_type": "HYD",
            "zone_id": "zone_pf1_fob_lift",
            "location": "PF-1",
            "status": "inactive",
            "is_active": False,
            "settings": {"target_fps": 1}
        }
    ]

    print("Checking for missing cameras...")
    
    for cam in cameras_to_add:
        # Check if exists
        existing = await db.cameras.find_one({"camera_id": cam["camera_id"]})
        if existing:
            print(f"[SKIP] Camera {cam['camera_id']} already exists")
            # Optional: Update zone_id if missing
            if existing.get("zone_id") != cam["zone_id"]:
                 await db.cameras.update_one(
                     {"camera_id": cam["camera_id"]},
                     {"$set": {"zone_id": cam["zone_id"]}}
                 )
                 print(f"   [FIX] Updated zone_id for {cam['camera_id']}")
        else:
            # Create
            cam["created_at"] = datetime.now(UTC)
            cam["updated_at"] = datetime.now(UTC)
            cam["last_seen_at"] = None
            
            await db.cameras.insert_one(cam)
            print(f"[OK] Created camera: {cam['name']}")

    print("Done.")
    client.close()

if __name__ == "__main__":
    asyncio.run(add_missing_cameras())
