from fastapi import APIRouter, status
from app.schemas.location import LocationUpdate

router = APIRouter()

@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(data: LocationUpdate):
    # Here you would typically save to a database
    return {"message": "Location update received successfully", "device_id": data.device_id}
