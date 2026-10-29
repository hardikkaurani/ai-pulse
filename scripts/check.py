"""Run backend, frontend and production-build checks."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
_venv_python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
python = _venv_python if _venv_python.exists() else Path(sys.executable)
npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
for command, cwd in [
    ([str(python), "-m", "pytest", "-q"], ROOT / "backend"),
    ([npm, "test"], ROOT / "frontend"),
    ([npm, "run", "build"], ROOT / "frontend"),
]:
    subprocess.run(command, cwd=cwd, check=True)
