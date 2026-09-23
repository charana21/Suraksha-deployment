"""
Train schedule management service
Handles Excel parsing, database operations, and schedule queries
"""
import pandas as pd
from datetime import UTC, datetime, timedelta, time
from typing import Optional, List, Dict, Any, Tuple
from io import BytesIO
from db.mongodb import MongoDB
from services.live_refresh_toggle_service import LiveTrainRefreshToggleService
import logging
logger = logging.getLogger(__name__)

class TrainScheduleService:
    """Train schedule CRUD and Excel parsing operations"""

    @staticmethod
    def parse_railway_datetime(raw_value: Any) -> Tuple[Optional[datetime], Optional[Any]]:
        """
        Parse Railway Excel date/time format.

        Railway Excel format: "DD-MM-YYYY HH:MM" (in Arrv/Dep columns)
        Also handles:
        - Time only: "HH:MM" (needs date from context)
        - Empty/None for ORIGINATING/TERMINATING trains

        Returns: (date_only, datetime_or_time)
        """
        if pd.isna(raw_value) or raw_value is None or str(raw_value).strip() == "":
            return None, None

        raw_str = str(raw_value).strip()

        # Try full datetime format: "DD-MM-YYYY HH:MM" or variations
        for fmt in ["%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]:
            try:
                dt = datetime.strptime(raw_str, fmt)
                return dt.replace(hour=0, minute=0, second=0, microsecond=0), dt
            except ValueError:
                continue

        # Try time-only format: "HH:MM" (will need date from another column)
        for fmt in ["%H:%M", "%H:%M:%S"]:
            try:
                t = datetime.strptime(raw_str, fmt).time()
                return None, t
            except ValueError:
                continue

        # Try Excel serial date (if pandas read as float)
        if isinstance(raw_value, (int, float)):
            try:
                dt = pd.to_datetime(raw_value, unit='D', origin='1899-12-30')
                return dt.replace(hour=0, minute=0, second=0, microsecond=0), dt.to_pydatetime()
            except (ValueError, TypeError):
                pass

        # Try pandas Timestamp
        if isinstance(raw_value, pd.Timestamp):
            dt = raw_value.to_pydatetime()
            return dt.replace(hour=0, minute=0, second=0, microsecond=0), dt

        return None, None

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> Dict[str, str]:
        """
        Create a mapping from expected column names to actual column names.
        Handles case-insensitivity and common variations.
        """
        # Expected columns and their possible variations (lowercase)
        column_variants = {
            "train": ["train", "train no", "train_no", "trainno", "train number"],
            "train_name": ["train name", "train_name", "trainname", "name"],
            "type": ["type", "train type", "train_type"],
            "src": ["src", "source", "from", "origin"],
            "dstn": ["dstn", "dest", "destination", "to"],
            "train_event": ["train event", "train_event", "trainevent", "event"],
            "arrv": ["arrv", "arr", "arrival", "arrives", "arr time", "arrival time"],
            "dep": ["dep", "dept", "departure", "departs", "dep time", "departure time"],
            "boarding": ["boarding", "board", "boarding count"],
            "deboarding": ["deboarding", "deboard", "deboarding count", "alighting"],
            "total": ["total", "total count", "total passengers"],
            "uts": ["uts", "uts count", "uts passengers"],
        }

        # Create lowercase mapping of actual columns
        actual_cols_lower = {col.lower().strip(): col for col in df.columns}

        # Build mapping
        col_map = {}
        for expected, variants in column_variants.items():
            for variant in variants:
                if variant in actual_cols_lower:
                    col_map[expected] = actual_cols_lower[variant]
                    break

        return col_map

    @staticmethod
    async def parse_excel(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse Railway Excel file and return structured data.

        Args:
            file_content: Raw Excel file bytes
            filename: Original filename for logging

        Returns:
            Dict with parsed records, errors, dates_found
        """
        result = {
            "records": [],
            "errors": [],
            "dates_found": set()
        }

        try:
            # First, read a preview to find the header row
            # We read without header (header=None) to inspect rows
            df_preview = pd.read_excel(BytesIO(file_content), header=None, nrows=20)
            
            header_row_idx = 0
            
            # Define variants to look for (matching _normalize_columns)
            train_variants = ["train", "train no", "train_no", "trainno", "train number"]
            name_variants = ["train name", "train_name", "trainname", "name"]
            
            # Search for header row
            for idx, row in df_preview.iterrows():
                # Get row values as lowercased string list, handling NaNs
                row_values = [str(v).lower().strip() for v in row.values if pd.notna(v)]
                
                # Check for required column headers
                has_train = any(variant in row_values for variant in train_variants)
                has_name = any(variant in row_values for variant in name_variants)
                
                if has_train and has_name:
                    header_row_idx = idx
                    logger.info(f"[TrainSchedule] Detected header at row index {idx}")
                    break
            
            # Read full file with detected header
            df = pd.read_excel(BytesIO(file_content), header=header_row_idx)
            
        except Exception as e:
            result["errors"].append(f"Failed to read Excel: {str(e)}")
            return result

        # Normalize column names (strip whitespace and ensure string)
        df.columns = df.columns.astype(str).str.strip()

        # Get column mapping
        col_map = TrainScheduleService._normalize_columns(df)

        # Debug: log found columns
        logger.info(f"[TrainSchedule] Excel columns: {list(df.columns)}")
        logger.info(f"[TrainSchedule] Column mapping: {col_map}")

        # Validate required columns
        required = ["train", "train_name"]
        missing = [col for col in required if col not in col_map]
        if missing:
            result["errors"].append(f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
            return result

        for idx, row in df.iterrows():
            try:
                record = TrainScheduleService._parse_row(row, idx, filename, col_map)
                if record:
                    result["records"].append(record)
                    if record.get("schedule_date"):
                        result["dates_found"].add(record["schedule_date"].strftime("%Y-%m-%d"))
            except Exception as e:
                # Adjust error row index to account for header offset
                row_display_idx = idx + header_row_idx + 2
                result["errors"].append(f"Row {row_display_idx}: {str(e)}")

        result["dates_found"] = sorted(list(result["dates_found"]))
        return result

    @staticmethod
    def _get_col(row: pd.Series, col_map: Dict[str, str], key: str, default=""):
        """Get a row value using the column mapping, falling back to `default`"""
        if key not in col_map:
            return default
        val = row.get(col_map[key])
        return default if pd.isna(val) else val

    @staticmethod
    def _combine_schedule_time(schedule_date: datetime, value: Any) -> Optional[datetime]:
        if isinstance(value, time):
            return datetime.combine(schedule_date.date(), value)
        if isinstance(value, datetime):
            return value
        return None

    @staticmethod
    def _resolve_schedule_times(get_col) -> Tuple[datetime, Optional[datetime], Optional[datetime]]:
        """Parse arrival/departure columns into (schedule_date, arrival_dt, departure_dt)"""
        arr_date, arr_time = TrainScheduleService.parse_railway_datetime(get_col("arrv"))
        dep_date, dep_time = TrainScheduleService.parse_railway_datetime(get_col("dep"))

        # Determine schedule_date from whichever time field has it
        schedule_date = arr_date or dep_date
        if not schedule_date:
            # Fallback: use today's date if no date in data
            schedule_date = (datetime.now(UTC) + timedelta(hours=5, minutes=30)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Removed IST to UTC conversion. We now store strictly in IST (naive).
        arrival_dt = TrainScheduleService._combine_schedule_time(schedule_date, arr_time)
        departure_dt = TrainScheduleService._combine_schedule_time(schedule_date, dep_time)

        return schedule_date, arrival_dt, departure_dt

    @staticmethod
    def _infer_train_event(raw_event: str, arrival_dt: Optional[datetime], departure_dt: Optional[datetime]) -> str:
        if raw_event in ["ORIGINATING", "TERMINATING", "THROUGH"]:
            return raw_event
        if arrival_dt is None and departure_dt is not None:
            return "ORIGINATING"
        if arrival_dt is not None and departure_dt is None:
            return "TERMINATING"
        return "THROUGH"

    @staticmethod
    def _safe_int(val) -> int:
        if pd.isna(val) or val is None:
            return 0
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_row(row: pd.Series, row_idx: int, filename: str, col_map: Dict[str, str]) -> Optional[Dict]:
        """Parse single Excel row into schedule document"""
        def get_col(key: str, default=""):
            return TrainScheduleService._get_col(row, col_map, key, default)

        train_number = str(get_col("train", "")).strip()
        if not train_number or train_number == "nan":
            return None

        # Sanitize: Remove .0 if it was parsed as float
        train_number = train_number.split(".")[0]

        schedule_date, arrival_dt, departure_dt = TrainScheduleService._resolve_schedule_times(get_col)

        train_event_raw = str(get_col("train_event", "")).strip().upper()
        train_event_raw = TrainScheduleService._infer_train_event(train_event_raw, arrival_dt, departure_dt)

        safe_int = TrainScheduleService._safe_int

        # Build document
        return {
            "train_number": train_number,
            "train_name": str(get_col("train_name", "")).strip(),
            "train_type": str(get_col("type", "")).strip(),
            "schedule_date": schedule_date, # This is just the date component, can stay naive or match UTC date
            "source": str(get_col("src", "")).strip(),
            "destination": str(get_col("dstn", "")).strip(),
            "train_event": train_event_raw,
            "arrival_time": arrival_dt,
            "departure_time": departure_dt,
            "boarding_count": safe_int(get_col("boarding", 0)),
            "deboarding_count": safe_int(get_col("deboarding", 0)),
            "total_passengers": safe_int(get_col("total", 0)),
            "uts_passengers": safe_int(get_col("uts", 0)),
            "uploaded_at": datetime.now(UTC) + timedelta(hours=5, minutes=30),
            "source_file": filename,
            "arrival_hour": arrival_dt.hour if arrival_dt else None,
            "departure_hour": departure_dt.hour if departure_dt else None
        }

    @staticmethod
    async def upsert_schedules(records: List[Dict]) -> Dict[str, int]:
        """
        Insert or update train schedules with duplicate detection using Bulk Write.

        Duplicate key: (train_number, schedule_date, arrival_time, departure_time)

        Returns: {"inserted": N, "updated": N, "skipped": N}
        """
        if MongoDB.database is None:
            raise RuntimeError("MongoDB not connected")

        if not records:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        from pymongo import UpdateOne

        # Build bulk operations - single DB round-trip
        operations = []
        for record in records:
            filter_key = {
                "train_number": record["train_number"],
                "schedule_date": record["schedule_date"],
                "arrival_time": record["arrival_time"],
                "departure_time": record["departure_time"]
            }
            operations.append(UpdateOne(filter_key, {"$set": record}, upsert=True))

        # Execute all operations in one batch
        result = await MongoDB.database.train_schedules.bulk_write(operations, ordered=False)

        return {
            "inserted": result.upserted_count,
            "updated": result.modified_count,
            "skipped": result.matched_count - result.modified_count
        }

    @staticmethod
    async def get_upcoming_trains(window_hours: Optional[float] = None, include_live_status: bool = True) -> Dict[str, Any]:
        """
        Get trains arriving/departing within the specified time window.
        Strictly filters by scheduled time (Now to Now + Window).
        Optionally merges live status data from RapidAPI.

        Args:
            window_hours: Lookahead window (defaults to settings.live_train_window_hours)
            include_live_status: Whether to merge live status data (default True)

        Returns:
            Dict with "trains" list (combined arriving/departing with live status)
        """
        from services.live_train_service import LiveTrainService
        from config.config import get_settings

        settings = get_settings()
        if window_hours is None:
            window_hours = settings.live_train_window_hours

        if MongoDB.database is None:
            return {"trains": [], "total_count": 0, "live_data_enabled": False, "last_fetch_cycle": None}

        # Use IST for "now"
        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
        
        # Look forward only (Simple Logic)
        start_time = now
        arrival_start_time = now - timedelta(minutes=2)  # 2-min buffer for arrivals
        window_end = now + timedelta(hours=window_hours)

        # Query for arrivals in window
        arriving_cursor = MongoDB.database.train_schedules.find({
            "arrival_time": {"$gte": arrival_start_time, "$lte": window_end}
        }).sort("arrival_time", 1)

        arriving = await arriving_cursor.to_list(length=100)

        # Query for departures in window
        departing_cursor = MongoDB.database.train_schedules.find({
            "departure_time": {"$gte": start_time, "$lte": window_end}
        }).sort("departure_time", 1)

        departing = await departing_cursor.to_list(length=100)

        # Combine and deduplicate by train_number + schedule_date
        trains_map = {}
        for train in arriving:
            key = f"{train['train_number']}_{train['schedule_date'].strftime('%Y-%m-%d')}"
            if key not in trains_map:
                trains_map[key] = {"doc": train, "status": "arriving"}

        for train in departing:
            key = f"{train['train_number']}_{train['schedule_date'].strftime('%Y-%m-%d')}"
            if key not in trains_map:
                trains_map[key] = {"doc": train, "status": "departing"}

        # Determine if live refresh toggle is enabled
        toggle_enabled = await LiveTrainRefreshToggleService.is_live_refresh_enabled()
        live_status_included = include_live_status and toggle_enabled

        # Format all trains with live status
        trains_formatted = []
        for train_data in trains_map.values():
            doc = train_data["doc"]
            status = train_data["status"]

            # Get live status if enabled
            live_status = None
            if live_status_included:
                live_status = await LiveTrainService.get_live_status(
                    doc["train_number"],
                    doc["schedule_date"]
                )

            formatted = TrainScheduleService._format_train_item_with_live(doc, now, status, live_status)
            trains_formatted.append(formatted)

        # Sort by scheduled arrival/departure time
        # Helper to safely get parsing string
        def get_sort_time(x):
            return x.get("arrival_scheduled") or x.get("departure_scheduled") or "23:59"

        trains_formatted.sort(key=get_sort_time)

        # Get last fetch cycle
        last_fetch_cycle = await LiveTrainService.get_last_fetch_cycle() if live_status_included else None

        return {
            "trains": trains_formatted,
            "total_count": len(trains_formatted),
            "live_data_enabled": include_live_status,
            "live_refresh_enabled": toggle_enabled,
            "live_data_active": live_status_included,
            "last_fetch_cycle": last_fetch_cycle,
        }

    @staticmethod
    def _format_train_item(doc: Dict, now: datetime, status: str) -> Dict:
        """Format train document for API response (legacy format without live status)"""
        arr_time = doc.get("arrival_time")
        dep_time = doc.get("departure_time")

        minutes_until_arrival = None
        minutes_until_departure = None

        if arr_time:
            minutes_until_arrival = int((arr_time - now).total_seconds() / 60)
        if dep_time:
            minutes_until_departure = int((dep_time - now).total_seconds() / 60)

        return {
            "train_number": doc["train_number"], 
            "train_name": doc["train_name"],
            "source": doc.get("source", ""),
            "destination": doc.get("destination", ""),
            "schedule_date": doc.get("schedule_date").strftime("%Y-%m-%d") if doc.get("schedule_date") else None,
            "train_type": doc.get("train_type", ""),
            "source": doc.get("source", ""),
            "destination": doc.get("destination", ""),
            "train_event": doc.get("train_event", "THROUGH"),
            "arrival_time": arr_time.isoformat() if arr_time else None,
            "departure_time": dep_time.isoformat() if dep_time else None,
            "arrival_display": arr_time.strftime("%H:%M") if arr_time else None,
            "departure_display": dep_time.strftime("%H:%M") if dep_time else None,
            "minutes_until_arrival": minutes_until_arrival,
            "minutes_until_departure": minutes_until_departure,
            "boarding_count": doc.get("boarding_count", 0),
            "deboarding_count": doc.get("deboarding_count", 0),
            "total_passengers": doc.get("total_passengers", 0),
            "status": status
        }

    @staticmethod
    def _live_value(live_status: Optional[Dict], key: str, default=None):
        """Read a key from the live-status dict, or `default` when there's no live status"""
        return live_status.get(key, default) if live_status else default

    @staticmethod
    def _int_or_none(val) -> Optional[int]:
        return int(val) if val is not None else None

    @staticmethod
    def _str_or_none(val) -> Optional[str]:
        return str(val) if val else None

    @staticmethod
    def _format_train_item_with_live(doc: Dict, now: datetime, status: str, live_status: Optional[Dict]) -> Dict:
        """Format train document with live status merged for API response (User Specific Format)"""
        from config.config import get_settings
        from services.live_train_service import LiveTrainService

        settings = get_settings()

        arr_time = doc.get("arrival_time")
        dep_time = doc.get("departure_time")

        # DB Time is already IST (naive), so we use it directly for display
        arr_sched = arr_time.strftime("%H:%M") if arr_time else None
        dep_sched = dep_time.strftime("%H:%M") if dep_time else None

        # Data extraction
        live_raw = TrainScheduleService._live_value(live_status, "api_response_raw", {})

        # Determine values
        sequence = live_raw.get("serial") or live_raw.get("sequence")
        distance = live_raw.get("distance")

        # User requested fields
        station_code = settings.live_train_station_code
        station_name = settings.live_train_station_name or station_code

        # Actual Times
        arr_actual = TrainScheduleService._live_value(live_status, "actual_arrival")
        dep_actual = TrainScheduleService._live_value(live_status, "actual_departure")

        platform_scheduled = doc.get("platform")
        platform_live = TrainScheduleService._live_value(live_status, "platform_number")
        platform = platform_live or platform_scheduled

        delay_status = TrainScheduleService._live_value(live_status, "delay_status", "")
        delay_minutes = None
        if live_status and delay_status is not None:
            delay_minutes = LiveTrainService._parse_delay_status(delay_status)

        # is_current Logic
        is_current = live_raw.get("is_current", True)

        current_status = TrainScheduleService._live_value(live_status, "current_status", "SCHEDULED")

        return {
            "sequence": TrainScheduleService._int_or_none(sequence),
            "code": station_code,
            "name": station_name,
            "distance": TrainScheduleService._int_or_none(distance),
            "platform": TrainScheduleService._str_or_none(platform),
            "platform_scheduled": TrainScheduleService._str_or_none(platform_scheduled),
            "platform_live": TrainScheduleService._str_or_none(platform_live),
            "arrival_scheduled": arr_sched,
            "arrival_actual": arr_actual or arr_sched, # Fallback to scheduled if no actual
            "departure_scheduled": dep_sched,
            "departure_actual": dep_actual or dep_sched,
            "delay_status": delay_status,
            "delay_minutes": delay_minutes,
            "is_current": is_current,
            "current_status": current_status,

            # Keep basic ID fields for frontend keys
            "train_number": doc["train_number"],
            "train_name": doc["train_name"],

            # Passenger Counts (User requested total_passengers)
            "total_passengers": doc.get("total_passengers", 0),
            "boarding_count": doc.get("boarding_count", 0),
            "deboarding_count": doc.get("deboarding_count", 0)
        }

    @staticmethod
    async def get_schedules_by_date(date: datetime) -> List[Dict]:
        """Get all schedules for a specific date"""
        if MongoDB.database is None:
            return []

        target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)

        cursor = MongoDB.database.train_schedules.find({
            "schedule_date": target_date
        }).sort([("arrival_time", 1), ("departure_time", 1)])

        return await cursor.to_list(length=500)

    @staticmethod
    async def delete_schedules_by_date(date: datetime) -> int:
        """Delete all schedules for a specific date (for re-upload)"""
        if MongoDB.database is None:
            return 0

        target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        result = await MongoDB.database.train_schedules.delete_many({
            "schedule_date": target_date
        })
        return result.deleted_count

    @staticmethod
    async def get_available_dates() -> List[str]:
        """Get list of dates that have schedule data"""
        if MongoDB.database is None:
            return []

        pipeline = [
            {"$group": {"_id": "$schedule_date"}},
            {"$sort": {"_id": 1}}
        ]

        cursor = MongoDB.database.train_schedules.aggregate(pipeline)
        results = await cursor.to_list(length=100)

        return [r["_id"].strftime("%Y-%m-%d") for r in results if r["_id"]]
