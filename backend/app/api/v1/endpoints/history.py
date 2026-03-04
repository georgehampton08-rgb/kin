"""
History Replay Endpoint
========================
GET /api/v1/history/replay/{device_id}/{date}

Returns all MatchedRoutes for a device on a given date as a GeoJSON FeatureCollection.
PostGIS's ST_AsGeoJSON handles the geometry serialization server-side for maximum speed.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from app.db.session import AsyncSessionLocal

router = APIRouter()

@router.get("/replay/{device_id}/{date}")
async def replay_history(device_id: str, date: str):
    """
    Returns a GeoJSON FeatureCollection of all matched routes for a device on the given date.
    Each Feature contains the matched LineString geometry and a `trip_start` timestamp property.
    """
    # Parse the date parameter
    try:
        day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Date must be in YYYY-MM-DD format")

    day_end = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT
                    id,
                    trip_start,
                    trip_end,
                    raw_point_count,
                    confidence,
                    provider,
                    ST_AsGeoJSON(matched_path::geometry) AS geojson
                FROM matched_routes
                WHERE
                    device_id = :device_id
                    AND trip_start >= :day_start
                    AND trip_start <  :day_end
                ORDER BY trip_start ASC
            """),
            {
                "device_id": device_id,
                "day_start": day_start,
                "day_end": day_end,
            }
        )
        rows = result.fetchall()

    if not rows:
        # Return an empty FeatureCollection — not a 404 — so the frontend handles gracefully
        return {
            "type": "FeatureCollection",
            "features": [],
            "meta": {"device_id": device_id, "date": date, "route_count": 0}
        }

    import json

    features = []
    for row in rows:
        geometry = json.loads(row.geojson)  # PostGIS returns valid GeoJSON string
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
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "device_id": device_id,
            "date": date,
            "route_count": len(features),
        }
    }
