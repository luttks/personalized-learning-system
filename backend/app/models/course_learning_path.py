from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CourseLearningPath(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_learning_paths"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            "path_version",
            name="uq_course_learning_paths_user_course_version",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_publications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    learner_course_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("learner_course_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    diagnostic_attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("diagnostic_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    path_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    required_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    mastery_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    gaps_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    skipped_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    items_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    generator: Mapped[str] = mapped_column(String(100), nullable=False)
