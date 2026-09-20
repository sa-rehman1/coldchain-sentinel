"""Consistent public API errors."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException

from coldchain.application.workflow import AuthorizationError, WorkflowConflictError


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    correlation_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class ServiceUnavailableError(RuntimeError):
    """Raised when a required dependency is unavailable."""


async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return _error_response(request, 403, "forbidden", str(exc))


async def workflow_conflict_handler(request: Request, exc: WorkflowConflictError) -> JSONResponse:
    return _error_response(request, 409, "workflow_conflict", str(exc))


async def unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
    return _error_response(
        request,
        500,
        "internal_error",
        "the request could not be completed",
    )


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unavailable")
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, correlation_id=correlation_id)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def service_unavailable_handler(
    request: Request, exc: ServiceUnavailableError
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unavailable")
    body = ErrorResponse(
        error=ErrorDetail(
            code="service_unavailable",
            message=str(exc),
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(status_code=503, content=body.model_dump(mode="json"))


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unavailable")
    body = ErrorResponse(
        error=ErrorDetail(
            code="http_error",
            message=str(exc.detail),
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unavailable")
    body = ErrorResponse(
        error=ErrorDetail(
            code="validation_error",
            message="request validation failed",
            correlation_id=correlation_id,
            details={"errors": exc.errors()},
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))
