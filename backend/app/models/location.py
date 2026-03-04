from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from geoalchemy2 import Geography
from datetime import datetime, timezone

Base = declarative_base()

class CurrentStatus(Base):
    __tablename__ = 'current_status'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    altitude = Column(Float)
    speed = Column(Float)
    battery_level = Column(Float)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class LocationHistory(Base):
    __tablename__ = 'location_history'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    altitude = Column(Float)
    speed = Column(Float)
    battery_level = Column(Float)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Zone(Base):
    __tablename__ = 'zones'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    center = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    radius_meters = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class GeofenceEvent(Base):
    __tablename__ = 'geofence_events'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    zone_id = Column(Integer, ForeignKey('zones.id'), nullable=False)
    zone_name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # 'ENTRY' or 'EXIT'
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MatchedRoute(Base):
    __tablename__ = 'matched_routes'
    id = Column(Integer, primary_key=True)
    device_id = Column(String, index=True, nullable=False)
    trip_start = Column(DateTime(timezone=True), nullable=True)
    trip_end = Column(DateTime(timezone=True), nullable=True)
    raw_point_count = Column(Integer, nullable=False)
    # Road-snapped LineString from OSRM / Google Roads
    matched_path = Column(Geography(geometry_type='LINESTRING', srid=4326), nullable=False)
    confidence = Column(Float, nullable=True)   # OSRM 0–1; Google provides quality score
    provider = Column(String, default='osrm')   # 'osrm' or 'google'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
