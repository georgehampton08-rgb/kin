"""
Heartbeat Endpoint
===================
POST /api/v1/telemetry/heartbeat

Accepts a lightweight ping from the device every 5 minutes.
Upserts device_status: sets status=ONLINE, records battery + GPS accuracy.

If no heartbeat arrives within 12 minutes, APScheduler marks the device STALE.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import text

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.db.session import AsyncSessionLocal

router = APIRouter()


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    device_id: str = Field(..., min_length=1, max_length=255, description="Unique device identifier")
    battery_level: float | None = Field(None, ge=0, le=100)
    gps_accuracy: float | None = Field(None, ge=0, le=1000, description="Accuracy in metres")
    timestamp: datetime | None = Field(None)

    @field_validator("timestamp")
    @classmethod
    def validate_ts(cls, v):
        if v is not None:
            now = datetime.now(timezone.utc)
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v > now + timedelta(seconds=60):
                raise ValueError("Timestamp cannot be more than 60 seconds in the future")
            if v < now - timedelta(hours=24):
                raise ValueError("Timestamp cannot be older than 24 hours")
        return v


@router.post("/heartbeat")
@limiter.limit("60/minute")
async def heartbeat(
    request: Request,
    payload: HeartbeatPayload,
    user: dict = Depends(get_current_user),
):
    """Upsert device_status and reset staleness clock."""
    family_id = user.get("family_id")
    now = payload.timestamp or datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO device_status
                    (device_id, family_id, status, battery_level, gps_accuracy, last_heartbeat, updated_at)
                VALUES (:device_id, :family_id, 'ONLINE', :battery, :accuracy, :hb, now())
                ON CONFLICT (device_id) DO UPDATE SET
                    status         = 'ONLINE',
                    battery_level  = EXCLUDED.battery_level,
                    gps_accuracy   = EXCLUDED.gps_accuracy,
                    last_heartbeat = EXCLUDED.last_heartbeat,
                    updated_at     = now()
            """),
            {
                "device_id": payload.device_id,
                "family_id": str(family_id),
                "battery": payload.battery_level,
                "accuracy": payload.gps_accuracy,
                "hb": now,
            },
        )
        await session.commit()

    from app.core.ws_manager import ws_manager
    import asyncio
    
    # Broadcast new status and battery to dashboards
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.push_device_status(payload.device_id))
    except RuntimeError:
        # If no running loop, just don't push (shouldn't happen in fastapi endpoint)
        pass

    return {"ack": True, "device_id": payload.device_id, "status": "ONLINE"}
