"""
History Replay Endpoint
========================
GET /api/v1/history/replay/{device_id}/{date}

Requires a parent-scoped JWT. Returns 403 if device doesn't belong to caller's family.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text, select
from datetime import datetime, timedelta, timezone
from app.db.session import AsyncSessionLocal
from app.api.deps import get_current_user
from app.models.location import Device

router = APIRouter()


@router.get("/replay/{device_id}/{date}")
async def replay_history(
    device_id: str,
    date: str,
    user: dict = Depends(get_current_user),
):
    """Returns a GeoJSON FeatureCollection of matched routes for a device on a date."""
    role = user.get("role")
    family_id = user.get("family_id")

    async with AsyncSessionLocal() as session:
        if role == "admin":
            query = select(Device).where(Device.device_identifier == device_id)
        else:
            query = select(Device).where(
                Device.device_identifier == device_id,
                Device.family_id == family_id,
            )
        device_result = await session.execute(query)
        device = device_result.scalar_one_or_none()

        if not device:
            raise HTTPException(status_code=403, detail="Access denied")

        try:
            day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="Date must be in YYYY-MM-DD format")

        day_end = day_start + timedelta(days=1)

        result = await session.execute(
            text("""
                SELECT id, trip_start, trip_end, raw_point_count, confidence,
                       provider, ST_AsGeoJSON(matched_path::geometry) AS geojson
                FROM matched_routes
                WHERE device_id = :device_id
                  AND trip_start >= :day_start AND trip_start < :day_end
                ORDER BY trip_start ASC
            """),
            {"device_id": device_id, "day_start": day_start, "day_end": day_end},
        )
        rows = result.fetchall()

    if not rows:
        return {
            "type": "FeatureCollection",
            "features": [],
            "meta": {"device_id": device_id, "date": date, "route_count": 0},
        }

    import json

    features = []
    for row in rows:
        geometry = json.loads(row.geojson)
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": row.id,
                "trip_start": row.trip_start.isoformat(),
                "trip_end": row.trip_end.isoformat(),
                "raw_point_count": row.raw_point_count,
                "confidence": float(row.confidence) if row.confidence else None,
                "provider": row.provider,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {"device_id": device_id, "date": date, "route_count": len(features)},
    }
