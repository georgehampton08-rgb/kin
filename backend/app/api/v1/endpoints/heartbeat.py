"""
Heartbeat Endpoint
===================
POST /api/v1/telemetry/heartbeat

Accepts a lightweight ping from the device every 5 minutes.
Upserts device_status: sets status=ONLINE, records battery + GPS accuracy.

If no heartbeat arrives within 12 minutes, APScheduler marks the device STALE.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal

router = APIRouter()


class HeartbeatPayload(BaseModel):
    device_id: str = Field(..., description="Unique device identifier")
    battery_level: float | None = Field(None, ge=0, le=100)
    gps_accuracy: float | None = Field(None, description="Accuracy in metres")
    timestamp: datetime | None = Field(None)


@router.post("/heartbeat")
async def heartbeat(
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

    return {"ack": True, "device_id": payload.device_id, "status": "ONLINE"}
