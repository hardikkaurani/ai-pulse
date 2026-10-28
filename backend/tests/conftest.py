import os
import tempfile
import pytest

# Allocate an isolated temporary SQLite database outside the workspace repository
_TEST_DB_FILE = os.path.join(tempfile.gettempdir(), f"aipulse_test_{os.getpid()}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_FILE}"
os.environ["AI_MODE"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import seed  # noqa: E402
from app.db import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Ensure test database is cleaned up after the test session."""
    yield
    # Dispose active connections so Windows unlocks the file for deletion
    engine.dispose()
    if os.path.exists(_TEST_DB_FILE):
        try:
            os.remove(_TEST_DB_FILE)
        except OSError:
            pass


@pytest.fixture()
def client():
    seed.run()
    return TestClient(app)


def login(client, email, org_name=None):
    r = client.post("/auth/login", json={"email": email, "password": "pulse123"})
    data = r.json()
    token = data["token"]
    if org_name:
        org = next(o for o in data["organizations"] if o["org_name"] == org_name)
        token = client.post(
            "/auth/select-org",
            json={"org_id": org["org_id"]},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["token"]
    return {"Authorization": f"Bearer {token}"}, data
