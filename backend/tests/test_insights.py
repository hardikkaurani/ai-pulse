import json
from unittest.mock import patch, MagicMock
import pytest
from tests.conftest import login
from app import models
from app.db import SessionLocal
from app.services.questions import questions_for


def seed_department_cohort(db, org_id, dept_name, count, flags=None):
    """Helper to seed `count` completed employee diagnostics for a department."""
    dept = db.query(models.Department).filter_by(org_id=org_id, name=dept_name).first()
    if not dept:
        dept = models.Department(org_id=org_id, name=dept_name)
        db.add(dept)
        db.flush()

    members = []
    for i in range(count):
        email = f"emp_{dept_name.lower()}_{i}@northwind.test"
        u = db.query(models.User).filter_by(email=email).first()
        if not u:
            u = models.User(name=f"User {dept_name} {i}", email=email, password_hash="dummy")
            db.add(u)
            db.flush()

        m = db.query(models.Membership).filter_by(user_id=u.id, org_id=org_id).first()
        if not m:
            m = models.Membership(
                user_id=u.id,
                org_id=org_id,
                department_id=dept.id,
                role="employee",
                job_role="sales",
                seniority="junior",
            )
            db.add(m)
            db.flush()
        members.append(m)

        # Answer all expected questions to qualify as complete
        expected_qs = questions_for(m.job_role, m.seniority)
        for q in expected_qs:
            q_flags = flags if flags and q["id"] == "common-open" else []
            db.add(models.Response(
                membership_id=m.id,
                question_id=q["id"],
                answer="Testing response answer with enough text content",
                score=4,
                reason="Valid test response",
                flags=q_flags,
            ))
    db.commit()
    return dept


def test_employee_cannot_access_insights(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/insights", headers=headers)
    assert r.status_code == 403
    assert "Admins only" in r.json()["detail"]


def test_admin_cannot_access_other_org_insights(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/insights?org_id=2", headers=headers)
    assert r.status_code == 403
    assert "Cannot view another organization's insights" in r.json()["detail"]


def test_insights_suppresses_departments_below_threshold(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]

    # In baseline seed, Engineering only has 2 members (< 5 threshold)
    with SessionLocal() as db:
        eng_dept = db.query(models.Department).filter_by(org_id=org_id, name="Engineering").first()
        assert eng_dept is not None
        eng_id = eng_dept.id

    r = client.get(f"/insights?department_id={eng_id}", headers=headers)
    assert r.status_code == 403
    assert "suppressed for privacy" in r.json()["detail"]


def test_insights_qualifying_department_success(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]

    with SessionLocal() as db:
        # Seed 5 completed members for Support with customer_data_shared flag
        dept = seed_department_cohort(db, org_id, "Support", 5, flags=["customer_data_shared"])
        dept_id = dept.id

    r = client.get(f"/insights?department_id={dept_id}", headers=headers)
    assert r.status_code == 200
    res = r.json()

    assert res["department"] == "Support"
    assert "insights" in res
    assert len(res["insights"]) > 0

    first = res["insights"][0]
    assert "observed_pattern" in first
    assert "recommended_action" in first
    assert "reason" in first
    assert first["priority"] in ("high", "medium", "low")
    assert "customer data" in first["observed_pattern"].lower() or "customer" in first["recommended_action"].lower()


def test_insights_adversarial_check_does_not_leak_raw_data(client):
    """Verify that insights payloads never contain employee names, emails, raw text, or IDs."""
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]

    with SessionLocal() as db:
        seed_department_cohort(db, org_id, "Sales", 6, flags=["confidential_data_shared"])

    r = client.get("/insights", headers=headers)
    assert r.status_code == 200
    raw_text = r.text.lower()

    # Must NOT leak user emails or user names
    assert "emp_sales_" not in raw_text
    assert "@northwind.test" not in raw_text
    assert "testing response answer" not in raw_text
    assert "membership_id" not in raw_text


def test_insights_deterministic_mock_mode(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]

    with SessionLocal() as db:
        seed_department_cohort(db, org_id, "Support", 5, flags=["unreviewed_output"])

    r = client.get("/insights", headers=headers)
    assert r.status_code == 200
    res = r.json()
    assert res["source"] in ("mock", "rules")
    assert any("unreviewed" in str(ins).lower() or "peer-review" in str(ins).lower() for ins in res["insights"])


def test_insights_llm_failure_graceful_fallback(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]

    with SessionLocal() as db:
        seed_department_cohort(db, org_id, "Support", 5, flags=["policy_unaware"])

    # Simulate live AI mode with simulated LLM network failure
    with patch("app.services.insights_service.AI_MODE", "live"), \
         patch("app.services.insights_service.LLM_API_KEY", "test-key"), \
         patch("app.services.insights_service.LLM_API_URL", "https://api.openai.com/v1/chat/completions"), \
         patch("httpx.post", side_effect=Exception("Connection timed out")):

        r = client.get("/insights", headers=headers)
        assert r.status_code == 200
        res = r.json()
        assert res["source"] == "rules"
        assert len(res["insights"]) > 0
