import json
import logging
import asyncio
import os
import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app.db.session import AsyncSessionLocal
from app.models.location import CurrentStatus, LocationHistory, Device
from app.schemas.location import LocationUpdate
from app.core.geofencing import check_geofences
from app.core.ws_manager import ws_manager
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "kin/telemetry/+"
MQTT_MAX_PAYLOAD_BYTES = 65536  # 64 KB

# Store the global event loop reference
_main_loop = None


def _validate_device_id(device_id: str) -> bool:
    """Validate device_id is a plausible identifier (non-empty, bounded length)."""
    if not device_id or len(device_id) > 255:
        return False
    # Reject obviously malicious patterns
    if any(c in device_id for c in ("'", '"', ";", "--", "/*")):
        return False
    return True


async def _device_exists(device_id: str) -> bool:
    """Check if device_id exists in the devices table."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Device).where(Device.device_identifier == device_id)
        )
        return result.scalar_one_or_none() is not None


async def process_telemetry(payload: dict, device_id: str):
    # Validate device_id
    if not _validate_device_id(device_id):
        logger.warning(f"MQTT: Invalid device_id format: {device_id[:50]}")
        return

    # Validate payload using the same Pydantic model as REST endpoints
    try:
        validated = LocationUpdate(
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            altitude=payload.get("altitude"),
            speed=payload.get("speed"),
            battery_level=payload.get("battery_level"),
            device_id=device_id,
        )
    except (ValidationError, TypeError) as e:
        logger.warning(f"MQTT: Invalid payload for {device_id}: {e}")
        return

    lat = validated.latitude
    lon = validated.longitude
    alt = validated.altitude
    speed = validated.speed
    battery = validated.battery_level

    # Verify device exists in DB (silently drop messages for unknown devices)
    if not await _device_exists(device_id):
        logger.warning(f"MQTT: Message from unknown device_id '{device_id}', dropping")
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
    if not _validate_device_id(device_id):
        logger.warning(f"MQTT LWT: Invalid device_id format: {device_id[:50]}")
        return

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

    # Enforce max payload size
    if len(msg.payload) > MQTT_MAX_PAYLOAD_BYTES:
        logger.warning(
            f"MQTT: Oversized payload ({len(msg.payload)} bytes) on topic {topic}, dropping"
        )
        return

    try:
        payload = json.loads(msg.payload.decode())
    except Exception as e:
        logger.error(f"Failed to decode JSON payload: {e}")
        return

    # Extract device_id from topic
    parts = topic.split("/")

    if len(parts) == 3 and parts[2] != "+":
        device_id = parts[2]
        if not _validate_device_id(device_id):
            logger.warning(f"MQTT: Invalid device_id in topic: {topic}")
            return
        if _main_loop:
            asyncio.run_coroutine_threadsafe(process_telemetry(payload, device_id), _main_loop)

    elif len(parts) == 4 and parts[3] == "status":
        device_id = parts[2]
        if not _validate_device_id(device_id):
            logger.warning(f"MQTT LWT: Invalid device_id in topic: {topic}")
            return
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
