import hashlib
from datetime import date, timedelta
import pytest
from app import models
from app.db import SessionLocal
from app.auth import hash_password, verify_password
from app.services import llm
from app.services.scoring import parse_result, ScoringUnavailable
from app.services.privacy import publish
from tests.conftest import login


def employee(client, email="priya@northwind.test", org="Northwind Logistics"):
    return login(client, email, org)[0]


def payload(
    client,
    headers,
    open_answer="I used an approved tool to draft a fictional reply and reviewed it.",
    index=2,
):
    qs = client.get("/diagnostic/questions", headers=headers).json()
    return {
        "answers": [
            {
                "question_id": q["id"],
                "answer": q["options"][index] if q["type"] == "mcq" else open_answer,
            }
            for q in qs
        ]
    }


def report(client, headers):
    return client.get("/reports/me", headers=headers).json()


def support(client, headers):
    return next(
        x
        for x in client.get("/dashboard", headers=headers).json()["departments"]
        if x["department"] == "Support"
    )


def test_five_to_four_after_deletion_and_return_to_five(client):
    admin = employee(client, "asha@northwind.test")
    priya = employee(client)
    initial = support(client, admin)
    assert initial["responded"] == 5 and initial["average_score"] is not None
    assert client.delete("/reports/me", headers=priya).status_code == 200
    hidden = support(client, admin)
    assert (
        hidden["protected"]
        and hidden["responded"] is None
        and hidden["average_score"] is None
    )
    assert hidden["risks"] == []
    fresh = employee(client, "new@northwind.test")
    body = payload(client, fresh)
    assert (
        client.post("/diagnostic/submit", headers=fresh, json=body).json()["status"]
        == "completed"
    )
    assert support(client, admin)["responded"] == 5
    first_id = report(client, fresh)["assessment_id"]
    repeated = client.post("/diagnostic/submit", headers=fresh, json=body).json()
    assert repeated["reused"] and repeated["assessment_id"] == first_id
    assert support(client, admin)["responded"] == 5


@pytest.mark.parametrize("scope", ["current", "all"])
def test_admin_personal_deletion_preserves_other_employees(client, scope):
    admin = employee(client, "asha@northwind.test")
    priya = employee(client)
    before = report(client, priya)
    before_support = support(client, admin)
    assert before["status"] == "completed" and before["actions"]
    submitted = client.post(
        "/diagnostic/submit", headers=admin, json=payload(client, admin)
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "completed"

    deleted = client.delete(f"/reports/me?scope={scope}", headers=admin)

    assert deleted.status_code == 200
    assert deleted.json()["answers_deleted"] > 0
    assert report(client, admin)["status"] == "not_started"
    assert report(client, priya) == before
    assert support(client, admin) == before_support


def test_unassigned_row_does_not_reveal_first_completion_or_deletion(client):
    admin = employee(client, "asha@northwind.test")

    def unassigned():
        groups = client.get("/dashboard", headers=admin).json()["departments"]
        return next((g for g in groups if g["department"] == "Unassigned"), None)

    before = unassigned()
    assert before is not None and before["protected"] is True
    response = client.post(
        "/diagnostic/submit", headers=admin, json=payload(client, admin)
    )
    assert response.status_code == 200 and response.json()["status"] == "completed"
    assert unassigned() == before
    assert client.delete("/reports/me", headers=admin).status_code == 200
    assert unassigned() == before


def test_deletion_cascades_actions_and_does_not_touch_other_people(client):
    headers = employee(client)
    before = report(client, headers)
    assert before["actions"]
    other = employee(client, "dev@northwind.test")
    untouched = report(client, other)
    client.delete("/reports/me", headers=headers)
    assert report(client, headers)["status"] == "not_started"
    with SessionLocal() as db:
        assert db.get(models.Assessment, before["assessment_id"]) is None
        assert (
            db.query(models.Action)
            .filter_by(assessment_id=before["assessment_id"])
            .count()
            == 0
        )
        assert (
            db.query(models.Response)
            .filter_by(assessment_id=before["assessment_id"])
            .count()
            == 0
        )
    assert report(client, other)["assessment_id"] == untouched["assessment_id"]
    assert client.delete("/reports/me", headers=headers).json()["answers_deleted"] == 0


def test_action_is_private_and_completion_does_not_change_score(client):
    priya, dev = employee(client), employee(client, "dev@northwind.test")
    before = report(client, priya)
    action_id = before["actions"][0]["id"]
    assert (
        client.patch(
            f"/reports/me/actions/{action_id}", headers=dev, json={"done": True}
        ).status_code
        == 404
    )
    target = (date.today() + timedelta(days=4)).isoformat()
    changed = client.patch(
        f"/reports/me/actions/{action_id}",
        headers=priya,
        json={"done": True, "due_date": target},
    )
    assert changed.status_code == 200, changed.text
    after = report(client, priya)
    assert (
        after["actions"][0]["done"] is True
        and after["actions"][0]["due_date"] == target
    )
    assert after["average_score"] == before["average_score"]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "wrong_role", "wrong_option", "short_open"]
)
def test_rejects_invalid_submission_without_changing_saved_data(client, mutation):
    headers = employee(client)
    before = report(client, headers)
    body = payload(client, headers)
    if mutation == "duplicate":
        body["answers"].append(body["answers"][0])
    elif mutation == "missing":
        body["answers"].pop()
    elif mutation == "wrong_role":
        body["answers"][-1]["question_id"] = "eng-arch"
    elif mutation == "wrong_option":
        body["answers"][0]["answer"] = "invented"
    else:
        next(a for a in body["answers"] if a["question_id"] == "common-open")[
            "answer"
        ] = " "
    assert (
        client.post("/diagnostic/submit", headers=headers, json=body).status_code == 422
    )
    assert report(client, headers)["assessment_id"] == before["assessment_id"]


def test_model_failure_is_pending_not_a_fake_score_and_retry_completes(
    client, monkeypatch
):
    headers = employee(client)
    monkeypatch.setattr(
        llm, "score_answer", lambda *args: '{"score":7,"reason":"bad","flags":[]}'
    )
    result = client.post(
        "/diagnostic/submit", headers=headers, json=payload(client, headers)
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "pending"
    data = report(client, headers)
    assert data["average_score"] is None and data["actions"] == []
    assert next(a for a in data["answers"] if a["type"] == "open")["score"] is None
    admin = employee(client, "asha@northwind.test")
    assert support(client, admin)["protected"]
    monkeypatch.setattr(
        llm,
        "score_answer",
        lambda *args: '{"score":4,"reason":"Checked outputs.","flags":[]}',
    )
    assert (
        client.post("/diagnostic/retry", headers=headers).json()["status"]
        == "completed"
    )
    assert support(client, admin)["responded"] == 5


def test_delete_while_model_is_running_cannot_resurrect_data(client, monkeypatch):
    headers = employee(client)

    def delayed_score(*args):
        assert client.delete("/reports/me", headers=headers).status_code == 200
        return '{"score":4,"reason":"Checked outputs.","flags":[]}'

    monkeypatch.setattr(llm, "score_answer", delayed_score)
    r = client.post(
        "/diagnostic/submit", headers=headers, json=payload(client, headers)
    )
    assert r.status_code == 404
    assert report(client, headers)["status"] == "not_started"


def test_retake_replaces_plan_and_answers(client):
    headers = employee(client)
    before = report(client, headers)
    client.post(
        "/diagnostic/submit", headers=headers, json=payload(client, headers, index=0)
    )
    after = report(client, headers)
    assert after["assessment_id"] != before["assessment_id"]
    assert len(after["answers"]) == len(
        client.get("/diagnostic/questions", headers=headers).json()
    )
    with SessionLocal() as db:
        assert (
            db.query(models.Action)
            .filter_by(assessment_id=before["assessment_id"])
            .count()
            == 0
        )


def test_multi_company_roles_and_account_wide_deletion(client):
    nw = employee(client, "ravi@consult.test")
    bp = employee(client, "ravi@consult.test", "Bluepeak Retail")
    assert client.get("/dashboard", headers=nw).status_code == 403
    assert client.get("/dashboard?org_id=1", headers=bp).status_code == 403
    assert client.get("/dashboard", headers=bp).status_code == 200
    assert (
        client.post(
            "/diagnostic/submit", headers=bp, json=payload(client, bp)
        ).status_code
        == 200
    )
    client.delete("/reports/me", headers=nw)
    assert report(client, bp)["status"] == "completed"
    client.delete("/reports/me?scope=all", headers=nw)
    assert report(client, bp)["status"] == "not_started"


def test_scores_are_average_of_people_not_rows(client):
    headers = employee(client, "asha@northwind.test")
    data = support(client, headers)
    with SessionLocal() as db:
        members = (
            db.query(models.Membership)
            .join(models.Department)
            .filter(models.Department.name == "Support")
            .all()
        )
        averages = []
        for member in members:
            rows = db.query(models.Response).filter_by(membership_id=member.id).all()
            if rows:
                averages.append(sum(r.score for r in rows) / len(rows))
    assert data["average_score"] == round(sum(averages) / len(averages), 2)


@pytest.mark.parametrize("size", [0, 1, 4, 5, 6])
def test_privacy_threshold_and_rare_risks(size):
    rows = [
        {"average": 4, "flags": ["customer_data_shared"] if i == 0 else []}
        for i in range(size)
    ]
    group = publish([{"name": "Team", "people": rows}])[0]
    assert group["protected"] == (size < 5)
    if size < 5:
        assert group["responded"] is None and group["risks"] == []
    else:
        assert group["average_score"] == 4
        assert all(x["people"] is None for x in group["risks"])


def test_risk_count_counts_people_once():
    rows = [
        {"average": 3, "flags": ["unreviewed_output", "unreviewed_output"]}
        for _ in range(5)
    ]
    rows.extend({"average": 3, "flags": []} for _ in range(5))
    group = publish([{"name": "Team", "people": rows}])[0]
    assert (
        next(x for x in group["risks"] if x["key"] == "unreviewed_output")["people"]
        == 5
    )


@pytest.mark.parametrize(
    "size, flagged, expected",
    [
        (6, 5, None),
        (6, 6, None),
        (9, 5, None),
        (10, 5, 5),
        (10, 6, None),
        (10, 0, None),
        (11, 6, 6),
    ],
)
def test_risk_counts_protect_both_flagged_and_unflagged_people(size, flagged, expected):
    rows = [
        {"average": 3, "flags": ["unreviewed_output"] if i < flagged else []}
        for i in range(size)
    ]
    group = publish([{"name": "Team", "people": rows}])[0]
    assert group["responded"] == size
    assert (
        next(r for r in group["risks"] if r["key"] == "unreviewed_output")["people"]
        == expected
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not JSON",
        "[]",
        '{"score":7,"reason":"x","flags":[]}',
        '{"score":0,"reason":"x","flags":[]}',
        '{"score":"four","reason":"x","flags":[]}',
        '{"score":true,"reason":"x","flags":[]}',
        '{"score":3.5,"reason":"x","flags":[]}',
        '{"score":4,"flags":[]}',
        '{"score":4,"reason":" ","flags":[]}',
        '{"score":4,"reason":"x","flags":["probably_lying"]}',
        '{"score":4,"reason":"x","flags":"unreviewed_output"}',
        '{"score":4,"reason":"x","flags":[],"admin":true}',
        '{"score":3,"score":5,"reason":"x","flags":[]}',
        '{"score":NaN,"reason":"x","flags":[]}',
    ],
)
def test_invalid_ai_output_is_not_coerced_into_a_result(raw):
    with pytest.raises(ScoringUnavailable):
        parse_result(raw)


def test_valid_fenced_output_is_supported():
    fence = chr(96) * 3
    assert (
        parse_result(
            fence + 'json\n{"score":4,"reason":"Reviewed work.","flags":[]}\n' + fence
        )["score"]
        == 4
    )


def test_password_hashes_are_salted_and_legacy_upgrade_works(client):
    a, b = hash_password("test-password"), hash_password("test-password")
    assert a != b and verify_password("test-password", a)
    assert not verify_password("wrong", a)
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email="priya@northwind.test").one()
        user.password_hash = hashlib.sha256(b"pulse123").hexdigest()
        db.commit()
    employee(client)
    with SessionLocal() as db:
        assert (
            db.query(models.User)
            .filter_by(email="priya@northwind.test")
            .one()
            .password_hash.startswith("$argon2")
        )


def test_validation_never_echoes_passwords(client):
    secret = "not-a-real-password-" * 30
    response = client.post("/auth/login", json={"email": "a", "password": secret})
    assert response.status_code == 422 and secret not in response.text


def test_body_limit(client):
    r = client.post(
        "/auth/login",
        content=b"x" * 70000,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_login_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/auth/login",
                json={"email": "unknown@example.test", "password": "incorrect"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login",
            json={"email": "unknown@example.test", "password": "incorrect"},
        ).status_code
        == 429
    )


def test_missing_malformed_and_wrong_scope_tokens(client):
    for token in ("", "Bearer invalid", "Basic abc"):
        assert (
            client.get("/reports/me", headers={"Authorization": token}).status_code
            == 401
        )
    headers, _ = login(client, "priya@northwind.test")
    assert client.get("/reports/me", headers=headers).status_code == 400


def test_sensitive_responses_are_not_cached(client):
    headers = employee(client)
    assert (
        client.get("/reports/me", headers=headers).headers["cache-control"]
        == "no-store"
    )
