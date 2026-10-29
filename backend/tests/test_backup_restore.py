"""Tests for database backup and restore verification drill."""

import json
from pathlib import Path
import sqlite3
import sys
import pytest

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.backup import backup_sqlite  # noqa: E402
from scripts.restore import restore_sqlite  # noqa: E402


@pytest.fixture
def populated_db(tmp_path):
    db_file = tmp_path / "source.db"
    with sqlite3.connect(db_file) as conn:
        conn.executescript("""
            CREATE TABLE organizations (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT);
            CREATE TABLE assessments (id TEXT PRIMARY KEY, status TEXT);
            INSERT INTO organizations VALUES (1, 'Org A'), (2, 'Org B');
            INSERT INTO users VALUES (1, 'u1@test.com', 'User 1'), (2, 'u2@test.com', 'User 2');
            INSERT INTO assessments VALUES ('a1', 'completed'), ('a2', 'pending');
        """)
    return db_file


def test_backup_and_restore_cycle(tmp_path, populated_db):
    backup_dir = tmp_path / "backups"
    backup_file, manifest_file = backup_sqlite(populated_db, backup_dir)

    assert backup_file.exists()
    assert manifest_file.exists()

    manifest = json.loads(manifest_file.read_text())
    assert manifest["database_type"] == "sqlite"
    assert manifest["row_counts"] == {"organizations": 2, "users": 2, "assessments": 2}
    assert manifest["total_rows"] == 6

    # Restore to a fresh location
    restored_target = tmp_path / "restored.db"
    result = restore_sqlite(backup_file, manifest_file, restored_target)

    assert result["status"] == "success"
    assert result["total_rows_verified"] == 6

    # Verify rows in restored database directly
    with sqlite3.connect(restored_target) as conn:
        orgs = conn.execute("SELECT name FROM organizations ORDER BY id").fetchall()
        assert orgs == [("Org A",), ("Org B",)]


def test_restore_rejects_corrupted_backup(tmp_path, populated_db):
    backup_dir = tmp_path / "backups"
    backup_file, manifest_file = backup_sqlite(populated_db, backup_dir)

    # Corrupt the backup file by appending junk bytes
    with open(backup_file, "ab") as f:
        f.write(b"corrupted_tampered_payload")

    restored_target = tmp_path / "restored.db"
    with pytest.raises(ValueError, match="Checksum mismatch"):
        restore_sqlite(backup_file, manifest_file, restored_target)


def test_restore_rejects_row_count_tampering(tmp_path, populated_db):
    backup_dir = tmp_path / "backups"
    backup_file, manifest_file = backup_sqlite(populated_db, backup_dir)

    # Tamper with the manifest to expect 99 organizations
    manifest = json.loads(manifest_file.read_text())
    # Recompute checksum if someone modified the DB, or just simulate manifest discrepancy
    manifest["row_counts"]["organizations"] = 99
    # To bypass checksum check and test row count verification, update checksum in manifest
    import hashlib

    hasher = hashlib.sha256()
    with open(backup_file, "rb") as f:
        hasher.update(f.read())
    manifest["sha256"] = hasher.hexdigest()
    manifest_file.write_text(json.dumps(manifest))

    restored_target = tmp_path / "restored.db"
    with pytest.raises(ValueError, match="Row count mismatch"):
        restore_sqlite(backup_file, manifest_file, restored_target)
