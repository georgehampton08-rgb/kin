import json
import logging
import asyncio
import os
import paho.mqtt.client as mqtt
from app.db.session import AsyncSessionLocal
from app.models.location import CurrentStatus, LocationHistory
from app.core.geofencing import check_geofences
from app.core.ws_manager import ws_manager
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "kin/telemetry/+"

# Store the global event loop reference
_main_loop = None

async def process_telemetry(payload: dict, device_id: str):
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    alt = payload.get("altitude")
    speed = payload.get("speed")
    battery = payload.get("battery_level")
    
    if lat is None or lon is None:
        logger.warning(f"Invalid payload for {device_id}: missing lat/lon")
        return

    async with AsyncSessionLocal() as session:
        # History
        history = LocationHistory(
            device_id=device_id,
            coordinates=f"POINT({lon} {lat})",
            altitude=alt,
            speed=speed,
            battery_level=battery
        )
        session.add(history)

        # Upsert
        stmt = pg_insert(CurrentStatus).values(
            device_id=device_id,
            coordinates=f"POINT({lon} {lat})",
            altitude=alt,
            speed=speed,
            battery_level=battery
        )

        upsert = stmt.on_conflict_do_update(
            index_elements=['device_id'],
            set_=dict(
                coordinates=stmt.excluded.coordinates,
                altitude=stmt.excluded.altitude,
                speed=stmt.excluded.speed,
                battery_level=stmt.excluded.battery_level,
                last_updated=func.now()
            )
        )
        await session.execute(upsert)
        await session.commit()
        logger.info(f"Successfully processed telemetry for {device_id}")

        # Geofencing check — runs inside the same session after commit
        await check_geofences(session, device_id, lon, lat)
        await session.commit()

        # Push to any real-time dashboards connected via WebSocket
        await ws_manager.broadcast(device_id, {
            "type": "telemetry",
            "lat": lat,
            "lon": lon,
            "speed": speed,
            "battery_level": battery
        })

async def process_lwt(device_id: str):
    # The LWT writes a 'status: offline' marker to history without coordinates
    # We use a dummy coordinate of 0 0 for the point requirement to satisfy DB constraints, 
    # but practically we would flag an 'is_active' boolean. To keep schemas identical per the plan, 
    # we log -1 altitude to represent a system event.
    async with AsyncSessionLocal() as session:
        history = LocationHistory(
            device_id=device_id,
            coordinates="POINT(0 0)",
            altitude=-1.0, 
            battery_level=-1.0
        )
        session.add(history)
        await session.commit()
        logger.warning(f"Device Offline: {device_id} disconnected unexpectedly.")

def on_connect(client, userdata, flags, rc):
    logger.info(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    client.subscribe("kin/telemetry/+/status")

def on_message(client, userdata, msg):
    topic = msg.topic
    
    try:
        payload = json.loads(msg.payload.decode())
    except Exception as e:
        logger.error(f"Failed to decode JSON payload: {e}")
        return

    # Extract device_id from topic
    parts = topic.split("/")
    
    # We are in a background thread created by paho-mqtt. 
    # Use asyncio.run() to safely execute async functions from this synchronous thread.
    if len(parts) == 3 and parts[2] != "+":
        device_id = parts[2]
        if _main_loop:
            asyncio.run_coroutine_threadsafe(process_telemetry(payload, device_id), _main_loop)
            
    elif len(parts) == 4 and parts[3] == "status":
        device_id = parts[2]
        status = payload.get("status")
        if status == "offline" and _main_loop:
            asyncio.run_coroutine_threadsafe(process_lwt(device_id), _main_loop)

class MQTTListener:
    def __init__(self):
        self.client = mqtt.Client(client_id="kin_fastapi_backend")
        self.client.on_connect = on_connect
        self.client.on_message = on_message

    def start(self):
        global _main_loop
        _main_loop = asyncio.get_running_loop()
        try:
            if MQTT_PASSWORD:
                self.client.username_pw_set(username="kin", password=MQTT_PASSWORD)
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            logger.info(f"MQTT Listener connected to {MQTT_BROKER}:{MQTT_PORT}")
        except Exception as e:
            logger.error(f"Could not connect to MQTT broker: {e}")
            
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT Listener stopped.")
