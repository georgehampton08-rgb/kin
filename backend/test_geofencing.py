"""
Geofencing Integration Test
============================
Definition of Done:
  1. A 'School' zone is created at (40.7128, -74.0060), radius 100m.
  2. Coordinate A at the exact centre  -> triggers ENTRY event.
  3. Coordinate B ~210m away           -> triggers EXIT event.
  4. Both events are retrieved from geofence_events and printed.
"""
import asyncio
import logging
from sqlalchemy import select, delete

from app.db.session import AsyncSessionLocal
from app.models.location import Zone, GeofenceEvent
from app.core.geofencing import check_geofences, _device_zone_state

logging.basicConfig(level=logging.WARNING, format="%(message)s")

DEVICE = "test_child_01"
# School centre: New York City Hall area
SCHOOL_LAT  =  40.7128
SCHOOL_LON  = -74.0060
SCHOOL_RADIUS = 100   # metres

# ~210m north of the school centre
OUTSIDE_LAT =  40.7147
OUTSIDE_LON = -74.0060


async def seed_zone(session) -> Zone:
    zone = Zone(
        name="School",
        center=f"POINT({SCHOOL_LON} {SCHOOL_LAT})",
        radius_meters=SCHOOL_RADIUS,
    )
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone


async def cleanup(session, zone_id: int):
    await session.execute(delete(GeofenceEvent).where(GeofenceEvent.zone_id == zone_id))
    await session.execute(delete(Zone).where(Zone.id == zone_id))
    await session.commit()
    # Clear in-memory state
    _device_zone_state.pop(DEVICE, None)


async def run_test():
    async with AsyncSessionLocal() as session:
        print("=" * 55)
        print("   Kin Geofencing Engine — Integration Test")
        print("=" * 55)

        # --- Setup ---
        zone = await seed_zone(session)
        print(f"\n[SETUP] Created zone '{zone.name}' (id={zone.id}) "
              f"@ ({SCHOOL_LAT}, {SCHOOL_LON}), radius={SCHOOL_RADIUS}m\n")

        # --- Step 1: Place device INSIDE the school zone ---
        print(f"[TEST 1] Publishing coordinates inside zone  ({SCHOOL_LAT}, {SCHOOL_LON}) ...")
        await check_geofences(session, DEVICE, SCHOOL_LON, SCHOOL_LAT)
        await session.commit()

        # --- Step 2: Move device OUTSIDE (~210m away) ---
        print(f"[TEST 2] Publishing coordinates outside zone ({OUTSIDE_LAT}, {OUTSIDE_LON}) ...")
        await check_geofences(session, DEVICE, OUTSIDE_LON, OUTSIDE_LAT)
        await session.commit()

        # --- Verify events in DB ---
        result = await session.execute(
            select(GeofenceEvent)
            .where(GeofenceEvent.device_id == DEVICE)
            .order_by(GeofenceEvent.id)
        )
        events = result.scalars().all()

        print(f"\n{'─'*55}")
        print(f"  {'#':<4} {'Type':<8} {'Zone':<12} {'Device'}")
        print(f"{'─'*55}")
        for e in events:
            icon = "🟢" if e.event_type == "ENTRY" else "🔴"
            print(f"  {e.id:<4} {icon} {e.event_type:<6} {e.zone_name:<12} {e.device_id}")
        print(f"{'─'*55}\n")

        # Assertions
        assert len(events) == 2, f"Expected 2 events, got {len(events)}"
        assert events[0].event_type == "ENTRY", "First event should be ENTRY"
        assert events[1].event_type == "EXIT",  "Second event should be EXIT"
        print("✅  All assertions passed. Definition of Done MET.\n")

        # --- Cleanup ---
        await cleanup(session, zone.id)
        print("[CLEANUP] Test zone and events removed from DB.")


if __name__ == "__main__":
    asyncio.run(run_test())
