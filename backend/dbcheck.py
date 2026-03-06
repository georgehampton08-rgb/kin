import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT id, email, hashed_password, role FROM users WHERE email='admin@kin.com'"))
        print(res.fetchone())
        
        # Test George user
        res2 = await s.execute(text("SELECT id, email, hashed_password FROM users WHERE email='georgehampton08@gmail.com'"))
        print("George: ", res2.fetchone())

if __name__ == "__main__":
    asyncio.run(check())
