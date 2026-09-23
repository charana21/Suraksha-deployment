from typing import List
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from api.errors import DatabaseError, NotFoundError, ValidationError
from db.mongodb import get_database
from modules.roles import PermissionObject
from utils.logging_config import get_logger

class Permission(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    module_id: str = Field(..., alias="moduleID")
    module_name: str = Field(..., alias="moduleName")
    url_name: str = Field(..., alias="urlName")
    master: bool = Field(False, alias="master")
    actions: PermissionObject = Field(..., alias="actions")


class UserDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId")
    role_id: str = Field(..., alias="roleID")
    user_name: str = Field(..., alias="userName")
    role_name: str = Field(..., alias="roleName")
    email: str = Field(..., alias="email")
    modules: List[Permission] = Field(default_factory=list, alias="modules")


class SelfServiceManager:
    USER_COLLECTION = "viewers_user_collection"
    ROLE_COLLECTION = "roles"
    MODULE_COLLECTION = "modules"
    logger = get_logger("crowdvision.modules.selfservice")

    @classmethod
    async def _db(cls, db: AsyncIOMotorDatabase = None):
        if db is None:
            db = get_database()
        if db is None:
            raise DatabaseError("Authentication database unavailable")
        return db

    @classmethod
    async def get_my_permissions(
        cls,
        user_id: str,
        db: AsyncIOMotorDatabase = None,
    ) -> UserDetails:
        if not ObjectId.is_valid(user_id):
            raise ValidationError("Invalid user id")

        database = await cls._db(db)
        users = database[cls.USER_COLLECTION]
        roles = database[cls.ROLE_COLLECTION]
        modules = database[cls.MODULE_COLLECTION]

        try:
            user_doc = await users.find_one({"_id": ObjectId(user_id)})
            if user_doc is None:
                raise NotFoundError("User not found")

            role_id = user_doc.get("roleID")
            if not role_id or not ObjectId.is_valid(str(role_id)):
                raise ValidationError("User role is missing or invalid")

            role_doc = await roles.find_one({"_id": ObjectId(str(role_id))})
            if role_doc is None:
                raise NotFoundError("Role not found")

            module_docs = await modules.find({}).to_list(length=None)
        except (DatabaseError, NotFoundError, ValidationError):
            raise
        except PyMongoError as exc:
            cls.logger.exception("Failed to load self-service permissions for user=%s", user_id)
            raise DatabaseError("Failed to fetch user permissions") from exc

        role_permissions = role_doc.get("permissions", [])
        modules_out: List[Permission] = []

        for role_perm in role_permissions:
            role_perm_module_id = str(role_perm.get("moduleID", ""))
            for module_doc in module_docs:
                module_id = str(module_doc.get("_id"))
                if module_id == role_perm_module_id:
                    modules_out.append(
                        Permission(
                            moduleID=module_id,
                            moduleName=module_doc.get("name", ""),
                            urlName=module_doc.get("urlName", ""),
                            master=bool(module_doc.get("master", False)),
                            actions=PermissionObject(
                                moduleID=role_perm_module_id,
                                add=int(role_perm.get("add", 0)),
                                edit=int(role_perm.get("edit", 0)),
                                view=int(role_perm.get("view", 0)),
                                delete=int(role_perm.get("delete", 0)),
                            ),
                        )
                    )

        modules_out.reverse()

        return UserDetails(
            userId=str(user_doc["_id"]),
            roleID=str(role_doc["_id"]),
            userName=user_doc.get("name", ""),
            roleName=role_doc.get("name", ""),
            email=user_doc.get("email", ""),
            modules=modules_out,
        )
