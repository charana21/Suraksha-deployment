"""
Verification Script: Test RTSP Stream Readability & Verify MongoDB Storage
"""
import asyncio
import sys
import time
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import get_settings
from db.mongodb import connect_to_mongo, close_mongo_connection, MongoDB

async def verify_system():
    print("=" * 60)
    print(" 1. TESTING RTSP STREAM ACCESSIBILITY")
    print("=" * 60)
    
    test_rtsp = "rtsp://localhost:8554/cam_01"
    cap = cv2.VideoCapture(test_rtsp)
    ret, frame = cap.read()
    cap.release()

    if ret and frame is not None:
        print(f"[SUCCESS] Successfully read frame from {test_rtsp} (Resolution: {frame.shape[1]}x{frame.shape[0]})")
    else:
        print(f"[WARNING] Could not read frame from {test_rtsp}. Retrying...")
        time.sleep(2)
        cap = cv2.VideoCapture(test_rtsp)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            print(f"[SUCCESS] Retry succeeded! Frame read from {test_rtsp}")
        else:
            print(f"[FAIL] RTSP stream {test_rtsp} failed to yield frames.")

    print("\n" + "=" * 60)
    print(" 2. CHECKING MONGODB COLLECTIONS & RECORDS")
    print("=" * 60)

    settings = get_settings()
    await connect_to_mongo(settings)
    db = MongoDB.prod_database if MongoDB.prod_database is not None else MongoDB.database

    collections = await db.list_collection_names()
    print(f"MongoDB Database : '{db.name}'")
    print(f"Collections Found: {collections}\n")

    # Check cameras collection
    camera_count = await db.cameras.count_documents({})
    sim_cam_count = await db.cameras.count_documents({"camera_id": {"$regex": "^cam_sim_"}})
    print(f" Total Cameras in DB    : {camera_count}")
    print(f" Simulated Cameras (40) : {sim_cam_count}")

    # Check analytics collection
    analytics_count = await db.crowd_analytics.count_documents({})
    if analytics_count == 0:
        analytics_count = await db.analytics.count_documents({})
    print(f" Total Analytics Records : {analytics_count}")

    # Check heatmaps collection
    heatmaps_count = await db.heatmaps.count_documents({})
    print(f" Total Heatmap Records   : {heatmaps_count}")

    # Check alerts collection
    alerts_count = await db.alerts.count_documents({})
    print(f" Total Alert Records     : {alerts_count}")

    await close_mongo_connection()
    print("\n[DONE] Verification complete.")

if __name__ == "__main__":
    asyncio.run(verify_system())
