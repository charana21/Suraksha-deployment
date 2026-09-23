"""
Seed HYB FOB Cameras into MongoDB

IMPORTANT:
- Camera `name` MUST exactly match `camera_mappings.camera_name`
  in config/stations/hyb_fob.json
- This script ONLY creates cameras
- Zone mapping is done by seed_station_layout.py --auto-map
"""
import asyncio
import sys
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import get_settings
from db.mongodb import connect_to_mongo, close_mongo_connection
from services.camera_service import CameraService


# ============================================================
# CAMERA DEFINITIONS (MATCH hyb_fob.json EXACTLY)
# ============================================================

CAMERAS = [
    {
        "camera_id": "cam_pf1_fob_kzj",
        "name": "HYB FOB FACING PF 10",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.18:8554",
        "location": "PF1 FOB - KZJ Side",
    },
    {
        "camera_id": "cam_pf1_fob_hyb_end",
        "name": "PF 10 HYB FOB PATHWAY FACING PF 1",
        "rtsp_url": "rtsp://localhos/mystream",
        "location": "PF 10 HYB FOB PATHWAY FACING PF 1",
    },
    {
        "camera_id": "cam_pf1_fob_pf10",
        "name": "PF 1 HYB FOB FC PF 10",
        "rtsp_url": "rtsp://localhos/mystream1",
        "location": "PF1 FOB - PF10 Side",
    },
    {
        "camera_id": "cam_middle_fob_4_5",
        "name": "HYB FOB MIDDLE FACING PF 4&5",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.21:8554",
        "location": "HYB FOB MIDDLE FACING PF 4&5",
    },
    {
        "camera_id": "cam_middle_fob_6_7",
        "name": "HYB FOB MIDD FC 6&7",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.22:8554",
        "location": "Middle FOB - PF6 & PF7",
    },
    {
        "camera_id": "cam_pf10_fob_pf1",
        "name": "PF 10 HYB FOB FC PF1",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.19:8554",
        "location": "PF10 FOB - PF1 Side",
    },
    {
        "camera_id": "cam_pf10_fob_steps",
        "name": "PF 10 HYB FOB FC HYB STEPS",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.20:8554",
        "location": "PF10 FOB - Steps",
    },
    {
        "camera_id": "cam_pf10_fob_vip",
        "name": "PF 10 HYB FOB FC VIP ENTRANCE",
        "rtsp_url": "rtsp://localhost:8554/pf10_vip",
        "location": "PF10 FOB - VIP Entry",
    },
    {
        "camera_id": "cam_pf1_fob_lift",
        "name": "PF 1 HYB FOB LIFT",
        "rtsp_url": "rtsp://admin:Admin@123@10.51.200.24:8554",
        "location": "PF1 FOB - Lift",
    },
]


# ============================================================
# SEED LOGIC
# ============================================================

async def seed_cameras():
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("HYB FOB CAMERA SEEDING")
    logger.info("=" * 60)

    await connect_to_mongo(settings)

    created = 0
    skipped = 0

    for cam in CAMERAS:
        existing = await CameraService.get_camera(cam["camera_id"])

        if existing:
            logger.info(f"[UPDATE] Camera exists, updating config: {cam['name']}")
            await CameraService.update_camera(
                cam["camera_id"],
                {
                    "rtsp_url": cam["rtsp_url"],
                    "location": cam["location"],
                    "name": cam["name"]
                }
            )
            # skipped += 1 
            continue

        await CameraService.register_camera(
            camera_id=cam["camera_id"],
            name=cam["name"],
            rtsp_url=cam["rtsp_url"],
            location=cam["location"],
            settings={
                "target_fps": 1,
                "enable_analytics": True,
                "enable_alerts": True,
                "enable_heatmaps": True,
            },
        )

        logger.info(f"[OK] Created camera: {cam['name']}")
        created += 1

    logger.info("\n" + "=" * 60)
    logger.info("SEED SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Created : {created}")
    logger.info(f"Skipped : {skipped}")
    logger.info(f"Total   : {len(CAMERAS)}")

    await close_mongo_connection()
    logger.info("\n[DONE] Camera seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_cameras())
