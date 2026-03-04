from fastapi.testclient import TestClient
from app.main import app
from app.core.security import API_KEY

client = TestClient(app)

def test_ingest_telemetry_success():
    payload = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "altitude": 10.5,
        "speed": 1.2,
        "battery_level": 85.0,
        "device_id": "device_123"
    }
    
    response = client.post(
        "/api/v1/telemetry/ingest",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )
    
    assert response.status_code == 201
    assert response.json() == {"message": "Location update received successfully", "device_id": "device_123"}

def test_ingest_telemetry_missing_api_key():
    payload = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "device_id": "device_123"
    }
    
    response = client.post(
        "/api/v1/telemetry/ingest",
        json=payload
    )
    
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API Key"}

def test_ingest_telemetry_validation_error():
    payload = {
        "latitude": "invalid_latitude",  # Should be float
        "longitude": -122.4194,
        "device_id": "device_123"
    }
    
    response = client.post(
        "/api/v1/telemetry/ingest",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )
    
    assert response.status_code == 422  # Unprocessable Entity
