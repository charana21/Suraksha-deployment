import asyncio
from db.mongodb import connect_to_mongo, close_mongo_connection
from services.camera_service import CameraService
from config.config import get_settings
import logging
logger = logging.getLogger(__name__)

async def check_cameras():
    await connect_to_mongo(get_settings())
    cameras = await CameraService.list_cameras()
    # print(f"Total cameras: {len(cameras)}")
    logger.info(f"Total cameras found: {len(cameras)}")
    for cam in cameras:
        # print(f"ID: {cam['camera_id']}, Name: {cam['name']}, URL: {cam['rtsp_url']}, Zone: {cam.get('zone_id')}, Status: {cam['status']}")
        logger.info(f"Camera found: ID: {cam['camera_id']}, Name: {cam['name']}, URL: {cam['rtsp_url']}, Zone: {cam.get('zone_id')}, Status: {cam['status']}")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(check_cameras())
