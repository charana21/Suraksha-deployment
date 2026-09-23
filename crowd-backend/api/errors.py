from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            **kwargs,
        )


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            **kwargs,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Unauthorized access", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            **kwargs,
        )


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            **kwargs,
        )


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            **kwargs,
        )


class DatabaseError(AppError):
    def __init__(self, message: str = "Database operation failed", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="DATABASE_ERROR",
            **kwargs,
        )


class InternalServerError(AppError):
    def __init__(self, message: str = "Internal server error", **kwargs: Any) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            **kwargs,
        )


def app_error_to_http_exception(exc: AppError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "message": exc.message,
            "code": exc.error_code,
        },
    )
