from datetime import datetime, timezone, date
from uuid import uuid4
from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
    DateTime,
    Text,
    Float,
    JSON,
    UniqueConstraint,
    Boolean,
    Date,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    departments = relationship("Department", back_populates="org")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(80))
    org = relationship("Organization", back_populates="departments")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    memberships = relationship("Membership", back_populates="user")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20))
    job_role: Mapped[str] = mapped_column(String(40))
    seniority: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    user = relationship("User", back_populates="memberships")
    org = relationship("Organization")
    department = relationship("Department")


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    fingerprint: Mapped[str] = mapped_column(String(64))
    question_version: Mapped[str] = mapped_column(String(64))
    question_snapshot: Mapped[list] = mapped_column(JSON)
    ai_mode: Mapped[str] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    responses = relationship(
        "Response", cascade="all, delete-orphan", passive_deletes=True
    )
    actions = relationship("Action", cascade="all, delete-orphan", passive_deletes=True)


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_id", name="uq_response_question"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id"))
    # Null preserves legacy answers without claiming that they form a completed assessment.
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    question_id: Mapped[str] = mapped_column(String(40))
    answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("assessment_id", "key", name="uq_action_key"),)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
