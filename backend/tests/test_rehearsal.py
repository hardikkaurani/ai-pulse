"""Verify the recording fixture cannot replace a configured live database."""

from pathlib import Path
import os
import runpy
import socket
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_rehearsal_is_isolated_repeatable_and_starts_at_privacy_boundary(
    tmp_path, monkeypatch
):
    live_db = tmp_path / "live.db"
    with sqlite3.connect(live_db) as db:
        db.execute("CREATE TABLE preserved (value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('keep me')")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + live_db.as_posix())
    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("LLM_API_KEY", "test-key-that-must-not-be-used")
    prepare = runpy.run_path(str(ROOT / "scripts" / "rehearse.py"))["prepare_workspace"]
    first, first_env = prepare(tmp_path / "rehearsals")
    second, second_env = prepare(tmp_path / "rehearsals")
    assert first != second and first_env["SECRET_KEY"] != second_env["SECRET_KEY"]
    assert first_env["AI_MODE"] == "mock" and first_env["LLM_API_KEY"] == ""
    assert (
        first_env["PULSE_API_PORT"] == "8001" and first_env["PULSE_WEB_PORT"] == "5174"
    )
    with sqlite3.connect(live_db) as db:
        assert db.execute("SELECT value FROM preserved").fetchall() == [("keep me",)]
    for workspace in (first, second):
        with sqlite3.connect(workspace / "rehearsal.db") as db:
            count = db.execute("""
                SELECT count(*) FROM assessments a
                JOIN memberships m ON m.id=a.membership_id
                JOIN departments d ON d.id=m.department_id
                JOIN organizations o ON o.id=m.org_id
                WHERE d.name='Support' AND o.name='Northwind Logistics'
                AND a.status='completed'
            """).fetchone()[0]
            assert count == 5
            assert db.execute(
                "SELECT DISTINCT ai_mode FROM assessments"
            ).fetchall() == [("mock",)]


def test_launcher_refuses_an_occupied_port_without_starting_services():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run.py")],
            env={**os.environ, "PULSE_API_PORT": str(port), "PULSE_WEB_PORT": "5174"},
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert f"Port {port} is occupied" in result.stderr
