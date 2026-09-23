from datetime import UTC, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from api.errors import DatabaseError, ValidationError
from db.mongodb import get_database
from utils.logging_config import get_logger
from util.constants import INVALID_ROLEID

OBJECT_ID_PATTERN = r"^[0-9a-fA-F]{24}$"
PermissionAction = Literal["add", "edit", "view", "delete"]
logger = get_logger("crowdvision.modules.roles")


class PermissionObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    module_id: str = Field(..., alias="moduleID")
    add: int = Field(0, ge=0, le=1, alias="add")
    edit: int = Field(0, ge=0, le=1, alias="edit")
    view: int = Field(0, ge=0, le=1, alias="view")
    delete: int = Field(0, ge=0, le=1, alias="delete")

    @field_validator("module_id")
    @classmethod
    def validate_module_id(cls, value: str) -> str:
        import re

        if not re.match(OBJECT_ID_PATTERN, value):
            raise ValueError("moduleID must be a valid Mongo ObjectId")
        return value


class RoleBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(..., max_length=120, alias="name")
    description: Optional[str] = Field(None, max_length=500, alias="description")
    level: int = Field(..., ge=1, le=999, alias="level")
    is_super_user: bool = Field(False, alias="isSuperUser")
    permissions: List[PermissionObject] = Field(default_factory=list, alias="permissions")
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


class RoleCreateRequest(RoleBase):
    pass


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: Optional[str] = Field(None, max_length=120, alias="name")
    description: Optional[str] = Field(None, max_length=500, alias="description")
    level: Optional[int] = Field(None, ge=1, le=999, alias="level")
    is_super_user: Optional[bool] = Field(None, alias="isSuperUser")
    permissions: Optional[List[PermissionObject]] = Field(None, alias="permissions")
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


class RoleResponse(RoleBase):
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


class RoleListResponse(BaseModel):
    status: str = "success"
    count: int
    roles: List[RoleResponse]


class UpdateRolePermissionsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    permissions: List[PermissionObject] = Field(..., alias="permissions")


def has_module_permission(role: RoleResponse, module_id: str, action: PermissionAction) -> bool:
    """Role-based permission check for module actions."""
    if role.is_super_user:
        return True

    for permission in role.permissions:
        if permission.module_id == module_id:
            return bool(getattr(permission, action, 0))

    return False


class RoleManager:
    COLLECTION = "roles"

    @classmethod
    async def get_collection(cls, db: AsyncIOMotorDatabase = None):
        if db is None:
            db = get_database()
        if db is None:
            raise DatabaseError("Authentication database unavailable")
        return db[cls.COLLECTION]

    @classmethod
    async def create_role(
        cls,
        request: RoleCreateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> RoleResponse:
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
            doc = await collection.find_one({"_id": result.inserted_id})
            return cls._to_response(doc)
        except PyMongoError as exc:
            logger.exception("Failed to create role")
            raise DatabaseError("Failed to create role") from exc

    @classmethod
    async def list_roles(cls, db: AsyncIOMotorDatabase = None) -> List[RoleResponse]:
        collection = await cls.get_collection(db)
        try:
            docs = await collection.find({}).sort("level", 1).to_list(length=None)
            return [cls._to_response(doc) for doc in docs]
        except PyMongoError as exc:
            logger.exception("Failed to list roles")
            raise DatabaseError("Failed to fetch roles") from exc

    @classmethod
    async def update_role(
        cls,
        role_id: str,
        request: RoleUpdateRequest,
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[RoleResponse]:
        if not ObjectId.is_valid(role_id):
            raise ValidationError(INVALID_ROLEID)

        updates = request.model_dump(by_alias=True, exclude_none=True)
        if not updates:
            return await cls.get_role(role_id, db=db)

        updates["updateAt"] = datetime.now(UTC)
        updates["updateBy"] = actor_user_id
        collection = await cls.get_collection(db)
        try:
            await collection.update_one({"_id": ObjectId(role_id)}, {"$set": updates})
            return await cls.get_role(role_id, db=db)
        except PyMongoError as exc:
            logger.exception("Failed to update role")
            raise DatabaseError("Failed to update role") from exc

    @classmethod
    async def delete_role(cls, role_id: str, db: AsyncIOMotorDatabase = None) -> bool:
        if not ObjectId.is_valid(role_id):
            raise ValidationError(INVALID_ROLEID)
        collection = await cls.get_collection(db)
        try:
            result = await collection.delete_one({"_id": ObjectId(role_id)})
            return result.deleted_count > 0
        except PyMongoError as exc:
            logger.exception("Failed to delete role")
            raise DatabaseError("Failed to delete role") from exc

    @classmethod
    async def get_role(
        cls,
        role_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[RoleResponse]:
        if not ObjectId.is_valid(role_id):
            raise ValidationError(INVALID_ROLEID)
        collection = await cls.get_collection(db)
        try:
            doc = await collection.find_one({"_id": ObjectId(role_id)})
            if doc is None:
                return None
            return cls._to_response(doc)
        except PyMongoError as exc:
            logger.exception("Failed to fetch role")
            raise DatabaseError("Failed to fetch role") from exc

    @classmethod
    async def update_role_permissions(
        cls,
        role_id: str,
        permissions: List[PermissionObject],
        actor_user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> Optional[RoleResponse]:
        if not ObjectId.is_valid(role_id):
            raise ValidationError(INVALID_ROLEID)

        collection = await cls.get_collection(db)
        permission_docs = [perm.model_dump(by_alias=True) for perm in permissions]
        try:
            result = await collection.update_one(
                {"_id": ObjectId(role_id)},
                {
                    "$set": {
                        "permissions": permission_docs,
                        "updateAt": datetime.now(UTC),
                        "updateBy": actor_user_id,
                    }
                },
            )
            if result.matched_count == 0:
                return None
            return await cls.get_role(role_id, db=db)
        except PyMongoError as exc:
            logger.exception("Failed to update role permissions")
            raise DatabaseError("Failed to update role permissions") from exc

    @staticmethod
    def _to_response(doc: dict) -> RoleResponse:
        doc = dict(doc)
        doc["_id"] = str(doc.get("_id", ObjectId()))
        return RoleResponse.model_validate(doc)
