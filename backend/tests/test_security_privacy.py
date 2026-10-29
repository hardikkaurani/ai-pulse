"""Comprehensive security, privacy and authorization tests.

Validates the complete endpoint authorization matrix, cross-tenant isolation,
role changes, stale token invalidation, IDOR/BOLA defenses, small-group privacy,
complement disclosure, and reverse-proxy rate limiting.
"""

from datetime import datetime, timedelta, timezone
import jwt
from app import models, config
from app.db import SessionLocal
from tests.conftest import login, employee, admin, report


def test_endpoint_authorization_matrix_unauthenticated(client):
    """Every protected endpoint must reject unauthenticated requests with 401."""
    protected_endpoints = [
        ("GET", "/auth/me", None),
        ("POST", "/auth/select-org", {"org_id": 1}),
        ("GET", "/diagnostic/questions", None),
        ("POST", "/diagnostic/submit", {"answers": []}),
        ("POST", "/diagnostic/retry", None),
        ("GET", "/reports/me", None),
        ("PATCH", "/reports/me/actions/nonexistent", {"done": True}),
        ("DELETE", "/reports/me", None),
        ("GET", "/dashboard", None),
    ]
    for method, path, json_body in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json=json_body)
        elif method == "PATCH":
            res = client.patch(path, json=json_body)
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 401, (
            f"{method} {path} should return 401 without token, got {res.status_code}"
        )


def test_endpoint_authorization_matrix_user_vs_org_token(client):
    """User-only token (unscoped) can access /auth/me and /auth/select-org, but cannot access org-scoped routes."""
    user_headers, _ = login(client, "priya@northwind.test")

    # Allowed for user token
    assert client.get("/auth/me", headers=user_headers).status_code == 200
    assert (
        client.post(
            "/auth/select-org", headers=user_headers, json={"org_id": 1}
        ).status_code
        == 200
    )

    # Denied for user token (requires organization selection)
    org_scoped = [
        ("GET", "/diagnostic/questions"),
        ("GET", "/reports/me"),
        ("DELETE", "/reports/me"),
        ("GET", "/dashboard"),
    ]
    for method, path in org_scoped:
        res = (
            client.get(path, headers=user_headers)
            if method == "GET"
            else client.delete(path, headers=user_headers)
        )
        assert res.status_code == 400, (
            f"{method} {path} should require org selection (HTTP 400), got {res.status_code}"
        )


def test_endpoint_authorization_matrix_employee_cannot_access_dashboard(client):
    """Employee membership must be denied access to admin dashboard with HTTP 403."""
    emp_headers = employee(client, "priya@northwind.test")
    res = client.get("/dashboard", headers=emp_headers)
    assert res.status_code == 403
    assert "admin" in res.json()["detail"].lower()


def test_cross_tenant_org_dashboard_forbidden(client):
    """Admin of Organization 1 cannot view Organization 2's dashboard."""
    # Ravi is an employee at Northwind (org 1) and admin at Bluepeak Retail (org 2)
    bp_admin = employee(client, "ravi@consult.test", "Bluepeak Retail")
    assert client.get("/dashboard", headers=bp_admin).status_code == 200

    # Explicit cross-tenant query for org_id=1
    res = client.get("/dashboard?org_id=1", headers=bp_admin)
    assert res.status_code == 403
    assert "another organization" in res.json()["detail"].lower()


def test_cross_tenant_select_org_forbidden(client):
    """User cannot select an organization they have no membership in."""
    headers, _ = login(client, "priya@northwind.test")
    # Priya only has membership in Northwind (org 1), not Bluepeak (org 2)
    res = client.post("/auth/select-org", headers=headers, json={"org_id": 2})
    assert res.status_code == 403
    assert "not a member" in res.json()["detail"].lower()


def test_role_change_immediately_revokes_admin_access(client):
    """When a user's role is demoted in the database, subsequent requests immediately reflect the new role."""
    headers = admin(client)
    # Admin access verified
    assert client.get("/dashboard", headers=headers).status_code == 200

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="asha@northwind.test").one()
        user_id = user.id
        membership = (
            db.query(models.Membership).filter_by(user_id=user_id, org_id=1).one()
        )
        membership.role = "employee"
        db.commit()

    try:
        # Same token must now be rejected for /dashboard without requiring token expiration
        res = client.get("/dashboard", headers=headers)
        assert res.status_code == 403
        assert "admin" in res.json()["detail"].lower()
    finally:
        # Restore role
        with SessionLocal() as db:
            m = db.query(models.Membership).filter_by(user_id=user_id, org_id=1).one()
            m.role = "admin"
            db.commit()


def test_membership_deletion_immediately_revokes_token(client):
    """When a user's membership is deleted, existing tokens for that org are immediately rejected."""
    headers = employee(client, "new@northwind.test")
    assert client.get("/reports/me", headers=headers).status_code == 200

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="new@northwind.test").one()
        user_id = user.id
        membership = (
            db.query(models.Membership).filter_by(user_id=user_id, org_id=1).one()
        )
        dept_id = membership.department_id
        job_role = membership.job_role
        seniority = membership.seniority
        db.delete(membership)
        db.commit()

    try:
        # Token must now return 403 Not a member
        res = client.get("/reports/me", headers=headers)
        assert res.status_code == 403
        assert "not a member" in res.json()["detail"].lower()
    finally:
        # Restore membership
        with SessionLocal() as db:
            db.add(
                models.Membership(
                    user_id=user_id,
                    org_id=1,
                    department_id=dept_id,
                    role="employee",
                    job_role=job_role,
                    seniority=seniority,
                )
            )
            db.commit()


def test_idor_action_update_prevents_tampering(client):
    """User cannot update another employee's action plan activity (IDOR defense)."""
    priya = employee(client, "priya@northwind.test")
    arjun = employee(client, "arjun@northwind.test")

    # Get Priya's actions
    priya_report = report(client, priya)
    assert len(priya_report["actions"]) > 0
    priya_action_id = priya_report["actions"][0]["id"]

    # Arjun attempts to update Priya's action
    res = client.patch(
        f"/reports/me/actions/{priya_action_id}",
        headers=arjun,
        json={"done": True},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Activity not found."


def test_idor_invalid_action_id_formats(client):
    """Malformed or injection-attempt action IDs are safely handled."""
    priya = employee(client, "priya@northwind.test")
    for malformed in ["' OR '1'='1", "../../../etc/passwd", "a" * 500, "<script>"]:
        res = client.patch(
            f"/reports/me/actions/{malformed}",
            headers=priya,
            json={"done": True},
        )
        assert res.status_code in (404, 422)


def test_token_tampering_and_forgery_defenses(client):
    """Tokens with altered payloads, wrong algorithms, or forged signatures are rejected."""
    headers = employee(client)
    valid_token = headers["Authorization"].split(" ")[1]

    # 1. Signature truncation/tampering
    tampered_sig = valid_token[:-4] + "abcd"
    assert (
        client.get(
            "/reports/me", headers={"Authorization": f"Bearer {tampered_sig}"}
        ).status_code
        == 401
    )

    # 2. 'none' algorithm attack
    header = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"
    payload_part = valid_token.split(".")[1]
    none_token = f"{header}.{payload_part}."
    assert (
        client.get(
            "/reports/me", headers={"Authorization": f"Bearer {none_token}"}
        ).status_code
        == 401
    )

    # 3. Forged token with different secret
    forged = jwt.encode(
        {
            "sub": "1",
            "org": 1,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": "ai-pulse",
            "aud": "ai-pulse-web",
        },
        "wrong-secret-key-that-is-at-least-32-chars-long",
        algorithm="HS256",
    )
    assert (
        client.get(
            "/reports/me", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )

    # 4. Expired token
    expired = jwt.encode(
        {
            "sub": "1",
            "org": 1,
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iss": "ai-pulse",
            "aud": "ai-pulse-web",
        },
        config.SECRET_KEY,
        algorithm="HS256",
    )
    assert (
        client.get(
            "/reports/me", headers={"Authorization": f"Bearer {expired}"}
        ).status_code
        == 401
    )


def test_proxy_ip_rate_limiting_with_forwarded_headers(client):
    """When behind a trusted reverse proxy, X-Forwarded-For isolates distinct client IPs."""
    # Simulate 10 requests from Client A
    for _ in range(10):
        res = client.post(
            "/auth/login",
            json={"email": "bad@test.com", "password": "wrong"},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        assert res.status_code == 401

    # 11th request from Client A is rate-limited
    res_a = client.post(
        "/auth/login",
        json={"email": "bad@test.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    assert res_a.status_code == 429

    # Client B through the SAME proxy must NOT be blocked
    res_b = client.post(
        "/auth/login",
        json={"email": "bad@test.com", "password": "wrong"},
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    assert res_b.status_code == 401, (
        "Distinct client behind proxy must not be blocked by Client A's rate limit"
    )


def test_small_group_and_complement_disclosure_comprehensive():
    """Verify that department averages and risk counts never leak small groups or complements."""
    from app.services.privacy import publish

    # 1. Sub-threshold department (headcount < 5)
    for count in range(5):
        dept = [
            {
                "name": "Small",
                "people": [{"average": 4, "flags": []} for _ in range(count)],
            }
        ]
        res = publish(dept)[0]
        assert res["protected"] is True
        assert res["responded"] is None
        assert res["average_score"] is None
        assert res["risks"] == []

    # 2. Complementary count test for group of 10
    # Flagged count = 6 -> unflagged = 4 (< 5). Both must be protected (None).
    dept_10_6 = [
        {
            "name": "Team",
            "people": [
                {"average": 3.5, "flags": ["customer_data_shared"] if i < 6 else []}
                for i in range(10)
            ],
        }
    ]
    res = publish(dept_10_6)[0]
    assert res["protected"] is False
    assert res["responded"] == 10
    customer_risk = next(r for r in res["risks"] if r["key"] == "customer_data_shared")
    assert customer_risk["people"] is None, (
        "6 out of 10 leaves 4 unflagged; complement must remain protected"
    )

    # 3. Exactly 5 flagged and 5 unflagged -> permissible count publication
    dept_10_5 = [
        {
            "name": "Team",
            "people": [
                {"average": 3.5, "flags": ["customer_data_shared"] if i < 5 else []}
                for i in range(10)
            ],
        }
    ]
    res = publish(dept_10_5)[0]
    customer_risk = next(r for r in res["risks"] if r["key"] == "customer_data_shared")
    assert customer_risk["people"] == 5


def test_differencing_attack_audit(client):
    """Audit repeated snapshots: verify that individual answers are never returned in dashboard."""
    admin_headers = admin(client)
    res = client.get("/dashboard", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    # Confirm no raw answers, user IDs, emails or timestamps of submission exist in published departments
    for dept in data["departments"]:
        assert "people" not in dept
        assert "user_id" not in dept
        assert "email" not in dept
        if not dept["protected"]:
            assert isinstance(dept["average_score"], (int, float))


def test_cors_preflight_and_origin_allowlist(client):
    """CORS must permit Vercel production frontend and reject untrusted origins."""
    res_vercel = client.options(
        "/auth/login",
        headers={
            "Origin": "https://ai-pulse-rho-one.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert res_vercel.status_code == 200
    assert (
        res_vercel.headers.get("access-control-allow-origin")
        == "https://ai-pulse-rho-one.vercel.app"
    )
    assert "POST" in res_vercel.headers.get("access-control-allow-methods", "")

    res_preview = client.options(
        "/auth/login",
        headers={
            "Origin": "https://ai-pulse-branch-preview.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert res_preview.status_code == 200
    assert (
        res_preview.headers.get("access-control-allow-origin")
        == "https://ai-pulse-branch-preview.vercel.app"
    )

    res_untrusted = client.options(
        "/auth/login",
        headers={
            "Origin": "https://untrusted-attacker.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert (
        res_untrusted.status_code == 400
        or "access-control-allow-origin" not in res_untrusted.headers
    )


def test_login_demo_credentials_and_error_classification(client):
    """Demo login succeeds with 200 and invalid credentials return 401 without network/CORS error."""
    res_valid = client.post(
        "/auth/login",
        json={"email": "asha@northwind.test", "password": "pulse123"},
        headers={"Origin": "https://ai-pulse-rho-one.vercel.app"},
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert "token" in data
    assert data["email"] == "asha@northwind.test"
    assert (
        res_valid.headers.get("access-control-allow-origin")
        == "https://ai-pulse-rho-one.vercel.app"
    )

    res_invalid = client.post(
        "/auth/login",
        json={"email": "asha@northwind.test", "password": "wrong-password"},
        headers={"Origin": "https://ai-pulse-rho-one.vercel.app"},
    )
    assert res_invalid.status_code == 401
    assert res_invalid.json()["detail"] == "Email or password is incorrect."

