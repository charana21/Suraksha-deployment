from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import Any, Dict, List
from db.mongodb import MongoDB
from services.whatsapp_alert_service import WhatsAppNotificationService as WhatsAppTemplateService
logger = logging.getLogger(__name__)

DATABASE_NOT_AVAILABLE_ERROR = "Database not available"

_POSITIVE_REPLIES = {"yes", "y", "start", "subscribe", "optin", "opt in", "confirm", "train_alert_yes", "allow"}
_NEGATIVE_REPLIES = {"stop", "unsubscribe", "cancel", "no", "n", "optout", "opt out", "train_alert_no", "deny"}


class WhatsAppOptInService:
    logger.info("[WhatsAppOptInService] Service class loaded")

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _normalize_e164(number: str) -> str:
        cleaned = (number or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith("whatsapp:"):
            cleaned = cleaned.split("whatsapp:", 1)[1]
        if not cleaned.startswith("+"):
            cleaned = f"+{cleaned}"
        logger.debug("[WhatsAppOptInService] Normalized phone number to E.164 format: %s", cleaned)
        return cleaned

    @classmethod
    async def request_opt_in(
        cls,
        username: str,
        phone_number: str,
        full_name: str = "User",
    ) -> Dict[str, Any]:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available — cannot process opt-in request")
            return {"saved": False, "optin_sent": False, "error": DATABASE_NOT_AVAILABLE_ERROR}

        phone_e164 = cls._normalize_e164(phone_number)
        logger.info("[WhatsAppOptInService] Requesting opt-in for username=%s, phone_number=%s", username, phone_e164)
        if not phone_e164:
            return {"saved": False, "optin_sent": False, "error": "Invalid phone number"}

        from modules.users import UsersManager

        user_collection = MongoDB.database[UsersManager.USER_COLLECTION]
        existing = await user_collection.find_one(
            {
                "$or": [
                    {"phone": phone_e164},
                    {"phone": phone_e164.replace("+", "")},
                ]
            },
            {"sendAlerts": 1},
        )
        if not existing:
            logger.info("[WhatsAppOptIn] No viewer user found for %s; opt-in message not sent", phone_e164)
            return {"saved": False, "optin_sent": False, "error": "Viewer user not found"}

        already_confirmed = bool(existing.get("sendAlerts"))

        send_result = {"success": True, "sid": None, "error": None, "skipped": already_confirmed}
        if not already_confirmed:
            send_result = WhatsAppTemplateService.send_optin_message(
                phone_e164,
                full_name=full_name or "User",
            )
        logger.info(
            "[WhatsAppOptIn] Opt-in send result %s",
            {
                "username": username,
                "phone_number": phone_e164,
                "success": send_result.get("success"),
                "sid": send_result.get("sid"),
                "error": send_result.get("error"),
                "skipped": send_result.get("skipped", False),
            },
        )

        try:
            await user_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "lastWhatsAppOptinRequestedAt": cls._now_utc(),
                        "lastOptinMessageSid": send_result.get("sid"),
                        "lastOptinSendError": send_result.get("error"),
                        "updateAt": cls._now_utc(),
                    }
                },
            )
            logger.info("[WhatsAppOptIn] Viewer opt-in request tracked for %s", phone_e164)
        except Exception as e:
            logger.exception("[WhatsAppOptIn] Failed to update viewer opt-in request for %s", phone_e164)
            optin_sent = bool(send_result.get("success")) and not bool(send_result.get("skipped"))
            return {"saved": False, "optin_sent": optin_sent, "error": str(e)}

        optin_sent = bool(send_result.get("success")) and not bool(send_result.get("skipped"))
        return {
            "saved": True,
            "optin_sent": optin_sent,
            "message_sid": send_result.get("sid"),
            "error": send_result.get("error"),
            "phone_number": phone_e164,
        }

    @classmethod
    async def disable_opt_in(cls, username: str, phone_number: str) -> Dict[str, Any]:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available — cannot disable opt-in")
            return {"saved": False, "error": DATABASE_NOT_AVAILABLE_ERROR}

        phone_e164 = cls._normalize_e164(phone_number)

        try:
            from modules.users import UsersManager

            success = await UsersManager.update_alert_optin(phone_e164, False)
            logger.info("[WhatsAppOptIn] Opt-in disabled successfully for %s", phone_e164)
            return {"saved": success, "modified": 1 if success else 0}
        except Exception as e:
            logger.exception("[WhatsAppOptIn] Failed to disable opt-in for %s", phone_e164)
            return {"saved": False, "error": str(e)}

    @staticmethod
    def _classify_reply(text: str) -> tuple[str, bool, bool]:
        if text in _POSITIVE_REPLIES:
            return "confirmed", True, True
        if text in _NEGATIVE_REPLIES:
            return "unsubscribed", False, False
        return "pending", False, True

    @classmethod
    async def _update_viewer_optin(cls, phone_e164: str, confirmed: bool) -> bool:
        # ONLY update viewers_user_collection (Suraksha AI / CrowdVision users)
        try:
            from modules.users import UsersManager

            update_success = await UsersManager.update_alert_optin(phone_e164, confirmed)
            if update_success:
                logger.info("[WhatsAppOptIn] Updated viewers_user_collection opt-in for %s to %s", phone_e164, confirmed)
            else:
                logger.info("[WhatsAppOptIn] Could not find phone %s in viewers_user_collection to update", phone_e164)
            return update_success
        except Exception:
            logger.exception("[WhatsAppOptIn] Failed to update viewers_user_collection opt-in for %s", phone_e164)
            return False

    @classmethod
    def _send_subscribed_message(cls, phone_e164: str) -> Dict[str, Any]:
        subscribed_result = WhatsAppTemplateService.send_subscribed_message(
            phone_number=phone_e164,
            full_name="Passenger",
        )
        logger.info(
            "[WhatsAppOptIn] Subscribed message result %s",
            {
                "phone_number": phone_e164,
                "success": (subscribed_result or {}).get("success"),
                "sid": (subscribed_result or {}).get("sid"),
                "error": (subscribed_result or {}).get("error"),
            },
        )
        return subscribed_result or {}

    @classmethod
    async def process_inbound_confirmation(cls, from_number: str, body: str, payload: str = "") -> Dict[str, Any]:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available — cannot process inbound confirmation")
            return {"updated": False, "error": DATABASE_NOT_AVAILABLE_ERROR}

        phone_e164 = cls._normalize_e164(from_number)
        text = (payload or body or "").strip().lower()
        status, confirmed, enabled = cls._classify_reply(text)

        update_success = await cls._update_viewer_optin(phone_e164, confirmed)

        subscribed_result: Dict[str, Any] = {}
        if confirmed and update_success:
            subscribed_result = cls._send_subscribed_message(phone_e164)

        return {
            "updated": update_success,
            "phone_number": phone_e164,
            "opt_in_status": status,
            "opt_in_confirmed": confirmed,
            "train_alert_enabled": enabled,
            "subscribed_sent": bool(subscribed_result.get("success")),
            "subscribed_message_sid": subscribed_result.get("sid"),
            "subscribed_error": subscribed_result.get("error"),
        }

    @classmethod
    async def get_confirmed_numbers(cls) -> List[str]:
        logger.info("[WhatsAppOptIn] Public passenger subscriptions are ignored for alert recipients")
        return []

    @classmethod
    async def get_subscription(cls, phone_number: str) -> Dict[str, Any]:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available - cannot fetch viewer alert status")
            return {}
        phone_e164 = cls._normalize_e164(phone_number)
        from modules.users import UsersManager

        doc = await MongoDB.database[UsersManager.USER_COLLECTION].find_one(
            {
                "$or": [
                    {"phone": phone_e164},
                    {"phone": phone_e164.replace("+", "")},
                ]
            },
            {"password": 0},
        )
        if not doc:
            logger.info("[WhatsAppOptIn] No viewer user found for %s", phone_e164)
            return {}
        doc["_id"] = str(doc["_id"])
        return doc

    @classmethod
    async def is_confirmed_enabled(cls, phone_number: str) -> bool:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available - cannot check viewer alert status")
            return False
        phone_e164 = cls._normalize_e164(phone_number)
        from modules.users import UsersManager

        doc = await MongoDB.database[UsersManager.USER_COLLECTION].find_one(
            {
                "$or": [
                    {"phone": phone_e164},
                    {"phone": phone_e164.replace("+", "")},
                ],
                "active": 1,
                "sendAlerts": True,
                "services": {"$in": ["msg91_custom_whatsapp_message_template_id", "custom_whatsapp_message"]},
            },
            {"_id": 1},
        )
        result = bool(doc)
        logger.info("[WhatsAppOptIn] viewer custom WhatsApp enabled for %s: %s", phone_e164, result)
        return result

    @classmethod
    async def get_enabled_numbers(cls) -> List[str]:
        if MongoDB.database is None:
            logger.error("[WhatsAppOptIn] Database not available — cannot fetch enabled numbers")
            return []

        logger.info("[WhatsAppOptIn] Public passenger subscriptions are ignored for alert recipients")
        return []
