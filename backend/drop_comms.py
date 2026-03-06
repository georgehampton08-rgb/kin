import asyncio
import asyncpg
import sys

async def run():
    try:
        conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:15432/kin')
        await conn.execute("DROP TABLE IF EXISTS call_logs CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS sms_messages CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS notifications CASCADE;")
        print("Dropped orphaned comms tables!")
        await conn.close()
    except Exception as e:
        print(f"Error dropping tables: {e}")
        sys.exit(1)

asyncio.run(run())
