"""
SQL Injection Prevention Tests
================================
Sends classic SQL injection payloads to validate:
1. Type-mismatch payloads (strings in numeric fields) are rejected with 422
2. String-field payloads reach parameterized queries safely (no SQL leakage in response)
3. Extra/unknown fields are rejected by ConfigDict(extra='forbid')
4. Out-of-bounds values are rejected
"""
import json
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import create_access_token

# raise_server_exceptions=False so we see the actual HTTP response
client = TestClient(app, raise_server_exceptions=False)

_test_token = create_access_token(
    user_id="00000000-0000-0000-0000-000000000001",
    family_id="00000000-0000-0000-0000-000000000002",
    role="parent",
    scope="dashboard",
)
AUTH_HEADERS = {"Authorization": f"Bearer {_test_token}"}

INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE locations_raw; --",
    '{"$gt": ""}',
    "1; SELECT * FROM users --",
    "admin'--",
    "' UNION SELECT * FROM users --",
    "'); DELETE FROM devices; --",
]

# Sensitive SQL keywords that must never appear in error responses
LEAKED_SQL_PATTERNS = ["SELECT ", "INSERT ", "DELETE ", "DROP ", "UPDATE ", "FROM users", "FROM devices"]


def _assert_no_sql_leakage(resp, context: str):
    """Assert that the response body doesn't contain leaked SQL."""
    body = resp.text
    for pattern in LEAKED_SQL_PATTERNS:
        assert pattern not in body, (
            f"SQL leakage detected in {context}: found '{pattern}' in response"
        )
    assert "Traceback" not in body, f"Python traceback leaked in {context}"
    assert "site-packages" not in body, f"Internal path leaked in {context}"


class TestTelemetryIngestInjection:
    """Test POST /api/v1/telemetry/ingest with injection payloads."""

    def test_injection_in_device_id_no_leakage(self):
        """device_id injection payloads: response must not leak SQL or succeed."""
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "latitude": 41.8781,
                    "longitude": -87.6298,
                    "speed": 5.0,
                    "battery_level": 80.0,
                    "device_id": payload,
                },
                headers=AUTH_HEADERS,
            )
            # Must not succeed
            assert resp.status_code not in (200, 201), (
                f"Injection '{payload}' succeeded with {resp.status_code}"
            )
            _assert_no_sql_leakage(resp, f"telemetry device_id='{payload}'")

    def test_injection_in_latitude(self):
        """Latitude must be a float — strings should be rejected at validation."""
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "latitude": payload,
                    "longitude": -87.6298,
                    "speed": 5.0,
                    "battery_level": 80.0,
                    "device_id": "test-device-01",
                },
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 422

    def test_injection_in_longitude(self):
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "latitude": 41.8781,
                    "longitude": payload,
                    "speed": 5.0,
                    "battery_level": 80.0,
                    "device_id": "test-device-01",
                },
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 422

    def test_out_of_bounds_latitude(self):
        for bad_lat in [-91, 91, 999, -999]:
            resp = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "latitude": bad_lat,
                    "longitude": -87.6298,
                    "speed": 5.0,
                    "battery_level": 80.0,
                    "device_id": "test-device-01",
                },
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 422

    def test_out_of_bounds_longitude(self):
        for bad_lng in [-181, 181, 999, -999]:
            resp = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "latitude": 41.8781,
                    "longitude": bad_lng,
                    "speed": 5.0,
                    "battery_level": 80.0,
                    "device_id": "test-device-01",
                },
                headers=AUTH_HEADERS,
            )
            assert resp.status_code == 422

    def test_extra_fields_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "test-device-01",
                "admin_override": True,
                "sql_inject": "'; DROP TABLE users; --",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestHeartbeatInjection:

    def test_injection_in_device_id_no_leakage(self):
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/telemetry/heartbeat",
                json={"device_id": payload, "battery_level": 80.0},
                headers=AUTH_HEADERS,
            )
            assert resp.status_code not in (200, 201)
            _assert_no_sql_leakage(resp, f"heartbeat device_id='{payload}'")


class TestAuthInjection:

    def test_login_injection_no_leakage(self):
        """Injection in login fields must not leak SQL."""
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": payload, "password": "password123"},
            )
            _assert_no_sql_leakage(resp, f"login email='{payload}'")

        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "test@test.com", "password": payload},
            )
            _assert_no_sql_leakage(resp, f"login password='{payload}'")

    def test_register_injection_in_email(self):
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": payload,
                    "password": "password123",
                    "family_name": "TestFamily",
                },
            )
            assert resp.status_code in (400, 422)

    def test_register_extra_fields_rejected(self):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "family_name": "Test",
                "role": "admin",
            },
        )
        assert resp.status_code == 422


class TestCommsInjection:

    def test_injection_in_comms_device_id_no_leakage(self):
        for payload in INJECTION_PAYLOADS:
            resp = client.post(
                "/api/v1/telemetry/comms",
                json={"device_id": payload, "notifications": []},
                headers=AUTH_HEADERS,
            )
            _assert_no_sql_leakage(resp, f"comms device_id='{payload}'")

    def test_invalid_call_type_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device-01",
                "calls": [{
                    "number": "555-1234",
                    "duration_seconds": 60,
                    "type": "'; DROP TABLE call_logs; --",
                    "timestamp": "2026-03-05T12:00:00Z",
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestBatchInjection:

    def test_oversized_batch_rejected(self):
        huge_batch = [{"lat": 41.8781, "lng": -87.6298} for _ in range(101)]
        resp = client.post(
            "/api/v1/telemetry/ingest/batch",
            json={"device_id": "test-device-01", "batch": huge_batch},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_out_of_bounds_batch_point(self):
        resp = client.post(
            "/api/v1/telemetry/ingest/batch",
            json={
                "device_id": "test-device-01",
                "batch": [{"lat": 999, "lng": -87.6298}],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
