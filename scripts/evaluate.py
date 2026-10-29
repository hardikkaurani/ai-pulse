"""Versioned, reproducible evaluation harness for AI Pulse scoring.

Supports calibration, held-out splits, per-class confusion matrix, precision/recall/F1,
score MAE, invalid-output rates, and failure tracking.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ALLOWED_FLAGS = [
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
]


def load_cases(split: str = "calibration") -> list[dict]:
    eval_dir = ROOT / "backend/evals"
    if split == "calibration":
        path = eval_dir / "cases.json"
        return json.loads(path.read_text(encoding="utf-8"))
    elif split == "holdout":
        path = eval_dir / "holdout_cases.json"
        return json.loads(path.read_text(encoding="utf-8"))
    elif split == "all":
        cal = json.loads((eval_dir / "cases.json").read_text(encoding="utf-8"))
        hold = json.loads((eval_dir / "holdout_cases.json").read_text(encoding="utf-8"))
        return cal + hold
    raise ValueError(f"Unknown split: {split}")


def compute_metrics(results: list[dict], cases: list[dict]) -> dict:
    cases_by_id = {c["id"]: c for c in cases}
    total = len(results)
    valid_count = sum(1 for r in results if r.get("valid"))
    invalid_count = total - valid_count

    # Per-class risk statistics
    class_stats = {flag: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for flag in ALLOWED_FLAGS}

    score_diffs = []
    score_in_range_count = 0
    exact_risk_matches = 0

    for r in results:
        cid = r["case"]
        expected = cases_by_id[cid]
        if not r.get("valid"):
            continue

        pred_score = r["score"]
        exp_min = expected["score_min"]
        exp_max = expected["score_max"]
        target_mid = (exp_min + exp_max) / 2.0
        score_diffs.append(abs(pred_score - target_mid))

        if exp_min <= pred_score <= exp_max:
            score_in_range_count += 1

        pred_flags = set(r.get("flags", []))
        exp_flags = set(expected.get("flags", []))

        if pred_flags == exp_flags:
            exact_risk_matches += 1

        for flag in ALLOWED_FLAGS:
            is_pred = flag in pred_flags
            is_exp = flag in exp_flags
            if is_pred and is_exp:
                class_stats[flag]["tp"] += 1
            elif is_pred and not is_exp:
                class_stats[flag]["fp"] += 1
            elif not is_pred and is_exp:
                class_stats[flag]["fn"] += 1
            else:
                class_stats[flag]["tn"] += 1

    per_class = {}
    f1_sum = 0.0
    for flag, s in class_stats.items():
        tp, fp, fn, tn = s["tp"], s["fp"], s["fn"], s["tn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_sum += f1
        per_class[flag] = {
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    macro_f1 = round(f1_sum / len(ALLOWED_FLAGS), 4)
    mae = round(sum(score_diffs) / len(score_diffs), 4) if score_diffs else None

    return {
        "total_cases": total,
        "valid_outputs": valid_count,
        "invalid_output_rate": round(invalid_count / total, 4) if total > 0 else 0.0,
        "score_in_range_rate": round(score_in_range_count / valid_count, 4)
        if valid_count > 0
        else 0.0,
        "exact_risk_match_rate": round(exact_risk_matches / valid_count, 4)
        if valid_count > 0
        else 0.0,
        "score_mae": mae,
        "macro_f1": macro_f1,
        "per_class_risks": per_class,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate AI Pulse scoring reliability."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send examples to the configured model. Provider charges may apply.",
    )
    parser.add_argument(
        "--split",
        choices=["calibration", "holdout", "all"],
        default="calibration",
        help="Evaluation split to execute (default: calibration).",
    )
    parser.add_argument(
        "--output", type=Path, help="Optional path for the sanitized result JSON."
    )
    args = parser.parse_args()

    cases = load_cases(args.split)
    raw_bytes = json.dumps(cases, sort_keys=True).encode()
    dataset_hash = hashlib.sha256(raw_bytes).hexdigest()

    if not args.live:
        print(
            f"{len(cases)} synthetic cases available. No model calls made. Configure live mode and pass --live to evaluate."
        )
        raise SystemExit(0)

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
                    "flags": result["flags"],
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

    metrics = compute_metrics(results, cases)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": config.LLM_MODEL,
        "prompt_version": config.PROMPT_VERSION,
        "split": args.split,
        "dataset_sha256": dataset_hash,
        "metrics": metrics,
        "limitation": "Synthetic evaluation set. No measured domain or employment validity. Results reflect rubric adherence on isolated text snippets.",
        "results": results,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    all_matched = all(r.get("score_in_range") and r.get("flags_exact") for r in results)
    raise SystemExit(0 if all_matched else 1)


if __name__ == "__main__":
    main()
