"""
Seed KZJ FOB Cameras into MongoDB

IMPORTANT:
- Camera `name` MUST exactly match `camera_mappings.camera_name`
  in config/stations/kzj_fob.json
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
# CAMERA DEFINITIONS (MATCH kzj_fob.json EXACTLY)
# ============================================================

CAMERAS = [
    {
        "camera_id": "cam_kzj_pf1_fc_kzj",
        "name": "PF 1 KZJ FOB FC KZJ",
        "rtsp_url": "rtsp://localhost:8554/kzj_pf1_kzj",
        "location": "PF1 FOB - KZJ Side",
    },
    {
        "camera_id": "cam_kzj_pf1_fc_hyb",
        "name": "PF 1 KZJ FOB FC HYB",
        "rtsp_url": "rtsp://localhost:8554/kzj_pf1_hyb",
        "location": "PF1 FOB - HYB Side",
    },
    {
        "camera_id": "cam_kzj_new_middle_pf10",
        "name": "NEW KZJ FOB MIDDLE FC PF10",
        "rtsp_url": "rtsp://localhost:8554/kzj_new_middle_pf10",
        "location": "PF1 FOB Middle - PF10 Side",
    },
    {
        "camera_id": "cam_kzj_escalator_pf1",
        "name": "KZJ FOB ESCALATOR FC PF1",
        "rtsp_url": "rtsp://localhost:8554/kzj_escalator_pf1",
        "location": "PF1 Escalator Zone",
    },
    {
        "camera_id": "cam_kzj_new_near_pf01",
        "name": "NEW KZJ FOB NEAR PF01",
        "rtsp_url": "rtsp://localhost:8554/kzj_new_near_pf01",
        "location": "New Camera Near PF1",
    },
    {
        "camera_id": "cam_kzj_new_fc_pf01",
        "name": "NEW KZJ FOB FC PF01",
        "rtsp_url": "rtsp://localhost:8554/kzj_new_fc_pf01",
        "location": "New Camera Facing PF1",
    },
    {
        "camera_id": "cam_kzj_middle_4_5",
        "name": "KZJ FOB MIDDLE FC 4&5",
        "rtsp_url": "rtsp://localhost:8554/kzj_middle_4_5",
        "location": "Middle FOB - PF4 & PF5",
    },
    {
        "camera_id": "cam_kzj_middle_8_9",
        "name": "KZJ FOB MIDDLE FC 8&9",
        "rtsp_url": "rtsp://localhost:8554/kzj_middle_8_9",
        "location": "Middle FOB - PF8 & PF9",
    },
    {
        "camera_id": "cam_kzj_new_fc_pf10",
        "name": "NEW KZJ FOB FC PF10",
        "rtsp_url": "rtsp://localhost:8554/kzj_new_fc_pf10",
        "location": "New Camera Facing PF10",
    },
    {
        "camera_id": "cam_kzj_new_mid_pf10",
        "name": "NEW KZJ MID FC PF10",
        "rtsp_url": "rtsp://localhost:8554/kzj_new_mid_pf10",
        "location": "New Camera Middle PF10",
    },
]


# ============================================================
# SEED LOGIC
# ============================================================

async def seed_cameras():
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("KZJ FOB CAMERA SEEDING")
    logger.info("=" * 60)

    await connect_to_mongo(settings)

    created = 0
    updated = 0

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
            updated += 1
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
    logger.info(f"Updated : {updated}")
    logger.info(f"Total   : {len(CAMERAS)}")

    await close_mongo_connection()
    logger.info("\n[DONE] KZJ Camera seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_cameras())
