import json
import logging
from typing import Any, Dict, List, Optional
from config.config import get_settings
logger = logging.getLogger(__name__)


class WhatsAppNotificationService:
    """Template-based WhatsApp sender used for opt-in and train alerts."""

    @staticmethod
    def _normalize_delay_status(delay_status: Optional[str]) -> str:
        raw = (delay_status or "").strip()
        if not raw:
            return ""
        return " ".join(raw.split())

    @staticmethod
    def _is_meaningful_platform(platform_value: Optional[str]) -> bool:
        normalized = (platform_value or "").strip().lower()
        if not normalized:
            return False
        if normalized in {"-", "na", "n/a", "unknown", "tbd"}:
            return False
        return True

    @staticmethod
    def _is_delay_status(delay_status: Optional[str]) -> bool:
        normalized = WhatsAppNotificationService._normalize_delay_status(delay_status).lower()
        if not normalized:
            return False
        if "on time" in normalized:
            return False
        return "delay" in normalized

    @staticmethod
    def send_delay_alert_from_api_payload(
        train_number: str,
        api_payload: Dict[str, Any],
        station_code: Optional[str] = None,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """
        Send delay alert using the API-provided `delay_status` directly (no time math).

        Expects RapidAPI payload structure:
          { "data": { "train_name": "...", "stations": [ { "code": "...", "delay_status": "Delay 7m", ... } ] } }
        """
        data = (api_payload or {}).get("data") or {}
        resolved_station = (station_code or "").strip() or get_settings().live_train_station_code

        stations = data.get("stations") or []
        matched = next((s for s in stations if (s or {}).get("code") == resolved_station), None)
        if not matched:
            logger.info("[WhatsApp] Station %s not found in api_payload for %s", resolved_station, train_number)
            return False

        return WhatsAppNotificationService.send_train_alert(
            train_number=str(train_number or ""),
            train_name=str(data.get("train_name") or ""),
            platform_number=str(matched.get("platform") or ""),
            delay_status=str(matched.get("delay_status") or ""),
            recipients=recipients or None,
        )

    @staticmethod
    def _normalize_whatsapp_number(number: str) -> str:
        cleaned = (number or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith("whatsapp:"):
            cleaned = cleaned.replace("whatsapp:", "")
        if cleaned.startswith("+"):
            cleaned = cleaned.replace("+", "")
        return cleaned

    @staticmethod
    def _normalize_whatsapp_numbers(numbers: Optional[List[str]]) -> List[str]:
        if not numbers:
            return []
        normalized = []
        for value in numbers:
            if value is None:
                continue
            cleaned = WhatsAppNotificationService._normalize_whatsapp_number(str(value))
            if cleaned:
                normalized.append(cleaned)
        return normalized

    @staticmethod
    def _split_whatsapp_numbers(raw_numbers: str) -> List[str]:
        if not raw_numbers:
            return []
        candidates = []
        for chunk in str(raw_numbers).replace(";", ",").split(","):
            cleaned = chunk.strip()
            if cleaned:
                candidates.append(cleaned)
        return candidates

    @staticmethod
    def _build_platform_alert_variables(
        settings: Any,
        train_number: str,
        safe_platform: str,
        safe_old_platform: str,
        has_old_platform: bool,
        delay_minutes: int,
        route_source: str,
        route_destination: str,
        total_footfall: str,
        expected_arrival: str,
        expected_departure: str,
    ) -> Dict[str, str]:
        safe_route_source = (route_source or "").strip() or "N/A"
        safe_route_destination = (route_destination or "").strip() or "N/A"
        safe_total_footfall = (str(total_footfall).strip() if total_footfall is not None else "") or "N/A"
        safe_expected_arrival = (expected_arrival or "").strip() or "--"
        safe_expected_departure = (expected_departure or "").strip() or "--"
        safe_delay = f"{delay_minutes} mins" if delay_minutes > 0 else "On time"

        base_station_name = (getattr(settings, "live_train_station_name", "Secunderabad")).split()[0].lower()
        base_station_code = getattr(settings, "live_train_station_code", "SC").lower()

        source_lower = safe_route_source.lower()
        dest_lower = safe_route_destination.lower()

        if base_station_name in source_lower or base_station_code == source_lower:
            safe_expected_arrival = "-"
        if base_station_name in dest_lower or base_station_code == dest_lower:
            safe_expected_departure = "-"

        if has_old_platform and safe_old_platform != safe_platform:
            logger.info("[WhatsApp] Platform change alert triggered")
        else:
            logger.info("[WhatsApp] Platform assigned alert triggered")

        return {
            "var_1": str(train_number),
            "var_2": safe_platform,
            "var_3": f"{safe_route_source} to {safe_route_destination}",
            "var_4": safe_total_footfall,
            "var_5": safe_expected_arrival,
            "var_6": safe_expected_departure,
            "var_7": safe_delay,
        }

    @staticmethod
    def _build_delay_alert_variables(
        train_number: str,
        safe_train_name: str,
        safe_station_name: str,
        safe_platform: str,
        delay_minutes: int,
        safe_delay_status: str,
        safe_expected_arrival: str,
    ) -> Dict[str, str]:
        delay_value = "0"
        if delay_minutes > 0:
            delay_value = str(delay_minutes)
        elif safe_delay_status:
            from services.live_train_service import LiveTrainService

            parsed_mins = LiveTrainService._parse_delay_status(safe_delay_status)
            delay_value = str(parsed_mins) if parsed_mins > 0 else safe_delay_status

        logger.info("[WhatsApp] Train delay alert triggered")

        return {
            "var_1": str(train_number),
            "var_2": safe_train_name or "-",
            "var_3": safe_station_name or "-",
            "var_4": safe_platform or "-",
            "var_5": delay_value or "0",
            "var_6": safe_expected_arrival or "-",
        }

    @staticmethod
    def _dispatch_alert(
        to_numbers: List[str],
        content_sid: str,
        variables: Dict[str, str],
        train_number: str,
    ) -> bool:
        from services.notification_service import NotificationService

        ns = NotificationService.get_instance()
        success = False
        for number in to_numbers:
            logger.info("[WhatsApp] Sending to %s", number)
            res = ns._send_msg91_whatsapp(number, content_sid, variables, "")
            logger.info("[WhatsApp] Result: %s", res)
            if res.get("status") == "sent":
                success = True

        logger.info("[WhatsApp] Alert %s for train %s", "sent" if success else "failed", train_number)
        return success

    @staticmethod
    def send_train_alert(
        train_number: str,
        train_name: str = "",
        station_name: str = "",
        delay_minutes: int = 0,
        platform_number: str = "",
        old_platform: Optional[str] = None,
        recipients: Optional[List[str]] = None,
        delay_status: str = "",
        expected_arrival: str = "",
        route_source: str = "",
        route_destination: str = "",
        schedule_datetime: str = "",
        total_footfall: str = "",
        expected_departure: str = "",
    ) -> bool:
        settings = get_settings()
        logger.info("[WhatsApp] Preparing to send alert")

        if not getattr(settings, "msg91_whatsapp_enabled", True):
            logger.info("[WhatsApp] MSG91 disabled")
            return False

        try:
            safe_train_name = (train_name or "").strip()
            safe_station_name = (station_name or "").strip() or settings.live_train_station_code
            safe_platform = (platform_number or "").strip()
            safe_old_platform = (old_platform or "").strip()
            safe_delay_status = WhatsAppNotificationService._normalize_delay_status(delay_status)
            safe_expected_arrival = (expected_arrival or "").strip() or "-"

            has_new_platform = WhatsAppNotificationService._is_meaningful_platform(safe_platform)
            has_old_platform = WhatsAppNotificationService._is_meaningful_platform(safe_old_platform)
            delay_triggered = delay_minutes > 0 or WhatsAppNotificationService._is_delay_status(safe_delay_status)

            if has_new_platform:
                content_sid = getattr(settings, "msg91_platform_assigned_template_id", "") or "platform_alert"
                variables = WhatsAppNotificationService._build_platform_alert_variables(
                    settings,
                    train_number,
                    safe_platform,
                    safe_old_platform,
                    has_old_platform,
                    delay_minutes,
                    route_source,
                    route_destination,
                    total_footfall,
                    expected_arrival,
                    expected_departure,
                )
            elif delay_triggered:
                content_sid = getattr(settings, "msg91_train_delay_alert_template_id", "")
                variables = WhatsAppNotificationService._build_delay_alert_variables(
                    train_number,
                    safe_train_name,
                    safe_station_name,
                    safe_platform,
                    delay_minutes,
                    safe_delay_status,
                    safe_expected_arrival,
                )
            else:
                logger.info("[WhatsApp] No alert condition met")
                return False

            if not content_sid:
                logger.info("[WhatsApp] Missing content SID for selected alert type")
                return False

            to_numbers = WhatsAppNotificationService._normalize_whatsapp_numbers(recipients)
            if not to_numbers:
                logger.info("[WhatsApp] No valid recipient numbers provided")
                return False

            return WhatsAppNotificationService._dispatch_alert(to_numbers, content_sid, variables, train_number)

        except Exception:
            logger.exception("[WhatsApp] Error sending train alert for %s", train_number)
            return False

    @staticmethod
    def send_optin_message(phone_number: str, full_name: str = "User") -> Dict[str, Any]:
        settings = get_settings()
        to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
        content_sid = (getattr(settings, "msg91_whatsapp_optin_template_id", "") or "").strip()

        try:
            if not content_sid:
                return {"success": False, "error": "Missing msg91_whatsapp_optin_template_id"}
                
            from services.notification_service import NotificationService
            ns = NotificationService.get_instance()
            res = ns._send_msg91_whatsapp(to_number, content_sid, {}, "")
            return {"success": res.get("status") == "sent", "sid": res.get("sid"), "error": res.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def send_subscribed_message(phone_number: str, full_name: str = "Passenger") -> Dict[str, Any]:
        settings = get_settings()
        to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
        content_sid = (getattr(settings, "msg91_whatsapp_subscribed_template_id", "") or "").strip()

        try:
            body = (
                "✅ You are now subscribed to TRIDE Train Alerts.\n\n"
                "You will receive real-time notifications about your train status.\n\n"
                "To unsubscribe anytime, reply STOP."
            )
            from services.notification_service import NotificationService
            ns = NotificationService.get_instance()
            res = ns._send_msg91_whatsapp(to_number, content_sid, {}, body)
            return {"success": res.get("status") == "sent", "sid": res.get("sid"), "error": res.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def send_text_message(phone_number: str, message_text: str) -> Dict[str, Any]:
        to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
        safe_text = (message_text or "").strip()

        if not safe_text:
            return {"success": False, "error": "Message text is required"}

        try:
            from services.notification_service import NotificationService
            ns = NotificationService.get_instance()
            res = ns._send_msg91_whatsapp(to_number, "", {}, safe_text)
            return {"success": res.get("status") == "sent", "sid": res.get("sid"), "error": res.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def send_train_alert_template(
        phone_number: str,
        train_number: str,
        train_name: str = "",
        station_name: str = "",
        scheduled_arrival: str = "",
        expected_arrival: str = "",
        platform_number: str = "",
        eta_text: str = "",
        update_text: str = "",
        full_name: str = "Passenger",
    ) -> Dict[str, Any]:
        settings = get_settings()
        to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
        content_sid = (getattr(settings, "msg91_whatsapp_train_alert_template_id", "") or "").strip()

        safe_train_name = (train_name or "").strip()
        safe_station_name = (station_name or "").strip() or "-"
        safe_scheduled = (scheduled_arrival or "").strip() or (eta_text or "").strip() or "-"
        safe_expected = (expected_arrival or "").strip() or "-"
        safe_platform = (platform_number or "").strip() or "-"

        try:
            variables = {
                "1": str(train_number or ""),
                "2": safe_train_name or "-",
                "3": safe_station_name,
                "4": safe_scheduled,
                "5": safe_expected,
                "6": safe_platform,
            }
            body = (
                "Train Arrival Update\n\n"
                f"Train {train_number}, {safe_train_name}, is arriving at {safe_station_name} station.\n\n"
                f"Scheduled Arrival Time: {safe_scheduled}\n"
                f"Expected Arrival Time: {safe_expected}\n"
                f"Platform: {safe_platform}\n\n"
                f"Passengers are requested to proceed to Platform {safe_platform}."
            )
            
            from services.notification_service import NotificationService
            ns = NotificationService.get_instance()
            res = ns._send_msg91_whatsapp(to_number, content_sid, variables, body)
            return {"success": res.get("status") == "sent", "sid": res.get("sid"), "error": res.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

