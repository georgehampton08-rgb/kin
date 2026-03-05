"""Create missing tables: zones, geofence_events, matched_routes, alembic_version."""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

PROD_URL = "postgresql+asyncpg://kinuser:2026$psg2instance@127.0.0.1:15432/kindb"

SQLS = [
    # Zones
    """CREATE TABLE IF NOT EXISTS zones (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL,
        coordinates JSONB NOT NULL,
        radius DOUBLE PRECISION DEFAULT 200,
        zone_type VARCHAR DEFAULT 'safe',
        family_id UUID REFERENCES families(id),
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    # Geofence events
    """CREATE TABLE IF NOT EXISTS geofence_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        device_id VARCHAR NOT NULL,
        zone_id UUID REFERENCES zones(id),
        event_type VARCHAR(10) NOT NULL,
        timestamp TIMESTAMPTZ DEFAULT now()
    )""",
    # Matched routes
    """CREATE TABLE IF NOT EXISTS matched_routes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        device_id VARCHAR NOT NULL,
        family_id UUID,
        date DATE NOT NULL,
        route_geojson JSONB NOT NULL,
        confidence DOUBLE PRECISION DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    )""",
    # Alembic version tracking
    """CREATE TABLE IF NOT EXISTS alembic_version (
        version_num VARCHAR(32) NOT NULL,
        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
    )""",
    "INSERT INTO alembic_version (version_num) VALUES ('c1d50cf6d6ef') ON CONFLICT DO NOTHING",
]


async def apply():
    engine = create_async_engine(PROD_URL)
    for sql in SQLS:
        label = sql.strip()[:60].replace('\n', ' ')
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
            print(f"  OK: {label}")
        except Exception as e:
            print(f"  WARN: {str(e).split(chr(10))[0][:80]}")

    # Verify
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [row[0] for row in r.fetchall()]
        print(f"\nFinal: {len(tables)} tables: {tables}")
        r2 = await conn.execute(text("SELECT version_num FROM alembic_version"))
        print(f"Alembic: {r2.scalar()}")
    await engine.dispose()

asyncio.run(apply())
