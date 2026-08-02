"""add editable document content

Revision ID: 91d6a4c2f8b0
Revises: 5b7e2c1d9a40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "91d6a4c2f8b0"
down_revision: str | Sequence[str] | None = "5b7e2c1d9a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_analyses",
        sa.Column("llm_input_text", sa.Text(), server_default="", nullable=False),
    )
    op.add_column("document_analyses", sa.Column("edited_text", sa.Text()))
    op.add_column(
        "document_analyses",
        sa.Column("edited_by_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "document_analyses",
        sa.Column("edited_at", sa.DateTime(timezone=True)),
    )
    op.create_foreign_key(
        "fk_document_analyses_edited_by_id_users",
        "document_analyses",
        "users",
        ["edited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE document_analyses "
        "SET llm_input_text = left(extracted_text, 120000)"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_document_analyses_edited_by_id_users",
        "document_analyses",
        type_="foreignkey",
    )
    op.drop_column("document_analyses", "edited_at")
    op.drop_column("document_analyses", "edited_by_id")
    op.drop_column("document_analyses", "edited_text")
    op.drop_column("document_analyses", "llm_input_text")
