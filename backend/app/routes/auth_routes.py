from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import verify_password, hash_password, make_token, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class SelectOrgIn(BaseModel):
    org_id: int


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """Authenticate with email and password, issuing an unscoped user token."""
    user = db.query(models.User).filter_by(email=body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")

    # Transparent security upgrade: migrate legacy unsalted hash to bcrypt upon successful auth
    if not user.password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        user.password_hash = hash_password(body.password)
        db.commit()

    orgs = [
        {"org_id": m.org_id, "org_name": m.org.name, "role": m.role}
        for m in user.memberships
    ]
    return {"token": make_token(user.id), "name": user.name, "organizations": orgs}


@router.post("/select-org")
def select_org(body: SelectOrgIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Verify organization membership and issue an organization-scoped session token."""
    membership = (
        db.query(models.Membership)
        .filter_by(user_id=user.id, org_id=body.org_id)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")

    return {
        "token": make_token(user.id, body.org_id),
        "org_id": body.org_id,
        "role": membership.role,
    }
