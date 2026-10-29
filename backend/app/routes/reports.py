from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_user, current_membership
from ..utils import maturity_level

router = APIRouter(prefix="/reports", tags=["reports"])

NEXT_STEPS = {
    "support": [
        "Use AI to draft initial ticket replies, then verify and edit before sending",
        "Summarise complex conversation threads prior to tier-2 escalation",
        "Never paste identifiable customer details or credentials into public tools",
    ],
    "engineering": [
        "Leverage code completion models for test generation and refactoring",
        "Perform mandatory human code review on every AI suggestion before merge",
        "Keep secrets, tokens, and proprietary infrastructure out of external prompts",
    ],
    "sales": [
        "Draft outreach messages with AI and personalise with authentic context",
        "Automate meeting summary extraction into CRM records",
        "Double-check AI-generated product claims and pricing before sending",
    ],
    "manager": [
        "Establish and communicate an explicit AI acceptable-use policy for your team",
        "Select one key workflow per quarter to enhance responsibly with AI",
        "Measure business outcome quality and time saved, not raw tool activity",
    ],
}


@router.get("")
def list_my_reports(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Lists saved diagnostic assessment reports across organizations where the user is an authorized member."""
    memberships = db.query(models.Membership).filter_by(user_id=user.id).all()
    results = []
    for m in memberships:
        rows = db.query(models.Response).filter_by(membership_id=m.id).all()
        if not rows:
            continue
        scores = [r.score for r in rows if r.score is not None]
        avg = sum(scores) / len(scores) if scores else None
        results.append({
            "org_id": m.org_id,
            "organization": m.org.name,
            "role": m.role,
            "answered": len(rows),
            "average_score": round(avg, 2) if avg is not None else None,
            "level": maturity_level(avg),
            "has_report": True,
        })
    return results


@router.get("/me")
def my_report(
    org_id: int | None = None,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    """Retrieve the personal diagnostic report for the authenticated employee's active organization."""
    target_m = m
    if org_id is not None and org_id != m.org_id:
        target_m = db.query(models.Membership).filter_by(user_id=m.user_id, org_id=org_id).first()
        if not target_m:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of the requested organization")

    rows = db.query(models.Response).filter_by(membership_id=target_m.id).all()
    scores = [r.score for r in rows if r.score is not None]
    avg = sum(scores) / len(scores) if scores else None
    flags = sorted({f for r in rows for f in (r.flags or [])})
    return {
        "name": target_m.user.name,
        "organization": target_m.org.name,
        "answered": len(rows),
        "average_score": round(avg, 2) if avg is not None else None,
        "level": maturity_level(avg),
        "risks": flags,
        "next_steps": NEXT_STEPS.get(target_m.job_role, NEXT_STEPS["manager"]) if rows else [],
    }


@router.delete("/me")
def delete_my_report(
    org_id: int | None = None,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    """Deletes all diagnostic answers and generated report data for the authenticated user's organization membership."""
    target_m = m
    if org_id is not None and org_id != m.org_id:
        target_m = db.query(models.Membership).filter_by(user_id=m.user_id, org_id=org_id).first()
        if not target_m:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of the requested organization")

    try:
        deleted_count = (
            db.query(models.Response)
            .filter_by(membership_id=target_m.id)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete diagnostic data"
        ) from exc

    return {
        "deleted": deleted_count,
        "message": "All diagnostic answers and report data deleted successfully",
    }
