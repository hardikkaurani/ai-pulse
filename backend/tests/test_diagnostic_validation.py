from unittest.mock import patch
import pytest
from tests.conftest import login
from app import models
from app.db import SessionLocal


def get_member_questions(client, headers):
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    return r.json()


def test_submit_valid_diagnostic_success(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    assert len(qs) > 0

    answers = []
    for q in qs:
        if q["type"] == "mcq":
            answers.append({"question_id": q["id"], "answer": q["options"][0]})
        else:
            answers.append({"question_id": q["id"], "answer": "I use internal AI tools to review customer tickets with proper data anonymization."})

    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 200
    assert res.json()["saved"] == len(answers)


def test_submit_rejects_missing_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    # omit the first question
    partial_answers = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Detailed answer of at least 10 characters."}
        for q in qs[1:]
    ]
    res = client.post("/diagnostic/submit", json={"answers": partial_answers}, headers=headers)
    assert res.status_code == 422
    assert "Missing required questions" in res.json()["detail"]


def test_submit_rejects_unexpected_question_id(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    answers = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Detailed answer of at least 10 characters."}
        for q in qs
    ]
    # Replace one question ID with an unknown one
    answers[0]["question_id"] = "unknown-question-999"
    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 422
    assert "Unexpected question IDs" in res.json()["detail"] or "Missing required questions" in res.json()["detail"]


def test_submit_rejects_duplicate_question_ids(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    first_q = qs[0]
    ans = first_q["options"][0] if first_q["type"] == "mcq" else "Detailed answer of at least 10 characters."
    answers = [
        {"question_id": first_q["id"], "answer": ans},
        {"question_id": first_q["id"], "answer": ans},
    ]
    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 422
    assert "Duplicate question IDs" in res.json()["detail"]


def test_submit_rejects_blank_answer(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    answers = []
    for q in qs:
        answers.append({"question_id": q["id"], "answer": "   " if q == qs[0] else (q["options"][0] if q["type"] == "mcq" else "Detailed valid answer.")})
    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 422
    assert "cannot be blank" in res.json()["detail"]


def test_submit_rejects_invalid_mcq_option(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    mcq = next(q for q in qs if q["type"] == "mcq")
    answers = []
    for q in qs:
        if q["id"] == mcq["id"]:
            answers.append({"question_id": q["id"], "answer": "Totally Fabricated Option That Does Not Exist"})
        else:
            answers.append({"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Detailed valid answer."})
    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 422
    assert "Invalid option" in res.json()["detail"]


def test_submit_rejects_short_open_answer(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)
    open_q = next(q for q in qs if q["type"] == "open")
    answers = []
    for q in qs:
        if q["id"] == open_q["id"]:
            answers.append({"question_id": q["id"], "answer": "too short"})
        else:
            answers.append({"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Detailed valid answer."})
    res = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)
    assert res.status_code == 422
    assert "at least 10 characters" in res.json()["detail"]


def test_resubmission_atomically_replaces_previous_responses(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)

    answers1 = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Initial first round assessment answers."}
        for q in qs
    ]
    r1 = client.post("/diagnostic/submit", json={"answers": answers1}, headers=headers)
    assert r1.status_code == 200

    # Count responses in DB
    with SessionLocal() as db:
        m = db.query(models.Membership).join(models.User).filter(models.User.email == "priya@northwind.test").first()
        count1 = db.query(models.Response).filter_by(membership_id=m.id).count()
        assert count1 == len(qs)

    # Second submission with different answers
    answers2 = [
        {"question_id": q["id"], "answer": q["options"][-1] if q["type"] == "mcq" else "Updated second round assessment answers."}
        for q in qs
    ]
    r2 = client.post("/diagnostic/submit", json={"answers": answers2}, headers=headers)
    assert r2.status_code == 200

    with SessionLocal() as db:
        m = db.query(models.Membership).join(models.User).filter(models.User.email == "priya@northwind.test").first()
        count2 = db.query(models.Response).filter_by(membership_id=m.id).count()
        # MUST still be equal to len(qs), NOT duplicated to len(qs) * 2!
        assert count2 == len(qs)
        # Check text was updated
        open_resp = db.query(models.Response).filter_by(membership_id=m.id, question_id="common-open").first()
        assert "Updated second round" in open_resp.answer


def test_scoring_failure_rolls_back_and_preserves_previous(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    qs = get_member_questions(client, headers)

    # First successful submission
    answers1 = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Original stable diagnostic answers."}
        for q in qs
    ]
    r1 = client.post("/diagnostic/submit", json={"answers": answers1}, headers=headers)
    assert r1.status_code == 200

    # Attempt second submission with scoring failure simulated
    answers2 = [
        {"question_id": q["id"], "answer": q["options"][-1] if q["type"] == "mcq" else "New answer that should fail scoring."}
        for q in qs
    ]
    with patch("app.routes.diagnostic.score_open_answer", side_effect=RuntimeError("LLM cluster failure")):
        r2 = client.post("/diagnostic/submit", json={"answers": answers2}, headers=headers)
        assert r2.status_code == 503
        assert "AI scoring service temporarily unavailable" in r2.json()["detail"]

    # Verify previous responses are still intact in DB!
    with SessionLocal() as db:
        m = db.query(models.Membership).join(models.User).filter(models.User.email == "priya@northwind.test").first()
        open_resp = db.query(models.Response).filter_by(membership_id=m.id, question_id="common-open").first()
        assert "Original stable diagnostic" in open_resp.answer
