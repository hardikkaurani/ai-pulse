"""Opt-in integration against a disposable PostgreSQL database named aipulse_test."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

BACKEND = Path(__file__).resolve().parents[1]
URL = os.getenv("PULSE_TEST_POSTGRES_URL", "")


@pytest.mark.skipif(
    not URL, reason="Set PULSE_TEST_POSTGRES_URL for PostgreSQL integration"
)
def test_postgres_migrate_assess_persist_delete():
    if urlparse(URL).path != "/aipulse_test":
        pytest.fail("Refusing to use a database not named aipulse_test")
    env = {
        **os.environ,
        "DATABASE_URL": URL,
        "AI_MODE": "mock",
        "STATIC_DIR": "",
        "SECRET_KEY": "postgres-test-only-secret-never-deploy-123456",
        "LLM_API_KEY": "",
    }

    def run(*args):
        result = subprocess.run(
            [sys.executable, *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

    run("-m", "alembic", "upgrade", "head")
    run("-m", "alembic", "upgrade", "head")
    common = """
from fastapi.testclient import TestClient
from app.main import app
from app.db import engine
from app import seed
assert engine.dialect.name == 'postgresql'
seed.run()
client = TestClient(app)
def login(email):
    r = client.post('/auth/login', json={'email':email,'password':'pulse123'})
    assert r.status_code == 200
    org = r.json()['organizations'][0]
    selected = client.post('/auth/select-org', json={'org_id':org['org_id']},
        headers={'Authorization':'Bearer '+r.json()['token']})
    assert selected.status_code == 200
    return {'Authorization':'Bearer '+selected.json()['token']}
headers = login('new@northwind.test')
"""
    run(
        "-c",
        common
        + """
qs = client.get('/diagnostic/questions',headers=headers).json()
body = {'answers':[{'question_id':q['id'], 'answer':q['options'][2] if q['type']=='mcq'
    else 'A fictional example: I checked an AI draft before using it.'} for q in qs]}
r = client.post('/diagnostic/submit',headers=headers,json=body)
assert r.status_code == 200 and r.json()['status'] == 'completed', r.text
report = client.get('/reports/me',headers=headers).json()
assert report['answered'] == len(qs) and report['actions']
action = report['actions'][0]
r = client.patch('/reports/me/actions/'+action['id'],headers=headers,json={'done':True})
assert r.status_code == 200
assert client.get('/dashboard',headers=headers).status_code == 403
""",
    )
    # A new Python process must see the saved report/activity. Re-seeding above
    # must preserve them. Deletion then exercises PostgreSQL's FK cascades.
    run(
        "-c",
        common
        + """
report = client.get('/reports/me',headers=headers).json()
assert report['status'] == 'completed'
assert any(a['done'] for a in report['actions'])
assert client.delete('/reports/me',headers=headers).status_code == 200
assert client.get('/reports/me',headers=headers).json()['status'] == 'not_started'
admin = login('asha@northwind.test')
r = client.get('/dashboard',headers=admin)
assert r.status_code == 200
assert any(d['protected'] for d in r.json()['departments'])
""",
    )
