import requests
import time
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def print_step(msg):
    print(f"\n[+] {msg}")

def run_test():
    # 1. Register Parent
    print_step("Registering new parent user...")
    test_email = f"parent_{uuid.uuid4().hex[:8]}@example.com"
    res = requests.post(f"{BASE_URL}/auth/register", json={
        "email": test_email,
        "password": "SecurePassword123!",
        "family_name": "Test Family Comm"
    })
    
    if res.status_code != 201:
        print(f"Error registering: {res.text}")
        return
    parent_token = res.json()["access_token"]
    print(f"Parent registered. Token acquired.")

    # 2. Generate Pairing Token
    print_step("Generating pairing token...")
    res = requests.post(f"{BASE_URL}/auth/create-pairing-token", headers={
        "Authorization": f"Bearer {parent_token}"
    })
    if res.status_code != 200:
        print(f"Error creating pairing token: {res.text}")
        return
    pairing_token = res.json()["pairing_token"]
    print(f"Pairing token generated.")

    # 3. Simulate Device Pairing
    print_step("Simulating device pairing...")
    device_hw_id = f"android_{uuid.uuid4().hex[:12]}"
    res = requests.post(f"{BASE_URL}/auth/pair-device", json={
        "pairing_token": pairing_token,
        "device_identifier": device_hw_id
    })
    
    if res.status_code != 200:
        print(f"Error pairing device: {res.text}")
        return
    device_token = res.json()["access_token"]
    print(f"Device paired successfully! Device ID: {device_hw_id}")

    # 4. Ingest Comms (as Device)
    print_step("Ingesting communications payload (as device)...")
    comms_payload = {
        "device_id": device_hw_id,
        "notifications": [
            {
                "package_name": "com.whatsapp",
                "title": "Secret Agent",
                "text": "The package is secure.",
                "timestamp": "2026-03-05T18:00:00Z"
            }
        ],
        "sms": [
            {
                "sender": "+15558675309",
                "body": "Call me when you get this.",
                "timestamp": "2026-03-05T18:05:00Z",
                "is_incoming": True
            }
        ],
        "calls": [
            {
                "number": "+15551234567",
                "duration_seconds": 120,
                "type": "missed",
                "timestamp": "2026-03-05T18:10:00Z"
            }
        ]
    }
    
    res = requests.post(f"{BASE_URL}/telemetry/comms", json=comms_payload, headers={
        "Authorization": f"Bearer {device_token}"
    })
    print(f"Ingest response ({res.status_code}): {res.text}")
    if res.status_code != 201:
        return

    # 5. Retrieve Comms (as Parent)
    print_step("Retrieving Comms data (as Parent)...")
    
    # SMS
    res_sms = requests.get(f"{BASE_URL}/devices/{device_hw_id}/sms", headers={
        "Authorization": f"Bearer {parent_token}"
    })
    print(f"SMS Response ({res_sms.status_code}): {json.dumps(res_sms.json(), indent=2)}")

    # Calls
    res_calls = requests.get(f"{BASE_URL}/devices/{device_hw_id}/calls", headers={
        "Authorization": f"Bearer {parent_token}"
    })
    print(f"Calls Response ({res_calls.status_code}): {json.dumps(res_calls.json(), indent=2)}")

    # Notifications
    res_notif = requests.get(f"{BASE_URL}/devices/{device_hw_id}/notifications", headers={
        "Authorization": f"Bearer {parent_token}"
    })
    print(f"Notifications Response ({res_notif.status_code}): {json.dumps(res_notif.json(), indent=2)}")

if __name__ == "__main__":
    run_test()
