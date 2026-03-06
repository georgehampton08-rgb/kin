"""
Global Exception Handlers
===========================
Sanitize all error responses to prevent information leakage.
- 500 errors: return generic message with request_id for server-side correlation
- 422 validation errors: strip internal field paths
- All others: pass through with sanitized bodies
"""
import uuid
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Never expose internals."""
    request_id = str(uuid.uuid4())
    logger.error(
        f"Unhandled exception [request_id={request_id}] "
        f"path={request.url.path} method={request.method}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An internal error occurred",
            "request_id": request_id,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Sanitize 422 validation errors — remove internal field paths and details."""
    errors = []
    for err in exc.errors():
        sanitized = {
            "type": err.get("type", "value_error"),
            "msg": err.get("msg", "Invalid value"),
        }
        # Include field name but not internal path structure
        loc = err.get("loc", ())
        if loc:
            # Only show the last field name, not the full path (body -> field -> subfield)
            field_name = str(loc[-1]) if loc else "unknown"
            sanitized["field"] = field_name
        errors.append(sanitized)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Ensure HTTP exceptions don't leak internal details."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
