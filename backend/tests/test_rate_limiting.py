"""
Rate Limiting & IP Lockout Tests
====================================
Validates:
- slowapi rate limits on auth endpoints (10/min)
- IP lockout after 5 consecutive failures
- Lockout expiry after the block window
- Retry-After header on 429 responses
"""
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import create_access_token
from app.core.rate_limiter import (
    limiter,
    record_auth_failure,
    clear_auth_failures,
    check_ip_lockout,
    reset_lockout_state,
    LOCKOUT_THRESHOLD,
    LOCKOUT_DURATION_SECONDS,
    _auth_failure_tracker,
)

client = TestClient(app, raise_server_exceptions=False)

_test_token = create_access_token(
    user_id="00000000-0000-0000-0000-000000000001",
    family_id="00000000-0000-0000-0000-000000000002",
    role="parent",
    scope="dashboard",
)
AUTH_HEADERS = {"Authorization": f"Bearer {_test_token}"}


class TestAuthRateLimiting:
    """Test that auth endpoints are rate limited (slowapi)."""

    def setup_method(self):
        limiter.reset()
        reset_lockout_state()

    def test_login_rate_limit(self):
        """Sending 11 consecutive requests to /auth/login should return 429 on the 11th."""
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "test@test.com", "password": "wrongpassword"},
            )
            assert resp.status_code != 429, f"Got 429 too early on request {i + 1}"

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 429, f"Expected 429 on 11th request, got {resp.status_code}"

    def test_register_rate_limit(self):
        """Sending 11 consecutive requests to /auth/register should return 429 on the 11th."""
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{i}@test.com",
                    "password": "password123",
                    "family_name": "TestFamily",
                },
            )
            assert resp.status_code != 429, f"Got 429 too early on request {i + 1}"

        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "extra@test.com", "password": "password123", "family_name": "TestFamily"},
        )
        assert resp.status_code == 429

    def test_429_has_retry_after_header(self):
        """When rate limited, the response should include a Retry-After header."""
        for _ in range(11):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "test@test.com", "password": "wrongpassword"},
            )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers or "retry-after" in resp.headers


class TestIPLockout:
    """Test IP lockout logic after consecutive auth failures."""

    def setup_method(self):
        reset_lockout_state()

    def test_lockout_after_5_failures(self):
        """After 5 auth failures from the same IP, the 6th attempt should be blocked."""
        ip = "192.168.1.100"
        for _ in range(LOCKOUT_THRESHOLD):
            record_auth_failure(ip)

        # The entry should now be blocked
        entry = _auth_failure_tracker.get(ip)
        assert entry is not None
        assert entry["blocked_until"] > time.time()

    def test_lockout_blocks_requests(self):
        """A locked-out IP should get 429 even with valid credentials."""
        ip = "10.0.0.1"
        for _ in range(LOCKOUT_THRESHOLD):
            record_auth_failure(ip)

        from starlette.testclient import TestClient as SC
        from fastapi import HTTPException
        import pytest

        # Simulate the check
        with pytest.raises(HTTPException) as exc_info:
            # Create a mock request with the locked-out IP
            from starlette.requests import Request
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [],
                "client": (ip, 12345),
            }
            mock_request = Request(scope)
            check_ip_lockout(mock_request)

        assert exc_info.value.status_code == 429
        assert "Retry-After" in (exc_info.value.headers or {})

    def test_lockout_expires(self):
        """After the lockout window expires, requests should be allowed again."""
        ip = "10.0.0.2"
        for _ in range(LOCKOUT_THRESHOLD):
            record_auth_failure(ip)

        # Manually set blocked_until to the past
        entry = _auth_failure_tracker.get(ip)
        assert entry is not None
        entry["blocked_until"] = time.time() - 1  # Already expired

        # Should NOT raise — lockout has expired
        from starlette.requests import Request
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": (ip, 12345),
        }
        mock_request = Request(scope)
        check_ip_lockout(mock_request)  # Should not raise

    def test_clear_on_success(self):
        """Successful auth should clear failure count."""
        ip = "10.0.0.3"
        record_auth_failure(ip)
        record_auth_failure(ip)
        assert _auth_failure_tracker.get(ip) is not None

        clear_auth_failures(ip)
        assert _auth_failure_tracker.get(ip) is None
