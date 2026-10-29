import os
import tempfile
import pytest

_test_dir = tempfile.TemporaryDirectory(prefix="ai-pulse-tests-")
os.environ["DATABASE_URL"] = (
    "sqlite:///" + _test_dir.name.replace("\\", "/") + "/test.db"
)
os.environ["AI_MODE"] = "mock"
os.environ["SECRET_KEY"] = "isolated-test-secret-never-use-in-deployment-123456"

from fastapi.testclient import TestClient
from app.main import app
from app import seed
from app.db import Base, engine
from app.services.rate_limit import _attempts
from functools import lru_cache

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
