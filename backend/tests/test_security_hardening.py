from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import jwt
import pytest
from tests.conftest import login
from app import models
from app.auth import hash_password, verify_password, make_token
from app.config import SECRET_KEY
from app.db import SessionLocal


def test_password_hashing_uses_bcrypt():
    """Verify that hash_password generates a valid bcrypt hash."""
    h = hash_password("SuperSecret123")
    assert h.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password("SuperSecret123", h)
    assert not verify_password("WrongPassword", h)


def test_password_verification_supports_legacy_sha256():
    """Verify that legacy unsalted SHA-256 hashes are verified correctly."""
    import hashlib
    legacy_hash = hashlib.sha256(b"pulse123").hexdigest()
    assert verify_password("pulse123", legacy_hash)
    assert not verify_password("wrong", legacy_hash)


def test_login_transparently_migrates_sha256_to_bcrypt(client):
    """When a user with a legacy SHA-256 hash logs in, their hash is migrated to bcrypt."""
    with SessionLocal() as db:
        # Create a user with a raw legacy sha256 hash
        import hashlib
        legacy = hashlib.sha256("legacy_pass_123".encode()).hexdigest()
        u = models.User(name="Legacy User", email="legacy@northwind.test", password_hash=legacy)
        db.add(u)
        db.commit()

    # Log in
    res = client.post("/auth/login", json={"email": "legacy@northwind.test", "password": "legacy_pass_123"})
    assert res.status_code == 200

    # Verify that the DB record was upgraded to bcrypt
    with SessionLocal() as db:
        u_after = db.query(models.User).filter_by(email="legacy@northwind.test").first()
        assert u_after.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
        assert verify_password("legacy_pass_123", u_after.password_hash)


def test_expired_token_is_rejected(client):
    """A JWT with an expired timestamp must be rejected with 401."""
    expired_payload = {
        "sub": "1",
        "org": 1,
        "type": "access",
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm="HS256")
    res = client.get("/reports/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "Token has expired" in res.json()["detail"]


def test_malformed_token_is_rejected(client):
    """Invalid tokens or tampered signatures must return 401."""
    res1 = client.get("/reports/me", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert res1.status_code == 401
    assert "Invalid token" in res1.json()["detail"]

    # Tampered signature
    valid_token = make_token(1, 1)
    tampered = valid_token[:-4] + "xxxx"
    res2 = client.get("/reports/me", headers={"Authorization": f"Bearer {tampered}"})
    assert res2.status_code == 401


def test_missing_authorization_header_rejected(client):
    res = client.get("/reports/me")
    assert res.status_code == 401
    assert "Missing token" in res.json()["detail"]


def test_cross_org_report_access_denied(client):
    """User who is only a member of Northwind Logistics cannot access Bluepeak Retail report."""
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    # Priya belongs to Northwind (org 1), attempt to access Bluepeak (org 2)
    res = client.get("/reports/me?org_id=2", headers=headers)
    assert res.status_code == 403
    assert "Not a member" in res.json()["detail"]


def test_cross_org_deletion_denied(client):
    """User cannot delete responses in an organization they do not belong to."""
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    res = client.delete("/reports/me?org_id=2", headers=headers)
    assert res.status_code == 403
    assert "Not a member" in res.json()["detail"]


def test_list_reports_scoped_to_user_memberships(client):
    """GET /reports returns only organizations where user has membership."""
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    res = client.get("/reports", headers=headers)
    assert res.status_code == 200
    org_names = {r["organization"] for r in res.json()}
    # Priya is only in Northwind
    assert "Northwind Logistics" in org_names
    assert "Bluepeak Retail" not in org_names


def test_production_seed_endpoint_forbidden(client):
    """In production environment, the /seed endpoint returns 403 Forbidden."""
    with patch("app.main.ENVIRONMENT", "production"):
        res = client.get("/seed")
        assert res.status_code == 403
        assert "disabled in production" in res.json()["detail"]
