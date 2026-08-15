"""add subject and file_path to exam_analyses

Revision ID: a8f3b2c1d490
Revises: 5b133fef9d1b
Create Date: 2026-08-13 04:40:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a8f3b2c1d490"
down_revision: str | None = "5b133fef9d1b"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_analyses",
        sa.Column("subject", sa.String(255), nullable=True),
    )
    op.add_column(
        "exam_analyses",
        sa.Column("file_path", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_analyses", "file_path")
    op.drop_column("exam_analyses", "subject")
