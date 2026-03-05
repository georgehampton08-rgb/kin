from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
async def list_devices(user: dict = Depends(get_current_user)):
    """Returns all paired devices for the current family."""
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT d.device_identifier as device_id, d.is_active, d.paired_at
                FROM devices d
                WHERE d.is_active = true AND d.family_id = :family_id
                ORDER BY d.paired_at DESC
            """),
            {"family_id": family_id}
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
async def get_device_notifications(device_id: str, limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT n.id, n.package_name, n.title, n.text, n.timestamp
                FROM notifications n
                INNER JOIN devices d ON d.device_identifier = n.device_id
                WHERE n.device_id = :device_id AND d.family_id = :family_id
                ORDER BY n.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "family_id": family_id, "limit": limit, "offset": offset}
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
async def get_device_sms(device_id: str, limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT s.id, s.sender, s.body, s.timestamp, s.is_incoming
                FROM sms_messages s
                INNER JOIN devices d ON d.device_identifier = s.device_id
                WHERE s.device_id = :device_id AND d.family_id = :family_id
                ORDER BY s.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "family_id": family_id, "limit": limit, "offset": offset}
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
async def get_device_calls(device_id: str, limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT c.id, c.number, c.duration_seconds, c.type, c.timestamp
                FROM call_logs c
                INNER JOIN devices d ON d.device_identifier = c.device_id
                WHERE c.device_id = :device_id AND d.family_id = :family_id
                ORDER BY c.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            {"device_id": device_id, "family_id": family_id, "limit": limit, "offset": offset}
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
