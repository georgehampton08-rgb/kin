import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
PROD_URL = "postgresql+asyncpg://kinuser:2026$psg2instance@127.0.0.1:15432/kindb"
async def check():
    engine = create_async_engine(PROD_URL)
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='zones' ORDER BY ordinal_position"
        ))
        for row in r.fetchall():
            print(f"  {row[0]:20s} {row[1]}")
    await engine.dispose()
asyncio.run(check())
