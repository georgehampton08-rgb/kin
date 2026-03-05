import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix():
    async with AsyncSessionLocal() as s:
        await s.execute(text("ALTER TABLE pairing_tokens ALTER COLUMN created_by DROP NOT NULL"))
        await s.execute(text("UPDATE alembic_version SET version_num='c1d50cf6d6ef'"))
        await s.commit()
        print("Done!")
        r = await s.execute(text("SELECT is_nullable FROM information_schema.columns WHERE table_name='pairing_tokens' AND column_name='created_by'"))
        print("created_by nullable now:", r.fetchone()[0])

asyncio.run(fix())
