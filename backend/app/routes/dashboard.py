from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, config
from ..auth import current_membership
from ..services.privacy import publish
from ..models import now

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def org_dashboard(
    org_id: int | None = None,
    m=Depends(current_membership),
    db: Session = Depends(get_db),
):
    if m.role != "admin":
        raise HTTPException(
            403, "This dashboard is available to organization admins only."
        )
    if org_id is not None and org_id != m.org_id:
        raise HTTPException(403, "You cannot view another organization's dashboard.")
    departments = (
        db.query(models.Department)
        .filter_by(org_id=m.org_id)
        .order_by(models.Department.name)
        .all()
    )
    completed = (
        db.query(models.Assessment, models.Membership)
        .join(
            models.Membership, models.Membership.id == models.Assessment.membership_id
        )
        .filter(
            models.Membership.org_id == m.org_id,
            models.Assessment.status == "completed",
        )
        .all()
    )
    ids = [a.id for a, _ in completed]
    rows = (
        db.query(models.Response).filter(models.Response.assessment_id.in_(ids)).all()
        if ids
        else []
    )
    by_assessment = {}
    for row in rows:
        by_assessment.setdefault(row.assessment_id, []).append(row)
    groups = {d.id: {"name": d.name, "people": []} for d in departments}
    # Row presence must depend on membership, never on who has answered.
    has_unassigned_members = any(
        department_id not in groups
        for (department_id,) in db.query(models.Membership.department_id)
        .filter_by(org_id=m.org_id)
        .distinct()
        .all()
    )
    groups[None] = {"name": "Unassigned", "people": []}
    for assessment, member in completed:
        answers = by_assessment.get(assessment.id, [])
        expected = {q["id"] for q in assessment.question_snapshot}
        # Defend the publication boundary even if a row was damaged outside normal submission.
        if (
            {r.question_id for r in answers} != expected
            or not answers
            or any(r.score is None or not 1 <= r.score <= 5 for r in answers)
        ):
            continue
        groups.get(member.department_id, groups[None])["people"].append(
            {
                "demo": assessment.ai_mode == "mock",
                "average": sum(r.score for r in answers) / len(answers),
                "flags": [f for r in answers for f in (r.flags or [])],
            }
        )
    if not has_unassigned_members:
        del groups[None]
    return {
        "organization": m.org.name,
        "departments": publish(list(groups.values())),
        "minimum_group_size": config.MIN_GROUP_SIZE,
        "ai_mode": config.AI_MODE,
        "contains_demo_data": any(
            p["demo"]
            for g in groups.values()
            if len(g["people"]) >= config.MIN_GROUP_SIZE
            for p in g["people"]
        ),
        "updated_at": now(),
        "privacy_note": "Only completed assessments contribute. Small groups are protected. Exact risk counts require at least five people with the signal and five without. No company total is published.",
    }
