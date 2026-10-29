from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, config
from ..auth import (
    verify_password,
    make_token,
    current_user,
    hasher,
    hash_password,
    DUMMY_HASH,
)

from ..services.rate_limit import rate_limit, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class SelectOrgIn(BaseModel):
    org_id: int = Field(gt=0, strict=True)


def user_info(user):
    return {
        "name": user.name,
        "email": user.email,
        "ai_mode": config.AI_MODE,
        "organizations": [
            {
                "org_id": m.org_id,
                "org_name": m.org.name,
                "role": m.role,
                "job_role": m.job_role,
                "seniority": m.seniority,
            }
            for m in user.memberships
        ],
    }


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit("login:" + client_ip(request))
    user = db.query(models.User).filter_by(email=body.email.strip().lower()).first()
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    if not user.password_hash.startswith("$argon2") or hasher.check_needs_rehash(
        user.password_hash
    ):
        user.password_hash = hash_password(body.password)
        db.commit()
    return {"token": make_token(user.id), **user_info(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    return user_info(user)


@router.post("/select-org")
def select_org(
    body: SelectOrgIn, user=Depends(current_user), db: Session = Depends(get_db)
):
    m = (
        db.query(models.Membership)
        .filter_by(user_id=user.id, org_id=body.org_id)
        .first()
    )
    if not m:
        raise HTTPException(403, "You are not a member of this organization.")
    return {"token": make_token(user.id, m.org_id), "org_id": m.org_id, "role": m.role}
