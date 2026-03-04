"""
Seed mock geofence Zones near the Chicago test route.
Run once: python seed_zones.py
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.location import Zone, GeofenceEvent
from sqlalchemy import delete

async def seed():
    async with AsyncSessionLocal() as session:
        # Must delete geofence_events first (FK references zones)
        await session.execute(delete(GeofenceEvent))
        await session.execute(delete(Zone))

        zones = [
            Zone(
                name="Home",
                center="SRID=4326;POINT(-87.6230 41.8800)",
                radius_meters=100.0,
                zone_type="safe",
            ),
            Zone(
                name="School",
                center="SRID=4326;POINT(-87.6190 41.8855)",
                radius_meters=150.0,
                zone_type="caution",
            ),
            Zone(
                name="Restricted Area",
                center="SRID=4326;POINT(-87.6100 41.8830)",
                radius_meters=80.0,
                zone_type="restricted",
            ),
        ]
        for z in zones:
            session.add(z)
        await session.commit()
        print(f"✅ Seeded {len(zones)} zones: Home, School, Restricted Area")

if __name__ == "__main__":
    asyncio.run(seed())
