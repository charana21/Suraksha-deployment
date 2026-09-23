"""
Live train refresh toggle helper
Stores the UI toggle state so scheduled fetchers can check whether to hit RapidAPI.
"""
from datetime import UTC, datetime
from typing import Optional, Dict, Any
from db.mongodb import MongoDB

class LiveTrainRefreshToggleService:
    """Helper for storing/fetching live train API toggle state"""

    COLLECTION = "app_settings"
    DOCUMENT_ID = "train_live_refresh_toggle"

    @classmethod
    def _build_filter(cls) -> Dict[str, Any]:
        return {"_id": cls.DOCUMENT_ID}

    @classmethod
    async def get_toggle_document(cls) -> Optional[Dict[str, Any]]:
        if MongoDB.database is None:
            return None

        doc = await MongoDB.database[cls.COLLECTION].find_one(cls._build_filter())
        return doc

    @classmethod
    async def is_live_refresh_enabled(cls, default: bool = True) -> bool:
        doc = await cls.get_toggle_document()
        if not doc:
            return default
        return bool(doc.get("live_train_refresh_enabled", default))

    @classmethod
    async def set_live_refresh_enabled(
        cls, enabled: bool, updated_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if MongoDB.database is None:
            return None

        now = datetime.now(UTC)
        update = {
            "$set": {
                "live_train_refresh_enabled": enabled,
                "updated_at": now,
            }
        }
        if updated_by:
            update["$set"]["updated_by"] = updated_by

        await MongoDB.database[cls.COLLECTION].update_one(cls._build_filter(), update, upsert=True)
        return await cls.get_toggle_document()
