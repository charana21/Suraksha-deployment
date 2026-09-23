"""
Footfall & Calendar Insights APIs with UTS & PRS Passenger Forecasting Integration

Data sources:
─────────────────────────────────────────────────────────────────────────────
• `forecasting_data`  → Primary source for upcoming month UTS & PRS predictions.
• `historical_data`   → Historical actuals (UTS Inward/Outward/Total, PRS Inward/Outward/Total).
• `calendar`          → Excel uploaded schedules & train boarding/deboarding counts.
• `special_trains`    → Lookup for special train passenger numbers.
• `train_schedules`   → Hourly distribution buckets.
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Body, HTTPException, Query, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from db.mongodb import MongoDB
from services.calendar_upload_service import CalendarUploadService
from services.forecasting.runner import ForecastingRunner
from services.forecasting.db_service import ForecastingDBService
from services.forecasting.data_loader import seed_historical_collection_if_empty
from utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

MONGO_MATCH = "$match"
MONGO_IFNULL = "$ifNull"
FIELD_TOTAL_PASSENGERS = "$total_passengers"

IST = timezone(timedelta(hours=5, minutes=30))
MONTH_META = [
    {"name": "January",   "short": "JAN"},
    {"name": "February",  "short": "FEB"},
    {"name": "March",     "short": "MAR"},
    {"name": "April",     "short": "APR"},
    {"name": "May",       "short": "MAY"},
    {"name": "June",      "short": "JUN"},
    {"name": "July",      "short": "JUL"},
    {"name": "August",    "short": "AUG"},
    {"name": "September", "short": "SEP"},
    {"name": "October",   "short": "OCT"},
    {"name": "November",  "short": "NOV"},
    {"name": "December",  "short": "DEC"},
]

HOURLY_BUCKETS = [
    {"label": "00:00 – 05:00", "start": 0,  "end": 5},
    {"label": "05:00 – 10:00", "start": 5,  "end": 10},
    {"label": "10:00 – 15:00", "start": 10, "end": 15},
    {"label": "15:00 – 20:00", "start": 15, "end": 20},
    {"label": "20:00 – 24:00", "start": 20, "end": 24},
]


class FootfallTickIn(BaseModel):
    pax_delta: int = 1
    special_trains: Optional[int] = None
    event_name: Optional[str] = None
    timestamp: Optional[datetime] = None


class ForecastRunRequest(BaseModel):
    skip_backtest: bool = True


def _now_ist() -> datetime:
    return datetime.now(IST)


def _date_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _month_shell() -> List[Dict[str, Any]]:
    return [
        {
            "name": m["name"],
            "short": m["short"],
            "totalPax": 0,
            "totalScheduledPax": 0,
            "totalSpecialPax": 0,
            "totalUtsPax": 0,
            "totalPrsPax": 0,
            "totalUtsPredicted": 0,
            "totalPrsPredicted": 0,
            "totalSpecialTrains": 0,
            "totalSpecialTrainsFootfall": 0,
            "days": [],
        }
        for m in MONTH_META
    ]


import math


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return default
        return int(round(val))
    except (TypeError, ValueError):
        return default


def _safe_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return int(round(val))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return default
    s = str(value).strip()
    if s.lower() in ("nan", "none", "null"):
        return default
    return s


def clean_nan_values(obj: Any) -> Any:
    """Recursively replaces NaN / Inf with None or safe types to ensure standard JSON compliance."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_nan_values(v) for v in obj]
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class FootfallInsightsService:

    # ── Index maintenance ─────────────────────────────────────────────────────

    @classmethod
    async def _safe_create_index(cls, collection, keys, name: str) -> None:
        from pymongo.errors import OperationFailure
        try:
            await collection.create_index(keys, name=name)
        except OperationFailure as exc:
            if exc.code in (85, 86):
                pass
            else:
                raise

    @classmethod
    async def ensure_indexes(cls) -> None:
        if MongoDB.database is None:
            return
        await cls._safe_create_index(
            MongoDB.database.forecasting_data,
            [("date", 1)],
            "idx_forecasting_data_date",
        )
        await cls._safe_create_index(
            MongoDB.database.historical_data,
            [("date", 1)],
            "idx_historical_data_date",
        )
        await cls._safe_create_index(
            MongoDB.database.calendar,
            [("schedule_date", 1)],
            "idx_calendar_schedule_date",
        )
        await cls._safe_create_index(
            MongoDB.database.train_schedules,
            [("schedule_date", 1)],
            "idx_train_schedules_schedule_date",
        )
        await cls._safe_create_index(
            MongoDB.database.train_schedules,
            [("train_number", 1)],
            "idx_train_schedules_train_number",
        )
        await cls._safe_create_index(
            MongoDB.database.special_trains,
            [("train_number", 1)],
            "idx_special_trains_train_number",
        )

    # ── Special train number lookup ───────────────────────────────────────────

    @classmethod
    async def _get_special_train_numbers(cls) -> Set[Any]:
        if MongoDB.database is None:
            raise HTTPException(status_code=503, detail="Database not available")

        docs = await MongoDB.database.special_trains.find(
            {}, {"train_number": 1, "_id": 0}
        ).to_list(length=None)

        return {doc["train_number"] for doc in docs if "train_number" in doc}

    @classmethod
    async def _get_special_trains_summary(cls) -> Dict[str, int]:
        if MongoDB.database is None:
            raise HTTPException(status_code=503, detail="Database not available")

        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "totalSpecialTrains": {"$sum": 1},
                    "totalSpecialPax": {
                        "$sum": {MONGO_IFNULL: [FIELD_TOTAL_PASSENGERS, 0]}
                    },
                }
            }
        ]

        result = await MongoDB.database.special_trains.aggregate(pipeline).to_list(length=1)

        if result:
            return {
                "totalSpecialTrains": result[0].get("totalSpecialTrains", 0),
                "totalSpecialPax": result[0].get("totalSpecialPax", 0),
            }

        return {
            "totalSpecialTrains": 0,
            "totalSpecialPax": 0,
        }

    @classmethod
    async def _get_special_trains_by_date(cls, year: Optional[int] = None) -> Dict[str, Any]:
        if MongoDB.database is None:
            return {}

        match_filter: Dict[str, Any] = {}
        if year is not None:
            year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
            year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            match_filter["schedule_date"] = {"$gte": year_start, "$lt": year_end}

        pipeline = [
            {MONGO_MATCH: match_filter} if match_filter else {MONGO_MATCH: {}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$schedule_date",
                            "timezone": "UTC",
                        }
                    },
                    "train_count": {"$sum": 1},
                    "total_passengers": {"$sum": {MONGO_IFNULL: [FIELD_TOTAL_PASSENGERS, 0]}},
                    "train_numbers": {"$addToSet": "$train_number"},
                }
            },
        ]

        docs = await MongoDB.database.special_trains.aggregate(pipeline).to_list(length=None)

        result = {}
        for doc in docs:
            date_str = doc.get("_id")
            if date_str:
                result[date_str] = {
                    "count": doc.get("train_count", 0),
                    "passengers": doc.get("total_passengers", 0),
                    "train_numbers": doc.get("train_numbers", []),
                }

        return result

    # ── Dashboard payload (Integrating UTS/PRS Forecasting & Historical Data) ───

    @classmethod
    async def get_dashboard_payload(cls, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Builds the monthly & daily calendar dashboard payload:
        1. Checks `forecasting_data` for predicted UTS, PRS, and Overall passenger counts.
        2. Checks `historical_data` for actual records.
        3. Checks `calendar` collection for uploaded schedule records.
        4. Merges into standard monthly cards format.
        """
        if MongoDB.database is None:
            raise HTTPException(status_code=503, detail="Database not available")

        now = _now_ist()
        target_year = year if year is not None else now.year
        today_key = _date_key(now)
        months = _month_shell()

        # ── 1. Fetch Forecast Predictions from forecasting_data ───────────────
        forecast_query: Dict[str, Any] = {"date": {"$regex": f"^{target_year}-"}}
        forecast_docs = await MongoDB.database.forecasting_data.find(forecast_query, {"_id": 0}).to_list(length=None)
        forecast_map = {doc["date"]: doc for doc in forecast_docs if "date" in doc}

        # ── 2. Fetch Historical Actuals from historical_data ───────────────────
        hist_query: Dict[str, Any] = {"date": {"$regex": f"^{target_year}-"}}
        hist_docs = await MongoDB.database.historical_data.find(hist_query, {"_id": 0}).to_list(length=None)
        hist_map = {doc["date"]: doc for doc in hist_docs if "date" in doc}

        # ── 3. Fetch Uploaded Calendar Records ─────────────────────────────────
        year_start = datetime(target_year, 1, 1, tzinfo=timezone.utc)
        year_end = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
        calendar_match = {"schedule_date": {"$gte": year_start, "$lt": year_end}}

        cal_pipeline = [
            {MONGO_MATCH: calendar_match},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$schedule_date",
                            "timezone": "UTC",
                        }
                    },
                    "boarding": {"$sum": {MONGO_IFNULL: ["$boarding_count", 0]}},
                    "deboarding": {"$sum": {MONGO_IFNULL: ["$deboarding_count", 0]}},
                    "latest_updated_at": {"$max": "$updated_at"},
                }
            },
        ]
        cal_docs = await MongoDB.database.calendar.aggregate(cal_pipeline).to_list(length=None)
        cal_map = {doc["_id"]: doc for doc in cal_docs if "_id" in doc}

        # ── 4. Fetch Special Trains by Date ───────────────────────────────────
        special_trains_by_date = await cls._get_special_trains_by_date(target_year)

        # Collect all unique dates across sources for target_year
        all_dates = set(forecast_map.keys()) | set(hist_map.keys()) | set(cal_map.keys()) | set(special_trains_by_date.keys())

        total_footfall = 0
        total_scheduled_pax = 0
        total_special_pax = 0
        total_uts_pax = 0
        total_prs_pax = 0
        total_uts_predicted = 0
        total_prs_predicted = 0

        live_pax = 0
        live_scheduled_pax = 0
        live_special_pax = 0
        live_special_trains_count = 0
        latest_updated_at: Optional[datetime] = None

        for date_str in all_dates:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            month_index = dt.month - 1
            day_number = dt.day

            f_doc = forecast_map.get(date_str)
            h_doc = hist_map.get(date_str)
            c_doc = cal_map.get(date_str)
            sp_doc = special_trains_by_date.get(date_str, {})

            # Determine values based on priority (Forecast -> Historical -> Calendar)
            is_forecast = False
            is_blind_forecast = False
            uts_pred = 0
            prs_pred = 0
            uts_act = None
            prs_act = None
            occasion = ""

            day_special_pax = sp_doc.get("passengers", 0)
            day_specials_count = sp_doc.get("count", 0)
            special_train_numbers = sp_doc.get("train_numbers", [])

            if f_doc:
                is_forecast = True
                is_blind_forecast = bool(f_doc.get("is_blind_forecast", True))
                uts_pred = _safe_int(f_doc.get("uts_total_predicted", 0))
                prs_pred = _safe_int(f_doc.get("prs_total_predicted", 0))
                uts_act = _safe_optional_int(f_doc.get("uts_total_actual"))
                prs_act = _safe_optional_int(f_doc.get("prs_total_actual"))
                occasion = _safe_str(f_doc.get("occasion_or_holiday"))

                if is_blind_forecast:
                    day_uts_pax = uts_pred
                    day_prs_pax = prs_pred
                    day_scheduled_pax = uts_pred + prs_pred
                else:
                    day_uts_pax = uts_act if uts_act is not None else uts_pred
                    day_prs_pax = prs_act if prs_act is not None else prs_pred
                    day_scheduled_pax = day_uts_pax + day_prs_pax

                day_total_pax = day_scheduled_pax

            elif h_doc:
                is_forecast = False
                day_uts_pax = _safe_int(h_doc.get("uts_total", 0))
                day_prs_pax = _safe_int(h_doc.get("prs_total", 0))
                day_scheduled_pax = day_uts_pax + day_prs_pax
                day_total_pax = _safe_int(h_doc.get("overall_total", day_scheduled_pax))
                occasion = _safe_str(h_doc.get("occasion_or_holiday"))

            elif c_doc:
                is_forecast = False
                day_scheduled_pax = _safe_int(c_doc.get("boarding", 0)) + _safe_int(c_doc.get("deboarding", 0))
                day_uts_pax = 0
                day_prs_pax = 0
                day_total_pax = day_scheduled_pax
                up_at = c_doc.get("latest_updated_at")
                if up_at and (latest_updated_at is None or up_at > latest_updated_at):
                    latest_updated_at = up_at
            else:
                day_scheduled_pax = 0
                day_uts_pax = 0
                day_prs_pax = 0
                day_total_pax = 0

            day_card = {
                "d": day_number,
                "lbl": occasion,
                "pax": day_total_pax,
                "scheduledPax": day_scheduled_pax,
                "specialPax": day_special_pax,
                "utsPax": day_uts_pax,
                "prsPax": day_prs_pax,
                "utsPredicted": uts_pred,
                "prsPredicted": prs_pred,
                "utsActual": uts_act,
                "prsActual": prs_act,
                "isForecast": is_forecast,
                "isBlindForecast": is_blind_forecast,
                "sp": day_specials_count,
                "specialTrainNumbers": special_train_numbers,
                "specialTrainsTotalPax": day_special_pax,
            }

            months[month_index]["days"].append(day_card)
            months[month_index]["totalPax"] += day_total_pax
            months[month_index]["totalScheduledPax"] += day_scheduled_pax
            months[month_index]["totalSpecialPax"] += day_special_pax
            months[month_index]["totalUtsPax"] += day_uts_pax
            months[month_index]["totalPrsPax"] += day_prs_pax
            months[month_index]["totalUtsPredicted"] += uts_pred
            months[month_index]["totalPrsPredicted"] += prs_pred
            months[month_index]["totalSpecialTrains"] += day_specials_count
            months[month_index]["totalSpecialTrainsFootfall"] += day_special_pax

            total_footfall += day_total_pax
            total_scheduled_pax += day_scheduled_pax
            total_special_pax += day_special_pax
            total_uts_pax += day_uts_pax
            total_prs_pax += day_prs_pax
            total_uts_predicted += uts_pred
            total_prs_predicted += prs_pred

            if date_str == today_key:
                live_pax = day_total_pax
                live_scheduled_pax = day_scheduled_pax
                live_special_pax = day_special_pax
                live_special_trains_count = day_specials_count

        for month in months:
            month["days"] = sorted(month["days"], key=lambda d: d["d"])

        current_month_total = months[now.month - 1]["totalPax"]
        previous_month_total = months[now.month - 2]["totalPax"] if now.month > 1 else 0
        mom_growth = (
            ((current_month_total - previous_month_total) / previous_month_total) * 100
            if previous_month_total > 0 else 0.0
        )
        if math.isnan(mom_growth) or math.isinf(mom_growth):
            mom_growth = 0.0

        updated_str = (
            latest_updated_at.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
            if latest_updated_at
            else now.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
        )

        special_summary = await cls._get_special_trains_summary()

        payload = {
            "months": months,
            "totalFootfall": total_footfall,
            "livePax": live_pax,
            "totalScheduledPax": total_scheduled_pax,
            "totalSpecialPax": _safe_int(special_summary.get("totalSpecialPax", 0)),
            "totalUtsPax": total_uts_pax,
            "totalPrsPax": total_prs_pax,
            "totalUtsPredicted": total_uts_predicted,
            "totalPrsPredicted": total_prs_predicted,
            "totalSpecialTrains": _safe_int(special_summary.get("totalSpecialTrains", 0)),
            "liveScheduledPax": live_scheduled_pax,
            "liveSpecialPax": live_special_pax,
            "liveSpecialTrains": live_special_trains_count,
            "lastUpdated": updated_str,
            "yoyGrowth": 0.0,
            "momGrowth": _safe_float(round(mom_growth, 1)),
            "dataSource": "forecasting_data",
        }
        return clean_nan_values(payload)

    # ── Hourly buckets (train_schedules only, split by scheduled vs special) ──

    @classmethod
    async def _aggregate_hourly_split_for_date(
        cls,
        target_date: datetime,
        special_train_numbers: Set[Any],
    ) -> Dict[str, List[int]]:
        if MongoDB.database is None:
            raise HTTPException(status_code=503, detail="Database not available")

        scheduled_hourly: List[int] = [0] * 24
        special_hourly: List[int] = [0] * 24

        pipeline = [
            {MONGO_MATCH: {"schedule_date": target_date}},
            {
                "$project": {
                    "train_number": 1,
                    "departure_hour": {MONGO_IFNULL: ["$departure_hour", "$hour", "$scheduled_hour", -1]},
                    "arrival_hour": {MONGO_IFNULL: ["$arrival_hour", -1]},
                    "boarding_count": {MONGO_IFNULL: ["$boarding_count", 0]},
                    "deboarding_count": {MONGO_IFNULL: ["$deboarding_count", 0]},
                    "total_passengers": {MONGO_IFNULL: [FIELD_TOTAL_PASSENGERS, 0]},
                    "hourly_passengers": {MONGO_IFNULL: ["$hourly_passengers", []]}
                }
            }
        ]

        docs = await MongoDB.database.train_schedules.aggregate(pipeline).to_list(length=None)

        for doc in docs:
            train_number = doc.get("train_number")
            is_special = (
                train_number is not None
                and (
                    train_number in special_train_numbers
                    or str(train_number) in special_train_numbers
                )
            )

            dep_h = _safe_int(doc.get("departure_hour", -1))
            arr_h = _safe_int(doc.get("arrival_hour", -1))
            boarding = _safe_int(doc.get("boarding_count", 0))
            deboarding = _safe_int(doc.get("deboarding_count", 0))
            total = _safe_int(doc.get("total_passengers", 0))
            hp = doc.get("hourly_passengers", [])

            if boarding > 0 or deboarding > 0:
                if boarding > 0:
                    target_h = dep_h if 0 <= dep_h <= 23 else (arr_h if 0 <= arr_h <= 23 else 0)
                    if is_special: special_hourly[target_h] += boarding
                    else: scheduled_hourly[target_h] += boarding

                if deboarding > 0:
                    target_h = arr_h if 0 <= arr_h <= 23 else (dep_h if 0 <= dep_h <= 23 else 0)
                    if is_special: special_hourly[target_h] += deboarding
                    else: scheduled_hourly[target_h] += deboarding

            elif total > 0 and (0 <= dep_h <= 23 or 0 <= arr_h <= 23):
                target_h = dep_h if 0 <= dep_h <= 23 else arr_h
                if is_special: special_hourly[target_h] += total
                else: scheduled_hourly[target_h] += total

            elif hp and isinstance(hp, list) and len(hp) > 0:
                for h, val in enumerate(hp[:24]):
                    pax = _safe_int(val)
                    if is_special: special_hourly[h] += pax
                    else: scheduled_hourly[h] += pax

            elif total > 0:
                per_hour = total // 24
                for h in range(24):
                    if is_special: special_hourly[h] += per_hour
                    else: scheduled_hourly[h] += per_hour

        return {
            "scheduled": scheduled_hourly,
            "special": special_hourly,
        }

    @classmethod
    async def get_hourly_buckets(cls, date_str: str) -> Dict[str, Any]:
        if MongoDB.database is None:
            raise HTTPException(status_code=503, detail="Database not available")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

        special_train_numbers = await cls._get_special_train_numbers()
        hourly_split = await cls._aggregate_hourly_split_for_date(target_date, special_train_numbers)

        scheduled_hourly = hourly_split["scheduled"]
        special_hourly = hourly_split["special"]

        combined_hourly = [scheduled_hourly[h] + special_hourly[h] for h in range(24)]

        buckets = []
        for b in HOURLY_BUCKETS:
            s, e = b["start"], b["end"]
            bucket_scheduled = sum(scheduled_hourly[s:e])
            bucket_special = sum(special_hourly[s:e])
            bucket_combined = bucket_scheduled + bucket_special

            buckets.append({
                "label": b["label"],
                "start": s,
                "end": e,
                "pax": bucket_combined,
                "hourly": combined_hourly[s:e],
                "scheduledPax": bucket_scheduled,
                "specialPax": bucket_special,
                "scheduledHourly": scheduled_hourly[s:e],
                "specialHourly": special_hourly[s:e],
            })

        if buckets:
            max_pax = max(b["pax"] for b in buckets)
            dominant_marked = False
            for b in buckets:
                if not dominant_marked and b["pax"] == max_pax and max_pax > 0:
                    b["isDominant"] = True
                    dominant_marked = True
                else:
                    b["isDominant"] = False

        return clean_nan_values({
            "date": date_str,
            "hourly": combined_hourly,
            "scheduledHourly": scheduled_hourly,
            "specialHourly": special_hourly,
            "buckets": buckets,
            "totalPax": sum(combined_hourly),
            "totalScheduledPax": sum(scheduled_hourly),
            "totalSpecialPax": sum(special_hourly),
            "dataSource": "MongoDB-TrainSchedules",
        })


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/footfall-insights", tags=["Footfall Insights"])
async def get_footfall_insights(year: Optional[int] = None):
    await FootfallInsightsService.ensure_indexes()
    return await FootfallInsightsService.get_dashboard_payload(year=year)


@router.get("/calendar/insights", tags=["Footfall Insights"])
async def get_calendar_insights(year: Optional[int] = None):
    await FootfallInsightsService.ensure_indexes()
    return await FootfallInsightsService.get_dashboard_payload(year=year)


@router.get("/footfall/calendar-insights", tags=["Footfall Insights"])
async def get_footfall_calendar_insights(year: Optional[int] = None):
    await FootfallInsightsService.ensure_indexes()
    return await FootfallInsightsService.get_dashboard_payload(year=year)


@router.get(
    "/footfall/hourly-buckets",
    tags=["Footfall Insights"],
    summary="Hourly passenger buckets split by scheduled vs special trains",
)
async def get_hourly_buckets(
    date: str = Query(..., description="Date in YYYY-MM-DD format, e.g. 2026-04-14"),
):
    await FootfallInsightsService.ensure_indexes()
    return await FootfallInsightsService.get_hourly_buckets(date_str=date)


@router.post("/footfall-insights/tick", tags=["Footfall Insights"])
async def create_footfall_tick(tick: FootfallTickIn = Body(default_factory=FootfallTickIn)):
    return {
        "status": "ignored",
        "message": "Footfall is derived from forecasting_data, historical_data, and calendar collections.",
    }


@router.post("/calendar/upload", tags=["Footfall Insights"])
async def upload_calendar_data(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be Excel format")
    content = await file.read()
    return await CalendarUploadService.upload_calendar_excel(content, file.filename)


@router.post("/special-trains/upload", tags=["Footfall Insights"])
async def upload_special_trains_data(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be Excel format")
    content = await file.read()
    return await CalendarUploadService.upload_special_trains_excel(content, file.filename)


# ── New Forecasting & Data Ingestion Endpoints ───────────────────────────────

@router.post("/historical-data/upload", tags=["Forecasting"])
async def upload_historical_data(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Upload historical actuals CSV file to populate MongoDB collection `historical_data`.
    Automatically preprocesses data, trains ML models, and regenerates UTS/PRS forecasts
    into `forecasting_data` in a background task — no manual steps required.
    """
    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    content = await file.read()
    from services.forecasting.data_loader import parse_and_insert_historical_csv
    from services.forecasting.auto_pipeline import AutoForecastTrigger
    await FootfallInsightsService.ensure_indexes()
    result = parse_and_insert_historical_csv(content)

    # Immediately trigger the auto-pipeline (non-blocking, deduplicates concurrent runs)
    await AutoForecastTrigger.trigger("historical_data_upload")

    return {
        "status": "success",
        "message": (
            "Historical data uploaded. The UTS/PRS forecasting pipeline has been "
            "automatically started in the background. Predictions will be updated in "
            "`forecasting_data` once training completes."
        ),
        "filename": file.filename,
        "result": result,
    }


@router.post("/forecasting-data/upload", tags=["Forecasting"])
async def upload_forecasting_data(file: UploadFile = File(...)):
    """
    Upload a forecasting CSV file to populate MongoDB collection `forecasting_data`.
    """
    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel format")
    content = await file.read()
    from services.forecasting.data_loader import parse_and_insert_forecasting_csv
    await FootfallInsightsService.ensure_indexes()
    result = parse_and_insert_forecasting_csv(content)
    return {
        "status": "success",
        "filename": file.filename,
        "result": result,
    }


@router.post("/forecast/run", tags=["Forecasting"])
async def trigger_forecast_pipeline(
    request: ForecastRunRequest = Body(default_factory=ForecastRunRequest),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Triggers model training and upcoming-month prediction generation.
    Reads from `historical_data`, trains models, and stores forecasts into `forecasting_data`.
    """
    await FootfallInsightsService.ensure_indexes()
    result = await ForecastingRunner.run_pipeline_async(skip_backtest=request.skip_backtest)
    return {
        "status": "completed",
        "message": "Forecasting pipeline executed successfully.",
        "result": result,
    }


@router.get("/forecast/predictions", tags=["Forecasting"])
@router.get("/forecasting-data", tags=["Forecasting"])
async def get_predictions(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    year: Optional[int] = Query(None, description="Year e.g. 2026")
):
    """
    Retrieves predicted UTS and PRS passenger forecasts from MongoDB collection `forecasting_data`.
    """
    await FootfallInsightsService.ensure_indexes()
    predictions = await ForecastingDBService.get_forecast_predictions(
        start_date=start_date, end_date=end_date, year=year
    )
    return clean_nan_values({
        "count": len(predictions),
        "predictions": predictions,
    })


@router.get("/historical-data", tags=["Forecasting"])
async def get_historical_data(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    year: Optional[int] = Query(None, description="Year e.g. 2026")
):
    """
    Retrieves historical actual records from MongoDB collection `historical_data`.
    """
    await FootfallInsightsService.ensure_indexes()
    if MongoDB.database is None:
        return {"count": 0, "records": []}
    
    query: Dict[str, Any] = {}
    if year:
        query["date"] = {"$regex": f"^{year}-"}
    elif start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["date"] = date_filter

    cursor = MongoDB.database.historical_data.find(query, {"_id": 0}).sort("date", 1)
    records = await cursor.to_list(length=None)
    return clean_nan_values({
        "count": len(records),
        "records": records,
    })


@router.post("/forecast/seed", tags=["Forecasting"])
@router.post("/forecast/seed-historical", tags=["Forecasting"])
async def seed_data_collections():
    """
    Seeds both MongoDB collections (`historical_data` and `forecasting_data`)
    """
    await FootfallInsightsService.ensure_indexes()
    from services.forecasting.data_loader import seed_all_collections
    result = seed_all_collections()
    return {
        "status": "success",
        "result": result,
    }

