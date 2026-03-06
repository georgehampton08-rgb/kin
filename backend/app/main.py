import os
import re
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.security import JWTAuthMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.rate_limiter import limiter
from app.core.mqtt import MQTTListener
from app.core.ws_manager import ws_manager
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.exception_handlers import (
    generic_exception_handler,
    validation_exception_handler,
    http_exception_handler,
)
from app.api.v1.endpoints.health import set_mqtt_listener

logger = logging.getLogger(__name__)

WS_MAX_MESSAGE_BYTES = 65536  # 64 KB

mqtt_listener = MQTTListener()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — load secrets first, before anything else
    from app.core.secrets_loader import load_secrets
    from app.core.auth import reload_secrets
    load_secrets()
    reload_secrets()
    logger.info("Application secrets loaded successfully")

    mqtt_listener.start()
    set_mqtt_listener(mqtt_listener)
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    mqtt_listener.stop()


# Build CORS origins from env — supports comma-separated list for multi-origin prod setups
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://kin-tracker.web.app"
)
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(title="Kin Backend API", version="2.0.0", lifespan=lifespan)

# ── Rate limiter state ──────────────────────────────────────────
app.state.limiter = limiter


async def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 handler that includes Retry-After header."""
    response = JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )
    response.headers["Retry-After"] = "60"
    logger.warning(
        f"Rate limit exceeded: {request.client.host} on {request.url.path}"
    )
    return response


app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)

# ── Global exception handlers ──────────────────────────────────
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# ── Middleware stack (order matters: first added = outermost) ───
# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — locked to explicit origin allowlist from env
# JWT is sent via Authorization header, not cookies, so allow_credentials=False
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Content-Encoding"],
)

# JWT authentication
app.add_middleware(JWTAuthMiddleware)

# Mount /health at root level (not under /api/v1) so Cloud Run probe hits it cheaply
from app.api.v1.endpoints import health as health_module
app.include_router(health_module.router)

app.include_router(api_router, prefix="/api/v1")


# ── WebSocket endpoint with security hardening ──────────────────

# UUID v4 pattern for device_id validation
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)


def _is_valid_device_id(device_id: str) -> bool:
    """Check device_id is a plausible identifier (UUID or SHA-256 hash)."""
    if not device_id or len(device_id) > 255:
        return False
    return True


@app.websocket("/ws/live/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    # Validate device_id format
    if not _is_valid_device_id(device_id):
        await websocket.close(code=1008)
        return

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        from app.core.auth import decode_token
        payload = decode_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    family_id = payload.get("family_id")
    if not family_id:
        await websocket.close(code=1008)
        return

    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.location import Device
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Device).where(
                Device.device_identifier == device_id,
                Device.family_id == family_id
            )
        )
        if not result.scalar_one_or_none():
            await websocket.close(code=1008)
            return

    await ws_manager.connect(device_id, websocket)
    await ws_manager.push_device_status(device_id)
    try:
        while True:
            data = await websocket.receive_bytes()
            # Enforce max message size (64 KB)
            if len(data) > WS_MAX_MESSAGE_BYTES:
                logger.warning(
                    f"WebSocket message too large from device {device_id}: "
                    f"{len(data)} bytes (max {WS_MAX_MESSAGE_BYTES})"
                )
                await websocket.close(code=1009)
                break
    except WebSocketDisconnect:
        ws_manager.disconnect(device_id, websocket)


@app.get("/")
def root():
    return {"message": "Welcome to the Kin API v2"}
