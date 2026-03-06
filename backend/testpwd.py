import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.auth import verify_password

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT hashed_password FROM users WHERE email='admin@kin.com'"))
        hashed = res.scalar()
        print("Hash in DB:", hashed)
        print("Verification result for 'adminadmin':", verify_password("adminadmin", hashed))

if __name__ == "__main__":
    asyncio.run(check())
