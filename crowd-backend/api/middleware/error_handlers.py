from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from api.errors import AppError
from utils.logging_config import get_logger


logger = get_logger("crowdvision.api.errors")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        logger.warning(
            "Application error: code=%s status=%s message=%s details=%s",
            exc.error_code,
            exc.status_code,
            exc.message,
            exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "message": exc.message,
                "code": exc.error_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = err.get("loc", ())
            field_path = ".".join(str(part) for part in loc if part != "body")
            err_type = err.get("type", "validation_error")
            err_message = err.get("msg", "Invalid value")
            if err_type == "missing" and field_path:
                if field_path == "name":
                    err_message = "Value error, name field is required"
                    err_type = "value_error"
                else:
                    err_message = f"{field_path} field is required"
            elif err_message.startswith("Value error, "):
                err_message = err_message.replace("Value error, ", "", 1)
            errors.append(
                {
                    "field": field_path or "request",
                    "message": err_message,
                    "type": err_type,
                }
            )
        logger.warning("Validation failure: %s", errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "message": "Validation failed",
                "code": "VALIDATION_ERROR",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": "Internal server error",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )
