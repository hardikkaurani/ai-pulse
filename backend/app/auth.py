import hashlib
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_HOURS
from .db import get_db
from . import models


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt with standard salt rounds."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against a hash.

    Supports bcrypt hashes ($2b$, $2a$, $2y$) and maintains transparent
    fallback compatibility for legacy unsalted SHA-256 demo hashes.
    """
    if not hashed or not password:
        return False

    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    # Legacy SHA-256 verification fallback
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return legacy_hash == hashed


def make_token(user_id: int, org_id: int | None = None) -> str:
    """Creates a signed, time-bounded JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": org_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_HOURS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode(authorization: str | None) -> dict:
    """Decodes and cryptographically validates a Bearer JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    if "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token claims")

    return payload


def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.User:
    """Resolves and returns the authenticated user from the Bearer token."""
    data = _decode(authorization)
    try:
        user_id = int(data["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user identifier")

    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def current_membership(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> models.Membership:
    """Resolves the verified organization membership for the active session context."""
    data = _decode(authorization)
    if not data.get("org"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select an organization first")

    try:
        user_id = int(data["sub"])
        org_id = int(data["org"])
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid token claims")

    m = (
        db.query(models.Membership)
        .filter_by(user_id=user_id, org_id=org_id)
        .first()
    )
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    return m
