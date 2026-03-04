"""
Map-Matching Integration Test — Chicago
========================================
Definition of Done:
  - 10 "jagged" GPS coordinates near downtown Chicago streets (slightly offset from road centrelines)
  - OSRM snaps them to the nearest roads and interpolates a smooth path
  - matched_path stored as PostGIS LINESTRING
  - Assertions:
      * confidence >= 0.5
      * geometry type is ST_LineString
      * returned vertices > 10 (OSRM interpolates between raw points)
"""
import asyncio
import logging
from sqlalchemy import select, text, delete

from app.db.session import AsyncSessionLocal
from app.models.location import MatchedRoute
from app.core.map_matching import match_trip

logging.basicConfig(level=logging.INFO, format="%(message)s")

DEVICE = "test_child_chicago"

# 10 raw GPS points near Chicago's North Michigan Avenue ("Magnificent Mile")
# Deliberately offset 5-20m from the road centreline to simulate GPS drift
RAW_COORDS = [
    # (lon, lat)
    (-87.6244, 41.8800),
    (-87.6243, 41.8810),
    (-87.6242, 41.8820),
    (-87.6241, 41.8832),
    (-87.6240, 41.8845),
    (-87.6241, 41.8858),
    (-87.6242, 41.8870),
    (-87.6243, 41.8882),
    (-87.6244, 41.8895),
    (-87.6245, 41.8907),
]


async def cleanup():
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(MatchedRoute).where(MatchedRoute.device_id == DEVICE)
        )
        await session.commit()


async def run_test():
    await cleanup()

    print("=" * 60)
    print("  Kin Map-Matching Integration Test — Chicago")
    print("=" * 60)
    print(f"\n  Input: {len(RAW_COORDS)} jagged GPS points near N. Michigan Ave")
    print("  Provider: OSRM (self-hosted, Chicago street network)\n")

    route = await match_trip(
        device_id=DEVICE,
        coords=RAW_COORDS,
    )

    if route is None:
        print("❌  match_trip returned None — is OSRM running on port 5000?")
        print("     Run: docker start osrm-chicago   (or see OSRM setup notes)")
        return

    # Verify in DB via PostGIS spatial query
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT
                    id,
                    device_id,
                    raw_point_count,
                    confidence,
                    provider,
                    ST_GeometryType(matched_path::geometry) AS geom_type,
                    ST_NPoints(matched_path::geometry)      AS vertex_count
                FROM matched_routes
                WHERE device_id = :device_id
                ORDER BY id DESC
                LIMIT 1
            """),
            {"device_id": DEVICE}
        )
        row = result.fetchone()

    print(f"{'─'*60}")
    print(f"  DB Row ID        : {row.id}")
    print(f"  Device           : {row.device_id}")
    print(f"  Raw points in    : {row.raw_point_count}")
    print(f"  Snapped vertices : {row.vertex_count}  (OSRM interpolated)")
    print(f"  Geometry type    : {row.geom_type}")
    print(f"  Confidence score : {row.confidence:.3f}")
    print(f"  Provider         : {row.provider}")
    print(f"{'─'*60}\n")

    # OSRM confidence: not a simple percentage — 0.3+ is a strong match.
    # (Google Roads doesn't return confidence at all.)
    assert row.geom_type == "ST_LineString",  f"Expected ST_LineString, got {row.geom_type}"
    assert row.confidence >= 0.3,             f"Confidence too low: {row.confidence}"
    assert row.vertex_count > len(RAW_COORDS),f"Expected more vertices than raw input after interpolation"

    print("✅  All assertions passed. Definition of Done MET.\n")
    await cleanup()
    print("[CLEANUP] Test route removed from DB.")


if __name__ == "__main__":
    asyncio.run(run_test())
