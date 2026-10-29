"""Start both local services. Ctrl+C stops only these child processes."""

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
_venv_python = (
    ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)
python = _venv_python if _venv_python.exists() else Path(sys.executable)
node = shutil.which("node")
if not python.exists() or not node:
    raise SystemExit("Run python scripts/setup.py --demo first.")
try:
    api_port = int(os.getenv("PULSE_API_PORT", "8000"))
    web_port = int(os.getenv("PULSE_WEB_PORT", "5173"))
    if api_port == web_port or not all(0 < p < 65536 for p in (api_port, web_port)):
        raise ValueError
except ValueError:
    raise SystemExit("Choose two different ports between 1 and 65535.")
for port in (api_port, web_port):
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(
            f"Port {port} is occupied. Stop that local service before starting AI Pulse."
        )
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
processes = []
exit_code = 0
try:
    processes.append(
        subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            cwd=ROOT / "backend",
            creationflags=flags,
        )
    )
    processes.append(
        subprocess.Popen(
            [
                node,
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                str(web_port),
                "--strictPort",
            ],
            cwd=ROOT / "frontend",
            creationflags=flags,
            env={**os.environ, "VITE_API_URL": f"http://127.0.0.1:{api_port}"},
        )
    )
    print(
        f"AI Pulse: http://127.0.0.1:{web_port} | API: http://127.0.0.1:{api_port}",
        flush=True,
    )
    while all(p.poll() is None for p in processes):
        time.sleep(0.5)
    print("A local service stopped. Check its error above.", flush=True)
    exit_code = 1
except KeyboardInterrupt:
    print("Stopping AI Pulse...", flush=True)
finally:
    for p in processes:
        if p.poll() is None:
            if os.name == "nt":
                # The virtualenv launcher has its own Python child on Windows.
                subprocess.run(
                    ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                p.terminate()
    for p in processes:
        p.wait()
raise SystemExit(exit_code)
