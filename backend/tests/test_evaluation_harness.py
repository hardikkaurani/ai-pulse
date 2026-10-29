"""Unit and integration tests for AI evaluation harness and metric computation."""

from pathlib import Path
import sys
import pytest

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.services.scoring import parse_result, ScoringUnavailable  # noqa: E402
from scripts.evaluate import compute_metrics, load_cases  # noqa: E402


def test_load_cases_splits():
    cal = load_cases("calibration")
    assert len(cal) == 10
    hold = load_cases("holdout")
    assert len(hold) == 12
    all_cases = load_cases("all")
    assert len(all_cases) == 22


def test_compute_metrics_accuracy_and_f1():
    cases = [
        {"id": "c1", "score_min": 4, "score_max": 4, "flags": ["customer_data_shared"]},
        {"id": "c2", "score_min": 2, "score_max": 2, "flags": []},
        {"id": "c3", "score_min": 3, "score_max": 3, "flags": ["unreviewed_output"]},
        {
            "id": "c4",
            "score_min": 5,
            "score_max": 5,
            "flags": ["confidential_data_shared", "policy_unaware"],
        },
    ]
    results = [
        {"case": "c1", "valid": True, "score": 4, "flags": ["customer_data_shared"]},
        {"case": "c2", "valid": True, "score": 2, "flags": []},
        {"case": "c3", "valid": True, "score": 3, "flags": ["unreviewed_output"]},
        {
            "case": "c4",
            "valid": True,
            "score": 5,
            "flags": ["confidential_data_shared", "policy_unaware"],
        },
    ]
    m = compute_metrics(results, cases)
    assert m["total_cases"] == 4
    assert m["valid_outputs"] == 4
    assert m["invalid_output_rate"] == 0.0
    assert m["score_in_range_rate"] == 1.0
    assert m["exact_risk_match_rate"] == 1.0
    assert m["score_mae"] == 0.0
    assert m["macro_f1"] == 1.0
    for flag in [
        "customer_data_shared",
        "unreviewed_output",
        "confidential_data_shared",
        "policy_unaware",
    ]:
        assert m["per_class_risks"][flag]["f1"] == 1.0
        assert m["per_class_risks"][flag]["confusion"]["tp"] == 1
        assert m["per_class_risks"][flag]["confusion"]["fp"] == 0
        assert m["per_class_risks"][flag]["confusion"]["fn"] == 0


def test_compute_metrics_with_discrepancies_and_invalids():
    cases = [
        {"id": "c1", "score_min": 4, "score_max": 4, "flags": ["customer_data_shared"]},
        {"id": "c2", "score_min": 2, "score_max": 2, "flags": []},
    ]
    results = [
        # Predicted wrong flag and score out of range (score 2 instead of 4)
        {"case": "c1", "valid": True, "score": 2, "flags": ["unreviewed_output"]},
        # Invalid / failed provider output
        {"case": "c2", "valid": False, "error": "provider_unavailable"},
    ]
    m = compute_metrics(results, cases)
    assert m["total_cases"] == 2
    assert m["valid_outputs"] == 1
    assert m["invalid_output_rate"] == 0.5
    assert m["score_mae"] == 2.0  # |2 - 4| = 2.0
    # Customer data shared had 1 FN, 0 TP
    assert m["per_class_risks"]["customer_data_shared"]["confusion"]["fn"] == 1
    assert m["per_class_risks"]["customer_data_shared"]["f1"] == 0.0
    # Unreviewed output had 1 FP, 0 TP
    assert m["per_class_risks"]["unreviewed_output"]["confusion"]["fp"] == 1
    assert m["per_class_risks"]["unreviewed_output"]["f1"] == 0.0


def test_adversarial_and_malformed_rejection():
    malformed_payloads = [
        "",  # empty
        "   ",  # whitespace
        "Not json",  # plain text
        '{"score": 6, "reason": "High", "flags": []}',  # score > 5
        '{"score": 0, "reason": "Zero", "flags": []}',  # score < 1
        '{"score": "4", "reason": "String", "flags": []}',  # string score
        '{"score": true, "reason": "Bool", "flags": []}',  # bool score
        '{"score": 4, "reason": "", "flags": []}',  # empty reason
        '{"score": 4, "reason": "   ", "flags": []}',  # whitespace reason
        '{"score": 4, "reason": "Valid", "flags": ["unknown_risk"]}',  # invalid flag
        '{"score": 4, "reason": "Valid", "flags": ["customer_data_shared", "customer_data_shared"]}',  # duplicate flag
        '{"score": 4, "reason": "Valid", "flags": [], "injected": true}',  # unknown extra property
        '{"score": 4, "score": 3, "reason": "Valid", "flags": []}',  # duplicate json key
        '~~~json\n{"score": 4, "reason": "Valid", "flags": []}\n~~~',  # tilde fence
    ]
    for raw in malformed_payloads:
        with pytest.raises(ScoringUnavailable):
            parse_result(raw)


def test_fenced_json_is_safely_parsed():
    fenced = '```json\n{"score": 4, "reason": "Verified valid.", "flags": ["policy_unaware"]}\n```'
    parsed = parse_result(fenced)
    assert parsed["score"] == 4
    assert parsed["reason"] == "Verified valid."
    assert parsed["flags"] == ["policy_unaware"]
