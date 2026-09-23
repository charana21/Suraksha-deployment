"""
Train data persistence service.
Stores full RapidAPI payload in `train_data` collection.
"""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional
import re
from db.mongodb import MongoDB

class TrainDataService:
    """Persist full train API payload to train_data collection."""

    COLLECTION_NAME = "train_data"

    @staticmethod
    def _now_ist() -> datetime:
        return datetime.now(UTC) + timedelta(hours=5, minutes=30)

    @staticmethod
    def _normalize_schedule_date(schedule_date: datetime) -> datetime:
        return schedule_date.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _extract_platform(api_payload: Dict[str, Any], station_code: str) -> Optional[str]:
        data = (api_payload or {}).get("data") or {}
        stations = data.get("stations") or []
        for station in stations:
            if (station or {}).get("code") == station_code:
                platform = station.get("platform")
                return str(platform).strip() if platform else None
        return None

    @staticmethod
    def _extract_delay_status(api_payload: Dict[str, Any], station_code: str) -> Optional[str]:
        data = (api_payload or {}).get("data") or {}
        stations = data.get("stations") or []
        for station in stations:
            if (station or {}).get("code") == station_code:
                delay_status = station.get("delay_status")
                return str(delay_status).strip() if delay_status else None
        return None

    @staticmethod
    def _parse_delay_status(delay_status: Optional[str]) -> int:
        if not delay_status:
            return 0
        # Bound the input length before regex matching: this is untrusted
        # external API data, and capping it puts a hard ceiling on worst-case
        # regex work regardless of the pattern used (defense in depth against
        # ReDoS / Sonar python:S5852).
        delay_str = delay_status.strip().lower()[:64]
        if "on time" in delay_str or delay_str == "":
            return 0
        is_early = "early" in delay_str
        total_minutes = 0
        # Quantifiers are bounded (no unbounded \d+\s* runs on untrusted
        # input) so matching stays linear.
        hour_match = re.search(r"(\d{1,3})\s{0,3}h", delay_str)
        if hour_match:
            total_minutes += int(hour_match.group(1)) * 60
        min_match = re.search(r"(\d{1,3})\s{0,3}m", delay_str)
        if min_match:
            total_minutes += int(min_match.group(1))
        if total_minutes == 0:
            digits = re.findall(r"\d{1,3}", delay_str)
            if digits:
                total_minutes = int(digits[0])
        return -total_minutes if is_early else total_minutes

    @staticmethod
    async def get_record(
        train_number: str,
        schedule_date: datetime,
        station_code: str,
    ) -> Optional[Dict[str, Any]]:
        if MongoDB.database is None:
            return None
        schedule_day = TrainDataService._normalize_schedule_date(schedule_date)
        return await MongoDB.database[TrainDataService.COLLECTION_NAME].find_one({
            "train_number": train_number,
            "schedule_date": schedule_day,
            "station_code": station_code,
        })

    @staticmethod
    async def upsert_full_payload(
        train_number: str,
        schedule_date: datetime,
        station_code: str,
        api_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save full API payload to `train_data` collection."""
        if MongoDB.database is None:
            return {"saved": False}

        now_ist = TrainDataService._now_ist()
        schedule_day = TrainDataService._normalize_schedule_date(schedule_date)

        existing = await MongoDB.database[TrainDataService.COLLECTION_NAME].find_one({
            "train_number": train_number,
            "schedule_date": schedule_day,
            "station_code": station_code,
        })

        current_platform = TrainDataService._extract_platform(api_payload, station_code)
        current_delay_status = TrainDataService._extract_delay_status(api_payload, station_code)
        current_delay_minutes = TrainDataService._parse_delay_status(current_delay_status)

        previous_platform = None
        if existing:
            prior_current = existing.get("platform_number_live")
            if current_platform and prior_current and current_platform != prior_current:
                previous_platform = prior_current
            else:
                previous_platform = existing.get("previous_platform_number")

        previous_delay_minutes = None
        if existing:
            prior_delay = existing.get("delay_minutes", 0)
            if current_delay_minutes != prior_delay:
                previous_delay_minutes = prior_delay
            else:
                previous_delay_minutes = existing.get("previous_delay_minutes")

        doc = {
            "train_number": train_number,
            "schedule_date": schedule_day,
            "station_code": station_code,
            "api_payload": api_payload,
            "platform_number_live": current_platform,
            "previous_platform_number": previous_platform,
            "delay_status": current_delay_status,
            "delay_minutes": current_delay_minutes,
            "previous_delay_minutes": previous_delay_minutes,
            "last_fetched_at": now_ist,
            "updated_at": now_ist,
            "created_at": existing.get("created_at", now_ist) if existing else now_ist,
        }

        await MongoDB.database[TrainDataService.COLLECTION_NAME].update_one(
            {
                "train_number": train_number,
                "schedule_date": schedule_day,
                "station_code": station_code,
            },
            {"$set": doc},
            upsert=True,
        )

        return {"saved": True}
