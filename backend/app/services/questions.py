import json
import os
import hashlib

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "questions.json")
RANK = {"junior": 0, "mid": 1, "senior": 2, "lead": 3}


def load_questions():
    with open(_PATH) as f:
        return json.load(f)


def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    if seniority not in RANK:
        raise ValueError("Unknown seniority")
    result = []
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        if RANK[seniority] < RANK[q.get("min_seniority", "junior")]:
            continue
        result.append(q)
    return result


def question_version():
    return hashlib.sha256(
        json.dumps(load_questions(), sort_keys=True).encode()
    ).hexdigest()[:12]
