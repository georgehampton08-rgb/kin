import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix():
    async with AsyncSessionLocal() as s:
        print("UPDATE devices...")
        await s.execute(text("UPDATE devices SET family_id = 'c84b8cee-91d3-4e89-a714-2ea33376bc74'"))
        await s.commit()
        print("DONE")

if __name__ == "__main__":
    asyncio.run(fix())
