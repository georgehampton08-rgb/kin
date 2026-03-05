"""
Zones API Endpoint
==================
GET /api/v1/zones/
Returns all zones. No auth required (dashboard has no login).
"""
from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

router = APIRouter()

ZONE_COLORS = {
    "safe":       "#00cc66",
    "caution":    "#ffaa00",
    "restricted": "#ff3333",
}


@router.get("/")
async def list_zones():
    """Returns all zones (no auth — dashboard is public)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id::text, name, zone_type,
                       COALESCE(radius, 200) AS radius_meters,
                       coordinates
                FROM zones ORDER BY created_at
            """)
        )
        rows = result.fetchall()

    features = []
    for row in rows:
        coords = row.coordinates or {}
        lon = coords.get("lng", coords.get("lon", 0))
        lat = coords.get("lat", 0)
        color = ZONE_COLORS.get(row.zone_type or "safe", "#00cc66")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": row.id,
                "name": row.name,
                "zone_type": row.zone_type or "safe",
                "radius_meters": float(row.radius_meters),
                "color": color,
            },
        })

    return {"type": "FeatureCollection", "features": features}
