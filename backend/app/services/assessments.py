"""An assessment has one owner, a stable question snapshot, and explicit scoring state."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import update, delete
from .. import models, config
from .questions import questions_for, question_version
from .scoring import score_open_answer, ScoringUnavailable
from .actions import create_plan


def utcnow():
    return datetime.now(timezone.utc)


def current(db, member_id):
    return db.query(models.Assessment).filter_by(membership_id=member_id).first()


def validate_answers(member, answers):
    questions = questions_for(member.job_role, member.seniority)
    by_id = {a.question_id: a.answer.strip() for a in answers}
    if len(by_id) != len(answers) or set(by_id) != {q["id"] for q in questions}:
        raise HTTPException(422, "Answer each assigned question exactly once.")
    for q in questions:
        answer = by_id[q["id"]]
        if q["type"] == "mcq" and answer not in [o["text"] for o in q["options"]]:
            raise HTTPException(422, "Choose a valid option for each question.")
        if q["type"] == "open" and not 10 <= len(answer) <= 2000:
            raise HTTPException(
                422, "Written answers must be between 10 and 2,000 characters."
            )
    return questions, by_id


def save_submission(db, member, answers):
    questions, by_id = validate_answers(member, answers)
    version = question_version()
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                version,
                config.PROMPT_VERSION,
                config.AI_MODE,
                config.LLM_MODEL if config.AI_MODE == "live" else "demo-fixture",
                by_id,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    member_id = member.id
    # Serialize writes for this member. No model request is made while holding this lock.
    changed = db.execute(
        update(models.Membership)
        .where(
            models.Membership.id == member_id,
            models.Membership.revision == member.revision,
        )
        .values(revision=models.Membership.revision + 1)
    ).rowcount
    if not changed:
        db.rollback()
        raise HTTPException(
            409,
            "Your assessment changed in another request. Refresh before submitting again.",
        )
    existing = current(db, member_id)
    if existing and existing.fingerprint == fingerprint:
        db.commit()
        return existing.id, False
    db.execute(
        delete(models.Assessment).where(models.Assessment.membership_id == member_id)
    )
    # Remove old unversioned responses too; the retake explicitly replaces the old assessment.
    db.execute(
        delete(models.Response).where(models.Response.membership_id == member_id)
    )
    assessment = models.Assessment(
        membership_id=member_id,
        status="pending",
        fingerprint=fingerprint,
        question_version=version,
        question_snapshot=questions,
        ai_mode=config.AI_MODE,
        model=config.LLM_MODEL if config.AI_MODE == "live" else "demo-fixture",
        prompt_version=config.PROMPT_VERSION,
    )
    db.add(assessment)
    db.flush()
    for q in questions:
        option = next(
            (o for o in q.get("options", []) if o["text"] == by_id[q["id"]]), None
        )
        db.add(
            models.Response(
                membership_id=member_id,
                assessment_id=assessment.id,
                question_id=q["id"],
                answer=by_id[q["id"]],
                score=option["points"] if option else None,
                reason="Scored using the published questionnaire rubric."
                if option
                else None,
                flags=[],
            )
        )
    assessment_id = assessment.id
    db.commit()
    return assessment_id, True


def score_saved(db, assessment_id, member_id):
    assessment = db.get(models.Assessment, assessment_id)
    if not assessment or assessment.membership_id != member_id:
        raise HTTPException(404, "This assessment was deleted or replaced.")
    if assessment.status == "completed":
        return
    active_model = config.LLM_MODEL if config.AI_MODE == "live" else "demo-fixture"
    if (assessment.ai_mode, assessment.model, assessment.prompt_version) != (
        config.AI_MODE,
        active_model,
        config.PROMPT_VERSION,
    ):
        raise HTTPException(
            409,
            "The scoring configuration changed. Retake the assessment to use the new configuration.",
        )
    claimed_at = utcnow()
    # Recover an abandoned request after a process interruption; active requests retain their lease.
    stale = utcnow().replace(tzinfo=None) - timedelta(seconds=60)
    claimed = db.execute(
        update(models.Assessment)
        .where(
            models.Assessment.id == assessment_id,
            (models.Assessment.status == "pending")
            | (
                (models.Assessment.status == "scoring")
                & (models.Assessment.updated_at < stale)
            ),
        )
        .values(status="scoring", error=None, updated_at=claimed_at)
    ).rowcount
    db.commit()
    if not claimed:
        return
    db.expire_all()
    assessment = db.get(models.Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "This assessment was deleted or replaced.")
    questions = assessment.question_snapshot
    rows = db.query(models.Response).filter_by(assessment_id=assessment_id).all()
    inputs = {r.question_id: r.answer for r in rows}
    # Release the read transaction before network I/O.
    db.commit()
    results = {}
    error = None
    try:
        for q in questions:
            if q["type"] == "open":
                results[q["id"]] = score_open_answer(q["text"], inputs[q["id"]])
    except ScoringUnavailable as exc:
        error = str(exc)
    # Conditional UPDATE is the write lock and existence check. A late result cannot recreate deletion.
    updated = db.execute(
        update(models.Assessment)
        .where(
            models.Assessment.id == assessment_id,
            models.Assessment.status == "scoring",
            models.Assessment.updated_at == claimed_at,
        )
        .values(
            status="pending" if error else "completed", error=error, updated_at=utcnow()
        )
    ).rowcount
    if not updated:
        db.rollback()
        raise HTTPException(404, "This assessment was deleted or replaced.")
    if not error:
        for qid, result in results.items():
            db.execute(
                update(models.Response)
                .where(
                    models.Response.assessment_id == assessment_id,
                    models.Response.question_id == qid,
                )
                .values(**result)
            )
        db.flush()
        member = db.get(models.Membership, member_id)
        assessment = db.get(models.Assessment, assessment_id)
        rows = db.query(models.Response).filter_by(assessment_id=assessment_id).all()
        db.execute(
            delete(models.Action).where(models.Action.assessment_id == assessment_id)
        )
        create_plan(db, assessment, rows, member.job_role)
    db.commit()
