import pytest
from app.db import SessionLocal
from app import models
from app.services.questions import questions_for
from tests.conftest import login


def _setup_org_with_members(org_name, dept_name, count, role="employee", job_role="support", seniority="junior"):
    """Creates an organization, department, and N members, returning integer IDs."""
    db = SessionLocal()
    org = models.Organization(name=org_name)
    db.add(org)
    db.flush()

    dept = models.Department(org_id=org.id, name=dept_name)
    db.add(dept)
    db.flush()

    member_ids = []
    for i in range(count):
        user = models.User(name=f"User {i} {dept_name}", email=f"user_{i}_{dept_name.lower().replace(' ', '_')}@test.com", password_hash="dummy")
        db.add(user)
        db.flush()
        m = models.Membership(
            user_id=user.id,
            org_id=org.id,
            department_id=dept.id,
            role=role,
            job_role=job_role,
            seniority=seniority,
        )
        db.add(m)
        db.flush()
        member_ids.append(m.id)

    # Also add an admin user to the org so we can log in and view dashboard
    from app.auth import hash_password
    admin_user = models.User(name=f"Admin {org_name}", email=f"admin_{org.id}@test.com", password_hash=hash_password("pulse123"))
    db.add(admin_user)
    db.flush()
    admin_m = models.Membership(
        user_id=admin_user.id,
        org_id=org.id,
        department_id=None,
        role="admin",
        job_role="manager",
        seniority="lead",
    )
    db.add(admin_m)
    db.commit()

    org_id = org.id
    dept_id = dept.id
    admin_email = admin_user.email
    db.close()
    return org_id, dept_id, admin_email, member_ids


def _complete_diagnostic_for_member(membership_id, job_role="support", seniority="junior", score=4.0, flags=None):
    """Adds a complete diagnostic submission (all expected questions) for a member."""
    db = SessionLocal()
    qs = questions_for(job_role, seniority)
    for q in qs:
        resp = models.Response(
            membership_id=membership_id,
            question_id=q["id"],
            answer="Detailed answer test",
            score=score,
            reason="Good answer",
            flags=flags or [],
        )
        db.add(resp)
    db.commit()
    db.close()


def _partial_diagnostic_for_member(membership_id, job_role="support", seniority="junior", score=3.0, flags=None):
    """Adds an incomplete diagnostic submission (only subset of questions)."""
    db = SessionLocal()
    qs = questions_for(job_role, seniority)
    # Only answer the first question
    if qs:
        resp = models.Response(
            membership_id=membership_id,
            question_id=qs[0]["id"],
            answer="Partial answer",
            score=score,
            reason="Partial",
            flags=flags or [],
        )
        db.add(resp)
    db.commit()
    db.close()


def test_department_zero_completed_employees(client):
    """Scenario 1: Department with zero completed employees is suppressed."""
    org_id, _, admin_email, _ = _setup_org_with_members("Org Zero", "Empty Dept", count=6)
    headers, _ = login(client, admin_email, "Org Zero")

    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    depts = [d["department"] for d in r.json()["departments"]]
    assert "Empty Dept" not in depts


def test_departments_one_to_four_completed_are_suppressed(client):
    """Scenario 2: Departments with 1, 2, 3, or 4 completed employees are suppressed individually."""
    for count in (1, 2, 3, 4):
        org_id, dept_id, admin_email, member_ids = _setup_org_with_members(f"Org {count}", f"Dept {count}", count=6)
        # Complete diagnostic for exactly 'count' members
        for i in range(count):
            _complete_diagnostic_for_member(member_ids[i], score=3.5)

        headers, _ = login(client, admin_email, f"Org {count}")
        r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
        assert r.status_code == 200
        depts = [d["department"] for d in r.json()["departments"]]
        # Must not appear individually
        assert f"Dept {count}" not in depts


def test_department_exactly_five_completed_appears(client):
    """Scenario 3: Department with exactly 5 completed employees satisfies threshold and appears."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Five", "Five Dept", count=7)
    for i in range(5):
        _complete_diagnostic_for_member(member_ids[i], score=4.0)

    headers, _ = login(client, admin_email, "Org Five")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    dept_map = {d["department"]: d for d in r.json()["departments"]}
    assert "Five Dept" in dept_map
    assert dept_map["Five Dept"]["responded"] == 5
    assert dept_map["Five Dept"]["average_score"] == 4.0
    assert dept_map["Five Dept"]["level"] == "Leader"


def test_department_more_than_five_completed_appears(client):
    """Scenario 4: Department with more than 5 completed employees (7) appears with correct average."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Seven", "Seven Dept", count=8)
    # 7 completed with alternating scores 3.0 and 5.0 (avg: 4 * 3.0 + 3 * 5.0 = 27 / 7 = 3.86)
    for i in range(7):
        score = 3.0 if i % 2 == 0 else 5.0
        _complete_diagnostic_for_member(member_ids[i], score=score)

    headers, _ = login(client, admin_email, "Org Seven")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    dept_map = {d["department"]: d for d in r.json()["departments"]}
    assert "Seven Dept" in dept_map
    assert dept_map["Seven Dept"]["responded"] == 7
    expected_avg = round((4 * 3.0 + 3 * 5.0) / 7, 2)
    assert dept_map["Seven Dept"]["average_score"] == expected_avg


def test_partial_versus_completed_diagnostics(client):
    """Scenario 5: Partial submissions do not count toward the completion threshold."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Partial", "Partial Dept", count=8)
    # 3 completed, 3 partial (total responded rows exist for 6, but only 3 are complete)
    for i in range(3):
        _complete_diagnostic_for_member(member_ids[i], score=4.0)
    for i in range(3, 6):
        _partial_diagnostic_for_member(member_ids[i], score=2.0)

    headers, _ = login(client, admin_email, "Org Partial")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    depts = [d["department"] for d in r.json()["departments"]]
    # Since only 3 completed, department is suppressed
    assert "Partial Dept" not in depts


def test_multiple_response_rows_do_not_inflate_weight(client):
    """Scenario 6: Duplicate responses for one employee do not count twice in headcount or score weighting."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Dups", "Dup Dept", count=6)

    # 5 members complete diagnostic: 4 members have score 2.0, 1 member completes twice with score 4.0
    for i in range(4):
        _complete_diagnostic_for_member(member_ids[i], score=2.0)

    # 5th member submits diagnostic twice
    _complete_diagnostic_for_member(member_ids[4], score=4.0)
    _complete_diagnostic_for_member(member_ids[4], score=4.0)

    headers, _ = login(client, admin_email, "Org Dups")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    dept_map = {d["department"]: d for d in r.json()["departments"]}
    assert "Dup Dept" in dept_map
    # Responded count must be 5 (distinct completed employees)
    assert dept_map["Dup Dept"]["responded"] == 5
    # Department mean: (4 * 2.0 + 1 * 4.0) / 5 = 12 / 5 = 2.4
    assert dept_map["Dup Dept"]["average_score"] == 2.4


def test_null_or_unscored_responses_do_not_qualify(client):
    """Scenario 7: Responses with null/missing score do not count toward completion."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Unscored", "Unscored Dept", count=6)

    # 4 complete with score, 5th has one question with score=None
    for i in range(4):
        _complete_diagnostic_for_member(member_ids[i], score=4.0)

    # 5th member has unscored answers
    db = SessionLocal()
    qs = questions_for("support", "junior")
    for q in qs:
        resp = models.Response(
            membership_id=member_ids[4],
            question_id=q["id"],
            answer="Unscored text",
            score=None,
            reason=None,
            flags=[],
        )
        db.add(resp)
    db.commit()
    db.close()

    headers, _ = login(client, admin_email, "Org Unscored")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    depts = [d["department"] for d in r.json()["departments"]]
    # 5th member is incomplete due to null scores, so only 4 completed -> suppressed!
    assert "Unscored Dept" not in depts


def test_risk_flags_from_suppressed_departments_do_not_leak(client):
    """Scenario 8: Risk flags from small/suppressed departments do not appear in company-wide top_risks."""
    db = SessionLocal()
    from app.auth import hash_password
    org = models.Organization(name="Org Risk Isolation")
    db.add(org)
    db.flush()

    d_large = models.Department(org_id=org.id, name="Safe Large Dept")
    d_small = models.Department(org_id=org.id, name="Small Leaky Dept")
    db.add_all([d_large, d_small])
    db.flush()

    admin_u = models.User(name="Risk Admin", email="risk_admin@test.com", password_hash=hash_password("pulse123"))
    db.add(admin_u)
    db.flush()
    db.add(models.Membership(user_id=admin_u.id, org_id=org.id, role="admin", job_role="manager", seniority="lead"))

    # 5 members in large dept
    large_mem_ids = []
    for i in range(5):
        u = models.User(name=f"Large {i}", email=f"large_{i}@test.com", password_hash="dummy")
        db.add(u)
        db.flush()
        m = models.Membership(user_id=u.id, org_id=org.id, department_id=d_large.id, role="employee", job_role="support", seniority="junior")
        db.add(m)
        db.flush()
        large_mem_ids.append(m.id)

    # 1 member in small dept
    small_u = models.User(name="Small Lone", email="small_lone@test.com", password_hash="dummy")
    db.add(small_u)
    db.flush()
    small_m = models.Membership(user_id=small_u.id, org_id=org.id, department_id=d_small.id, role="employee", job_role="support", seniority="junior")
    db.add(small_m)
    db.flush()
    small_mem_id = small_m.id
    org_id = org.id
    db.commit()
    db.close()

    # Complete diagnostics
    for mid in large_mem_ids:
        _complete_diagnostic_for_member(mid, score=3.0, flags=["unreviewed_output"])
    # Small member has the sensitive flag
    _complete_diagnostic_for_member(small_mem_id, score=2.0, flags=["customer_data_shared"])

    headers, _ = login(client, "risk_admin@test.com", "Org Risk Isolation")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200

    data = r.json()
    dept_names = [d["department"] for d in data["departments"]]
    assert "Safe Large Dept" in dept_names
    assert "Small Leaky Dept" not in dept_names

    # Check top_risks: "customer_data_shared" MUST NOT BE IN TOP RISKS!
    risk_names = [item[0] for item in data["top_risks"]]
    assert "unreviewed_output" in risk_names
    assert "customer_data_shared" not in risk_names


def test_other_teams_grouping_when_combined_satisfies_threshold(client):
    """Scenario 9: Multiple small departments aggregate into 'Other teams' when aggregate >= 5."""
    db = SessionLocal()
    from app.auth import hash_password
    org = models.Organization(name="Org Other Teams")
    db.add(org)
    db.flush()

    d1 = models.Department(org_id=org.id, name="Small Team A")
    d2 = models.Department(org_id=org.id, name="Small Team B")
    db.add_all([d1, d2])
    db.flush()

    admin_u = models.User(name="Other Admin", email="other_admin@test.com", password_hash=hash_password("pulse123"))
    db.add(admin_u)
    db.flush()
    db.add(models.Membership(user_id=admin_u.id, org_id=org.id, role="admin", job_role="manager", seniority="lead"))

    # Team A has 3 completed members (avg score 2.0)
    mems_a_ids = []
    for i in range(3):
        u = models.User(name=f"A {i}", email=f"a_{i}@test.com", password_hash="dummy")
        db.add(u)
        db.flush()
        m = models.Membership(user_id=u.id, org_id=org.id, department_id=d1.id, role="employee", job_role="support", seniority="junior")
        db.add(m)
        db.flush()
        mems_a_ids.append(m.id)

    # Team B has 3 completed members (avg score 4.0)
    mems_b_ids = []
    for i in range(3):
        u = models.User(name=f"B {i}", email=f"b_{i}@test.com", password_hash="dummy")
        db.add(u)
        db.flush()
        m = models.Membership(user_id=u.id, org_id=org.id, department_id=d2.id, role="employee", job_role="support", seniority="junior")
        db.add(m)
        db.flush()
        mems_b_ids.append(m.id)

    org_id = org.id
    db.commit()
    db.close()

    for mid in mems_a_ids:
        _complete_diagnostic_for_member(mid, score=2.0)
    for mid in mems_b_ids:
        _complete_diagnostic_for_member(mid, score=4.0)

    headers, _ = login(client, "other_admin@test.com", "Org Other Teams")
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200

    dept_map = {d["department"]: d for d in r.json()["departments"]}
    # Neither Small Team A nor Small Team B appears individually
    assert "Small Team A" not in dept_map
    assert "Small Team B" not in dept_map

    # "Other teams" aggregate appears because 3 + 3 = 6 >= 5 across >= 2 teams
    assert "Other teams" in dept_map
    assert dept_map["Other teams"]["responded"] == 6
    # Average: (3 * 2.0 + 3 * 4.0) / 6 = 18 / 6 = 3.0
    assert dept_map["Other teams"]["average_score"] == 3.0


def test_dashboard_reflects_immediate_deletion(client):
    """Scenario 13: Dashboard immediately recalculates when a response is deleted from database."""
    org_id, dept_id, admin_email, member_ids = _setup_org_with_members("Org Immediate", "Live Dept", count=6)
    # 5 members complete
    for i in range(5):
        _complete_diagnostic_for_member(member_ids[i], score=4.0)

    headers, _ = login(client, admin_email, "Org Immediate")
    r1 = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r1.status_code == 200
    depts1 = [d["department"] for d in r1.json()["departments"]]
    assert "Live Dept" in depts1

    # Remove all responses for 5th member
    db = SessionLocal()
    db.query(models.Response).filter_by(membership_id=member_ids[4]).delete()
    db.commit()
    db.close()

    # Query dashboard again without restarting: department count drops to 4, so it is suppressed!
    r2 = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r2.status_code == 200
    depts2 = [d["department"] for d in r2.json()["departments"]]
    assert "Live Dept" not in depts2
