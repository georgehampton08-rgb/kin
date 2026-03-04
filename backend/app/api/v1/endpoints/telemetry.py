"""
Telemetry Ingest Endpoint
==========================
POST /api/v1/telemetry/ingest

Requires a device-scoped JWT. On ingest, writes:
1. pgcrypto-encrypted coordinates to locations_raw (permanent audit trail)
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy import text

from app.schemas.location import LocationUpdate
from app.api.deps import get_current_user
from app.core.auth import PGCRYPTO_KEY

router = APIRouter()


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    data: LocationUpdate,
    user: dict = Depends(get_current_user),
):
    """Ingest a location update from a paired device."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO locations_raw
                    (device_id, lat_encrypted, lng_encrypted, altitude, speed, battery_level)
                VALUES (
                    :device_id,
                    pgp_sym_encrypt(:lat, :key),
                    pgp_sym_encrypt(:lng, :key),
                    :altitude,
                    :speed,
                    :battery_level
                )
            """),
            {
                "device_id": data.device_id,
                "lat": str(data.latitude),
                "lng": str(data.longitude),
                "key": PGCRYPTO_KEY,
                "altitude": data.altitude,
                "speed": data.speed,
                "battery_level": data.battery_level,
            },
        )
        await session.commit()

    return {"message": "Location update received successfully", "device_id": data.device_id}
