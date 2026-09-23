import os
import re
import base64
import json
import logging
import boto3
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv
from gtts import gTTS
from fastapi import APIRouter, HTTPException, Depends, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import UTC, datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import json_util
from db.mongodb import MongoDB
from services.firebase_service import FirebaseService
from services.live_train_service import LiveTrainService
from services.train_data_service import TrainDataService
from config.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/announcements", tags=["Announcements"])

load_dotenv()

try:
    from sarvam import SarvamAI  # type: ignore
except Exception:
    try:
        from sarvamai import SarvamAI  # type: ignore
    except Exception:
        SarvamAI = None


RECENT_ANNOUNCEMENTS_API_TOKEN = "Tride@2025"


def require_recent_announcements_token(
    x_api_token: Optional[str] = Header(default=None, alias="X-API-Token")
):
    if not x_api_token or x_api_token.strip() != RECENT_ANNOUNCEMENTS_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )

# ================== AWS S3 ==================

def get_aws_s3_config():
    """Resolve AWS S3 bucket/region, falling back to a fresh .env read
    if the process-level env vars are missing (mirrors MSG91's fallback pattern).
    Credentials are intentionally NOT resolved here - S3 access relies solely on
    the AWS credentials available via the environment/IAM role (see get_s3_client)."""
    bucket = os.getenv("AWS_S3_BUCKET")
    region = os.getenv("AWS_REGION")

    if not bucket or not region:
        from dotenv import dotenv_values
        env_dict = dotenv_values(".env")
        bucket = bucket or env_dict.get("AWS_S3_BUCKET")
        region = region or env_dict.get("AWS_REGION")

    return bucket, region


def get_s3_client(region: str):
    """Create an S3 client using AWS credentials resolved by boto3's default
    credential chain (e.g. IAM role/instance profile) - no static keys used."""
    return boto3.client("s3", region_name=region)

TTS_PROVIDER = "gtts"  # Hardcoded to bypass Sarvam API
# SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
_sarvam_client = None  # Disabled Sarvam client


BULBUL_V2_MODEL = "bulbul:v2"
BULBUL_V3_MODEL = "bulbul:v3"
BULBUL_V3_BETA_MODEL = "bulbul:v3-beta"


def _normalize_sarvam_tts_model(raw_model: Optional[str]) -> str:
    allowed = {BULBUL_V2_MODEL, BULBUL_V3_BETA_MODEL, BULBUL_V3_MODEL}
    if not raw_model:
        return BULBUL_V3_MODEL

    model = raw_model.strip().lower()
    if model in allowed:
        return model

    compact = re.sub(r"[^a-z0-9]+", "", model)
    synonyms = {
        "bulbulv2": BULBUL_V2_MODEL,
        "bulbul:v2": BULBUL_V2_MODEL,
        "bulbulv3": BULBUL_V3_MODEL,
        "bulbul:v3": BULBUL_V3_MODEL,
        "bulbulv3beta": BULBUL_V3_BETA_MODEL,
        "bulbul:v3beta": BULBUL_V3_BETA_MODEL,
        "bulbul:v3-beta": BULBUL_V3_BETA_MODEL,
    }
    normalized = synonyms.get(compact) or synonyms.get(model)
    return normalized if normalized in allowed else BULBUL_V3_MODEL


# SARVAM_TTS_MODEL = _normalize_sarvam_tts_model(os.getenv("SARVAM_TTS_MODEL"))
SARVAM_TTS_MODEL = BULBUL_V3_MODEL
# SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER") or "vidya"
SARVAM_TTS_SPEAKER = "manisha"
# try:
#     SARVAM_TTS_PACE = float(os.getenv("SARVAM_TTS_PACE") or "1.0")
# except Exception:
#     SARVAM_TTS_PACE = 1.0
SARVAM_TTS_PACE = 1.0

AWS_S3_CONFIG_MISSING_ERROR = "AWS S3 configuration missing (AWS_S3_BUCKET/AWS_REGION)"
AWS_CREDENTIALS_NOT_FOUND_ERROR = "AWS credentials not found"
JN_TO_JUNCTION_PATTERN = r'\bjn\b\.?'
DATABASE_NOT_AVAILABLE_ERROR = "Database not available"


# ================== SCHEMA ==================
class AnnouncementResponse(BaseModel):
    train_number: str
    audio_url: str
    announcement_text: str
    platform: str
    delay_minutes: int
    status: str


class StoredAnnouncementResponse(BaseModel):
    train_number: str
    train_name: str
    schedule_date: str
    station_code: str
    arrival: Optional[Dict[str, str]] = None
    departure: Optional[Dict[str, str]] = None
    delay: Optional[Dict[str, str]] = None
    general: Optional[Dict[str, str]] = None
    i18n: Optional[Dict[str, Any]] = None


class StoredAnnouncementI18nResponse(BaseModel):
    train_number: str
    train_name: str
    schedule_date: str
    station_code: str
    arrival: Dict[str, Dict[str, str]]
    dep: Dict[str, Dict[str, str]]
    delay: Dict[str, Dict[str, str]]
    general: Dict[str, Dict[str, str]]


class PlatformAnnouncementRequest(BaseModel):
    train_number: str
    train_name: str = ""
    source: str
    destination: str
    platform_number: str
    languages: Optional[List[str]] = None


class PlatformAnnouncementResponse(BaseModel):
    train_number: str
    messages: Dict[str, str]
    audio_urls: Dict[str, str]


LANGUAGE_CONFIG: Dict[str, Dict[str, str]] = {
    "english": {"language_code": "en-IN", "speaker": "manisha", "suffix": "en", "tts_lang": "en"},
    "hin": {"language_code": "hi-IN", "speaker": "manisha", "suffix": "hi", "tts_lang": "hi"},
    "tel": {"language_code": "te-IN", "speaker": "manisha", "suffix": "te", "tts_lang": "te"},
}


PLATFORM_ANNOUNCEMENT_TEMPLATES: Dict[str, str] = {
    "english": (
        "Attention passengers, train number {train_number} from {source} to {destination} "
        "will come on platform {platform_number}. Please go to platform {platform_number} as per your coach number."
    ),
    "hin": (
        "ध्यान दें यात्रियों, ट्रेन नंबर {train_number} {source} से {destination} के लिए "
        "प्लेटफॉर्म नंबर {platform_number} पर आएगी। कृपया अपने कोच नंबर के अनुसार प्लेटफॉर्म {platform_number} पर जाएं।"
    ),
    "tel": (
        "ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {train_number} {source} నుంచి {destination} కి "
        "ప్లాట్‌ఫామ్ {platform_number} కి వస్తుంది. దయచేసి మీ కోచ్ నంబర్ ప్రకారం ప్లాట్‌ఫామ్ {platform_number} కి వెళ్లండి."
    ),
}


def _normalize_language_keys(languages: Optional[List[str]]) -> List[str]:
    if not languages:
        return ["english", "hin", "tel"]

    synonyms = {
        "en": "english",
        "eng": "english",
        "english": "english",
        "hi": "hin",
        "hin": "hin",
        "hindi": "hin",
        "te": "tel",
        "tel": "tel",
        "telugu": "tel",
    }

    normalized: List[str] = []
    seen = set()
    for raw in languages:
        if not raw:
            continue
        key = synonyms.get(raw.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized or ["english", "hin", "tel"]


# ================== LOCALIZATION HELPERS ==================

# Digit words per language
_DIGIT_WORDS: Dict[str, Dict[str, str]] = {
    "eng": {
        "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    },
    "hin": {
        "0": "शून्य", "1": "एक", "2": "दो", "3": "तीन", "4": "चार",
        "5": "पांच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ",
    },
    "tel": {
        "0": "సున్నా", "1": "ఒకటి", "2": "రెండు", "3": "మూడు", "4": "నాలుగు",
        "5": "ఐదు", "6": "ఆరు", "7": "ఏడు", "8": "ఎనిమిది", "9": "తొమ్మిది",
    },
}

# Number words for minutes (0-59 cover all practical delay & minute-to-departure values)
_NUMBER_WORDS_EN: Dict[int, str] = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    21: "twenty one", 22: "twenty two", 23: "twenty three", 24: "twenty four", 25: "twenty five",
    26: "twenty six", 27: "twenty seven", 28: "twenty eight", 29: "twenty nine", 30: "thirty",
    31: "thirty one", 32: "thirty two", 33: "thirty three", 34: "thirty four", 35: "thirty five",
    36: "thirty six", 37: "thirty seven", 38: "thirty eight", 39: "thirty nine", 40: "forty",
    41: "forty one", 42: "forty two", 43: "forty three", 44: "forty four", 45: "forty five",
    46: "forty six", 47: "forty seven", 48: "forty eight", 49: "forty nine", 50: "fifty",
    51: "fifty one", 52: "fifty two", 53: "fifty three", 54: "fifty four", 55: "fifty five",
    56: "fifty six", 57: "fifty seven", 58: "fifty eight", 59: "fifty nine", 60: "sixty",
}

_NUMBER_WORDS_HI: Dict[int, str] = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पांच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 30: "तीस",
    31: "इकतीस", 32: "बत्तीस", 33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस",
    36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस", 40: "चालीस",
    41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस", 44: "चौवालीस", 45: "पैंतालीस",
    46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस", 49: "उनचास", 50: "पचास",
    51: "इक्यावन", 52: "बावन", 53: "तिरपन", 54: "चौवन", 55: "पचपन",
    56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन", 59: "उनसठ", 60: "साठ",
}

_NUMBER_WORDS_TE: Dict[int, str] = {
    0: "సున్నా", 1: "ఒకటి", 2: "రెండు", 3: "మూడు", 4: "నాలుగు", 5: "ఐదు",
    6: "ఆరు", 7: "ఏడు", 8: "ఎనిమిది", 9: "తొమ్మిది", 10: "పది",
    11: "పదకొండు", 12: "పన్నెండు", 13: "పదమూడు", 14: "పదనాలుగు", 15: "పదిహేను",
    16: "పదహారు", 17: "పదిహేడు", 18: "పదెనిమిది", 19: "పందొమ్మిది", 20: "ఇరవై",
    21: "ఇరవై ఒకటి", 22: "ఇరవై రెండు", 23: "ఇరవై మూడు", 24: "ఇరవై నాలుగు", 25: "ఇరవై ఐదు",
    26: "ఇరవై ఆరు", 27: "ఇరవై ఏడు", 28: "ఇరవై ఎనిమిది", 29: "ఇరవై తొమ్మిది", 30: "ముప్పై",
    31: "ముప్పై ఒకటి", 32: "ముప్పై రెండు", 33: "ముప్పై మూడు", 34: "ముప్పై నాలుగు", 35: "ముప్పై ఐదు",
    36: "ముప్పై ఆరు", 37: "ముప్పై ఏడు", 38: "ముప్పై ఎనిమిది", 39: "ముప్పై తొమ్మిది", 40: "నలభై",
    41: "నలభై ఒకటి", 42: "నలభై రెండు", 43: "నలభై మూడు", 44: "నలభై నాలుగు", 45: "నలభై ఐదు",
    46: "నలభై ఆరు", 47: "నలభై ఏడు", 48: "నలభై ఎనిమిది", 49: "నలభై తొమ్మిది", 50: "యాభై",
    51: "యాభై ఒకటి", 52: "యాభై రెండు", 53: "యాభై మూడు", 54: "యాభై నాలుగు", 55: "యాభై ఐదు",
    56: "యాభై ఆరు", 57: "యాభై ఏడు", 58: "యాభై ఎనిమిది", 59: "యాభై తొమ్మిది", 60: "అరవై",
}


def _number_to_words(n: int, lang: str) -> str:
    """Convert an integer to spoken words in the given language (eng/hin/tel)."""
    if lang == "hin":
        table = _NUMBER_WORDS_HI
    elif lang == "tel":
        table = _NUMBER_WORDS_TE
    else:
        table = _NUMBER_WORDS_EN

    if n in table:
        return table[n]

    # Fallback: digit-by-digit for large numbers
    digit_words = _DIGIT_WORDS.get(lang, _DIGIT_WORDS["eng"])
    return " ".join(digit_words.get(ch, ch) for ch in str(n))


FALLBACK_KEY_ON_TIME = "on time"
HINDI_SHORTLY_WORD = "जल्द ही"
TELUGU_SHORTLY_WORD = "త్వరలో"


def _resolve_time_fallback(normalized: str, safe_lang: str, fallback_map: Dict[str, Dict[str, str]]) -> Optional[str]:
    """Match a normalized fallback keyword (any language) to its target-language word."""
    fb = fallback_map.get(safe_lang, fallback_map["eng"])
    for k, v in fb.items():
        if normalized in {k, v}:
            return v
    return None


def _time_period_key(hour: int) -> str:
    """Time-of-day bucket: morning 05-11, afternoon 12-16, evening 17-18, else night."""
    if 3 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 16 < hour <= 18:
        return "evening"
    return "night"


def _format_localized_time(safe_lang: str, hour_word: str, minute_word: str, period_word: str, minute: int) -> str:
    if safe_lang == "hin":
        # Hindi: period first, then time — "सुबह आठ बजे" / "दोपहर दो बजकर तीस मिनट"
        if minute == 0:
            return f"{period_word} {hour_word} बजे"
        return f"{period_word} {hour_word} बजकर {minute_word} मिनट"
    if safe_lang == "tel":
        # Telugu: period first, then time — "ఉదయం ఎనిమిది గంటలకు" / "సాయంత్రం రెండు గంటల ముప్పై నిమిషాలకు"
        if minute == 0:
            return f"{period_word} {hour_word} గంటలకు"
        return f"{period_word} {hour_word} గంటల {minute_word} నిమిషాలకు"
    # English: time first, period after — "eight o'clock in the morning" / "two thirty in the afternoon"
    if minute == 0:
        return f"{hour_word} o'clock {period_word}"
    return f"{hour_word} {minute_word} {period_word}"


def _localize_time(time_str: str, lang: str) -> str:
    """
    Convert a time string like "14:30" or "9:05" into a fully spoken
    representation in the given language (eng/hin/tel).

    Handles:
      - "HH:MM" → spoken hour and minute words
      - Fallback strings like "shortly" / "जल्दी" / "త్వరలో" passed through unchanged
        after translation to the correct language.
    """
    fallback_map: Dict[str, Dict[str, str]] = {
        "eng": {"shortly": "shortly", FALLBACK_KEY_ON_TIME: FALLBACK_KEY_ON_TIME},
        "hin": {"shortly": HINDI_SHORTLY_WORD, FALLBACK_KEY_ON_TIME: "समय पर"},
        "tel": {"shortly": TELUGU_SHORTLY_WORD, FALLBACK_KEY_ON_TIME: "సమయానికి"},
    }
    safe_lang = (lang or "eng").strip().lower()
    normalized = (time_str or "").strip().lower()

    # If it is a known fallback keyword (in any language), return the target-language version
    eng_fallbacks = {"shortly", FALLBACK_KEY_ON_TIME, HINDI_SHORTLY_WORD, "समय पर", "त्वरलो", "तvaralo",
                     "त्वरालो", "సమయానికి", TELUGU_SHORTLY_WORD, "jaldi hi", "tvaralo"}
    if normalized in eng_fallbacks or not re.match(r"^\d{1,2}:\d{2}$", normalized):
        fallback = _resolve_time_fallback(normalized, safe_lang, fallback_map)
        return fallback if fallback is not None else time_str  # Unknown fallback – return as-is

    # Parse HH:MM (24-hour input) → convert to 12-hour
    try:
        h, m = [int(x) for x in time_str.split(":")]
    except ValueError:
        return time_str

    # Convert to 12-hour clock
    h12 = h % 12 or 12  # 0 → 12, 13 → 1, etc.

    hour_word = _number_to_words(h12, safe_lang)
    minute_word = _number_to_words(m, safe_lang)

    period_labels: Dict[str, Dict[str, str]] = {
        "eng": {
            "morning":   "in the morning",
            "afternoon": "in the afternoon",
            "evening":   "in the evening",
            "night":     "at night",
        },
        "hin": {
            "morning":   "सुबह",
            "afternoon": "दोपहर",
            "evening":   "शाम",
            "night":     "रात",
        },
        "tel": {
            "morning":   "ఉదయం",
            "afternoon": "మధ్యాహ్నం",
            "evening":   "సాయంత్రం",
            "night":     "రాత్రి",
        },
    }
    period_word = period_labels.get(safe_lang, period_labels["eng"])[_time_period_key(h)]

    return _format_localized_time(safe_lang, hour_word, minute_word, period_word, m)


def _localize_minutes(n: int, lang: str) -> str:
    """Return spoken minute count + unit word in the given language."""
    safe_lang = (lang or "eng").strip().lower()
    word = _number_to_words(n, safe_lang)
    if safe_lang == "hin":
        return f"{word} मिनट"
    elif safe_lang == "tel":
        return f"{word} నిమిషాలు"
    else:
        unit = "minute" if n == 1 else "minutes"
        return f"{word} {unit}"


def _train_number_for_language(train_number: str, lang_key: str) -> str:
    """Convert a train/platform number to digit-by-digit spoken words for the given language."""
    digits = str(train_number or "").strip()
    words = _DIGIT_WORDS.get((lang_key or "").strip().lower(), _DIGIT_WORDS["eng"])
    return " ".join(words.get(ch, ch) for ch in digits)


# ================== ENDPOINT ==================

@router.post(
    "/platform",
    response_model=PlatformAnnouncementResponse,
    responses={
        400: {"description": "Unsupported language(s) requested"},
        500: {"description": "AWS S3 misconfiguration, missing AWS credentials, or audio generation/upload failure"},
    },
)
async def generate_platform_announcement(payload: PlatformAnnouncementRequest):
    bucket, region = get_aws_s3_config()
    if not bucket or not region:
        raise HTTPException(status_code=500, detail=AWS_S3_CONFIG_MISSING_ERROR)

    language_keys = _normalize_language_keys(payload.languages)
    unsupported = [k for k in language_keys if k not in LANGUAGE_CONFIG or k not in PLATFORM_ANNOUNCEMENT_TEMPLATES]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported languages: {', '.join(unsupported)}. Supported: english, hin, tel",
        )

    messages: Dict[str, str] = {}
    audio_urls: Dict[str, str] = {}
    spoken_train_number = payload.train_number  # fallback
    
    # Clean up source and destination names (Replace Jn with Junction)
    payload.source = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', payload.source or "", flags=re.IGNORECASE).strip().title()
    payload.destination = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', payload.destination or "", flags=re.IGNORECASE).strip().title()

    for lang_key in language_keys:
        # Map platform language keys to i18n keys for digit words
        lang_i18n_key = {"english": "eng", "hin": "hin", "tel": "tel"}.get(lang_key, "eng")
        spoken_train_number = _train_number_for_language(payload.train_number, lang_i18n_key)
        spoken_platform = _train_number_for_language(payload.platform_number, lang_i18n_key)

        msg = PLATFORM_ANNOUNCEMENT_TEMPLATES[lang_key].format(
            train_number=spoken_train_number,
            train_name=(payload.train_name or "").strip(),
            source=payload.source,
            destination=payload.destination,
            platform_number=spoken_platform,
        ).replace("  ", " ").strip()

        config = LANGUAGE_CONFIG[lang_key]
        messages[lang_key] = msg
        audio_urls[lang_key] = _generate_audio_and_upload_multilang(
            msg,
            payload.train_number,
            f"platform_{config['suffix']}",
            lang=config["tts_lang"],
            speaker=config["speaker"],
        )

    return PlatformAnnouncementResponse(
        train_number=spoken_train_number,
        messages=messages,
        audio_urls=audio_urls,
    )


def _parse_api_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    if not date_str or not time_str:
        return None
    if "day" in time_str.lower():
        return None
    try:
        base = datetime.strptime(date_str, "%d-%m-%Y")
        h, m = time_str.split(":")
        return base.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return None


def _generate_audio_and_upload(text: str, train_number: str, suffix: str) -> str:
    return _generate_audio_and_upload_multilang(text, train_number, suffix, lang="en")


_SARVAM_TARGET_LANGUAGE_BY_LANG = {
    "en": "en-IN",
    "hi": "hi-IN",
    "te": "te-IN",
}


def _resolve_use_sarvam() -> bool:
    """Whether to use Sarvam TTS, falling back to gTTS if requested but unconfigured."""
    use_sarvam = TTS_PROVIDER == "sarvam" or (TTS_PROVIDER == "auto" and _sarvam_client is not None)
    if use_sarvam and _sarvam_client is None:
        logger.warning(
            "Sarvam TTS requested but not configured (missing sarvamai install and/or SARVAM_API_KEY). Falling back to gTTS."
        )
        return False
    return use_sarvam


def _extract_sarvam_audio_bytes(sarvam_resp: Any) -> bytes:
    """Pull raw audio bytes out of a Sarvam TTS response, whatever shape it comes in."""
    if isinstance(sarvam_resp, (bytes, bytearray)):
        return bytes(sarvam_resp)
    if hasattr(sarvam_resp, "audios"):
        combined_audio = "".join(getattr(sarvam_resp, "audios") or [])
        return base64.b64decode(combined_audio) if combined_audio else b""
    if isinstance(sarvam_resp, dict) and "audios" in sarvam_resp:
        combined_audio = "".join(sarvam_resp.get("audios") or [])
        return base64.b64decode(combined_audio) if combined_audio else b""
    raise ValueError(f"Unexpected Sarvam TTS response type: {type(sarvam_resp)}")


def _upload_audio_to_s3(s3_client, file_name: str, bucket: str, s3_key: str, content_type: str, log_label: str) -> None:
    logger.info(f"Uploading {log_label} audio to S3: bucket={bucket}, key={s3_key}")
    try:
        s3_client.upload_file(file_name, bucket, s3_key, ExtraArgs={"ContentType": content_type})
    except Exception:
        logger.exception(f"S3 Upload failed for {log_label}")
        raise
    logger.info(f"Successfully uploaded {log_label} audio to S3: {s3_key}")


def _generate_via_sarvam(
    text: str, train_number: str, suffix: str, safe_lang: str, speaker: Optional[str],
    bucket: str, region: str, s3_client,
) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    target_language_code = _SARVAM_TARGET_LANGUAGE_BY_LANG.get(safe_lang, "en-IN")
    file_name = f"announcement_{train_number}_{suffix}_{safe_lang}_{timestamp}.wav"
    try:
        sarvam_resp = _sarvam_client.text_to_speech.convert(
            text=text,
            target_language_code=target_language_code,
            speaker=speaker or SARVAM_TTS_SPEAKER,
            model=SARVAM_TTS_MODEL,
            pace=SARVAM_TTS_PACE,
        )

        audio_bytes = _extract_sarvam_audio_bytes(sarvam_resp)
        if not audio_bytes:
            raise ValueError("Empty audio returned by Sarvam TTS")

        with open(file_name, "wb") as audio_file:
            audio_file.write(audio_bytes)

        s3_key = f"announcements/{file_name}"
        _upload_audio_to_s3(s3_client, file_name, bucket, s3_key, "audio/wav", "Sarvam TTS")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        raise HTTPException(status_code=500, detail=AWS_CREDENTIALS_NOT_FOUND_ERROR)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {str(e)}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)


def _generate_via_gtts(
    text: str, train_number: str, suffix: str, safe_lang: str,
    bucket: str, region: str, s3_client,
) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    file_name = f"announcement_{train_number}_{suffix}_{safe_lang}_{timestamp}.mp3"
    try:
        try:
            tts = gTTS(text=text, lang=safe_lang)
            tts.save(file_name)
        except Exception:
            logger.exception("gTTS audio generation failed")
            raise

        s3_key = f"announcements/{file_name}"
        _upload_audio_to_s3(s3_client, file_name, bucket, s3_key, "audio/mpeg", "gTTS fallback")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        raise HTTPException(status_code=500, detail=AWS_CREDENTIALS_NOT_FOUND_ERROR)
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)


def _generate_audio_and_upload_multilang(
    text: str,
    train_number: str,
    suffix: str,
    *,
    lang: str = "en",
    speaker: Optional[str] = None,
) -> str:
    safe_lang = (lang or "en").strip().lower()

    bucket, region = get_aws_s3_config()
    if not bucket or not region:
        raise HTTPException(status_code=500, detail=AWS_S3_CONFIG_MISSING_ERROR)
    s3_client = get_s3_client(region)

    if _resolve_use_sarvam():
        return _generate_via_sarvam(text, train_number, suffix, safe_lang, speaker, bucket, region, s3_client)

    return _generate_via_gtts(text, train_number, suffix, safe_lang, bucket, region, s3_client)


async def _get_live_api_data(train_number: str, schedule_date_dt: datetime, scheduled_arrival_dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch live train status.
    Optimization: First check 'train_data' collection which stores full RapidAPI payloads.
    Fallback: Fetch from RapidAPI if not found or incomplete.
    """
    settings = get_settings()
    station_code_target = settings.live_train_station_code

    # 1. Try fetching from 'train_data' (complete payload store)
    api_data = await TrainDataService.get_record(train_number, schedule_date_dt, station_code_target)
    
    if api_data:
        payload = api_data.get("api_payload", {})
        if isinstance(payload, dict):
            # Reconstruct the structure expected by callers
            stations = (payload.get("data") or {}).get("stations") or []
            found_station = None
            for s in stations:
                if s.get("code") == station_code_target:
                    found_station = s
                    break
            
            if found_station:
                # Map fields to match LiveTrainService response structure
                return {
                    "train_number": train_number,
                    "station_code": station_code_target,
                    "platform": found_station.get("platform", ""),
                    "platform_number": found_station.get("platform", ""),
                    "actual_arrival": found_station.get("arrival_actual"),
                    "actual_departure": found_station.get("departure_actual"),
                    "delay_minutes": api_data.get("delay_minutes", 0),
                    "delay_status": api_data.get("delay_status"),
                    "api_response_raw": found_station,
                    "api_payload": payload
                }

    return None



def _extract_stations_from_payload(api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = api_data.get("api_payload", {}) if isinstance(api_data, dict) else {}
    if not isinstance(payload, dict):
        return []
    data_block = payload.get("data") or {}
    if not isinstance(data_block, dict):
        return []
    raw_stations = data_block.get("stations") or payload.get("stations") or []
    if not isinstance(raw_stations, list):
        return []
    return [s for s in raw_stations if isinstance(s, dict)]


def _source_dest_from_stations(stations: List[Dict[str, Any]]) -> tuple:
    """Strictly consider the first station as source, last station as destination."""
    if not stations:
        return "", ""
    first_station = stations[0]
    last_station = stations[-1]
    # Use name if available and not empty, otherwise fallback to code
    source = str(first_station.get("name") or first_station.get("code") or "").strip().rstrip("~")
    destination = str(last_station.get("name") or last_station.get("code") or "").strip().rstrip("~")
    return source, destination


def _source_dest_from_train_doc(train_doc: Dict[str, Any]) -> tuple:
    source = str(
        train_doc.get("source")
        or train_doc.get("src")
        or train_doc.get("source_station")
        or train_doc.get("route_source")
        or ""
    ).strip()
    destination = str(
        train_doc.get("destination")
        or train_doc.get("dest")
        or train_doc.get("destination_station")
        or train_doc.get("route_destination")
        or ""
    ).strip()
    return source, destination


def _extract_train_name(train_doc: Dict[str, Any], api_data: Dict[str, Any]) -> str:
    payload = api_data.get("api_payload", {}) if isinstance(api_data, dict) else {}
    if isinstance(payload, dict):
        data_block = payload.get("data") or {}
        if isinstance(data_block, dict):
            train_name = str(data_block.get("train_name") or "").strip()
            if train_name:
                return train_name
    return str(train_doc.get("train_name") or "").strip()


def _parse_source_dest_from_train_name(train_name: str) -> tuple:
    """Parse 'Source - Destination Express' style train names."""
    if not train_name or " - " not in train_name:
        return None, None
    parts = train_name.split(" - ", 1)
    if len(parts) != 2:
        return None, None
    parsed_source = parts[0].strip()
    # Remove common suffixes like "Express", "Express Train", etc.
    parsed_dest = re.sub(
        r'\s+(Express|Express Train|Passenger|Mail|Superfast|Shatabdi|Rajdhani|Duronto|Jan Shatabdi|'
        r'Garib Rath|Sampark Kranti|Antyodaya|Tejas|Uday|Double Decker|Humsafar|Vande Bharat| Gatimaan)$',
        '', parts[1].strip(), flags=re.IGNORECASE,
    ).strip()
    return parsed_source, parsed_dest


def _resolve_route_endpoints(train_doc: Dict[str, Any], api_data: Dict[str, Any]) -> tuple:
    """Returns (source, destination) as raw English station name strings."""
    stations = _extract_stations_from_payload(api_data)
    source, destination = _source_dest_from_stations(stations)

    # Fallback to train_doc if payload provided no names
    if not source or not destination:
        fallback_source, fallback_destination = _source_dest_from_train_doc(train_doc)
        source = source or fallback_source
        destination = destination or fallback_destination

    # Fallback: parse train_name if available (format: "Source - Destination Express")
    if not source or not destination:
        train_name = _extract_train_name(train_doc, api_data)
        parsed_source, parsed_destination = _parse_source_dest_from_train_name(train_name)
        source = source or parsed_source or ""
        destination = destination or parsed_destination or ""

    # Replace 'Jn' with 'Junction' for clearer announcements
    source = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', source, flags=re.IGNORECASE).strip()
    destination = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', destination, flags=re.IGNORECASE).strip()

    # Title case for better presentation in announcements
    return (source or "N/A").title(), (destination or "N/A").title()


def _resolve_route_path(train_doc: Dict[str, Any], api_data: Dict[str, Any]) -> str:
    """Returns 'Source to Destination' English string (kept for backward compat)."""
    src, dst = _resolve_route_endpoints(train_doc, api_data)
    return f"{src} to {dst}"


# ================== I18N LANG CONFIG ==================

I18N_LANG_CONFIG: Dict[str, Dict[str, str]] = {
    "tel": {"tts_lang": "te", "speaker": "manisha", "suffix": "te"},
    "hin": {"tts_lang": "hi", "speaker": "manisha", "suffix": "hi"},
    "eng": {"tts_lang": "en", "speaker": "manisha", "suffix": "en"},
}


# ================== STATION NAME TRANSLITERATION ==================

# In-memory cache: (station_name_lower, lang_code) -> transliterated string
_station_transliteration_cache: Dict[tuple, str] = {}

# Connector words for route path per language
_ROUTE_CONNECTOR: Dict[str, str] = {
    "eng": "to",
    "hin": "से",
    "tel": "నుండి",
}


def _transliterate_station(name: str, target_lang_code: str) -> str:
    """
    Transliterate an English station name into the target script using Sarvam AI.
    Falls back to the original name if Sarvam is unavailable or fails.
    target_lang_code: "hi-IN" | "te-IN" | "en-IN"
    """
    if not name or name in ("N/A",):
        return name
    if target_lang_code == "en-IN":
        return name  # No transliteration needed for English

    cache_key = (name.strip().lower(), target_lang_code)
    if cache_key in _station_transliteration_cache:
        return _station_transliteration_cache[cache_key]

    if _sarvam_client is None:
        logger.warning("Sarvam client not available; using raw station name for TTS.")
        return name

    try:
        resp = _sarvam_client.text.transliterate(
            input=name.strip(),
            source_language_code="en-IN",
            target_language_code=target_lang_code,
        )
        # The Sarvam transliterate response has an `output` field
        result = (getattr(resp, "output", None) or "").strip() or name
        _station_transliteration_cache[cache_key] = result
        return result
    except Exception:
        logger.warning(f"Sarvam transliteration failed for '{name}' → {target_lang_code}; using raw name.")
        _station_transliteration_cache[cache_key] = name
        return name


def _localize_route(source: str, destination: str, lang: str) -> str:
    """
    Return a fully localized 'Source <connector> Destination' string.
    Station names are transliterated into the target script.
    lang: "eng" | "hin" | "tel"
    """
    lang_code_map = {"eng": "en-IN", "hin": "hi-IN", "tel": "te-IN"}
    target_code = lang_code_map.get(lang, "en-IN")

    src_local = _transliterate_station(source, target_code)
    dst_local = _transliterate_station(destination, target_code)
    connector = _ROUTE_CONNECTOR.get(lang, "to")

    return f"{src_local} {connector} {dst_local}"


# ================== MESSAGE BUILDER (ENGLISH ONLY - LEGACY) ==================

def _build_messages(
    train_number: str,
    route_path: str,
    station_name: str,
    platform: str,
    delay_minutes: int,
    arrival_time: str,
    departure_time: str,
    minutes_to_dep: Optional[int],
) -> Dict[str, str]:
    """Build English-only announcement messages (legacy/simple path)"""
    
    spoken_tn = train_number.replace(" ", " ").strip()
    spoken_pf = platform
    dep_soon = f"in {minutes_to_dep} minutes" if minutes_to_dep else "shortly"
    
    return {
        "arrival": (
            f"Attention passengers. Train number {spoken_tn}, {route_path}, "
            f"is now arriving on platform {spoken_pf} at {arrival_time}. "
            f"Please stand back from the platform edge."
        ),
        "departure": (
            f"Passengers of train number {spoken_tn}, {route_path}, "
            f"departing from platform {spoken_pf} at {departure_time}, "
            f"please board the train. Doors are closing."
        ),
        "delay": (
            f"Train number {spoken_tn}, {route_path}, "
            f"is running {delay_minutes} minutes late."
        ),
        "general": (
            f"Train number {spoken_tn}, {route_path}, expected {dep_soon}."
        ),
    }


# ================== MESSAGE BUILDER (FULLY LOCALIZED) ==================

def _build_platform_change_messages_i18n(
    train_number: str,
    source: str,
    destination: str,
    station_name: str,
    platform: str,
) -> Dict[str, str]:
    """Build a dedicated multilingual platform-change announcement message."""
    route_en = _localize_route(source, destination, "eng")
    route_hi = _localize_route(source, destination, "hin")
    route_te = _localize_route(source, destination, "tel")

    spoken_tn_en = _train_number_for_language(train_number, "eng")
    spoken_tn_hi = _train_number_for_language(train_number, "hin")
    spoken_tn_te = _train_number_for_language(train_number, "tel")

    spoken_pf_en = _train_number_for_language(platform, "eng")
    spoken_pf_hi = _train_number_for_language(platform, "hin")
    spoken_pf_te = _train_number_for_language(platform, "tel")

    station_hi = _transliterate_station(station_name, "hi-IN")
    station_te = _transliterate_station(station_name, "te-IN")
# platform change
    english = (
        f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
        f"has changed platform and is now arriving at platform {spoken_pf_en}. "
        f"Please proceed to platform {spoken_pf_en} as per your coach number."
    )
    hindi = (
        f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
        f"प्लेटफॉर्म बदल चुकी है और अब प्लेटफॉर्म नंबर {spoken_pf_hi} पर है। "
        f"कृपया अपने कोच नंबर के अनुसार प्लेटफॉर्म {spoken_pf_hi} पर जाएं।"
    )
    telugu = (
        f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
        f"ప్లాట్‌ఫామ్ మార్చబడింది మరియు ఇప్పుడు ప్లాట్‌ఫామ్ {spoken_pf_te} వద్ద ఉంది. "
        f"దయచేసి మీ కోచ్ నంబర్ ప్రకారం ప్లాట్‌ఫామ్ {spoken_pf_te} కి వెళ్లండి."
    )

    return {
        "english": english,
        "hin": hindi,
        "tel": telugu,
    }


def _build_messages_i18n(
    train_number: str,
    source: str,
    destination: str,
    station_name: str,
    platform: str,
    delay_minutes: int,
    arrival_time: str,
    departure_time: str,
    minutes_to_dep: Optional[int],
    route_path: str = "",  # kept for backward compat; ignored when source/destination provided
) -> Dict[str, Dict[str, str]]:
    """
    Build announcement text for all three languages.
    Every numeric value (time, delay, platform, minutes) is fully spoken
    in the target language — no raw digits or English units leak into Hindi/Telugu.
    Station names are transliterated into the target script via Sarvam AI.
    """
    # Localize route path per language (transliterates station names)
    route_en = _localize_route(source, destination, "eng")
    route_hi = _localize_route(source, destination, "hin")
    route_te = _localize_route(source, destination, "tel")

    # ── spoken train number ──────────────────────────────────────────────────
    spoken_tn_en = _train_number_for_language(train_number, "eng")
    spoken_tn_hi = _train_number_for_language(train_number, "hin")
    spoken_tn_te = _train_number_for_language(train_number, "tel")

    # ── spoken platform ──────────────────────────────────────────────────────
    spoken_pf_en = _train_number_for_language(platform, "eng")
    spoken_pf_hi = _train_number_for_language(platform, "hin")
    spoken_pf_te = _train_number_for_language(platform, "tel")

    # ── spoken times (fully localized) ──────────────────────────────────────
    arr_time_en = _localize_time(arrival_time, "eng")
    arr_time_hi = _localize_time(arrival_time, "hin")
    arr_time_te = _localize_time(arrival_time, "tel")

    dep_time_en = _localize_time(departure_time, "eng")
    dep_time_hi = _localize_time(departure_time, "hin")
    dep_time_te = _localize_time(departure_time, "tel")

    # ── spoken delay ────────────────────────────────────────────────────────
    delay_en = _localize_minutes(delay_minutes, "eng")
    delay_hi = _localize_minutes(delay_minutes, "hin")
    delay_te = _localize_minutes(delay_minutes, "tel")

    # ── minutes to departure ─────────────────────────────────────────────────
    if minutes_to_dep is not None:
        dep_in_en = _localize_minutes(minutes_to_dep, "eng")
        dep_in_hi = _localize_minutes(minutes_to_dep, "hin")
        dep_in_te = _localize_minutes(minutes_to_dep, "tel")
        dep_soon_en = f"in {dep_in_en}"
        dep_soon_hi = f"{dep_in_hi} में"
        dep_soon_te = f"{dep_in_te} లో"
    else:
        dep_soon_en = "shortly"
        dep_soon_hi = HINDI_SHORTLY_WORD
        dep_soon_te = TELUGU_SHORTLY_WORD

    # ── transliterated current station name ──────────────────────────────────
    station_hi = _transliterate_station(station_name, "hi-IN")
    station_te = _transliterate_station(station_name, "te-IN")

    # ── ARRIVAL ─────────────────────────────────────────────────────────────
    arrival_text_en = (
        f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
        f"is now arriving on platform {spoken_pf_en} at {arr_time_en}. "
        f"Please stand back from the platform edge."
    )
    arrival_text_hi = (
        f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
        f"प्लेटफॉर्म नंबर {spoken_pf_hi} पर {arr_time_hi} पर आ रही है। "
        f"कृपया प्लेटफॉर्म के किनारे से पीछे हटें।"
    )
    arrival_text_te = (
        f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
        f"ప్లాట్‌ఫామ్ {spoken_pf_te} కి {arr_time_te} కు వస్తోంది. "
        f"దయచేసి ప్లాట్‌ఫామ్ అంచు నుండి వెనుకకు తగ్గండి."
    )

    # ── DEPARTURE ────────────────────────────────────────────────────────────
    departure_text_en = (
        f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
        f"will depart from platform {spoken_pf_en} at {dep_time_en}. "
        f"Please go to platform {spoken_pf_en} as per your coach number."
    )
    departure_text_hi = (
        f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
        f"प्लेटफॉर्म नंबर {spoken_pf_hi} से {dep_time_hi} पर प्रस्थान करेगी। "
        f"कृपया अपने कोच नंबर के अनुसार प्लेटफॉर्म {spoken_pf_hi} पर जाएं।"
    )
    departure_text_te = (
        f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
        f"ప్లాట్‌ఫామ్ {spoken_pf_te} నుండి {dep_time_te} కు బయలుదేరుతుంది. "
        f"దయచేసి మీ కోచ్ నంబర్ ప్రకారం ప్లాట్‌ఫామ్ {spoken_pf_te} కి వెళ్లండి."
    )

    # ── DELAY ────────────────────────────────────────────────────────────────
    if delay_minutes > 0:
        delay_text_en = (
            f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
            f"is running approximately {delay_en} late. "
            f"Expected arrival time is {arr_time_en}. "
            f"Please go to platform {spoken_pf_en} as per your coach number. "
            f"We regret the inconvenience caused."
        )
        delay_text_hi = (
            f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
            f"लगभग {delay_hi} की देरी से चल रही है। "
            f"अनुमानित आगमन समय {arr_time_hi} है। "
            f"कृपया अपने कोच नंबर के अनुसार प्लेटफॉर्म {spoken_pf_hi} पर जाएं। "
            f"असुविधा के लिए खेद है।"
        )
        delay_text_te = (
            f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
            f"సుమారు {delay_te} ఆలస్యంగా నడుస్తోంది. "
            f"అంచనా రాక సమయం {arr_time_te}. "
            f"దయచేసి మీ కోచ్ నంబర్ ప్రకారం ప్లాట్‌ఫామ్ {spoken_pf_te} కి వెళ్లండి. "
            f"అసౌకర్యానికి చింతిస్తున్నాము."
        )
    else:
        delay_text_en = (
            f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
            f"is running on time and will arrive at {arr_time_en}. "
            f"Please go to platform {spoken_pf_en} as per your coach number."
        )
        delay_text_hi = (
            f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
            f"समय पर चल रही है और {arr_time_hi} पर पहुंचेगी। "
            f"कृपया अपने कोच नंबर के अनुसार प्लेटफॉर्म {spoken_pf_hi} पर जाएं।"
        )
        delay_text_te = (
            f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
            f"సమయానికి నడుస్తోంది మరియు {arr_time_te} కు చేరుకుంటుంది. "
            f"దయచేసి మీ కోచ్ నంబర్ ప్రకారం ప్లాట్‌ఫామ్ {spoken_pf_te} కి వెళ్లండి."
        )

    # ── GENERAL ──────────────────────────────────────────────────────────────
    general_text_en = (
        f"Attention passengers. Train number {spoken_tn_en}, {route_en} Express, "
        f"is currently at {station_name} station. "
        f"Please check station displays for updates."
    )
    general_text_hi = (
        f"ध्यान दें यात्रियों, ट्रेन नंबर {spoken_tn_hi}, {route_hi} एक्सप्रेस, "
        f"वर्तमान में {station_hi} स्टेशन पर है। "
        f"कृपया अपडेट के लिए स्टेशन डिस्प्ले देखें।"
    )
    general_text_te = (
        f"ప్రయాణికులకు గమనిక, ట్రైన్ నంబర్ {spoken_tn_te}, {route_te} ఎక్స్‌ప్రెస్, "
        f"ప్రస్తుతం {station_te} స్టేషన్ వద్ద ఉంది. "
        f"తాజా సమాచారం కోసం స్టేషన్ డిస్ప్లేలను చూడండి."
    )

    return {
        "arrival": {"eng": arrival_text_en, "hin": arrival_text_hi, "tel": arrival_text_te},
        "dep":     {"eng": departure_text_en, "hin": departure_text_hi, "tel": departure_text_te},
        "delay":   {"eng": delay_text_en, "hin": delay_text_hi, "tel": delay_text_te},
        "general": {"eng": general_text_en, "hin": general_text_hi, "tel": general_text_te},
    }


def _build_multilingual_audio_block_i18n(
    category_texts: Dict[str, str],
    train_number: str,
    category_name: str,
) -> Dict[str, Dict[str, str]]:
    response: Dict[str, Dict[str, str]] = {}

    for lang_key, text in category_texts.items():
        config = I18N_LANG_CONFIG[lang_key]
        audio_url = _generate_audio_and_upload_multilang(
            text,
            train_number,
            f"{category_name}_{config['suffix']}",
            lang=config["tts_lang"],
            speaker=config["speaker"],
        )
        response[lang_key] = {"text": text, "audiourl": audio_url}

    return response


def _train_number_for_tts(train_number: str) -> str:
    """Convert a train number into English digit-by-digit spoken form for TTS."""
    return _train_number_for_language(train_number, "eng")


def _serialize_mongo_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_mongo_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_mongo_value(v) for v in value]
    return value


def _serialize_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: _serialize_mongo_value(v) for k, v in doc.items()}
    if "_id" in out:
        out["_id"] = str(out["_id"])
    return out


async def _publish_recent_announcements_snapshot() -> List[Dict[str, Any]]:
    """Publish the same recent-announcements window used by /announcements/recent.

    Only trains whose platform actually CHANGED (not first-time assignment) in
    the current fetch cycle are pushed to Firebase. A new train being assigned
    a platform for the first time does NOT get published. MongoDB
    (train_announcements) keeps storing every train as before; this filtering
    only applies to the Firebase snapshot.
    """
    if MongoDB.database is None:
        return []

    now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    window_start = now - timedelta(hours=1)

    cursor = MongoDB.database.train_announcements.find(
        {"updated_at": {"$gte": window_start, "$lte": now}}
    ).sort("updated_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    serialized_docs = json.loads(json_util.dumps(docs))

    current_cycle = LiveTrainService._get_current_fetch_cycle()
    platform_changed_keys = set()
    alerts_cursor = MongoDB.database.live_train_alerts.find(
        {
            "alert-type": "platform",
            "fetch_cycle": current_cycle,
            "alert_type": "platform_change",
        },
        {"train_number": 1, "schedule_date": 1, "station_code": 1},
    )
    async for alert in alerts_cursor:
        schedule_date = alert.get("schedule_date")
        schedule_date_str = (
            schedule_date.strftime("%Y-%m-%d") if isinstance(schedule_date, datetime) else str(schedule_date)
        )
        platform_changed_keys.add(
            (str(alert.get("train_number")), schedule_date_str, str(alert.get("station_code")))
        )

    def _matches_platform_change(doc: Dict[str, Any]) -> bool:
        schedule_date = doc.get("schedule_date")
        schedule_date_str = (
            schedule_date.get("$date", "")[:10] if isinstance(schedule_date, dict) else str(schedule_date)[:10]
        )
        return (
            str(doc.get("train_number")), schedule_date_str, str(doc.get("station_code"))
        ) in platform_changed_keys

    filtered_docs = [doc for doc in serialized_docs if _matches_platform_change(doc)]

    await FirebaseService.publish_recent_announcements(filtered_docs)
    return serialized_docs


async def _clear_legacy_firebase_recent_snapshots(fallback_station_code: str) -> None:
    """Clear old station-scoped recent announcement snapshots."""
    station_codes = {fallback_station_code}

    if MongoDB.database is not None:
        try:
            station_codes.update(
                str(station_code).strip()
                for station_code in await MongoDB.database.train_announcements.distinct("station_code")
                if station_code
            )
        except Exception as exc:
            logger.warning("Failed to list recent announcement station codes for Firebase cleanup: %s", exc)

    for station_code in station_codes:
        await FirebaseService.clear_station_recent_announcements(station_code)


async def _clear_firebase_congestion_snapshots(fallback_station_code: str) -> None:
    """Clear API-shaped congestion plus old station-scoped congestion snapshots."""
    station_codes = {fallback_station_code}

    if MongoDB.database is not None:
        try:
            station_ids = await MongoDB.database.congestion_alerts.distinct("station_id")
            station_codes.update(str(station_id).strip() for station_id in station_ids if station_id)
        except Exception as exc:
            logger.warning("Failed to list congestion station IDs for Firebase cleanup: %s", exc)

    await FirebaseService.publish_congestion(None)

    # Compatibility cleanup for older Firebase path shape:
    # stations/{station_code}/announcements/congestion
    for station_code in station_codes:
        await FirebaseService.clear_station_congestion(station_code)


# ================== ANNOUNCEMENT RUN LOGGER ==================

class AnnouncementRunLogger:
    """
    Writes a single structured log document to `logs_announcements` collection.
    One document per /next-hour run; each train gets its own nested entry inside `trains`.
    Call log_step() to append a step entry, flush() to persist to MongoDB.
    """

    def __init__(self):
        self._run_id: str = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        self._started_at: datetime = datetime.now(UTC)
        self._run_steps: list = []       # top-level pipeline steps
        self._trains: Dict[str, Any] = {}  # keyed by train_number

    def _ts(self) -> datetime:
        return datetime.now(UTC)

    # ── top-level (non-train) steps ──────────────────────────────────────────

    def info(self, step: str, message: str, **extra):
        entry = {"step": step, "level": "INFO", "message": message, "ts": self._ts()}
        entry.update(extra)
        self._run_steps.append(entry)
        logger.info("[ANN-LOG][%s] %s", step, message)

    def error(self, step: str, message: str, **extra):
        entry = {"step": step, "level": "ERROR", "message": message, "ts": self._ts()}
        entry.update(extra)
        self._run_steps.append(entry)
        logger.error("[ANN-LOG][%s] %s", step, message)

    # ── per-train steps ───────────────────────────────────────────────────────

    def train_info(self, train_number: str, step: str, message: str, **extra):
        entry = {"step": step, "level": "INFO", "message": message, "ts": self._ts()}
        entry.update(extra)
        self._trains.setdefault(train_number, {"steps": []})["steps"].append(entry)
        logger.info("[ANN-LOG][%s][%s] %s", train_number, step, message)

    def train_error(self, train_number: str, step: str, message: str, **extra):
        entry = {"step": step, "level": "ERROR", "message": message, "ts": self._ts()}
        entry.update(extra)
        self._trains.setdefault(train_number, {"steps": []})["steps"].append(entry)
        logger.error("[ANN-LOG][%s][%s] %s", train_number, step, message)

    # ── persist ───────────────────────────────────────────────────────────────

    async def flush(self):
        if MongoDB.database is None:
            logger.warning("[ANN-LOG] MongoDB not available – skipping log flush.")
            return
        try:
            doc = {
                "run_id": self._run_id,
                "started_at": self._started_at,
                "finished_at": datetime.now(UTC),
                "steps": self._run_steps,
                "trains": self._trains,
            }
            await MongoDB.database.logs_announcements.insert_one(doc)
            logger.info("[ANN-LOG] Run log flushed to logs_announcements (run_id=%s)", self._run_id)
        except Exception:
            logger.exception("[ANN-LOG] Failed to flush run log")


# ================== ENDPOINTS ==================

@router.post(
    "/next-hour",
    response_model=List[StoredAnnouncementResponse],
    responses={
        500: {"description": "AWS S3 misconfiguration or audio generation/upload failure"},
        503: {"description": DATABASE_NOT_AVAILABLE_ERROR},
    },
)
async def _query_trains_in_window(now: datetime, window_end: datetime) -> tuple:
    """Query train_schedules for arrivals in [now, window_end], deduped by (train_number, schedule_date)."""
    arriving_cursor = MongoDB.database.train_schedules.find(
        {"arrival_time": {"$gte": now, "$lte": window_end}}
    )
    arriving = await arriving_cursor.to_list(length=500)

    trains_map: Dict[str, Dict[str, Any]] = {}
    for train in arriving:
        key = f"{train['train_number']}_{train['schedule_date'].strftime('%Y-%m-%d')}"
        if key not in trains_map:
            trains_map[key] = train

    trains = list(trains_map.values())
    print(f"Found {len(trains)} trains to process for announcements.")
    return trains, len(arriving)


async def _fetch_live_data_for_announcement(
    train_number: str, schedule_date: datetime, scheduled_arrival_dt: Optional[datetime], _log,
) -> Optional[Dict[str, Any]]:
    """STEP 2: fetch live API data for one train; returns None if the train should be skipped."""
    _log.train_info(train_number, "STEP_2_LIVE_DATA", "Fetching live API data",
                    schedule_date=schedule_date.strftime("%Y-%m-%d"),
                    scheduled_arrival=scheduled_arrival_dt.isoformat() if scheduled_arrival_dt else None)
    try:
        api_data = await _get_live_api_data(train_number, schedule_date, scheduled_arrival_dt)
    except Exception as _exc:
        _log.train_error(train_number, "STEP_2_LIVE_DATA", f"Exception fetching live data: {_exc}")
        return None

    if not api_data:
        _log.train_error(train_number, "STEP_2_LIVE_DATA",
                         "No live data returned – train skipped (not found in train_data collection)")
        return None

    _log.train_info(train_number, "STEP_2_LIVE_DATA", "Live data fetched successfully",
                    station_code=api_data.get("station_code"),
                    platform=api_data.get("platform_number"),
                    delay_minutes=api_data.get("delay_minutes"))
    return api_data


def _extract_announcement_fields(train: Dict[str, Any], api_data: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """STEP 3: derive station/platform/delay/route fields from live data."""
    station_raw = api_data.get("api_response_raw", {}) or {}
    station_name = station_raw.get("name", "") or station_raw.get("station_name", "Unknown")
    station_name = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', station_name, flags=re.IGNORECASE).strip().title()
    station_code = api_data.get("station_code", "")
    platform = str(api_data.get("platform_number") or station_raw.get("platform") or "unknown")
    delay_minutes = int(api_data.get("delay_minutes", 0))

    api_payload = api_data.get("api_payload", {}) or {}
    start_date = (api_payload.get("data", {}) or {}).get("start_date", "")
    arrival_time = station_raw.get("arrival_actual") or station_raw.get("arrival_scheduled") or "shortly"
    departure_time = station_raw.get("departure_actual") or station_raw.get("departure_scheduled") or "shortly"

    dep_dt = _parse_api_datetime(start_date, departure_time)
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    minutes_to_dep = int((dep_dt - now_naive).total_seconds() / 60) if dep_dt and dep_dt > now_naive else None
    route_source, route_destination = _resolve_route_endpoints(train, api_data)
    route_path = f"{route_source} to {route_destination}"  # English, kept for legacy _build_messages

    return {
        "station_name": station_name,
        "station_code": station_code,
        "platform": platform,
        "delay_minutes": delay_minutes,
        "arrival_time": arrival_time,
        "departure_time": departure_time,
        "minutes_to_dep": minutes_to_dep,
        "route_source": route_source,
        "route_destination": route_destination,
        "route_path": route_path,
    }


def _build_i18n_block_for_train(
    train_number: str, fields: Dict[str, Any], _log, include_platform_change: bool = False,
) -> Dict[str, Any]:
    """STEP 4: build multilingual announcement texts + audio."""
    _log.train_info(train_number, "STEP_4_BUILD_I18N", "Building multilingual announcement texts + audio")
    try:
        texts_i18n = _build_messages_i18n(
            train_number=train_number,
            source=fields["route_source"],
            destination=fields["route_destination"],
            station_name=fields["station_name"],
            platform=fields["platform"],
            delay_minutes=fields["delay_minutes"],
            arrival_time=fields["arrival_time"],
            departure_time=fields["departure_time"],
            minutes_to_dep=fields["minutes_to_dep"],
        )
        i18n_block = {
            "arrival": _build_multilingual_audio_block_i18n(texts_i18n["arrival"], train_number, "arrival"),
            "dep": _build_multilingual_audio_block_i18n(texts_i18n["dep"], train_number, "dep"),
            "delay": _build_multilingual_audio_block_i18n(texts_i18n["delay"], train_number, "delay") if fields["delay_minutes"] > 0 else {},
            "general": _build_multilingual_audio_block_i18n(texts_i18n["general"], train_number, "general"),
        }
        if include_platform_change:
            i18n_block["platform_change"] = _build_platform_change_block_i18n(
                train_number, fields["route_source"], fields["route_destination"],
                fields["station_name"], fields["platform"],
            )
        _log.train_info(train_number, "STEP_4_BUILD_I18N", "i18n messages + audio built successfully")
        return i18n_block
    except Exception as _exc:
        _log.train_error(train_number, "STEP_4_BUILD_I18N", f"Failed to build i18n block: {_exc}")
        raise


def _build_english_texts(train_number: str, fields: Dict[str, Any], _log) -> Dict[str, str]:
    """STEP 5: build English announcement texts."""
    _log.train_info(train_number, "STEP_5_BUILD_ENGLISH", "Building English announcement texts")
    try:
        texts = _build_messages(
            train_number=train_number,
            route_path=fields["route_path"],
            station_name=fields["station_name"],
            platform=fields["platform"],
            delay_minutes=fields["delay_minutes"],
            arrival_time=fields["arrival_time"],
            departure_time=fields["departure_time"],
            minutes_to_dep=fields["minutes_to_dep"],
        )
        _log.train_info(train_number, "STEP_5_BUILD_ENGLISH", "English texts built successfully")
        return texts
    except Exception as _exc:
        _log.train_error(train_number, "STEP_5_BUILD_ENGLISH", f"Failed to build English messages: {_exc}")
        raise


def _generate_english_audio(train_number: str, texts: Dict[str, str], delay_minutes: int, _log) -> Dict[str, Optional[str]]:
    """STEP 6: generate audio via gTTS and upload to S3 for each message."""
    _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "Generating audio via gTTS and uploading to S3")
    try:
        arrival_audio = _generate_audio_and_upload(texts["arrival"], train_number, "arrival")
        _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "Arrival audio uploaded", url=arrival_audio)

        departure_audio = _generate_audio_and_upload(texts["departure"], train_number, "departure")
        _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "Departure audio uploaded", url=departure_audio)

        delay_audio = None
        if delay_minutes > 0:
            delay_audio = _generate_audio_and_upload(texts["delay"], train_number, "delay")
            _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "Delay audio uploaded", url=delay_audio)
        else:
            _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "Delay audio skipped (no delay)")

        general_audio = _generate_audio_and_upload(texts["general"], train_number, "general")
        _log.train_info(train_number, "STEP_6_GENERATE_AUDIO", "General audio uploaded", url=general_audio)
    except Exception as _exc:
        _log.train_error(train_number, "STEP_6_GENERATE_AUDIO", f"Audio generation/upload failed: {_exc}")
        raise

    return {"arrival": arrival_audio, "departure": departure_audio, "delay": delay_audio, "general": general_audio}


async def _train_platform_changed_this_cycle(
    train_number: str, schedule_date: datetime, station_code: str,
) -> bool:
    """Whether RapidAPI reported a real platform CHANGE (not first-time assignment)
    for this train/schedule/station in the current hourly fetch cycle.

    Reuses the same live_train_alerts records the WhatsApp platform-change
    alert relies on, so announcement generation and alerting agree on what
    counts as a "change".
    """
    if MongoDB.database is None:
        return False
    current_cycle = LiveTrainService._get_current_fetch_cycle()
    existing = await MongoDB.database.live_train_alerts.find_one(
        {
            "alert-type": "platform",
            "alert_type": "platform_change",
            "fetch_cycle": current_cycle,
            "train_number": str(train_number),
            "schedule_date": schedule_date,
            "station_code": str(station_code),
        },
        {"_id": 1},
    )
    return existing is not None


def _build_platform_change_messages_by_i18n_key(
    train_number: str, route_source: str, route_destination: str, station_name: str, platform: str,
) -> Dict[str, str]:
    """Build platform-change messages keyed by I18N_LANG_CONFIG keys (eng/hin/tel)."""
    messages = _build_platform_change_messages_i18n(
        train_number=train_number,
        source=route_source,
        destination=route_destination,
        station_name=station_name,
        platform=platform,
    )
    return {"eng": messages["english"], "hin": messages["hin"], "tel": messages["tel"]}


def _build_platform_change_block_i18n(
    train_number: str, route_source: str, route_destination: str, station_name: str, platform: str,
) -> Dict[str, Dict[str, str]]:
    """Part of STEP 7: build the platform-change text + audio block, same shape as
    the arrival/dep i18n blocks: {lang_key: {"text": ..., "audiourl": ...}}."""
    messages_by_key = _build_platform_change_messages_by_i18n_key(
        train_number, route_source, route_destination, station_name, platform,
    )
    return _build_multilingual_audio_block_i18n(messages_by_key, train_number, "platform_change")


async def _upsert_announcement_doc(
    train_number: str, schedule_date: datetime, station_code: str,
    doc: Dict[str, Any], now: datetime, embed_i18n: bool, i18n_only: bool, _log,
) -> None:
    """STEP 8: upsert the built document into train_announcements."""
    _log.train_info(train_number, "STEP_8_UPSERT_DB",
                    "Upserting document into train_announcements collection",
                    filter={"train_number": train_number,
                            "schedule_date": schedule_date.isoformat(),
                            "station_code": station_code})
    try:
        update_doc: Dict[str, Any] = {"$set": doc, "$setOnInsert": {"created_at": now}}
        if embed_i18n and i18n_only:
            update_doc["$unset"] = {"arrival": "", "departure": "", "delay": "", "general": ""}

        await MongoDB.database.train_announcements.update_one(
            {"train_number": train_number, "schedule_date": schedule_date, "station_code": station_code},
            update_doc,
            upsert=True,
        )
        _log.train_info(train_number, "STEP_8_UPSERT_DB",
                        "Document upserted successfully into train_announcements")
    except Exception as _exc:
        _log.train_error(train_number, "STEP_8_UPSERT_DB",
                         f"Failed to upsert into train_announcements: {_exc}")
        raise


async def _process_train_for_next_hour_announcement(
    train: Dict[str, Any], now: datetime, embed_i18n: bool, i18n_only: bool, _log,
) -> Optional[StoredAnnouncementResponse]:
    """Run STEPs 2-8 for a single train; returns None if the train is skipped."""
    train_number = train["train_number"]
    train_name = train.get("train_name", "")
    schedule_date = train["schedule_date"]
    scheduled_arrival_dt = train.get("arrival_time")

    api_data = await _fetch_live_data_for_announcement(train_number, schedule_date, scheduled_arrival_dt, _log)
    if api_data is None:
        return None

    _log.train_info(train_number, "STEP_3_EXTRACT_FIELDS", "Extracting announcement fields from live data")
    fields = _extract_announcement_fields(train, api_data, now)
    _log.train_info(train_number, "STEP_3_EXTRACT_FIELDS", "Fields extracted",
                    station_name=fields["station_name"], station_code=fields["station_code"],
                    platform=fields["platform"], delay_minutes=fields["delay_minutes"],
                    arrival_time=fields["arrival_time"], departure_time=fields["departure_time"],
                    minutes_to_dep=fields["minutes_to_dep"], route=fields["route_path"])

    platform_changed = False
    if fields["platform"] and fields["platform"] != "unknown":
        platform_changed = await _train_platform_changed_this_cycle(
            train_number, schedule_date, fields["station_code"],
        )

    i18n_block: Optional[Dict[str, Any]] = None
    if embed_i18n:
        i18n_block = _build_i18n_block_for_train(
            train_number, fields, _log, include_platform_change=platform_changed,
        )

    texts: Optional[Dict[str, str]] = None
    audio_urls: Dict[str, Optional[str]] = {}
    if not (embed_i18n and i18n_only):
        texts = _build_english_texts(train_number, fields, _log)
        audio_urls = _generate_english_audio(train_number, texts, fields["delay_minutes"], _log)

    # ── STEP 7: Build document ────────────────────────────────────────────
    _log.train_info(train_number, "STEP_7_BUILD_DOC", "Building MongoDB document")
    doc: Dict[str, Any] = {
        "train_number": train_number,
        "train_name": train_name,
        "schedule_date": schedule_date,
        "station_code": fields["station_code"],
        "arrival_time": scheduled_arrival_dt,
        "updated_at": now,
    }
    if i18n_block is not None:
        doc["i18n"] = i18n_block

    if texts is not None:
        doc["arrival"] = {"textmsg": texts["arrival"], "audiourl": audio_urls.get("arrival")}
        doc["departure"] = {"textmsg": texts["departure"], "audiourl": audio_urls.get("departure")}
        doc["delay"] = {"textmsg": texts["delay"], "audiourl": audio_urls.get("delay")}
        doc["general"] = {"textmsg": texts["general"], "audiourl": audio_urls.get("general")}

    _log.train_info(train_number, "STEP_7_BUILD_DOC", "Document built",
                    has_i18n=i18n_block is not None, has_english=texts is not None,
                    platform_changed=platform_changed)

    await _upsert_announcement_doc(
        train_number, schedule_date, fields["station_code"], doc, now, embed_i18n, i18n_only, _log,
    )

    return StoredAnnouncementResponse(
        train_number=train_number,
        train_name=train_name,
        schedule_date=schedule_date.strftime("%Y-%m-%d"),
        station_code=fields["station_code"],
        arrival=doc.get("arrival"),
        departure=doc.get("departure"),
        delay=doc.get("delay"),
        general=doc.get("general"),
        i18n=doc.get("i18n"),
    )


async def generate_next_hour_announcements():
    _log = AnnouncementRunLogger()
    _log.info("STEP_0_INIT", "generate_next_hour_announcements started")

    bucket, region = get_aws_s3_config()
    if not bucket or not region:
        _log.error("STEP_0_INIT", "AWS S3 configuration missing", aws_s3_bucket=bucket, aws_region=region)
        await _log.flush()
        raise HTTPException(status_code=500, detail=AWS_S3_CONFIG_MISSING_ERROR)
    if MongoDB.database is None:
        _log.error("STEP_0_INIT", "MongoDB database not available")
        await _log.flush()
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    embed_i18n = (os.getenv("ANNOUNCEMENTS_EMBED_I18N") or "0").strip().lower() in ("1", "true", "yes", "y", "on")
    i18n_only = (os.getenv("ANNOUNCEMENTS_I18N_ONLY") or "0").strip().lower() in ("1", "true", "yes", "y", "on")

    settings = get_settings()
    now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    window_end = now + timedelta(hours=settings.live_train_window_hours)

    # ── STEP 1: Query train_schedules ─────────────────────────────────────────
    _log.info("STEP_1_QUERY_SCHEDULES", "Querying train_schedules collection",
              window_start=now.isoformat(), window_end=window_end.isoformat())
    try:
        trains, total_raw_records = await _query_trains_in_window(now, window_end)
        _log.info("STEP_1_QUERY_SCHEDULES", f"Found {len(trains)} unique trains in window",
                  total_raw_records=total_raw_records, unique_trains=len(trains))
    except Exception as _exc:
        _log.error("STEP_1_QUERY_SCHEDULES", f"Failed to query train_schedules: {_exc}")
        await _log.flush()
        raise

    if not trains:
        _log.info("STEP_1_QUERY_SCHEDULES", "No trains found in window – returning empty result")
        await _log.flush()
        return []

    results = []
    for train in trains:
        result = await _process_train_for_next_hour_announcement(train, now, embed_i18n, i18n_only, _log)
        if result is not None:
            results.append(result)

    # ── STEP 9: Publish to Firebase ───────────────────────────────────────────
    _log.info("STEP_9_FIREBASE", "Publishing recent announcements snapshot to Firebase")
    try:
        await _publish_recent_announcements_snapshot()
        _log.info("STEP_9_FIREBASE", "Firebase snapshot published successfully")
    except Exception as _exc:
        _log.error("STEP_9_FIREBASE", f"Firebase publish failed: {_exc}")

    _log.info("STEP_10_DONE", f"Pipeline complete – {len(results)} trains stored in train_announcements",
              stored_count=len(results), total_trains=len(trains))
    await _log.flush()
    return results


@router.post(
    "/next-hour",
    response_model=List[StoredAnnouncementI18nResponse],
    responses={
        500: {"description": "AWS S3 misconfiguration or audio generation/upload failure"},
        503: {"description": DATABASE_NOT_AVAILABLE_ERROR},
    },
)
async def generate_next_hour_announcements_i18n():
    bucket, region = get_aws_s3_config()
    if not bucket or not region:
        raise HTTPException(status_code=500, detail=AWS_S3_CONFIG_MISSING_ERROR)
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    settings = get_settings()
    now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    window_end = now + timedelta(hours=settings.live_train_window_hours)

    arriving_cursor = MongoDB.database.train_schedules.find(
        {"arrival_time": {"$gte": now, "$lte": window_end}}
    )
    arriving = await arriving_cursor.to_list(length=500)

    trains_map: Dict[str, Dict[str, Any]] = {}
    for train in arriving:
        key = f"{train['train_number']}_{train['schedule_date'].strftime('%Y-%m-%d')}"
        if key not in trains_map:
            trains_map[key] = train

    trains = list(trains_map.values())
    if not trains:
        return []

    results: List[StoredAnnouncementI18nResponse] = []

    for train in trains:
        train_number = train["train_number"]
        train_name = train.get("train_name", "")
        schedule_date = train["schedule_date"]
        scheduled_arrival_dt = train.get("arrival_time")

        api_data = await _get_live_api_data(train_number, schedule_date, scheduled_arrival_dt)
        if not api_data:
            continue

        station_raw = api_data.get("api_response_raw", {}) or {}
        station_name = station_raw.get("name", "") or station_raw.get("station_name", "Unknown")
        station_name = re.sub(JN_TO_JUNCTION_PATTERN, 'Junction', station_name, flags=re.IGNORECASE).strip().title()
        station_code = api_data.get("station_code", "")
        platform = str(api_data.get("platform_number") or station_raw.get("platform") or "unknown")
        delay_minutes = int(api_data.get("delay_minutes", 0))

        api_payload = api_data.get("api_payload", {}) or {}
        start_date = (api_payload.get("data", {}) or {}).get("start_date", "")
        arrival_time = station_raw.get("arrival_actual") or station_raw.get("arrival_scheduled") or "shortly"
        departure_time = station_raw.get("departure_actual") or station_raw.get("departure_scheduled") or "shortly"

        dep_dt = _parse_api_datetime(start_date, departure_time)
        minutes_to_dep = int((dep_dt - now).total_seconds() / 60) if dep_dt and dep_dt > now else None
        route_source, route_destination = _resolve_route_endpoints(train, api_data)

        texts_i18n = _build_messages_i18n(
            train_number=train_number,
            source=route_source,
            destination=route_destination,
            station_name=station_name,
            platform=platform,
            delay_minutes=delay_minutes,
            arrival_time=arrival_time,
            departure_time=departure_time,
            minutes_to_dep=minutes_to_dep,
        )

        arrival_block = _build_multilingual_audio_block_i18n(texts_i18n["arrival"], train_number, "arrival")
        dep_block = _build_multilingual_audio_block_i18n(texts_i18n["dep"], train_number, "dep")
        delay_block = _build_multilingual_audio_block_i18n(texts_i18n["delay"], train_number, "delay") if delay_minutes > 0 else {}
        general_block = _build_multilingual_audio_block_i18n(texts_i18n["general"], train_number, "general")

        doc = {
            "train_number": train_number,
            "train_name": train_name,
            "schedule_date": schedule_date,
            "station_code": station_code,
            "arrival_time": scheduled_arrival_dt,
            "arrival": arrival_block,
            "dep": dep_block,
            "delay": delay_block,
            "general": general_block,
            "updated_at": now,
        }

        await MongoDB.database.train_announcements_i18n.update_one(
            {"train_number": train_number, "schedule_date": schedule_date, "station_code": station_code},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

        results.append(StoredAnnouncementI18nResponse(
            train_number=train_number,
            train_name=train_name,
            schedule_date=schedule_date.strftime("%Y-%m-%d"),
            station_code=station_code,
            arrival=doc["arrival"],
            dep=doc["dep"],
            delay=doc["delay"],
            general=doc["general"],
        ))

    return results


@router.get(
    "/next-hour",
    response_model=List[StoredAnnouncementI18nResponse],
    responses={503: {"description": DATABASE_NOT_AVAILABLE_ERROR}},
)
async def get_next_hour_announcements_i18n():
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    settings = get_settings()
    now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    window_end = now + timedelta(hours=1)

    station_code = settings.live_train_station_code
    cursor = MongoDB.database.train_announcements_i18n.find(
        {
            "station_code": station_code,
            "arrival_time": {"$gte": now, "$lte": window_end},
        }
    ).sort("arrival_time", 1)
    docs = await cursor.to_list(length=500)

    if not docs:
        return []

    results: List[StoredAnnouncementI18nResponse] = []
    for doc in docs:
        doc.pop("_id", None)
        schedule_date = doc.get("schedule_date")
        schedule_date_str = schedule_date.strftime("%Y-%m-%d") if hasattr(schedule_date, "strftime") else str(schedule_date)
        results.append(StoredAnnouncementI18nResponse(
            train_number=doc["train_number"],
            train_name=doc.get("train_name", ""),
            schedule_date=schedule_date_str,
            station_code=doc.get("station_code", ""),
            arrival=doc.get("arrival", {}),
            dep=doc.get("dep", doc.get("departure", {})),
            delay=doc.get("delay", {}),
            general=doc.get("general", {}),
        ))

    return results


@router.get(
    "/next-hour",
    response_model=List[StoredAnnouncementResponse],
    responses={503: {"description": DATABASE_NOT_AVAILABLE_ERROR}},
)
async def get_next_hour_announcements():
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    settings = get_settings()
    now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    window_end = now + timedelta(hours=1)

    station_code = settings.live_train_station_code
    cursor = MongoDB.database.train_announcements.find(
        {
            "station_code": station_code,
            "arrival_time": {"$gte": now, "$lte": window_end},
        }
    ).sort("arrival_time", 1)
    docs = await cursor.to_list(length=500)

    if not docs:
        return []

    results: List[StoredAnnouncementResponse] = []
    for doc in docs:
        doc.pop("_id", None)

        schedule_date = doc.get("schedule_date")
        schedule_date_str = schedule_date.strftime("%Y-%m-%d") if hasattr(schedule_date, "strftime") else str(schedule_date)
        results.append(StoredAnnouncementResponse(
            train_number=doc["train_number"],
            train_name=doc.get("train_name", ""),
            schedule_date=schedule_date_str,
            station_code=doc.get("station_code", ""),
            arrival=doc.get("arrival"),
            departure=doc.get("departure"),
            delay=doc.get("delay"),
            general=doc.get("general"),
            i18n=doc.get("i18n"),
        ))

    return results


@router.get(
    "/recent",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(require_recent_announcements_token)],
    responses={503: {"description": DATABASE_NOT_AVAILABLE_ERROR}},
)
async def get_recent_announcements():
    if MongoDB.database is None:
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    settings = get_settings()
    serialized_docs = await _publish_recent_announcements_snapshot()
    await _clear_legacy_firebase_recent_snapshots(settings.live_train_station_code)
    if not serialized_docs:
        return []

    return JSONResponse(content=serialized_docs)

@router.get(
    "/congestion",
    response_model=List[Dict[str, Any]],
    responses={
        503: {"description": DATABASE_NOT_AVAILABLE_ERROR},
        500: {"description": "Error fetching congestion alerts"},
    },
)
async def get_congestion_alerts():
    """
    Fetch only the freshest congestion alert from the dedicated collection.
    """
    if MongoDB.database is None:
        logger.error("MongoDB database is None - connection not established")
        raise HTTPException(status_code=503, detail=DATABASE_NOT_AVAILABLE_ERROR)

    try:
        settings = get_settings()
        # congestion_alerts.timestamp is stored in UTC, so compare in UTC too.
        now = datetime.now(UTC)
        freshness_cutoff = now - timedelta(minutes=15)

        cursor = MongoDB.database.congestion_alerts.find(
            {"timestamp": {"$gte": freshness_cutoff}}
        ).sort([
            ("timestamp", -1),
            ("people_count", -1),
            ("updated_at", -1),
        ]).limit(1)
        docs = await cursor.to_list(length=1)
        
        logger.info(f"[/congestion] Retrieved {len(docs)} documents from congestion_alerts collection")
        
        if not docs:
            logger.info("[/congestion] No documents found, returning empty list")
            await _clear_firebase_congestion_snapshots(settings.live_train_station_code)
            return []

        # Convert ObjectId and datetime objects for JSON serialization
        serialized_docs = json.loads(json_util.dumps(docs))
        await FirebaseService.publish_congestion(
            serialized_docs[0] if serialized_docs else None,
        )
        logger.info(f"[/congestion] Serialized {len(serialized_docs)} documents successfully")
        return serialized_docs
    except Exception as e:
        logger.exception("[/congestion] Error fetching congestion alerts")
        raise HTTPException(status_code=500, detail=f"Error fetching congestion alerts: {str(e)}")
