import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.api import api_router
from app.core.security import JWTAuthMiddleware
from app.core.mqtt import MQTTListener
from app.core.ws_manager import ws_manager
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.endpoints.health import set_mqtt_listener

mqtt_listener = MQTTListener()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    mqtt_listener.start()
    set_mqtt_listener(mqtt_listener)
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    mqtt_listener.stop()


# Build CORS origins from env — supports comma-separated list for multi-origin prod setups
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
)
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(title="Kin Backend API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(JWTAuthMiddleware)

# Mount /health at root level (not under /api/v1) so Cloud Run probe hits it cheaply
from app.api.v1.endpoints import health as health_module
app.include_router(health_module.router)

app.include_router(api_router, prefix="/api/v1")


@app.websocket("/ws/live/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await ws_manager.connect(device_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(device_id, websocket)


@app.get("/")
def root():
    return {"message": "Welcome to the Kin API v2"}
