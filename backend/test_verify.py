import asyncio
from app.db.session import AsyncSessionLocal
from app.models.location import LocationHistory, CurrentStatus
from sqlalchemy import select

async def verify():
    async with AsyncSessionLocal() as session:
        # Check History insertions
        history_result = await session.execute(
            select(LocationHistory.device_id, LocationHistory.battery_level)
            .where(LocationHistory.device_id == 'device_001')
        )
        print('History (LWT writes -1.0 battery):', history_result.fetchall())
        
        # Check Current Status assertion
        current_result = await session.execute(
            select(CurrentStatus.device_id, CurrentStatus.battery_level)
            .where(CurrentStatus.device_id == 'device_001')
        )
        print('Current Status (Should hold last valid battery):', current_result.fetchall())

if __name__ == "__main__":
    asyncio.run(verify())
