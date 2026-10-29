"""Exercise Alembic against disposable files, not the user's configured database."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest

BACKEND = Path(__file__).resolve().parents[1]
LEGACY = """
CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL);
CREATE TABLE departments (id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES organizations(id), name VARCHAR(80) NOT NULL);
CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(200) NOT NULL UNIQUE, name VARCHAR(120) NOT NULL, password_hash VARCHAR(200) NOT NULL);
CREATE TABLE memberships (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), org_id INTEGER NOT NULL REFERENCES organizations(id), department_id INTEGER REFERENCES departments(id), role VARCHAR(20) NOT NULL, job_role VARCHAR(40) NOT NULL, seniority VARCHAR(20) NOT NULL);
CREATE TABLE responses (id INTEGER PRIMARY KEY, membership_id INTEGER NOT NULL REFERENCES memberships(id), question_id VARCHAR(40) NOT NULL, answer TEXT NOT NULL, score FLOAT, reason TEXT, flags JSON, created_at DATETIME NOT NULL);
INSERT INTO organizations VALUES (1, 'Legacy');
INSERT INTO users VALUES (1, 'legacy@example.test', 'Legacy user', 'old-password-hash');
INSERT INTO memberships VALUES (1, 1, 1, NULL, 'employee', 'support', 'junior');
INSERT INTO responses VALUES (1, 1, 'common-open', 'Keep this answer', 3, 'Old explanation', '[]', '2026-01-01');
"""


@pytest.mark.parametrize("legacy", [False, True])
def test_fresh_and_legacy_database_migrations(tmp_path, legacy):
    path = tmp_path / "migration.db"
    if legacy:
        with sqlite3.connect(path) as db:
            db.executescript(LEGACY)
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + path.as_posix()}
    for _ in range(2):  # Re-running upgrade must be safe.
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "001_pilot"
        )
        assert {"assessments", "actions"} <= {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert any(
            r[2] == "assessments" and r[6] == "CASCADE"
            for r in db.execute("PRAGMA foreign_key_list(responses)")
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        if legacy:
            assert db.execute(
                "SELECT answer, assessment_id FROM responses"
            ).fetchone() == ("Keep this answer", None)
            assert db.execute("SELECT revision FROM memberships").fetchone()[0] == 0
