"""
Zones API Endpoint
==================
GET /api/v1/zones/
Returns all zones for the authenticated user's family.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.api.deps import get_current_user

router = APIRouter()

ZONE_COLORS = {
    "safe":       "#00cc66",
    "caution":    "#ffaa00",
    "restricted": "#ff3333",
}


@router.get("/")
async def list_zones(user: dict = Depends(get_current_user)):
    """Returns all zones for the authenticated user's family."""
    family_id = user.get("family_id")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, name, zone_type, radius_meters,
                       ST_X(center::geometry) AS lon,
                       ST_Y(center::geometry) AS lat, created_at
                FROM zones
                WHERE family_id = :family_id::uuid OR family_id IS NULL
                ORDER BY id
            """),
            {"family_id": str(family_id)},
        )
        rows = result.fetchall()

    features = []
    for row in rows:
        color = ZONE_COLORS.get(row.zone_type or "safe", "#00cc66")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
            "properties": {
                "id": row.id,
                "name": row.name,
                "zone_type": row.zone_type or "safe",
                "radius_meters": float(row.radius_meters),
                "color": color,
            },
        })

    return {"type": "FeatureCollection", "features": features}
