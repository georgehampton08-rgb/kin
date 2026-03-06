from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.api.deps import get_current_user

router = APIRouter()

from pydantic import BaseModel, Field

class DeviceUpdatePayload(BaseModel):
    nickname: str | None = Field(None, max_length=255)

class MarkReadPayload(BaseModel):
    type: str = Field(..., description="Type of comms to mark read: sms, calls, or notifications")


@router.get("/")
async def list_devices(user: dict = Depends(get_current_user)):
    """Returns all paired devices for the current family, with unread counters."""
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT d.device_identifier as device_id, d.is_active, d.paired_at, 
                       d.nickname, d.app_version, d.os_info,
                       (SELECT COUNT(id) FROM sms_messages s WHERE s.device_id = d.device_identifier AND s.is_read = false) as unread_sms,
                       (SELECT COUNT(id) FROM call_logs c WHERE c.device_id = d.device_identifier AND c.is_read = false AND c.type = 'missed') as missed_calls,
                       (SELECT COUNT(id) FROM notifications n WHERE n.device_id = d.device_identifier AND n.is_read = false) as unread_notifs
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
            "nickname": row.nickname,
            "app_version": row.app_version,
            "os_info": row.os_info,
            "unread_sms": row.unread_sms,
            "missed_calls": row.missed_calls,
            "unread_notifs": row.unread_notifs,
        })

    return {"devices": devices}


@router.patch("/{device_id}")
async def update_device(device_id: str, payload: DeviceUpdatePayload, user: dict = Depends(get_current_user)):
    """Update device properties like nickname (Parent Dashboard)."""
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                UPDATE devices 
                SET nickname = :nickname 
                WHERE device_identifier = :device_id AND family_id = :family_id
            """),
            {"device_id": device_id, "family_id": family_id, "nickname": payload.nickname}
        )
        await session.commit()
    return {"status": "ok", "nickname": payload.nickname}


@router.post("/{device_id}/comms/mark_read")
async def mark_comms_read(device_id: str, payload: MarkReadPayload, user: dict = Depends(get_current_user)):
    """Mark all unread communications of a specific type as read."""
    family_id = user.get("family_id")
    async with AsyncSessionLocal() as session:
        # Verify ownership
        dev = await session.execute(
            text("SELECT 1 FROM devices WHERE device_identifier = :dev_id AND family_id = :fam_id"),
            {"dev_id": device_id, "fam_id": family_id}
        )
        if not dev.fetchone():
            return {"error": "Device not found"}

        if payload.type == "sms":
            await session.execute(text("UPDATE sms_messages SET is_read = true WHERE device_id = :dev_id"), {"dev_id": device_id})
        elif payload.type == "calls":
            await session.execute(text("UPDATE call_logs SET is_read = true WHERE device_id = :dev_id AND type = 'missed'"), {"dev_id": device_id})
        elif payload.type == "notifications":
            await session.execute(text("UPDATE notifications SET is_read = true WHERE device_id = :dev_id"), {"dev_id": device_id})

        await session.commit()
    return {"status": "ok", "marked": payload.type}


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
