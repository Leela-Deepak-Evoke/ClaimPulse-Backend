from collections.abc import Mapping
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()

_STATUS_CODES = {
    401: "NOT_AUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


class AppError(Exception):
    """An expected error that maps to a client response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _envelope(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "requestId": getattr(request.state, "request_id", None),
    }
    if details:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code, headers=headers)


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(AppError, exc)
    return _envelope(request, exc.status_code, exc.code, exc.message, headers=exc.headers)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"][1:]),
            "message": str(err["msg"]).removeprefix("Value error, "),
        }
        for err in exc.errors()
    ]
    return _envelope(request, 422, "VALIDATION_ERROR", "Request validation failed.", details)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code = _STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    return _envelope(request, exc.status_code, code, str(exc.detail), headers=exc.headers)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", path=request.url.path, exc_info=exc)
    return _envelope(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
