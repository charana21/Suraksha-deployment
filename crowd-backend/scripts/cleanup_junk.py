import asyncio
from db.mongodb import connect_to_mongo, close_mongo_connection
from services.camera_service import CameraService
from config.config import get_settings
import logging
logger = logging.getLogger(__name__)
async def cleanup():
    await connect_to_mongo(get_settings())
    # Delete the known junk camera
    junk_id = "camera_1cefc255" # From user logs
    await CameraService.delete_camera(junk_id)
    logger.info(f"Deleted {junk_id}")
    
    # Also delete any other cameras that look auto-generated (camera_xxxxxxxx) and have the mystream URL
    cameras = await CameraService.list_cameras()
    for cam in cameras:
        if cam['camera_id'].startswith("camera_") and "mystream" in cam['rtsp_url']:
             await CameraService.delete_camera(cam['camera_id'])
             logger.info(f"Deleted duplicate {cam['camera_id']}")

    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(cleanup())
