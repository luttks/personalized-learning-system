from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Course,
    CourseStatus,
    CourseVersion,
    CourseVersionStatus,
    Document,
    DocumentJob,
    DocumentJobStatus,
)
from app.models.content_catalog import CourseChapter
from app.models.content_chunk import ContentChunk
from app.models.document_analysis import DocumentAnalysis
from app.models.user import User, UserRole
from app.services.document_storage import (
    DocumentStorageError,
    LocalDocumentStorage,
    StoredDocument,
)


class CourseAccessError(Exception):
    pass


class CourseNotFoundError(CourseAccessError):
    pass


class CourseDeleteConflictError(CourseAccessError):
    pass


@dataclass(frozen=True)
class DocumentJobSnapshot:
    job: DocumentJob
    document: Document
    version: CourseVersion
    course: Course


def can_manage_course(user: User, course: Course) -> bool:
    return user.role == UserRole.ADMIN or course.owner_id == user.id


async def create_course(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    subject: str,
    grade_level: int,
    description: str | None,
) -> Course:
    course = Course(
        owner_id=user.id,
        title=title.strip(),
        subject=subject.strip(),
        grade_level=grade_level,
        description=description.strip() if description else None,
        status=CourseStatus.DRAFT.value,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def list_courses(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[Course]:
    statement = select(Course).order_by(Course.created_at.desc())
    if user.role != UserRole.ADMIN:
        statement = statement.where(Course.owner_id == user.id)
    result = await session.execute(statement.limit(limit).offset(offset))
    return list(result.scalars().all())


async def get_course_for_manager(
    session: AsyncSession,
    user: User,
    course_id: UUID,
    *,
    lock: bool = False,
) -> Course:
    statement = select(Course).where(Course.id == course_id)
    if lock:
        statement = statement.with_for_update()
    course = (await session.execute(statement)).scalar_one_or_none()
    if course is None or not can_manage_course(user, course):
        raise CourseNotFoundError
    return course


async def create_document_upload(
    session: AsyncSession,
    user: User,
    course_id: UUID,
    stored: StoredDocument,
) -> DocumentJobSnapshot:
    course = await get_course_for_manager(session, user, course_id, lock=True)
    max_version = await session.scalar(
        select(func.coalesce(func.max(CourseVersion.version_number), 0)).where(
            CourseVersion.course_id == course.id
        )
    )
    version = CourseVersion(
        course_id=course.id,
        version_number=int(max_version or 0) + 1,
        status=CourseVersionStatus.QUEUED.value,
        created_by_id=user.id,
    )
    session.add(version)
    await session.flush()
    document = Document(
        course_version_id=version.id,
        storage_key=stored.storage_key,
        original_name=stored.original_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    session.add(document)
    await session.flush()
    job = DocumentJob(
        document_id=document.id,
        status=DocumentJobStatus.QUEUED.value,
        current_step="queued",
    )
    session.add(job)
    await session.commit()
    await session.refresh(version)
    await session.refresh(document)
    await session.refresh(job)
    return DocumentJobSnapshot(job=job, document=document, version=version, course=course)


async def get_document_job_snapshot(
    session: AsyncSession,
    user: User,
    job_id: UUID,
) -> DocumentJobSnapshot:
    result = await session.execute(
        select(DocumentJob, Document, CourseVersion, Course)
        .join(Document, Document.id == DocumentJob.document_id)
        .join(CourseVersion, CourseVersion.id == Document.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
        .where(DocumentJob.id == job_id)
    )
    row = result.one_or_none()
    if row is None:
        raise CourseNotFoundError
    job, document, version, course = row
    if not can_manage_course(user, course):
        raise CourseNotFoundError
    return DocumentJobSnapshot(job=job, document=document, version=version, course=course)


async def get_analysis_for_manager(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> DocumentAnalysis | None:
    result = await session.execute(
        select(DocumentAnalysis, Course)
        .join(CourseVersion, CourseVersion.id == DocumentAnalysis.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
        .where(DocumentAnalysis.course_version_id == course_version_id)
    )
    row = result.one_or_none()
    if row is None:
        raise CourseNotFoundError
    analysis, course = row
    if not can_manage_course(user, course):
        raise CourseNotFoundError
    return analysis


async def list_course_documents(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> list[tuple[Document, CourseVersion, DocumentJob, DocumentAnalysis | None]]:
    await get_course_for_manager(session, user, course_id)
    result = await session.execute(
        select(Document, CourseVersion, DocumentJob, DocumentAnalysis)
        .join(CourseVersion, CourseVersion.id == Document.course_version_id)
        .join(DocumentJob, DocumentJob.document_id == Document.id)
        .outerjoin(DocumentAnalysis, DocumentAnalysis.course_version_id == CourseVersion.id)
        .where(CourseVersion.course_id == course_id)
        .order_by(CourseVersion.version_number.desc())
    )
    return list(result.all())


async def get_document_preview(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> tuple[Document, CourseVersion, DocumentAnalysis | None]:
    result = await session.execute(
        select(Document, CourseVersion, DocumentAnalysis)
        .join(CourseVersion, CourseVersion.id == Document.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
        .outerjoin(DocumentAnalysis, DocumentAnalysis.course_version_id == CourseVersion.id)
        .where(CourseVersion.id == course_version_id)
    )
    row = result.one_or_none()
    if row is None:
        raise CourseNotFoundError
    document, version, analysis = row
    if not can_manage_course(user, await session.get(Course, version.course_id)):
        raise CourseNotFoundError
    return document, version, analysis


async def save_document_edit(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
    edited_text: str,
) -> tuple[Document, CourseVersion, DocumentAnalysis]:
    document, version, analysis = await get_document_preview(
        session, user, course_version_id
    )
    if analysis is None or analysis.status != "completed":
        raise CourseNotFoundError
    if version.status == CourseVersionStatus.PUBLISHED.value:
        raise CourseDeleteConflictError(
            "Version đang publish; hãy unpublish trước khi sửa nội dung."
        )
    analysis.edited_text = edited_text.strip()
    analysis.edited_by_id = user.id
    analysis.edited_at = datetime.now(UTC)
    await session.execute(
        delete(ContentChunk).where(
            ContentChunk.course_version_id == course_version_id
        )
    )
    await session.commit()
    await session.refresh(analysis)
    return document, version, analysis


async def save_analysis_structure_edit(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
    structure: dict[str, Any],
) -> DocumentAnalysis:
    if user.role != UserRole.ADMIN:
        raise CourseNotFoundError
    analysis = await get_analysis_for_manager(session, user, course_version_id)
    if analysis is None or analysis.status != "completed":
        raise CourseNotFoundError
    version_status = await session.scalar(
        select(CourseVersion.status).where(CourseVersion.id == course_version_id)
    )
    if version_status == CourseVersionStatus.PUBLISHED.value:
        raise CourseDeleteConflictError(
            "Version đang publish; hãy unpublish trước khi sửa phân tích."
        )
    analysis.edited_structure_json = structure
    analysis.structure_edited_by_id = user.id
    analysis.structure_edited_at = datetime.now(UTC)
    await session.execute(
        delete(CourseChapter).where(
            CourseChapter.course_version_id == course_version_id
        )
    )
    await session.commit()
    await session.refresh(analysis)
    return analysis


async def delete_course_for_admin(
    session: AsyncSession,
    user: User,
    course_id: UUID,
) -> list[str]:
    if user.role != UserRole.ADMIN:
        raise CourseNotFoundError
    course = await get_course_for_manager(session, user, course_id, lock=True)
    if course.status == CourseStatus.PUBLISHED.value or course.published_version_id:
        raise CourseDeleteConflictError(
            "Hãy unpublish khóa học trước khi xóa vĩnh viễn."
        )
    active_job = await session.scalar(
        select(DocumentJob.status)
        .join(Document, Document.id == DocumentJob.document_id)
        .join(CourseVersion, CourseVersion.id == Document.course_version_id)
        .where(
            CourseVersion.course_id == course_id,
            DocumentJob.status.in_(
                [
                    DocumentJobStatus.PROCESSING.value,
                    DocumentJobStatus.ANALYZING.value,
                ]
            ),
        )
    )
    if active_job:
        raise CourseDeleteConflictError(
            "Khóa học có tài liệu đang được xử lý, hãy chờ hoàn tất trước khi xóa."
        )
    storage_keys = list(
        (
            await session.scalars(
                select(Document.storage_key)
                .join(CourseVersion, CourseVersion.id == Document.course_version_id)
                .where(CourseVersion.course_id == course_id)
            )
        ).all()
    )
    course.published_version_id = None
    await session.flush()
    await session.delete(course)
    await session.commit()
    return storage_keys


async def delete_document_version_for_admin(
    session: AsyncSession,
    user: User,
    course_version_id: UUID,
) -> list[str]:
    if user.role != UserRole.ADMIN:
        raise CourseNotFoundError
    result = await session.execute(
        select(CourseVersion, Course)
        .join(Course, Course.id == CourseVersion.course_id)
        .where(CourseVersion.id == course_version_id)
        .with_for_update()
    )
    row = result.one_or_none()
    if row is None:
        raise CourseNotFoundError
    version, course = row
    if (
        course.published_version_id == version.id
        or version.status == CourseVersionStatus.PUBLISHED.value
    ):
        raise CourseDeleteConflictError(
            "Không thể xóa phiên bản đang được publish."
        )
    active_job = await session.scalar(
        select(DocumentJob.status)
        .join(Document, Document.id == DocumentJob.document_id)
        .where(Document.course_version_id == version.id)
    )
    if active_job in {
        DocumentJobStatus.PROCESSING.value,
        DocumentJobStatus.ANALYZING.value,
    }:
        raise CourseDeleteConflictError(
            "Tài liệu đang được xử lý, hãy chờ hoàn tất trước khi xóa."
        )
    storage_keys = list(
        (
            await session.scalars(
                select(Document.storage_key).where(
                    Document.course_version_id == version.id
                )
            )
        ).all()
    )
    await session.delete(version)
    await session.commit()
    return storage_keys


async def mark_job_enqueue_failed(
    session: AsyncSession,
    job_id: UUID,
    detail: str,
) -> None:
    snapshot = await _get_job_snapshot_without_access(session, job_id, lock=True)
    if snapshot.job.status != DocumentJobStatus.QUEUED.value:
        return
    now = datetime.now(UTC)
    snapshot.job.status = DocumentJobStatus.FAILED.value
    snapshot.job.progress = 0
    snapshot.job.current_step = "enqueue"
    snapshot.job.error_code = "QUEUE_UNAVAILABLE"
    snapshot.job.error_detail = detail[:2000]
    snapshot.job.finished_at = now
    snapshot.version.status = CourseVersionStatus.FAILED.value
    snapshot.version.failure_code = "QUEUE_UNAVAILABLE"
    snapshot.version.failure_detail = detail[:2000]
    await session.commit()


async def retry_document_job(
    session: AsyncSession,
    user: User,
    job_id: UUID,
) -> DocumentJobSnapshot:
    snapshot = await get_document_job_snapshot(session, user, job_id)
    if snapshot.version.status == CourseVersionStatus.PUBLISHED.value:
        raise CourseDeleteConflictError(
            "Version đang publish; hãy unpublish trước khi xử lý lại."
        )
    if snapshot.job.status not in {
        DocumentJobStatus.FAILED.value,
        DocumentJobStatus.COMPLETED.value,
    }:
        return snapshot

    snapshot.job.status = DocumentJobStatus.QUEUED.value
    snapshot.job.progress = 0
    snapshot.job.current_step = "queued_for_retry"
    snapshot.job.retry_count += 1
    snapshot.job.error_code = None
    snapshot.job.error_detail = None
    snapshot.job.started_at = None
    snapshot.job.finished_at = None
    snapshot.version.status = CourseVersionStatus.QUEUED.value
    snapshot.version.failure_code = None
    snapshot.version.failure_detail = None
    analysis = await session.scalar(
        select(DocumentAnalysis).where(
            DocumentAnalysis.course_version_id == snapshot.version.id
        )
    )
    if analysis is not None:
        await session.execute(
            delete(CourseChapter).where(
                CourseChapter.course_version_id == snapshot.version.id
            )
        )
        await session.execute(
            delete(ContentChunk).where(
                ContentChunk.course_version_id == snapshot.version.id
            )
        )
        analysis.status = "queued"
        analysis.source_characters = 0
        analysis.extracted_text = ""
        analysis.llm_input_text = ""
        analysis.edited_text = None
        analysis.edited_by_id = None
        analysis.edited_at = None
        analysis.structure_json = {}
        analysis.edited_structure_json = None
        analysis.structure_edited_by_id = None
        analysis.structure_edited_at = None
        analysis.provider = None
        analysis.model = None
        analysis.error_code = None
        analysis.error_detail = None
    await session.commit()
    await session.refresh(snapshot.job)
    await session.refresh(snapshot.version)
    return snapshot


async def verify_document_job(
    session_factory: Any,
    storage: LocalDocumentStorage,
    job_id: UUID,
) -> dict[str, str | int]:
    async with session_factory() as session:
        snapshot = await _get_job_snapshot_without_access(session, job_id, lock=True)
        if snapshot.job.status != DocumentJobStatus.QUEUED.value:
            return {"job_id": str(job_id), "status": snapshot.job.status}
        now = datetime.now(UTC)
        snapshot.job.status = DocumentJobStatus.PROCESSING.value
        snapshot.job.progress = 20
        snapshot.job.current_step = "verifying_file"
        snapshot.job.started_at = snapshot.job.started_at or now
        snapshot.version.status = CourseVersionStatus.VERIFYING.value
        await session.commit()

    try:
        storage.verify(
            snapshot.document.storage_key,
            expected_size=snapshot.document.size_bytes,
            expected_checksum=snapshot.document.checksum_sha256,
        )
    except (DocumentStorageError, OSError) as error:
        async with session_factory() as session:
            failed = await _get_job_snapshot_without_access(session, job_id, lock=True)
            failed.job.status = DocumentJobStatus.FAILED.value
            failed.job.progress = 0
            failed.job.current_step = "verification_failed"
            failed.job.error_code = "FILE_VERIFICATION_FAILED"
            failed.job.error_detail = str(error)[:2000]
            failed.job.finished_at = datetime.now(UTC)
            failed.version.status = CourseVersionStatus.FAILED.value
            failed.version.failure_code = "FILE_VERIFICATION_FAILED"
            failed.version.failure_detail = str(error)[:2000]
            await session.commit()
        return {"job_id": str(job_id), "status": DocumentJobStatus.FAILED.value}

    async with session_factory() as session:
        ready = await _get_job_snapshot_without_access(session, job_id, lock=True)
        ready.job.status = DocumentJobStatus.READY_FOR_ANALYSIS.value
        ready.job.progress = 100
        ready.job.current_step = "upload_verified"
        ready.job.finished_at = datetime.now(UTC)
        ready.version.status = CourseVersionStatus.READY_FOR_ANALYSIS.value
        await session.commit()
    return {"job_id": str(job_id), "status": DocumentJobStatus.READY_FOR_ANALYSIS.value}


async def _get_job_snapshot_without_access(
    session: AsyncSession,
    job_id: UUID,
    *,
    lock: bool = False,
) -> DocumentJobSnapshot:
    statement = (
        select(DocumentJob, Document, CourseVersion, Course)
        .join(Document, Document.id == DocumentJob.document_id)
        .join(CourseVersion, CourseVersion.id == Document.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
        .where(DocumentJob.id == job_id)
    )
    if lock:
        statement = statement.with_for_update()
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise CourseNotFoundError
    job, document, version, course = row
    return DocumentJobSnapshot(job=job, document=document, version=version, course=course)
