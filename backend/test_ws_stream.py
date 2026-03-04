"""
Mock Streamer for WebSocket Dashboard
======================================
This script does NOT write to the database or trigger MQTT.
It connects directly to the FastAPI WebSocket endpoint as a fake device
and pushes a coordinate every 2 seconds to verify the React dashboard animates correctly.
"""
import asyncio
import json
import websockets

DEVICE = "test_child_chicago"
WS_URL = f"ws://localhost:8000/ws/live/{DEVICE}"

# Coordinates near Millennium Park, Chicago
MOCK_PATH = [
    (41.8827, -87.6226, 1.2), # start
    (41.8827, -87.6210, 1.2), # walking east
    (41.8827, -87.6190, 1.3),
    (41.8810, -87.6190, 1.4), # turning south into the park
    (41.8795, -87.6190, 1.3),
    (41.8780, -87.6190, 1.2),
    (41.8780, -87.6210, 1.1), # turning west
    (41.8780, -87.6230, 0.8),
    (41.8780, -87.6240, 0.5), # slowing down
    (41.8780, -87.6240, 0.0), # stopped
]

async def run_stream():
    print(f"Connecting mock stream to {WS_URL} ...")
    
    async with websockets.connect(WS_URL) as ws:
        print("✅  WebSocket connected. Starting stream...")
        
        while True:
            for lat, lon, speed in MOCK_PATH:
                payload = {
                    "type": "telemetry",
                    "lat": lat,
                    "lon": lon,
                    "speed": speed,
                    "battery_level": 85
                }
                
                print(f"📡 Emitting: {payload}")
                await ws.send_text(json.dumps(payload))
                
                # Wait 2 seconds between points to simulate GPS interval
                await asyncio.sleep(2.0)
                
            print("🔄 Path complete. Looping from start...\n")
            
if __name__ == "__main__":
    asyncio.run(run_stream())
