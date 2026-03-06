"""
Rate Limiting Tests
=====================
Validates that rate limits are enforced on auth and telemetry endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import create_access_token
from app.core.rate_limiter import limiter

client = TestClient(app, raise_server_exceptions=False)

_test_token = create_access_token(
    user_id="00000000-0000-0000-0000-000000000001",
    family_id="00000000-0000-0000-0000-000000000002",
    role="parent",
    scope="dashboard",
)
AUTH_HEADERS = {"Authorization": f"Bearer {_test_token}"}


class TestAuthRateLimiting:
    """Test that auth endpoints are rate limited."""

    def setup_method(self):
        """Reset rate limiter state before each test."""
        limiter.reset()

    def test_login_rate_limit(self):
        """Sending 11 consecutive requests to /auth/login should return 429 on the 11th."""
        for i in range(10):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "test@test.com", "password": "wrongpassword"},
            )
            # Should be 401 (wrong creds) or possibly a DB error, but NOT 429 yet
            assert resp.status_code != 429, (
                f"Got 429 too early on request {i + 1}"
            )

        # The 11th request should be rate limited
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 429, (
            f"Expected 429 on 11th request, got {resp.status_code}"
        )

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
            assert resp.status_code != 429, (
                f"Got 429 too early on request {i + 1}"
            )

        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test_extra@test.com",
                "password": "password123",
                "family_name": "TestFamily",
            },
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
        assert "Retry-After" in resp.headers or "retry-after" in resp.headers, (
            "429 response missing Retry-After header"
        )
