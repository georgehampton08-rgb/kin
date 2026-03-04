from pydantic import BaseModel, Field

class LocationUpdate(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    altitude: float | None = Field(None, description="Altitude in meters")
    speed: float | None = Field(None, description="Speed in meters per second")
    battery_level: float | None = Field(None, description="Device battery level percentage")
    device_id: str = Field(..., description="Unique device identifier")
