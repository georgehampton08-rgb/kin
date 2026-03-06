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
import re
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request, status, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import text

from app.schemas.location import LocationUpdate
from app.api.deps import get_current_user
from app.core.auth import PGCRYPTO_KEY
from app.core.rate_limiter import limiter
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

LOW_BATTERY_THRESHOLD = 20.0

router = APIRouter()

# E.164 phone number format
_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")

def _strip_html(value: str) -> str:
    """Remove HTML/script tags from string fields to prevent stored XSS."""
    if not value:
        return value
    # Remove script tags and their contents
    value = re.sub(r"<script[^>]*>.*?</script>", "", value, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining HTML tags
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip()


MAX_BATCH_SIZE = 100
MAX_DECOMPRESSED_BYTES = 1_048_576  # 1 MB


def _validate_timestamp_window(v: datetime) -> datetime:
    """Reject timestamps more than 60s in the future or older than 24h."""
    now = datetime.now(timezone.utc)
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    if v > now + timedelta(seconds=60):
        raise ValueError("Timestamp cannot be more than 60 seconds in the future")
    if v < now - timedelta(hours=24):
        raise ValueError("Timestamp cannot be older than 24 hours")
    return v


class BatchPoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    speed: float | None = Field(None, ge=0, le=200)
    accuracy: float | None = Field(None, ge=0, le=1000)
    battery_level: float | None = Field(None, ge=0, le=100)
    ts: datetime | None = None

    @field_validator("ts")
    @classmethod
    def validate_ts(cls, v):
        if v is not None:
            return _validate_timestamp_window(v)
        return v


class BatchPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    device_id: str = Field(..., min_length=1, max_length=255)
    batch: list[BatchPoint] = Field(..., max_length=MAX_BATCH_SIZE)


# ── Comms Interception Payloads ────────────────────────────────

class NotificationPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    package_name: str = Field(..., min_length=1, max_length=255)
    title: str | None = Field(None, max_length=500)
    text: str | None = Field(None, max_length=2000)
    timestamp: datetime

    @field_validator("title", "text", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _strip_html(v) if isinstance(v, str) else v

    @field_validator("timestamp")
    @classmethod
    def validate_ts(cls, v):
        return _validate_timestamp_window(v)


class SmsPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    sender: str = Field(..., min_length=1, max_length=50)
    body: str | None = Field(None, max_length=1600)  # Max multi-part SMS length
    timestamp: datetime
    is_incoming: bool

    @field_validator("sender")
    @classmethod
    def validate_sender_e164(cls, v):
        if not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format (e.g. +15551234567)")
        return v

    @field_validator("body", mode="before")
    @classmethod
    def sanitize_body(cls, v):
        return _strip_html(v) if isinstance(v, str) else v

    @field_validator("timestamp")
    @classmethod
    def validate_ts(cls, v):
        return _validate_timestamp_window(v)


class CallLogPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    number: str = Field(..., min_length=1, max_length=30)
    duration_seconds: int = Field(..., ge=0, le=86400)
    type: str = Field(..., pattern=r"^(missed|incoming|outgoing)$")
    timestamp: datetime

    @field_validator("number")
    @classmethod
    def validate_number_e164(cls, v):
        if not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format (e.g. +15551234567)")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_ts(cls, v):
        return _validate_timestamp_window(v)


class CommsBatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    device_id: str = Field(..., min_length=1, max_length=255)
    notifications: list[NotificationPayload] | None = Field(None, max_length=100)
    sms: list[SmsPayload] | None = Field(None, max_length=100)
    calls: list[CallLogPayload] | None = Field(None, max_length=100)



# ── Single point ingest ───────────────────────────────────────

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def ingest_telemetry(
    request: Request,
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
@limiter.limit("60/minute")
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
        try:
            body = gzip.decompress(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid gzip data")
        if len(body) > MAX_DECOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="Decompressed payload too large")

    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    try:
        payload = BatchPayload(**raw)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid batch payload")

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
@limiter.limit("60/minute")
async def ingest_comms(
    request: Request,
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
