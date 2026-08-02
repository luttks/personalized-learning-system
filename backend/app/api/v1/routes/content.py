from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_admin, get_current_teacher_or_admin
from app.core.config import settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.content import (
    CourseCatalogEditRequest,
    CourseCatalogResponse,
    CourseCreate,
    CourseDocumentItem,
    CoursePublicationResponse,
    CourseQualityGateResponse,
    CourseResponse,
    CourseVersionResponse,
    DocumentAnalysisEditRequest,
    DocumentAnalysisResponse,
    DocumentEditRequest,
    DocumentJobResponse,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentStructure,
    DocumentUploadResponse,
    RagIndexResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagSearchResult,
)
from app.services.catalog_service import (
    CatalogNotReadyError,
    get_aggregate_course_quality_gate,
    get_course_catalog_data,
    publish_course_snapshot,
    rebuild_aggregate_course_catalog,
    rebuild_course_catalog,
    save_course_catalog_edit,
    unpublish_course_snapshot,
)
from app.services.content_service import (
    CourseDeleteConflictError,
    CourseNotFoundError,
    DocumentJobSnapshot,
    create_course,
    create_document_upload,
    delete_course_for_admin,
    delete_document_version_for_admin,
    get_analysis_for_manager,
    get_course_for_manager,
    get_document_job_snapshot,
    get_document_preview,
    list_course_documents,
    list_courses,
    mark_job_enqueue_failed,
    retry_document_job,
    save_analysis_structure_edit,
    save_document_edit,
)
from app.services.document_storage import (
    DocumentStorageError,
    LocalDocumentStorage,
)
from app.services.rag_service import (
    EMBEDDING_MODEL,
    content_index_count,
    rebuild_content_index,
    search_content_chunks,
)
from app.worker.tasks import verify_document_upload_task

router = APIRouter(prefix="/courses", tags=["Courses and Documents"])
job_router = APIRouter(prefix="/document-jobs", tags=["Courses and Documents"])

CurrentContentManager = Annotated[
    User,
    Depends(get_current_teacher_or_admin),
]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@lru_cache
def get_document_storage() -> LocalDocumentStorage:
    return LocalDocumentStorage(
        settings.uploads_dir,
        max_upload_bytes=settings.document_max_upload_bytes,
        chunk_bytes=settings.document_upload_chunk_bytes,
    )


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_route(
    payload: CourseCreate,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> CourseResponse:
    course = await create_course(
        session,
        current_user,
        title=payload.title,
        subject=payload.subject,
        grade_level=payload.grade_level,
        description=payload.description,
    )
    return CourseResponse.model_validate(course)


@router.get("", response_model=list[CourseResponse])
async def list_courses_route(
    current_user: CurrentContentManager,
    session: DatabaseSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CourseResponse]:
    courses = await list_courses(session, current_user, limit=limit, offset=offset)
    return [CourseResponse.model_validate(course) for course in courses]


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_route(
    course_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
    storage: Annotated[LocalDocumentStorage, Depends(get_document_storage)],
) -> None:
    try:
        storage_keys = await delete_course_for_admin(session, current_user, course_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CourseDeleteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    for storage_key in storage_keys:
        storage.delete(storage_key)


@router.post(
    "/{course_id}/publish",
    response_model=CoursePublicationResponse,
)
async def publish_course(
    course_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> CoursePublicationResponse:
    try:
        publication = await publish_course_snapshot(
            session, current_user, course_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CatalogNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return _publication_response(publication)


@router.post(
    "/{course_id}/unpublish",
    response_model=CoursePublicationResponse,
)
async def unpublish_course(
    course_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> CoursePublicationResponse:
    try:
        publication = await unpublish_course_snapshot(
            session, current_user, course_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CatalogNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return _publication_response(publication)


def _publication_response(publication: Any) -> CoursePublicationResponse:
    return CoursePublicationResponse(
        id=publication.id,
        course_id=publication.course_id,
        revision=publication.revision,
        status=publication.status,
        version_ids=[UUID(value) for value in publication.version_ids_json],
        quality_snapshot=publication.quality_snapshot_json,
        published_by_id=publication.published_by_id,
        published_at=publication.published_at,
        unpublished_at=publication.unpublished_at,
    )


@router.get("/{course_id}/documents", response_model=list[CourseDocumentItem])
async def list_course_documents_route(
    course_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> list[CourseDocumentItem]:
    try:
        rows = await list_course_documents(session, current_user, course_id)
        course = await get_course_for_manager(session, current_user, course_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return [
        CourseDocumentItem(
            document=DocumentResponse.model_validate(document),
            version=CourseVersionResponse.model_validate(version),
            job=_job_response(
                DocumentJobSnapshot(
                    job=job,
                    document=document,
                    version=version,
                    course=course,
                )
            ),
            analysis_status=analysis.status if analysis else None,
            source_characters=analysis.source_characters if analysis else 0,
        )
        for document, version, job, analysis in rows
    ]


@router.get(
    "/{course_id}/quality-gate",
    response_model=CourseQualityGateResponse,
)
async def get_course_quality_gate(
    course_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> CourseQualityGateResponse:
    try:
        data = await get_aggregate_course_quality_gate(
            session, current_user, course_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return CourseQualityGateResponse.model_validate(data)


@router.post(
    "/{course_id}/quality-gate/build",
    response_model=CourseQualityGateResponse,
)
async def build_course_quality_gate(
    course_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> CourseQualityGateResponse:
    try:
        data = await rebuild_aggregate_course_catalog(
            session, current_user, course_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CatalogNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return CourseQualityGateResponse.model_validate(data)


@router.post(
    "/{course_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_course_document(
    course_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
    file: Annotated[UploadFile, File(...)],
    storage: Annotated[LocalDocumentStorage, Depends(get_document_storage)],
) -> DocumentUploadResponse:
    try:
        await get_course_for_manager(session, current_user, course_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error

    try:
        stored = await storage.save_upload(file)
    except DocumentStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_DOCUMENT",
                "message": str(error),
                "retryable": False,
            },
        ) from error

    try:
        snapshot = await create_document_upload(
            session,
            current_user,
            course_id,
            stored,
        )
    except CourseNotFoundError as error:
        storage.delete(stored.storage_key)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except Exception:
        storage.delete(stored.storage_key)
        raise

    try:
        verify_document_upload_task.delay(str(snapshot.job.id))
    except Exception as error:
        await mark_job_enqueue_failed(session, snapshot.job.id, str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "QUEUE_UNAVAILABLE",
                "message": "Không thể đưa tài liệu vào hàng đợi xử lý.",
                "retryable": True,
                "job_id": str(snapshot.job.id),
            },
        ) from error

    return _upload_response(snapshot)


@job_router.get("/{job_id}", response_model=DocumentJobResponse)
async def get_document_job(
    job_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> DocumentJobResponse:
    try:
        snapshot = await get_document_job_snapshot(session, current_user, job_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return _job_response(snapshot)


@job_router.post("/{job_id}/retry", response_model=DocumentJobResponse)
async def retry_document_job_route(
    job_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> DocumentJobResponse:
    try:
        snapshot = await retry_document_job(session, current_user, job_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CourseDeleteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    if snapshot.job.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job đang được xử lý nên chưa thể chạy lại.",
        )
    try:
        verify_document_upload_task.delay(str(snapshot.job.id))
    except Exception as error:
        await mark_job_enqueue_failed(session, snapshot.job.id, str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể đưa tài liệu vào hàng đợi xử lý.",
        ) from error
    return _job_response(snapshot)


@router.get(
    "/versions/{course_version_id}/analysis",
    response_model=DocumentAnalysisResponse,
)
async def get_course_version_analysis(
    course_version_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> DocumentAnalysisResponse:
    try:
        analysis = await get_analysis_for_manager(session, current_user, course_version_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _analysis_response(analysis)


@router.patch(
    "/versions/{course_version_id}/analysis",
    response_model=DocumentAnalysisResponse,
)
async def save_course_version_analysis(
    course_version_id: UUID,
    payload: DocumentAnalysisEditRequest,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> DocumentAnalysisResponse:
    try:
        analysis = await save_analysis_structure_edit(
            session,
            current_user,
            course_version_id,
            payload.structure.model_dump(mode="json"),
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CourseDeleteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return _analysis_response(analysis)


def _analysis_response(analysis: Any) -> DocumentAnalysisResponse:
    original_structure = DocumentStructure.model_validate(analysis.structure_json)
    edited_structure = (
        DocumentStructure.model_validate(analysis.edited_structure_json)
        if analysis.edited_structure_json
        else None
    )
    return DocumentAnalysisResponse(
        id=analysis.id,
        course_version_id=analysis.course_version_id,
        document_id=analysis.document_id,
        status=analysis.status,
        source_characters=analysis.source_characters,
        structure=edited_structure or original_structure,
        original_structure=original_structure,
        edited_structure=edited_structure,
        structure_edited_by_id=analysis.structure_edited_by_id,
        structure_edited_at=analysis.structure_edited_at,
        provider=analysis.provider,
        model=analysis.model,
        error_code=analysis.error_code,
        error_detail=analysis.error_detail,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.get(
    "/versions/{course_version_id}/rag",
    response_model=RagIndexResponse,
)
async def get_rag_index(
    course_version_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> RagIndexResponse:
    try:
        count = await content_index_count(session, current_user, course_version_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RagIndexResponse(
        course_version_id=course_version_id,
        chunk_count=count,
        embedding_model=EMBEDDING_MODEL,
    )


@router.post(
    "/versions/{course_version_id}/rag/index",
    response_model=RagIndexResponse,
)
async def create_rag_index(
    course_version_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> RagIndexResponse:
    try:
        chunks = await rebuild_content_index(session, current_user, course_version_id)
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RagIndexResponse(
        course_version_id=course_version_id,
        chunk_count=len(chunks),
        embedding_model=EMBEDDING_MODEL,
    )


@router.post(
    "/versions/{course_version_id}/rag/search",
    response_model=RagSearchResponse,
)
async def search_rag_index(
    course_version_id: UUID,
    payload: RagSearchRequest,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> RagSearchResponse:
    try:
        index_count = await content_index_count(
            session, current_user, course_version_id
        )
        rows = await search_content_chunks(
            session,
            current_user,
            course_version_id,
            payload.query.strip(),
            payload.limit,
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return RagSearchResponse(
        course_version_id=course_version_id,
        query=payload.query.strip(),
        index_count=index_count,
        results=[
            RagSearchResult(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_number=chunk.page_number,
                source_label=chunk.source_label,
                cosine_score=cosine_score,
                score=score,
            )
            for chunk, cosine_score, score in rows
        ],
    )


@router.get(
    "/versions/{course_version_id}/catalog",
    response_model=CourseCatalogResponse,
)
async def get_course_catalog(
    course_version_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> CourseCatalogResponse:
    try:
        data = await get_course_catalog_data(
            session, current_user, course_version_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return CourseCatalogResponse.model_validate(data)


@router.post(
    "/versions/{course_version_id}/catalog/build",
    response_model=CourseCatalogResponse,
)
async def build_course_catalog(
    course_version_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> CourseCatalogResponse:
    try:
        await rebuild_course_catalog(session, current_user, course_version_id)
        data = await get_course_catalog_data(
            session, current_user, course_version_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CatalogNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return CourseCatalogResponse.model_validate(data)


@router.patch(
    "/versions/{course_version_id}/catalog",
    response_model=CourseCatalogResponse,
)
async def edit_course_catalog(
    course_version_id: UUID,
    payload: CourseCatalogEditRequest,
    current_user: CurrentAdmin,
    session: DatabaseSession,
) -> CourseCatalogResponse:
    try:
        data = await save_course_catalog_edit(
            session,
            current_user,
            course_version_id,
            payload.model_dump(mode="python"),
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CatalogNotReadyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return CourseCatalogResponse.model_validate(data)


@router.get(
    "/versions/{course_version_id}/preview",
    response_model=DocumentPreviewResponse,
)
async def get_document_preview_route(
    course_version_id: UUID,
    current_user: CurrentContentManager,
    session: DatabaseSession,
    max_chars: int = Query(default=50_000, ge=1_000, le=200_000),
) -> DocumentPreviewResponse:
    try:
        document, version, analysis = await get_document_preview(
            session, current_user, course_version_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return _preview_response(document, version, analysis, max_chars)


@router.delete(
    "/versions/{course_version_id}/document",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document_version_route(
    course_version_id: UUID,
    current_user: CurrentAdmin,
    session: DatabaseSession,
    storage: Annotated[LocalDocumentStorage, Depends(get_document_storage)],
) -> None:
    try:
        storage_keys = await delete_document_version_for_admin(
            session, current_user, course_version_id
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CourseDeleteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    for storage_key in storage_keys:
        storage.delete(storage_key)


@router.patch(
    "/versions/{course_version_id}/preview",
    response_model=DocumentPreviewResponse,
)
async def save_document_edit_route(
    course_version_id: UUID,
    payload: DocumentEditRequest,
    current_user: CurrentContentManager,
    session: DatabaseSession,
) -> DocumentPreviewResponse:
    try:
        document, version, analysis = await save_document_edit(
            session,
            current_user,
            course_version_id,
            payload.edited_text,
        )
    except CourseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except CourseDeleteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return _preview_response(document, version, analysis, 200_000)


def _preview_response(
    document: Any,
    version: Any,
    analysis: Any | None,
    max_chars: int,
) -> DocumentPreviewResponse:
    original_text = analysis.extracted_text if analysis else ""
    edited_text = analysis.edited_text if analysis else None
    return DocumentPreviewResponse(
        document=DocumentResponse.model_validate(document),
        version=CourseVersionResponse.model_validate(version),
        status=analysis.status if analysis else version.status,
        original_text=original_text[:max_chars],
        llm_input_text=(analysis.llm_input_text[:max_chars] if analysis else ""),
        edited_text=(edited_text[:max_chars] if edited_text else None),
        effective_text=(edited_text or original_text)[:max_chars],
        edited_by_id=analysis.edited_by_id if analysis else None,
        edited_at=analysis.edited_at if analysis else None,
        source_characters=analysis.source_characters if analysis else 0,
        structure=(
            DocumentStructure.model_validate(
                analysis.edited_structure_json or analysis.structure_json
            )
            if analysis and (analysis.edited_structure_json or analysis.structure_json)
            else None
        ),
    )


def _upload_response(snapshot: DocumentJobSnapshot) -> DocumentUploadResponse:
    return DocumentUploadResponse(
        course_version=snapshot.version,
        document=DocumentResponse.model_validate(snapshot.document),
        job=_job_response(snapshot),
    )


def _job_response(snapshot: DocumentJobSnapshot) -> DocumentJobResponse:
    return DocumentJobResponse(
        id=snapshot.job.id,
        document_id=snapshot.document.id,
        course_version_id=snapshot.version.id,
        course_id=snapshot.course.id,
        version_number=snapshot.version.version_number,
        original_name=snapshot.document.original_name,
        version_status=snapshot.version.status,
        status=snapshot.job.status,
        progress=snapshot.job.progress,
        current_step=snapshot.job.current_step,
        retry_count=snapshot.job.retry_count,
        error_code=snapshot.job.error_code,
        error_detail=snapshot.job.error_detail,
        started_at=snapshot.job.started_at,
        finished_at=snapshot.job.finished_at,
        created_at=snapshot.job.created_at,
        updated_at=snapshot.job.updated_at,
    )
