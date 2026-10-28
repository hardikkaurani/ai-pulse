from app.db import SessionLocal
from app import models
from tests.conftest import login
from unittest.mock import patch


def test_authenticated_employee_can_delete_own_responses(client):
    """Scenario 1 & 2: Authenticated employee deletes their own diagnostic data."""
    # Vikram is in Northwind with 2 responses in seed data
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")

    # Confirm report shows responses before deletion
    rep_before = client.get("/reports/me", headers=headers)
    assert rep_before.status_code == 200
    assert rep_before.json()["answered"] > 0

    # Delete responses
    res = client.delete("/reports/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["deleted"] >= 2
    assert "deleted successfully" in data["message"]

    # Verify report endpoint now returns empty/unassessed state
    rep_after = client.get("/reports/me", headers=headers)
    assert rep_after.status_code == 200
    assert rep_after.json()["answered"] == 0
    assert rep_after.json()["average_score"] is None
    assert rep_after.json()["level"] == "Not assessed"
    assert rep_after.json()["risks"] == []


def test_other_employees_responses_remain_untouched(client):
    """Scenario 3: Deleting employee A's data does not affect employee B."""
    headers_vikram, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    headers_priya, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    # Priya has answers before deletion
    priya_before = client.get("/reports/me", headers=headers_priya).json()["answered"]
    assert priya_before > 0

    # Vikram deletes his answers
    del_res = client.delete("/reports/me", headers=headers_vikram)
    assert del_res.status_code == 200

    # Priya's answers still exist untouched
    priya_after = client.get("/reports/me", headers=headers_priya).json()["answered"]
    assert priya_after == priya_before


def test_cannot_delete_other_user_by_supplying_id(client):
    """Scenario 4: Endpoint does not accept or honor client-supplied membership or user IDs."""
    headers_priya, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    # Attempt to pass query parameters targeting Vikram's membership or user id
    res = client.delete("/reports/me?membership_id=2&user_id=2", headers=headers_priya)
    assert res.status_code == 200

    # Priya's own responses were deleted (target is strictly derived from token)
    priya_after = client.get("/reports/me", headers=headers_priya).json()["answered"]
    assert priya_after == 0

    # Vikram's responses remain completely intact
    headers_vikram, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    vikram_after = client.get("/reports/me", headers=headers_vikram).json()["answered"]
    assert vikram_after > 0


def test_multi_organization_isolation_on_deletion(client):
    """Scenario 5: Multi-org user deleting in Org A does not delete answers in Org B."""
    db = SessionLocal()
    # Find Ravi Kapoor's memberships in Northwind and Bluepeak
    ravi = db.query(models.User).filter_by(email="ravi@consult.test").first()
    mem_nw = db.query(models.Membership).filter_by(user_id=ravi.id, org_id=1).first()
    mem_bp = db.query(models.Membership).filter_by(user_id=ravi.id, org_id=2).first()

    # Seed answers for both memberships
    resp_nw = models.Response(membership_id=mem_nw.id, question_id="common-freq", answer="Daily", score=4.0, flags=[])
    resp_bp = models.Response(membership_id=mem_bp.id, question_id="common-freq", answer="Daily", score=4.0, flags=["unreviewed_output"])
    db.add_all([resp_nw, resp_bp])
    db.commit()
    db.close()

    # Log in as Ravi at Northwind Logistics
    headers_nw, _ = login(client, "ravi@consult.test", "Northwind Logistics")
    headers_bp, _ = login(client, "ravi@consult.test", "Bluepeak Retail")

    # Both show 1 answer
    assert client.get("/reports/me", headers=headers_nw).json()["answered"] == 1
    assert client.get("/reports/me", headers=headers_bp).json()["answered"] == 1

    # Delete answers in Northwind Logistics
    del_res = client.delete("/reports/me", headers=headers_nw)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] == 1

    # Northwind is now empty
    assert client.get("/reports/me", headers=headers_nw).json()["answered"] == 0

    # Bluepeak answers remain untouched!
    bp_report = client.get("/reports/me", headers=headers_bp).json()
    assert bp_report["answered"] == 1
    assert bp_report["risks"] == ["unreviewed_output"]


def test_repeated_deletion_is_idempotent(client):
    """Scenario 6: Repeated deletion requests succeed safely and leave no responses."""
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")

    # First deletion deletes answers
    res1 = client.delete("/reports/me", headers=headers)
    assert res1.status_code == 200
    assert res1.json()["deleted"] > 0

    # Second deletion is safe and returns deleted: 0
    res2 = client.delete("/reports/me", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["deleted"] == 0

    # Third deletion via diagnostic alias is also safe
    res3 = client.delete("/diagnostic/my-data", headers=headers)
    assert res3.status_code == 200
    assert res3.json()["deleted"] == 0


def test_dashboard_reflects_deletion_immediately(client):
    """Scenario 8 & 9: Dashboard aggregates and risk flags reflect deletion on the next request."""
    # Seed 5 completed members in a test department with flag "customer_data_shared"
    db = SessionLocal()
    from app.auth import hash_password
    org = models.Organization(name="Org Delete Dashboard")
    db.add(org)
    db.flush()

    dept = models.Department(org_id=org.id, name="Support Team")
    db.add(dept)
    db.flush()

    admin_u = models.User(name="Del Admin", email="del_admin@test.com", password_hash=hash_password("pulse123"))
    db.add(admin_u)
    db.flush()
    db.add(models.Membership(user_id=admin_u.id, org_id=org.id, role="admin", job_role="manager", seniority="lead"))

    member_emails = []
    member_ids = []
    for i in range(5):
        email = f"supp_{i}@test.com"
        u = models.User(name=f"Supp {i}", email=email, password_hash=hash_password("pulse123"))
        db.add(u)
        db.flush()
        m = models.Membership(user_id=u.id, org_id=org.id, department_id=dept.id, role="employee", job_role="support", seniority="junior")
        db.add(m)
        db.flush()
        member_emails.append(email)
        member_ids.append(m.id)
    org_id = org.id
    db.commit()
    db.close()

    from tests.test_dashboard_privacy import _complete_diagnostic_for_member
    for mid in member_ids:
        _complete_diagnostic_for_member(mid, score=4.0, flags=["customer_data_shared"])

    headers_admin, _ = login(client, "del_admin@test.com", "Org Delete Dashboard")

    # Initial check: 5 completed -> department appears, flag appears in top_risks
    d1 = client.get(f"/dashboard?org_id={org_id}", headers=headers_admin).json()
    assert any(d["department"] == "Support Team" for d in d1["departments"])
    assert any(r[0] == "customer_data_shared" for r in d1["top_risks"])

    # 5th employee logs in and deletes their diagnostic data
    headers_emp, _ = login(client, member_emails[4], "Org Delete Dashboard")
    del_res = client.delete("/reports/me", headers=headers_emp)
    assert del_res.status_code == 200

    # Immediate dashboard query: department count drops to 4 (< 5), so it is suppressed!
    d2 = client.get(f"/dashboard?org_id={org_id}", headers=headers_admin).json()
    assert not any(d["department"] == "Support Team" for d in d2["departments"])
    # And its risk flag is isolated and no longer leaked in top_risks!
    assert not any(r[0] == "customer_data_shared" for r in d2["top_risks"])


def test_unauthenticated_requests_cannot_delete(client):
    """Scenario 10: Unauthenticated request cannot delete data."""
    res1 = client.delete("/reports/me")
    assert res1.status_code == 401

    res2 = client.delete("/reports/me", headers={"Authorization": "Bearer invalid_token"})
    assert res2.status_code == 401

    res3 = client.delete("/diagnostic/my-data")
    assert res3.status_code == 401


def test_database_error_handling_and_transaction_rollback(client):
    """Scenario 11: Database failure rolls back transaction and returns HTTP 500 error."""
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")

    with patch.object(models.Response, "__table__") as mock_table:
        # Simulate a database failure during delete query execution
        with patch("sqlalchemy.orm.Query.delete", side_effect=Exception("Database lock/connection error")):
            res = client.delete("/reports/me", headers=headers)
            assert res.status_code == 500
            assert "Failed to delete" in res.json()["detail"]

    # Verify data was NOT partially deleted
    rep = client.get("/reports/me", headers=headers)
    assert rep.status_code == 200
    assert rep.json()["answered"] > 0
