"""
JWT Authentication Utilities
=============================
Handles token creation, validation, password hashing, and the
RLS context variable for family-scoped queries.
"""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from contextvars import ContextVar

from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "DEV_ONLY_CHANGE_ME_IN_PRODUCTION_256bit_key_abc123")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

PGCRYPTO_KEY = os.getenv("PGCRYPTO_KEY", "DEV_ONLY_PGCRYPTO_SYMMETRIC_KEY")

# ── Password hashing ────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Context variable for RLS ────────────────────────────────
# Set by middleware, read by the DB session pool's checkout event
current_family_id: ContextVar[Optional[str]] = ContextVar("current_family_id", default=None)
current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


def hash_password(password: str) -> str:
    # bcrypt has a hard 72-byte limit — truncate to avoid ValueError
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    family_id: str,
    role: str,
    scope: str,
    device_id: Optional[str] = None,
) -> str:
    """Create a short-lived access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "family_id": family_id,
        "role": role,
        "scope": scope,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    if device_id:
        payload["device_id"] = device_id
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    family_id: str,
    role: str,
    device_id: Optional[str] = None,
) -> tuple[str, str, datetime]:
    """
    Create a long-lived refresh token.
    Returns (encoded_token, jti, expires_at).
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "family_id": family_id,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
        "jti": jti,
    }
    if device_id:
        payload["device_id"] = device_id
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises JWTError or ExpiredSignatureError on failure.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
