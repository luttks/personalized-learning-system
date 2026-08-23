"""add document chat sessions and messages"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7c9d1e2f304"
down_revision = "af5b7c2d9e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_version_id"], ["course_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chat_sessions_course_version_id", "document_chat_sessions", ["course_version_id"])
    op.create_index("ix_document_chat_sessions_user_id", "document_chat_sessions", ["user_id"])
    op.create_table(
        "document_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["document_chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chat_messages_session_id", "document_chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chat_messages_session_id", table_name="document_chat_messages")
    op.drop_table("document_chat_messages")
    op.drop_index("ix_document_chat_sessions_user_id", table_name="document_chat_sessions")
    op.drop_index("ix_document_chat_sessions_course_version_id", table_name="document_chat_sessions")
    op.drop_table("document_chat_sessions")
