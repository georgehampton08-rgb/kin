from fastapi import APIRouter
from app.api.v1.endpoints import telemetry
from app.api.v1.endpoints import history
from app.api.v1.endpoints import zones
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import heartbeat
from app.api.v1.endpoints import devices

api_router = APIRouter()
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(zones.router, prefix="/zones", tags=["zones"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(heartbeat.router, prefix="/telemetry", tags=["heartbeat"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
