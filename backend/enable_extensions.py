import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def enable_postgis():
    async with AsyncSessionLocal() as s:
        try:
            await s.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await s.commit()
            print("PostGIS extension ENABLED!")
        except Exception as e:
            print(f"PostGIS enable failed: {e}")
            await s.rollback()
        
        try:
            await s.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await s.commit()
            print("pgcrypto extension ENABLED!")
        except Exception as e:
            print(f"pgcrypto enable failed: {e}")
            await s.rollback()
        
        # Verify
        try:
            r = await s.execute(text("SELECT PostGIS_Version()"))
            print(f"PostGIS version: {r.scalar()}")
        except Exception as e:
            print(f"PostGIS NOT available: {e}")

asyncio.run(enable_postgis())
