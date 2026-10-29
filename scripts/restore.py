"""Database restore utility with integrity drill and checksum verification.

Restores SQLite database from verified backup, validates checksum, foreign keys,
and row counts against manifest.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def restore_sqlite(backup_file: Path, manifest_file: Path, target_path: Path) -> dict:
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    expected_sha256 = manifest["sha256"]
    expected_counts = manifest["row_counts"]

    # 1. Verify Checksum
    hasher = hashlib.sha256()
    with open(backup_file, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_sha256 = hasher.hexdigest()

    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Checksum mismatch! Expected {expected_sha256}, got {actual_sha256}."
        )

    # 2. Perform Restore (atomic file copy to target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_suffix(".tmp_restore")
    shutil.copy2(backup_file, temp_target)
    if target_path.exists():
        target_path.unlink()
    temp_target.rename(target_path)

    # 3. Verify Foreign Keys and Row Counts
    actual_counts = {}
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        fk_errors = cursor.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(
                f"Foreign key violations detected after restore: {fk_errors}"
            )

        for table in expected_counts:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            actual_counts[table] = cursor.fetchone()[0]

    # 4. Compare Row Counts
    for table, count in expected_counts.items():
        if actual_counts.get(table) != count:
            raise ValueError(
                f"Row count mismatch in table '{table}': expected {count}, got {actual_counts.get(table)}"
            )

    return {
        "status": "success",
        "verified_sha256": actual_sha256,
        "tables_verified": len(expected_counts),
        "total_rows_verified": sum(actual_counts.values()),
        "target": str(target_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Restore verified AI Pulse database backup."
    )
    parser.add_argument("backup_file", type=Path, help="Path to the backup .db file.")
    parser.add_argument("--manifest", type=Path, help="Optional path to manifest JSON.")
    parser.add_argument(
        "--target",
        type=Path,
        help="Target database path to restore into.",
    )
    args = parser.parse_args()

    manifest = args.manifest or args.backup_file.with_suffix(".json")
    target = args.target or (ROOT / "backend/aipulse.db")

    result = restore_sqlite(args.backup_file, manifest, target)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
