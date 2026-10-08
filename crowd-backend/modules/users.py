from datetime import UTC, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from util.constants import USER_ALREADY_EXISTS, INVALID_USER_ID, WHATSAPP_PREFIX
from api.errors import (
    ConflictError,
    DatabaseError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from config.config import get_settings
from db.mongodb import get_database
from utils.logging_config import get_logger

try:
    from passlib.context import CryptContext
except ImportError:
    CryptContext = None

try:
    from jose import jwt
except ImportError:
    jwt = None


OBJECT_ID_PATTERN = r"^[0-9a-fA-F]{24}$"
PHONE_PATTERN = r"^\+[1-9][0-9]{7,14}$"
SPECIAL_CHAR_PATTERN = r"[!@#$%^&*(),.?\":{}|<>_\-\\/\[\];'`~+=]"
GENDER_VALUES = {"male", "female", "other"}

logger = get_logger("crowdvision.modules.users")

_background_tasks: set = set()

WHATSAPP_SERVICE_ALIASES = {
    "msg91_platform_assigned_template_id": [
        "msg91_platform_assigned_template_id",
        "twilio_platform_assigned_content_sid",
    ],
    "msg91_train_delay_alert_template_id": [
        "msg91_train_delay_alert_template_id",
        "twilio_train_delay_alert_content_sid",
    ],
    "msg91_whatsapp_booking_office_template_id": [
        "msg91_whatsapp_booking_office_template_id",
        "twilio_whatsapp_booking_office_content_sid",
    ],
    "msg91_whatsapp_crowd_alert_template_id": [
        "msg91_whatsapp_crowd_alert_template_id",
        "whatsapp_content_sid",
        "twilio_whatsapp_content_sid",
    ],
    "msg91_custom_whatsapp_message_template_id": [
        "msg91_custom_whatsapp_message_template_id",
        "custom_whatsapp_message",
    ],
    "msg91_whatsapp_island_alert_template_id": [
        "msg91_whatsapp_island_alert_template_id",
    ],
    "msg91_whatsapp_fob_alert_template_id": [
        "msg91_whatsapp_fob_alert_template_id",
        "msg91_whatsapp_crowd_alert_template_id",
        "whatsapp_content_sid",
        "twilio_whatsapp_content_sid",
    ],
}

WHATSAPP_SERVICE_KEYS = {
    "msg91_platform_assigned_template_id",
    "msg91_train_delay_alert_template_id",
    "msg91_whatsapp_booking_office_template_id",
    "msg91_whatsapp_crowd_alert_template_id",
    "msg91_custom_whatsapp_message_template_id",
    "msg91_whatsapp_island_alert_template_id",
    "msg91_whatsapp_fob_alert_template_id",
    "suraksha_ai",
    *[
        alias
        for aliases in WHATSAPP_SERVICE_ALIASES.values()
        for alias in aliases
    ],
}


class UserBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(..., max_length=120, alias="name")
    email: EmailStr = Field(..., alias="email")
    phone: str = Field(..., alias="phone")
    role_id: str = Field(..., alias="roleID")
    active: int = Field(1, ge=0, le=1, alias="active")
    gender: Optional[str] = Field(None, alias="gender")

    services: List[str] = Field(default_factory=list, alias="services")
    sendAlerts: bool = Field(False, alias="sendAlerts")

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped_value = value.strip().lower()
        if stripped_value not in GENDER_VALUES:
            raise ValueError("gender must be one of: male, female, other")
        return stripped_value

    @field_validator("role_id")
    @classmethod
    def validate_role_id(cls, value: str) -> str:
        import re

        if not re.match(OBJECT_ID_PATTERN, value):
            raise ValueError("roleID must be a valid Mongo ObjectId")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("name field is required")
        if len(stripped_value) < 2:
            raise ValueError("name should have at least 2 characters")
        return stripped_value

    @field_validator("services")
    @classmethod
    def validate_services(cls, value: List[str]) -> List[str]:
        if value is None:
            return []
        normalized = []
        for item in value:
            service = str(item or "").strip()
            if not service:
                continue
            if service not in WHATSAPP_SERVICE_KEYS:
                raise ValueError(f"Invalid service: {service}")
            if service not in normalized:
                normalized.append(service)
        return normalized


class UserCreateRequest(UserBase):
    gender: str = Field(..., alias="gender")
    password: str = Field(..., max_length=128, alias="password")

    @field_validator("gender")
    @classmethod
    def validate_create_gender(cls, value: str) -> str:
        stripped_value = value.strip().lower()
        if stripped_value not in GENDER_VALUES:
            raise ValueError("gender must be one of: male, female, other")
        return stripped_value

    @field_validator("phone")
    @classmethod
    def validate_create_phone(cls, value: str) -> str:
        import re

        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("phone field is required")
        if not re.match(PHONE_PATTERN, stripped_value):
            raise ValueError("phone must be in E.164 format, for example +917812345690")
        return stripped_value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        import re

        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("password field is required")
        if len(stripped_value) < 8:
            raise ValueError("password must be at least 8 characters")
        if not re.search(SPECIAL_CHAR_PATTERN, stripped_value):
            raise ValueError("password must include at least one special character")
        return stripped_value


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: Optional[str] = Field(None, max_length=120, alias="name")
    email: Optional[EmailStr] = Field(None, alias="email")
    phone: Optional[str] = Field(None, alias="phone")
    password: Optional[str] = Field(None, max_length=128, alias="password")
    role_id: Optional[str] = Field(None, alias="roleID")
    active: Optional[int] = Field(None, ge=0, le=1, alias="active")
    gender: Optional[str] = Field(None, alias="gender")
    services: Optional[List[str]] = Field(None, alias="services")
    sendAlerts: Optional[bool] = Field(None, alias="sendAlerts")

    @field_validator("gender")
    @classmethod
    def validate_optional_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped_value = value.strip().lower()
        if stripped_value not in GENDER_VALUES:
            raise ValueError("gender must be one of: male, female, other")
        return stripped_value

    @field_validator("role_id")
    @classmethod
    def validate_optional_role_id(cls, value: Optional[str]) -> Optional[str]:
        import re

        if value is None:
            return value
        if not re.match(OBJECT_ID_PATTERN, value):
            raise ValueError("roleID must be a valid Mongo ObjectId")
        return value

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("name field is required")
        if len(stripped_value) < 2:
            raise ValueError("name should have at least 2 characters")
        return stripped_value

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: Optional[str]) -> Optional[str]:
        import re

        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("phone field is required")
        if not re.match(PHONE_PATTERN, stripped_value):
            raise ValueError("phone must be in E.164 format, for example +917812345690")
        return stripped_value

    @field_validator("password")
    @classmethod
    def validate_optional_password_strength(cls, value: Optional[str]) -> Optional[str]:
        import re

        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("password field is required")
        if len(stripped_value) < 8:
            raise ValueError("password must be at least 8 characters")
        if not re.search(SPECIAL_CHAR_PATTERN, stripped_value):
            raise ValueError("password must include at least one special character")
        return stripped_value

    @field_validator("services")
    @classmethod
    def validate_optional_services(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        normalized = []
        for item in value:
            service = str(item or "").strip()
            if not service:
                continue
            if service not in WHATSAPP_SERVICE_KEYS:
                raise ValueError(f"Invalid service: {service}")
            if service not in normalized:
                normalized.append(service)
        return normalized

class UserResponse(UserBase):
    id: str = Field(..., alias="_id")
    create_at: datetime = Field(default_factory=datetime.now(UTC), alias="createAt")
    update_at: datetime = Field(default_factory=datetime.now(UTC), alias="updateAt")
    create_by: Optional[str] = Field(None, alias="createBy")
    update_by: Optional[str] = Field(None, alias="updateBy")

    @field_validator("id")
    @classmethod
    def validate_object_id(cls, value: str) -> str:
        import re

        if not re.match(OBJECT_ID_PATTERN, value):
            raise ValueError("Invalid Mongo ObjectId format for _id")
        return value


class UserListResponse(BaseModel):
    status: str = "success"
    count: int
    users: List[UserResponse]


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    old_password: str = Field(..., alias="currentPassword")
    new_password: str = Field(..., max_length=128, alias="newPassword")
    confirm_password: str = Field(..., max_length=128, alias="confirmPassword")

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        import re

        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("newPassword field is required")
        if len(stripped_value) < 8:
            raise ValueError("newPassword must be at least 8 characters")
        if not re.search(SPECIAL_CHAR_PATTERN, stripped_value):
            raise ValueError("newPassword must include at least one special character")
        return stripped_value

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password_matches(cls, value: str, info) -> str:
        new_password = info.data.get("new_password")
        if new_password is not None and value.strip() != new_password:
            raise ValueError("confirmPassword must match newPassword")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_login_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password cannot be blank")
        return value


class TokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    response_msg: str = Field("Success", alias="responseMsg")
    response_code: int = Field(200, alias="responseCode")
    token: str
    user_id: str = Field(..., alias="userID")


class UsersManager:
    USER_COLLECTION = "viewers_user_collection"
    LOGIN_COLLECTION = "userlogin"

    @classmethod
    async def get_user_collection(cls, db: AsyncIOMotorDatabase = None):
        if db is None:
            db = get_database()
        if db is None:
            raise DatabaseError("Authentication database unavailable")
        return db[cls.USER_COLLECTION]

    @classmethod
    async def get_login_collection(cls, db: AsyncIOMotorDatabase = None):
        if db is None:
            db = get_database()
        if db is None:
            raise DatabaseError("Authentication database unavailable")
        return db[cls.LOGIN_COLLECTION]

    @staticmethod
    def _pwd_context():
        if CryptContext is None:
            raise InternalServerError("Authentication service unavailable")
        return CryptContext(schemes=["bcrypt"], deprecated="auto")

    @classmethod
    def hash_password(cls, password: str) -> str:
        return cls._pwd_context().hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        return cls._pwd_context().verify(plain_password, hashed_password)

    @classmethod
    async def create_user(
        cls,
        request: UserCreateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> UserResponse:
        collection = await cls.get_user_collection(db)
        now = datetime.now(UTC)
        payload = request.model_dump(by_alias=True, exclude_none=True)
        payload["email"] = payload["email"].lower()
        payload["sendAlerts"] = False

        try:
            existing = await collection.find_one({"email": payload["email"]})
            if existing:
                raise ConflictError(USER_ALREADY_EXISTS)

            payload["password"] = cls.hash_password(payload["password"])
            payload["createAt"] = now
            payload["updateAt"] = now
            payload["createBy"] = actor_user_id
            payload["updateBy"] = actor_user_id

            result = await collection.insert_one(payload)
            doc = await collection.find_one({"_id": result.inserted_id})

            if "suraksha_ai" in payload.get("services", []):
                try:
                    from services.suraksha_optin_service import SurakshaOptInService
                    import asyncio
                    task = asyncio.create_task(SurakshaOptInService.send_optin_to_user(doc))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
                except Exception as e:
                    logger.exception("Failed to trigger immediate suraksha opt-in: %s", e)

            return cls._to_response(doc)
        except DuplicateKeyError as exc:
            raise ConflictError(USER_ALREADY_EXISTS) from exc
        except PyMongoError as exc:
            logger.exception("Failed to create user")
            raise DatabaseError("Failed to create user") from exc

    @classmethod
    async def list_users(cls, db: AsyncIOMotorDatabase = None) -> List[UserResponse]:
        collection = await cls.get_user_collection(db)
        try:
            docs = await collection.find({}).sort("createAt", -1).to_list(length=None)
            return [cls._to_response(doc) for doc in docs]
        except PyMongoError as exc:
            logger.exception("Failed to list users")
            raise DatabaseError("Failed to fetch users") from exc

    @classmethod
    async def update_user(
        cls,
        user_id: str,
        request: UserUpdateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[UserResponse]:
        if not ObjectId.is_valid(user_id):
            raise ValidationError(INVALID_USER_ID)

        updates = request.model_dump(by_alias=True, exclude_none=True)
        if "email" in updates:
            updates["email"] = updates["email"].lower()
        if "password" in updates:
            updates["password"] = cls.hash_password(updates["password"])
        if not updates:
            return await cls.get_user(user_id, db=db)

        updates["updateAt"] = datetime.now(UTC)
        updates["updateBy"] = actor_user_id
        collection = await cls.get_user_collection(db)
        try:
            if "email" in updates:
                existing = await collection.find_one(
                    {"email": updates["email"], "_id": {"$ne": ObjectId(user_id)}}
                )
                if existing:
                    raise ConflictError(USER_ALREADY_EXISTS)

            await collection.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
            return await cls.get_user(user_id, db=db)
        except DuplicateKeyError as exc:
            raise ConflictError(USER_ALREADY_EXISTS) from exc
        except PyMongoError as exc:
            logger.exception("Failed to update user")
            raise DatabaseError("Failed to update user") from exc

    @classmethod
    async def delete_user(cls, user_id: str, db: AsyncIOMotorDatabase = None) -> bool:
        if not ObjectId.is_valid(user_id):
            raise ValidationError(INVALID_USER_ID)
        collection = await cls.get_user_collection(db)
        try:
            result = await collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except PyMongoError as exc:
            logger.exception("Failed to delete user")
            raise DatabaseError("Failed to delete user") from exc

    @classmethod
    async def get_user(cls, user_id: str, db: AsyncIOMotorDatabase = None) -> Optional[UserResponse]:
        if not ObjectId.is_valid(user_id):
            raise ValidationError(INVALID_USER_ID)
        collection = await cls.get_user_collection(db)
        try:
            doc = await collection.find_one({"_id": ObjectId(user_id)})
            if doc is None:
                return None
            return cls._to_response(doc)
        except PyMongoError as exc:
            logger.exception("Failed to fetch user")
            raise DatabaseError("Failed to fetch user") from exc

    @classmethod
    async def change_password(
        cls,
        actor_user_id: str,
        request: "ChangePasswordRequest",
        db: AsyncIOMotorDatabase = None,
    ) -> None:
        if not ObjectId.is_valid(actor_user_id):
            raise ValidationError(INVALID_USER_ID)

        collection = await cls.get_user_collection(db)
        try:
            doc = await collection.find_one({"_id": ObjectId(actor_user_id)})
            if doc is None:
                raise NotFoundError("User not found")

            if not cls.verify_password(request.old_password, doc.get("password", "")):
                raise UnauthorizedError("Old password is incorrect")

            if cls.verify_password(request.new_password, doc.get("password", "")):
                raise ValidationError("New password must be different from old password")

            await collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "password": cls.hash_password(request.new_password),
                        "updateAt": datetime.now(UTC),
                        "updateBy": actor_user_id,
                    }
                },
            )
        except PyMongoError as exc:
            logger.exception("Failed to change password")
            raise DatabaseError("Failed to change password") from exc

    @staticmethod
    def _normalize_whatsapp_phone(phone: str) -> str:
        cleaned = str(phone or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith(WHATSAPP_PREFIX):
            cleaned = cleaned.split(WHATSAPP_PREFIX, 1)[1].strip()
        return cleaned if cleaned.startswith("+") else ""

    @classmethod
    async def get_whatsapp_numbers_for_services(
        cls,
        services: List[str],
        db: AsyncIOMotorDatabase = None,
    ) -> List[str]:
        service_keys = [str(service or "").strip() for service in services if str(service or "").strip()]
        service_keys = [service for service in dict.fromkeys(service_keys) if service in WHATSAPP_SERVICE_KEYS]
        if not service_keys:
            return []
        query_service_keys = []
        for service in service_keys:
            aliases = WHATSAPP_SERVICE_ALIASES.get(service, [service])
            for alias in aliases:
                if alias not in query_service_keys:
                    query_service_keys.append(alias)

        collection = await cls.get_user_collection(db)
        try:
            docs = await collection.find(
                {
                    "active": 1,
                    "sendAlerts": True,
                    "phone": {"$exists": True, "$ne": ""},
                    "services": {"$in": query_service_keys},
                },
                {"phone": 1},
            ).to_list(length=None)
        except PyMongoError as exc:
            logger.exception("Failed to fetch WhatsApp recipients for services=%s", service_keys)
            raise DatabaseError("Failed to fetch WhatsApp recipients") from exc

        numbers = []
        for doc in docs:
            number = cls._normalize_whatsapp_phone(doc.get("phone", ""))
            if number and number not in numbers:
                numbers.append(number)
        return numbers

    @classmethod
    def _normalize_msg91_phone_to_e164(cls, phone: str) -> str:
        import re
        cleaned = str(phone or "").strip()
        if not cleaned:
            return ""
        if cleaned.startswith(WHATSAPP_PREFIX):
            cleaned = cleaned.split(WHATSAPP_PREFIX, 1)[1].strip()
        cleaned = cleaned.replace(" ", "").replace("-", "")
        cleaned = re.sub(r"^0+", "", cleaned)
        if cleaned and not cleaned.startswith("+"):
            cleaned = f"+{cleaned}"
        return cleaned

    @classmethod
    async def update_alert_optin(
        cls,
        phone_number: str,
        allowed: bool,
        db: AsyncIOMotorDatabase = None,
    ) -> bool:
        normalized = cls._normalize_msg91_phone_to_e164(phone_number)
        if not normalized:
            logger.warning(f"Could not normalize phone number for opt-in: {phone_number}")
            return False

        collection = await cls.get_user_collection(db)
        now = datetime.now(UTC)
        try:
            query = {
                "$or": [
                    {"phone": normalized},
                    {"phone": normalized.replace("+", "")}
                ]
            }
            result = await collection.update_many(
                query,
                {"$set": {"sendAlerts": allowed, "updateAt": now}}
            )
            logger.info(f"Updated alert opt-in for phone {normalized} to {allowed}. Modified count: {result.modified_count}")
            return result.modified_count > 0
        except PyMongoError as exc:
            logger.exception(f"Failed to update alert opt-in for phone {phone_number}")
            raise DatabaseError("Failed to update user opt-in status") from exc

    @classmethod
    async def login(
        cls,
        request: LoginRequest,
        db: AsyncIOMotorDatabase = None,
    ) -> TokenResponse:
        if jwt is None:
            raise InternalServerError("Authentication service unavailable")

        settings = get_settings()
        user_collection = await cls.get_user_collection(db)
        login_collection = await cls.get_login_collection(db)

        try:
            user = await user_collection.find_one({"email": request.email.lower()})
            if user is None:
                raise UnauthorizedError("Invalid credentials")

            password_hash = user.get("password", "")
            if not password_hash or not cls.verify_password(request.password, password_hash):
                raise UnauthorizedError("Invalid credentials")

            now = datetime.now(UTC)
            exp = now.timestamp() + (settings.jwt_expire_hours * 3600)
            user_id = str(user["_id"])
            session_id = str(ObjectId())

            token_payload = {
                "email": user["email"],
                "exp": int(exp),
                "iat": int(now.timestamp()),
                "name": user.get("name", ""),
                "sID": session_id,
                "uID": user_id,
            }
            token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

            await login_collection.insert_one(
                {
                    "userID": user_id,
                    "login": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "logout": "",
                    "createAt": now,
                    "updateAt": now,
                    "createBy": user_id,
                    "updateBy": user_id,
                }
            )

            return TokenResponse(
                responseMsg="Success",
                responseCode=200,
                token=token,
                userID=user_id,
            )
        except UnauthorizedError:
            raise
        except PyMongoError as exc:
            logger.exception("Login database operation failed for user=%s", request.email.lower())
            raise DatabaseError("Login failed due to database error") from exc
        except Exception as exc:
            logger.exception("Unexpected login failure")
            raise InternalServerError("Unable to complete login") from exc

    @staticmethod
    def _to_response(doc: dict) -> UserResponse:
        doc = dict(doc)
        doc["_id"] = str(doc.get("_id", ObjectId()))
        doc.pop("password", None)
        return UserResponse.model_validate(doc)
