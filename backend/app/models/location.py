"""
SQLAlchemy Models
==================
All database models for the Kin backend.
Includes location/geofencing models and the security/auth models.
"""
import uuid
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Boolean, LargeBinary, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geography
from datetime import datetime, timezone

Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


def _genuuid():
    return uuid.uuid4()


# ──────────────────────────────────────────────────────────────
# Security / Auth Models
# ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # 'parent', 'child', or 'admin'
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    avatar_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    memberships = relationship("FamilyMembership", back_populates="user")
    devices = relationship("Device", back_populates="user")


class Family(Base):
    __tablename__ = "families"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    memberships = relationship("FamilyMembership", back_populates="family")
    devices = relationship("Device", back_populates="family")


class FamilyMembership(Base):
    __tablename__ = "family_memberships"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'parent' or 'child'

    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_family_user"),
    )

    family = relationship("Family", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Device(Base):
    __tablename__ = "devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    device_identifier = Column(String(255), unique=True, nullable=False, index=True)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    mqtt_username = Column(String(255), nullable=True)
    mqtt_password_hash = Column(String(255), nullable=True)
    paired_at = Column(DateTime(timezone=True), default=_utcnow)
    is_active = Column(Boolean, default=True)
    
    # Parent Dashboard enhancements
    nickname = Column(String(255), nullable=True)
    os_info = Column(String(255), nullable=True)
    app_version = Column(String(50), nullable=True)
    
    # Last known location
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    family = relationship("Family", back_populates="devices")
    user = relationship("User", back_populates="devices")


class PairingToken(Base):
    __tablename__ = "pairing_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    token = Column(String(64), unique=True, nullable=False, index=True)
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_genuuid)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# ──────────────────────────────────────────────────────────────
# Encrypted Location Storage
# ──────────────────────────────────────────────────────────────

class LocationRaw(Base):
    """Permanent audit trail with pgcrypto-encrypted coordinates."""
    __tablename__ = "locations_raw"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, nullable=False, index=True)
    lat_encrypted = Column(LargeBinary, nullable=False)
    lng_encrypted = Column(LargeBinary, nullable=False)
    altitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)


# ──────────────────────────────────────────────────────────────
# Location / Geofencing Models (existing, retained)
# ──────────────────────────────────────────────────────────────

class CurrentStatus(Base):
    __tablename__ = 'current_status'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    altitude = Column(Float)
    speed = Column(Float)
    battery_level = Column(Float)
    last_updated = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class LocationHistory(Base):
    __tablename__ = 'location_history'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    altitude = Column(Float)
    speed = Column(Float)
    battery_level = Column(Float)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)


class Zone(Base):
    __tablename__ = 'zones'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    center = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    radius_meters = Column(Float, nullable=False)
    zone_type = Column(String, default='safe')
    family_id = Column(UUID(as_uuid=True), ForeignKey("families.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class GeofenceEvent(Base):
    __tablename__ = 'geofence_events'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    zone_id = Column(Integer, ForeignKey('zones.id'), nullable=False)
    zone_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)


class MatchedRoute(Base):
    __tablename__ = 'matched_routes'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    trip_start = Column(DateTime(timezone=True), nullable=True)
    trip_end = Column(DateTime(timezone=True), nullable=True)
    raw_point_count = Column(Integer, nullable=False)
    matched_path = Column(Geography(geometry_type='LINESTRING', srid=4326), nullable=False)
    confidence = Column(Float, nullable=True)
    provider = Column(String, default='osrm')
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ──────────────────────────────────────────────────────────────
# Communications Interception Models
# ──────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    package_name = Column(String, nullable=False)
    title = Column(String, nullable=True)
    text = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)


class SmsMessage(Base):
    __tablename__ = 'sms_messages'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    sender = Column(String, nullable=False)
    body = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    is_incoming = Column(Boolean, nullable=False, default=True)
    is_read = Column(Boolean, nullable=False, default=False)


class CallLog(Base):
    __tablename__ = 'call_logs'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    number = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
    type = Column(String, nullable=False)  # 'missed', 'incoming', 'outgoing'
    timestamp = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)

