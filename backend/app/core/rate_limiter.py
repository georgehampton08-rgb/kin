"""
Rate Limiting Configuration
=============================
Three-tier rate limiting using slowapi:
  - Auth endpoints: 10/min per IP (brute force protection)
  - Telemetry endpoints: 60/min per device_id (high-frequency but bounded)
  - All other endpoints: 120/min per authenticated user

Supports Redis backend when REDIS_URL is set, falls back to in-memory for dev.
Includes IP lockout after 5 consecutive auth failures.
"""
import os
import time
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ── Storage backend ──────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "")
_storage_uri = REDIS_URL if REDIS_URL else "memory://"

if REDIS_URL:
    logger.info("Rate limiter using Redis backend")
else:
    logger.info("Rate limiter using in-memory backend (dev only)")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri=_storage_uri,
)

# ── IP Lockout after consecutive failures ─────────────────────
# In-memory store for dev; production should use Redis via REDIS_URL
# Format: ip -> {"failures": int, "blocked_until": float (timestamp)}
_auth_failure_tracker: dict[str, dict] = {}

LOCKOUT_THRESHOLD = 5  # consecutive failures before lockout
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes


def record_auth_failure(ip: str) -> None:
    """Record an authentication failure for an IP address."""
    now = time.time()
    entry = _auth_failure_tracker.get(ip)

    if entry and entry.get("blocked_until", 0) > now:
        return  # Already blocked

    if not entry:
        _auth_failure_tracker[ip] = {"failures": 1, "blocked_until": 0}
    else:
        entry["failures"] = entry.get("failures", 0) + 1
        if entry["failures"] >= LOCKOUT_THRESHOLD:
            entry["blocked_until"] = now + LOCKOUT_DURATION_SECONDS
            logger.warning(f"IP {ip} locked out for {LOCKOUT_DURATION_SECONDS}s after {LOCKOUT_THRESHOLD} failures")


def clear_auth_failures(ip: str) -> None:
    """Clear failure count on successful auth."""
    _auth_failure_tracker.pop(ip, None)


def check_ip_lockout(request: Request) -> None:
    """FastAPI dependency that checks if an IP is locked out."""
    ip = get_remote_address(request)
    entry = _auth_failure_tracker.get(ip)
    if not entry:
        return

    now = time.time()
    if entry.get("blocked_until", 0) > now:
        remaining = int(entry["blocked_until"] - now)
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please try again later.",
            headers={"Retry-After": str(remaining)},
        )

    # If block has expired, clear the entry
    if entry.get("blocked_until", 0) > 0 and entry["blocked_until"] <= now:
        _auth_failure_tracker.pop(ip, None)


def reset_lockout_state() -> None:
    """Reset all lockout state (for testing)."""
    _auth_failure_tracker.clear()
