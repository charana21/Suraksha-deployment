import smtplib
import asyncio
import logging
import json
import base64
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, Any, Optional
import requests
import os
from util.constants import THRESHOLD_EXCEEDED
from config.config import get_settings
logger = logging.getLogger(__name__)

CONTENT_TYPE_JSON = "application/json"
ISO_UTC_SUFFIX = '+00:00'
IST_TIMESTAMP_FORMAT = "%d %B %Y, %I:%M:%S %p IST"

class NotificationService:
    """
    Service for sending notifications (Email, etc.) asynchronously.
    Supports both Gmail (SMTP) and Microsoft (OAuth2) providers.
    """
    _instance: Optional['NotificationService'] = None

    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.email_alerts_enabled
        self.provider = self.settings.email_provider.lower()

        if self.enabled:
            logger.info(f"Email notifications enabled. Provider: {self.provider}")
            if self.provider == "gmail":
                logger.info(f"SMTP Server: {self.settings.smtp_server}")
            elif self.provider == "microsoft":
                logger.info(f"Microsoft OAuth2 configured for tenant: {self.settings.microsoft_tenant_id}")
        else:
            logger.info("Email notifications disabled in settings.")

        # Track last email time per camera to prevent spam
        # format: {camera_id: last_email_timestamp_float}
        self._last_email_time: Dict[str, float] = {}
        # Track last WhatsApp time per camera to prevent spam
        # format: {camera_id: last_whatsapp_timestamp_float}
        self._last_whatsapp_time: Dict[str, float] = {}

        # Microsoft OAuth2 cache
        self._microsoft_access_token: Optional[str] = None
        self._microsoft_token_expiry: Optional[float] = None

    @classmethod
    def get_instance(cls) -> 'NotificationService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _build_feed_monitor_excel_attachment(alert_data: Dict[str, Any]):
        rows = alert_data.get("feed_monitor_rows", [])
        if len(rows) <= 1:
            return None

        from openpyxl import Workbook
        from openpyxl.styles import Font

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Inactive Cameras"
        worksheet.append(["Camera Id", "Last Timestamp", "Inactive Duration"])
        for cell in worksheet[1]:
            cell.font = Font(bold=True)

        for row in rows:
            worksheet.append([
                row["camera_id"],
                row["last_timestamp"] or "No record found",
                row["inactive_duration"] or "Unknown",
            ])

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        worksheet.column_dimensions["A"].width = 32
        worksheet.column_dimensions["B"].width = 34
        worksheet.column_dimensions["C"].width = 30

        output = BytesIO()
        workbook.save(output)
        return "inactive_camera_feeds.xlsx", output.getvalue()

    async def send_email_alert(self, alert_data: Dict[str, Any], skip_checks: bool = False) -> Dict[str, Any]:
        """
        Send an email alert asynchronously.
        Only sends if configuration is valid and enabled.

        Args:
            alert_data: Alert information dict
            skip_checks: If True, skip severity and cooldown checks (for testing)

        Returns:
            Dict with status: "sent", "skipped", "disabled", or "error"
        """
        if alert_data.get("send_email") is False:
            return {"status": "skipped", "error": "Email disabled for this alert"}

        if not self.enabled:
            return {"status": "disabled", "error": "Email alerts disabled"}

        severity = alert_data.get('severity', 'UNKNOWN')

        if not skip_checks:
            # Check severity - redundant if caller checks, but good for safety
            if severity not in ['CRITICAL']:
                return {"status": "skipped", "error": f"Severity {severity} not in CRITICAL"}

            # Check Email Cooldown (Separate from system cooldown)
            import time
            camera_id = alert_data.get('camera_id')
            now = time.time()

            last_time = self._last_email_time.get(camera_id, 0.0)
            cooldown = self.settings.email_alert_cooldown_seconds

            if (now - last_time) < cooldown:
                remaining = int(cooldown - (now - last_time))
                logger.info(f"Skipping email for {camera_id}: Cooldown active ({remaining}s remaining)")
                return {"status": "skipped", "error": f"Cooldown active ({remaining}s remaining)"}

            # Update last sent time immediately (optimistic update to prevent races)
            self._last_email_time[camera_id] = now

        # Run blocking email call in a separate thread
        loop = asyncio.get_running_loop()
        try:
            if self.provider == "gmail":
                result = await loop.run_in_executor(
                    None,
                    partial(self._send_email_smtp, alert_data)
                )
                return result or {"status": "sent"}
            elif self.provider == "microsoft":
                result = await loop.run_in_executor(
                    None,
                    partial(self._send_email_microsoft, alert_data)
                )
                return result or {"status": "sent"}
            else:
                logger.error(f"Unknown email provider: {self.provider}")
                return {"status": "error", "error": f"Unknown provider: {self.provider}"}
        except Exception as e:
            logger.exception("Failed to schedule email alert")
            return {"status": "error", "error": str(e)}

    def _send_email_smtp(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send email via Gmail SMTP with App Password.
        Should be run in executor (blocking operation).
        Supports multiple recipients.
        """
        sender = self.settings.smtp_username
        receivers = self.settings.alert_receiver_emails_list  # List of emails
        password = self.settings.smtp_password
        smtp_server = self.settings.smtp_server
        smtp_port = self.settings.smtp_port

        if not all([sender, receivers, password, smtp_server]):
            logger.error("Missing SMTP configuration. Cannot send email.")
            return {"status": "error", "error": "Missing SMTP configuration (username/password/server/receivers)"}

        # Convert list to comma-separated string for To header
        receivers_str = ", ".join(receivers)

        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = receivers_str  # Comma-separated for multiple recipients
            msg['Subject'] = alert_data.get('email_subject') or f"[{alert_data.get('severity')}] Crowd Alert: {alert_data.get('camera_id')}"

            body = self._format_email_body(alert_data)
            msg.attach(MIMEText(body, 'html'))

            attachment = self._build_feed_monitor_excel_attachment(alert_data)
            if attachment:
                filename, content = attachment
                excel_part = MIMEApplication(
                    content,
                    _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                excel_part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename,
                )
                msg.attach(excel_part)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)

            logger.info(f"Email alert sent via SMTP to {receivers_str} for {alert_data.get('alert_id')}")
            return {"status": "sent", "provider": "gmail", "recipients": receivers}

        except Exception as e:
            logger.exception("Failed to send SMTP email")
            return {"status": "error", "error": str(e)}

    def _send_email_microsoft(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send email via Microsoft Graph API with OAuth2.
        Should be run in executor (blocking operation).
        Supports multiple recipients.
        """
        try:
            import msal
            import requests
        except ImportError:
            logger.error("msal package not installed. Run: pip install msal")
            return {"status": "error", "error": "msal package not installed. Run: pip install msal"}

        sender = self.settings.microsoft_sender_email
        receivers = self.settings.alert_receiver_emails_list  # List of emails
        tenant_id = self.settings.microsoft_tenant_id
        client_id = self.settings.microsoft_client_id
        client_secret = self.settings.microsoft_client_secret

        if not all([sender, receivers, tenant_id, client_id, client_secret]):
            logger.error("Missing Microsoft OAuth2 configuration. Cannot send email.")
            return {"status": "error", "error": "Missing Microsoft OAuth2 configuration (tenant_id/client_id/client_secret/sender_email/receivers)"}

        try:
            # Get access token
            access_token = self._get_microsoft_access_token(
                tenant_id, client_id, client_secret
            )

            if not access_token:
                logger.error("Failed to obtain Microsoft access token")
                return {"status": "error", "error": "Failed to obtain Microsoft access token"}

            # Prepare email message
            subject = alert_data.get('email_subject') or f"[{alert_data.get('severity')}] Crowd Alert: {alert_data.get('camera_id')}"
            body_html = self._format_email_body(alert_data)

            # Build toRecipients list for multiple recipients
            to_recipients = [
                {"emailAddress": {"address": email}}
                for email in receivers
            ]

            # Microsoft Graph API email payload
            email_payload = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": to_recipients
                },
                "saveToSentItems": "true"
            }

            attachment = self._build_feed_monitor_excel_attachment(alert_data)
            if attachment:
                filename, content = attachment
                email_payload["message"]["attachments"] = [{
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": filename,
                    "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "contentBytes": base64.b64encode(content).decode("ascii"),
                }]

            # Send via Microsoft Graph API
            graph_endpoint = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": CONTENT_TYPE_JSON
            }

            response = requests.post(
                graph_endpoint,
                headers=headers,
                json=email_payload,
                timeout=30
            )

            if response.status_code == 202:
                logger.info(f"Email alert sent via Microsoft Graph to {receivers} for {alert_data.get('alert_id')}")
                return {"status": "sent", "provider": "microsoft", "recipients": receivers}
            else:
                logger.error(f"Failed to send Microsoft email. Status: {response.status_code}, Response: {response.text}")
                return {"status": "error", "error": f"Microsoft API error: {response.status_code} - {response.text}"}

        except Exception as e:
            logger.exception("Failed to send Microsoft email")
            return {"status": "error", "error": str(e)}

    def _get_microsoft_access_token(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str
    ) -> Optional[str]:
        """
        Get Microsoft OAuth2 access token using client credentials flow.
        Caches token until expiry.
        """
        import time
        import msal

        # Check cached token
        if self._microsoft_access_token and self._microsoft_token_expiry:
            if time.time() < self._microsoft_token_expiry - 300:  # 5 min buffer
                return self._microsoft_access_token

        try:
            # Create MSAL confidential client
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            app = msal.ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret
            )

            # Request token with Mail.Send scope
            scopes = ["https://graph.microsoft.com/.default"]
            result = app.acquire_token_for_client(scopes=scopes)

            if "access_token" in result:
                self._microsoft_access_token = result["access_token"]
                self._microsoft_token_expiry = time.time() + result.get("expires_in", 3600)
                logger.info("Microsoft access token obtained successfully")
                return self._microsoft_access_token
            else:
                error = result.get("error_description", result.get("error", "Unknown error"))
                logger.error(f"Failed to get Microsoft token: {error}")
                return None

        except Exception:
            logger.exception("Exception getting Microsoft token")
            return None

    def _format_email_body(self, alert_data: Dict[str, Any]) -> str:
        """Format the email body as beautiful HTML with IST time"""
        from datetime import timedelta

        # Camera feed monitor alerts use a plain body (details inline, or in the Excel attachment)
        if "feed_monitor_rows" in alert_data:
            return f"<html><body>{alert_data.get('trigger_reason', '')}</body></html>"

        # Parse timestamp and convert to IST
        timestamp = alert_data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', ISO_UTC_SUFFIX))
            except ValueError:
                pass

        # Convert to IST (UTC+5:30)
        if isinstance(timestamp, datetime):
            ist_time = timestamp + timedelta(hours=5, minutes=30)
            ts_str = ist_time.strftime(IST_TIMESTAMP_FORMAT)
        else:
            ts_str = str(timestamp)

        # Get severity and set colors
        severity = alert_data.get('severity', 'UNKNOWN')
        severity_colors = {
            'CRITICAL': {'bg': '#dc3545', 'text': '#ffffff', 'border': '#bd2130'},
            'HIGH': {'bg': '#ff6b6b', 'text': '#ffffff', 'border': '#ee5a52'},
            'MEDIUM': {'bg': '#ffc107', 'text': '#000000', 'border': '#e0a800'}
        }
        colors = severity_colors.get(severity, {'bg': '#6c757d', 'text': '#ffffff', 'border': '#545b62'})

        # Extract data
        camera_id = alert_data.get('camera_id', 'Unknown')
        camera_name = alert_data.get('camera_name', camera_id)
        people_count = alert_data.get('people_count', 0)
        density_level = alert_data.get('density_level') or alert_data.get('density', 'N/A')
        trigger_reason = alert_data.get('trigger_reason', THRESHOLD_EXCEEDED)
        location = alert_data.get('location', 'Unknown')

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, {colors['bg']} 0%, {colors['border']} 100%);
                    color: {colors['text']};
                    padding: 30px 20px;
                    text-align: center;
                    border-bottom: 4px solid {colors['border']};
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 600;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
                }}
                .severity-badge {{
                    display: inline-block;
                    background-color: rgba(255,255,255,0.3);
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    margin-top: 10px;
                    border: 2px solid rgba(255,255,255,0.5);
                }}
                .content {{
                    padding: 30px 20px;
                }}
                .info-row {{
                    display: flex;
                    padding: 15px;
                    margin-bottom: 10px;
                    background-color: #f8f9fa;
                    border-radius: 6px;
                    border-left: 4px solid {colors['bg']};
                }}
                .info-label {{
                    font-weight: 600;
                    color: #495057;
                    min-width: 130px;
                    display: flex;
                    align-items: center;
                }}
                .info-label::before {{
                    content: '▸';
                    margin-right: 8px;
                    color: {colors['bg']};
                    font-weight: bold;
                }}
                .info-value {{
                    color: #212529;
                    flex: 1;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin: 20px 0;
                }}
                .stat-card {{
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                    border: 2px solid #dee2e6;
                }}
                .stat-value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: {colors['bg']};
                    margin: 10px 0;
                }}
                .stat-label {{
                    font-size: 12px;
                    color: #6c757d;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .alert-box {{
                    background-color: #fff3cd;
                    border: 2px solid #ffc107;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .alert-box strong {{
                    color: #856404;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    border-top: 2px solid #dee2e6;
                }}
                .button {{
                    display: inline-block;
                    background-color: {colors['bg']};
                    color: {colors['text']};
                    padding: 12px 30px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin-top: 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }}
                .button:hover {{
                    background-color: {colors['border']};
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                }}
                .emoji {{
                    font-size: 24px;
                    margin-right: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1><span class="emoji">🚨</span> Crowd Alert</h1>
                    <div class="severity-badge">{severity} SEVERITY</div>
                </div>

                <div class="content">
                    <div class="info-row">
                        <div class="info-label">Camera</div>
                        <div class="info-value">{camera_name}</div>
                    </div>

                    <div class="info-row">
                        <div class="info-label">Location</div>
                        <div class="info-value">{location}</div>
                    </div>

                    <div class="info-row">
                        <div class="info-label">Time</div>
                        <div class="info-value">{ts_str}</div>
                    </div>

                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">People Detected</div>
                            <div class="stat-value">{people_count}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Density Level</div>
                            <div class="stat-value">{density_level}</div>
                        </div>
                    </div>

                    <div class="alert-box">
                        <strong>⚠️ Alert Reason:</strong> {trigger_reason}
                    </div>
                </div>

                <div class="footer">
                    <p style="margin: 0 0 10px 0; color: #6c757d; font-size: 14px;">
                        Please check the live dashboard for real-time updates
                    </p>
                    <a href="http://10.51.200.71" class="button">View Dashboard</a>
                    <p style="margin: 20px 0 0 0; color: #adb5bd; font-size: 12px;">
                        CrowdVision Alert System | Automated Detection
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _split_whatsapp_numbers(self, raw_numbers: Optional[str]) -> list[str]:
        if not raw_numbers:
            return []
        return [part.strip() for part in str(raw_numbers).replace(";", ",").split(",") if part.strip()]

    def _whatsapp_service_keys_for_alert(
        self,
        alert_data: Dict[str, Any],
        template_id: str,
    ) -> list[str]:
        booking_office_id = (
            os.getenv(
                "MSG91_WHATSAPP_BOOKING_OFFICE_TEMPLATE_ID",
                getattr(self.settings, "msg91_whatsapp_booking_office_template_id", ""),
            )
            or ""
        ).strip()
        crowd_id = (
            os.getenv(
                "MSG91_WHATSAPP_CROWD_ALERT_TEMPLATE_ID",
                getattr(self.settings, "msg91_whatsapp_crowd_alert_template_id", ""),
            )
            or ""
        ).strip()
        alert_category = str(alert_data.get("alert_category") or "").strip().lower()

        service_keys = []
        is_booking_office = alert_category == "booking_office_diversion" or (
            booking_office_id and template_id == booking_office_id
        )

        is_island = alert_category == "island_footfall_risk"

        if is_booking_office:
            service_keys.append("msg91_whatsapp_booking_office_template_id")
        elif is_island:
            service_keys.append("msg91_whatsapp_island_alert_template_id")
        elif alert_category == "fob_congestion":
            service_keys.extend([
                "msg91_whatsapp_fob_alert_template_id",
                "msg91_whatsapp_crowd_alert_template_id",
                "msg91_custom_whatsapp_message_template_id"
            ])
        elif crowd_id and template_id == crowd_id:
            service_keys.append("msg91_whatsapp_crowd_alert_template_id")
        elif template_id:
            service_keys.append("msg91_whatsapp_crowd_alert_template_id")
        if not (is_booking_office or is_island) and str(alert_data.get("custom_whatsapp_message") or "").strip():
            service_keys.append("msg91_custom_whatsapp_message_template_id")

        return list(dict.fromkeys(service_keys))

    async def _resolve_whatsapp_recipients(
        self,
        alert_data: Dict[str, Any],
        template_id: str,
    ) -> list[str]:
        service_keys = self._whatsapp_service_keys_for_alert(alert_data, template_id)
        if service_keys:
            try:
                from modules.users import UsersManager

                user_recipients = await UsersManager.get_whatsapp_numbers_for_services(service_keys)
                if user_recipients:
                    return user_recipients
                logger.info(
                    "No eligible WhatsApp recipients found in viewers_user_collection for services=%s",
                    service_keys,
                )
                return []
            except Exception as exc:
                logger.warning(
                    "Failed to resolve WhatsApp recipients from users collection: %s",
                    exc,
                )
                return []

        logger.info(
            "No WhatsApp service mapping found for alert_id=%s template_id=%s; skipping recipient resolution",
            alert_data.get("alert_id"),
            template_id,
        )
        return []

    def _get_msg91_credentials(self) -> tuple[Optional[str], Optional[str]]:
        auth_key = os.getenv("MSG91_AUTH_KEY") or getattr(self.settings, 'msg91_auth_key', None)
        integrated_number = os.getenv("MSG91_WHATSAPP_NUMBER") or getattr(self.settings, 'msg91_whatsapp_number', None)

        if not auth_key or not integrated_number:
            from dotenv import dotenv_values
            env_dict = dotenv_values(".env")
            auth_key = auth_key or env_dict.get("MSG91_AUTH_KEY")
            integrated_number = integrated_number or env_dict.get("MSG91_WHATSAPP_NUMBER")

        return auth_key, integrated_number

    def _build_msg91_template_bulk_payload(
        self, to_number: str, template_id: str, integrated_number: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        components_dict = {
            f"body_{k}": {"type": "text", "value": str(variables[k]), "parameter_name": str(k)}
            for k in sorted(variables.keys(), key=lambda x: int(x) if x.isdigit() else x)
        }
        to_component = {"to": [to_number], "components": components_dict}
        return {
            "integrated_number": integrated_number,
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "type": "template",
                "template": {
                    "name": template_id,
                    "language": {"code": "en", "policy": "deterministic"},
                    "namespace": os.getenv("MSG91_WHATSAPP_NAMESPACE", "0f13edef_771b_422d_bb6e_1e7123702fd4"),
                    "to_and_components": [to_component]
                }
            }
        }

    def _build_msg91_template_payload(self, to_number: str, template_id: str, integrated_number: str) -> Dict[str, Any]:
        return {
            "integrated_number": integrated_number,
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_number,
                "type": "template",
                "template": {
                    "name": template_id,
                    "language": {"code": "en", "policy": "deterministic"},
                    "components": []
                }
            }
        }

    def _build_msg91_text_payload(self, to_number: str, integrated_number: str, fallback_text: str) -> Dict[str, Any]:
        return {
            "integrated_number": integrated_number,
            "content_type": "text",
            "payload": {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_number,
                "type": "text",
                "text": {"preview_url": False, "body": fallback_text}
            }
        }

    def _build_msg91_request(
        self, to_number: str, template_id: str, variables: Optional[Dict[str, Any]],
        fallback_text: str, integrated_number: str
    ) -> tuple[str, Dict[str, Any]]:
        base_url = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/"
        if not template_id:
            return base_url, self._build_msg91_text_payload(to_number, integrated_number, fallback_text)
        if variables:
            bulk_url = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
            return bulk_url, self._build_msg91_template_bulk_payload(to_number, template_id, integrated_number, variables)
        return base_url, self._build_msg91_template_payload(to_number, template_id, integrated_number)

    def _send_msg91_whatsapp(self, to_number: str, template_id: str, variables: Optional[Dict[str, Any]], fallback_text: str) -> Dict[str, Any]:
        auth_key, integrated_number = self._get_msg91_credentials()

        if not all([auth_key, integrated_number]):
            return {"status": "error", "error": "Missing MSG91 auth key or integrated number"}

        headers = {
            "authkey": auth_key,
            "accept": CONTENT_TYPE_JSON,
            "content-type": CONTENT_TYPE_JSON
        }
        url, payload = self._build_msg91_request(to_number, template_id, variables, fallback_text, integrated_number)

        try:
            response = requests.post(url, json=payload, headers=headers)
            response_data = response.json()
            if response.status_code in [200, 202] and response_data.get("hasError") is False:
                return {"status": "sent", "sid": response_data.get("messageId", "msg91-success")}
            else:
                logger.error(f"MSG91 error: {response_data}")
                return {"status": "error", "error": str(response_data)}
        except Exception as e:
            logger.exception("MSG91 request failed")
            return {"status": "error", "error": str(e)}

    def _check_whatsapp_cooldown(self, alert_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        import time
        camera_id = alert_data.get('camera_id')
        now = time.time()
        last_time = self._last_whatsapp_time.get(camera_id, 0.0)
        cooldown = alert_data.get("whatsapp_cooldown_seconds")
        if cooldown is None:
            cooldown = getattr(self.settings, "whatsapp_alert_cooldown_seconds", 1800.0)
        if (now - last_time) < cooldown:
            remaining = int(cooldown - (now - last_time))
            logger.info(f"Skipping WhatsApp for {camera_id}: Cooldown active ({remaining}s remaining)")
            return {"status": "skipped", "error": f"Cooldown active ({remaining}s remaining)"}
        self._last_whatsapp_time[camera_id] = now
        return None

    def _resolve_whatsapp_template_id(self, alert_data: Dict[str, Any]) -> str:
        return alert_data.get("whatsapp_template_id") or alert_data.get("whatsapp_content_sid") or os.getenv(
            "MSG91_WHATSAPP_CROWD_ALERT_TEMPLATE_ID",
            getattr(self.settings, 'msg91_whatsapp_crowd_alert_template_id', '')
        ) or ''

    async def send_whatsapp_alert(self, alert_data: Dict[str, Any], skip_checks: bool = False) -> Dict[str, Any]:
        """
        Send a WhatsApp alert using MSG91.
        Reads credentials and numbers from environment variables or settings.
        """
        if alert_data.get("send_whatsapp") is False:
            return {"status": "skipped", "error": "WhatsApp disabled for this alert"}

        if not skip_checks:
            cooldown_result = self._check_whatsapp_cooldown(alert_data)
            if cooldown_result is not None:
                return cooldown_result

        auth_key, integrated_number = self._get_msg91_credentials()
        if not auth_key or not integrated_number:
            logger.error("MSG91 credentials not configured")
            return {"status": "error", "error": "MSG91 credentials not configured"}

        template_id = self._resolve_whatsapp_template_id(alert_data)

        if template_id == "camera_alert":
            severity = str(alert_data.get('severity', 'UNKNOWN')).strip().upper()
            if severity != "CRITICAL":
                logger.info(f"Skipping WhatsApp crowd alert for {alert_data.get('camera_id')}: Severity {severity} is not CRITICAL.")
                return {"status": "skipped", "error": f"Crowd Alert requires CRITICAL severity, got {severity}"}

        receivers = await self._resolve_whatsapp_recipients(alert_data, template_id)

        if not receivers:
            logger.info("Skipping WhatsApp alert: no eligible sendAlerts=True users with matching services.")
            return {
                "status": "skipped",
                "error": "No eligible sendAlerts=True users with matching services",
            }

        message = self._format_whatsapp_body(alert_data)

        results = [
            self._send_whatsapp_to_recipient(number, template_id, alert_data, message)
            for number in receivers
        ]
        return {'results': results}

    @staticmethod
    def _normalize_whatsapp_number(value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        return cleaned.replace("whatsapp:", "").replace("+", "")

    def _build_whatsapp_template_variables(self, alert_data: Dict[str, Any]) -> Dict[str, str]:
        if "whatsapp_template_variables" in alert_data:
            return {str(k): str(v) for k, v in alert_data["whatsapp_template_variables"].items()}

        timestamp = alert_data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', ISO_UTC_SUFFIX))
            except ValueError:
                pass
        if isinstance(timestamp, datetime):
            ist_time = timestamp + timedelta(hours=5, minutes=30)
            ts_str = ist_time.strftime(IST_TIMESTAMP_FORMAT)
        else:
            ts_str = str(timestamp)

        camera_id = alert_data.get('camera_id', 'Unknown')
        return {
            "var_1": str(alert_data.get('location', 'Unknown')),
            "var_2": str(ts_str),
            "var_3": str(alert_data.get('camera_name', camera_id)),
            "var_4": str(alert_data.get('severity', 'UNKNOWN')),
            "var_5": str(alert_data.get('people_count', 0)),
            "var_6": str(alert_data.get('density_level') or alert_data.get('density', 'N/A')),
            "var_7": str(alert_data.get('trigger_reason', THRESHOLD_EXCEEDED)),
        }

    def _send_whatsapp_to_recipient(
        self, number: str, template_id: str, alert_data: Dict[str, Any], message: str
    ) -> Dict[str, Any]:
        to_number = self._normalize_whatsapp_number(number)
        try:
            variables = None
            if template_id:
                logger.info(f"WhatsApp crowd alert using MSG91 template: {template_id}")
                variables = self._build_whatsapp_template_variables(alert_data)
                logger.debug(
                    "[WhatsApp] Sending MSG91 template message: template_id=%s, variables=%s",
                    template_id, json.dumps(variables)
                )

            response_result = self._send_msg91_whatsapp(to_number, template_id, variables, message)

            if response_result.get("status") == "sent":
                logger.info(f"WhatsApp alert sent to {number}: {response_result.get('sid')}")
                return {'number': number, 'status': 'sent', 'sid': response_result.get('sid')}

            if template_id:
                logger.warning(f"WhatsApp template send failed for {number}; falling back to text body")
                response_result = self._send_msg91_whatsapp(to_number, "", None, message)
                if response_result.get("status") == "sent":
                    return {'number': number, 'status': 'sent', 'sid': response_result.get('sid')}

            return {'number': number, 'status': 'error', 'error': response_result.get("error")}
        except Exception as e:
            logger.exception("Failed to send WhatsApp alert to %s", number)
            return {'number': number, 'status': 'error', 'error': str(e)}

    def _format_whatsapp_body(self, alert_data: Dict[str, Any]) -> str:
        custom_message = str(alert_data.get("custom_whatsapp_message") or "").strip()
        if custom_message:
            return custom_message

        from datetime import timedelta
        timestamp = alert_data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', ISO_UTC_SUFFIX))
            except ValueError:
                pass
        if isinstance(timestamp, datetime):
            ist_time = timestamp + timedelta(hours=5, minutes=30)
            ts_str = ist_time.strftime(IST_TIMESTAMP_FORMAT)
        else:
            ts_str = str(timestamp)
        severity = alert_data.get('severity', 'UNKNOWN')
        camera_id = alert_data.get('camera_id', 'Unknown')
        camera_name = alert_data.get('camera_name', camera_id)
        people_count = alert_data.get('people_count', 0)
        density_level = alert_data.get('density_level') or alert_data.get('density', 'N/A')
        trigger_reason = alert_data.get('trigger_reason', THRESHOLD_EXCEEDED)
        location = alert_data.get('location', 'Unknown')
        station_code = alert_data.get("station_code") or getattr(self.settings, "station_code", "SC")
        message = (
            f"🚨 Crowd Alert\n"
            f"Station: SC\n"
            f"Location: {location}\n\n"
            f"Time: {ts_str}\n\n"
            f"Camera: {camera_name}\n\n"
            f"Severity: {severity}\n\n"
            f"People Detected: {people_count}\n"
            f"Density Level: {density_level}\n\n"
            f"Alert Reason: {trigger_reason}\n\n"
            f"Please take necessary action."
        )
        return message
