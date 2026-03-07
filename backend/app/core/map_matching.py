"""
Map-Matching Service
====================
Provider abstraction supporting:
  - osrm   : Self-hosted OSRM (MIT licensed) — DEFAULT
  - valhalla: Self-hosted Valhalla (MIT licensed) — OSM data (ODbL)

Both are 100% open-source with zero commercial API key requirements.
Google Roads has been removed; no proprietary map-matching APIs exist
anywhere in this codebase.

Active provider controlled by env var MAP_MATCHING_PROVIDER (default: "osrm").
To switch to Valhalla:
  1. Set MAP_MATCHING_PROVIDER=valhalla
  2. Set VALHALLA_BASE_URL=http://<your-valhalla-host>:8002
  3. Run: docker run -dt -p 8002:8002 ghcr.io/gis-ops/docker-valhalla:latest
"""
import os
import logging
import aiohttp
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.location import MatchedRoute
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
MAP_MATCHING_PROVIDER = os.getenv("MAP_MATCHING_PROVIDER", "osrm")
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://localhost:5000")
VALHALLA_BASE_URL = os.getenv("VALHALLA_BASE_URL", "http://localhost:8002")


# ──────────────────────────────────────────────────────────────
# Base abstract provider
# ──────────────────────────────────────────────────────────────
class MapMatchingProvider(ABC):
    @abstractmethod
    async def match(self, coords: list[tuple[float, float]]) -> dict:
        """
        Accept a list of (lon, lat) tuples.
        Return dict with keys:
          - 'wkt'        : WKT LINESTRING string for PostGIS
          - 'confidence' : float 0–1 (or None)
          - 'provider'   : str provider name
        """


# ──────────────────────────────────────────────────────────────
# OSRM Provider (default)
# ──────────────────────────────────────────────────────────────
class OsrmProvider(MapMatchingProvider):
    async def match(self, coords: list[tuple[float, float]]) -> dict:
        # Build coordinate string: lon,lat;lon,lat;...
        coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
        url = f"{OSRM_BASE_URL}/match/v1/foot/{coord_str}"
        params = {
            "geometries": "geojson",
            "overview": "full",
            "annotations": "false",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()

        if data.get("code") != "Ok" or not data.get("matchings"):
            raise ValueError(f"OSRM match failed: {data.get('code')} — {data.get('message', '')}")

        matching = data["matchings"][0]
        confidence = matching.get("confidence")
        geojson_coords = matching["geometry"]["coordinates"]  # [[lon, lat], ...]

        # Build WKT LineString
        wkt_inner = ", ".join(f"{lon} {lat}" for lon, lat in geojson_coords)
        wkt = f"LINESTRING({wkt_inner})"

        return {"wkt": wkt, "confidence": confidence, "provider": "osrm",
                "vertex_count": len(geojson_coords)}


# ──────────────────────────────────────────────────────────────
# Valhalla Provider (open-source alternative)
# MIT licensed, self-hosted via ghcr.io/gis-ops/docker-valhalla
# ──────────────────────────────────────────────────────────────
class ValhallaProvider(MapMatchingProvider):
    """
    Valhalla /trace_route map-matching endpoint.

    Shape array format: [{"lon": x, "lat": y}, ...]
    Costing: "auto" for driving, "pedestrian" for walking.
    Costing is selected dynamically from the "costing" env var or defaults to "auto".

    Docker quickstart:
      docker run -dt -p 8002:8002 ghcr.io/gis-ops/docker-valhalla:latest
    """

    async def match(self, coords: list[tuple[float, float]]) -> dict:
        costing = os.getenv("VALHALLA_COSTING", "auto")
        shape = [{"lon": lon, "lat": lat} for lon, lat in coords]
        payload = {
            "shape": shape,
            "costing": costing,
            "shape_match": "map_snap",
            "filters": {
                "attributes": ["edge.road_class", "edge.names"],
                "action": "include",
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{VALHALLA_BASE_URL}/trace_route",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()

        if "trip" not in data:
            raise ValueError(f"Valhalla trace_route failed: {data}")

        legs = data["trip"]["legs"]
        all_coords: list[tuple[float, float]] = []
        for leg in legs:
            import polyline as pl  # python-polyline (MIT)
            decoded = pl.decode(leg["shape"], 6)
            all_coords.extend((lon, lat) for lat, lon in decoded)

        wkt_inner = ", ".join(f"{lon} {lat}" for lon, lat in all_coords)
        wkt = f"LINESTRING({wkt_inner})"

        return {
            "wkt": wkt,
            "confidence": None,  # Valhalla does not expose a confidence score
            "provider": f"valhalla:{costing}",
            "vertex_count": len(all_coords),
        }


# ──────────────────────────────────────────────────────────────
# Provider factory
# ──────────────────────────────────────────────────────────────
def get_provider() -> MapMatchingProvider:
    if MAP_MATCHING_PROVIDER == "valhalla":
        return ValhallaProvider()
    return OsrmProvider()


# ──────────────────────────────────────────────────────────────
# Public entry point — called by trip_detector
# ──────────────────────────────────────────────────────────────
async def match_trip_by_id(trip_id: str) -> MatchedRoute | None:
    """
    Entry point called by the trip state machine.
    Fetches coordinates for a TRIP_CLOSED trip from location_history
    and runs map-matching.

    GATE: Only processes trips with status = 'TRIP_CLOSED'.
    Open or paused trips are silently skipped.
    """
    from sqlalchemy import text as sa_text

    async with AsyncSessionLocal() as session:
        # Verify trip is actually closed
        trip_result = await session.execute(
            sa_text("""
                SELECT device_id, start_time, end_time, status
                FROM trips WHERE id = :trip_id
            """),
            {"trip_id": trip_id},
        )
        trip = trip_result.fetchone()

    if trip is None:
        logger.warning(f"[MapMatch] Trip {trip_id} not found — skipping")
        return None

    if trip.status != "TRIP_CLOSED":
        logger.debug(
            f"[MapMatch] Trip {trip_id} has status '{trip.status}' — "
            "map-matching gated to TRIP_CLOSED only, skipping"
        )
        return None

    device_id = trip.device_id
    trip_start = trip.start_time
    trip_end = trip.end_time

    # Fetch raw coordinates from location_history for this device in trip window
    async with AsyncSessionLocal() as session:
        coords_result = await session.execute(
            sa_text("""
                SELECT ST_X(coordinates::geometry) AS lon,
                       ST_Y(coordinates::geometry) AS lat
                FROM location_history
                WHERE device_id = :device_id
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
                ORDER BY timestamp ASC
            """),
            {"device_id": device_id, "start_time": trip_start, "end_time": trip_end},
        )
        rows = coords_result.fetchall()

    if len(rows) < 2:
        logger.warning(
            f"[MapMatch] Trip {trip_id} has only {len(rows)} points — "
            "cannot match, need at least 2"
        )
        return None

    coords = [(row.lon, row.lat) for row in rows]
    return await match_trip(device_id, coords, trip_start, trip_end)


async def match_trip(
    device_id: str,
    coords: list[tuple[float, float]],     # (lon, lat) pairs
    trip_start: datetime | None = None,
    trip_end: datetime | None = None,
) -> MatchedRoute | None:
    provider = get_provider()
    try:
        result = await provider.match(coords)
    except Exception as e:
        logger.error(f"[MapMatch] Provider '{MAP_MATCHING_PROVIDER}' failed for {device_id}: {e}")
        return None

    async with AsyncSessionLocal() as session:
        route = MatchedRoute(
            device_id=device_id,
            trip_start=trip_start,
            trip_end=trip_end,
            raw_point_count=len(coords),
            matched_path=result["wkt"],
            confidence=result["confidence"],
            provider=result["provider"],
        )
        session.add(route)
        await session.commit()
        await session.refresh(route)

    logger.info(
        f"[MapMatch] ✅ Trip saved for '{device_id}' — "
        f"provider={result['provider']}, confidence={result['confidence']}, "
        f"vertices={result['vertex_count']} (raw={len(coords)})"
    )
    return route
