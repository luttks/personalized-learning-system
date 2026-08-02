import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from itertools import pairwise
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    CourseStatus,
    CourseVersion,
    CourseVersionStatus,
    Document,
    DocumentJob,
)
from app.models.content_catalog import (
    ConceptPrerequisite,
    CourseChapter,
    CourseConcept,
    CourseLesson,
)
from app.models.content_chunk import ContentChunk
from app.models.course_publication import CoursePublication
from app.models.document_analysis import DocumentAnalysis
from app.models.user import User
from app.schemas.content import DocumentStructure
from app.services.content_service import (
    CourseNotFoundError,
    get_analysis_for_manager,
    get_course_for_manager,
)
from app.services.rag_service import feature_hash_embedding, rebuild_content_index


class CatalogNotReadyError(Exception):
    pass


async def publish_course_snapshot(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> CoursePublication:
    course = await get_course_for_manager(session, user, course_id, lock=True)
    quality = await get_aggregate_course_quality_gate(session, user, course_id)
    if not quality["ready"]:
        raise CatalogNotReadyError(
            "Quality gate cuối chưa đạt; không thể publish khóa học."
        )
    if course.active_publication_id:
        active = await session.get(CoursePublication, course.active_publication_id)
        if active:
            active.status = "superseded"
    revision = int(
        await session.scalar(
            select(func.coalesce(func.max(CoursePublication.revision), 0)).where(
                CoursePublication.course_id == course_id
            )
        )
        or 0
    ) + 1
    version_ids = [item["course_version_id"] for item in quality["versions"]]
    now = datetime.now(UTC)
    quality_snapshot = {
        "document_count": quality["document_count"],
        "chapter_count": quality["chapter_count"],
        "lesson_count": quality["lesson_count"],
        "concept_count": quality["concept_count"],
        "chunk_count": quality["chunk_count"],
        "versions": [
            {
                "course_version_id": str(item["course_version_id"]),
                "version_number": item["version_number"],
                "document_id": str(item["document_id"]),
                "original_name": item["original_name"],
            }
            for item in quality["versions"]
        ],
    }
    publication = CoursePublication(
        course_id=course_id,
        revision=revision,
        status="published",
        version_ids_json=[str(version_id) for version_id in version_ids],
        quality_snapshot_json=quality_snapshot,
        published_by_id=user.id,
        published_at=now,
    )
    session.add(publication)
    await session.flush()
    course.active_publication_id = publication.id
    course.published_version_id = version_ids[-1]
    course.status = CourseStatus.PUBLISHED.value
    versions = list(
        (
            await session.scalars(
                select(CourseVersion).where(CourseVersion.id.in_(version_ids))
            )
        ).all()
    )
    for version in versions:
        version.status = CourseVersionStatus.PUBLISHED.value
    await session.commit()
    await session.refresh(publication)
    return publication


async def unpublish_course_snapshot(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> CoursePublication:
    course = await get_course_for_manager(session, user, course_id, lock=True)
    if not course.active_publication_id:
        raise CatalogNotReadyError("Khóa học chưa có publication đang hoạt động.")
    publication = await session.get(CoursePublication, course.active_publication_id)
    if publication is None:
        raise CatalogNotReadyError("Không tìm thấy publication đang hoạt động.")
    publication.status = "unpublished"
    publication.unpublished_at = datetime.now(UTC)
    course.active_publication_id = None
    course.status = CourseStatus.UNPUBLISHED.value
    version_ids = [UUID(value) for value in publication.version_ids_json]
    versions = list(
        (
            await session.scalars(
                select(CourseVersion).where(CourseVersion.id.in_(version_ids))
            )
        ).all()
    )
    for version in versions:
        version.status = CourseVersionStatus.UNPUBLISHED.value
    await session.commit()
    await session.refresh(publication)
    return publication


async def rebuild_aggregate_course_catalog(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> dict:
    await get_course_for_manager(session, user, course_id)
    rows = (
        await session.execute(
            select(CourseVersion, Document, DocumentJob, DocumentAnalysis)
            .join(Document, Document.course_version_id == CourseVersion.id)
            .join(DocumentJob, DocumentJob.document_id == Document.id)
            .outerjoin(
                DocumentAnalysis,
                DocumentAnalysis.course_version_id == CourseVersion.id,
            )
            .where(CourseVersion.course_id == course_id)
            .order_by(CourseVersion.version_number)
        )
    ).all()
    if not rows:
        raise CatalogNotReadyError("Khóa học chưa có tài liệu.")
    incomplete = [
        version.version_number
        for version, _document, job, analysis in rows
        if job.status != "completed" or analysis is None or analysis.status != "completed"
    ]
    if incomplete:
        versions = ", ".join(str(number) for number in incomplete)
        raise CatalogNotReadyError(
            f"Version {versions} chưa phân tích xong; không thể dựng quality gate cuối."
        )

    for version, _document, _job, _analysis in rows:
        chunk_count = int(
            await session.scalar(
                select(func.count(ContentChunk.id)).where(
                    ContentChunk.course_version_id == version.id
                )
            )
            or 0
        )
        chapter_count = int(
            await session.scalar(
                select(func.count(CourseChapter.id)).where(
                    CourseChapter.course_version_id == version.id
                )
            )
            or 0
        )
        if chunk_count == 0:
            await rebuild_content_index(session, user, version.id)
            chapter_count = 0
        if chapter_count == 0:
            await rebuild_course_catalog(session, user, version.id)

    ordered_concepts = list(
        (
            await session.scalars(
                select(CourseConcept)
                .join(CourseLesson, CourseLesson.id == CourseConcept.lesson_id)
                .join(CourseChapter, CourseChapter.id == CourseLesson.chapter_id)
                .join(
                    CourseVersion,
                    CourseVersion.id == CourseConcept.course_version_id,
                )
                .where(CourseVersion.course_id == course_id)
                .order_by(
                    CourseVersion.version_number,
                    CourseChapter.order_index,
                    CourseLesson.order_index,
                    CourseConcept.order_index,
                )
            )
        ).all()
    )
    concept_ids = [concept.id for concept in ordered_concepts]
    if concept_ids:
        await session.execute(
            delete(ConceptPrerequisite).where(
                ConceptPrerequisite.concept_id.in_(concept_ids)
            )
        )
        session.add_all(
            [
                ConceptPrerequisite(
                    concept_id=current.id,
                    prerequisite_concept_id=previous.id,
                )
                for previous, current in pairwise(ordered_concepts)
            ]
        )
        await session.commit()
    return await get_aggregate_course_quality_gate(session, user, course_id)


async def get_aggregate_course_quality_gate(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> dict:
    await get_course_for_manager(session, user, course_id)
    rows = (
        await session.execute(
            select(CourseVersion, Document, DocumentJob, DocumentAnalysis)
            .join(Document, Document.course_version_id == CourseVersion.id)
            .join(DocumentJob, DocumentJob.document_id == Document.id)
            .outerjoin(
                DocumentAnalysis,
                DocumentAnalysis.course_version_id == CourseVersion.id,
            )
            .where(CourseVersion.course_id == course_id)
            .order_by(CourseVersion.version_number)
        )
    ).all()
    versions: list[dict] = []
    aggregate_issues: list[str] = []
    for version, document, job, analysis in rows:
        issues: list[str] = []
        catalog = None
        if job.status != "completed" or analysis is None or analysis.status != "completed":
            issues.append("Tài liệu chưa được phân tích hoàn tất.")
        else:
            catalog = await get_course_catalog_data(session, user, version.id)
            issues.extend(catalog["issues"])
        if issues:
            aggregate_issues.append(
                f"Version {version.version_number}: {' '.join(issues)}"
            )
        versions.append(
            {
                "course_version_id": version.id,
                "version_number": version.version_number,
                "document_id": document.id,
                "original_name": document.original_name,
                "processing_status": analysis.status if analysis else job.status,
                "ready": bool(catalog and catalog["ready"] and not issues),
                "issues": issues,
                "chapter_count": catalog["chapter_count"] if catalog else 0,
                "lesson_count": catalog["lesson_count"] if catalog else 0,
                "concept_count": catalog["concept_count"] if catalog else 0,
                "chunk_count": catalog["chunk_count"] if catalog else 0,
            }
        )
    if not rows:
        aggregate_issues.append("Khóa học chưa có tài liệu.")
    ready_versions = sum(1 for version in versions if version["ready"])
    return {
        "course_id": course_id,
        "ready": bool(versions and ready_versions == len(versions)),
        "issues": aggregate_issues,
        "document_count": len(versions),
        "ready_document_count": ready_versions,
        "chapter_count": sum(item["chapter_count"] for item in versions),
        "lesson_count": sum(item["lesson_count"] for item in versions),
        "concept_count": sum(item["concept_count"] for item in versions),
        "chunk_count": sum(item["chunk_count"] for item in versions),
        "versions": versions,
    }


def stable_concept_key(title: str, position: int) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:120] or "concept"
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    return f"{position:03d}-{slug}-{digest}"


def vector_similarity(left: list[float], right: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def focused_concept_description(
    concept_title: str,
    chunk_text: str,
    chapter_summary: str,
) -> str:
    title_tokens = set(re.findall(r"\w+", concept_title.casefold()))
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", chunk_text)
        if sentence.strip()
    ]
    ranked = sorted(
        sentences,
        key=lambda sentence: len(
            title_tokens & set(re.findall(r"\w+", sentence.casefold()))
        ),
        reverse=True,
    )
    normalized_title = " ".join(concept_title.casefold().split())
    normalized_summary = " ".join(chapter_summary.casefold().split())
    for sentence in ranked:
        normalized = " ".join(sentence.casefold().split())
        if (
            len(sentence) >= 30
            and normalized != normalized_title
            and normalized != normalized_summary
        ):
            return sentence[:600].strip()
    return concept_title.strip()


async def rebuild_course_catalog(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> None:
    analysis = await get_analysis_for_manager(session, user, course_version_id)
    version = await session.get(CourseVersion, course_version_id)
    if version and version.status == CourseVersionStatus.PUBLISHED.value:
        raise CatalogNotReadyError(
            "Version đang publish; hãy unpublish trước khi dựng lại catalog."
        )
    if analysis is None or analysis.status != "completed":
        raise CourseNotFoundError
    structure = DocumentStructure.model_validate(
        analysis.edited_structure_json or analysis.structure_json
    )
    chunks = list(
        (
            await session.scalars(
                select(ContentChunk)
                .where(ContentChunk.course_version_id == course_version_id)
                .order_by(ContentChunk.chunk_index)
            )
        ).all()
    )
    if not structure.chapters:
        raise CatalogNotReadyError("Bản phân tích chưa có chương.")
    if not chunks:
        raise CatalogNotReadyError("Hãy tạo chỉ mục RAG trước khi dựng catalog.")

    await session.execute(
        delete(CourseChapter).where(
            CourseChapter.course_version_id == course_version_id
        )
    )
    await session.flush()

    lesson_targets: list[tuple[CourseLesson, list[float]]] = []
    previous_concept: CourseConcept | None = None
    concept_position = 0
    for chapter_index, chapter_data in enumerate(structure.chapters):
        target = feature_hash_embedding(
            f"{chapter_data.title}\n{chapter_data.summary}\n"
            + "\n".join(chapter_data.key_points)
        )
        best_chunk = max(
            chunks,
            key=lambda chunk: vector_similarity(list(chunk.embedding), target),
        )
        chapter = CourseChapter(
            course_version_id=course_version_id,
            order_index=chapter_index,
            title=chapter_data.title.strip(),
            summary=chapter_data.summary.strip(),
            source_label=best_chunk.source_label,
        )
        session.add(chapter)
        await session.flush()
        lesson = CourseLesson(
            course_version_id=course_version_id,
            chapter_id=chapter.id,
            order_index=0,
            title=chapter_data.title.strip(),
            summary=chapter_data.summary.strip(),
            source_label=best_chunk.source_label,
        )
        session.add(lesson)
        await session.flush()
        lesson_targets.append((lesson, target))

        concept_titles = chapter_data.key_points or [chapter_data.title]
        for concept_index, concept_title in enumerate(concept_titles):
            concept_position += 1
            concept_target = feature_hash_embedding(concept_title)
            concept_chunk = max(
                chunks,
                key=lambda chunk: vector_similarity(
                    list(chunk.embedding), concept_target
                ),
            )
            concept = CourseConcept(
                course_version_id=course_version_id,
                lesson_id=lesson.id,
                stable_key=stable_concept_key(concept_title, concept_position),
                order_index=concept_index,
                title=concept_title.strip(),
                description=focused_concept_description(
                    concept_title,
                    concept_chunk.text,
                    chapter_data.summary,
                ),
                estimated_minutes=20,
            )
            session.add(concept)
            await session.flush()
            if previous_concept is not None:
                session.add(
                    ConceptPrerequisite(
                        concept_id=concept.id,
                        prerequisite_concept_id=previous_concept.id,
                    )
                )
            previous_concept = concept

    for chunk in chunks:
        chunk_vector = list(chunk.embedding)
        chunk.lesson_id = max(
            lesson_targets,
            key=lambda item: vector_similarity(chunk_vector, item[1]),
        )[0].id
    await session.commit()


async def get_course_catalog_data(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> dict:
    await get_analysis_for_manager(session, user, course_version_id)
    return await get_catalog_data(session, course_version_id)


async def get_catalog_data(
    session: AsyncSession,
    course_version_id: UUID,
) -> dict:
    chapters = list(
        (
            await session.scalars(
                select(CourseChapter)
                .where(CourseChapter.course_version_id == course_version_id)
                .order_by(CourseChapter.order_index)
            )
        ).all()
    )
    lessons = list(
        (
            await session.scalars(
                select(CourseLesson)
                .where(CourseLesson.course_version_id == course_version_id)
                .order_by(CourseLesson.order_index)
            )
        ).all()
    )
    concepts = list(
        (
            await session.scalars(
                select(CourseConcept)
                .where(CourseConcept.course_version_id == course_version_id)
                .order_by(CourseConcept.order_index)
            )
        ).all()
    )
    prerequisites = list(
        (
            await session.scalars(
                select(ConceptPrerequisite).where(
                    ConceptPrerequisite.concept_id.in_([item.id for item in concepts])
                )
            )
        ).all()
    ) if concepts else []
    chunk_counts = dict(
        (
            await session.execute(
                select(ContentChunk.lesson_id, func.count(ContentChunk.id))
                .where(ContentChunk.course_version_id == course_version_id)
                .group_by(ContentChunk.lesson_id)
            )
        ).all()
    )
    key_by_id = {concept.id: concept.stable_key for concept in concepts}
    external_prerequisite_ids = {
        prerequisite.prerequisite_concept_id
        for prerequisite in prerequisites
        if prerequisite.prerequisite_concept_id not in key_by_id
    }
    if external_prerequisite_ids:
        key_by_id.update(
            dict(
                (
                    await session.execute(
                        select(CourseConcept.id, CourseConcept.stable_key).where(
                            CourseConcept.id.in_(external_prerequisite_ids)
                        )
                    )
                ).all()
            )
        )
    prerequisites_by_concept: dict[UUID, list[str]] = {}
    for prerequisite in prerequisites:
        prerequisites_by_concept.setdefault(prerequisite.concept_id, []).append(
            key_by_id[prerequisite.prerequisite_concept_id]
        )
    concepts_by_lesson: dict[UUID, list[dict]] = {}
    for concept in concepts:
        concepts_by_lesson.setdefault(concept.lesson_id, []).append(
            {
                "id": concept.id,
                "stable_key": concept.stable_key,
                "order_index": concept.order_index,
                "title": concept.title,
                "description": concept.description,
                "estimated_minutes": concept.estimated_minutes,
                "prerequisite_keys": prerequisites_by_concept.get(concept.id, []),
            }
        )
    lessons_by_chapter: dict[UUID, list[dict]] = {}
    for lesson in lessons:
        lessons_by_chapter.setdefault(lesson.chapter_id, []).append(
            {
                "id": lesson.id,
                "order_index": lesson.order_index,
                "title": lesson.title,
                "summary": lesson.summary,
                "source_label": lesson.source_label,
                "chunk_count": int(chunk_counts.get(lesson.id, 0)),
                "concepts": concepts_by_lesson.get(lesson.id, []),
            }
        )
    issues: list[str] = []
    if not chapters:
        issues.append("Chưa có chương.")
    if chapters and not lessons:
        issues.append("Chưa có bài học.")
    if lessons and not concepts:
        issues.append("Chưa có concept.")
    if any(not chunk_counts.get(lesson.id) for lesson in lessons):
        issues.append("Có bài học chưa được liên kết với chunk nguồn.")
    if chunk_counts.get(None):
        issues.append("Có chunk nguồn chưa được gắn vào bài học.")
    return {
        "course_version_id": course_version_id,
        "ready": bool(chapters and lessons and concepts and not issues),
        "issues": issues,
        "chapter_count": len(chapters),
        "lesson_count": len(lessons),
        "concept_count": len(concepts),
        "chunk_count": sum(int(value) for value in chunk_counts.values()),
        "chapters": [
            {
                "id": chapter.id,
                "order_index": chapter.order_index,
                "title": chapter.title,
                "summary": chapter.summary,
                "source_label": chapter.source_label,
                "lessons": lessons_by_chapter.get(chapter.id, []),
            }
            for chapter in chapters
        ],
    }


async def save_course_catalog_edit(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
    payload: dict,
) -> dict:
    await get_analysis_for_manager(session, user, course_version_id)
    version = await session.get(CourseVersion, course_version_id)
    if version and version.status == CourseVersionStatus.PUBLISHED.value:
        raise CatalogNotReadyError(
            "Version đang publish; hãy unpublish trước khi chỉnh sửa catalog."
        )
    chapters = {
        chapter.id: chapter
        for chapter in (
            await session.scalars(
                select(CourseChapter).where(
                    CourseChapter.course_version_id == course_version_id
                )
            )
        ).all()
    }
    lessons = {
        lesson.id: lesson
        for lesson in (
            await session.scalars(
                select(CourseLesson).where(
                    CourseLesson.course_version_id == course_version_id
                )
            )
        ).all()
    }
    concepts = {
        concept.id: concept
        for concept in (
            await session.scalars(
                select(CourseConcept).where(
                    CourseConcept.course_version_id == course_version_id
                )
            )
        ).all()
    }
    supplied_chapter_ids = {item["id"] for item in payload["chapters"]}
    supplied_lesson_ids = {
        lesson["id"]
        for chapter in payload["chapters"]
        for lesson in chapter["lessons"]
    }
    supplied_concept_ids = {
        concept["id"]
        for chapter in payload["chapters"]
        for lesson in chapter["lessons"]
        for concept in lesson["concepts"]
    }
    if (
        supplied_chapter_ids != set(chapters)
        or supplied_lesson_ids != set(lessons)
        or supplied_concept_ids != set(concepts)
    ):
        raise CatalogNotReadyError(
            "Cấu trúc chỉnh sửa không còn khớp catalog hiện tại. Hãy tải lại."
        )
    for chapter_data in payload["chapters"]:
        chapter = chapters[chapter_data["id"]]
        chapter.title = chapter_data["title"].strip()
        chapter.summary = chapter_data["summary"].strip()
        for lesson_data in chapter_data["lessons"]:
            lesson = lessons[lesson_data["id"]]
            if lesson.chapter_id != chapter.id:
                raise CatalogNotReadyError("Bài học không thuộc chương đã gửi.")
            lesson.title = lesson_data["title"].strip()
            lesson.summary = lesson_data["summary"].strip()
            for concept_data in lesson_data["concepts"]:
                concept = concepts[concept_data["id"]]
                if concept.lesson_id != lesson.id:
                    raise CatalogNotReadyError("Concept không thuộc bài học đã gửi.")
                concept.title = concept_data["title"].strip()
                concept.description = concept_data["description"].strip()
                concept.estimated_minutes = concept_data["estimated_minutes"]
    await session.commit()
    return await get_course_catalog_data(session, user, course_version_id)
