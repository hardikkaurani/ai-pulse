from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..services.questions import questions_for
from ..services.scoring import score_open_answer

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])

MAX_ANSWER_LENGTH = 2000
MIN_OPEN_ANSWER_LENGTH = 10
MAX_SUBMISSION_ANSWERS = 50


class AnswerIn(BaseModel):
    question_id: str = Field(..., max_length=100)
    answer: str = Field(..., max_length=MAX_ANSWER_LENGTH)


class SubmitIn(BaseModel):
    answers: list[AnswerIn] = Field(..., max_length=MAX_SUBMISSION_ANSWERS)


@router.get("/questions")
def get_questions(m: models.Membership = Depends(current_membership)):
    """Return only the questions configured for the authenticated member's job role and seniority."""
    qs = questions_for(m.job_role, m.seniority)
    # Never leak internal scoring points to the client
    return [
        {k: v for k, v in q.items() if k != "points"} | (
            {"options": [o["text"] for o in q["options"]]} if q["type"] == "mcq" else {}
        )
        for q in qs
    ]


@router.post("/submit")
def submit(body: SubmitIn, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    """Strictly validate, score, and atomically replace the employee's diagnostic assessment.

    Validation guarantees:
    - Exactly the assigned questions for the member's job role and seniority must be present.
    - No missing, unexpected, or duplicate question IDs.
    - Non-blank answers with minimum 10 characters for free text, and exact matching MCQ options.
    - All answers scored in memory before deleting or replacing existing responses.
    - Database replacement is fully atomic within a single transaction.
    """
    expected_questions = questions_for(m.job_role, m.seniority)
    expected_map = {q["id"]: q for q in expected_questions}
    expected_ids = set(expected_map.keys())

    # 1. Check for duplicates
    submitted_ids = [a.question_id for a in body.answers]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Duplicate question IDs found in submission."
        )

    # 2. Check exact question set match
    submitted_set = set(submitted_ids)
    if submitted_set != expected_ids:
        missing = expected_ids - submitted_set
        unexpected = submitted_set - expected_ids
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Missing required questions for your role and seniority: {', '.join(sorted(missing))}"
            )
        if unexpected:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unexpected question IDs for your role and seniority: {', '.join(sorted(unexpected))}"
            )

    # 3. Validate answers before any DB mutation or scoring
    for a in body.answers:
        q = expected_map[a.question_id]
        cleaned_answer = (a.answer or "").strip()
        if not cleaned_answer:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Answer for '{q['id']}' cannot be blank."
            )

        if q["type"] == "mcq":
            valid_options = [opt["text"] for opt in q.get("options", [])]
            if a.answer not in valid_options:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Invalid option for '{q['id']}'. Must match an assigned choice."
                )
        elif q["type"] == "open":
            if len(cleaned_answer) < MIN_OPEN_ANSWER_LENGTH:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Answer for '{q['id']}' must be at least {MIN_OPEN_ANSWER_LENGTH} characters."
                )

    # 4. Score all answers in memory before modifying DB
    staged_responses = []
    for a in body.answers:
        q = expected_map[a.question_id]
        cleaned_answer = a.answer.strip()
        if q["type"] == "mcq":
            option = next(o for o in q["options"] if o["text"] == a.answer)
            score = option["points"]
            reason = None
            flags = []
        else:
            try:
                result = score_open_answer(q["text"], cleaned_answer)
            except Exception as err:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    f"AI scoring service temporarily unavailable: {err}"
                )
            score = result["score"]
            reason = result["reason"]
            flags = result["flags"]

        staged_responses.append(
            models.Response(
                membership_id=m.id,
                question_id=q["id"],
                answer=cleaned_answer,
                score=score,
                reason=reason,
                flags=flags,
            )
        )

    # 5. Atomic replacement transaction: delete previous responses and persist new ones
    try:
        db.query(models.Response).filter_by(membership_id=m.id).delete(synchronize_session=False)
        for resp in staged_responses:
            db.add(resp)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to save diagnostic responses atomically."
        ) from exc

    return {"saved": len(body.answers)}


@router.delete("/my-data")
def delete_my_diagnostic(m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    """Delete all diagnostic answers for the authenticated employee's active membership."""
    try:
        deleted_count = (
            db.query(models.Response)
            .filter_by(membership_id=m.id)
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
        "message": "All diagnostic answers deleted successfully",
    }
