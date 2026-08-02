"""add course learning paths

Revision ID: e9b1c3d6f842
Revises: d8a0b2c5e731
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9b1c3d6f842"
down_revision: str | None = "d8a0b2c5e731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_learning_paths",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "learner_course_profile_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column(
            "diagnostic_attempt_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("path_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("required_mastery", sa.Float(), nullable=False),
        sa.Column("total_estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("mastery_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("gaps_json", sa.JSON(), nullable=False),
        sa.Column("skipped_json", sa.JSON(), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("generator", sa.String(100), nullable=False),
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
            ["diagnostic_attempt_id"], ["diagnostic_attempts.id"], ondelete="RESTRICT"
        ),
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
        sa.UniqueConstraint(
            "user_id",
            "course_id",
            "path_version",
            name="uq_course_learning_paths_user_course_version",
        ),
    )
    op.create_index(
        "ix_course_learning_paths_course_id", "course_learning_paths", ["course_id"]
    )
    op.create_index(
        "ix_course_learning_paths_user_id", "course_learning_paths", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_course_learning_paths_user_id", table_name="course_learning_paths"
    )
    op.drop_index(
        "ix_course_learning_paths_course_id", table_name="course_learning_paths"
    )
    op.drop_table("course_learning_paths")
