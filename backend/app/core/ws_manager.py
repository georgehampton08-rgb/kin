"""
WebSocket Connection Manager
=============================
Maintains active WebSockets per device_id and allows background processes
(like MQTT ingestion) to broadcast live coordinate updates to any
connected parental dashboards.
"""
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps device_id -> set of active WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        if device_id not in self.active_connections:
            self.active_connections[device_id] = set()
        self.active_connections[device_id].add(websocket)
        logger.info(f"Dashboard connected for device '{device_id}'")

    def disconnect(self, device_id: str, websocket: WebSocket):
        if device_id in self.active_connections:
            self.active_connections[device_id].discard(websocket)
            if not self.active_connections[device_id]:
                del self.active_connections[device_id]
            logger.info(f"Dashboard disconnected for device '{device_id}'")

    async def broadcast(self, device_id: str, message: dict):
        """Sends a JSON payload to all connected clients listening for device_id."""
        connections = self.active_connections.get(device_id, set())
        if not connections:
            return  # No parents currently listening

        dead_connections = set()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to websocket: {e}")
                dead_connections.add(connection)
        
        # Cleanup broken pipes
        for dead in dead_connections:
            self.disconnect(device_id, dead)


# Singleton instance shared across the app
ws_manager = ConnectionManager()
