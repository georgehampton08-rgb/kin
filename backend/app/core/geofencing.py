"""
Geofencing engine.

For every new location ingestion, this service:
1. Loads all defined Zones
2. Uses PostGIS ST_DWithin to check containment (metres, using geography type)
3. Compares against the device's known zone presence state (in-memory cache)
4. Writes ENTRY or EXIT events to geofence_events and logs a mock notification
"""
import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.location import Zone, GeofenceEvent
from app.core.ws_manager import ws_manager

logger = logging.getLogger(__name__)

# In-memory store: device_id -> set of zone_ids the device is currently inside
# In production this would live in Redis for multi-instance safety
_device_zone_state: dict[str, set[int]] = {}


async def check_geofences(session: AsyncSession, device_id: str, lon: float, lat: float) -> None:
    """
    Run a spatial ST_DWithin check for every Zone and emit ENTRY / EXIT events.
    Called automatically during telemetry ingestion.
    """
    # Fetch all zones with their ids, names, and radius
    zones_result = await session.execute(
        select(Zone.id, Zone.name, Zone.radius_meters)
    )
    zones = zones_result.fetchall()

    if not zones:
        return

    point_wkt = f"SRID=4326;POINT({lon} {lat})"
    currently_inside: set[int] = set()

    for zone in zones:
        zone_id, zone_name, radius = zone.id, zone.name, zone.radius_meters

        # ST_DWithin on geography columns operates in metres natively
        result = await session.execute(
            text(
                "SELECT ST_DWithin("
                "  geography(ST_GeomFromText(:point, 4326)),"
                "  center,"
                "  :radius"
                ") FROM zones WHERE id = :zone_id"
            ),
            {"point": f"POINT({lon} {lat})", "radius": radius, "zone_id": zone_id}
        )
        is_inside = result.scalar()

        if is_inside:
            currently_inside.add(zone_id)

    previous_inside = _device_zone_state.get(device_id, set())

    # --- ENTRY events ---
    entered = currently_inside - previous_inside
    for zone_id in entered:
        zone_name = next(z.name for z in zones if z.id == zone_id)
        event = GeofenceEvent(
            device_id=device_id,
            zone_id=zone_id,
            zone_name=zone_name,
            event_type="ENTRY"
        )
        session.add(event)
        # Broadcast WebSocket alert to parent dashboards
        await ws_manager.broadcast(device_id, {
            "type": "geofence_alert",
            "event": "ENTRY",
            "zone_name": zone_name,
            "device_id": device_id,
        })
        logger.warning(
            f"[NOTIFICATION] 🟢 ENTRY — Device '{device_id}' entered zone '{zone_name}'"
        )

    # --- EXIT events ---
    exited = previous_inside - currently_inside
    for zone_id in exited:
        zone_name = next(z.name for z in zones if z.id == zone_id)
        event = GeofenceEvent(
            device_id=device_id,
            zone_id=zone_id,
            zone_name=zone_name,
            event_type="EXIT"
        )
        session.add(event)
        # Broadcast WebSocket alert to parent dashboards
        await ws_manager.broadcast(device_id, {
            "type": "geofence_alert",
            "event": "EXIT",
            "zone_name": zone_name,
            "device_id": device_id,
        })
        logger.warning(
            f"[NOTIFICATION] 🔴 EXIT  — Device '{device_id}' left zone '{zone_name}'"
        )

    # Update in-memory state
    _device_zone_state[device_id] = currently_inside
