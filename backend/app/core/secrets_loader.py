"""
Secrets Loader
================
Loads application secrets with the following priority:
  1. GCP Secret Manager (production)
  2. Environment variables (development)
  3. RuntimeError if neither is available in production

Called once during FastAPI lifespan startup — never per-request.
"""
import os
import logging

logger = logging.getLogger(__name__)

_ENV = os.getenv("ENVIRONMENT", "development")
_GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "")

# Cached secrets — populated by load_secrets()
_secrets: dict[str, str] = {}

# Map of secret names to their GCP Secret Manager IDs
_SECRET_MAP = {
    "JWT_SECRET_KEY": "jwt-secret-key",
    "PGCRYPTO_KEY": "pgcrypto-key",
    "MQTT_PASSWORD": "mqtt-password",
}


def _load_from_gcp(secret_id: str) -> str | None:
    """Load a single secret from GCP Secret Manager."""
    if not _GCP_PROJECT:
        return None
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{_GCP_PROJECT}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.warning(f"Could not load secret '{secret_id}' from GCP: {e}")
        return None


def load_secrets() -> dict[str, str]:
    """
    Load all required secrets. Called once at startup.
    Returns a dict of secret_name -> value.
    Raises RuntimeError in production if any required secret is missing.
    """
    global _secrets

    for secret_name, gcp_id in _SECRET_MAP.items():
        # Try GCP Secret Manager first
        value = _load_from_gcp(gcp_id)

        # Fall back to environment variable
        if not value:
            value = os.getenv(secret_name, "")

        if value:
            _secrets[secret_name] = value
        elif secret_name == "MQTT_PASSWORD":
            # MQTT password is optional (some brokers allow anonymous)
            _secrets[secret_name] = ""
        else:
            # JWT_SECRET_KEY and PGCRYPTO_KEY are required
            if _ENV == "production":
                raise RuntimeError(
                    f"{secret_name} must be set via GCP Secret Manager or environment variable in production"
                )
            # Dev-only defaults
            if secret_name == "JWT_SECRET_KEY":
                _secrets[secret_name] = "DEV_ONLY_CHANGE_ME_IN_PRODUCTION_256bit_key_abc123"
                logger.warning("Using development-only JWT_SECRET_KEY — DO NOT use in production")
            elif secret_name == "PGCRYPTO_KEY":
                _secrets[secret_name] = "DEV_ONLY_PGCRYPTO_SYMMETRIC_KEY"
                logger.warning("Using development-only PGCRYPTO_KEY — DO NOT use in production")

    logger.info("All application secrets loaded successfully")
    return _secrets


def get_secret(name: str) -> str:
    """Retrieve a loaded secret by name. Must call load_secrets() first."""
    if name not in _secrets:
        raise RuntimeError(f"Secret '{name}' not loaded. Call load_secrets() at startup.")
    return _secrets[name]
