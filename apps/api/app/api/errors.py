from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)
_SAFE_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", "req_" + uuid.uuid4().hex[:20])


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str | None]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    safe_code = code if _SAFE_CODE.fullmatch(code) else "INTERNAL_ERROR"
    body: dict[str, Any] = {
        "error": {
            "code": safe_code,
            "message": message,
            "request_id": request_id_for(request),
            "details": details or [],
        }
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _safe_validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for item in exc.errors():
        location = item.get("loc", ())
        field = ".".join(str(part) for part in location if part != "body") or None
        # Never include Pydantic's input/context; they may contain raw identifiers or CSV.
        details.append({"field": field, "reason": "Request value is missing or invalid."})
    return details


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            request,
            422,
            "VALIDATION_ERROR",
            "Request body or parameters failed validation.",
            _safe_validation_details(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = exc.status_code
        code, message = {
            400: ("BAD_REQUEST", "The request could not be processed."),
            401: ("UNAUTHORIZED", "Authentication is required or has expired."),
            403: ("FORBIDDEN", "You are not permitted to perform this operation."),
            404: ("NOT_FOUND", "The requested resource was not found."),
            405: ("METHOD_NOT_ALLOWED", "The HTTP method is not allowed for this resource."),
            429: ("TOO_MANY_REQUESTS", "Too many requests. Try again later."),
            409: (
                "CAPACITY_CONFLICT",
                "The request conflicts with current approved intake capacity.",
            ),
        }.get(status, ("HTTP_ERROR", "The request could not be completed."))
        safe_headers = {
            key: value
            for key, value in (exc.headers or {}).items()
            if key.lower() in {"www-authenticate", "retry-after"}
        }
        return error_response(request, status, code, message, headers=safe_headers)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request failure request_id=%s exception_type=%s",
            request_id_for(request),
            type(exc).__name__,
        )
        return error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "An internal error occurred.",
        )


def make_request_id(value: str | None) -> str:
    if value and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        return value
    return "req_" + uuid.uuid4().hex[:20]


def error_details_from_mapping(value: Mapping[str, str]) -> list[dict[str, str]]:
    return [{"field": key, "reason": reason} for key, reason in value.items()]
