"""Stable public API error contracts and FastAPI exception mapping."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

ApiErrorCode = Literal[
    "VALIDATION_FAILED",
    "SESSION_EXPIRED",
    "SESSION_NOT_FOUND",
    "RATE_LIMITED",
    "AI_UNAVAILABLE",
    "AI_BUDGET_EXHAUSTED",
    "QUOTE_VERSION_CONFLICT",
    "OPERATION_UNCERTAIN",
    "CONFIRMATION_INVALID",
    "SKU_NOT_RESOLVED",
    "NOT_FOUND",
]


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ApiErrorCode
    message: str
    request_id: UUID
    retryable: bool = False
    details: dict[str, str] | None = None


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ApiError


_STATUS_CODES: dict[int, ApiErrorCode] = {
    401: "SESSION_NOT_FOUND",
    403: "VALIDATION_FAILED",
    404: "NOT_FOUND",
    409: "OPERATION_UNCERTAIN",
    422: "VALIDATION_FAILED",
    500: "AI_UNAVAILABLE",
}

_STATUS_DESCRIPTIONS = {
    401: "Guest authentication is required.",
    403: "Trusted Origin validation failed.",
    404: "The requested resource was not found.",
    409: "The request conflicts with committed state.",
    422: "The request is invalid.",
    500: "The request could not be completed.",
}


def api_error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Return route-specific OpenAPI error declarations using the shared envelope."""
    return {
        status_code: {
            "model": ApiErrorResponse,
            "description": _STATUS_DESCRIPTIONS[status_code],
        }
        for status_code in status_codes
    }


def _request_id(request: Request) -> UUID:
    """Use a caller correlation ID only when it is a valid UUID."""
    try:
        return UUID(request.headers.get("x-request-id", ""))
    except ValueError:
        return uuid4()


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, error: HTTPException) -> JSONResponse:
        request_id = _request_id(_)
        detail: Any = error.detail
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            code = detail["code"]
            message = str(detail.get("message", "Request could not be completed."))
        else:
            code = _STATUS_CODES.get(error.status_code, "AI_UNAVAILABLE")
            message = str(detail)
        return JSONResponse(
            status_code=error.status_code,
            content=ApiErrorResponse(
                error=ApiError(code=code, message=message, request_id=request_id)
            ).model_dump(mode="json"),
            headers={**(error.headers or {}), "X-Request-ID": str(request_id)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, __: RequestValidationError) -> JSONResponse:
        request_id = _request_id(_)
        return JSONResponse(
            status_code=422,
            content=ApiErrorResponse(
                error=ApiError(
                    code="VALIDATION_FAILED",
                    message="Request validation failed.",
                    request_id=request_id,
                )
            ).model_dump(mode="json"),
            headers={"X-Request-ID": str(request_id)},
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_: Request, __: Exception) -> JSONResponse:
        request_id = _request_id(_)
        return JSONResponse(
            status_code=500,
            content=ApiErrorResponse(
                error=ApiError(
                    code="AI_UNAVAILABLE",
                    message="The request could not be completed.",
                    request_id=request_id,
                )
            ).model_dump(mode="json"),
            headers={"X-Request-ID": str(request_id)},
        )
