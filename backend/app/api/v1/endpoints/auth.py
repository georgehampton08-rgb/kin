"""
Auth Endpoints
===============
POST /auth/pair-device  — Accept a one-time pairing token, create device, return JWTs
POST /auth/refresh      — Rotate refresh token
POST /auth/register     — Register a new parent user (creates family automatically)
POST /auth/login        — Login and get tokens
POST /auth/create-pairing-token — Parent generates a pairing token for QR code
"""
import os
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import limiter

from app.db.session import AsyncSessionLocal
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    current_family_id,
)
from app.models.location import (
    User, Family, FamilyMembership, Device,
    PairingToken, RefreshToken,
)
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

PAIRING_TOKEN_TTL_MINUTES = 10


# ── Schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str = Field(..., min_length=5, max_length=255, description="Parent email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    family_name: str = Field(..., min_length=1, max_length=100, description="Family name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class PairDeviceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    pairing_token: str = Field(..., min_length=1, max_length=128, description="One-time pairing token from QR code")
    device_identifier: str = Field(..., min_length=1, max_length=255, description="Android hardware ID (SHA-256)")


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    refresh_token: str = Field(..., min_length=1, max_length=2048)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PairDeviceResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    device_id: str
    mqtt_config: dict


# ── Register ─────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, req: RegisterRequest):
    """Register a new parent user. Automatically creates a family."""
    async with AsyncSessionLocal() as session:
        # Check if email already exists
        existing = await session.execute(
            select(User).where(User.email == req.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create family
        family = Family(name=req.family_name)
        session.add(family)
        await session.flush()

        # Create user
        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            role="parent",
        )
        session.add(user)
        await session.flush()

        # Create membership
        membership = FamilyMembership(
            family_id=family.id,
            user_id=user.id,
            role="parent",
        )
        session.add(membership)
        await session.commit()

        # Generate tokens
        access_token = create_access_token(
            user_id=str(user.id),
            family_id=str(family.id),
            role="parent",
            scope="dashboard",
        )
        refresh_tok, jti, expires_at = create_refresh_token(
            user_id=str(user.id),
            family_id=str(family.id),
            role="parent",
        )

        # Store refresh token
        rt = RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at)
        session.add(rt)
        await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_tok)


# ── Login ────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    """Login with email + password."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == req.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Get the user's family
        membership_result = await session.execute(
            select(FamilyMembership).where(FamilyMembership.user_id == user.id)
        )
        membership = membership_result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no family membership",
            )

        family_id = str(membership.family_id)

        access_token = create_access_token(
            user_id=str(user.id),
            family_id=family_id,
            role=user.role,
            scope="dashboard" if user.role == "parent" else "telemetry",
        )
        refresh_tok, jti, expires_at = create_refresh_token(
            user_id=str(user.id),
            family_id=family_id,
            role=user.role,
        )

        rt = RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at)
        session.add(rt)
        await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_tok)


# ── Create Pairing Token ────────────────────────────────────

@router.post("/create-pairing-token")
async def create_pairing_token(user: dict = Depends(get_current_user)):
    """Parent creates a one-time pairing token for QR code."""
    token_value = secrets.token_urlsafe(48)  # ~64 chars

    async with AsyncSessionLocal() as session:
        family_id = user.get("family_id")
        user_id = user.get("sub") or user.get("user_id")

        pt = PairingToken(
            token=token_value,
            family_id=family_id,
            created_by=user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=PAIRING_TOKEN_TTL_MINUTES),
        )
        session.add(pt)
        await session.commit()

    return {
        "pairing_token": token_value,
        "expires_in_seconds": PAIRING_TOKEN_TTL_MINUTES * 60,
        "qr_payload": {
            "api_url": os.getenv("KIN_API_URL", "https://kin-api-3snosaq75a-uc.a.run.app"),
            "pairing_token": token_value,
            "mqtt_host": os.getenv("MQTT_HOST", "34.123.69.22"),
            "mqtt_port": int(os.getenv("MQTT_PORT", "1883")),
        },
    }


# ── Pair Device ──────────────────────────────────────────────

@router.post("/pair-device", response_model=PairDeviceResponse)
@limiter.limit("10/minute")
async def pair_device(request: Request, req: PairDeviceRequest):
    """
    Accept a one-time pairing token (from QR code), validate it,
    create the device record, and return a device-scoped JWT.
    """
    async with AsyncSessionLocal() as session:
        # Look up the pairing token
        result = await session.execute(
            select(PairingToken).where(PairingToken.token == req.pairing_token)
        )
        pt = result.scalar_one_or_none()

        if not pt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pairing token",
            )

        if pt.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pairing token already consumed",
            )

        if pt.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pairing token has expired",
            )

        # Check if device_identifier is already paired
        existing_device_result = await session.execute(
            select(Device).where(Device.device_identifier == req.device_identifier)
        )
        device = existing_device_result.scalar_one_or_none()
        is_new_device = device is None
        mqtt_password = None

        if device:
            # Re-pairing an existing device — update family
            device.family_id = pt.family_id
            device.is_active = True
        else:
            # Create a child user for the device
            child_user = User(
                email=f"device_{req.device_identifier[:16]}@kin.local",
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                role="child",
            )
            session.add(child_user)
            await session.flush()

            # Add child to family
            membership = FamilyMembership(
                family_id=pt.family_id,
                user_id=child_user.id,
                role="child",
            )
            session.add(membership)

            # Create device
            mqtt_password = secrets.token_urlsafe(24)
            device = Device(
                device_identifier=req.device_identifier,
                family_id=pt.family_id,
                user_id=child_user.id,
                mqtt_username=f"device_{str(uuid.uuid4())[:8]}",
                mqtt_password_hash=hash_password(mqtt_password),
            )
            session.add(device)
            await session.flush()

        # Mark token as used
        pt.used_at = datetime.now(timezone.utc)
        pt.device_id = device.id

        # Get or determine the child user_id
        child_user_id = str(device.user_id)
        family_id = str(pt.family_id)

        # Generate device-scoped tokens
        access_token = create_access_token(
            user_id=child_user_id,
            family_id=family_id,
            role="device",
            scope="telemetry",
            device_id=str(device.id),
        )
        refresh_tok, jti, expires_at = create_refresh_token(
            user_id=child_user_id,
            family_id=family_id,
            role="device",
            device_id=str(device.id),
        )

        rt = RefreshToken(
            jti=jti,
            user_id=uuid.UUID(child_user_id),
            device_id=device.id,
            expires_at=expires_at,
        )
        session.add(rt)
        await session.commit()

        mqtt_config = {
            "host": os.getenv("MQTT_HOST", "localhost"),
            "port": int(os.getenv("MQTT_PORT", "1883")),
            "username": device.mqtt_username,
            "password": mqtt_password if is_new_device else "(use existing credentials)",
            "topic_publish": f"kin/telemetry/{device.device_identifier}",
            "topic_lwt": f"kin/telemetry/{device.device_identifier}/status",
        }

    return PairDeviceResponse(
        access_token=access_token,
        refresh_token=refresh_tok,
        device_id=str(device.id),
        mqtt_config=mqtt_config,
    )


# ── Refresh Token ────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(request: Request, req: RefreshRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    from jose import JWTError, ExpiredSignatureError

    try:
        payload = decode_token(req.refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    jti = payload.get("jti")

    async with AsyncSessionLocal() as session:
        # Check if token is revoked
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        rt = result.scalar_one_or_none()

        if not rt:
            raise HTTPException(status_code=401, detail="Refresh token not found")

        if rt.revoked_at is not None:
            # Token reuse detected — revoke all tokens for this user/device
            logger.warning(f"Refresh token reuse detected for user {payload['sub']}")
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")

        # Revoke the old refresh token
        rt.revoked_at = datetime.now(timezone.utc)

        # Issue new tokens
        user_id = payload["sub"]
        family_id = payload["family_id"]
        role = payload["role"]
        device_id = payload.get("device_id")

        scope = "dashboard" if role == "parent" else "telemetry"

        new_access = create_access_token(
            user_id=user_id,
            family_id=family_id,
            role=role,
            scope=scope,
            device_id=device_id,
        )
        new_refresh, new_jti, new_expires = create_refresh_token(
            user_id=user_id,
            family_id=family_id,
            role=role,
            device_id=device_id,
        )

        new_rt = RefreshToken(
            jti=new_jti,
            user_id=uuid.UUID(user_id),
            device_id=uuid.UUID(device_id) if device_id else None,
            expires_at=new_expires,
        )
        session.add(new_rt)
        await session.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)
