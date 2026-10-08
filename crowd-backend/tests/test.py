# import json
# from typing import Any, Dict, Optional

# from twilio.rest import Client

# from config.config import get_settings


# class WhatsAppNotificationService:
#     """Template-based WhatsApp sender used for opt-in and train alerts."""

#     @staticmethod
#     def _normalize_whatsapp_number(number: str) -> str:
#         cleaned = (number or "").strip()
#         if not cleaned:
#             return ""
#         return cleaned if cleaned.startswith("whatsapp:") else f"whatsapp:{cleaned}"

#     @staticmethod
#     def _get_client() -> Optional[Client]:
#         settings = get_settings()
#         account_sid = (settings.twilio_account_sid or "").strip()
#         auth_token = (settings.twilio_auth_token or "").strip()
#         if not account_sid or not auth_token:
#             return None
#         return Client(account_sid, auth_token)

#     @staticmethod
#     def send_optin_message(phone_number: str, full_name: str = "User") -> Dict[str, Any]:
#         settings = get_settings()
#         client = WhatsAppNotificationService._get_client()
#         from_number = WhatsAppNotificationService._normalize_whatsapp_number(settings.twilio_whatsapp_number)
#         to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)

#         if not client or not from_number or not to_number:
#             return {"success": False, "error": "Missing Twilio credentials or phone numbers"}

#         content_sid = (getattr(settings, "twilio_whatsapp_optin_content_sid", "") or "").strip()

#         try:
#             if content_sid:
#                 message = client.messages.create(
#                     from_=from_number,
#                     to=to_number,
#                     content_sid=content_sid,
#                     content_variables=json.dumps({"1": full_name or "User"}),
#                 )
#             else:
#                 body = (
#                     "Railway alerts opt-in request. Reply YES to receive train delay/platform "
#                     "change WhatsApp alerts. Reply STOP anytime to unsubscribe."
#                 )
#                 message = client.messages.create(
#                     from_=from_number,
#                     to=to_number,
#                     body=body,
#                 )

#             return {"success": True, "sid": message.sid}
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     @staticmethod
#     def send_train_alert_template(
#         phone_number: str,
#         train_number: str,
#         eta_text: str,
#         update_text: str,
#         full_name: str = "Passenger",
#     ) -> Dict[str, Any]:
#         settings = get_settings()
#         client = WhatsAppNotificationService._get_client()
#         from_number = WhatsAppNotificationService._normalize_whatsapp_number(settings.twilio_whatsapp_number)
#         to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)

#         if not client or not from_number or not to_number:
#             return {"success": False, "error": "Missing Twilio credentials or phone numbers"}

#         content_sid = (getattr(settings, "twilio_whatsapp_train_alert_content_sid", "") or "").strip()

#         try:
#             if content_sid:
#                 message = client.messages.create(
#                     from_=from_number,
#                     to=to_number,
#                     content_sid=content_sid,
#                     content_variables=json.dumps(
#                         {
#                             "1": full_name or "Passenger",
#                             "2": str(train_number or ""),
#                             "3": eta_text or "-",
#                             "4": update_text or "-",
#                         }
#                     ),
#                 )
#             else:
#                 body = (
#                     f"Train {train_number}: {update_text}. "
#                     f"Time: {eta_text}. Reply STOP to unsubscribe."
#                 )
#                 message = client.messages.create(
#                     from_=from_number,
#                     to=to_number,
#                     body=body,
#                 )

#             return {"success": True, "sid": message.sid}
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     @staticmethod
#     def send_subscribed_message(phone_number: str, full_name: str = "Passenger") -> Dict[str, Any]:
#         settings = get_settings()
#         client = WhatsAppNotificationService._get_client()
#         from_number = WhatsAppNotificationService._normalize_whatsapp_number(settings.twilio_whatsapp_number)
#         to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
#         content_sid = (getattr(settings, "twilio_whatsapp_subscribed_content_sid", "") or "").strip()

#         if not client or not from_number or not to_number:
#             return {"success": False, "error": "Missing Twilio credentials or phone numbers"}
#         if not content_sid:
#             return {"success": False, "error": "Missing twilio_whatsapp_subscribed_content_sid"}

#         try:
#             message = client.messages.create(
#                 from_=from_number,
#                 to=to_number,
#                 content_sid=content_sid,
#                 content_variables=json.dumps({"1": full_name or "Passenger"}),
#             )
#             return {"success": True, "sid": message.sid}
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     @staticmethod
#     def send_text_message(phone_number: str, message_text: str) -> Dict[str, Any]:
#         settings = get_settings()
#         client = WhatsAppNotificationService._get_client()
#         from_number = WhatsAppNotificationService._normalize_whatsapp_number(settings.twilio_whatsapp_number)
#         to_number = WhatsAppNotificationService._normalize_whatsapp_number(phone_number)
#         safe_text = (message_text or "").strip()

#         if not client or not from_number or not to_number:
#             return {"success": False, "error": "Missing Twilio credentials or phone numbers"}
#         if not safe_text:
#             return {"success": False, "error": "Message text is required"}

#         try:
#             message = client.messages.create(
#                 from_=from_number,
#                 to=to_number,
#                 body=safe_text,
#             )
#             return {"success": True, "sid": message.sid}
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     @staticmethod
#     def test_template_message() -> bool:
#         settings = get_settings()
#         test_number = (settings.alert_receiver_whatsapp or "").split(",")[0].strip()
#         result = WhatsAppNotificationService.send_train_alert_template(
#             phone_number=test_number,
#             train_number="12627",
#             eta_text="14:30",
#             update_text="Running late by 25 minutes.",
#             full_name="Rahul",
#         )
#         if result.get("success"):
#             print(f"[WhatsApp] Test message sent. SID: {result.get('sid')}")
#             return True
#         print(f"[WhatsApp] Error: {result.get('error')}")
#         return False


# if __name__ == "__main__":
#     print("Result:", WhatsAppNotificationService.test_template_message())
