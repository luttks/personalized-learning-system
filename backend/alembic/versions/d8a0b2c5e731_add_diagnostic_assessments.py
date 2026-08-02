"""add diagnostic assessments

Revision ID: d8a0b2c5e731
Revises: c7f9a1b4d620
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8a0b2c5e731"
down_revision: str | None = "c7f9a1b4d620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_assessments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "learner_course_profile_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("assessment_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["learner_course_profile_id"],
            ["learner_course_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["course_publications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_diagnostic_assessments_course_id", "diagnostic_assessments", ["course_id"]
    )
    op.create_index(
        "ix_diagnostic_assessments_user_id", "diagnostic_assessments", ["user_id"]
    )
    op.create_table(
        "diagnostic_attempts",
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["diagnostic_assessments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_diagnostic_attempts_user_idempotency"
        ),
    )
    op.create_index(
        "ix_diagnostic_attempts_assessment_id", "diagnostic_attempts", ["assessment_id"]
    )
    op.create_index(
        "ix_diagnostic_attempts_user_id", "diagnostic_attempts", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostic_attempts_user_id", table_name="diagnostic_attempts")
    op.drop_index(
        "ix_diagnostic_attempts_assessment_id", table_name="diagnostic_attempts"
    )
    op.drop_table("diagnostic_attempts")
    op.drop_index(
        "ix_diagnostic_assessments_user_id", table_name="diagnostic_assessments"
    )
    op.drop_index(
        "ix_diagnostic_assessments_course_id", table_name="diagnostic_assessments"
    )
    op.drop_table("diagnostic_assessments")
