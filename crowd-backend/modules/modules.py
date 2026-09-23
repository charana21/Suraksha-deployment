from datetime import UTC, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from api.errors import DatabaseError, ValidationError
from db.mongodb import get_database
from utils.logging_config import get_logger
from util.constants import ERR_INVALID_MODULE_ID

OBJECT_ID_PATTERN = r"^[0-9a-fA-F]{24}$"
DEFAULT_ROUTE_MAPPINGS = {
    "user": "Users",
    "roles": "Roles",
    "modules": "Modules",
    "session": "Sessions",
    "auditlogs": "Audits",
}
logger = get_logger("crowdvision.modules.modules")


class ModuleBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(..., max_length=120, alias="name")
    description: Optional[str] = Field(None, max_length=500, alias="description")
    url_name: str = Field(..., max_length=120, alias="urlName")
    master: bool = Field(False, alias="master")
    # project_name: Optional[str] = Field(None, max_length=120, alias="projectName")
    active: int = Field(1, ge=0, le=1, alias="active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("name field is required")
        if len(stripped_value) < 2:
            raise ValueError("name should have at least 2 characters")
        return stripped_value

    @field_validator("url_name")
    @classmethod
    def validate_url_name(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("urlName field is required")
        if len(stripped_value) < 2:
            raise ValueError("urlName should have at least 2 characters")
        return stripped_value


class ModuleCreateRequest(ModuleBase):
    pass


class ModuleUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: Optional[str] = Field(None, max_length=120, alias="name")
    description: Optional[str] = Field(None, max_length=500, alias="description")
    url_name: Optional[str] = Field(None, max_length=120, alias="urlName")
    master: Optional[bool] = Field(None, alias="master")
    active: Optional[int] = Field(None, ge=0, le=1, alias="active")

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

    @field_validator("url_name")
    @classmethod
    def validate_optional_url_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("urlName field is required")
        if len(stripped_value) < 2:
            raise ValueError("urlName should have at least 2 characters")
        return stripped_value


class ModuleResponse(ModuleBase):
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


class ModuleListResponse(BaseModel):
    status: str = "success"
    count: int
    modules: List[ModuleResponse]


class ModuleCreateResponse(BaseModel):
    response_msg: str = Field("New module created successfully", alias="responseMsg")
    response_code: int = Field(200, alias="responseCode")
    module: ModuleResponse


class ModuleManager:
    COLLECTION = "modules"
    MAPPINGS_COLLECTION = "column_mapping"
    ROUTE_MAPPINGS_NAME = "route_mappings"

    @classmethod
    async def get_db(cls, db: AsyncIOMotorDatabase = None):
        if db is None:
            db = get_database()
        if db is None:
            raise DatabaseError("Authentication database unavailable")
        return db

    @classmethod
    async def get_collection(cls, db: AsyncIOMotorDatabase = None):
        db = await cls.get_db(db)
        return db[cls.COLLECTION]

    @classmethod
    async def get_mappings_collection(cls, db: AsyncIOMotorDatabase = None):
        db = await cls.get_db(db)
        return db[cls.MAPPINGS_COLLECTION]

    @staticmethod
    def _normalize_route_key(module_name: str) -> str:
        return "_".join(module_name.strip().lower().split())

    @classmethod
    async def _ensure_route_mappings(cls, db: AsyncIOMotorDatabase = None) -> dict:
        mappings_collection = await cls.get_mappings_collection(db)
        try:
            mapping_doc = await mappings_collection.find_one({"name": cls.ROUTE_MAPPINGS_NAME})
            if mapping_doc is not None:
                return mapping_doc

            now = datetime.now(UTC)
            seed_doc = {
                "name": cls.ROUTE_MAPPINGS_NAME,
                "mapping": DEFAULT_ROUTE_MAPPINGS.copy(),
                "createdAt": now,
                "updatedAt": now,
            }
            await mappings_collection.insert_one(seed_doc)
            return seed_doc
        except PyMongoError as exc:
            logger.exception("Failed to ensure route mappings")
            raise DatabaseError("Failed to initialize module mappings") from exc

    @classmethod
    async def _upsert_route_mapping_entry(
        cls,
        key: str,
        module_name: str,
        db: AsyncIOMotorDatabase = None,
    ) -> None:
        try:
            await cls._ensure_route_mappings(db=db)
            mappings_collection = await cls.get_mappings_collection(db)
            await mappings_collection.update_one(
                {"name": cls.ROUTE_MAPPINGS_NAME},
                {
                    "$set": {
                        f"mapping.{key}": module_name,
                        "updatedAt": datetime.now(UTC),
                    }
                },
            )
        except PyMongoError as exc:
            logger.exception("Failed to update route mapping key=%s", key)
            raise DatabaseError("Failed to update module mappings") from exc

    @classmethod
    async def create_module(
        cls,
        request: ModuleCreateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> ModuleResponse:
        collection = await cls.get_collection(db)
        now = datetime.now(UTC)
        payload = request.model_dump(by_alias=True, exclude_none=True)
        payload.update(
            {
                "createAt": now,
                "updateAt": now,
                "createBy": actor_user_id,
                "updateBy": actor_user_id,
            }
        )

        try:
            result = await collection.insert_one(payload)
            route_key = cls._normalize_route_key(payload["name"])
            await cls._upsert_route_mapping_entry(route_key, payload["name"], db=db)
            doc = await collection.find_one({"_id": result.inserted_id})
            return cls._to_response(doc)
        except PyMongoError as exc:
            logger.exception("Failed to create module")
            raise DatabaseError("Failed to create module") from exc

    @classmethod
    async def list_modules(cls, db: AsyncIOMotorDatabase = None) -> List[ModuleResponse]:
        collection = await cls.get_collection(db)
        try:
            docs = await collection.find({}).sort("createAt", -1).to_list(length=None)
            return [cls._to_response(doc) for doc in docs]
        except PyMongoError as exc:
            logger.exception("Failed to list modules")
            raise DatabaseError("Failed to fetch modules") from exc

    @classmethod
    async def update_module(
        cls,
        module_id: str,
        request: ModuleUpdateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[ModuleResponse]:
        if not ObjectId.is_valid(module_id):
            raise ValidationError(ERR_INVALID_MODULE_ID)

        existing = await cls.get_module(module_id, db=db)
        if existing is None:
            return None

        updates = request.model_dump(by_alias=True, exclude_none=True)
        if not updates:
            return await cls.get_module(module_id, db=db)

        old_name = existing.name
        new_name = updates.get("name", old_name)

        updates["updateAt"] = datetime.now(UTC)
        updates["updateBy"] = actor_user_id
        collection = await cls.get_collection(db)
        try:
            await collection.update_one({"_id": ObjectId(module_id)}, {"$set": updates})

            if new_name != old_name:
                mapping_doc = await cls._ensure_route_mappings(db=db)
                current_mapping = mapping_doc.get("mapping", {})
                for route_key, mapped_module_name in current_mapping.items():
                    if mapped_module_name == old_name:
                        await cls._upsert_route_mapping_entry(route_key, new_name, db=db)

            return await cls.get_module(module_id, db=db)
        except PyMongoError as exc:
            logger.exception("Failed to update module")
            raise DatabaseError("Failed to update module") from exc

    @classmethod
    async def delete_module(cls, module_id: str, db: AsyncIOMotorDatabase = None) -> bool:
        if not ObjectId.is_valid(module_id):
            raise ValidationError(ERR_INVALID_MODULE_ID)
        collection = await cls.get_collection(db)
        try:
            result = await collection.delete_one({"_id": ObjectId(module_id)})
            return result.deleted_count > 0
        except PyMongoError as exc:
            logger.exception("Failed to delete module")
            raise DatabaseError("Failed to delete module") from exc

    @classmethod
    async def get_module(
        cls,
        module_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[ModuleResponse]:
        if not ObjectId.is_valid(module_id):
            raise ValidationError(ERR_INVALID_MODULE_ID)
        collection = await cls.get_collection(db)
        try:
            doc = await collection.find_one({"_id": ObjectId(module_id)})
            if doc is None:
                return None
            return cls._to_response(doc)
        except PyMongoError as exc:
            logger.exception("Failed to fetch module")
            raise DatabaseError("Failed to fetch module") from exc

    @staticmethod
    def _to_response(doc: dict) -> ModuleResponse:
        doc = dict(doc)
        doc["_id"] = str(doc.get("_id", ObjectId()))
        return ModuleResponse.model_validate(doc)
