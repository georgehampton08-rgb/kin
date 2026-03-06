import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import urllib.parse
import os

with open('.env', 'r') as f:
    for line in f:
        if line.startswith('DATABASE_URL='):
            DATABASE_URL = line.split('=', 1)[1].strip()

DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS call_logs CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS sms_messages CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS notifications CASCADE;"))
    print("Tables dropped.")
    await engine.dispose()

asyncio.run(run())
