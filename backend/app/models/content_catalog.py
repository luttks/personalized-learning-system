from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CourseChapter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_chapters"

    course_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "course_version_id",
            "order_index",
            name="uq_course_chapters_version_order",
        ),
    )


class CourseLesson(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_lessons"

    course_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "order_index",
            name="uq_course_lessons_chapter_order",
        ),
    )


class CourseConcept(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "course_concepts"

    course_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lesson_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    stable_key: Mapped[str] = mapped_column(String(180), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "course_version_id",
            "stable_key",
            name="uq_course_concepts_version_stable_key",
        ),
        UniqueConstraint(
            "lesson_id",
            "order_index",
            name="uq_course_concepts_lesson_order",
        ),
    )


class ConceptPrerequisite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "concept_prerequisites"

    concept_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    prerequisite_concept_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("course_concepts.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "prerequisite_concept_id",
            name="uq_concept_prerequisites_pair",
        ),
    )
