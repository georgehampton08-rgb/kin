"""
Zones API Endpoint
==================
GET /api/v1/zones/
Returns all zones as a GeoJSON FeatureCollection.
Uses PostGIS ST_X / ST_Y to extract lon/lat from the geography point.
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
    """Returns all zones including center coordinates, radius, and zone_type."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT
                    id,
                    name,
                    zone_type,
                    radius_meters,
                    ST_X(center::geometry) AS lon,
                    ST_Y(center::geometry) AS lat,
                    created_at
                FROM zones
                ORDER BY id
            """)
        )
        rows = result.fetchall()

    features = []
    for row in rows:
        color = ZONE_COLORS.get(row.zone_type or "safe", "#00cc66")
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.lon, row.lat]
            },
            "properties": {
                "id": row.id,
                "name": row.name,
                "zone_type": row.zone_type or "safe",
                "radius_meters": float(row.radius_meters),
                "color": color,
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
