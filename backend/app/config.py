"""Configuration fails closed; setup generates a local secret outside Git."""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if len(SECRET_KEY) < 32 or SECRET_KEY.startswith(("ai-pulse-dev", "pulse-7f")):
    raise RuntimeError(
        "Set a new SECRET_KEY of at least 32 characters. Run scripts/setup.py."
    )
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aipulse.db")
# Hosting providers supply either postgres:// or postgresql://. Select the
# installed Psycopg 3 driver explicitly while preserving credentials/options.
for prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix) :]
        break
AI_MODE = os.getenv("AI_MODE", "mock")
if AI_MODE not in {"mock", "live"}:
    raise RuntimeError("AI_MODE must be mock or live")
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
if AI_MODE == "live":
    url = urlparse(LLM_API_URL)
    if not LLM_MODEL or not url.hostname or url.scheme not in {"http", "https"}:
        raise RuntimeError(
            "Live mode requires a model and an HTTP(S) chat-completions URL"
        )
    if url.scheme != "https" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Remote model endpoints require HTTPS")
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://ai-pulse-rho-one.vercel.app",
]
if os.getenv("RENDER_EXTERNAL_URL"):
    ext = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if ext and ext not in DEFAULT_ORIGINS:
        DEFAULT_ORIGINS.append(ext)

_custom_cors = os.getenv("CORS_ORIGINS", "")
if _custom_cors:
    CORS_ORIGINS = [origin.strip() for origin in _custom_cors.split(",") if origin.strip()]
    for default_origin in DEFAULT_ORIGINS:
        if default_origin not in CORS_ORIGINS:
            CORS_ORIGINS.append(default_origin)
else:
    CORS_ORIGINS = DEFAULT_ORIGINS

SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() in {"1", "true", "yes"}
TOKEN_HOURS = 1
STATIC_DIR = os.getenv("STATIC_DIR", "")
MIN_GROUP_SIZE = 5
PROMPT_VERSION = "pulse-rubric-v3"
