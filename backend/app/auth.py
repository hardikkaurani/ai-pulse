import hashlib
import hmac
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .config import SECRET_KEY, TOKEN_HOURS
from .db import get_db
from . import models

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("nonexistent-user-timing-placeholder")


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    # Upgrade inherited hashes on successful login without losing existing accounts.
    if len(hashed) == 64 and all(c in "0123456789abcdef" for c in hashed):
        return hmac.compare_digest(
            hashlib.sha256(password.encode()).hexdigest(), hashed
        )
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False
    try:
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def make_token(user_id: int, org_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "org": org_id,
            "iat": now,
            "exp": now + timedelta(hours=TOKEN_HOURS),
            "iss": "ai-pulse",
            "aud": "ai-pulse-web",
        },
        SECRET_KEY,
        algorithm="HS256",
    )


def _decode(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in.")
    try:
        data = jwt.decode(
            authorization[7:],
            SECRET_KEY,
            algorithms=["HS256"],
            issuer="ai-pulse",
            audience="ai-pulse-web",
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        if not str(data["sub"]).isdigit() or int(data["sub"]) < 1:
            raise ValueError()
        if data.get("org") is not None and (
            type(data["org"]) is not int or data["org"] < 1
        ):
            raise ValueError()
        return data
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(
            401, "Your session expired or is invalid. Please sign in again."
        )


def current_user(
    authorization: str | None = Header(None), db: Session = Depends(get_db)
):
    user = db.get(models.User, int(_decode(authorization)["sub"]))
    if not user:
        raise HTTPException(401, "Please sign in again.")
    return user


def current_membership(
    authorization: str | None = Header(None), db: Session = Depends(get_db)
):
    data = _decode(authorization)
    if not data.get("org"):
        raise HTTPException(400, "Select an organization first.")
    member = (
        db.query(models.Membership)
        .filter_by(user_id=int(data["sub"]), org_id=data["org"])
        .first()
    )
    if not member:
        raise HTTPException(403, "You are not a member of this organization.")
    return member
