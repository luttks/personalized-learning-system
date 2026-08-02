"""add course publications

Revision ID: a5d7e9f2b408
Revises: f2c4a8d1e306
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a5d7e9f2b408"
down_revision: str | Sequence[str] | None = "f2c4a8d1e306"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_publications",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version_ids_json", sa.JSON(), nullable=False),
        sa.Column("quality_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("published_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unpublished_at", sa.DateTime(timezone=True)),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_publications")),
        sa.UniqueConstraint("course_id", "revision", name="uq_course_publications_course_revision"),
    )
    op.create_index(op.f("ix_course_publications_course_id"), "course_publications", ["course_id"])
    op.add_column("courses", sa.Column("active_publication_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_courses_active_publication_id_course_publications", "courses", "course_publications", ["active_publication_id"], ["id"], ondelete="SET NULL", use_alter=True)


def downgrade() -> None:
    op.drop_constraint("fk_courses_active_publication_id_course_publications", "courses", type_="foreignkey")
    op.drop_column("courses", "active_publication_id")
    op.drop_index(op.f("ix_course_publications_course_id"), table_name="course_publications")
    op.drop_table("course_publications")
