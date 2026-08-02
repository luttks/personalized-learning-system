"""fix learner course profile timestamp defaults

Revision ID: c7f9a1b4d620
Revises: b6e8f0a3c519
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f9a1b4d620"
down_revision: str | None = "b6e8f0a3c519"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "learner_course_profiles",
        "created_at",
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "learner_course_profiles",
        "updated_at",
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "learner_course_profiles",
        "updated_at",
        server_default=None,
    )
    op.alter_column(
        "learner_course_profiles",
        "created_at",
        server_default=None,
    )
