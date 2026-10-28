from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..services.questions import questions_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

PRIVACY_THRESHOLD = 5


def level_for(avg):
    if avg is None:
        return "Not assessed"
    if avg < 1.5:
        return "Beginner"
    if avg < 2.5:
        return "Exploring"
    if avg < 3.5:
        return "Practitioner"
    return "Leader"


def compute_member_diagnostic(m: models.Membership, rows: list[models.Response]):
    """
    Evaluates whether an employee has completed their diagnostic.
    Returns:
        (is_complete: bool, avg_score: float | None, flags: list[str])
    """
    expected_qs = questions_for(m.job_role, m.seniority)
    if not expected_qs:
        return False, None, []

    expected_ids = {q["id"] for q in expected_qs}

    # Deduplicate responses by question_id (taking the latest by id/created_at)
    latest_by_qid: dict[str, models.Response] = {}
    for r in sorted(rows, key=lambda x: (x.created_at, x.id) if x.created_at else (x.id,)):
        latest_by_qid[r.question_id] = r

    # Must have answered all expected questions with non-null scores
    scored_expected = {
        qid: latest_by_qid[qid].score
        for qid in expected_ids
        if qid in latest_by_qid and latest_by_qid[qid].score is not None
    }

    if len(scored_expected) < len(expected_ids):
        # Incomplete diagnostic (missing one or more expected questions)
        return False, None, []

    # Completed diagnostic: compute employee average score across expected questions
    scores = list(scored_expected.values())
    emp_avg = sum(scores) / len(scores)

    # Collect unique flags from completed responses
    emp_flags = []
    for qid in expected_ids:
        resp = latest_by_qid.get(qid)
        if resp and resp.flags:
            for f in resp.flags:
                if f and f not in emp_flags:
                    emp_flags.append(f)

    return True, emp_avg, emp_flags


@router.get("")
def org_dashboard(
    org_id: int | None = None,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    # Security: Ensure administrator can only access their authorized organization
    target_org_id = m.org_id
    if org_id is not None and org_id != m.org_id:
        raise HTTPException(403, "Not authorized for this organization")

    org = db.get(models.Organization, target_org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=target_org_id).all()

    # Pre-fetch all responses for members of this organization
    member_ids = [mem.id for mem in members]
    responses_by_mem_id: dict[int, list[models.Response]] = {mid: [] for mid in member_ids}
    if member_ids:
        all_responses = (
            db.query(models.Response)
            .filter(models.Response.membership_id.in_(member_ids))
            .all()
        )
        for r in all_responses:
            responses_by_mem_id[r.membership_id].append(r)

    qualifying_departments = []
    small_departments_data = []
    qualifying_flags: dict[str, int] = {}

    for dept in org.departments:
        dept_members = [x for x in members if x.department_id == dept.id]
        completed_scores = []
        dept_flags = []

        for dm in dept_members:
            mem_responses = responses_by_mem_id.get(dm.id, [])
            is_complete, emp_avg, emp_flags = compute_member_diagnostic(dm, mem_responses)
            if is_complete and emp_avg is not None:
                completed_scores.append(emp_avg)
                dept_flags.extend(emp_flags)

        completed_count = len(completed_scores)
        dept_avg = (
            sum(completed_scores) / completed_count
            if completed_count > 0
            else None
        )

        dept_summary = {
            "department": dept.name,
            "employees": len(dept_members),
            "completed": completed_count,
            "responded": completed_count,
            "average_score": round(dept_avg, 2) if dept_avg is not None else None,
            "level": level_for(dept_avg),
            "_flags": dept_flags,
            "_completed_scores": completed_scores,
        }

        if completed_count >= PRIVACY_THRESHOLD:
            # Department satisfies threshold: individually visible
            qualifying_departments.append(dept_summary)
            # Accumulate risk flags into organization top risks
            for f in dept_flags:
                qualifying_flags[f] = qualifying_flags.get(f, 0) + 1
        else:
            # Department is below privacy threshold: suppressed from individual view
            small_departments_data.append(dept_summary)

    # Privacy preservation for small departments:
    # An "Other teams" group is only created if:
    # 1. Total completed employees in the aggregate >= PRIVACY_THRESHOLD (5)
    # 2. It aggregates at least 2 distinct small departments (to prevent deanonymizing a single small team)
    total_small_completed = sum(d["completed"] for d in small_departments_data)
    total_small_employees = sum(d["employees"] for d in small_departments_data)
    all_small_scores = [s for d in small_departments_data for s in d["_completed_scores"]]

    if len(small_departments_data) >= 2 and total_small_completed >= PRIVACY_THRESHOLD:
        other_avg = sum(all_small_scores) / len(all_small_scores) if all_small_scores else None
        other_summary = {
            "department": "Other teams",
            "employees": total_small_employees,
            "completed": total_small_completed,
            "responded": total_small_completed,
            "average_score": round(other_avg, 2) if other_avg is not None else None,
            "level": level_for(other_avg),
        }
        qualifying_departments.append(other_summary)
        # Add flags from "Other teams" since the aggregate meets the threshold
        for d in small_departments_data:
            for f in d["_flags"]:
                qualifying_flags[f] = qualifying_flags.get(f, 0) + 1

    # Format department list, stripping internal calculation helpers
    formatted_departments = [
        {
            "department": d["department"],
            "employees": d["employees"],
            "responded": d["responded"],
            "average_score": d["average_score"],
            "level": d["level"],
        }
        for d in qualifying_departments
    ]

    return {
        "organization": org.name,
        "departments": formatted_departments,
        "top_risks": sorted(qualifying_flags.items(), key=lambda kv: -kv[1])[:5],
    }
