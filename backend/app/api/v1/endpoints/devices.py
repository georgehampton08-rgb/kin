from fastapi import APIRouter, Depends, HTTPException
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
    role = user.get("role")
    
    where_clause = "d.is_active = true" if role == "admin" else "d.is_active = true AND d.family_id = :family_id"
    params = {} if role == "admin" else {"family_id": family_id}
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT d.device_identifier as device_id,
                       d.is_active,
                       d.paired_at,
                       COALESCE(d.nickname, NULL)      as nickname,
                       COALESCE(d.app_version, NULL)   as app_version,
                       COALESCE(d.os_info, NULL)        as os_info,
                       COALESCE(
                           (SELECT COUNT(s.id) FROM sms_messages s
                            WHERE s.device_id = d.device_identifier AND s.is_read = false),
                           0
                       ) as unread_sms,
                       COALESCE(
                           (SELECT COUNT(c.id) FROM call_logs c
                            WHERE c.device_id = d.device_identifier
                              AND c.is_read = false
                              AND c.type = 'missed'),
                           0
                       ) as missed_calls,
                       COALESCE(
                           (SELECT COUNT(n.id) FROM notifications n
                            WHERE n.device_id = d.device_identifier AND n.is_read = false),
                           0
                       ) as unread_notifs,
                       d.last_lat,
                       d.last_lon,
                       d.last_seen_at
                FROM devices d
                WHERE {where_clause}
                ORDER BY d.paired_at DESC
            """),
            params
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
            "unread_sms": int(row.unread_sms or 0),
            "missed_calls": int(row.missed_calls or 0),
            "unread_notifs": int(row.unread_notifs or 0),
            "last_lat": float(row.last_lat) if row.last_lat else None,
            "last_lon": float(row.last_lon) if row.last_lon else None,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        })

    return {"devices": devices}


@router.patch("/{device_id}")
async def update_device(device_id: str, payload: DeviceUpdatePayload, user: dict = Depends(get_current_user)):
    """Update device properties like nickname (Parent Dashboard)."""
    family_id = user.get("family_id")
    role = user.get("role")
    
    where_clause = "device_identifier = :device_id" if role == "admin" else "device_identifier = :device_id AND family_id = :family_id"
    params = {"device_id": device_id, "nickname": payload.nickname}
    if role != "admin":
        params["family_id"] = family_id
        
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"""
                UPDATE devices 
                SET nickname = :nickname 
                WHERE {where_clause}
            """),
            params
        )
        await session.commit()
    return {"status": "ok", "nickname": payload.nickname}


@router.delete("/{device_id}")
async def delete_device(device_id: str, user: dict = Depends(get_current_user)):
    """Permanently delete a device and all its associated data."""
    family_id = user.get("family_id")
    role = user.get("role")

    where_clause = "device_identifier = :device_id" if role == "admin" else "device_identifier = :device_id AND family_id = :family_id"
    params = {"device_id": device_id}
    if role != "admin":
        params["family_id"] = family_id

    async with AsyncSessionLocal() as session:
        # Verify it exists and belongs to this family
        res = await session.execute(
            text(f"SELECT id FROM devices WHERE {where_clause}"),
            params
        )
        row = res.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")

        # Delete all associated data first
        await session.execute(text("DELETE FROM notifications WHERE device_id = :device_id"), {"device_id": device_id})
        await session.execute(text("DELETE FROM sms_messages WHERE device_id = :device_id"), {"device_id": device_id})
        await session.execute(text("DELETE FROM call_logs WHERE device_id = :device_id"), {"device_id": device_id})
        await session.execute(text("DELETE FROM location_history WHERE device_id = :device_id"), {"device_id": device_id})
        await session.execute(text("DELETE FROM locations_raw WHERE device_id = :device_id"), {"device_id": device_id})

        # Delete the device itself
        await session.execute(
            text(f"DELETE FROM devices WHERE {where_clause}"),
            params
        )
        await session.commit()

    return {"status": "deleted", "device_id": device_id}


@router.post("/{device_id}/comms/mark_read")
async def mark_comms_read(device_id: str, payload: MarkReadPayload, user: dict = Depends(get_current_user)):
    """Mark all unread communications of a specific type as read."""
    family_id = user.get("family_id")
    role = user.get("role")
    
    where_c = "device_identifier = :dev_id" if role == "admin" else "device_identifier = :dev_id AND family_id = :fam_id"
    params = {"dev_id": device_id}
    if role != "admin":
        params["fam_id"] = family_id
        
    async with AsyncSessionLocal() as session:
        # Verify ownership
        dev = await session.execute(
            text(f"SELECT 1 FROM devices WHERE {where_c}"),
            params
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
    role = user.get("role")
    
    where_clause = "n.device_id = :device_id" if role == "admin" else "n.device_id = :device_id AND d.family_id = :family_id"
    params = {"device_id": device_id, "limit": limit, "offset": offset}
    if role != "admin":
        params["family_id"] = family_id
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT n.id, n.package_name, n.title, n.text, n.timestamp
                FROM notifications n
                INNER JOIN devices d ON d.device_identifier = n.device_id
                WHERE {where_clause}
                ORDER BY n.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            params
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
    role = user.get("role")
    
    where_clause = "s.device_id = :device_id" if role == "admin" else "s.device_id = :device_id AND d.family_id = :family_id"
    params = {"device_id": device_id, "limit": limit, "offset": offset}
    if role != "admin":
        params["family_id"] = family_id
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT s.id, s.sender, s.body, s.timestamp, s.is_incoming
                FROM sms_messages s
                INNER JOIN devices d ON d.device_identifier = s.device_id
                WHERE {where_clause}
                ORDER BY s.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            params
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
    role = user.get("role")
    
    where_clause = "c.device_id = :device_id" if role == "admin" else "c.device_id = :device_id AND d.family_id = :family_id"
    params = {"device_id": device_id, "limit": limit, "offset": offset}
    if role != "admin":
        params["family_id"] = family_id
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(f"""
                SELECT c.id, c.number, c.duration_seconds, c.type, c.timestamp
                FROM call_logs c
                INNER JOIN devices d ON d.device_identifier = c.device_id
                WHERE {where_clause}
                ORDER BY c.timestamp DESC
                LIMIT :limit OFFSET :offset
            """),
            params
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
