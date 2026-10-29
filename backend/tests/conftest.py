import os
from pathlib import Path
import sys
import tempfile
import pytest

_backend_dir = Path(__file__).resolve().parent.parent
_root_dir = _backend_dir.parent
for p in (_root_dir, _backend_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_test_dir = tempfile.TemporaryDirectory(prefix="ai-pulse-tests-")

os.environ["DATABASE_URL"] = (
    "sqlite:///" + _test_dir.name.replace("\\", "/") + "/test.db"
)
os.environ["AI_MODE"] = "mock"
os.environ["SECRET_KEY"] = "isolated-test-secret-never-use-in-deployment-123456"

from functools import lru_cache  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import seed  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.services.rate_limit import _attempts  # noqa: E402


seed.hash_password = lru_cache(maxsize=1)(seed.hash_password)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _test_dir.cleanup()


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _attempts.clear()
    seed.run()
    with TestClient(app) as test_client:
        yield test_client


def login(client, email, org_name=None):
    r = client.post("/auth/login", json={"email": email, "password": "pulse123"})
    assert r.status_code == 200, r.text
    data = r.json()
    token = data["token"]
    if org_name:
        org = next(o for o in data["organizations"] if o["org_name"] == org_name)
        result = client.post(
            "/auth/select-org",
            json={"org_id": org["org_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert result.status_code == 200
        token = result.json()["token"]
    return {"Authorization": f"Bearer {token}"}, data


def employee(client, email="priya@northwind.test", org="Northwind Logistics"):
    return login(client, email, org)[0]


def admin(client, email="asha@northwind.test", org="Northwind Logistics"):
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
