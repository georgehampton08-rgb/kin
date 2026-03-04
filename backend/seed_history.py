"""
Seed mock MatchedRoutes for today (Chicago path) so the history scrubber has data.
Run once: python seed_history.py
"""
import asyncio
from datetime import datetime, timedelta, timezone
from app.db.session import AsyncSessionLocal
from app.models.location import MatchedRoute

# A path near Chicago's Millennium Park area (35 points over 8 hours)
ROUTE_COORDS = [
    (-87.6230, 41.8800), (-87.6225, 41.8807), (-87.6220, 41.8814),
    (-87.6215, 41.8821), (-87.6210, 41.8827), (-87.6205, 41.8834),
    (-87.6200, 41.8841), (-87.6196, 41.8848), (-87.6193, 41.8855),
    (-87.6190, 41.8862), (-87.6188, 41.8868), (-87.6186, 41.8874),
    (-87.6184, 41.8880), (-87.6180, 41.8886), (-87.6175, 41.8891),
    (-87.6170, 41.8896), (-87.6165, 41.8899), (-87.6160, 41.8901),
    (-87.6155, 41.8899), (-87.6150, 41.8896), (-87.6145, 41.8893),
    (-87.6140, 41.8890), (-87.6135, 41.8887), (-87.6130, 41.8884),
    (-87.6125, 41.8880), (-87.6120, 41.8876), (-87.6115, 41.8872),
    (-87.6110, 41.8867), (-87.6105, 41.8861), (-87.6100, 41.8854),
    (-87.6097, 41.8847), (-87.6095, 41.8840), (-87.6093, 41.8833),
    (-87.6091, 41.8826), (-87.6090, 41.8820),
]

def coords_to_wkt(coords):
    pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts})"

async def seed():
    today = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    interval = timedelta(minutes=15)

    async with AsyncSessionLocal() as session:
        # Create 4 trip segments throughout the day
        segments = [
            (ROUTE_COORDS[:10],  today),
            (ROUTE_COORDS[8:20], today + timedelta(hours=2)),
            (ROUTE_COORDS[15:28], today + timedelta(hours=4)),
            (ROUTE_COORDS[25:],  today + timedelta(hours=6)),
        ]
        for coords, trip_start in segments:
            trip_end = trip_start + timedelta(minutes=len(coords) * 2)
            route = MatchedRoute(
                device_id="test_child_chicago",
                trip_start=trip_start,
                trip_end=trip_end,
                raw_point_count=len(coords),
                matched_path=f"SRID=4326;{coords_to_wkt(coords)}",
                confidence=0.82,
                provider="osrm",
            )
            session.add(route)

        await session.commit()
        print(f"✅ Seeded {len(segments)} MatchedRoute segments for today.")

if __name__ == "__main__":
    asyncio.run(seed())
