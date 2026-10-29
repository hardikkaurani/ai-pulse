"""Small synthetic live-model smoke evaluation, not a validated benchmark."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--live",
    action="store_true",
    help="Send 10 synthetic examples to the configured model. Provider charges may apply.",
)
parser.add_argument(
    "--output", type=Path, help="Optional path for the sanitized result JSON."
)
args = parser.parse_args()
cases = json.loads((ROOT / "backend/evals/cases.json").read_text(encoding="utf-8"))
if not args.live:
    print(
        f"{len(cases)} synthetic cases available. No model calls made. Configure live mode and pass --live to evaluate."
    )
    raise SystemExit(0)
sys.path.insert(0, str(ROOT / "backend"))
from app import config
from app.services.scoring import score_open_answer, ScoringUnavailable

if config.AI_MODE != "live":
    raise SystemExit(
        "Refusing semantic evaluation in mock mode. Configure backend/.env with AI_MODE=live first."
    )
results = []
for case in cases:
    started = time.monotonic()
    try:
        result = score_open_answer(
            "Describe your recent use of AI at work.", case["answer"]
        )
        actual, expected = set(result["flags"]), set(case["flags"])
        results.append(
            {
                "case": case["id"],
                "valid": True,
                "score": result["score"],
                "score_in_range": case["score_min"]
                <= result["score"]
                <= case["score_max"],
                "flags_exact": actual == expected,
                "missing_flags": sorted(expected - actual),
                "extra_flags": sorted(actual - expected),
                "seconds": round(time.monotonic() - started, 2),
            }
        )
    except ScoringUnavailable as exc:
        results.append(
            {
                "case": case["id"],
                "valid": False,
                "error": str(exc),
                "seconds": round(time.monotonic() - started, 2),
            }
        )
    print(json.dumps(results[-1]))
summary = {
    "model": config.LLM_MODEL,
    "prompt_version": config.PROMPT_VERSION,
    "cases": len(cases),
    "valid_outputs": sum(r["valid"] for r in results),
    "score_matches": sum(r.get("score_in_range", False) for r in results),
    "exact_risk_matches": sum(r.get("flags_exact", False) for r in results),
    "limitation": "Small author-written smoke set. No external validation or measured employment validity.",
    "results": results,
}
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
raise SystemExit(
    0 if all(r.get("score_in_range") and r.get("flags_exact") for r in results) else 1
)
