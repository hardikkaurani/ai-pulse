from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from ..db import get_db
from ..auth import current_membership
from ..services.questions import questions_for
from ..services import assessments
from ..services.rate_limit import rate_limit

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=2000)


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[AnswerIn] = Field(min_length=1, max_length=30)


@router.get("/questions")
def get_questions(m=Depends(current_membership)):
    return [
        {
            "id": q["id"],
            "type": q["type"],
            "text": q["text"],
            "options": [o["text"] for o in q.get("options", [])],
        }
        for q in questions_for(m.job_role, m.seniority)
    ]


@router.post("/submit")
def submit(
    body: SubmitIn, m=Depends(current_membership), db: Session = Depends(get_db)
):
    rate_limit("score:" + str(m.user_id))
    assessment_id, created = assessments.save_submission(db, m, body.answers)
    if created:
        assessments.score_saved(db, assessment_id, m.id)
    db.expire_all()
    saved = assessments.current(db, m.id)
    if not saved or saved.id != assessment_id:
        raise HTTPException(
            409, "This assessment was replaced or deleted in another request."
        )
    return {"assessment_id": saved.id, "status": saved.status, "reused": not created}


@router.post("/retry")
def retry(m=Depends(current_membership), db: Session = Depends(get_db)):
    rate_limit("score:" + str(m.user_id))
    saved = assessments.current(db, m.id)
    if not saved:
        raise HTTPException(404, "No assessment to retry.")
    assessments.score_saved(db, saved.id, m.id)
    db.expire_all()
    saved = assessments.current(db, m.id)
    if not saved:
        raise HTTPException(404, "This assessment was deleted.")
    return {"status": saved.status}
