from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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


class CourseStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"


class CourseVersionStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    VERIFYING = "verifying"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    COMPLETED = "completed"
    FAILED = "failed"


class Course(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "courses"

    owner_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), default=CourseStatus.DRAFT.value, nullable=False
    )
    published_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    active_publication_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_publications.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "grade_level >= 1 AND grade_level <= 12",
            name="course_grade_level_range",
        ),
    )


class CourseVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_versions"

    course_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default=CourseVersionStatus.DRAFT.value, nullable=False
    )
    created_by_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_detail: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "version_number",
            name="uq_course_versions_course_version_number",
        ),
    )


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    course_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="document_size_positive"),
    )


class DocumentJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_jobs"

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(40), default=DocumentJobStatus.QUEUED.value, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="document_job_progress_range",
        ),
        CheckConstraint("retry_count >= 0", name="document_job_retry_non_negative"),
    )
