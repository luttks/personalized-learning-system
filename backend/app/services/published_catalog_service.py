from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Course, CourseStatus, CourseVersion, Document
from app.models.course_publication import CoursePublication
from app.services.catalog_service import get_catalog_data


class PublishedCourseNotFoundError(Exception):
    pass


def _snapshot_count(publication: CoursePublication, key: str) -> int:
    return int(publication.quality_snapshot_json.get(key, 0))


def _course_summary(course: Course, publication: CoursePublication) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "subject": course.subject,
        "grade_level": course.grade_level,
        "description": course.description,
        "publication_revision": publication.revision,
        "document_count": _snapshot_count(publication, "document_count"),
        "chapter_count": _snapshot_count(publication, "chapter_count"),
        "lesson_count": _snapshot_count(publication, "lesson_count"),
        "concept_count": _snapshot_count(publication, "concept_count"),
        "published_at": publication.published_at,
    }


async def list_published_courses(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(Course, CoursePublication)
            .join(
                CoursePublication,
                CoursePublication.id == Course.active_publication_id,
            )
            .where(
                Course.status == CourseStatus.PUBLISHED.value,
                CoursePublication.status == "published",
            )
            .order_by(CoursePublication.published_at.desc(), Course.title)
        )
    ).all()
    return [_course_summary(course, publication) for course, publication in rows]


async def get_published_course(
    session: AsyncSession,
    course_id: UUID,
) -> dict:
    row = (
        await session.execute(
            select(Course, CoursePublication)
            .join(
                CoursePublication,
                CoursePublication.id == Course.active_publication_id,
            )
            .where(
                Course.id == course_id,
                Course.status == CourseStatus.PUBLISHED.value,
                CoursePublication.status == "published",
            )
        )
    ).one_or_none()
    if row is None:
        raise PublishedCourseNotFoundError
    course, publication = row
    version_ids = [UUID(value) for value in publication.version_ids_json]
    version_rows = (
        await session.execute(
            select(CourseVersion, Document)
            .join(Document, Document.course_version_id == CourseVersion.id)
            .where(
                CourseVersion.course_id == course.id,
                CourseVersion.id.in_(version_ids),
            )
            .order_by(CourseVersion.version_number)
        )
    ).all()
    versions = []
    for version, document in version_rows:
        catalog = await get_catalog_data(session, version.id)
        versions.append(
            {
                "course_version_id": version.id,
                "version_number": version.version_number,
                "original_name": document.original_name,
                "chapter_count": catalog["chapter_count"],
                "lesson_count": catalog["lesson_count"],
                "concept_count": catalog["concept_count"],
                "chunk_count": catalog["chunk_count"],
                "chapters": catalog["chapters"],
            }
        )
    if len(versions) != len(version_ids):
        raise PublishedCourseNotFoundError
    return {
        **_course_summary(course, publication),
        "publication_id": publication.id,
        "versions": versions,
    }
