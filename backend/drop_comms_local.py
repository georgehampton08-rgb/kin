import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://kinuser:kinpass@localhost:5432/kindb"
engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS call_logs CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS sms_messages CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS notifications CASCADE;"))
        await conn.execute(text("DELETE FROM alembic_version WHERE version_num = '12def9e7f486';"))
    print("Tables dropped and alembic version forcefully downgraded.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
