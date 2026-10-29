"""A fresh synthetic demo on separate ports; never changes the live .env or database."""

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
_venv_python = (
    ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)
PYTHON = _venv_python if _venv_python.exists() else Path(sys.executable)


def prepare_workspace(parent=None):
    if not PYTHON.exists():
        raise SystemExit("Run python scripts/setup.py first.")
    parent = Path(parent) if parent else ROOT / "work" / "rehearsals"
    parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="demo-", dir=parent)).resolve()
    environment = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + (workspace / "rehearsal.db").as_posix(),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "AI_MODE": "mock",
        "LLM_API_KEY": "",
        "LLM_API_URL": "",
        "LLM_MODEL": "",
        "CORS_ORIGINS": "http://127.0.0.1:5174,http://localhost:5174",
        "PULSE_API_PORT": "8001",
        "PULSE_WEB_PORT": "5174",
    }
    # Explicit process settings override .env. Credentials and real data are not copied.
    for command in [
        [str(PYTHON), "-m", "alembic", "upgrade", "head"],
        [str(PYTHON), "-m", "app.seed", "--demo"],
    ]:
        subprocess.run(command, cwd=ROOT / "backend", env=environment, check=True)
    return workspace, environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Create the isolated fixture without starting services.",
    )
    args = parser.parse_args()
    workspace, environment = prepare_workspace()
    print("SYNTHETIC REHEARSAL: fixed demo scores; no live AI requests.", flush=True)
    print(f"Fresh database: {workspace / 'rehearsal.db'}", flush=True)
    print(
        "Support starts with 5 completed people. Your normal app is unchanged.",
        flush=True,
    )
    if args.prepare_only:
        return 0
    try:
        return subprocess.call(
            [str(PYTHON), str(ROOT / "scripts" / "run.py")], env=environment
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
