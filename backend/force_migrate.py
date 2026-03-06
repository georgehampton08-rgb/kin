import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.db.session import DATABASE_URL

engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        print("DATABASE URL IS:", DATABASE_URL)
        
        # 1. Drop existing just in case
        await conn.execute(text("DROP TABLE IF EXISTS call_logs CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS sms_messages CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS notifications CASCADE;"))

        # 2. Add comms tables
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
        await conn.execute(text("CREATE INDEX ix_call_logs_device_id ON call_logs (device_id);"))
        
        await conn.execute(text("""
        CREATE TABLE notifications (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR NOT NULL,
            package_name VARCHAR NOT NULL,
            title VARCHAR,
            text VARCHAR,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL
        )
        """))
        await conn.execute(text("CREATE INDEX ix_notifications_device_id ON notifications (device_id);"))

        await conn.execute(text("""
        CREATE TABLE sms_messages (
            id SERIAL PRIMARY KEY,
            device_id VARCHAR NOT NULL,
            sender VARCHAR NOT NULL,
            body VARCHAR,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            is_incoming BOOLEAN NOT NULL
        )
        """))
        await conn.execute(text("CREATE INDEX ix_sms_messages_device_id ON sms_messages (device_id);"))

        # 3. Apply the pairing token null constraint
        await conn.execute(text("UPDATE pairing_tokens SET created_by = (SELECT id FROM users LIMIT 1) WHERE created_by IS NULL;"))
        await conn.execute(text("ALTER TABLE pairing_tokens ALTER COLUMN created_by SET NOT NULL;"))

        # 4. Stamp Alembic!
        await conn.execute(text("DELETE FROM alembic_version;"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('4b27d38fb544');"))
        print("Database fully synced to head!")

if __name__ == "__main__":
    asyncio.run(run())
