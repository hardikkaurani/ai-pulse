"""Small, curated activities. No extra AI call, and completion never changes a score."""

from datetime import date, timedelta
from .. import models

CATALOG = {
    "data": {
        "title": "Practise a safer prompt",
        "minutes": 10,
        "source": "common-data",
        "why": "Your answer suggests there is room to strengthen how you protect sensitive information.",
        "steps": [
            "Write a fictional customer ticket. Use invented names and details only.",
            "Replace names, account details and identifying context with neutral placeholders.",
            "Check whether the prompt still contains enough information to help with the task.",
        ],
        "success": "You can explain what you removed and why. Use only company-approved tools.",
    },
    "review": {
        "title": "Build your three-check habit",
        "minutes": 15,
        "source": "common-review",
        "why": "Your answer suggests that reviewing AI output could become a more consistent habit.",
        "steps": [
            "Create a short AI draft about a non-sensitive topic relevant to your role.",
            "Pick three factual claims and check each against a reliable source.",
            "Correct the draft and identify one check you will repeat next time.",
        ],
        "success": "Three claims checked, corrections made, and a reusable review habit identified.",
    },
    "policy": {
        "title": "Find your team's AI ground rules",
        "minutes": 10,
        "source": "common-policy",
        "why": "Your answer indicates uncertainty about your organization's AI policy.",
        "steps": [
            "Locate the current company AI policy or ask the policy owner where to find it.",
            "Identify which tools and data types are permitted.",
            "Write one question to clarify with the policy owner; keep it outside this app.",
        ],
        "success": "You know where the policy lives and which tools are approved, or know who to ask.",
    },
    "practice": {
        "title": "Try one small, reviewed workflow",
        "minutes": 15,
        "source": "common-freq",
        "why": "A small, reviewed experiment helps you decide where AI is useful in your work.",
        "steps": [
            "Choose a routine task and create fictional input with no private information.",
            "Use an approved AI tool to make a first draft.",
            "Check and edit the result. Decide whether the workflow was actually useful.",
        ],
        "success": "One reviewed example and a clear decision about whether to use the workflow again.",
    },
}
ROLE_TASKS = {
    "support": "a fictional support reply",
    "engineering": "tests for a small sample function",
    "sales": "a fictional outreach email",
    "manager": "a meeting agenda using invented topics",
}


def recommendations(rows, role):
    scores = {r.question_id: r.score for r in rows}
    flags = {f for r in rows for f in (r.flags or [])}
    picks = []
    rules = [
        ("data", "customer_data_shared"),
        ("review", "unreviewed_output"),
        ("policy", "policy_unaware"),
    ]
    for key, risk in rules:
        if (
            scores.get(CATALOG[key]["source"], 5) <= 3
            or risk in flags
            or (key == "data" and "confidential_data_shared" in flags)
        ):
            picks.append(key)
    if not picks or scores.get("common-freq", 5) <= 2:
        picks.append("practice")
    return picks[:3]


def describe(action, role):
    item = CATALOG[action.key]
    return {
        "id": action.id,
        "key": action.key,
        **item,
        "role_example": ROLE_TASKS.get(role, ROLE_TASKS["manager"]),
        "due_date": action.due_date,
        "done": action.done,
    }


def create_plan(db, assessment, rows, role):
    for key in recommendations(rows, role):
        db.add(
            models.Action(
                assessment_id=assessment.id,
                key=key,
                due_date=date.today() + timedelta(days=7),
                done=False,
            )
        )
