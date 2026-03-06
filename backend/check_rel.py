import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://kinuser:kinpass@localhost:5432/kindb"
engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT relname, relkind FROM pg_class WHERE relkind IN ('r', 'v', 'S', 'i') AND relname LIKE '%call_logs%';"))
        for row in res:
            print(f"Found relation matching call_logs: {row}")

if __name__ == "__main__":
    asyncio.run(run())
