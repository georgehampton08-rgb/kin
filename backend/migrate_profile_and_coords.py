import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def migrate():
    async with AsyncSessionLocal() as s:
        # --- DEVICES: add last known location ---
        for col, typ in [
            ("last_lat", "DOUBLE PRECISION"),
            ("last_lon", "DOUBLE PRECISION"),
            ("last_seen_at", "TIMESTAMPTZ"),
        ]:
            try:
                await s.execute(text(f"ALTER TABLE devices ADD COLUMN {col} {typ}"))
                print(f"  + devices.{col}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"  = devices.{col} (exists)")
                else:
                    print(f"  ! devices.{col}: {e}")

        # --- USERS: add profile fields ---
        for col, typ in [
            ("first_name", "VARCHAR(100)"),
            ("last_name", "VARCHAR(100)"),
            ("avatar_url", "TEXT"),
        ]:
            try:
                await s.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typ}"))
                print(f"  + users.{col}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"  = users.{col} (exists)")
                else:
                    print(f"  ! users.{col}: {e}")

        # Set George's name
        await s.execute(text(
            "UPDATE users SET first_name='George', last_name='Hampton' WHERE email='georgehampton08@gmail.com'"
        ))
        # Set admin name
        await s.execute(text(
            "UPDATE users SET first_name='Admin', last_name='Kin' WHERE email='admin@kin.com'"
        ))

        await s.commit()
        print("\nDone!")

asyncio.run(migrate())
