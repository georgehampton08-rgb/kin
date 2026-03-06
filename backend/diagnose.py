import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def diagnose():
    async with AsyncSessionLocal() as s:
        # 1. Check devices and their last known location
        r = await s.execute(text("""
            SELECT device_identifier, nickname, last_lat, last_lon, last_seen_at, paired_at, is_active 
            FROM devices ORDER BY paired_at DESC
        """))
        print("=== DEVICES ===")
        for row in r.fetchall():
            print(f"  {row.device_identifier}: lat={row.last_lat} lon={row.last_lon} seen={row.last_seen_at} active={row.is_active}")

        # 2. Check recent telemetry (location_history)
        r = await s.execute(text("""
            SELECT device_id, ST_X(coordinates::geometry) as lon, ST_Y(coordinates::geometry) as lat, 
                   speed, battery_level, timestamp
            FROM location_history ORDER BY timestamp DESC LIMIT 10
        """))
        rows = r.fetchall()
        print(f"\n=== RECENT LOCATION HISTORY ({len(rows)} rows) ===")
        for row in rows:
            print(f"  {row.device_id}: lat={row.lat} lon={row.lon} speed={row.speed} bat={row.battery_level} ts={row.timestamp}")

        # 3. Check recent comms
        for table, label in [("sms_messages", "SMS"), ("call_logs", "CALLS"), ("notifications", "NOTIFS")]:
            r = await s.execute(text(f"SELECT COUNT(*) FROM {table}"))
            print(f"\n{label} count: {r.scalar()}")

        # 4. Check locations_raw
        r = await s.execute(text("SELECT COUNT(*) FROM locations_raw"))
        print(f"\nlocations_raw count: {r.scalar()}")

asyncio.run(diagnose())
