from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update, delete
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models
from ..auth import current_membership
from ..utils import maturity_level
from ..services.assessments import current
from ..services.actions import describe
from ..services.privacy import RISK_LABELS

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/me")
def my_report(m=Depends(current_membership), db: Session = Depends(get_db)):
    assessment = current(db, m.id)
    base = {"name": m.user.name, "organization": m.org.name, "job_role": m.job_role}
    if not assessment:
        legacy = db.query(models.Response).filter_by(membership_id=m.id).count()
        return {
            **base,
            "status": "not_started",
            "legacy_answers": legacy,
            "actions": [],
        }
    rows = db.query(models.Response).filter_by(assessment_id=assessment.id).all()
    questions = {q["id"]: q for q in assessment.question_snapshot}
    rows.sort(key=lambda r: list(questions).index(r.question_id))
    complete = assessment.status == "completed"
    avg = (
        round(sum(r.score for r in rows) / len(rows), 2)
        if complete and rows and all(r.score is not None for r in rows)
        else None
    )
    flags = sorted({f for r in rows for f in (r.flags or [])})
    return {
        **base,
        "assessment_id": assessment.id,
        "status": assessment.status,
        "average_score": avg,
        "level": maturity_level(avg),
        "answered": len(rows),
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
        "ai_mode": assessment.ai_mode,
        "model": assessment.model,
        "question_version": assessment.question_version,
        "prompt_version": assessment.prompt_version,
        "scoring_note": "Each question has equal weight. This is a self-reported diagnostic, not a verified measure of job performance.",
        "risks": [
            {"key": f, "label": RISK_LABELS[f]} for f in flags if f in RISK_LABELS
        ],
        "answers": [
            {
                "question": questions[r.question_id]["text"],
                "question_id": r.question_id,
                "type": questions[r.question_id]["type"],
                "answer": r.answer,
                "score": r.score,
                "reason": r.reason,
                "flags": r.flags or [],
            }
            for r in rows
        ],
        "actions": [
            describe(a, m.job_role)
            for a in db.query(models.Action)
            .filter_by(assessment_id=assessment.id)
            .all()
        ],
        "error": assessment.error,
    }


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    done: bool
    due_date: date | None = Field(default=None, strict=False)


@router.patch("/me/actions/{action_id}")
def update_action(
    action_id: str,
    body: ActionIn,
    m=Depends(current_membership),
    db: Session = Depends(get_db),
):
    # Ownership is checked through the assessment, not a user ID supplied by the browser.
    action = (
        db.query(models.Action)
        .join(models.Assessment)
        .filter(models.Action.id == action_id, models.Assessment.membership_id == m.id)
        .first()
    )
    if not action:
        raise HTTPException(404, "Activity not found.")
    if body.due_date and not date.today() - timedelta(
        days=30
    ) <= body.due_date <= date.today() + timedelta(days=365):
        raise HTTPException(422, "Choose a target date within the next year.")
    action.done = body.done
    if "due_date" in body.model_fields_set:
        action.due_date = body.due_date
    db.commit()
    return describe(action, m.job_role)


@router.delete("/me")
def delete_my_data(
    scope: Literal["current", "all"] = "current",
    m=Depends(current_membership),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(models.Membership).filter_by(user_id=m.user_id).all()
        if scope == "all"
        else [m]
    )
    ids = [member.id for member in memberships]
    db.execute(
        update(models.Membership)
        .where(models.Membership.id.in_(ids))
        .values(revision=models.Membership.revision + 1)
    )
    count = (
        db.query(models.Response).filter(models.Response.membership_id.in_(ids)).count()
    )
    db.execute(delete(models.Response).where(models.Response.membership_id.in_(ids)))
    db.execute(
        delete(models.Assessment).where(models.Assessment.membership_id.in_(ids))
    )
    db.commit()  # cascades activities; no cached reports or raw-answer audit log to retain
    return {
        "deleted": True,
        "scope": scope,
        "answers_deleted": count,
        "organizations_affected": len(ids),
    }
