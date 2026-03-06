"""
Auth Security Tests
=====================
Validates:
- Missing/invalid/expired JWTs return 401 with no stack trace
- Security headers are present on all responses
- Error responses don't leak internal details
"""
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import create_access_token
import time
from jose import jwt
from datetime import datetime, timezone, timedelta

client = TestClient(app, raise_server_exceptions=False)

_test_token = create_access_token(
    user_id="00000000-0000-0000-0000-000000000001",
    family_id="00000000-0000-0000-0000-000000000002",
    role="parent",
    scope="dashboard",
)
AUTH_HEADERS = {"Authorization": f"Bearer {_test_token}"}


class TestMissingJWT:
    """Requests without JWT to protected endpoints should return 401."""

    def test_no_auth_on_telemetry_ingest(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "test-device",
            },
        )
        assert resp.status_code == 401
        body = resp.json()
        # Must not contain stack traces or internal paths
        assert "traceback" not in resp.text.lower()
        assert "Traceback" not in resp.text
        assert ".py" not in resp.text

    def test_no_auth_on_heartbeat(self):
        resp = client.post(
            "/api/v1/telemetry/heartbeat",
            json={"device_id": "test-device"},
        )
        assert resp.status_code == 401

    def test_no_auth_on_history(self):
        resp = client.get("/api/v1/history/replay/test-device/2026-03-05")
        assert resp.status_code == 401


class TestInvalidJWT:
    """Invalid JWTs should return 401 with no stack trace."""

    def test_garbage_token(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "test-device",
            },
            headers={"Authorization": "Bearer garbage.not.a.token"},
        )
        assert resp.status_code == 401
        assert "traceback" not in resp.text.lower()

    def test_expired_token(self):
        """Create an already-expired token and verify 401."""
        from app.core.auth import JWT_SECRET_KEY, JWT_ALGORITHM
        expired_payload = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "family_id": "00000000-0000-0000-0000-000000000002",
            "role": "parent",
            "scope": "dashboard",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "test-device",
            },
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "expired" in body.get("detail", "").lower()


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    def test_headers_on_public_endpoint(self):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "max-age=63072000" in resp.headers.get("Strict-Transport-Security", "")
        assert resp.headers.get("Referrer-Policy") == "no-referrer"

    def test_headers_on_root(self):
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_csp_header_present(self):
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp
        assert "unsafe-inline" not in csp or "style-src" in csp
        assert "frame-ancestors 'none'" in csp

    def test_permissions_policy_present(self):
        resp = client.get("/")
        pp = resp.headers.get("Permissions-Policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp


class TestErrorSanitization:
    """Verify error responses don't leak internal details."""

    def test_422_no_internal_paths(self):
        """Validation errors should not expose full internal field paths."""
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": "not_a_number"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
        body = resp.text
        # Should not contain Python internal paths
        assert "app/" not in body
        assert "site-packages" not in body

    def test_401_clean_response(self):
        """401 responses should be clean JSON with no stack traces."""
        resp = client.get(
            "/api/v1/history/replay/test/2026-03-05",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body
        assert "File" not in resp.text
        assert "line" not in resp.text.split('"')  # Not in raw text outside JSON strings


class TestInputValidationBounds:
    """Verify Pydantic bounds on LocationUpdate."""

    def test_speed_too_high(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "speed": 999,
                "device_id": "test-device",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_battery_over_100(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "battery_level": 150,
                "device_id": "test-device",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_negative_battery(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "battery_level": -10,
                "device_id": "test-device",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    def test_empty_device_id_rejected(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
