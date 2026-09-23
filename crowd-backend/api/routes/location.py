"""
WhatsApp OTP Authentication Router — MSG91 VERSION
"""

import hashlib
import logging
import secrets
import os
import math
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from db.mongodb import MongoDB
from config.config import get_settings
from services.firebase_service import FirebaseService
logger = logging.getLogger(__name__)

router = APIRouter()
logger = logging.getLogger(__name__)

settings = get_settings()

OTP_EXPIRY_MINUTES = 5
MAX_ATTEMPTS = 5
DATABASE_UNAVAILABLE_MESSAGE = "Database not available"
MONGO_FIRST_OPERATOR = "$first"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    phoneNumber: str
    latitude: float
    longitude: float
    platform: str
    accuracy: float | None = None

    @field_validator('phoneNumber')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if '+91' not in v:
            raise ValueError('Please enter the mobile number with +91 country code.')
        return v


class VerifyOTPRequest(BaseModel):
    phoneNumber: str
    otp: str


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float]


class TrackingUserRequest(BaseModel):
    phoneNumber: str
    latitude: float
    longitude: float
    platform: str


class LogoutUserRequest(BaseModel):
    phoneNumber: str


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _normalize_phone_for_msg91(phone: str) -> str:
    """Strip leading + for MSG91 (expects 91XXXXXXXXXX)."""
    return phone.lstrip("+")


def _is_master_phone(phone: str) -> bool:
    master = settings.otp_master_phone.strip()
    return bool(master) and phone.strip() == master


def _lat_lon_to_svg_coordinates(latitude: float, longitude: float) -> dict:
    """Convert latitude/longitude to SVG x,y coordinates using Web Mercator projection."""
    svg_width = 1000.0
    svg_height = 1000.0

    # Normalize longitude from [-180, 180] to [0, svg_width]
    x = (longitude + 180.0) / 360.0 * svg_width

    # Use Web Mercator projection for latitude.
    lat_rad = math.radians(latitude)
    merc_n = math.log(math.tan((math.pi / 4.0) + (lat_rad / 2.0)))
    y = (1.0 - merc_n / math.pi) / 2.0 * svg_height

    return {
        "x": round(x, 2),
        "y": round(y, 2),
    }


async def _send_otp_via_msg91(phone: str, otp: str) -> bool:
    """Send OTP via MSG91 WhatsApp template. Returns True on success."""
    auth_key = settings.msg91_auth_key
    integrated_number = settings.msg91_whatsapp_number
    template_id = settings.msg91_whatsapp_otp_template_id

    if not all([auth_key, integrated_number, template_id]):
        raise HTTPException(status_code=500, detail="MSG91 WhatsApp OTP not configured (check auth key, number, template id)")

    to_number = _normalize_phone_for_msg91(phone)

    url = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
    headers = {
        "authkey": auth_key,
        "accept": "application/json",
        "content-type": "application/json",
    }

    payload = {
        "integrated_number": integrated_number,
        "content_type": "template",
        "payload": {
            "messaging_product": "whatsapp",
            "type": "template",
            "template": {
                "name": template_id,
                "language": {"code": "en", "policy": "deterministic"},
                "namespace": os.getenv("MSG91_WHATSAPP_NAMESPACE", ""),
                "to_and_components": [
                    {
                        "to": [to_number],
                        "components": {
                            "body_1": {
                                "type": "text",
                                "value": otp,
                                "parameter_name": "1",
                            },
                            "button_1": {
                                "type": "text",
                                "value": otp,
                                "parameter_name": "1",
                                "sub_type": "url",
                                "index": "0",
                            },
                        },
                    }
                ],
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        data = resp.json()
        if resp.status_code in (200, 202) and not data.get("hasError"):
            logger.info("[OTP] MSG91 sent OTP to %s: %s", phone, data.get("messageId"))
            return True
        logger.exception("[OTP] MSG91 error for %s: %s", phone, data)
        raise HTTPException(status_code=502, detail=f"Failed to send OTP via WhatsApp: {data}")
    except HTTPException:
        raise
    except Exception:
        logger.exception("[OTP] MSG91 request failed")
        raise HTTPException(status_code=502, detail="Failed to send OTP")


# ─────────────────────────────────────────────────────────────
# RATE LIMIT
# ─────────────────────────────────────────────────────────────

async def _check_rate_limit(phone: str):
    now = _utc_now()
    window_start = now - timedelta(minutes=10)

    count = await MongoDB.database.otp_rate_limit.count_documents({
        "phoneNumber": phone,
        "requestedAt": {"$gte": window_start}
    })

    if count >= 3:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again after 10 minutes.")

    await MongoDB.database.otp_rate_limit.insert_one({
        "phoneNumber": phone,
        "requestedAt": now
    })

    await MongoDB.database.otp_rate_limit.delete_many({
        "phoneNumber": phone,
        "requestedAt": {"$lt": window_start}
    })


# ─────────────────────────────────────────────────────────────
# SEND OTP
# ─────────────────────────────────────────────────────────────

@router.post(
    "/send-otp",
    tags=["Auth"],
    responses={
        403: {"description": "Phone number not registered"},
        429: {"description": "Too many OTP requests"},
        500: {"description": "MSG91 OTP service not configured"},
        502: {"description": "Failed to send OTP via WhatsApp"},
        503: {"description": "Database not available"},
    },
)
async def send_otp(data: SendOTPRequest):
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    # Verify phone exists in viewers_user_collection
    user = await MongoDB.database.viewers_user_collection.find_one(
        {"phone": data.phoneNumber},
        {"_id": 1, "phone": 1, "name": 1}
    )
    if not user:
        raise HTTPException(status_code=403, detail="Phone number not registered. Please contact your administrator.")

    now_ist = _utc_now() + timedelta(hours=5, minutes=30)
    login_date = now_ist.strftime("%Y-%m-%d")

    # Save or update today's login-location record
    await MongoDB.database.user_locations.update_one(
        {"phoneNumber": data.phoneNumber, "loginDate": login_date},
        {
            "$set": {
                "name": user.get("name"),
                "location": {
                    "type": "Point",
                    "coordinates": [data.longitude, data.latitude],
                },
                "platform": data.platform,
                "timestamp": now_ist,
            }
        },
        upsert=True,
    )

    await _check_rate_limit(data.phoneNumber)

    is_master = _is_master_phone(data.phoneNumber)

    if is_master:
        # Master user: store fixed OTP with no expiry
        otp = settings.otp_master_code
        await MongoDB.database.otp_store.update_one(
            {"phoneNumber": data.phoneNumber},
            {
                "$set": {
                    "otpHash": _hash_otp(otp),
                    "expiresAt": None,  # never expires
                    "isMaster": True,
                    "attempts": 0,
                    "createdAt": _utc_now(),
                }
            },
            upsert=True,
        )
    else:
        otp = str(secrets.randbelow(900000) + 100000)
        expires_at = _utc_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
        await MongoDB.database.otp_store.update_one(
            {"phoneNumber": data.phoneNumber},
            {
                "$set": {
                    "otpHash": _hash_otp(otp),
                    "expiresAt": expires_at,
                    "isMaster": False,
                    "attempts": 0,
                    "createdAt": _utc_now(),
                }
            },
            upsert=True,
        )

    await _send_otp_via_msg91(data.phoneNumber, otp)

    return {
        "success": True,
        "message": "OTP sent to your WhatsApp number",
        "expires_in_minutes": None if is_master else OTP_EXPIRY_MINUTES,
    }


# ─────────────────────────────────────────────────────────────
# VERIFY OTP
# ─────────────────────────────────────────────────────────────

@router.post(
    "/verify-otp",
    tags=["Auth"],
    responses={
        400: {"description": "Invalid or expired OTP"},
        404: {"description": "No OTP found"},
        429: {"description": "Too many incorrect attempts"},
        503: {"description": "Database not available"},
    },
)
async def verify_otp(data: VerifyOTPRequest):
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    record = await MongoDB.database.otp_store.find_one({"phoneNumber": data.phoneNumber})

    if not record:
        raise HTTPException(status_code=404, detail="No OTP found. Please request a new OTP.")

    is_master = record.get("isMaster", False)

    # Expiry check — skip for master user
    if not is_master:
        expires_at = record.get("expiresAt")
        if expires_at and _utc_now() > expires_at:
            await MongoDB.database.otp_store.delete_one({"phoneNumber": data.phoneNumber})
            raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    if record.get("attempts", 0) >= MAX_ATTEMPTS:
        if not is_master:
            await MongoDB.database.otp_store.delete_one({"phoneNumber": data.phoneNumber})
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new OTP.")

    if _hash_otp(data.otp.strip()) != record["otpHash"]:
        await MongoDB.database.otp_store.update_one(
            {"phoneNumber": data.phoneNumber},
            {"$inc": {"attempts": 1}},
        )
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Mark verified
    now_ist = _utc_now() + timedelta(hours=5, minutes=30)
    await MongoDB.database.verified_users.update_one(
        {"phoneNumber": data.phoneNumber},
        {"$set": {"verified": True, "verifiedAt": now_ist}},
        upsert=True,
    )

    # For regular users delete the OTP; master users keep theirs for reuse
    if not is_master:
        await MongoDB.database.otp_store.delete_one({"phoneNumber": data.phoneNumber})

    # Generate Firebase custom token so the Flutter app can authenticate with Firebase
    firebase_token = await FirebaseService.create_custom_token(data.phoneNumber)

    response: dict = {
        "success": True,
        "message": "Phone verified successfully",
    }
    if firebase_token:
        response["firebase_token"] = firebase_token

    return response


# ─────────────────────────────────────────────────────────────
# RESEND OTP
# ─────────────────────────────────────────────────────────────

@router.post(
    "/resend-otp",
    tags=["Auth"],
    responses={
        403: {"description": "Phone number not registered"},
        429: {"description": "Too many OTP requests"},
        500: {"description": "MSG91 OTP service not configured"},
        502: {"description": "Failed to resend OTP via WhatsApp"},
        503: {"description": "Database not available"},
    },
)
async def resend_otp(data: SendOTPRequest):
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    user = await MongoDB.database.viewers_user_collection.find_one(
        {"phone": data.phoneNumber},
        {"_id": 1}
    )
    if not user:
        raise HTTPException(status_code=403, detail="Phone number not registered.")

    await _check_rate_limit(data.phoneNumber)

    is_master = _is_master_phone(data.phoneNumber)

    now_ist = _utc_now() + timedelta(hours=5, minutes=30)
    login_date = now_ist.strftime("%Y-%m-%d")

    await MongoDB.database.user_locations.update_one(
        {"phoneNumber": data.phoneNumber, "loginDate": login_date},
        {
            "$set": {
                "location": {
                    "type": "Point",
                    "coordinates": [data.longitude, data.latitude],
                },
                "platform": data.platform,
                "accuracy": data.accuracy,
                "timestamp": now_ist,
            }
        },
        upsert=True,
    )

    await MongoDB.database.otp_store.delete_one({"phoneNumber": data.phoneNumber})

    if is_master:
        otp = settings.otp_master_code
        await MongoDB.database.otp_store.insert_one({
            "phoneNumber": data.phoneNumber,
            "otpHash": _hash_otp(otp),
            "expiresAt": None,
            "isMaster": True,
            "attempts": 0,
            "createdAt": _utc_now(),
        })
    else:
        otp = str(secrets.randbelow(900000) + 100000)
        expires_at = _utc_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
        await MongoDB.database.otp_store.insert_one({
            "phoneNumber": data.phoneNumber,
            "otpHash": _hash_otp(otp),
            "expiresAt": expires_at,
            "isMaster": False,
            "attempts": 0,
            "createdAt": _utc_now(),
        })

    await _send_otp_via_msg91(data.phoneNumber, otp)

    return {
        "success": True,
        "message": "OTP resent successfully",
        "expires_in_minutes": None if is_master else OTP_EXPIRY_MINUTES,
    }


# ─────────────────────────────────────────────────────────────
# TRACK USER LOCATION
# ─────────────────────────────────────────────────────────────

@router.post(
    "/tracking-user",
    tags=["Location"],
    responses={503: {"description": "Database not available"}},
)
async def tracking_user(data: TrackingUserRequest):
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    timestamp = _utc_now() + timedelta(hours=5, minutes=30)

    tracking_data = {
        "phoneNumber": data.phoneNumber,
        "location": {
            "type": "Point",
            "coordinates": [data.longitude, data.latitude],
        },
        "platform": data.platform,
        "timestamp": timestamp,
    }

    await MongoDB.database.traking_users.insert_one(tracking_data)

    return {"success": True, "message": "User location tracked successfully"}


# ─────────────────────────────────────────────────────────────
# LOGOUT USER
# ─────────────────────────────────────────────────────────────

@router.post(
    "/logout-user",
    tags=["Location"],
    responses={503: {"description": "Database not available"}},
)
async def logout_user(data: LogoutUserRequest):
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    timestamp = _utc_now() + timedelta(hours=5, minutes=30)

    await MongoDB.database.user_logouts.insert_one({
        "phoneNumber": data.phoneNumber,
        "logoutAt": timestamp,
        "status": "logged_out",
    })

    return {"success": True, "message": "User logout event recorded successfully"}


# ─────────────────────────────────────────────────────────────
# GET ALL LOCATIONS
# ─────────────────────────────────────────────────────────────

@router.get(
    "/location/all",
    tags=["Location"],
    responses={503: {"description": "Database not available"}},
)
async def get_all_locations():
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    cursor = MongoDB.database.user_locations.find({}).sort("timestamp", -1)
    docs = await cursor.to_list(length=None)

    for doc in docs:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        location = doc.get("location") or {}
        coordinates = location.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2:
            longitude, latitude = coordinates
            doc["svgCordinates"] = _lat_lon_to_svg_coordinates(latitude, longitude)

    return {"count": len(docs), "locations": docs}


# ─────────────────────────────────────────────────────────────
# GET TRACKING DATA FOR TODAY'S LOGGED-IN USERS
# ─────────────────────────────────────────────────────────────

@router.get(
    "/tracking-user",
    tags=["Location"],
    responses={503: {"description": "Database not available"}},
)
async def get_tracking_data():
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    # Get today's date in IST timezone
    now_ist = _utc_now() + timedelta(hours=5, minutes=30)
    today_date = now_ist.strftime("%Y-%m-%d")

    # Get phone numbers of users who logged in today from user_locations using loginDate
    logged_in_today = await MongoDB.database.user_locations.find({
        "loginDate": today_date
    }).to_list(length=None)

    phone_numbers = [doc["phoneNumber"] for doc in logged_in_today if "phoneNumber" in doc]
    name_by_phone = {
        doc["phoneNumber"]: doc.get("name")
        for doc in logged_in_today
        if "phoneNumber" in doc
    }

    if not phone_numbers:
        return {"count": 0, "tracking": []}

    # Look up gender for these phone numbers from the users collection
    user_docs = await MongoDB.database.viewers_user_collection.find(
        {"phone": {"$in": phone_numbers}},
        {"phone": 1, "gender": 1},
    ).to_list(length=None)
    gender_by_phone = {doc["phone"]: doc.get("gender") for doc in user_docs}

    # Aggregate to get the latest tracking data for each phone number
    pipeline = [
        {"$match": {"phoneNumber": {"$in": phone_numbers}}},
        {"$sort": {"phoneNumber": 1, "timestamp": -1}},
        {"$group": {
            "_id": "$phoneNumber",
            "phoneNumber": {MONGO_FIRST_OPERATOR: "$phoneNumber"},
            "coordinates": {MONGO_FIRST_OPERATOR: "$location.coordinates"},
            "timestamp": {MONGO_FIRST_OPERATOR: "$timestamp"},
        }},
    ]

    results = await MongoDB.database.traking_users.aggregate(pipeline).to_list(length=None)

    # Convert to desired format with SVG coordinates
    tracking_data = []
    for doc in results:
        if doc.get("coordinates") and len(doc["coordinates"]) == 2:
            longitude, latitude = doc["coordinates"]
            svg_coords = _lat_lon_to_svg_coordinates(latitude, longitude)

            tracking_data.append({
                "phoneNumber": doc["phoneNumber"],
                "name": name_by_phone.get(doc["phoneNumber"]),
                "gender": gender_by_phone.get(doc["phoneNumber"]),
                "coordinates": {
                    "longitude": longitude,
                    "latitude": latitude,
                },
                "timestamp": doc["timestamp"],
                "svgCoordinates": svg_coords,
            })

    return {"count": len(tracking_data), "tracking": tracking_data}
