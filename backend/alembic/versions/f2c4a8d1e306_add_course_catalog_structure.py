"""add course catalog structure

Revision ID: f2c4a8d1e306
Revises: e7b3f1a6d205
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2c4a8d1e306"
down_revision: str | Sequence[str] | None = "e7b3f1a6d205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_chapters",
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_version_id"], ["course_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_chapters")),
        sa.UniqueConstraint("course_version_id", "order_index", name="uq_course_chapters_version_order"),
    )
    op.create_index(op.f("ix_course_chapters_course_version_id"), "course_chapters", ["course_version_id"])
    op.create_table(
        "course_lessons",
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["course_chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_version_id"], ["course_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_lessons")),
        sa.UniqueConstraint("chapter_id", "order_index", name="uq_course_lessons_chapter_order"),
    )
    op.create_index(op.f("ix_course_lessons_course_version_id"), "course_lessons", ["course_version_id"])
    op.create_table(
        "course_concepts",
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stable_key", sa.String(length=180), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_version_id"], ["course_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["course_lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_concepts")),
        sa.UniqueConstraint("course_version_id", "stable_key", name="uq_course_concepts_version_stable_key"),
        sa.UniqueConstraint("lesson_id", "order_index", name="uq_course_concepts_lesson_order"),
    )
    op.create_index(op.f("ix_course_concepts_course_version_id"), "course_concepts", ["course_version_id"])
    op.create_table(
        "concept_prerequisites",
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prerequisite_concept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["course_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prerequisite_concept_id"], ["course_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concept_prerequisites")),
        sa.UniqueConstraint("concept_id", "prerequisite_concept_id", name="uq_concept_prerequisites_pair"),
    )
    op.add_column("content_chunks", sa.Column("lesson_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_content_chunks_lesson_id_course_lessons", "content_chunks", "course_lessons", ["lesson_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_content_chunks_lesson_id"), "content_chunks", ["lesson_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_content_chunks_lesson_id"), table_name="content_chunks")
    op.drop_constraint("fk_content_chunks_lesson_id_course_lessons", "content_chunks", type_="foreignkey")
    op.drop_column("content_chunks", "lesson_id")
    op.drop_table("concept_prerequisites")
    op.drop_index(op.f("ix_course_concepts_course_version_id"), table_name="course_concepts")
    op.drop_table("course_concepts")
    op.drop_index(op.f("ix_course_lessons_course_version_id"), table_name="course_lessons")
    op.drop_table("course_lessons")
    op.drop_index(op.f("ix_course_chapters_course_version_id"), table_name="course_chapters")
    op.drop_table("course_chapters")
