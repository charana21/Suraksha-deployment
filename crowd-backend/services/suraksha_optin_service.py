"""
Daily Suraksha AI Allow/Deny opt-in sender.

Sends the suraksha_ai WhatsApp template once per day at IST midnight to active
users in viewers_user_collection who have the suraksha_ai service assigned and
have not yet opted in (sendAlerts is false).
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from bson import ObjectId
from jose.jwt import UTC
from db.mongodb import MongoDB
from modules.users import UsersManager
from services.notification_service import NotificationService
from utils.logging_config import get_logger

logger = get_logger("crowdvision.services.suraksha_optin")

SURAKSHA_AI_TEMPLATE = "suraksha_ai"
SURAKSHA_OPTIN_FALLBACK_TEXT = (
    "Do you want to receive Suraksha AI alerts on this WhatsApp number? "
    "Please reply Allow or Deny."
)
IST_OFFSET = timedelta(hours=5, minutes=30)


def _ist_now() -> datetime:
    return datetime.now(UTC) + IST_OFFSET


def _ist_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def seconds_until_next_ist_midnight() -> float:
    """Seconds to sleep until the next IST midnight (00:00)."""
    ist_now = _ist_now()
    next_midnight = (ist_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(0.0, (next_midnight - ist_now).total_seconds())


def seconds_until_next_ist_11_59_pm() -> float:
    """Seconds to sleep until the next IST 11:59 PM (23:59)."""
    ist_now = _ist_now()
    next_11_59 = ist_now.replace(hour=23, minute=59, second=0, microsecond=0)
    if next_11_59 <= ist_now:
        next_11_59 += timedelta(days=1)
    return max(0.0, (next_11_59 - ist_now).total_seconds())


def _was_sent_today(doc: Dict[str, Any], ist_today: str) -> bool:
    last_sent = doc.get("lastSurakshaOptinSentAt")
    if not last_sent:
        return False
    if hasattr(last_sent, "strftime"):
        return _ist_date(last_sent + IST_OFFSET) == ist_today
    return False


class SurakshaOptInService:
    @classmethod
    async def get_eligible_users(cls) -> List[Dict[str, Any]]:
        if MongoDB.database is None:
            return []

        collection = MongoDB.database[UsersManager.USER_COLLECTION]
        ist_today = _ist_date(_ist_now())

        cursor = collection.find(
            {
                "active": 1,
                "services": SURAKSHA_AI_TEMPLATE,
                "phone": {"$exists": True, "$ne": ""},
            },
            {"phone": 1, "name": 1, "lastSurakshaOptinSentAt": 1},
        )

        eligible = []
        async for doc in cursor:
            if _was_sent_today(doc, ist_today):
                continue
            phone = UsersManager._normalize_whatsapp_phone(doc.get("phone", ""))
            if not phone:
                continue
            eligible.append({**doc, "phone": phone})
        return eligible

    @classmethod
    async def send_optin_to_user(cls, user_doc: Dict[str, Any]) -> Dict[str, Any]:
        phone = user_doc.get("phone", "")
        user_id = user_doc.get("_id")
        if not phone or user_id is None:
            return {"success": False, "error": "Missing phone or user id"}

        def _send() -> Dict[str, Any]:
            return NotificationService()._send_msg91_whatsapp(
                to_number=phone,
                template_id=SURAKSHA_AI_TEMPLATE,
                variables=None,
                fallback_text=SURAKSHA_OPTIN_FALLBACK_TEXT,
            )

        result = await asyncio.to_thread(_send)
        success = str(result.get("status", "")).lower() != "error" and not result.get("error")

        if success and MongoDB.database is not None:
            now = datetime.now(UTC)
            await MongoDB.database[UsersManager.USER_COLLECTION].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"lastSurakshaOptinSentAt": now, "updateAt": now}},
            )

        return {"success": success, "phone": phone, "result": result}

    @classmethod
    async def run_daily_batch(cls) -> Dict[str, Any]:
        users = await cls.get_eligible_users()
        if not users:
            logger.info("Suraksha opt-in daily batch: no eligible users")
            return {"sent": 0, "failed": 0, "total": 0}

        sent = 0
        failed = 0
        for user_doc in users:
            try:
                outcome = await cls.send_optin_to_user(user_doc)
                if outcome.get("success"):
                    sent += 1
                    logger.info(
                        "Suraksha opt-in sent to %s (%s)",
                        user_doc.get("name", ""),
                        outcome.get("phone"),
                    )
                else:
                    failed += 1
                    logger.warning(
                        "Suraksha opt-in failed for %s: %s",
                        outcome.get("phone"),
                        outcome.get("result"),
                    )
            except Exception as exc:
                failed += 1
                logger.exception("Suraksha opt-in error for user %s: %s", user_doc.get("_id"), exc)

        summary = {"sent": sent, "failed": failed, "total": len(users)}
        logger.info("Suraksha opt-in daily batch complete: %s", summary)
        return summary

    @classmethod
    async def run_daily_scheduler(cls) -> None:
        """Send Suraksha opt-in messages on a schedule."""
        # Production: sleep until IST midnight (start of day), send once per day.
        while True:
            wait_seconds = seconds_until_next_ist_midnight()
            logger.info(
                "Suraksha opt-in scheduler sleeping %.0f seconds until next IST midnight",
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            try:
                await cls.run_daily_batch()
            except Exception as exc:
                logger.exception("Suraksha opt-in daily batch failed: %s", exc)
            await asyncio.sleep(60)

    @classmethod
    async def reset_send_alerts_batch(cls) -> Dict[str, Any]:
        """Set sendAlerts=False for users with sendAlerts=True and services=suraksha_ai."""
        if MongoDB.database is None:
            return {"updated": 0}

        collection = MongoDB.database[UsersManager.USER_COLLECTION]
        
        try:
            result = await collection.update_many(
                {
                    "services": SURAKSHA_AI_TEMPLATE,
                    "sendAlerts": True,
                },
                {"$set": {"sendAlerts": False}}
            )
            updated_count = result.modified_count
            logger.info("Suraksha opt-in reset alerts batch: reset sendAlerts for %s users", updated_count)
            return {"updated": updated_count}
        except Exception as exc:
            logger.exception("Suraksha opt-in reset alerts error: %s", exc)
            return {"updated": 0, "error": str(exc)}

    @classmethod
    async def run_reset_alerts_scheduler(cls) -> None:
        """Reset sendAlerts to False at 11:59 PM."""
        while True:
            wait_seconds = seconds_until_next_ist_11_59_pm()
            logger.info(
                "Suraksha opt-in reset alerts scheduler sleeping %.0f seconds until next IST 11:59 PM",
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            try:
                await cls.reset_send_alerts_batch()
            except Exception as exc:
                logger.exception("Suraksha opt-in reset alerts batch failed: %s", exc)
            await asyncio.sleep(60)
