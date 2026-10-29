"""One publication policy shared by every leadership view. K is a minimum, not anonymity proof."""

from collections import Counter
from ..config import MIN_GROUP_SIZE
from ..utils import maturity_level
from .llm import ALLOWED_FLAGS

RISK_LABELS = {
    "customer_data_shared": "Customer information shared",
    "confidential_data_shared": "Confidential information shared",
    "unreviewed_output": "AI output used without review",
    "policy_unaware": "Uncertainty about AI policy",
}


def publish(departments):
    """Input groups contain completed people only, each with their own average and unique flags."""
    published = []
    for department in departments:
        people = department["people"]
        if len(people) < MIN_GROUP_SIZE:
            published.append(
                {
                    "department": department["name"],
                    "protected": True,
                    "responded": None,
                    "average_score": None,
                    "level": None,
                    "risks": [],
                    "message": "Results are protected until at least 5 people complete the assessment.",
                }
            )
            continue
        avg = round(sum(p["average"] for p in people) / len(people), 2)
        counts = Counter(flag for person in people for flag in set(person["flags"]))
        # A published total also reveals its complement. Protect both sides,
        # including zero/all, and keep every category present in a fixed order.
        risks = [
            {
                "key": flag,
                "label": RISK_LABELS[flag],
                "people": (
                    counts[flag]
                    if counts[flag] >= MIN_GROUP_SIZE
                    and len(people) - counts[flag] >= MIN_GROUP_SIZE
                    else None
                ),
            }
            for flag in ALLOWED_FLAGS
        ]
        published.append(
            {
                "department": department["name"],
                "protected": False,
                "responded": len(people),
                "average_score": avg,
                "level": maturity_level(avg),
                "risks": risks,
            }
        )
    # No company-wide score or totals: subtracting visible groups must not reveal hidden groups.
    return published
