"""Hosted single-process startup: validate, migrate, optionally seed, then serve."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def prepare():
    # Production must not silently fall back to an ephemeral relative database.
    if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
        raise SystemExit(
            "Set DATABASE_URL and SECRET_KEY in the host's secret settings."
        )
    static_dir = Path(os.environ.get("STATIC_DIR", ""))
    if not (static_dir / "index.html").is_file():
        raise SystemExit("STATIC_DIR must contain the built frontend index.html.")
    try:
        port = int(os.environ.get("PORT", "8000"))
        if not 0 < port < 65536:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be between 1 and 65535.")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True
    )
    if os.environ.get("SEED_DEMO") == "true":
        subprocess.run(
            [sys.executable, "-m", "app.seed", "--demo"], cwd=BACKEND, check=True
        )
    return port


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    port = prepare()
    if not args.prepare_only:
        os.chdir(BACKEND)
        os.execv(
            sys.executable,
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--workers",
                "1",
            ],
        )
