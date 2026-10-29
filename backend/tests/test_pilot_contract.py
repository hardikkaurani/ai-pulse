"""Client-facing promises, written before the implementation changes."""

from tests.conftest import login


def test_cross_company_dashboard_is_denied(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    assert client.get("/dashboard?org_id=2", headers=headers).status_code == 403


def test_cannot_select_unowned_company(client):
    headers, _ = login(client, "priya@northwind.test")
    assert (
        client.post("/auth/select-org", headers=headers, json={"org_id": 2}).status_code
        == 403
    )


def test_empty_assessment_is_not_completed(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    assert (
        client.post(
            "/diagnostic/submit", headers=headers, json={"answers": []}
        ).status_code
        == 422
    )


def test_partial_assessment_is_rejected(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.post(
        "/diagnostic/submit",
        headers=headers,
        json={"answers": [{"question_id": "common-freq", "answer": "Daily"}]},
    )
    assert r.status_code == 422


def test_small_departments_do_not_publish_scores(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    data = client.get("/dashboard?org_id=1", headers=headers).json()
    for team in data["departments"]:
        if team["protected"]:
            assert team["average_score"] is None
