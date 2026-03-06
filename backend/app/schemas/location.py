from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    altitude: float | None = Field(None, ge=-500, le=100000, description="Altitude in meters")
    speed: float | None = Field(None, ge=0, le=200, description="Speed in meters per second")
    battery_level: float | None = Field(None, ge=0, le=100, description="Device battery level percentage")
    device_id: str = Field(..., min_length=1, max_length=255, description="Unique device identifier")
