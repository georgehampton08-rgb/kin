from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

router = APIRouter()

@router.get("/")
async def list_devices():
    """Returns all paired devices (no auth for now, dashboard is public)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT d.device_identifier as device_id, d.is_active, d.paired_at
                FROM devices d
                WHERE d.is_active = true
                ORDER BY d.paired_at DESC
            """)
        )
        rows = result.fetchall()

    devices = []
    for row in rows:
        devices.append({
            "device_id": row.device_id,
            "is_active": row.is_active,
            "paired_at": row.paired_at.isoformat() if row.paired_at else None,
        })

    return {"devices": devices}
