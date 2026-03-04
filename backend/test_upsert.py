import asyncio
from sqlalchemy import insert, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from geoalchemy2.elements import WKTElement
from app.db.session import AsyncSessionLocal
from app.models.location import CurrentStatus, LocationHistory

async def upsert_location_record(device_id: str, lat: float, lon: float, altitude: float = None, speed: float = None, battery: float = None):
    async with AsyncSessionLocal() as session:
        # 1. Append to History Table
        history_record = LocationHistory(
            device_id=device_id,
            coordinates=f"POINT({lon} {lat})",
            altitude=altitude,
            speed=speed,
            battery_level=battery
        )
        session.add(history_record)

        # 2. Upsert CurrentStatus
        stmt = pg_insert(CurrentStatus).values(
            device_id=device_id,
            coordinates=f"POINT({lon} {lat})",
            altitude=altitude,
            speed=speed,
            battery_level=battery
        )

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['device_id'],
            set_=dict(
                coordinates=stmt.excluded.coordinates,
                altitude=stmt.excluded.altitude,
                speed=stmt.excluded.speed,
                battery_level=stmt.excluded.battery_level,
                last_updated=func.now()
            )
        )
        
        await session.execute(upsert_stmt)
        await session.commit()

async def verify_insertion():
    device = "test_device_postgis"
    # Insert Location
    await upsert_location_record(device, lat=40.7128, lon=-74.0060, altitude=10.0, speed=1.5, battery=100.0)
    print("Upsert successful.")

    # Retrieve and use ST_AsText
    async with AsyncSessionLocal() as session:
        query = select(CurrentStatus.device_id, func.ST_AsText(CurrentStatus.coordinates).label("wkt")).where(CurrentStatus.device_id == device)
        result = await session.execute(query)
        row = result.fetchone()
        
        if row:
            print(f"Retrieved CurrentStatus - Device: {row.device_id}, Coordinates WKT: {row.wkt}")
        else:
            print("Row not found.")

if __name__ == "__main__":
    asyncio.run(verify_insertion())
