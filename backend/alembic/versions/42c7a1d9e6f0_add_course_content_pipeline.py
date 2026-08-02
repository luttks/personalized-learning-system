"""add course content pipeline

Revision ID: 42c7a1d9e6f0
Revises: 8f3b1d2c4a5e
Create Date: 2026-07-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "42c7a1d9e6f0"
down_revision: str | Sequence[str] | None = "8f3b1d2c4a5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=150), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "grade_level >= 1 AND grade_level <= 12",
            name="course_grade_level_range",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_courses_owner_id", "courses", ["owner_id"])
    op.create_index("ix_courses_subject", "courses", ["subject"])

    op.create_table(
        "course_versions",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("failure_code", sa.String(length=80)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["course_id"], ["courses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id",
            "version_number",
            name="uq_course_versions_course_version_number",
        ),
    )
    op.create_index("ix_course_versions_course_id", "course_versions", ["course_id"])

    op.add_column("courses", sa.Column("published_version_id", sa.UUID()))
    op.create_foreign_key(
        "fk_courses_published_version_id_course_versions",
        "courses",
        "course_versions",
        ["published_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "documents",
        sa.Column("course_version_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint("size_bytes > 0", name="document_size_positive"),
        sa.ForeignKeyConstraint(
            ["course_version_id"],
            ["course_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_course_version_id", "documents", ["course_version_id"])

    op.create_table(
        "document_jobs",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(length=100)),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("error_detail", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="document_job_progress_range",
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name="document_job_retry_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_jobs_document_id", "document_jobs", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_jobs_document_id", table_name="document_jobs")
    op.drop_table("document_jobs")
    op.drop_index("ix_documents_course_version_id", table_name="documents")
    op.drop_table("documents")
    op.drop_constraint(
        "fk_courses_published_version_id_course_versions",
        "courses",
        type_="foreignkey",
    )
    op.drop_column("courses", "published_version_id")
    op.drop_index("ix_course_versions_course_id", table_name="course_versions")
    op.drop_table("course_versions")
    op.drop_index("ix_courses_subject", table_name="courses")
    op.drop_index("ix_courses_owner_id", table_name="courses")
    op.drop_table("courses")
