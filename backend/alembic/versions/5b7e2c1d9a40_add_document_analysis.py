"""add document analysis preview

Revision ID: 5b7e2c1d9a40
Revises: 42c7a1d9e6f0
Create Date: 2026-07-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b7e2c1d9a40"
down_revision: str | Sequence[str] | None = "42c7a1d9e6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_analyses",
        sa.Column("course_version_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_characters", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("structure_json", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("model", sa.String(length=150)),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("error_detail", sa.Text()),
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
            ["course_version_id"],
            ["course_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_version_id",
            name="uq_document_analysis_course_version",
        ),
    )
    op.create_index(
        "ix_document_analyses_course_version_id",
        "document_analyses",
        ["course_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_analyses_course_version_id",
        table_name="document_analyses",
    )
    op.drop_table("document_analyses")
