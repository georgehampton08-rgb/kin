import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.auth import hash_password

async def fix():
    new_pw = hash_password("KinParent2026!")
    async with AsyncSessionLocal() as s:
        await s.execute(
            text("UPDATE users SET hashed_password = :h WHERE email = 'georgehampton08@gmail.com'"),
            {"h": new_pw}
        )
        await s.commit()
    print("Password for georgehampton08@gmail.com reset to: KinParent2026!")

asyncio.run(fix())
