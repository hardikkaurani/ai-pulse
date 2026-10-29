import logging
import os

logger = logging.getLogger(__name__)

# Load .env if present
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower().strip()

# Secure default >= 32 characters for HMAC SHA-256 (RFC 7518) in development
DEFAULT_DEV_SECRET = "ai-pulse-development-secret-key-32-bytes-long"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_DEV_SECRET)

if ENVIRONMENT == "production":
    if SECRET_KEY in (DEFAULT_DEV_SECRET, "ai-pulse-dev-secret"):
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY must be explicitly set "
            "to a unique, high-entropy secret in production environments."
        )

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aipulse.db")
AI_MODE = os.getenv("AI_MODE", "mock").lower().strip()  # "mock" or "live"
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))
