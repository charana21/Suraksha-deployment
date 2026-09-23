"""
Database persistence service for UTS & PRS forecasting data.
Handles writing to MongoDB collection `forecasting_data` and reading historical/forecast data.
"""
import math
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd

from db.mongodb import MongoDB
from .data_loader import _get_sync_db
from . import forecasting_config as config

logger = logging.getLogger(__name__)


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


class ForecastingDBService:
    """Service to interact with MongoDB `forecasting_data` collection."""

    @staticmethod
    def dataframe_to_documents(df: pd.DataFrame) -> List[Dict[str, Any]]:
        docs = []
        for _, row in df.iterrows():
            uts_pred = int(round(float(row['UTS Total (Predicted)']))) if pd.notna(row.get('UTS Total (Predicted)')) else 0
            prs_pred = int(round(float(row['PRS Total (Predicted)']))) if pd.notna(row.get('PRS Total (Predicted)')) else 0
            uts_act = _clean_val(row.get('UTS Total (Actual)'))
            prs_act = _clean_val(row.get('PRS Total (Actual)'))
            overall_act = (uts_act + prs_act) if (uts_act is not None and prs_act is not None) else None

            docs.append({
                'date': row['Date'].strftime('%Y-%m-%d'),
                'day_of_week': str(row.get('Day of Week', '')),
                'uts_total_predicted': uts_pred,
                'prs_total_predicted': prs_pred,
                'overall_total_predicted': uts_pred + prs_pred,
                'uts_total_actual': uts_act,
                'prs_total_actual': prs_act,
                'overall_total_actual': overall_act,
                'occasion_or_holiday': _clean_str(row.get('Occasion / Public Holiday')),
                'is_blind_forecast': bool(row.get('Is Blind Forecast', True)),
                'note': _clean_str(row.get('Note')),
                'model_version': config.MODEL_VERSION,
                'generated_at': datetime.now(timezone.utc),
            })
        return docs

    @classmethod
    async def save_predictions_async(cls, df: pd.DataFrame, replace: bool = True) -> Dict[str, Any]:
        """Asynchronously writes prediction DataFrame to MongoDB `forecasting_data`."""
        if MongoDB.database is None:
            logger.warning("MongoDB not connected, skipping prediction write.")
            return {"inserted": 0, "status": "no_db"}

        collection = MongoDB.database[config.FORECASTING_COLLECTION]
        docs = cls.dataframe_to_documents(df)

        if replace:
            await collection.delete_many({})

        if docs:
            await collection.insert_many(docs)
            await collection.create_index("date", unique=True)

        logger.info(f"Successfully saved {len(docs)} forecast records into '{config.FORECASTING_COLLECTION}'.")
        return {
            "inserted": len(docs),
            "collection": config.FORECASTING_COLLECTION,
            "status": "success",
        }

    @classmethod
    def save_predictions_sync(cls, df: pd.DataFrame, replace: bool = True) -> Dict[str, Any]:
        """Synchronously writes prediction DataFrame to MongoDB `forecasting_data`."""
        db = _get_sync_db()
        if db is None:
            logger.warning("MongoDB not connected, skipping prediction write.")
            return {"inserted": 0, "status": "no_db"}

        collection = db[config.FORECASTING_COLLECTION]
        docs = cls.dataframe_to_documents(df)

        if replace:
            collection.delete_many({})

        if docs:
            collection.insert_many(docs)
            collection.create_index("date", unique=True)

        logger.info(f"Successfully saved {len(docs)} forecast records into '{config.FORECASTING_COLLECTION}'.")
        return {
            "inserted": len(docs),
            "collection": config.FORECASTING_COLLECTION,
            "status": "success",
        }

    @classmethod
    async def get_forecast_predictions(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Queries predictions from `forecasting_data` collection."""
        if MongoDB.database is None:
            return []

        collection = MongoDB.database[config.FORECASTING_COLLECTION]
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

        cursor = collection.find(query, {"_id": 0}).sort("date", 1)
        results = await cursor.to_list(length=None)
        return clean_nan_values(results)
