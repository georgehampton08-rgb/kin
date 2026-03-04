from fastapi import APIRouter
from app.api.v1.endpoints import telemetry
from app.api.v1.endpoints import history

api_router = APIRouter()
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
