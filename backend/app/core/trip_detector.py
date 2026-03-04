"""
Trip Detector
=============
Maintains a per-device rolling buffer of recent location points.
When 5+ consecutive points with speed > 0.5 m/s are detected, a trip
is considered complete and map-matching is triggered as a background task.
"""
import logging
from collections import defaultdict, deque
from datetime import datetime
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

# Minimum consecutive moving points to declare a trip
TRIP_THRESHOLD = 5
# Speed threshold in m/s below which a point is considered "stationary"
MOVING_SPEED_THRESHOLD = 0.5
# Max buffer size per device
BUFFER_SIZE = 50


class _DeviceBuffer:
    """Rolling buffer of (lon, lat, speed, timestamp) tuples for one device."""
    def __init__(self):
        self.points: deque = deque(maxlen=BUFFER_SIZE)
        self.dispatched_trips: set[int] = set()  # track buffer positions already sent


_buffers: dict[str, _DeviceBuffer] = defaultdict(_DeviceBuffer)


def push_point(
    device_id: str,
    lon: float,
    lat: float,
    speed: float | None,
    timestamp: datetime,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Called on every telemetry ingestion.
    Adds the point to the device buffer and checks if a trip threshold is met.
    """
    buf = _buffers[device_id]
    buf.points.append((lon, lat, speed or 0.0, timestamp))

    _check_and_dispatch(device_id, buf, background_tasks)


def _check_and_dispatch(device_id: str, buf: _DeviceBuffer, background_tasks: BackgroundTasks):
    """Extract a consecutive run of moving points and dispatch map-matching if threshold met."""
    from app.core.map_matching import match_trip  # local import avoids circular deps

    points = list(buf.points)
    moving_run: list = []

    for pt in reversed(points):
        lon, lat, speed, ts = pt
        if speed >= MOVING_SPEED_THRESHOLD:
            moving_run.insert(0, pt)
        else:
            # A stationary point breaks the run
            break

    if len(moving_run) < TRIP_THRESHOLD:
        return

    # Build a stable fingerprint for this batch to avoid duplicate dispatches
    trip_key = id(moving_run[0])
    if trip_key in buf.dispatched_trips:
        return
    buf.dispatched_trips.add(trip_key)

    coords = [(lon, lat) for lon, lat, _, _ in moving_run]
    trip_start = moving_run[0][3]
    trip_end = moving_run[-1][3]

    logger.info(
        f"[TripDetector] Trip detected for '{device_id}': "
        f"{len(coords)} points from {trip_start} → {trip_end}"
    )

    # Fire-and-forget via FastAPI BackgroundTasks
    background_tasks.add_task(match_trip, device_id, coords, trip_start, trip_end)
