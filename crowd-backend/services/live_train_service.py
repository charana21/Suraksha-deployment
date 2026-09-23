"""
Live Train Status Service
Integrates with RapidAPI to fetch real-time train status (delay, platform, actual times).
Designed for token conservation: fetches hourly for trains in 1-hour window only.
"""
from jose.jwt import UTC
import aiohttp
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from db.mongodb import MongoDB
from config.config import get_settings
from services.live_refresh_toggle_service import LiveTrainRefreshToggleService
from services.whatsapp_alert_service import WhatsAppNotificationService
from utils.logging_config import get_logger

logger = get_logger(__name__)


class LiveTrainService:
    """Service for fetching and managing live train status from RapidAPI"""

    @staticmethod
    def _get_current_fetch_cycle() -> str:
        """
        Get the current hourly fetch cycle identifier.
        Format: '2026-01-09T14:00' (truncated to hour)
        """
        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
        return now.strftime("%Y-%m-%dT%H:00")

    @staticmethod
    def _parse_delay_status(delay_status: Optional[str]) -> int:
        """
        Parse delay string from API into minutes.

        Examples:
        - "Delay 16m" -> 16
        - "Delay 1h 30m" -> 90
        - "On Time" -> 0
        - "Early 5m" -> -5
        - "" or None -> 0
        """
        if not delay_status:
            return 0

        # Bound the input length before regex matching: this is untrusted
        # external API data, and capping it puts a hard ceiling on worst-case
        # regex work regardless of the pattern used (defense in depth against
        # ReDoS/ Sonar python:S5852).
        delay_str = delay_status.strip().lower()[:64]

        if "on time" in delay_str or delay_str == "":
            return 0

        # Check for early
        is_early = "early" in delay_str

        total_minutes = 0

        # Extract hours: "1h", "2 h", etc. Quantifiers are bounded (no
        # unbounded \d+\s* runs on untrusted input) so matching stays linear.
        hour_match = re.search(r'(\d{1,3})\s{0,3}h', delay_str)
        if hour_match:
            total_minutes += int(hour_match.group(1)) * 60

        # Extract minutes: "16m", "30 m", "16 min", etc.
        min_match = re.search(r'(\d{1,3})\s{0,3}m', delay_str)
        if min_match:
            total_minutes += int(min_match.group(1))

        # If no pattern matched but has digits, try to extract just numbers
        if total_minutes == 0:
            digits = re.findall(r'\d{1,3}', delay_str)
            if digits:
                total_minutes = int(digits[0])

        return -total_minutes if is_early else total_minutes

    @staticmethod
    def _determine_train_status(
        delay_minutes: int,
        actual_arrival: Optional[str],
        actual_departure: Optional[str],
        has_arrived: bool = False,
        has_departed: bool = False
    ) -> str:
    
        """
        Determine train status based on delay and arrival/departure info.

        Returns: ON_TIME, DELAYED, ARRIVED, DEPARTED, SCHEDULED
        """
        if has_departed:
            return "DEPARTED"
        if has_arrived:
            return "ARRIVED"
        if delay_minutes == 0:
            return "ON_TIME"
        if delay_minutes != 0:
            return "DELAYED"
        return "SCHEDULED"

    @staticmethod
    def _first_nonempty_field(doc: Dict[str, Any], *keys: str) -> str:
        """Return the first non-empty stripped value among the given keys."""
        for key in keys:
            value = doc.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _station_label(station: Dict[str, Any]) -> str:
        return str(station.get("name") or station.get("code") or "").strip().rstrip("~")

    @staticmethod
    def _resolve_route_endpoints(train_doc: Dict[str, Any], api_data: Dict[str, Any]) -> tuple[str, str]:
        """Resolve route source/destination with schedule data first, API payload fallback."""
        source = LiveTrainService._first_nonempty_field(train_doc, "source", "src", "source_station")
        destination = LiveTrainService._first_nonempty_field(
            train_doc, "destination", "dstn", "destination_station"
        )

        if source and destination:
            return source, destination

        stations = ((api_data or {}).get("api_payload") or {}).get("data", {}).get("stations", [])
        if isinstance(stations, list) and stations:
            if not source:
                source = LiveTrainService._station_label(stations[0] or {})
            if not destination:
                destination = LiveTrainService._station_label(stations[-1] or {})

        return source or "N/A", destination or "N/A"

    @staticmethod
    def _platform_alert_type(old_platform: str, new_platform: str) -> Optional[str]:
        """Classify platform event for alerting."""
        has_old = WhatsAppNotificationService._is_meaningful_platform(old_platform)
        has_new = WhatsAppNotificationService._is_meaningful_platform(new_platform)
        if has_new and not has_old:
            return "platform_assigned"
        if has_new and has_old and old_platform != new_platform:
            return "platform_change"
        if has_new and has_old and old_platform == new_platform:
            return None
        return None

    @staticmethod
    def _build_platform_alert_key(
        train_number: str,
        schedule_day: datetime,
        station_code: str,
        alert_type: str,
        old_platform: str,
        new_platform: str,
    ) -> str:
        schedule_date_str = schedule_day.strftime("%Y-%m-%d")
        return (
            f"{train_number}|{schedule_date_str}|{station_code}|{alert_type}|"
            f"{old_platform or '-'}|{new_platform or '-'}"
        )

    @staticmethod
    async def _is_platform_alert_already_recorded(alert_key: str, fetch_cycle: str) -> bool:
        if MongoDB.database is None:
            return False
        existing = await MongoDB.database.live_train_alerts.find_one(
            {
                "alert_key": alert_key,
                "alert-type": "platform",
                "sent": True,
            },
            {"_id": 1},
        )
        return bool(existing)

    @staticmethod
    async def _record_platform_alert(
        *,
        alert_key: str,
        alert_type: str,
        train_number: str,
        schedule_day: datetime,
        station_code: str,
        station_name: str,
        train_name: str,
        old_platform: str,
        new_platform: str,
        sent: bool,
        route_source: str,
        route_destination: str,
        schedule_datetime: str,
        total_footfall: str,
        fetch_cycle: str,
    ) -> None:
        if MongoDB.database is None:
            return

        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
        doc = {
            "alert_key": alert_key,
            "alert-type": "platform",
            "alert_type": alert_type,
            "train_number": train_number,
            "schedule_date": schedule_day,
            "station_code": station_code,
            "station_name": station_name,
            "train_name": train_name,
            "old_platform": old_platform,
            "new_platform": new_platform,
            "route_source": route_source,
            "route_destination": route_destination,
            "schedule_datetime": schedule_datetime,
            "total_footfall": total_footfall,
            "sent": bool(sent),
            "fetch_cycle": fetch_cycle,
            "updated_at": now,
        }
        await MongoDB.database.live_train_alerts.update_one(
            {"alert_key": alert_key},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    @staticmethod
    def _normalize_train_number(train_number: str) -> str:
        """Sanitize train number (strip trailing '.0' from float conversion, zero-pad to 5 digits)."""
        if not train_number:
            return train_number
        train_number = str(train_number).split(".")[0].strip()
        if len(train_number) == 4:
            train_number = f"0{train_number}"
        return train_number

    @staticmethod
    def _has_api_error(data: Dict[str, Any]) -> bool:
        # RapidAPI response can have 'success': True OR 'status': 'success'
        return not data.get("success", False) and data.get("status") != "success"

    @staticmethod
    def _find_station(stations: List[Dict[str, Any]], station_code_normalized: str) -> Optional[Dict[str, Any]]:
        for station in stations:
            api_station_code = str(station.get("code") or "").strip().upper()
            if api_station_code == station_code_normalized:
                return station
        return None

    @staticmethod
    def _build_station_result(
        train_number: str, station_code: str, found_station: Dict[str, Any], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        delay_status = found_station.get("delay_status", "")
        delay_minutes = LiveTrainService._parse_delay_status(delay_status)

        arr_actual = found_station.get("arrival_actual", "")
        dep_actual = found_station.get("departure_actual", "")

        current_status = LiveTrainService._determine_train_status(
            delay_minutes,
            arr_actual,
            dep_actual,
            found_station.get("has_arrived", False),
            found_station.get("has_departed", False)
        )

        return {
            "train_number": train_number,
            "station_code": station_code,
            "platform": found_station.get("platform", ""),
            "platform_number": found_station.get("platform", ""),
            "actual_arrival": arr_actual if arr_actual else None,
            "actual_departure": dep_actual if dep_actual else None,
            "delay_minutes": delay_minutes,
            "delay_status": delay_status,
            "current_status": current_status,
            "is_terminal_status": current_status in ["ARRIVED", "DEPARTED"],
            "api_response_raw": found_station,
            "api_payload": data
        }

    @staticmethod
    async def _request_live_train_data(
        url: str, params: Dict[str, str], headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status != 200:
                    print(f"[LiveTrain] HTTP {response.status} for {params.get('trainnumber')}")
                    return None
                return await response.json()

    @staticmethod
    async def fetch_train_status(train_number: str, initial_start_day: int = 0) -> Optional[Dict[str, Any]]:
        """
        Fetch live train status from RapidAPI.
        Retries with incremented start_day (up to +2) if initial fetch fails,
        to handle trains that started on previous days.

        Args:
            train_number: Train number (e.g., '17646')
            initial_start_day: Calculated days offset (0 = today)

        Returns:
            Dict with parsed station data for configured station, or None if failed
        """
        settings = get_settings()
        train_number = LiveTrainService._normalize_train_number(train_number)

        if not settings.live_train_api_enabled or not settings.live_train_api_key:
            return None

        url = f"https://{settings.live_train_api_host}/api/LiveTrainApi/"
        headers = {
            "X-Rapidapi-Key": settings.live_train_api_key,
            "X-Rapidapi-Host": settings.live_train_api_host
        }

        # Call API (Single attempt as requested)
        params = {
            "trainnumber": train_number,
            "start_day": str(initial_start_day)
        }

        try:
            data = await LiveTrainService._request_live_train_data(url, params, headers)
            if data is None:
                return None

            if LiveTrainService._has_api_error(data):
                msg = data.get('message') or data.get('msg') or data.get('error') or "Unknown"
                print(f"[LiveTrain] API Fail {train_number}: {msg} | Raw: {str(data)[:200]}")
                return None

            station_code = settings.live_train_station_code
            station_code_normalized = str(station_code or "").strip().upper()
            stations = data.get("data", {}).get("stations", [])

            found_station = LiveTrainService._find_station(stations, station_code_normalized)
            if not found_station:
                print(f"[LiveTrain] Station {station_code} not in route for {train_number}")
                return None

            return LiveTrainService._build_station_result(train_number, station_code, found_station, data)

        except Exception:
            logger.exception(f"[LiveTrain] Error {train_number}")
            return None



    @staticmethod
    async def get_trains_to_fetch(window_hours: float = 1.0) -> List[Dict]:
        """
        Get list of trains that need live status fetching.

        Criteria:
        1. Scheduled to arrive/depart within window_hours from now
        2. Not already in terminal status (ARRIVED/DEPARTED)

        Args:
            window_hours: Lookahead window (default 1 hour)

        Returns:
            List of train schedule documents to fetch
        """
        if MongoDB.database is None:
            return []

        settings = get_settings()

        # Use IST for scheduling logic as DB times seem to require IST comparison
        # We use naive datetime for IST since DB stores naive IST
        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
        window_end = now + timedelta(hours=window_hours)

        # Get trains scheduled in the window (from train_schedules)
        arriving = await MongoDB.database.train_schedules.find({
            "arrival_time": {"$gte": now, "$lte": window_end}
        }).to_list(length=100)
        departing = await MongoDB.database.train_schedules.find({
            "departure_time": {"$gte": now, "$lte": window_end}
        }).to_list(length=100)

        trains_map = LiveTrainService._dedupe_trains_by_schedule(arriving + departing)

        trains_to_fetch = []
        for train in trains_map.values():
            existing = await MongoDB.database.train_live_status.find_one({
                "train_number": train["train_number"],
                "schedule_date": train["schedule_date"],
                "station_code": settings.live_train_station_code
            })

            if not LiveTrainService._is_recently_fetched(existing, train):
                trains_to_fetch.append(train)

        print(f"[LiveTrain] Trains to fetch after filtering: {len(trains_to_fetch)}")

        return trains_to_fetch

    @staticmethod
    def _dedupe_trains_by_schedule(trains: List[Dict]) -> Dict[str, Dict]:
        """Combine and deduplicate by train_number + schedule_date."""
        trains_map: Dict[str, Dict] = {}
        for train in trains:
            key = f"{train['train_number']}_{train['schedule_date'].strftime('%Y-%m-%d')}"
            trains_map.setdefault(key, train)
        return trains_map

    @staticmethod
    def _is_recently_fetched(existing: Optional[Dict], train: Dict) -> bool:
        """Check if an existing live-status record means this train can be skipped this cycle."""
        if not existing:
            return False

        if existing.get("is_terminal_status", False):
            return True

        last_fetched = existing.get("last_fetched_at")
        if not last_fetched:
            return False

        now_ist = datetime.now(UTC) + timedelta(hours=5, minutes=30)
        arrival_time = train.get("arrival_time") or train.get("departure_time")
        if arrival_time and arrival_time.tzinfo is None:
            mins_to_event = (arrival_time - now_ist.replace(tzinfo=None)).total_seconds() / 60
        else:
            mins_to_event = (arrival_time - now_ist).total_seconds() / 60 if arrival_time else 0
        if last_fetched.tzinfo is None:
            seconds_since_fetch = (now_ist.replace(tzinfo=None) - last_fetched).total_seconds()
        else:
            seconds_since_fetch = (now_ist - last_fetched).total_seconds()

        # Trains > 1 hour away: only refetch if data is older than 45 mins.
        # Trains < 1 hour away: only refetch if data is older than 20 mins.
        stale_after_seconds = 2700 if mins_to_event > 60 else 1200
        return seconds_since_fetch < stale_after_seconds

    @staticmethod
    async def update_live_status(
        train_number: str,
        schedule_date: datetime,
        api_data: Dict[str, Any]
    ) -> None:
        """
        Update or insert live status for a train.

        Args:
            train_number: Train number
            schedule_date: Schedule date
            api_data: Parsed API response data
        """
        if MongoDB.database is None:
            return

        settings = get_settings()
        current_cycle = LiveTrainService._get_current_fetch_cycle()

        # Normalize schedule_date to midnight
        schedule_date_normalized = schedule_date.replace(hour=0, minute=0, second=0, microsecond=0)

        doc = {
            "train_number": train_number,
            "schedule_date": schedule_date_normalized,
            "station_code": settings.live_train_station_code,
            "delay_minutes": api_data.get("delay_minutes", 0),
            "platform_number": api_data.get("platform_number"),
            "actual_arrival": api_data.get("actual_arrival"),
            "actual_departure": api_data.get("actual_departure"),
            "current_status": api_data.get("current_status", "SCHEDULED"),
            "delay_status": api_data.get("delay_status"),
            "last_fetched_at": datetime.now(UTC) + timedelta(hours=5, minutes=30),
            "api_response_raw": api_data.get("api_response_raw"),
            "fetch_cycle": current_cycle,
            "is_terminal_status": api_data.get("is_terminal_status", False)
        }

        await MongoDB.database.train_live_status.update_one(
            {
                "train_number": train_number,
                "schedule_date": schedule_date_normalized,
                "station_code": settings.live_train_station_code
            },
            {"$set": doc},
            upsert=True
        )

    @staticmethod
    async def get_live_status(
        train_number: str,
        schedule_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached live status for a train.

        Args:
            train_number: Train number
            schedule_date: Schedule date

        Returns:
            Live status document or None
        """
        if MongoDB.database is None:
            return None

        settings = get_settings()
        schedule_date_normalized = schedule_date.replace(hour=0, minute=0, second=0, microsecond=0)

        doc = await MongoDB.database.train_live_status.find_one({
            "train_number": train_number,
            "schedule_date": schedule_date_normalized,
            "station_code": settings.live_train_station_code
        })

        if doc:
            # Remove MongoDB _id for response
            doc.pop("_id", None)

        return doc

    @staticmethod
    async def get_recent_history(
        days: int = 10,
        train_number: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get train_live_status records for a date range, including
        actual_arrival and actual_departure.

        Args:
            days: Number of days to look back from today (used only if
                  start_date/end_date are not provided; default: 10)
            train_number: Optional filter for a specific train
            start_date: Optional explicit range start (overrides `days`)
            end_date: Optional explicit range end (defaults to start_date if
                      start_date is given but end_date is not)

        Returns:
            list: train_live_status documents, newest schedule_date first
        """
        if MongoDB.database is None:
            return []

        today = (datetime.now(UTC) + timedelta(hours=5, minutes=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        if start_date is not None:
            range_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            range_end = (end_date or start_date).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            range_end = today
            range_start = today - timedelta(days=days - 1)

        query: Dict[str, Any] = {
            "schedule_date": {"$gte": range_start, "$lte": range_end}
        }
        if train_number:
            query["train_number"] = train_number

        docs = await MongoDB.database.train_live_status.find(query).sort(
            [("schedule_date", -1), ("train_number", 1)]
        ).to_list(length=None)

        for doc in docs:
            doc["_id"] = str(doc["_id"])
            if doc.get("schedule_date"):
                doc["schedule_date"] = doc["schedule_date"].isoformat()
            if doc.get("last_fetched_at"):
                doc["last_fetched_at"] = doc["last_fetched_at"].isoformat()

        return docs

    @staticmethod
    def _record_failed_train(stats: Dict[str, Any], train_number: Any, schedule_date_str: str, reason: str, settings) -> None:
        if len(stats["failed_trains"]) < 25:
            stats["failed_trains"].append({
                "train_number": str(train_number),
                "schedule_date": schedule_date_str,
                "reason": reason,
                "station_code": settings.live_train_station_code,
            })

    @staticmethod
    def _classify_platform_alert_type(has_old_platform: bool, old_platform_str: str, new_platform_str: str) -> str:
        # Label used for logging and DB records (does not affect which template is sent)
        if has_old_platform and old_platform_str != new_platform_str:
            return "platform_change"
        if not has_old_platform:
            return "platform_assigned"
        return "platform_confirmed"  # same platform confirmed again

    @staticmethod
    def _format_schedule_datetime(train: Dict[str, Any], schedule_day: datetime) -> str:
        arr_time = train.get("arrival_time")
        dep_time = train.get("departure_time")
        schedule_time = arr_time or dep_time
        schedule_date_str = schedule_day.strftime("%Y-%m-%d")
        schedule_time_str = schedule_time.strftime("%H:%M") if schedule_time else ""
        if schedule_time_str:
            return f"{schedule_date_str} {schedule_time_str}".strip()
        return schedule_date_str

    @staticmethod
    async def _should_send_platform_alert(
        alert_key: str, current_cycle: str, stats: Dict[str, Any], log_context: Dict[str, Any]
    ) -> bool:
        # Dedup key: one WhatsApp alert per (train, date, station, platform_number).
        # If the platform number changes, the key changes → a new alert fires.
        # If the same platform is returned again in the next cycle → key exists → skip.
        already_recorded = await LiveTrainService._is_platform_alert_already_recorded(
            alert_key=alert_key,
            fetch_cycle=current_cycle,
        )
        if already_recorded:
            stats["platform_alert_skipped_duplicate_cycle"] += 1
            print("[WhatsApp] Platform alert skipped (same platform already sent)", log_context)
            return False
        return True

    @staticmethod
    async def _dispatch_platform_alert(
        *,
        train: Dict[str, Any],
        train_number: Any,
        schedule_day: datetime,
        api_data: Dict[str, Any],
        alert_key: str,
        platform_alert_type: str,
        old_platform_str: str,
        new_platform_str: str,
        settings,
        current_cycle: str,
        stats: Dict[str, Any],
    ) -> None:
        from modules.users import UsersManager

        schedule_datetime = LiveTrainService._format_schedule_datetime(train, schedule_day)
        route_source, route_destination = LiveTrainService._resolve_route_endpoints(train, api_data)

        # Send only to viewer users subscribed to the platform alert service.
        user_recipients = await UsersManager.get_whatsapp_numbers_for_services(
            ["msg91_platform_assigned_template_id"]
        )
        print(f"[WhatsApp] User-service recipients for {train_number}: {user_recipients}")

        recipients = list(
            dict.fromkeys(
                WhatsAppNotificationService._normalize_whatsapp_numbers(user_recipients or [])
            )
        )

        if not recipients:
            print(
                "[WhatsApp] Platform alert skipped: no sendAlerts=True viewer users "
                "with msg91_platform_assigned_template_id service"
            )

        total_footfall = str(train.get("total_passengers") or "").strip() or "N/A"
        train_name = str(train.get("train_name") or "").strip()
        station_name = str(settings.live_train_station_name or settings.live_train_station_code)

        print(
            "[WhatsApp] Platform alert payload",
            {
                "alert_type": platform_alert_type,
                "alert_key": alert_key,
                "train_number": train_number,
                "train_name": train_name,
                "station_name": station_name,
                "platform_number": new_platform_str,
                "old_platform": old_platform_str,
                "route_source": route_source,
                "route_destination": route_destination,
                "schedule_datetime": schedule_datetime,
                "total_footfall": total_footfall,
                "recipients": recipients,
            },
        )

        alert_sent = False
        if recipients:
            alert_sent = await asyncio.to_thread(
                WhatsAppNotificationService.send_train_alert,
                train_number=train_number,
                train_name=train_name,
                station_name=station_name,
                platform_number=new_platform_str,
                old_platform=old_platform_str,
                route_source=route_source,
                route_destination=route_destination,
                schedule_datetime=schedule_datetime,
                total_footfall=total_footfall,
                recipients=recipients,
                expected_arrival=api_data.get("actual_arrival") or "",
                expected_departure=api_data.get("actual_departure") or "",
                delay_minutes=int(api_data.get("delay_minutes", 0)),
            )

        print(
            "[WhatsApp] Platform alert send result",
            {
                "alert_type": platform_alert_type,
                "alert_key": alert_key,
                "train_number": train_number,
                "platform_number": new_platform_str,
                "sent": bool(alert_sent),
                "recipients": recipients,
            },
        )
        stats["platform_alert_attempted"] += 1
        if alert_sent:
            stats["platform_alert_sent"] += 1
        else:
            stats["platform_alert_send_failed"] += 1

        await LiveTrainService._record_platform_alert(
            alert_key=alert_key,
            alert_type=str(platform_alert_type),
            train_number=str(train_number),
            schedule_day=schedule_day,
            station_code=str(settings.live_train_station_code),
            station_name=station_name,
            train_name=train_name,
            old_platform=old_platform_str,
            new_platform=new_platform_str,
            sent=bool(alert_sent),
            route_source=route_source,
            route_destination=route_destination,
            schedule_datetime=schedule_datetime,
            total_footfall=total_footfall,
            fetch_cycle=current_cycle,
        )

    @staticmethod
    async def _process_train_fetch(
        train: Dict[str, Any], settings, current_cycle: str, stats: Dict[str, Any]
    ) -> None:
        from services.train_data_service import TrainDataService

        train_number = train["train_number"]
        schedule_date = train["schedule_date"]

        # Calculate start_day for API
        today = (datetime.now(UTC) + timedelta(hours=5, minutes=30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        schedule_day = schedule_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if schedule_day.tzinfo is None:
            start_day = max(0, (today.replace(tzinfo=None) - schedule_day).days)
        else:
            start_day = max(0, (today - schedule_day).days)

        api_data = await LiveTrainService.fetch_train_status(train_number, start_day)

        if not api_data:
            stats["failed"] += 1
            stats["failed_no_api_data"] += 1
            LiveTrainService._record_failed_train(
                stats, train_number, schedule_day.strftime("%Y-%m-%d"), "no_api_data_for_station", settings
            )
            return

        # Get existing record BEFORE update (needed for "platform assigned" detection)
        existing = await MongoDB.database.train_live_status.find_one({
            "train_number": train_number,
            "schedule_date": schedule_day,
            "station_code": settings.live_train_station_code
        })

        old_platform_str = str((existing or {}).get("platform_number") or "").strip()
        new_platform_str = str(api_data.get("platform_number") or "").strip()
        has_old_platform = WhatsAppNotificationService._is_meaningful_platform(old_platform_str)
        has_new_platform = WhatsAppNotificationService._is_meaningful_platform(new_platform_str)

        # ── Send WhatsApp alert whenever API returns a train with a known platform ──
        # This matches the mobile-app announcement logic:
        #   Mobile announcement  → fires for ANY train that has data in train_data
        #   WhatsApp alert       → fires for ANY train that has a platform in the API response
        # Previously this only fired on platform CHANGE, causing the mismatch.
        should_send_platform_alert = has_new_platform
        platform_alert_type = LiveTrainService._classify_platform_alert_type(
            has_old_platform, old_platform_str, new_platform_str
        )

        if should_send_platform_alert:
            alert_key = (
                f"{train_number}|{schedule_day.strftime('%Y-%m-%d')}|"
                f"{settings.live_train_station_code}|platform_alert|{new_platform_str}"
            )
            should_send_platform_alert = await LiveTrainService._should_send_platform_alert(
                alert_key,
                current_cycle,
                stats,
                {
                    "train_number": train_number,
                    "alert_type": platform_alert_type,
                    "alert_key": alert_key,
                    "old_platform": old_platform_str,
                    "platform_number": new_platform_str,
                },
            )

        if should_send_platform_alert:
            await LiveTrainService._dispatch_platform_alert(
                train=train,
                train_number=train_number,
                schedule_day=schedule_day,
                api_data=api_data,
                alert_key=alert_key,
                platform_alert_type=platform_alert_type,
                old_platform_str=old_platform_str,
                new_platform_str=new_platform_str,
                settings=settings,
                current_cycle=current_cycle,
                stats=stats,
            )
        else:
            # has_new_platform is False — RapidAPI returned no platform for this train
            stats["platform_alert_skipped_no_platform"] += 1
            print(
                "[WhatsApp] Platform alert skipped (no platform in RapidAPI response)",
                {
                    "train_number": train_number,
                    "platform_number": new_platform_str,
                    "station_code": settings.live_train_station_code,
                },
            )

        # Update DB after alert logic
        await LiveTrainService.update_live_status(train_number, schedule_date, api_data)

        # Persist full RapidAPI payload in train_data collection in the same cycle
        full_payload = api_data.get("api_payload")
        if isinstance(full_payload, dict) and full_payload:
            await TrainDataService.upsert_full_payload(
                train_number=train_number,
                schedule_date=schedule_date,
                station_code=settings.live_train_station_code,
                api_payload=full_payload,
            )

        stats["fetched"] += 1

    @staticmethod
    async def run_hourly_fetch_cycle() -> dict:
        settings = get_settings()

        toggle_enabled = await LiveTrainRefreshToggleService.is_live_refresh_enabled()
        if not toggle_enabled:
            return {
                "fetched": 0,
                "failed": 0,
                "skipped": 0,
                "toggle_disabled": True,
            }

        if not settings.live_train_api_enabled:
            return {"fetched": 0, "failed": 0, "skipped": 0}

        stats = {
            "fetched": 0,
            "failed": 0,
            "skipped": 0,
            "failed_no_api_data": 0,
            "failed_exception": 0,
            "failed_trains": [],
            "platform_alert_attempted": 0,
            "platform_alert_sent": 0,
            "platform_alert_send_failed": 0,
            "platform_alert_skipped_duplicate_cycle": 0,
            "platform_alert_skipped_no_platform": 0,
        }
        current_cycle = LiveTrainService._get_current_fetch_cycle()

        print(f"[LiveTrain] Starting fetch cycle: {current_cycle}")

        trains = await LiveTrainService.get_trains_to_fetch(
            window_hours=settings.live_train_window_hours
        )

        for train in trains:
            try:
                await LiveTrainService._process_train_fetch(train, settings, current_cycle, stats)
            except Exception as e:
                logger.exception(f"[LiveTrain] Error processing {train.get('train_number')}")
                stats["failed"] += 1
                stats["failed_exception"] += 1
                LiveTrainService._record_failed_train(
                    stats,
                    train.get("train_number"),
                    str(train.get("schedule_date")),
                    f"exception: {str(e)}",
                    settings,
                )

        logger.info(f"[LiveTrain] Fetch cycle complete: {stats}")
        return stats

    @staticmethod
    async def get_last_fetch_cycle() -> Optional[str]:
        """
        Get the timestamp of the most recent fetch cycle.

        Returns:
            Fetch cycle string or None
        """
        if MongoDB.database is None:
            return None

        settings = get_settings()

        # Find most recent live status entry
        doc = await MongoDB.database.train_live_status.find_one(
            {"station_code": settings.live_train_station_code},
            sort=[("last_fetched_at", -1)]
        )

        if doc:
            return doc.get("fetch_cycle")

        return None
