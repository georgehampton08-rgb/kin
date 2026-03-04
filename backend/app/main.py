from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.api.v1.api import api_router
from app.core.security import APIKeyMiddleware
from app.core.mqtt import MQTTListener
from app.core.ws_manager import ws_manager

mqtt_listener = MQTTListener()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    mqtt_listener.start()
    yield
    # Shutdown
    mqtt_listener.stop()

app = FastAPI(title="Kin Backend API", version="1.0.0", lifespan=lifespan)

# Add API Key Middleware
app.add_middleware(APIKeyMiddleware)

# Include v1 routers
app.include_router(api_router, prefix="/api/v1")

@app.websocket("/ws/live/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await ws_manager.connect(device_id, websocket)
    try:
        while True:
            # We only expect the dashboard to receive data, not send,
            # but we await receive to block and detect disconnects natively.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(device_id, websocket)

@app.get("/")
def root():
    return {"message": "Welcome to the Kin API"}
