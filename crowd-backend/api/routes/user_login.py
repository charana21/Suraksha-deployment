"""
Master RBAC endpoints for modules, roles, users, and user login audit.
"""

from typing import List
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson import ObjectId
from pydantic import BaseModel, Field
from config.config import get_settings
from api.errors import NotFoundError, UnauthorizedError
try:
    from jose import JWTError, jwt
except ImportError:
    jwt = None
    JWTError = Exception

from modules.modules import (
    ModuleCreateRequest,
    ModuleListResponse,
    ModuleUpdateRequest,
    ModuleManager,
    ModuleResponse,
)
from modules.roles import (
    PermissionObject,
    RoleCreateRequest,
    RoleListResponse,
    RoleManager,
    RoleResponse,
    RoleUpdateRequest,
)
from modules.users import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
    UsersManager,
)
from modules.selfservice import SelfServiceManager, UserDetails
from api.security import verify_token
from util.constants import ROLE_NOT_FOUND

router = APIRouter(prefix="/master", tags=["Master modules"])
security = HTTPBearer(auto_error=False)

class ActionResponse(BaseModel):
    response_msg: str = Field(..., alias="responseMsg")
    response_code: int = Field(200, alias="responseCode")


class UserActionResponse(ActionResponse):
    user: UserResponse


class RoleActionResponse(ActionResponse):
    role: RoleResponse


class ModuleActionResponse(ActionResponse):
    module: ModuleResponse

async def get_actor_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Resolve actor user id from Bearer token payload (uID preferred).
    """
    if jwt is None:
        raise UnauthorizedError("Authentication service unavailable")
    if credentials is None:
        raise UnauthorizedError("Authorization token is required")

    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    actor_user_id = payload.get("uID") or payload.get("userID")
    if not actor_user_id and ObjectId.is_valid(str(payload.get("sub", ""))):
        actor_user_id = str(payload["sub"])

    if not actor_user_id or not ObjectId.is_valid(actor_user_id):
        raise UnauthorizedError("Invalid token payload")
    return actor_user_id


@router.post("/login", response_model=TokenResponse)
async def user_login(request: LoginRequest):
    """Login by email/password and write userlogin audit record."""
    return await UsersManager.login(request)


@router.post("/users", response_model=UserActionResponse)
async def create_user(
    request: UserCreateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    """Create user in viewers_user_collection."""
    user = await UsersManager.create_user(request, actor_user_id=actor_user_id)
    return UserActionResponse(responseMsg="New user created successfully", user=user)


@router.get("/users", response_model=UserListResponse)
async def list_users(_payload: dict = Depends(verify_token)):
    users = await UsersManager.list_users()
    return UserListResponse(count=len(users), users=users)


@router.put("/users/change-password", response_model=ActionResponse)
async def change_password(
    request: ChangePasswordRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    """Self-service password change for the logged-in user, identified via JWT."""
    await UsersManager.change_password(actor_user_id, request)
    return ActionResponse(responseMsg="Password changed successfully")


@router.put("/users/{user_id}", response_model=UserActionResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    user = await UsersManager.update_user(user_id, request, actor_user_id=actor_user_id)
    if user is None:
        raise NotFoundError("User not found")
    return UserActionResponse(responseMsg="updated user successfully", user=user)


@router.delete("/users/{user_id}", response_model=ActionResponse)
async def delete_user(
    user_id: str,
    _payload: dict = Depends(verify_token),
):
    deleted = await UsersManager.delete_user(user_id)
    if not deleted:
        raise NotFoundError("User not found")
    return ActionResponse(responseMsg="deleted user successfully")


@router.post("/roles", response_model=RoleActionResponse)
async def create_role(
    request: RoleCreateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    """Create role in roles collection."""
    role = await RoleManager.create_role(request, actor_user_id=actor_user_id)
    return RoleActionResponse(responseMsg="New role created successfully", role=role)


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(_payload: dict = Depends(verify_token)):
    roles = await RoleManager.list_roles()
    return RoleListResponse(count=len(roles), roles=roles)


@router.put("/roles/{role_id}", response_model=RoleActionResponse)
async def update_role(
    role_id: str,
    request: RoleUpdateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    role = await RoleManager.update_role(role_id, request, actor_user_id=actor_user_id)
    if role is None:
        raise NotFoundError(ROLE_NOT_FOUND)

    return RoleActionResponse(
        responseMsg="updated role successfully",
        role=role,
    )

@router.delete("/roles/{role_id}", response_model=ActionResponse)
async def delete_role(
    role_id: str,
    _payload: dict = Depends(verify_token),
):
    deleted = await RoleManager.delete_role(role_id)
    if not deleted:
        raise NotFoundError(ROLE_NOT_FOUND)
    return ActionResponse(responseMsg="deleted role successfully")


@router.put("/roles/permissions/{role_id}", response_model=RoleActionResponse)
async def update_role_permissions(
    role_id: str,
    permissions: List[PermissionObject],
    actor_user_id: str = Depends(get_actor_user_id),
):
    role = await RoleManager.update_role_permissions(
        role_id=role_id,
        permissions=permissions,
        actor_user_id=actor_user_id,
    )
    if role is None:
        raise NotFoundError(ROLE_NOT_FOUND)
    return RoleActionResponse(responseMsg="permissions updated successfully", role=role)


@router.get("/userdetail", response_model=UserDetails)
async def get_my_permissions(actor_user_id: str = Depends(get_actor_user_id)):
    return await SelfServiceManager.get_my_permissions(actor_user_id)


@router.post("/modules", response_model=ModuleActionResponse)
async def create_module(
    request: ModuleCreateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    """Create module in modules collection."""
    module = await ModuleManager.create_module(request, actor_user_id=actor_user_id)
    return ModuleActionResponse(responseMsg="New module created successfully", module=module)


@router.get("/modules", response_model=ModuleListResponse)
async def list_modules(_payload: dict = Depends(verify_token)):
    modules = await ModuleManager.list_modules()
    return ModuleListResponse(count=len(modules), modules=modules)


@router.put("/modules/{module_id}", response_model=ModuleActionResponse)
async def update_module(
    module_id: str,
    request: ModuleUpdateRequest,
    actor_user_id: str = Depends(get_actor_user_id),
):
    module = await ModuleManager.update_module(module_id, request, actor_user_id=actor_user_id)
    if module is None:
        raise NotFoundError("Module not found")
    return ModuleActionResponse(responseMsg="updated module successfully", module=module)


@router.delete("/modules/{module_id}", response_model=ActionResponse)
async def delete_module(
    module_id: str,
    _payload: dict = Depends(verify_token),
):
    deleted = await ModuleManager.delete_module(module_id)
    if not deleted:
        raise NotFoundError("Module not found")
    return ActionResponse(responseMsg="deleted module successfully")
