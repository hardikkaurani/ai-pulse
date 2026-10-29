"""Adopt the starter schema and add versioned assessments without deleting legacy answers."""

from alembic import op
import sqlalchemy as sa

revision = "001_pilot"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if "organizations" not in existing:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
        )
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False
            ),
            sa.Column("name", sa.String(80), nullable=False),
        )
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("email", sa.String(200), nullable=False, unique=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("password_hash", sa.String(200), nullable=False),
        )
        op.create_table(
            "memberships",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False
            ),
            sa.Column("department_id", sa.Integer, sa.ForeignKey("departments.id")),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("job_role", sa.String(40), nullable=False),
            sa.Column("seniority", sa.String(20), nullable=False),
        )
        op.create_table(
            "responses",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "membership_id",
                sa.Integer,
                sa.ForeignKey("memberships.id"),
                nullable=False,
            ),
            sa.Column("question_id", sa.String(40), nullable=False),
            sa.Column("answer", sa.Text, nullable=False),
            sa.Column("score", sa.Float),
            sa.Column("reason", sa.Text),
            sa.Column("flags", sa.JSON),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
    elif (
        not {"organizations", "departments", "users", "memberships", "responses"}
        <= existing
    ):
        raise RuntimeError(
            "Incomplete legacy schema. Back up and repair it before migration."
        )
    # Unique indexes avoid rebuilding referenced SQLite tables with foreign keys enabled.
    op.add_column(
        "memberships",
        sa.Column("revision", sa.Integer, server_default="0", nullable=False),
    )
    op.create_index(
        "uq_membership_user_org", "memberships", ["user_id", "org_id"], unique=True
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "membership_id",
            sa.Integer,
            sa.ForeignKey("memberships.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("question_version", sa.String(64), nullable=False),
        sa.Column("question_snapshot", sa.JSON, nullable=False),
        sa.Column("ai_mode", sa.String(10), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("error", sa.String(80)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    # SQLite supports nullable REFERENCES columns through ADD COLUMN without recreating the table.
    if bind.dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE responses ADD COLUMN assessment_id VARCHAR(36) REFERENCES assessments(id) ON DELETE CASCADE"
        )
    else:
        op.add_column("responses", sa.Column("assessment_id", sa.String(36)))
        op.create_foreign_key(
            "fk_response_assessment",
            "responses",
            "assessments",
            ["assessment_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_responses_assessment_id", "responses", ["assessment_id"])
    op.create_index(
        "uq_response_question",
        "responses",
        ["assessment_id", "question_id"],
        unique=True,
    )
    op.create_table(
        "actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "assessment_id",
            sa.String(36),
            sa.ForeignKey("assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("due_date", sa.Date),
        sa.Column("done", sa.Boolean, nullable=False),
        sa.UniqueConstraint("assessment_id", "key", name="uq_action_key"),
    )
    op.create_index("ix_actions_assessment_id", "actions", ["assessment_id"])


def downgrade():
    raise RuntimeError(
        "This migration preserves legacy data. Restore a verified backup to roll back; automatic downgrade would lose assessments."
    )
