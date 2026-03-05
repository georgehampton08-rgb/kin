import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

PROD_URL = "postgresql+asyncpg://kinuser:2026$psg2instance@127.0.0.1:15432/kindb"

async def check():
    engine = create_async_engine(PROD_URL)
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [row[0] for row in r.fetchall()]
        print(f"Found {len(tables)} tables:")
        for t in tables:
            print(f"  - {t}")

        # Check alembic version
        try:
            r2 = await conn.execute(text("SELECT version_num FROM alembic_version"))
            print(f"\nalembic version: {[row[0] for row in r2.fetchall()]}")
        except Exception as e:
            print(f"\nalembic_version table error: {e}")

    await engine.dispose()

asyncio.run(check())
