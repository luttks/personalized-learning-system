"""add editable analysis structure

Revision ID: c4a8d9e2f103
Revises: 91d6a4c2f8b0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a8d9e2f103"
down_revision: str | Sequence[str] | None = "91d6a4c2f8b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_analyses",
        sa.Column("edited_structure_json", sa.JSON()),
    )
    op.add_column(
        "document_analyses",
        sa.Column("structure_edited_by_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "document_analyses",
        sa.Column("structure_edited_at", sa.DateTime(timezone=True)),
    )
    op.create_foreign_key(
        "fk_document_analyses_structure_edited_by_id_users",
        "document_analyses",
        "users",
        ["structure_edited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_document_analyses_structure_edited_by_id_users",
        "document_analyses",
        type_="foreignkey",
    )
    op.drop_column("document_analyses", "structure_edited_at")
    op.drop_column("document_analyses", "structure_edited_by_id")
    op.drop_column("document_analyses", "edited_structure_json")
