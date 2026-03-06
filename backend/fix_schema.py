import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix():
    async with AsyncSessionLocal() as s:
        # Drop and recreate location_history with PostGIS
        await s.execute(text("DROP TABLE IF EXISTS location_history"))
        await s.execute(text("""
            CREATE TABLE location_history (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(255) NOT NULL,
                coordinates GEOGRAPHY(Point, 4326),
                speed DOUBLE PRECISION,
                battery_level DOUBLE PRECISION,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await s.execute(text("CREATE INDEX idx_loc_hist_device_ts ON location_history(device_id, timestamp DESC)"))
        print("location_history: recreated with PostGIS")

        # Drop and recreate locations_raw with pgcrypto
        await s.execute(text("DROP TABLE IF EXISTS locations_raw"))
        await s.execute(text("""
            CREATE TABLE locations_raw (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(255) NOT NULL,
                lat_encrypted BYTEA,
                lng_encrypted BYTEA,
                altitude DOUBLE PRECISION,
                speed DOUBLE PRECISION,
                battery_level DOUBLE PRECISION,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        print("locations_raw: recreated with BYTEA for pgcrypto")

        # Drop and recreate matched_routes with PostGIS
        await s.execute(text("DROP TABLE IF EXISTS matched_routes"))
        await s.execute(text("""
            CREATE TABLE matched_routes (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(255) NOT NULL,
                trip_start TIMESTAMPTZ,
                trip_end TIMESTAMPTZ,
                raw_point_count INT,
                confidence DOUBLE PRECISION,
                provider VARCHAR(50),
                matched_path GEOGRAPHY(LineString, 4326),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        print("matched_routes: recreated with PostGIS")

        await s.commit()
        print("\nAll tables recreated with proper PostGIS types!")

asyncio.run(fix())
