"""Exercise hosted startup and static/API isolation using only a disposable DB."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_hosted_startup_keeps_data_and_serves_only_built_frontend(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>Isolated hosted frontend</html>")
    db_path = tmp_path / "hosted.db"
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + db_path.as_posix(),
        "SECRET_KEY": "hosted-test-secret-isolated-never-deploy-123456",
        "STATIC_DIR": str(web),
        "AI_MODE": "mock",
        "SEED_DEMO": "true",
        "LLM_API_KEY": "",
    }
    for attempt in range(2):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/serve.py"), "--prepare-only"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        with sqlite3.connect(db_path) as db:
            if attempt == 0:
                count = db.execute("SELECT count(*) FROM assessments").fetchone()[0]
                db.execute(
                    "UPDATE users SET name='Saved across startup' WHERE email='new@northwind.test'"
                )
            else:
                assert (
                    db.execute(
                        "SELECT name FROM users WHERE email='new@northwind.test'"
                    ).fetchone()[0]
                    == "Saved across startup"
                )
                assert (
                    db.execute("SELECT count(*) FROM assessments").fetchone()[0]
                    == count
                )
    check = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    assert 'Isolated hosted frontend' in client.get('/').text
    assert client.get('/health').json()['status'] == 'ok'
    assert client.get('/reports/me').status_code == 401
    login = client.post('/auth/login', json={'email':'new@northwind.test','password':'pulse123'})
    assert login.status_code == 200
    for path in ('/.env', '/aipulse.db', '/app/config.py', '/missing-api'):
        assert client.get(path).status_code == 404
"""
    result = subprocess.run(
        [sys.executable, "-c", check],
        cwd=ROOT / "backend",
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_hosted_startup_requires_explicit_storage(tmp_path):
    env = {**os.environ, "DATABASE_URL": ""}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/serve.py"), "--prepare-only"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Set DATABASE_URL" in result.stderr
