from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from app.agents.learner.understanding_agent import LearnerUnderstandingError
from app.core.config import Settings
from app.core.llm_client import LLMClient
from app.models.content import (
    CourseVersionStatus,
    DocumentJobStatus,
)
from app.models.document_analysis import DocumentAnalysis
from app.schemas.content import DocumentStructure
from app.services.content_service import (
    CourseNotFoundError,
    _get_job_snapshot_without_access,
)
from app.services.document_analyzer import analyze_with_llm
from app.services.document_extractor import (
    DocumentExtractionError,
    OcrOptions,
    extract_text,
    fallback_structure,
)
from app.services.document_storage import LocalDocumentStorage


async def analyze_document_job(
    session_factory: Any,
    storage: LocalDocumentStorage,
    settings: Settings,
    job_id: UUID,
) -> dict[str, str | int]:
    async with session_factory() as session:
        snapshot = await _get_job_snapshot_without_access(session, job_id, lock=True)
        if snapshot.job.status in {
            DocumentJobStatus.COMPLETED.value,
            DocumentJobStatus.FAILED.value,
        }:
            return {"job_id": str(job_id), "status": snapshot.job.status}
        analysis = await session.scalar(
            select(DocumentAnalysis).where(
                DocumentAnalysis.course_version_id == snapshot.version.id
            )
        )
        if analysis is None:
            analysis = DocumentAnalysis(
                course_version_id=snapshot.version.id,
                document_id=snapshot.document.id,
                status="processing",
            )
            session.add(analysis)
        else:
            analysis.status = "processing"
        snapshot.job.status = DocumentJobStatus.ANALYZING.value
        snapshot.job.progress = 45
        snapshot.job.current_step = "extracting_text_or_ocr"
        snapshot.version.status = CourseVersionStatus.PROCESSING.value
        await session.commit()

    try:
        text = extract_text(
            storage.path_for(snapshot.document.storage_key),
            snapshot.document.content_type,
            settings.document_analysis_output_chars,
            ocr=OcrOptions(
                enabled=settings.document_ocr_enabled,
                languages=settings.document_ocr_languages,
                dpi=settings.document_ocr_dpi,
                max_pages=settings.document_ocr_max_pages,
                min_text_chars=settings.document_ocr_min_text_chars,
                min_confidence=settings.document_ocr_min_confidence,
            ),
        )
        structure = fallback_structure(text, snapshot.document.original_name)
        llm_input_text = text[: settings.document_analysis_input_chars]
        provider_name = "fallback"
        model_name = None
        if settings.llm_api_key and settings.llm_model:
            provider = LLMClient(
                gemini_api_keys=settings.gemini_api_keys,
                groq_api_keys=settings.llm_api_keys,
                groq_base_url=settings.llm_base_url,
                groq_model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )
            try:
                structure = await analyze_with_llm(
                    provider,
                    llm_input_text,
                    snapshot.document.original_name,
                )
                provider_name = settings.llm_base_url
                model_name = settings.llm_model
            except (LearnerUnderstandingError, ValidationError):
                # The extracted text and deterministic structure remain useful
                # when an external LLM is unavailable or returns invalid JSON.
                provider_name = "fallback"
        await _complete_analysis(
            session_factory,
            job_id,
            text=text,
            llm_input_text=llm_input_text,
            structure=structure,
            provider=provider_name,
            model=model_name,
        )
        return {"job_id": str(job_id), "status": DocumentJobStatus.COMPLETED.value}
    except DocumentExtractionError as error:
        await _fail_analysis(session_factory, job_id, "EXTRACTION_FAILED", str(error))
        return {"job_id": str(job_id), "status": DocumentJobStatus.FAILED.value}
    except Exception as error:  # noqa: BLE001 - persist unexpected worker failures
        await _fail_analysis(session_factory, job_id, "ANALYSIS_FAILED", str(error))
        return {"job_id": str(job_id), "status": DocumentJobStatus.FAILED.value}


async def get_analysis(
    session_factory: Any,
    course_version_id: UUID,
) -> DocumentAnalysis | None:
    async with session_factory() as session:
        return await session.scalar(
            select(DocumentAnalysis).where(
                DocumentAnalysis.course_version_id == course_version_id
            )
        )


async def _complete_analysis(
    session_factory: Any,
    job_id: UUID,
    *,
    text: str,
    llm_input_text: str,
    structure: DocumentStructure,
    provider: str,
    model: str | None,
) -> None:
    async with session_factory() as session:
        snapshot = await _get_job_snapshot_without_access(session, job_id, lock=True)
        analysis = await session.scalar(
            select(DocumentAnalysis).where(
                DocumentAnalysis.course_version_id == snapshot.version.id
            )
        )
        if analysis is None:
            raise CourseNotFoundError
        analysis.status = "completed"
        analysis.source_characters = len(text)
        analysis.extracted_text = text
        analysis.llm_input_text = llm_input_text
        analysis.structure_json = structure.model_dump(mode="json")
        analysis.provider = provider
        analysis.model = model
        analysis.error_code = None
        analysis.error_detail = None
        snapshot.job.status = DocumentJobStatus.COMPLETED.value
        snapshot.job.progress = 100
        snapshot.job.current_step = "analysis_completed"
        snapshot.job.finished_at = datetime.now(UTC)
        snapshot.version.status = CourseVersionStatus.READY_FOR_REVIEW.value
        await session.commit()


async def _fail_analysis(
    session_factory: Any,
    job_id: UUID,
    code: str,
    detail: str,
) -> None:
    async with session_factory() as session:
        snapshot = await _get_job_snapshot_without_access(session, job_id, lock=True)
        analysis = await session.scalar(
            select(DocumentAnalysis).where(
                DocumentAnalysis.course_version_id == snapshot.version.id
            )
        )
        if analysis is not None:
            analysis.status = "failed"
            analysis.error_code = code
            analysis.error_detail = detail[:2000]
        snapshot.job.status = DocumentJobStatus.FAILED.value
        snapshot.job.current_step = "analysis_failed"
        snapshot.job.error_code = code
        snapshot.job.error_detail = detail[:2000]
        snapshot.job.finished_at = datetime.now(UTC)
        snapshot.version.status = CourseVersionStatus.FAILED.value
        snapshot.version.failure_code = code
        snapshot.version.failure_detail = detail[:2000]
        await session.commit()
