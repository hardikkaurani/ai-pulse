"""Run from any directory: python scripts/setup.py [--demo]. Existing data is never reset."""

import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
parser = argparse.ArgumentParser()
parser.add_argument(
    "--demo",
    action="store_true",
    help="Seed synthetic accounts only if the database is empty.",
)
parser.add_argument(
    "--skip-install", action="store_true", help="Use already installed dependencies."
)
args = parser.parse_args()
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required (tested with 3.13).")
if not PYTHON.exists():
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
env_file = ROOT / "backend" / ".env"
if not env_file.exists():
    env_file.write_text(
        "SECRET_KEY=" + secrets.token_urlsafe(48) + "\nAI_MODE=mock\n", encoding="utf-8"
    )
    print("Created private local configuration with a random signing key.")
if not args.skip_install:
    subprocess.run(
        [
            str(PYTHON),
            "-m",
            "pip",
            "install",
            "-r",
            str(ROOT / "backend/requirements-dev.txt"),
        ],
        check=True,
    )
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("Install Node.js 24 LTS, then rerun setup.")
    subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True)
subprocess.run(
    [str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", check=True
)
if args.demo:
    subprocess.run(
        [str(PYTHON), "-m", "app.seed", "--demo"], cwd=ROOT / "backend", check=True
    )
print("Ready. Start with: python scripts/run.py")
