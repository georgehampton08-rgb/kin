"""
Telemetry Endpoint Tests
=========================
Tests for the /api/v1/telemetry/ingest endpoint,
updated for JWT-based authentication.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.auth import JWT_SECRET_KEY, JWT_ALGORITHM

client = TestClient(app, raise_server_exceptions=False)


def _make_device_token():
    """Create a device-scoped JWT for telemetry ingestion."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "family_id": str(uuid.uuid4()),
            "role": "device",
            "scope": "telemetry",
            "device_id": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "jti": str(uuid.uuid4()),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def test_ingest_telemetry_missing_token():
    """No Authorization header → 401."""
    payload = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "device_id": "device_123",
    }

    response = client.post("/api/v1/telemetry/ingest", json=payload)
    assert response.status_code == 401


def test_ingest_telemetry_validation_error():
    """Invalid payload (string latitude) → 422."""
    payload = {
        "latitude": "invalid_latitude",
        "longitude": -122.4194,
        "device_id": "device_123",
    }

    token = _make_device_token()
    response = client.post(
        "/api/v1/telemetry/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
