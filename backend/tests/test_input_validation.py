"""
Input Validation Tests
========================
Validates Pydantic field constraints across all endpoints:
- Coordinate bounds (lat/lng), speed, battery
- Batch size limits
- Timestamp window rejection
- E.164 phone number format
- Extra field rejection (extra='forbid')
- HTML sanitization on text fields
"""
import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import create_access_token

client = TestClient(app, raise_server_exceptions=False)

_test_token = create_access_token(
    user_id="00000000-0000-0000-0000-000000000001",
    family_id="00000000-0000-0000-0000-000000000002",
    role="parent",
    scope="dashboard",
)
AUTH_HEADERS = {"Authorization": f"Bearer {_test_token}"}


class TestCoordinateBounds:
    """Coordinates outside physical bounds must return 422."""

    def test_latitude_above_90(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 999, "longitude": -87.6298, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_latitude_below_negative_90(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": -91, "longitude": -87.6298, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_longitude_above_180(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": 200, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_longitude_below_negative_180(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -181, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestSpeedAndBattery:
    """Speed and battery level must be bounded."""

    def test_speed_too_high(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62, "speed": 201, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_negative_speed(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62, "speed": -1, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_battery_over_100(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62, "battery_level": 150, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_negative_battery(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62, "battery_level": -10, "device_id": "test-device"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestBatchLimits:
    """Batch ingest must enforce size limits."""

    def test_batch_over_100_items(self):
        batch = [{"lat": 41.87, "lng": -87.62} for _ in range(101)]
        payload = json.dumps({"device_id": "test-device", "batch": batch})
        resp = client.post(
            "/api/v1/telemetry/ingest/batch",
            content=payload.encode(),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_batch_exactly_100_items_accepted(self):
        """100 items should be accepted (may return 500 due to no DB, but not 422)."""
        batch = [{"lat": 41.87, "lng": -87.62} for _ in range(100)]
        payload = json.dumps({"device_id": "test-device", "batch": batch})
        resp = client.post(
            "/api/v1/telemetry/ingest/batch",
            content=payload.encode(),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        # Should NOT be 422 (validation pass); may be 500 due to DB
        assert resp.status_code != 422


class TestExtraFieldRejection:
    """Any extra field not in the model must be rejected (extra='forbid')."""

    def test_extra_field_on_ingest(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.87,
                "longitude": -87.62,
                "device_id": "test-device",
                "evil_field": "should be rejected",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_extra_field_on_heartbeat(self):
        resp = client.post(
            "/api/v1/telemetry/heartbeat",
            json={
                "device_id": "test-device",
                "battery_level": 80,
                "unknown_field": "inject",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_extra_field_on_login(self):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@test.com",
                "password": "password123",
                "admin": True,
            },
        )
        assert resp.status_code == 422

    def test_extra_field_on_register(self):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@test.com",
                "password": "password123",
                "family_name": "Test",
                "role": "admin",  # Extra field
            },
        )
        assert resp.status_code == 422


class TestPhoneE164Validation:
    """Phone numbers must be in E.164 format."""

    def test_valid_e164_accepted(self):
        """Valid E.164 should not cause 422 (may fail at DB level, but not validation)."""
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "sms": [{
                    "sender": "+15551234567",
                    "body": "Hello",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_incoming": True,
                }],
            },
            headers=AUTH_HEADERS,
        )
        # Should NOT be 422 — validation passes
        assert resp.status_code != 422

    def test_invalid_phone_no_plus_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "sms": [{
                    "sender": "5551234567",
                    "body": "Hello",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_incoming": True,
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_invalid_phone_text_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "sms": [{
                    "sender": "not-a-phone",
                    "body": "Hello",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_incoming": True,
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_call_log_invalid_phone_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "calls": [{
                    "number": "555-123-4567",
                    "duration_seconds": 60,
                    "type": "incoming",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestTimestampBounds:
    """Timestamps must be within the allowed window."""

    def test_timestamp_2_hours_in_future_rejected(self):
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "sms": [{
                    "sender": "+15551234567",
                    "body": "Hello",
                    "timestamp": future_ts,
                    "is_incoming": True,
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_timestamp_48_hours_ago_rejected(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        resp = client.post(
            "/api/v1/telemetry/comms",
            json={
                "device_id": "test-device",
                "notifications": [{
                    "package_name": "com.test.app",
                    "title": "Test",
                    "text": "Body",
                    "timestamp": old_ts,
                }],
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


class TestHTMLSanitization:
    """HTML/script tags must be stripped from text fields."""

    def test_script_tag_stripped_from_sms_body(self):
        """Verify that <script> tags are removed from SMS body before storage."""
        from app.api.v1.endpoints.telemetry import _strip_html
        result = _strip_html('<script>alert("xss")</script>Hello')
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result

    def test_html_tags_stripped(self):
        from app.api.v1.endpoints.telemetry import _strip_html
        result = _strip_html('<b>Bold</b> and <img src="x" onerror="evil()">')
        assert "<b>" not in result
        assert "<img" not in result
        assert "Bold" in result

    def test_clean_text_passes_through(self):
        from app.api.v1.endpoints.telemetry import _strip_html
        result = _strip_html("Normal text message")
        assert result == "Normal text message"


class TestEmptyDeviceId:
    """Empty or missing device_id must be rejected."""

    def test_empty_device_id(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62, "device_id": ""},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_missing_device_id(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": 41.87, "longitude": -87.62},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
