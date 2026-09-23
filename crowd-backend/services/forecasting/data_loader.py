"""
Data loader for historical UTS/PRS datasets from MongoDB collection `historical_data`
and upcoming predictions from `forecasting_data`, with automatic seeding from reference CSVs.
"""
import io
import os
import math
import logging
from datetime import datetime, timezone
from functools import lru_cache
import numpy as np
import pandas as pd
from pymongo import MongoClient
from typing import Tuple, Dict, Any, Optional, List

from config.config import get_settings
from . import forecasting_config as config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_sync_db():
    """Genuine sync pymongo database for the forecasting pipeline's sync code paths
    (worker-thread pipeline run, CSV upload/seed helpers). Independent of the app's
    Motor async client in db/mongodb.py, which cannot be safely used off the event loop."""
    settings = get_settings()
    if not settings.mongodb_uri or not settings.mongodb_database:
        return None
    client = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        maxPoolSize=settings.mongodb_max_pool_size,
    )
    return client[settings.mongodb_database]


def _clean_val(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            return None
        return int(round(val))
    except (TypeError, ValueError):
        return None


def _clean_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    return s


def _clean_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            return default
        return int(round(val))
    except (TypeError, ValueError):
        return default


def seed_historical_collection_if_empty() -> int:
    """
    Checks if MongoDB `historical_data` collection has documents.
    Returns count of documents.
    """
    db = _get_sync_db()
    if db is None:
        logger.warning("MongoDB not connected, skipping historical count check.")
        return 0

    collection = db[config.HISTORICAL_COLLECTION]
    count = collection.count_documents({})
    if count > 0:
        logger.info(f"Collection {config.HISTORICAL_COLLECTION} has {count} records.")
    else:
        logger.warning(f"Collection {config.HISTORICAL_COLLECTION} is empty.")
    return count


def seed_all_collections() -> Dict[str, int]:
    """Checks historical_data record counts."""
    h_count = seed_historical_collection_if_empty()
    return {
        "historical_data": h_count,
    }


def parse_and_insert_historical_csv(file_content: bytes) -> Dict[str, Any]:
    """Parses an uploaded historical CSV file and updates `historical_data` collection."""
    db = _get_sync_db()
    if db is None:
        raise RuntimeError("MongoDB not connected")

    df = pd.read_csv(io.BytesIO(file_content))
    collection = db[config.HISTORICAL_COLLECTION]

    from pymongo import UpdateOne
    operations = []
    for _, row in df.iterrows():
        d_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        rec = {
            "date": d_str,
            "day_of_week": str(row.get("Day of Week", "")),
            "uts_inward": _clean_int(row.get("UTS Inward")),
            "uts_outward": _clean_int(row.get("UTS Outward")),
            "uts_total": _clean_int(row.get("UTS Total")),
            "prs_inward": _clean_int(row.get("PRS Inward")),
            "prs_outward": _clean_int(row.get("PRS Outward")),
            "prs_total": _clean_int(row.get("PRS Total")),
            "overall_total": _clean_int(row.get("Overall Total")),
            "occasion_or_holiday": _clean_str(row.get("Occasion / Public Holiday")),
            "is_holiday_festival": _clean_str(row.get("Is Holiday/Festival")) or "No",
            "uploaded_at": datetime.now(timezone.utc),
        }
        operations.append(UpdateOne({"date": d_str}, {"$set": rec}, upsert=True))

    if operations:
        res = collection.bulk_write(operations, ordered=False)
        collection.create_index("date", unique=True)
        return {
            "total_rows": len(df),
            "upserted": res.upserted_count,
            "modified": res.modified_count,
        }
    return {"total_rows": 0, "upserted": 0, "modified": 0}


def parse_and_insert_forecasting_csv(file_content: bytes) -> Dict[str, Any]:
    """Parses an uploaded forecast CSV file and updates `forecasting_data` collection."""
    db = _get_sync_db()
    if db is None:
        raise RuntimeError("MongoDB not connected")

    df = pd.read_csv(io.BytesIO(file_content))
    collection = db[config.FORECASTING_COLLECTION]

    from pymongo import UpdateOne
    operations = []
    for _, row in df.iterrows():
        d_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")
        uts_pred = _clean_int(row.get("UTS Total (Predicted)"))
        prs_pred = _clean_int(row.get("PRS Total (Predicted)"))
        uts_act = _clean_val(row.get("UTS Total (Actual)"))
        prs_act = _clean_val(row.get("PRS Total (Actual)"))
        overall_act = (uts_act + prs_act) if (uts_act is not None and prs_act is not None) else _clean_val(row.get("Overall Total (Actual)"))

        rec = {
            "date": d_str,
            "day_of_week": str(row.get("Day of Week", "")),
            "uts_total_predicted": uts_pred,
            "prs_total_predicted": prs_pred,
            "overall_total_predicted": uts_pred + prs_pred,
            "uts_total_actual": uts_act,
            "prs_total_actual": prs_act,
            "overall_total_actual": overall_act,
            "occasion_or_holiday": _clean_str(row.get("Occasion / Public Holiday")),
            "is_blind_forecast": bool(row.get("Is Blind Forecast", True)),
            "note": _clean_str(row.get("Note")),
            "model_version": config.MODEL_VERSION,
            "generated_at": datetime.now(timezone.utc),
        }
        operations.append(UpdateOne({"date": d_str}, {"$set": rec}, upsert=True))

    if operations:
        res = collection.bulk_write(operations, ordered=False)
        collection.create_index("date", unique=True)
        return {
            "total_rows": len(df),
            "upserted": res.upserted_count,
            "modified": res.modified_count,
        }
    return {"total_rows": 0, "upserted": 0, "modified": 0}


def load_historical_data_sync() -> pd.DataFrame:
    """
    Synchronously loads historical data from MongoDB `historical_data` collection.
    """
    db = _get_sync_db()
    if db is None:
        raise RuntimeError("MongoDB is not connected. Cannot load historical data.")

    try:
        collection = db[config.HISTORICAL_COLLECTION]
        cursor = collection.find({}).sort("date", 1)
        docs = list(cursor)
        if docs:
            rows = []
            for d in docs:
                rows.append({
                    "Date": pd.to_datetime(d.get("date")),
                    "Day of Week": d.get("day_of_week", ""),
                    "UTS Inward": d.get("uts_inward", 0),
                    "UTS Outward": d.get("uts_outward", 0),
                    "UTS Total": d.get("uts_total", d.get("UTS Total", 0)),
                    "PRS Inward": d.get("prs_inward", 0),
                    "PRS Outward": d.get("prs_outward", 0),
                    "PRS Total": d.get("prs_total", d.get("PRS Total", 0)),
                    "Overall Total": d.get("overall_total", d.get("Overall Total", 0)),
                    "Occasion / Public Holiday": d.get("occasion_or_holiday", d.get("Occasion / Public Holiday", "")),
                    "Is Holiday/Festival": d.get("is_holiday_festival", d.get("Is Holiday/Festival", "No")),
                })
            df = pd.DataFrame(rows)
            df = df.sort_values("Date").reset_index(drop=True)
            logger.info(f"Loaded {len(df)} historical records from MongoDB collection '{config.HISTORICAL_COLLECTION}'.")
            return df
        else:
            raise ValueError(f"MongoDB collection '{config.HISTORICAL_COLLECTION}' is empty.")
    except Exception as e:
        logger.error(f"Error loading from MongoDB {config.HISTORICAL_COLLECTION}: {e}")
        raise


def build_target_series(df: pd.DataFrame, target: str, idx_of_date: Dict[Any, int], n_full: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    values_actual_full = np.full(n_full, np.nan)
    for d, v in zip(df['Date'], df[target]):
        if d in idx_of_date:
            values_actual_full[idx_of_date[d]] = v

    bad_date = config.BAD_DAY_BY_TARGET.get(target)
    if bad_date and bad_date in idx_of_date:
        bad_idx = idx_of_date[bad_date]

        values_for_features_full = pd.Series(values_actual_full)
        values_for_features_full.iloc[bad_idx] = np.nan
        values_for_features_full = values_for_features_full.interpolate(limit_direction='both').to_numpy()

        values_actual_clean = values_actual_full.copy()
        values_actual_clean[bad_idx] = np.nan
    else:
        values_for_features_full = pd.Series(values_actual_full).interpolate(limit_direction='both').to_numpy()
        values_actual_clean = values_actual_full.copy()

    return values_actual_full, values_for_features_full, values_actual_clean
