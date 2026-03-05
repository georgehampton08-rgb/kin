import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        # Check if table exists
        r = await s.execute(text("SELECT to_regclass('pairing_tokens')"))
        print("pairing_tokens table exists?", r.scalar())

        r2 = await s.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='pairing_tokens' AND column_name='created_by'"
        ))
        row = r2.fetchone()
        print("created_by nullable:", row[0] if row else "COLUMN NOT FOUND")

        # Check alembic version
        r3 = await s.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic version:", [row[0] for row in r3.fetchall()])

asyncio.run(check())
