import os
import logging
from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

# Imported lazily to avoid circular import; assigned at startup by main.py
_mqtt_listener = None

def set_mqtt_listener(listener):
    global _mqtt_listener
    _mqtt_listener = listener


@router.get("/health", tags=["health"])
async def health_check():
    """
    Liveness + readiness probe used by Cloud Run startup probe and CI/CD canary check.
    Returns 200 only when both the database and MQTT broker are reachable.
    """
    version = os.getenv("APP_VERSION", "local")
    result = {
        "status": "ok",
        "db": "connected",
        "broker": "connected",
        "version": version,
    }

    # ── DB check ──────────────────────────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        result["db"] = f"error: {e}"
        result["status"] = "degraded"

    # ── Broker check ──────────────────────────────────────────────────────────
    try:
        if _mqtt_listener is None or not _mqtt_listener.client.is_connected():
            result["broker"] = "disconnected"
            result["status"] = "degraded"
    except Exception as e:
        logger.error(f"Health check broker error: {e}")
        result["broker"] = f"error: {e}"
        result["status"] = "degraded"

    return result
