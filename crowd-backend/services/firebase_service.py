"""
Firebase Realtime Database publishing helpers.

MongoDB remains the source of truth. Firebase is used only as a live sync layer
for mobile clients.
"""
import asyncio
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from bson import ObjectId
from config.config import get_settings
logger = logging.getLogger(__name__)

class FirebaseService:
    """Lazy Firebase Admin SDK wrapper for live announcement data."""

    _initialized = False
    _available = False
    _init_error: Optional[str] = None

    @classmethod
    def _safe_path_part(cls, value: Any) -> str:
        text = str(value or "unknown").strip() or "unknown"
        return re.sub(r"[.#$/\[\]]", "_", text)

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        """Convert MongoDB/Python values into Firebase-safe JSON values."""
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            # Normalize common json_util wrappers too, because keys such as $date
            # are not valid Realtime Database child keys.
            if set(value.keys()) == {"$oid"}:
                return str(value["$oid"])
            if set(value.keys()) == {"$date"}:
                return cls._json_safe(value["$date"])
            if set(value.keys()) == {"$numberLong"}:
                return str(value["$numberLong"])
            if set(value.keys()) == {"$numberInt"}:
                return int(value["$numberInt"])
            if set(value.keys()) == {"$numberDouble"}:
                return float(value["$numberDouble"])
            return {
                cls._safe_path_part(k): cls._json_safe(v)
                for k, v in value.items()
                if v is not None
            }
        if isinstance(value, list):
            return [cls._json_safe(item) for item in value]
        return value

    @classmethod
    def _ensure_initialized(cls) -> bool:
        if cls._initialized:
            return cls._available

        cls._initialized = True
        settings = get_settings()

        if not settings.firebase_enabled:
            cls._available = False
            return False

        if not settings.firebase_database_url or not settings.firebase_service_account_path:
            cls._init_error = "Firebase enabled but database URL or service account path is missing"
            logger.warning(cls._init_error)
            cls._available = False
            return False

        try:
            import firebase_admin
            from firebase_admin import credentials

            if not firebase_admin._apps:
                service_account_path = Path(settings.firebase_service_account_path)
                cred = credentials.Certificate(str(service_account_path))
                firebase_admin.initialize_app(
                    cred,
                    {"databaseURL": settings.firebase_database_url},
                )

            cls._available = True
            logger.info("Firebase live sync initialized")
            return True
        except Exception as exc:
            cls._init_error = str(exc)
            cls._available = False
            logger.exception("Firebase initialization failed")
            return False

    @classmethod
    def _set_value(cls, path: str, value: Any) -> bool:
        if not cls._ensure_initialized():
            return False

        try:
            from firebase_admin import db

            db.reference(path).set(cls._json_safe(value))
            return True
        except Exception:
            logger.exception("Firebase write failed for %s", path)
            return False

    @classmethod
    async def publish_recent_announcements(
        cls,
        announcements: List[Dict[str, Any]],
    ) -> bool:
        path = "announcements/recent"
        return await asyncio.to_thread(cls._set_value, path, announcements)

    @classmethod
    async def clear_station_recent_announcements(
        cls,
        station_code: str,
    ) -> bool:
        """Clear legacy station-scoped recent path after moving to API-shaped paths."""
        path = f"stations/{cls._safe_path_part(station_code)}/announcements/recent"
        return await asyncio.to_thread(cls._set_value, path, None)
# firebase endpoints
    @classmethod
    async def publish_congestion(
        cls,
        congestion: Optional[Dict[str, Any]],
    ) -> bool:
        path = "announcements/congestion"
        return await asyncio.to_thread(cls._set_value, path, congestion)

    @classmethod
    async def clear_station_congestion(
        cls,
        station_code: str,
    ) -> bool:
        """Clear legacy station-scoped congestion paths after moving to API-shaped paths."""
        path = f"stations/{cls._safe_path_part(station_code)}/announcements/congestion"
        return await asyncio.to_thread(cls._set_value, path, None)

    @classmethod
    def _create_custom_token_sync(cls, uid: str) -> Optional[str]:
        """Create a Firebase custom token for the given UID (runs synchronously)."""
        if not cls._ensure_initialized():
            return None
        try:
            import firebase_admin.auth as firebase_auth
            token_bytes = firebase_auth.create_custom_token(uid)
            return token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes
        except Exception:
            logger.exception("Firebase custom token creation failed for uid=%s", uid)
            return None

    @classmethod
    async def create_custom_token(cls, uid: str) -> Optional[str]:
        """Create a Firebase custom token for the given UID (async wrapper)."""
        return await asyncio.to_thread(cls._create_custom_token_sync, uid)
