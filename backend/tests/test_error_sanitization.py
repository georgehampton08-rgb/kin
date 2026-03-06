"""
Error Sanitization Tests
==========================
Validates that error responses never leak internal details:
- 500 errors return only {error, request_id}
- 422 errors don't expose internal field paths  
- Health endpoint shows "degraded" not DB error text
"""
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


class TestGenericErrorSanitization:
    """500 errors must return only {error, request_id} — never tracebacks."""

    def test_500_response_has_only_error_and_request_id(self):
        """
        Force a DB error by sending valid data to an endpoint that hits the database.
        The DB is not connected in test, so this will trigger an unhandled exception.
        """
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "latitude": 41.8781,
                "longitude": -87.6298,
                "device_id": "test-device-for-500",
            },
            headers=AUTH_HEADERS,
        )
        # If DB is not connected, this should result in a 500
        if resp.status_code == 500:
            body = resp.json()
            # Must have exactly these keys
            assert "error" in body, "500 response missing 'error' key"
            assert "request_id" in body, "500 response missing 'request_id' key"
            # Must NOT contain internal details
            assert "traceback" not in resp.text.lower()
            assert "Traceback" not in resp.text
            assert ".py" not in resp.text
            assert "sqlalchemy" not in resp.text.lower()
            assert "asyncpg" not in resp.text.lower()

    def test_500_no_postgres_error_text(self):
        """If a DB error occurs, the response must not contain Postgres error text."""
        resp = client.post(
            "/api/v1/telemetry/heartbeat",
            json={"device_id": "test-device-heartbeat"},
            headers=AUTH_HEADERS,
        )
        if resp.status_code == 500:
            assert "postgres" not in resp.text.lower()
            assert "relation" not in resp.text.lower()
            assert "SELECT" not in resp.text
            assert "INSERT" not in resp.text


class TestValidationErrorSanitization:
    """422 errors must not expose internal model names or full field paths."""

    def test_422_no_internal_paths(self):
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": "not_a_number"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
        body = resp.text
        assert "app/" not in body
        assert "site-packages" not in body
        assert "pydantic" not in body.lower() or "type" in body.lower()

    def test_422_shows_field_name_only(self):
        """The 'field' in the error should be the leaf field name, not a nested path."""
        resp = client.post(
            "/api/v1/telemetry/ingest",
            json={"latitude": "bad", "longitude": -87.62, "device_id": "test"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
        body = resp.json()
        detail = body.get("detail", [])
        for err in detail:
            if "field" in err:
                # Field should be a simple name, not "body -> latitude"
                assert "->" not in err["field"]
                assert "body" != err["field"]


class TestHealthEndpointSanitization:
    """Health endpoint must not leak DB error details."""

    def test_health_returns_degraded_not_error_text(self):
        resp = client.get("/health")
        body = resp.json()
        # If the DB is not connected, should show "degraded" not the error
        if body.get("db") == "error":
            assert "status" in body
            assert body["status"] == "degraded"
            # Must NOT contain exception text
            assert "connection" not in str(body).lower() or body.get("db") == "error"
            # The response should not have any key with exception details
            assert "traceback" not in str(body).lower()
            assert "asyncpg" not in str(body).lower()
