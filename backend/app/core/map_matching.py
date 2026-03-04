"""
Map-Matching Service
====================
Provider abstraction so switching OSRM → Google Roads is a one-line config change.

Active provider controlled by env var MAP_MATCHING_PROVIDER (default: "osrm").
To switch to Google later:
  1. Set MAP_MATCHING_PROVIDER=google
  2. Set GOOGLE_ROADS_API_KEY=<your key>
  3. No other code changes needed.
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
GOOGLE_ROADS_API_KEY = os.getenv("GOOGLE_ROADS_API_KEY", "")


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
# OSRM Provider (active)
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
# Google Roads Provider (stub — ready to fill in)
# ──────────────────────────────────────────────────────────────
class GoogleRoadsProvider(MapMatchingProvider):
    """
    To activate:
      MAP_MATCHING_PROVIDER=google
      GOOGLE_ROADS_API_KEY=<key>

    Google Roads Snap to Roads endpoint:
      POST https://roads.googleapis.com/v1/snapToRoads
      params: path=lat,lon|lat,lon&interpolate=true&key=...
    """
    async def match(self, coords: list[tuple[float, float]]) -> dict:
        if not GOOGLE_ROADS_API_KEY:
            raise EnvironmentError("GOOGLE_ROADS_API_KEY is not set.")

        path = "|".join(f"{lat},{lon}" for lon, lat in coords)
        url = "https://roads.googleapis.com/v1/snapToRoads"
        params = {
            "path": path,
            "interpolate": "true",
            "key": GOOGLE_ROADS_API_KEY,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()

        snapped = data.get("snappedPoints", [])
        if not snapped:
            raise ValueError("Google Roads returned no snapped points.")

        wkt_inner = ", ".join(
            f"{p['location']['longitude']} {p['location']['latitude']}" for p in snapped
        )
        wkt = f"LINESTRING({wkt_inner})"

        return {"wkt": wkt, "confidence": None, "provider": "google",
                "vertex_count": len(snapped)}


# ──────────────────────────────────────────────────────────────
# Provider factory
# ──────────────────────────────────────────────────────────────
def get_provider() -> MapMatchingProvider:
    if MAP_MATCHING_PROVIDER == "google":
        return GoogleRoadsProvider()
    return OsrmProvider()


# ──────────────────────────────────────────────────────────────
# Public entry point — called by trip_detector
# ──────────────────────────────────────────────────────────────
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
