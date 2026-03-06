import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        print("--- DEVICES ---")
        devices = await s.execute(text("SELECT device_identifier, family_id FROM devices"))
        for d in devices.fetchall():
            print(d)
        print("--- USERS ---")
        users = await s.execute(text("SELECT u.id, u.email, u.role, f.family_id FROM users u JOIN family_memberships f ON u.id = f.user_id WHERE u.role = 'parent'"))
        for u in users.fetchall():
            print(u)

if __name__ == "__main__":
    asyncio.run(check())
