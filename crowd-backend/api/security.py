"""
Shared API security dependencies.

This module keeps JWT verification and auth dependencies independent from the
legacy /auth user-management system.
"""

from typing import Any, Dict, List, Optional
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from api.errors import ForbiddenError, InternalServerError, UnauthorizedError
from config.config import get_settings
from utils.logging_config import get_logger
try:
    from jose import JWTError, jwt
except ImportError:
    jwt = None
    JWTError = Exception

security = HTTPBearer(auto_error=False)
logger = get_logger("crowdvision.api.security")

async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """Verify JWT token and return payload."""
    settings = get_settings()

    if not settings.auth_enabled:
        return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

    if jwt is None:
        raise InternalServerError("Authentication service unavailable")

    if credentials is None:
        raise UnauthorizedError("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        logger.warning("Token verification failed")
        raise UnauthorizedError("Invalid or expired token") from exc

    # Accept both old and new token payload shapes.
    if not any(payload.get(k) for k in ("sub", "uID", "userID", "email")):
        raise UnauthorizedError("Invalid token payload")

    return payload


def internal_forward_headers(request: Optional[Request] = None) -> Dict[str, str]:
    """Mark an internal shard request and preserve the caller's authorization."""
    headers = {"X-Internal-Forwarded": "true"}
    if request is not None:
        authorization = request.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization
    return headers


def require_auth():
    return Depends(verify_token)


def require_role(allowed_roles: List[str], methods: Optional[List[str]] = None):
    """
    Dependency factory.
    Role checks are intentionally bypassed currently to preserve existing behavior.
    """

    async def role_checker(
        request: Request,
        payload: Dict[str, Any] = Depends(verify_token),
    ) -> Dict[str, Any]:
        _ = methods
        role = str(payload.get("role", "")).lower()
        normalized_roles = [r.lower() for r in allowed_roles]
        if role and role not in normalized_roles:
            logger.warning(
                "Forbidden access: method=%s path=%s role=%s allowed=%s",
                request.method,
                request.url.path,
                role,
                normalized_roles,
            )
            raise ForbiddenError("Unauthorized access")
        return payload

    return Depends(role_checker)


require_admin = require_role(["admin"])
require_authorized = require_role(["admin", "operator"])
require_viewer = require_role(["admin", "operator", "viewer"])
require_operator = require_authorized


async def verify_ws_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None

    settings = get_settings()
    if not settings.auth_enabled:
        return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

    if jwt is None:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    if any(payload.get(k) for k in ("sub", "uID", "userID", "email")):
        return payload
    return None


async def ws_auth_required(websocket, token: Optional[str]) -> Optional[Dict[str, Any]]:
    settings = get_settings()

    if not settings.auth_enabled:
        return {"sub": "dev_user", "role": "admin", "auth_disabled": True}

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return None

    payload = await verify_ws_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return None

    return payload


async def ws_role_required(
    websocket, token: Optional[str], allowed_roles: List[str]
) -> Optional[Dict[str, Any]]:
    payload = await ws_auth_required(websocket, token)
    if payload is None:
        return None

    role = str(payload.get("role", "")).lower()
    normalized_roles = [r.lower() for r in allowed_roles]
    if role and role not in normalized_roles:
        await websocket.close(code=4003, reason="Unauthorized access")
        return None

    return payload

