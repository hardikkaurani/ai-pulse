import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "questions.json")

SENIORITY_RANKS = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
}


def seniority_rank(seniority: str) -> int:
    """Return numeric rank for a seniority level; defaults to junior (1) if unknown."""
    if not isinstance(seniority, str):
        return 1
    return SENIORITY_RANKS.get(seniority.strip().lower(), 1)


def load_questions():
    with open(_PATH) as f:
        return json.load(f)


def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    result = []
    user_rank = seniority_rank(seniority)
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        min_required = q.get("min_seniority", "junior")
        if user_rank < seniority_rank(min_required):
            continue
        result.append(q)
    return result
