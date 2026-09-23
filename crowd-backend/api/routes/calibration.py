"""
Camera Calibration API endpoints
Provides endpoints for managing homography calibrations
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json
from pathlib import Path
from datetime import UTC, datetime
import re

from models.schemas import (
    HomographyCalibrationRequest,
    HomographyCalibrationResponse,
    CalibrationInfo,
    CalibrationListResponse
)
from utils.homography import (
    ReferencePoint,
    compute_homography,
    validate_homography
)

router = APIRouter()

# Path to calibration config file
CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'camera_calibrations.json'


def _load_config() -> dict:
    """Load camera calibrations config"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_config(config: dict) -> None:
    """Save camera calibrations config"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


@router.post(
    "/calibration/compute",
    response_model=HomographyCalibrationResponse,
    tags=["Calibration"],
    responses={
        400: {"description": "Invalid calibration request"},
        500: {"description": "Calibration computation failed"}
    }
)
async def compute_calibration(request: HomographyCalibrationRequest):
    """
    Compute homography matrix from reference points.

    Requires at least 4 reference points mapping pixel coordinates to
    real-world coordinates in meters.

    Returns the computed 3x3 homography matrix and reprojection error.
    Does NOT save to config - use PUT /calibration/{camera_id} to save.
    """
    if len(request.reference_points) < 4:
        raise HTTPException(
            status_code=400,
            detail=f"At least 4 reference points required, got {len(request.reference_points)}"
        )

    try:
        # Convert to internal format
        ref_points = [
            ReferencePoint(
                pixel=tuple(p.pixel),
                world=tuple(p.world)
            )
            for p in request.reference_points
        ]

        frame_size = tuple(request.frame_size)

        # Compute homography
        H, error, mask = compute_homography(ref_points)

        # Validate
        is_valid, msg = validate_homography(H, frame_size)

        # Extract computed area from validation message
        computed_area = None
        match = re.search(r'area: ([\d.]+)', msg)
        if match:
            computed_area = float(match.group(1))

        if not is_valid:
            return HomographyCalibrationResponse(
                status="warning",
                camera_id=request.camera_id,
                matrix=H.tolist(),
                reprojection_error=error,
                computed_area_m2=computed_area,
                message=f"Homography computed with warning: {msg}"
            )

        return HomographyCalibrationResponse(
            status="success",
            camera_id=request.camera_id,
            matrix=H.tolist(),
            reprojection_error=error,
            computed_area_m2=computed_area,
            message=f"Homography computed successfully. {msg}"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Computation failed: {str(e)}")


@router.put(
    "/calibration/{camera_id}",
    tags=["Calibration"],
    responses={
        400: {"description": "Invalid calibration request"},
        500: {"description": "Failed to save calibration"}
    }
)
async def save_calibration(
    camera_id: str,
    request: HomographyCalibrationRequest,
    calibrated_by: Optional[str] = Query(None, description="User who performed calibration")
):
    """
    Compute and save homography calibration for a camera.

    This endpoint:
    1. Computes the homography matrix from reference points
    2. Validates the result
    3. Saves to camera_calibrations.json

    The camera entry will be created if it doesn't exist.
    """
    if len(request.reference_points) < 4:
        raise HTTPException(
            status_code=400,
            detail="At least 4 reference points required"
        )

    try:
        # Convert to internal format
        ref_points = [
            ReferencePoint(pixel=tuple(p.pixel), world=tuple(p.world))
            for p in request.reference_points
        ]

        frame_size = tuple(request.frame_size)

        # Compute
        H, error, mask = compute_homography(ref_points)

        # Validate
        is_valid, msg = validate_homography(H, frame_size)

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Homography validation failed: {msg}"
            )

        # Extract computed area
        computed_area = 150.0  # default
        match = re.search(r'area: ([\d.]+)', msg)
        if match:
            computed_area = float(match.group(1))

        # Load existing config
        config = _load_config()

        # Ensure camera entry exists
        if camera_id not in config:
            config[camera_id] = {
                'visible_area_m2': computed_area,
                'corridor_width_m': 4.0,
                'coverage_length_m': 40.0,
                'lane_count': 1,
                'camera_type': 'fob',
                'notes': 'Calibrated via API'
            }
        else:
            # Update visible_area with computed value
            config[camera_id]['visible_area_m2'] = computed_area

        # Add/update homography
        config[camera_id]['homography'] = {
            'enabled': True,
            'matrix': H.tolist(),
            'reference_points': [
                {'pixel': list(p.pixel), 'world': list(p.world)}
                for p in ref_points
            ],
            'frame_size': list(frame_size),
            'reprojection_error': error,
            'calibrated_at': datetime.now(UTC).isoformat() + 'Z',
            'calibrated_by': calibrated_by or 'api'
        }

        # Save
        _save_config(config)

        inliers = int(mask.sum()) if mask is not None else len(ref_points)

        return {
            'status': 'success',
            'camera_id': camera_id,
            'message': f'Calibration saved. {msg}',
            'reprojection_error': error,
            'computed_area_m2': computed_area,
            'inliers': inliers
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/calibration/{camera_id}",
    tags=["Calibration"],
    responses={404: {"description": "Camera calibration not found"}}
)
async def get_calibration(camera_id: str):
    """
    Get calibration data for a camera.

    Returns both the simple visible_area parameters and homography data if available.
    """
    config = _load_config()

    if camera_id not in config:
        # Try default
        if '_default_fob' in config:
            return {
                'status': 'success',
                'camera_id': camera_id,
                'is_default': True,
                'calibration': config['_default_fob']
            }
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    cal = config[camera_id]
    hom = cal.get('homography', {})

    return {
        'status': 'success',
        'camera_id': camera_id,
        'is_default': False,
        'calibration': {
            'visible_area_m2': cal.get('visible_area_m2'),
            'corridor_width_m': cal.get('corridor_width_m'),
            'coverage_length_m': cal.get('coverage_length_m'),
            'lane_count': cal.get('lane_count'),
            'camera_type': cal.get('camera_type'),
            'notes': cal.get('notes')
        },
        'has_homography': hom.get('enabled', False),
        'homography': hom if hom.get('enabled') else None
    }


@router.delete(
    "/calibration/{camera_id}/homography",
    tags=["Calibration"],
    responses={404: {"description": "Camera not found"}}
)
async def delete_homography(camera_id: str):
    """
    Remove homography calibration for a camera (keeps simple calibration).
    """
    config = _load_config()

    if camera_id not in config:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    if 'homography' in config[camera_id]:
        del config[camera_id]['homography']
        _save_config(config)
        return {'status': 'success', 'message': 'Homography calibration removed'}

    return {'status': 'success', 'message': 'No homography calibration to remove'}


@router.get("/calibration", response_model=CalibrationListResponse, tags=["Calibration"])
async def list_calibrations():
    """
    List all camera calibrations with their status.
    """
    config = _load_config()

    cameras = []
    for camera_id, cal in config.items():
        if camera_id.startswith('_'):
            continue

        hom = cal.get('homography', {})
        cameras.append(CalibrationInfo(
            camera_id=camera_id,
            visible_area_m2=cal.get('visible_area_m2', 150.0),
            corridor_width_m=cal.get('corridor_width_m'),
            coverage_length_m=cal.get('coverage_length_m'),
            has_homography=hom.get('enabled', False),
            reprojection_error=hom.get('reprojection_error'),
            calibrated_at=hom.get('calibrated_at'),
            calibrated_by=hom.get('calibrated_by')
        ))

    return CalibrationListResponse(
        status='success',
        count=len(cameras),
        cameras=cameras
    )


@router.post(
    "/calibration/{camera_id}/test",
    tags=["Calibration"],
    responses={
        400: {"description": "Calibration is not available or request is invalid"},
        404: {"description": "Camera not found"},
        500: {"description": "Calibration test failed"}
    }
)
async def test_calibration(
    camera_id: str,
    pixel_x: float = Query(..., description="Pixel X coordinate to test"),
    pixel_y: float = Query(..., description="Pixel Y coordinate to test")
):
    """
    Test a calibration by converting pixel coordinates to world coordinates.

    Useful for verifying the calibration is working correctly.
    """
    config = _load_config()

    if camera_id not in config:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    cal_config = config[camera_id]

    if not cal_config.get('homography', {}).get('enabled', False):
        raise HTTPException(
            status_code=400,
            detail="Camera does not have homography calibration"
        )

    try:
        from utils.homography import HomographyCalibration
        calibration = HomographyCalibration(camera_id, cal_config)

        world_x, world_y = calibration.pixel_to_world(pixel_x, pixel_y)
        scale = calibration.scale_at_y(
            int(pixel_y),
            cal_config['homography']['frame_size'][1],
            cal_config['homography']['frame_size'][0]
        )

        return {
            'status': 'success',
            'camera_id': camera_id,
            'input': {
                'pixel_x': pixel_x,
                'pixel_y': pixel_y
            },
            'output': {
                'world_x_m': round(world_x, 3),
                'world_y_m': round(world_y, 3),
                'scale_at_y': round(scale, 6)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
