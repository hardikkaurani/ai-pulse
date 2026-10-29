"""Load-testing harness for AI Pulse pilot SLO verification.

Measures p50, p90, p95, p99 latencies, throughput, and error rates across
representative pilot endpoints under concurrent load.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Ensure benchmark environment has required variables configured
os.environ.setdefault(
    "SECRET_KEY", "isolated-benchmark-secret-never-use-in-deployment-123456"
)
os.environ.setdefault("AI_MODE", "mock")
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + (ROOT / "benchmark_load.db").as_posix()
)


def run_benchmark(
    concurrency: int, total_requests: int, base_url: str | None = None
) -> dict:
    from fastapi.testclient import TestClient
    from app.main import app
    from app import seed
    from app.db import Base, engine
    from tests.conftest import employee, admin

    Base.metadata.create_all(engine)
    seed.run()

    # Setup client
    client = TestClient(app)

    emp_token = employee(client, "priya@northwind.test")
    adm_token = admin(client, "asha@northwind.test")

    endpoints = [
        {
            "name": "reports_me",
            "method": "GET",
            "path": "/reports/me",
            "headers": emp_token,
            "weight": 40,
        },
        {
            "name": "dashboard",
            "method": "GET",
            "path": "/dashboard",
            "headers": adm_token,
            "weight": 30,
        },
        {
            "name": "questions",
            "method": "GET",
            "path": "/diagnostic/questions",
            "headers": emp_token,
            "weight": 15,
        },
        {
            "name": "ready_probe",
            "method": "GET",
            "path": "/ready",
            "headers": {},
            "weight": 10,
        },
        {
            "name": "health_probe",
            "method": "GET",
            "path": "/health",
            "headers": {},
            "weight": 5,
        },
    ]

    import random

    request_pool = random.choices(
        endpoints,
        weights=[e["weight"] for e in endpoints],
        k=total_requests,
    )

    results = []

    def make_request(req_info):
        t0 = time.perf_counter()
        status = 0
        err = None
        try:
            if req_info["method"] == "GET":
                r = client.get(req_info["path"], headers=req_info["headers"])
                status = r.status_code
        except Exception as e:
            err = str(e)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "endpoint": req_info["name"],
            "status": status,
            "duration_ms": duration_ms,
            "error": err,
        }

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, r) for r in request_pool]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = time.perf_counter() - wall_start

    durations = sorted(r["duration_ms"] for r in results)
    successes = [r for r in results if 200 <= r["status"] < 300]
    errors = len(results) - len(successes)
    error_rate = errors / total_requests if total_requests > 0 else 0.0

    def percentile(data, p):
        if not data:
            return 0.0
        idx = int(round((len(data) - 1) * p / 100.0))
        return round(data[idx], 2)

    p50 = percentile(durations, 50)
    p90 = percentile(durations, 90)
    p95 = percentile(durations, 95)
    p99 = percentile(durations, 99)
    throughput = round(total_requests / total_time, 2) if total_time > 0 else 0.0

    # Per-endpoint breakdown
    by_endpoint = {}
    for e in endpoints:
        ep_name = e["name"]
        ep_durs = sorted(r["duration_ms"] for r in results if r["endpoint"] == ep_name)
        if ep_durs:
            by_endpoint[ep_name] = {
                "count": len(ep_durs),
                "p50_ms": percentile(ep_durs, 50),
                "p95_ms": percentile(ep_durs, 95),
                "mean_ms": round(statistics.mean(ep_durs), 2),
            }

    slo_read_p50 = p50 < 100.0
    slo_read_p95 = p95 < 250.0
    slo_error_rate = error_rate < 0.01

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "concurrency": concurrency,
        "total_requests": total_requests,
        "wall_time_seconds": round(total_time, 3),
        "throughput_rps": throughput,
        "error_count": errors,
        "error_rate": round(error_rate, 4),
        "latencies_ms": {
            "min": round(durations[0], 2) if durations else 0,
            "mean": round(statistics.mean(durations), 2) if durations else 0,
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
            "max": round(durations[-1], 2) if durations else 0,
        },
        "per_endpoint": by_endpoint,
        "slos": {
            "p50_under_100ms": {
                "target": "< 100ms",
                "actual": f"{p50}ms",
                "met": slo_read_p50,
            },
            "p95_under_250ms": {
                "target": "< 250ms",
                "actual": f"{p95}ms",
                "met": slo_read_p95,
            },
            "error_rate_under_1pct": {
                "target": "< 1%",
                "actual": f"{round(error_rate * 100, 2)}%",
                "met": slo_error_rate,
            },
        },
        "all_slos_met": slo_read_p50 and slo_read_p95 and slo_error_rate,
    }


def main():
    parser = argparse.ArgumentParser(description="AI Pulse load test harness.")
    parser.add_argument(
        "--concurrency", type=int, default=5, help="Number of concurrent workers."
    )
    parser.add_argument(
        "--requests", type=int, default=100, help="Total number of requests to execute."
    )
    parser.add_argument(
        "--output", type=Path, help="Optional path to write report JSON."
    )
    args = parser.parse_args()

    report = run_benchmark(args.concurrency, args.requests)
    report_json = json.dumps(report, indent=2)
    print(report_json)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_json + "\n", encoding="utf-8")

    sys.exit(0 if report["all_slos_met"] else 1)


if __name__ == "__main__":
    main()
