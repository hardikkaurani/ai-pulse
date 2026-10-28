from tests.conftest import login
from app.db import engine


def test_login_lists_organizations(client):
    _, data = login(client, "ravi@consult.test")
    names = {o["org_name"] for o in data["organizations"]}
    assert names == {"Northwind Logistics", "Bluepeak Retail"}


def test_employee_sees_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    assert any(q["id"] == "sup-drafts" for q in r.json())


def test_admin_dashboard(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["organization"] == "Northwind Logistics"
    assert "departments" in r.json()
    # In initial seed data, all departments have < 5 completed employees,
    # so individual departments are suppressed to protect employee privacy
    assert len(r.json()["departments"]) == 0


def test_admin_cannot_see_other_org(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    # Accessing own org succeeds
    r = client.get("/dashboard?org_id=1", headers=headers)
    assert r.status_code == 200
    assert "departments" in r.json()

    # Accessing another org (Bluepeak Retail, org_id 2) is forbidden
    r_other = client.get("/dashboard?org_id=2", headers=headers)
    assert r_other.status_code == 403
    assert "Not authorized" in r_other.json()["detail"]


def test_employee_cannot_access_dashboard(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 403
    assert "Admins only" in r.json()["detail"]


def test_database_isolation_active(client):
    """Verify that test engine is isolated from development aipulse.db."""
    db_url = str(engine.url)
    assert "aipulse.db" not in db_url
    assert "aipulse_test_" in db_url


def test_select_org_authorized_membership(client):
    """A member can select an organization they belong to."""
    r = client.post("/auth/login", json={"email": "priya@northwind.test", "password": "pulse123"})
    assert r.status_code == 200
    data = r.json()
    token = data["token"]
    org_id = data["organizations"][0]["org_id"]

    sel = client.post(
        "/auth/select-org",
        json={"org_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sel.status_code == 200
    assert sel.json()["org_id"] == org_id
    assert "token" in sel.json()


def test_select_org_forbidden_for_non_member(client):
    """A user cannot select an organization they are not a member of."""
    # Priya Nair belongs ONLY to Northwind Logistics (org_id 1)
    r = client.post("/auth/login", json={"email": "priya@northwind.test", "password": "pulse123"})
    token = r.json()["token"]

    # Attempt to select Bluepeak Retail (org_id 2)
    sel = client.post(
        "/auth/select-org",
        json={"org_id": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sel.status_code == 403
    assert "Not a member" in sel.json()["detail"]


def test_select_org_nonexistent_id(client):
    """Attempting to select a nonexistent organization ID returns 403 Forbidden."""
    r = client.post("/auth/login", json={"email": "priya@northwind.test", "password": "pulse123"})
    token = r.json()["token"]

    sel = client.post(
        "/auth/select-org",
        json={"org_id": 99999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sel.status_code == 403
    assert "Not a member" in sel.json()["detail"]


def test_multi_org_user_can_select_both_orgs(client):
    """Multi-org user (Ravi) can successfully select either of his organizations."""
    r = client.post("/auth/login", json={"email": "ravi@consult.test", "password": "pulse123"})
    token = r.json()["token"]
    org_ids = [o["org_id"] for o in r.json()["organizations"]]
    assert len(org_ids) >= 2

    for oid in org_ids:
        sel = client.post(
            "/auth/select-org",
            json={"org_id": oid},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sel.status_code == 200
        assert sel.json()["org_id"] == oid
