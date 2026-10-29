from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..services.questions import questions_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

PRIVACY_THRESHOLD = 5


def level_for(avg: float | None) -> str:
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


def compute_dashboard_aggregates(db: Session, target_org_id: int) -> dict:
    """Computes privacy-preserving department and organization aggregates.

    Privacy Rules:
    - Minimum threshold k = 5 completed respondents for individual department visibility.
    - Suppressed departments are excluded from individual view and risk rankings.
    - 'Other teams' aggregate is only formed if at least 2 small departments exist
      AND their combined completed respondents >= 5.
    """
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
        dept_flag_counts: dict[str, int] = {}

        for dm in dept_members:
            mem_responses = responses_by_mem_id.get(dm.id, [])
            is_complete, emp_avg, emp_flags = compute_member_diagnostic(dm, mem_responses)
            if is_complete and emp_avg is not None:
                completed_scores.append(emp_avg)
                dept_flags.extend(emp_flags)
                for f in emp_flags:
                    dept_flag_counts[f] = dept_flag_counts.get(f, 0) + 1

        completed_count = len(completed_scores)
        dept_avg = (
            sum(completed_scores) / completed_count
            if completed_count > 0
            else None
        )

        dept_summary = {
            "id": dept.id,
            "department": dept.name,
            "employees": len(dept_members),
            "completed": completed_count,
            "responded": completed_count,
            "average_score": round(dept_avg, 2) if dept_avg is not None else None,
            "level": level_for(dept_avg),
            "risk_counts": dept_flag_counts,
            "_flags": dept_flags,
            "_completed_scores": completed_scores,
        }

        if completed_count >= PRIVACY_THRESHOLD:
            # Department satisfies threshold: individually visible
            qualifying_departments.append(dept_summary)
            for f in dept_flags:
                qualifying_flags[f] = qualifying_flags.get(f, 0) + 1
        else:
            # Department is below privacy threshold: suppressed
            small_departments_data.append(dept_summary)

    # Other teams aggregation
    total_small_completed = sum(d["completed"] for d in small_departments_data)
    total_small_employees = sum(d["employees"] for d in small_departments_data)
    all_small_scores = [s for d in small_departments_data for s in d["_completed_scores"]]

    other_flag_counts: dict[str, int] = {}
    if len(small_departments_data) >= 2 and total_small_completed >= PRIVACY_THRESHOLD:
        other_avg = sum(all_small_scores) / len(all_small_scores) if all_small_scores else None
        for d in small_departments_data:
            for f, count in d.get("risk_counts", {}).items():
                other_flag_counts[f] = other_flag_counts.get(f, 0) + count

        other_summary = {
            "id": "other",
            "department": "Other teams",
            "employees": total_small_employees,
            "completed": total_small_completed,
            "responded": total_small_completed,
            "average_score": round(other_avg, 2) if other_avg is not None else None,
            "level": level_for(other_avg),
            "risk_counts": other_flag_counts,
        }
        qualifying_departments.append(other_summary)
        for d in small_departments_data:
            for f in d["_flags"]:
                qualifying_flags[f] = qualifying_flags.get(f, 0) + 1

    formatted_departments = [
        {
            "id": d.get("id"),
            "department": d["department"],
            "employees": d["employees"],
            "responded": d["responded"],
            "average_score": d["average_score"],
            "level": d["level"],
            "risk_counts": d.get("risk_counts", {}),
        }
        for d in qualifying_departments
    ]

    return {
        "organization": org.name,
        "departments": formatted_departments,
        "top_risks": sorted(qualifying_flags.items(), key=lambda kv: -kv[1])[:5],
        "hidden_small_groups": len(small_departments_data) > 0,
    }


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

    return compute_dashboard_aggregates(db, target_org_id)
