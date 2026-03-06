import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://kinuser:kinpass@localhost:5432/kindb"
engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
        tables = [row[0] for row in res.fetchall()]
        print("Existing tables:", tables)
        
        res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        versions = [row[0] for row in res.fetchall()]
        print("Alembic versions:", versions)
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
