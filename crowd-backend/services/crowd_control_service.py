"""
Crowd Control APIs

Live people count for platform, FOB and booking office cameras, with
platform-wise and FOB-wise totals. Camera groupings are read from
config/crowd_control_cameras.json.
"""
import json
import os
import asyncio
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pymongo import DESCENDING

from db.mongodb import MongoDB

router = APIRouter(prefix="/crowd_control", tags=["Crowd Control"])

CAMERAS_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "crowd_control_cameras.json",
)
ERR_DATABASE_NOT_AVAILABLE = "Database not available"


@lru_cache(maxsize=1)
def load_camera_config() -> dict:
    with open(CAMERAS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _iso(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" if ts else None


def _level(people_count, thresholds: list) -> str | None:
    if people_count is None:
        return None

    medium, high, critical = thresholds
    if people_count > critical:
        return "critical"
    if people_count > high:
        return "high"
    if people_count > medium:
        return "medium"
    return "accepted"


async def get_latest_by_camera(camera_ids: list) -> dict:
    """Latest analytics doc per camera, keyed by camera_id (uses idx_camera_time)."""
    unique_camera_ids = list(dict.fromkeys(camera_ids))
    if not unique_camera_ids:
        return {}

    projection = {
        "_id": 0,
        "camera_id": 1,
        "timestamp": 1,
        "people_count": 1,
        "risk_level": 1,
    }

    async def fetch_latest(camera_id: str):
        return await MongoDB.database.analytics.find_one(
            {"camera_id": camera_id},
            projection,
            sort=[("timestamp", DESCENDING)],
        )

    results = await asyncio.gather(
        *(fetch_latest(camera_id) for camera_id in unique_camera_ids)
    )
    return {doc["camera_id"]: doc for doc in results if doc}


def _camera_entry(
    camera_id: str,
    latest: dict,
    name: str | None = None,
    include_risk: bool = False,
    thresholds: list | None = None,
    capacity: int | None = None,
) -> dict:
    doc = latest.get(camera_id) or {}
    people_count = doc.get("people_count")
    entry = {
        "name": name,
        "camera_id": camera_id,
        "timestamp": _iso(doc.get("timestamp")),
        "people_count": people_count,
    }
    if include_risk:
        entry["risk_level"] = doc.get("risk_level")
    if thresholds:
        entry["level"] = _level(people_count, thresholds)
    if capacity:
        entry["capacity"] = capacity
    return entry


def _flatten_group_cameras(groups: dict) -> list:
    return [c for camera_ids in groups.values() for c in camera_ids]


def _camera_name_map(groups: dict) -> dict:
    camera_names = {}
    for name, camera_ids in groups.items():
        for camera_id in camera_ids:
            camera_names.setdefault(camera_id, name)
    return camera_names


def _sum_group(camera_ids: list, latest: dict):
    counts = [
        latest[c]["people_count"] for c in camera_ids
        if c in latest and latest[c].get("people_count") is not None
    ]
    return sum(counts) if counts else None


def _group_entries(groups: dict, latest: dict, threshold_for_group, capacity_for_group) -> list:
    """Sum the latest people_count of each camera in a group (None if no camera has data)."""
    result = []
    for name, camera_ids in groups.items():
        people_count = _sum_group(camera_ids, latest)
        thresholds = threshold_for_group(name)
        result.append({
            "name": name,
            "camera_ids": camera_ids,
            "people_count": people_count,
            "level": _level(people_count, thresholds),
            "capacity": capacity_for_group(name),
        })
    return result


def _holding_area_entries(groups: dict, latest: dict, threshold_config: dict) -> dict:
    holding_areas = {
        name: [_camera_entry(c, latest, name=name) for c in camera_ids]
        for name, camera_ids in groups.items()
    }
    thresholds = threshold_config.get("levels", [])
    capacity = threshold_config.get("capacity")
    holding_areas["group_level_count"] = []
    for name, camera_ids in groups.items():
        people_count = _sum_group(camera_ids, latest)
        holding_areas["group_level_count"].append({
            "name": name,
            "camera_ids": camera_ids,
            "people_count": people_count,
            "capacity": capacity,
            "level": _level(people_count, thresholds),
        })
    return holding_areas


def _platform_threshold_config(name: str, thresholds_config: dict) -> dict:
    platform_config = thresholds_config.get("platforms", {})
    main_config = platform_config.get("main", {})
    normalized_name = name.replace(" ", "")
    normalized_main_names = {main_name.replace(" ", "") for main_name in main_config.get("names", [])}
    if normalized_name in normalized_main_names:
        return main_config
    return platform_config.get("island", {})


async def get_live_summary() -> dict:
    config = load_camera_config()
    platform_groups = config.get("platforms", {})
    fob_groups = config.get("fobs", {})
    booking_groups = config.get("booking_office", {})
    holding_groups = config.get("holding_areas", {})
    thresholds_config = config.get("thresholds", {})
    booking_thresholds = thresholds_config.get("booking_office", {})

    platform_cams = _flatten_group_cameras(platform_groups)
    fob_cams = _flatten_group_cameras(fob_groups)
    booking_cams = _flatten_group_cameras(booking_groups)
    holding_cams = _flatten_group_cameras(holding_groups)
    platform_camera_names = _camera_name_map(platform_groups)
    fob_camera_names = _camera_name_map(fob_groups)
    booking_camera_names = _camera_name_map(booking_groups)

    latest = await get_latest_by_camera(platform_cams + fob_cams + booking_cams + holding_cams)

    return {
        "platforms": {
            "cameras": [
                _camera_entry(
                    c,
                    latest,
                    name=platform_camera_names.get(c),
                    include_risk=True,
                )
                for c in platform_cams
            ],
            "group_level_count": _group_entries(
                platform_groups,
                latest,
                lambda name: _platform_threshold_config(name, thresholds_config).get("levels", []),
                lambda name: _platform_threshold_config(name, thresholds_config).get("capacity"),
            ),
        },
        "fobs": {
            "cameras": [
                _camera_entry(c, latest, name=fob_camera_names.get(c))
                for c in fob_cams
            ],
            "group_level_count": _group_entries(
                fob_groups,
                latest,
                lambda name: thresholds_config.get("fobs", {}).get(name, {}).get("levels", []),
                lambda name: thresholds_config.get("fobs", {}).get(name, {}).get("capacity"),
            ),
        },
        "booking_office": {
            "cameras": [
                _camera_entry(
                    c,
                    latest,
                    name=booking_camera_names.get(c),
                    thresholds=booking_thresholds.get("levels", []),
                    capacity=booking_thresholds.get("capacity"),
                )
                for c in booking_cams
            ],
            "group_level_count": _group_entries(
                booking_groups,
                latest,
                lambda name: booking_thresholds.get("levels", []),
                lambda name: booking_thresholds.get("capacity"),
            ),
        },
        "holding_areas": _holding_area_entries(
            holding_groups,
            latest,
            thresholds_config.get("holding_areas", {}),
        ),
    }


@router.get("/live-summary", responses={503: {"description": ERR_DATABASE_NOT_AVAILABLE}})
async def live_summary():
    """
    Latest people count per platform, FOB and booking office camera,
    plus platform-wise and FOB-wise totals (sum of cameras in each group).
    """
    if MongoDB.database is None:
        raise HTTPException(503, ERR_DATABASE_NOT_AVAILABLE)
    return await get_live_summary()