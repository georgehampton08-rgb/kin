import paho.mqtt.client as mqtt
import json
import time

def publish_mock_data():
    client = mqtt.Client(client_id="mock_device_001")
    
    # Establish Last Will and Testament if device dies
    client.will_set(
        topic="kin/telemetry/device_001/status",
        payload=json.dumps({"status": "offline"}),
        qos=1,
        retain=True
    )
    
    client.connect("localhost", 1883, 60)
    
    print("Mock Device: Connected. Sending valid coordinates...")
    
    payload = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "speed": 2.5,
        "altitude": 10.0,
        "battery_level": 90.0
    }
    
    client.publish("kin/telemetry/device_001", json.dumps(payload), qos=1)
    print("Mock Device: Published location data.")
    
    # Start the loop to flush the network queue out to EMQX
    client.loop_start()
    
    # Wait longer to ensure EMQX actually routes the message to the FastAPI server
    time.sleep(2) 
    
    client.loop_stop()
    
    # Simulate an abrupt disconnection to trigger the LWT!
    print("Mock Device: Disconnecting abruptly offline! Triggering LWT...")
    # By abruptly closing the socket natively (bypassing disconnect), EMQX triggers the LWT
    client._sock.close()

if __name__ == "__main__":
    publish_mock_data()
