from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_analyses"

    course_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_characters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    llm_input_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text)
    edited_by_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    structure_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    edited_structure_json: Mapped[dict | None] = mapped_column(JSON)
    structure_edited_by_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    structure_edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(150))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("course_version_id", name="uq_document_analysis_course_version"),
    )
