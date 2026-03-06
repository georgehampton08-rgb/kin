import asyncio
from sqlalchemy import text, select
from app.db.session import AsyncSessionLocal
from app.models.location import User
import uuid

async def test():
    async with AsyncSessionLocal() as s:
        # test mapping string to uuid
        uid = "6da6aa3b-6585-445b-82d9-6936ae5444d8"
        stmt = select(User).where(User.id == uid)
        try:
            res = await s.execute(stmt)
            user = res.scalar_one_or_none()
            print("Found user:", user.email if user else None)
        except Exception as e:
            print("Query failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
