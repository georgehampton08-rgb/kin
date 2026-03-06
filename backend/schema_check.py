import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        # Check all tables
        r = await s.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
        print("TABLES:", [row[0] for row in r.fetchall()])
        
        # Check comms tables
        for t in ['sms_messages', 'call_logs', 'notifications']:
            r = await s.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position"))
            cols = r.fetchall()
            if cols:
                print(f"\n{t}:")
                for c in cols:
                    print(f"  {c[0]}: {c[1]}")
            else:
                print(f"\n{t}: TABLE MISSING")

asyncio.run(check())
