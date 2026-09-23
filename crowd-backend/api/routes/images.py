"""
Images API endpoints
Provides access to captured alert images
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
from datetime import UTC, datetime, timedelta
from pathlib import Path
from db.mongodb import MongoDB
from config.config import get_settings
from api.security import require_authorized
DB_ERROR_MSG = "Database not available"

router = APIRouter()
settings = get_settings()

@router.get("/images", tags=["Images"], responses={
    503: {"description": DB_ERROR_MSG},
    400: {"description": "Invalid risk_level parameter"}
})
async def list_images(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (HIGH/CRITICAL)"),
    hours: int = Query(24, description="Time range in hours"),
    limit: int = Query(50, description="Maximum number of images to return")
):
    """
    List alert images with filters

    - **camera_id**: Filter by camera
    - **risk_level**: Filter by risk level (HIGH, CRITICAL)
    - **hours**: Time range (default: last 24 hours)
    - **limit**: Maximum results (default: 50)

    Returns image metadata sorted by timestamp (newest first)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    # Build query
    query = {}

    if camera_id:
        query["camera_id"] = camera_id

    if risk_level:
        if risk_level not in ["HIGH", "CRITICAL"]:
            raise HTTPException(status_code=400, detail="Invalid risk_level. Must be: HIGH or CRITICAL")
        query["risk_level"] = risk_level

    # Time range
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    query["timestamp"] = {"$gte": cutoff}

    # Query database
    cursor = MongoDB.database.images.find(query).sort("timestamp", -1).limit(limit)
    images = await cursor.to_list(length=limit)

    # Convert ObjectId to string
    for image in images:
        image["_id"] = str(image["_id"])

    return {
        "status": "success",
        "count": len(images),
        "images": images,
        "query": {
            "camera_id": camera_id,
            "risk_level": risk_level,
            "hours": hours,
            "limit": limit
        }
    }


@router.get("/images/{image_id}", tags=["Images"], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": "Image not found"}
})
async def get_image_metadata(image_id: str):
    """
    Get image metadata by alert ID

    - **image_id**: Alert ID (UUID) linked to the image
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    image = await MongoDB.database.images.find_one({"alert_id": image_id})

    if not image:
        raise HTTPException(status_code=404, detail=f"Image for alert {image_id} not found")

    # Convert ObjectId to string
    image["_id"] = str(image["_id"])

    return {
        "status": "success",
        "image": image
    }


@router.get("/images/{image_id}/download", tags=["Images"], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": "Image not found"}
})
async def download_image(image_id: str):
    """
    Download actual image file

    - **image_id**: Alert ID (UUID) linked to the image

    Returns the image file (JPEG)
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    # Get image metadata
    image = await MongoDB.database.images.find_one({"alert_id": image_id})

    if not image:
        raise HTTPException(status_code=404, detail=f"Image for alert {image_id} not found")

    # Construct full file path
    file_path = Path(settings.images_dir) / image["file_path"]

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Image file not found on disk: {image['file_path']}"
        )

    # Return file
    return FileResponse(
        path=str(file_path),
        media_type="image/jpeg",
        filename=f"{image_id}.jpg"
    )


@router.get("/images/camera/{camera_id}/latest", tags=["Images"], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": "No images found for camera"}
})
async def get_latest_camera_image(camera_id: str):
    """
    Get latest image for specific camera

    - **camera_id**: Camera identifier

    Returns metadata for most recent image
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    image = await MongoDB.database.images.find_one(
        {"camera_id": camera_id},
        sort=[("timestamp", -1)]
    )

    if not image:
        raise HTTPException(status_code=404, detail=f"No images found for camera {camera_id}")

    # Convert ObjectId to string
    image["_id"] = str(image["_id"])

    return {
        "status": "success",
        "image": image
    }


@router.get("/images/camera/{camera_id}/count", tags=["Images"], responses={
    503: {"description": DB_ERROR_MSG}
})
async def get_camera_image_count(
    camera_id: str,
    hours: int = Query(24, description="Time range in hours")
):
    """
    Get count of images for specific camera

    - **camera_id**: Camera identifier
    - **hours**: Time range (default: 24 hours)

    Returns:
    - Total images
    - Images by risk level
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    # Count total
    total = await MongoDB.database.images.count_documents({
        "camera_id": camera_id,
        "timestamp": {"$gte": cutoff}
    })

    # Count by risk level
    high_count = await MongoDB.database.images.count_documents({
        "camera_id": camera_id,
        "timestamp": {"$gte": cutoff},
        "risk_level": "HIGH"
    })

    critical_count = await MongoDB.database.images.count_documents({
        "camera_id": camera_id,
        "timestamp": {"$gte": cutoff},
        "risk_level": "CRITICAL"
    })

    return {
        "status": "success",
        "camera_id": camera_id,
        "time_range_hours": hours,
        "total_images": total,
        "by_risk_level": {
            "HIGH": high_count,
            "CRITICAL": critical_count
        }
    }


@router.delete("/images/{image_id}", tags=["Images"], dependencies=[require_authorized], responses={
    503: {"description": DB_ERROR_MSG},
    404: {"description": "Image not found"}
})
async def delete_image(image_id: str):
    """
    Delete image (both file and metadata)

    - **image_id**: Alert ID (UUID) linked to the image
    """
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DB_ERROR_MSG)

    # Get image metadata
    image = await MongoDB.database.images.find_one({"alert_id": image_id})

    if not image:
        raise HTTPException(status_code=404, detail=f"Image for alert {image_id} not found")

    # Delete file
    file_path = Path(settings.images_dir) / image["file_path"]
    if file_path.exists():
        file_path.unlink()

    # Delete metadata
    await MongoDB.database.images.delete_one({"alert_id": image_id})

    # Unlink from alert
    await MongoDB.database.alerts.update_one(
        {"alert_id": image_id},
        {"$set": {"has_image": False}, "$unset": {"image_id": ""}}
    )

    return {
        "status": "success",
        "message": f"Image {image_id} deleted"
    }