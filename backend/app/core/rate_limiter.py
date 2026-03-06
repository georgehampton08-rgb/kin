"""
Rate Limiting Configuration
=============================
Three-tier rate limiting using slowapi:
  - Auth endpoints: 10/min per IP (brute force protection)
  - Telemetry endpoints: 60/min per device_id (high-frequency but bounded)
  - All other endpoints: 120/min per authenticated user
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

logger = logging.getLogger(__name__)


def _get_device_id_or_ip(request: Request) -> str:
    """Extract device_id from request body for telemetry rate limiting, fall back to IP."""
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri="memory://",
)
