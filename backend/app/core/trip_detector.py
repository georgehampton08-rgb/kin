"""
Postgres-Backed Trip State Machine
=====================================
Replaces the in-memory trip_detector.py.

State transitions (all persisted in the `trips` table):

  ACCUMULATING → TRIP_OPEN   : 3 consecutive points ≥ 1.5 m/s within 90 sec
  TRIP_OPEN    → TRIP_PAUSED : speed < 0.5 m/s (record paused_at)
  TRIP_PAUSED  → TRIP_OPEN   : speed ≥ 1.5 m/s AND paused_at < 8 min ago
  TRIP_PAUSED  → TRIP_CLOSED : paused_at ≥ 8 min ago (arrival)
  TRIP_OPEN    → TRIP_CLOSED : geofence ARRIVAL event (external call)

Map-matching is gated on TRIP_CLOSED only — never called for open or paused trips.

Battery note:
  If battery_level < 20, logs LOW_BATTERY_MODE_ACTIVE on every point.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import text, select

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────
OPEN_SPEED_MS = 1.5          # m/s — minimum speed to open/resume
PAUSE_SPEED_MS = 0.5         # m/s — below this triggers PAUSED
OPEN_CONSECUTIVE = 3         # consecutive points needed to open
OPEN_WINDOW_SEC = 90         # those 3 points must be within 90 sec
PAUSE_TIMEOUT_MIN = 8        # minutes before PAUSED → CLOSED
LOW_BATTERY_THRESHOLD = 20.0 # %

# Per-device short-term accumulator (in-memory, lightweight)
_accumulators: dict[str, list] = {}  # device_id → [(speed, ts), ...]


async def push_point(
    device_id: str,
    family_id: str,
    lon: float,
    lat: float,
    speed: float | None,
    timestamp: datetime,
    battery_level: float | None = None,
) -> None:
    """
    Called on every telemetry point. Drives the state machine.
    """
    spd = speed or 0.0

    # Battery warning
    if battery_level is not None and battery_level < LOW_BATTERY_THRESHOLD:
        logger.info(
            f"[TripDetector] LOW_BATTERY_MODE_ACTIVE device={device_id} "
            f"battery={battery_level}%"
        )

    async with AsyncSessionLocal() as session:
        # Get current open/paused/accumulating trip for this device
        result = await session.execute(
            text("""
                SELECT id, status, start_time, paused_at, point_count
                FROM trips
                WHERE device_id = :device_id
                  AND status IN ('ACCUMULATING', 'TRIP_OPEN', 'TRIP_PAUSED')
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"device_id": device_id},
        )
        row = result.fetchone()

        now = timestamp or datetime.now(timezone.utc)

        if row is None:
            # No active trip — try to accumulate
            await _handle_accumulating(session, device_id, family_id, spd, now)
        else:
            trip_id = row.id
            status = row.status
            start_time = row.start_time
            paused_at = row.paused_at
            point_count = row.point_count

            if status == 'ACCUMULATING':
                await _handle_accumulating(
                    session, device_id, family_id, spd, now,
                    trip_id=trip_id, start_time=start_time, count=point_count,
                )
            elif status == 'TRIP_OPEN':
                await _handle_open(session, trip_id, spd, now, point_count)
            elif status == 'TRIP_PAUSED':
                await _handle_paused(session, trip_id, device_id, spd, now, paused_at)
        await session.commit()
        
    from app.core.ws_manager import ws_manager
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.push_device_status(device_id))
    except RuntimeError:
        pass


async def _handle_accumulating(
    session, device_id, family_id, spd, now, trip_id=None, start_time=None, count=0
):
    """Accumulate fast points; open trip when threshold met."""
    if spd >= OPEN_SPEED_MS:
        new_count = count + 1

        if trip_id is None:
            # Create new ACCUMULATING record
            await session.execute(
                text("""
                    INSERT INTO trips (id, device_id, family_id, status, start_time, point_count)
                    VALUES (:id, :device_id, :family_id, 'ACCUMULATING', :start_time, 1)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "device_id": device_id,
                    "family_id": str(family_id),
                    "start_time": now,
                },
            )
            logger.debug(f"[TripDetector] {device_id}: ACCUMULATING (1/{OPEN_CONSECUTIVE})")
        elif new_count >= OPEN_CONSECUTIVE:
            # Check window: start_time must be within OPEN_WINDOW_SEC
            if start_time and (now - _ensure_tz(start_time)).total_seconds() <= OPEN_WINDOW_SEC:
                await session.execute(
                    text("""
                        UPDATE trips SET status = 'TRIP_OPEN', point_count = :count
                        WHERE id = :id
                    """),
                    {"count": new_count, "id": str(trip_id)},
                )
                logger.info(f"[TripDetector] {device_id}: TRIP_OPEN ✅ ({new_count} pts)")
            else:
                # Window expired — reset accumulator
                await session.execute(
                    text("UPDATE trips SET status = 'TRIP_CLOSED', end_time = :end WHERE id = :id"),
                    {"end": now, "id": str(trip_id)},
                )
                logger.debug(f"[TripDetector] {device_id}: ACCUMULATING window expired, reset")
        else:
            await session.execute(
                text("UPDATE trips SET point_count = :count WHERE id = :id"),
                {"count": new_count, "id": str(trip_id)},
            )
            logger.debug(f"[TripDetector] {device_id}: ACCUMULATING ({new_count}/{OPEN_CONSECUTIVE})")
    else:
        # Too slow — abandon accumulation if it exists
        if trip_id:
            await session.execute(
                text("UPDATE trips SET status = 'TRIP_CLOSED', end_time = :end WHERE id = :id"),
                {"end": now, "id": str(trip_id)},
            )


async def _handle_open(session, trip_id, spd, now, point_count):
    """Open trip — check for pause transition."""
    if spd < PAUSE_SPEED_MS:
        await session.execute(
            text("""
                UPDATE trips SET status = 'TRIP_PAUSED', paused_at = :paused_at,
                    point_count = :count
                WHERE id = :id
            """),
            {"paused_at": now, "count": point_count + 1, "id": str(trip_id)},
        )
        logger.info(f"[TripDetector] trip {trip_id}: TRIP_OPEN → TRIP_PAUSED")
    else:
        await session.execute(
            text("UPDATE trips SET point_count = :count WHERE id = :id"),
            {"count": point_count + 1, "id": str(trip_id)},
        )


async def _handle_paused(session, trip_id, device_id, spd, now, paused_at):
    """Paused trip — resume or close based on elapsed time."""
    if paused_at is None:
        paused_at = now

    paused_duration = (now - _ensure_tz(paused_at)).total_seconds() / 60.0

    if paused_duration >= PAUSE_TIMEOUT_MIN:
        # Timeout expired — close permanently
        await session.execute(
            text("""
                UPDATE trips SET status = 'TRIP_CLOSED', end_time = :end WHERE id = :id
            """),
            {"end": now, "id": str(trip_id)},
        )
        logger.info(
            f"[TripDetector] trip {trip_id}: TRIP_PAUSED → TRIP_CLOSED "
            f"(pause timeout {paused_duration:.1f} min)"
        )
        # Gate: trigger map-matching only on freshly closed trips
        from app.core.map_matching import match_trip_by_id
        import asyncio
        asyncio.create_task(match_trip_by_id(str(trip_id)))
    elif spd >= OPEN_SPEED_MS:
        # Resume
        await session.execute(
            text("""
                UPDATE trips SET status = 'TRIP_OPEN', paused_at = NULL WHERE id = :id
            """),
            {"id": str(trip_id)},
        )
        logger.info(f"[TripDetector] trip {trip_id}: TRIP_PAUSED → TRIP_OPEN (resumed)")
    # else: still paused, waiting


async def close_trip_on_arrival(device_id: str) -> None:
    """External call — geofence arrival event forces trip closed immediately."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                UPDATE trips
                SET status = 'TRIP_CLOSED', end_time = now()
                WHERE device_id = :device_id
                  AND status IN ('TRIP_OPEN', 'TRIP_PAUSED')
                RETURNING id
            """),
            {"device_id": device_id},
        )
        closed = [str(row[0]) for row in result.fetchall()]
        await session.commit()

    for trip_id in closed:
        logger.info(f"[TripDetector] trip {trip_id}: forced TRIP_CLOSED (geofence arrival)")
        from app.core.map_matching import match_trip_by_id
        from app.core.ws_manager import ws_manager
        import asyncio
        asyncio.create_task(match_trip_by_id(trip_id))
        asyncio.create_task(ws_manager.push_device_status(device_id))


def _ensure_tz(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
