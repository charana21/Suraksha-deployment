# """
# Authentication & User Management for CrowdVision

# Provides:
# - JWT token creation and verification
# - Password hashing with bcrypt
# - User CRUD operations (MongoDB)
# - Role-based access control (admin, operator, viewer)

# Roles:
#     admin: Full access - can create/delete users, manage system
#     operator: Same read access as viewer for now (role split planned later)
#     viewer: Read access to dashboards/analytics/alerts/reports
# """

# from datetime import datetime, timedelta, timezone
# from typing import Optional, Dict, Any, List
# from fastapi import Depends, HTTPException, status, Request
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from pydantic import BaseModel, Field
# from motor.motor_asyncio import AsyncIOMotorDatabase

# try:
#     from jose import JWTError, jwt
# except ImportError:
#     jwt = None
#     JWTError = Exception

# try:
#     from passlib.context import CryptContext
#     pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# except ImportError:
#     pwd_context = None

# from config.config import get_settings
# from db.mongodb import get_database

# # JWT Bearer security
# security = HTTPBearer(auto_error=False)


# def _normalize_profile_fields(data: Dict[str, Any]) -> Dict[str, Any]:
#     """Normalize optional profile fields before persistence."""
#     normalized = data.copy()

#     for field in ("full_name", "email", "phone", "designation"):
#         value = normalized.get(field)
#         if isinstance(value, str):
#             value = value.strip()
#             if value == "":
#                 value = None
#             if field == "email" and value is not None:
#                 value = value.lower()
#             normalized[field] = value

#     return normalized


# def _safe_datetime(val: Any, default_now: bool = False) -> Any:
#     """Handle invalid datetime strings from legacy records."""
#     if isinstance(val, str):
#         val = val.strip().lower()
#         if val in ('now', ''):
#             val = None
#     if val is None and default_now:
#         return datetime.now(timezone.utc)
#     return val


# # ============== Pydantic Models ==============

# class UserCreate(BaseModel):
#     """Schema for creating a new user (admin only)"""
#     username: str = Field(..., min_length=3, max_length=50)
#     password: str = Field(..., min_length=6)
#     role: str = Field(..., pattern="^(admin|operator|viewer)$")
#     full_name: Optional[str] = None
#     email: Optional[str] = Field(
#         None,
#         pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
#     )
#     phone: Optional[str] = Field(
#         None,
#         pattern=r"^\+?[0-9\-\s()]{7,20}$"
#     )
#     designation: Optional[str] = Field(None, max_length=100)


# class UserUpdate(BaseModel):
#     """Schema for updating user (admin only)"""
#     role: Optional[str] = Field(None, pattern="^(admin|operator|viewer)$")
#     full_name: Optional[str] = None
#     email: Optional[str] = Field(
#         None,
#         pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
#     )
#     phone: Optional[str] = Field(
#         None,
#         pattern=r"^\+?[0-9\-\s()]{7,20}$"
#     )
#     designation: Optional[str] = Field(None, max_length=100)
#     is_active: Optional[bool] = None


# class UserResponse(BaseModel):
#     """Schema for user response (no password)"""
#     username: str
#     role: str
#     full_name: Optional[str] = None
#     email: Optional[str] = None
#     phone: Optional[str] = None
#     designation: Optional[str] = None
#     is_active: bool = True
#     created_at: datetime
#     last_login: Optional[datetime] = None


# class UserProfileUpdate(BaseModel):
#     """Schema for updating own profile fields"""
#     full_name: Optional[str] = None
#     email: Optional[str] = Field(
#         None,
#         pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
#     )
#     phone: Optional[str] = Field(
#         None,
#         pattern=r"^\+?[0-9\-\s()]{7,20}$"
#     )
#     designation: Optional[str] = Field(None, max_length=100)


# class LoginRequest(BaseModel):
#     """Schema for login request"""
#     username: str
#     password: str


# class TokenResponse(BaseModel):
#     """Schema for token response"""
#     access_token: str
#     token_type: str = "bearer"
#     expires_in: int
#     role: str
#     username: str
#     full_name: Optional[str] = None
#     designation: Optional[str] = None


# class PasswordChange(BaseModel):
#     """Schema for password change"""
#     current_password: str
#     new_password: str = Field(..., min_length=6)


# class PasswordReset(BaseModel):
#     """Schema for admin password reset"""
#     new_password: str = Field(..., min_length=6)


# # ============== Password Functions ==============

# def hash_password(password: str) -> str:
#     """Hash a password using bcrypt"""
#     if pwd_context is None:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="passlib not installed. Run: pip install passlib[bcrypt]"
#         )
#     return pwd_context.hash(password)


# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     """Verify a password against its hash"""
#     if pwd_context is None:
#         return False
#     return pwd_context.verify(plain_password, hashed_password)


# # ============== Token Functions ==============

# def create_access_token(
#     data: Dict[str, Any],
#     expires_delta: Optional[timedelta] = None
# ) -> str:
#     """
#     Create a JWT access token.

#     Args:
#         data: Payload data (must include 'sub' for username)
#         expires_delta: Token expiration time

#     Returns:
#         Encoded JWT token
#     """
#     settings = get_settings()

#     if jwt is None:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="python-jose not installed. Run: pip install python-jose[cryptography]"
#         )

#     to_encode = data.copy()

#     expire = datetime.now(timezone.utc) + (
#         expires_delta or timedelta(hours=settings.jwt_expire_hours)
#     )

#     to_encode.update({
#         "exp": expire,
#         "iat": datetime.now(timezone.utc),
#         "iss": "crowdvision"
#     })

#     return jwt.encode(
#         to_encode,
#         settings.jwt_secret,
#         algorithm=settings.jwt_algorithm
#     )


# async def verify_token(
#     credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
# ) -> Dict[str, Any]:
#     """
#     Verify JWT token and return payload.

#     Raises:
#         HTTPException 401 if token is missing, invalid, or expired
#     """
#     settings = get_settings()

#     # Check if auth is disabled (development mode)
#     if not settings.auth_enabled:
#         return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

#     if jwt is None:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="JWT library not installed"
#         )

#     if credentials is None:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authentication required",
#             headers={"WWW-Authenticate": "Bearer"}
#         )

#     try:
#         payload = jwt.decode(
#             credentials.credentials,
#             settings.jwt_secret,
#             algorithms=[settings.jwt_algorithm]
#         )

#         username: str = payload.get("sub")
#         if username is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token: missing subject"
#             )

#         return payload

#     except JWTError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Invalid or expired token: {str(e)}",
#             headers={"WWW-Authenticate": "Bearer"}
#         )


# # ============== Dependencies ==============

# def require_auth():
#     """Dependency that requires valid authentication"""
#     return Depends(verify_token)



# def require_role(allowed_roles: list, methods: list = None):
#     """
#     Dependency factory that requires specific roles and optionally methods.

#     Usage:
#         @router.delete("/admin", dependencies=[require_role(["admin"])])
#         async def admin_only():
#             ...
#     """
#     async def role_checker(
#         request: Request,
#         payload: Dict = Depends(verify_token)
#     ) -> Dict:
#         # Dev mode bypass
#         if payload.get("auth_disabled"):
#             return payload

#         user_role = payload.get("role", "viewer")
        
#         # Method check for viewers and operators (Read-only)
#         # Skip check if the current method is explicitly allowed in the 'methods' list
#         if user_role in ["viewer", "operator"] and request.method not in ["GET", "HEAD", "OPTIONS"]:
#              if methods is None or request.method not in methods:
#                  raise HTTPException(
#                     status_code=status.HTTP_403_FORBIDDEN,
#                     detail="Access denied. Viewers and Operators have read-only access (GET requests only)."
#                 )

#         if user_role not in allowed_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Access denied. Required role: {' or '.join(allowed_roles)}"
#             )
#         return payload

#     return Depends(role_checker)


# # Pre-defined role requirements
# require_admin = require_role(["admin"])
# # Authorized roles (Admin ONLY now, since operator is restricted)
# require_authorized = require_role(["admin"])
# # Viewer role (Allowed for all, but request method restricted in require_role logic)
# require_viewer = require_role(["admin", "operator", "viewer"])

# # Alias legacy names if needed
# require_operator = require_authorized


# # ============== User Database Operations ==============

# class UserManager:
#     """
#     Manages user operations in MongoDB.

#     Collection: 'users'
#     """

#     COLLECTION = "users"

#     @classmethod
#     async def get_collection(cls, db: AsyncIOMotorDatabase = None):
#         """Get users collection (indexes are managed by admin/index sync command)."""
#         if db is None:
#             db = get_database()
#         return db[cls.COLLECTION]

#     @classmethod
#     async def create_user(
#         cls,
#         user_data: UserCreate,
#         db: AsyncIOMotorDatabase = None
#     ) -> UserResponse:
#         """
#         Create a new user.

#         Raises:
#             HTTPException 409 if username already exists
#         """
#         collection = await cls.get_collection(db)

#         # Check if username exists
#         existing = await collection.find_one({"username": user_data.username})
#         if existing:
#             raise HTTPException(
#                 status_code=status.HTTP_409_CONFLICT,
#                 detail=f"Username '{user_data.username}' already exists"
#             )

#         profile_data = _normalize_profile_fields(user_data.model_dump())

#         # Check if email exists (if provided)
#         email = profile_data.get("email")
#         if email:
#             existing_email = await collection.find_one({"email": email})
#             if existing_email:
#                 raise HTTPException(
#                     status_code=status.HTTP_409_CONFLICT,
#                     detail=f"Email '{email}' is already in use"
#                 )

#         # Check if phone exists (if provided)
#         phone = profile_data.get("phone")
#         if phone:
#             existing_phone = await collection.find_one({"phone": phone})
#             if existing_phone:
#                 raise HTTPException(
#                     status_code=status.HTTP_409_CONFLICT,
#                     detail=f"Phone number '{phone}' is already in use"
#                 )

#         # Create user document
#         now = datetime.now(timezone.utc)
#         user_doc = {
#             "username": user_data.username,
#             "password_hash": hash_password(user_data.password),
#             "role": user_data.role,
#             "full_name": profile_data.get("full_name"),
#             "email": profile_data.get("email"),
#             "phone": profile_data.get("phone"),
#             "designation": profile_data.get("designation"),
#             "is_active": True,
#             "created_at": now,
#             "last_login": None
#         }

#         await collection.insert_one(user_doc)

#         return UserResponse(
#             username=user_doc["username"],
#             role=user_doc["role"],
#             full_name=user_doc["full_name"],
#             email=user_doc.get("email"),
#             phone=user_doc.get("phone"),
#             designation=user_doc.get("designation"),
#             is_active=user_doc["is_active"],
#             created_at=user_doc["created_at"],
#             last_login=user_doc["last_login"]
#         )

#     @classmethod
#     async def authenticate(
#         cls,
#         username: str,
#         password: str,
#         db: AsyncIOMotorDatabase = None
#     ) -> Optional[Dict]:
#         """
#         Authenticate user with username and password.

#         Returns:
#             User document if authenticated, None otherwise
#         """
#         collection = await cls.get_collection(db)

#         user = await collection.find_one({"username": username})
#         if user is None:
#             return None

#         if not user.get("is_active", True):
#             return None

#         if not verify_password(password, user.get("password_hash", "")):
#             return None

#         # Update last login
#         await collection.update_one(
#             {"username": username},
#             {"$set": {"last_login": datetime.now(timezone.utc)}}
#         )

#         return user

#     @classmethod
#     async def get_user(
#         cls,
#         username: str,
#         db: AsyncIOMotorDatabase = None
#     ) -> Optional[UserResponse]:
#         """Get user by username"""
#         collection = await cls.get_collection(db)

#         user = await collection.find_one({"username": username})
#         if user is None:
#             return None

#         return UserResponse(
#             username=user.get("username", "unknown"),
#             role=user.get("role", "viewer"),
#             full_name=user.get("full_name"),
#             email=user.get("email"),
#             phone=user.get("phone"),
#             designation=user.get("designation"),
#             is_active=user.get("is_active", True),
#             created_at=_safe_datetime(user.get("created_at"), default_now=True),
#             last_login=_safe_datetime(user.get("last_login"))
#         )

#     @classmethod
#     async def list_users(
#         cls,
#         db: AsyncIOMotorDatabase = None
#     ) -> List[UserResponse]:
#         """List all users"""
#         collection = await cls.get_collection(db)

#         users = []
#         async for user in collection.find():
#             users.append(UserResponse(
#                 username=user.get("username", "unknown"),
#                 role=user.get("role", "viewer"),
#                 full_name=user.get("full_name"),
#                 email=user.get("email"),
#                 phone=user.get("phone"),
#                 designation=user.get("designation"),
#                 is_active=user.get("is_active", True),
#                 created_at=_safe_datetime(user.get("created_at"), default_now=True),
#                 last_login=_safe_datetime(user.get("last_login"))
#             ))

#         return users

#     @classmethod
#     async def update_user(
#         cls,
#         username: str,
#         updates: UserUpdate,
#         db: AsyncIOMotorDatabase = None
#     ) -> Optional[UserResponse]:
#         """Update user fields"""
#         collection = await cls.get_collection(db)

#         update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
#         update_data = _normalize_profile_fields(update_data)

#         if not update_data:
#             return await cls.get_user(username, db)

#         result = await collection.update_one(
#             {"username": username},
#             {"$set": update_data}
#         )

#         if result.matched_count == 0:
#             return None

#         return await cls.get_user(username, db)

#     @classmethod
#     async def update_profile(
#         cls,
#         username: str,
#         updates: UserProfileUpdate,
#         db: AsyncIOMotorDatabase = None
#     ) -> Optional[UserResponse]:
#         """Update self-service profile fields."""
#         collection = await cls.get_collection(db)
#         update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
#         update_data = _normalize_profile_fields(update_data)

#         if not update_data:
#             return await cls.get_user(username, db)

#         result = await collection.update_one(
#             {"username": username},
#             {"$set": update_data}
#         )
#         if result.matched_count == 0:
#             return None
#         return await cls.get_user(username, db)

#     @classmethod
#     async def change_password(
#         cls,
#         username: str,
#         current_password: str,
#         new_password: str,
#         db: AsyncIOMotorDatabase = None
#     ) -> bool:
#         """
#         Change user password.

#         Returns:
#             True if password changed, False if current password wrong
#         """
#         collection = await cls.get_collection(db)

#         user = await collection.find_one({"username": username})
#         if user is None:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="User not found"
#             )

#         if not verify_password(current_password, user.get("password_hash", "")):
#             return False

#         await collection.update_one(
#             {"username": username},
#             {"$set": {"password_hash": hash_password(new_password)}}
#         )

#         return True

#     @classmethod
#     async def reset_password(
#         cls,
#         username: str,
#         new_password: str,
#         db: AsyncIOMotorDatabase = None
#     ) -> bool:
#         """Reset password (admin only, no current password needed)"""
#         collection = await cls.get_collection(db)

#         result = await collection.update_one(
#             {"username": username},
#             {"$set": {"password_hash": hash_password(new_password)}}
#         )

#         return result.matched_count > 0

#     @classmethod
#     async def delete_user(
#         cls,
#         username: str,
#         db: AsyncIOMotorDatabase = None
#     ) -> bool:
#         """Delete a user"""
#         collection = await cls.get_collection(db)

#         result = await collection.delete_one({"username": username})
#         return result.deleted_count > 0

#     @classmethod
#     async def count_admins(
#         cls,
#         db: AsyncIOMotorDatabase = None
#     ) -> int:
#         """Count active admin users"""
#         collection = await cls.get_collection(db)
#         return await collection.count_documents({
#             "role": "admin",
#             "is_active": True
#         })

#     @classmethod
#     async def user_exists(
#         cls,
#         db: AsyncIOMotorDatabase = None
#     ) -> bool:
#         """Check if any user exists"""
#         collection = await cls.get_collection(db)
#         count = await collection.count_documents({})
#         return count > 0


# # ============== WebSocket Authentication ==============

# async def verify_ws_token(token: str) -> Optional[Dict[str, Any]]:
#     """
#     Verify JWT token for WebSocket connections.

#     Args:
#         token: JWT token string

#     Returns:
#         Token payload if valid, None if invalid/missing
#     """
#     if not token:
#         return None

#     settings = get_settings()

#     # If auth disabled, allow all connections
#     if not settings.auth_enabled:
#         return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

#     if jwt is None:
#         return None

#     try:
#         payload = jwt.decode(
#             token,
#             settings.jwt_secret,
#             algorithms=[settings.jwt_algorithm]
#         )

#         username = payload.get("sub")
#         if username is None:
#             return None

#         return payload

#     except JWTError:
#         return None


# async def ws_auth_required(
#     websocket,  # WebSocket type imported in routes
#     token: Optional[str]
# ) -> Optional[Dict[str, Any]]:
#     """
#     WebSocket authentication helper.

#     Call this BEFORE websocket.accept() to validate the token.
#     If auth fails, closes the connection with code 4001.

#     Args:
#         websocket: FastAPI WebSocket instance
#         token: JWT token from query param (?token=xxx)

#     Returns:
#         Token payload if authenticated, None if connection was closed

#     Usage:
#         @router.websocket("/ws/analytics")
#         async def ws_endpoint(websocket: WebSocket, token: str = Query(None)):
#             payload = await ws_auth_required(websocket, token)
#             if payload is None:
#                 return  # Connection closed

#             # Proceed with authenticated connection
#             await manager.connect(websocket)
#     """
#     settings = get_settings()

#     # If auth disabled, allow all connections
#     if not settings.auth_enabled:
#         return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

#     # No token provided
#     if not token:
#         await websocket.close(code=4001, reason="Missing authentication token")
#         return None

#     # Validate token
#     payload = await verify_ws_token(token)
#     if payload is None:
#         await websocket.close(code=4001, reason="Invalid or expired token")
#         return None

#     return payload


# async def ws_role_required(
#     websocket,
#     token: Optional[str],
#     allowed_roles: List[str]
# ) -> Optional[Dict[str, Any]]:
#     """
#     WebSocket auth + role enforcement helper.

#     Closes with code 4003 when role is not allowed.
#     """
#     payload = await ws_auth_required(websocket, token)
#     if payload is None:
#         return None

#     if payload.get("auth_disabled"):
#         return payload

#     user_role = payload.get("role", "viewer")
#     if user_role not in allowed_roles:
#         await websocket.close(
#             code=4003,
#             reason=f"Access denied. Required role: {' or '.join(allowed_roles)}"
#         )
#         return None

#     return payload


# __all__ = [
#     "UserCreate",
#     "UserUpdate",
#     "UserProfileUpdate",
#     "UserResponse",
#     "LoginRequest",
#     "TokenResponse",
#     "PasswordChange",
#     "PasswordReset",
#     "hash_password",
#     "verify_password",
#     "create_access_token",
#     "verify_token",
#     "require_auth",
#     "require_role",
#     "require_admin",
#     "require_operator",
#     "require_viewer",
#     "UserManager",
#     "verify_ws_token",
#     "ws_auth_required",
#     "ws_role_required",
# ]
