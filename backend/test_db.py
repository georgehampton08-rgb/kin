import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.db.session import DATABASE_URL

engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        print("DATABASE URL IS:", DATABASE_URL)
        await conn.execute(text("DROP TABLE IF EXISTS call_logs CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS sms_messages CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS notifications CASCADE;"))
        print("Dropped.")

        # Let's ALSO test if it creates them:
        await conn.execute(text("""
        CREATE TABLE call_logs (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR NOT NULL,
            number VARCHAR NOT NULL,
            duration_seconds INTEGER NOT NULL,
            type VARCHAR NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL
        )
        """))
        print("Created call_logs!")

if __name__ == "__main__":
    asyncio.run(run())
