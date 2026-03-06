"""
Startup Tests
===============
Validates that the application refuses to start without required secrets
in production mode.
"""
import os
import pytest


class TestSecretsLoaderProduction:
    """Verify secrets_loader raises RuntimeError in production without secrets."""

    def test_missing_jwt_secret_in_production_raises(self):
        """Application must refuse to start if JWT_SECRET_KEY is missing in production."""
        from app.core.secrets_loader import _secrets, _SECRET_MAP

        # Save original state
        original_env = os.environ.get("ENVIRONMENT")
        original_jwt = os.environ.get("JWT_SECRET_KEY")

        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ.pop("JWT_SECRET_KEY", None)
            os.environ.pop("GCP_PROJECT_ID", None)  # No GCP fallback

            # Re-import and reset to force re-evaluation
            import importlib
            import app.core.secrets_loader as sl
            sl._secrets.clear()
            sl._ENV = "production"
            sl._GCP_PROJECT = ""

            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
                sl.load_secrets()
        finally:
            # Restore original state
            if original_env is not None:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if original_jwt is not None:
                os.environ["JWT_SECRET_KEY"] = original_jwt

    def test_missing_pgcrypto_key_in_production_raises(self):
        """Application must refuse to start if PGCRYPTO_KEY is missing in production."""
        original_env = os.environ.get("ENVIRONMENT")
        original_key = os.environ.get("PGCRYPTO_KEY")
        original_jwt = os.environ.get("JWT_SECRET_KEY")

        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ["JWT_SECRET_KEY"] = "test-key-for-this-test"
            os.environ.pop("PGCRYPTO_KEY", None)
            os.environ.pop("GCP_PROJECT_ID", None)

            import app.core.secrets_loader as sl
            sl._secrets.clear()
            sl._ENV = "production"
            sl._GCP_PROJECT = ""

            with pytest.raises(RuntimeError, match="PGCRYPTO_KEY"):
                sl.load_secrets()
        finally:
            if original_env is not None:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if original_key is not None:
                os.environ["PGCRYPTO_KEY"] = original_key
            else:
                os.environ.pop("PGCRYPTO_KEY", None)
            if original_jwt is not None:
                os.environ["JWT_SECRET_KEY"] = original_jwt
            else:
                os.environ.pop("JWT_SECRET_KEY", None)


class TestSecretsLoaderDevelopment:
    """In development mode, missing secrets should use dev defaults (with warning)."""

    def test_dev_defaults_used_without_env_vars(self):
        """In dev mode, missing secrets should succeed with defaults."""
        original_env = os.environ.get("ENVIRONMENT")
        original_jwt = os.environ.get("JWT_SECRET_KEY")
        original_pg = os.environ.get("PGCRYPTO_KEY")

        try:
            os.environ["ENVIRONMENT"] = "development"
            os.environ.pop("JWT_SECRET_KEY", None)
            os.environ.pop("PGCRYPTO_KEY", None)
            os.environ.pop("GCP_PROJECT_ID", None)

            import app.core.secrets_loader as sl
            sl._secrets.clear()
            sl._ENV = "development"
            sl._GCP_PROJECT = ""

            result = sl.load_secrets()
            assert "JWT_SECRET_KEY" in result
            assert "PGCRYPTO_KEY" in result
            assert result["JWT_SECRET_KEY"].startswith("DEV_ONLY")
        finally:
            if original_env is not None:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if original_jwt is not None:
                os.environ["JWT_SECRET_KEY"] = original_jwt
            if original_pg is not None:
                os.environ["PGCRYPTO_KEY"] = original_pg
