"""
Seed 40 Simulated RTSP Cameras into MongoDB for live stream testing
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import get_settings
from db.mongodb import connect_to_mongo, close_mongo_connection
from services.camera_service import CameraService

NUM_CAMERAS = 40
RTSP_HOST = "rtsp://localhost:8554"

async def seed_40_cameras():
    settings = get_settings()
    print("=" * 60)
    print("SEEDING 40 SIMULATED RTSP CAMERAS INTO MONGODB")
    print("=" * 60)

    await connect_to_mongo(settings)

    created = 0
    updated = 0

    for i in range(1, NUM_CAMERAS + 1):
        cam_num = f"{i:02d}"
        cam_id = f"cam_sim_{cam_num}"
        cam_name = f"Simulated Camera {cam_num}"
        rtsp_url = f"{RTSP_HOST}/cam_{cam_num}"
        location = f"Simulated Zone {((i - 1) // 5) + 1}"

        existing = await CameraService.get_camera(cam_id)
        if existing:
            await CameraService.update_camera(
                cam_id,
                {
                    "rtsp_url": rtsp_url,
                    "location": location,
                    "name": cam_name,
                    "status": "ACTIVE"
                }
            )
            updated += 1
        else:
            await CameraService.register_camera(
                camera_id=cam_id,
                name=cam_name,
                rtsp_url=rtsp_url,
                location=location,
                settings={
                    "target_fps": 1,
                    "enable_analytics": True,
                    "enable_alerts": True,
                    "enable_heatmaps": True,
                },
            )
            created += 1

        print(f"[{cam_num}/40] Registered {cam_id} -> {rtsp_url}")

    print("=" * 60)
    print(f"SUMMARY: Created: {created} | Updated: {updated} | Total: {NUM_CAMERAS}")
    print("=" * 60)

    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed_40_cameras())
