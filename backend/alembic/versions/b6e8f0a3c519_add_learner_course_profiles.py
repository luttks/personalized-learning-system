"""add learner course profiles

Revision ID: b6e8f0a3c519
Revises: a5d7e9f2b408
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6e8f0a3c519"
down_revision: str | None = "a5d7e9f2b408"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_course_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_ids_json", sa.JSON(), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer(), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("available_periods", sa.JSON(), nullable=False),
        sa.Column("content_formats", sa.JSON(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("deadline >= start_date", name="learner_course_profile_date_order"),
        sa.CheckConstraint("days_per_week >= 1 AND days_per_week <= 7", name="learner_course_profile_days_range"),
        sa.CheckConstraint("minutes_per_day >= 10 AND minutes_per_day <= 600", name="learner_course_profile_minutes_range"),
        sa.CheckConstraint("profile_version >= 1", name="learner_course_profile_version_positive"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publication_id"], ["course_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_learner_course_profiles_user_course"),
    )
    op.create_index("ix_learner_course_profiles_course_id", "learner_course_profiles", ["course_id"])
    op.create_index("ix_learner_course_profiles_user_id", "learner_course_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_learner_course_profiles_user_id", table_name="learner_course_profiles")
    op.drop_index("ix_learner_course_profiles_course_id", table_name="learner_course_profiles")
    op.drop_table("learner_course_profiles")
